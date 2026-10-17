#!/usr/bin/env python3
"""
bookmark_sync.py — one-way bookmark mirror with Google Chrome as the master copy.

    Chrome  ──►  Chromium, Microsoft Edge, Brave   (Chromium-family JSON "Bookmarks" file)
            ──►  Firefox                            (places.sqlite)

Chrome is never written to. Each target is made to match Chrome exactly:
bookmarks that exist only in a target are removed (a backup is taken first).

Root mapping
    Chrome "Bookmarks bar"     → Chromium/Edge/Brave bar   → Firefox "Bookmarks Toolbar"
    Chrome "Other bookmarks"   → Other bookmarks           → Firefox "Other Bookmarks"
    Chrome "Mobile bookmarks"  → Mobile bookmarks          → Firefox "Mobile Bookmarks"
    Firefox "Bookmarks Menu" has no Chrome equivalent: left alone by default
    (--firefox-menu clear empties it so Firefox is a pure mirror).

Safety rules
    * A target is only written while that browser is CLOSED (it would overwrite
      the file on exit otherwise). Running targets are skipped and retried
      (in --watch mode) until they close.
    * Every write is preceded by a timestamped backup; the newest N are kept.
    * Nothing is written when the target already matches Chrome.
    * --dry-run reports what would change without touching anything.

Requirements: Python 3.8+, standard library only. Linux, macOS and Windows.
"""
from __future__ import annotations

import argparse
import configparser
import json
import logging
import os
import platform
import secrets
import base64
import shutil
import socket
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

__version__ = "1.3.1"

SYSTEM = platform.system()  # "Linux" | "Darwin" | "Windows"
HOME = Path.home()
STATE_DIR = HOME / ".bookmark_sync"
log = logging.getLogger("bookmark_sync")

# --------------------------------------------------------------------------- #
#  Browser locations                                                          #
# --------------------------------------------------------------------------- #

def _env_path(var: str, fallback: Path) -> Path:
    v = os.environ.get(var)
    return Path(v) if v else fallback


LOCALAPPDATA = _env_path("LOCALAPPDATA", HOME / "AppData" / "Local")
APPDATA = _env_path("APPDATA", HOME / "AppData" / "Roaming")
MAC_AS = HOME / "Library" / "Application Support"

# Candidate "User Data" directories for Chromium-family browsers, first existing wins.
CHROMIUM_FAMILY_DIRS: Dict[str, Dict[str, List[Path]]] = {
    "chrome": {
        "Linux": [HOME / ".config/google-chrome",
                  HOME / ".var/app/com.google.Chrome/config/google-chrome"],
        "Darwin": [MAC_AS / "Google/Chrome"],
        "Windows": [LOCALAPPDATA / "Google/Chrome/User Data"],
    },
    "chromium": {
        "Linux": [HOME / ".config/chromium",
                  HOME / "snap/chromium/common/chromium",
                  HOME / ".var/app/org.chromium.Chromium/config/chromium"],
        "Darwin": [MAC_AS / "Chromium"],
        "Windows": [LOCALAPPDATA / "Chromium/User Data"],
    },
    "edge": {
        "Linux": [HOME / ".config/microsoft-edge"],
        "Darwin": [MAC_AS / "Microsoft Edge"],
        "Windows": [LOCALAPPDATA / "Microsoft/Edge/User Data"],
    },
    "brave": {
        "Linux": [HOME / ".config/BraveSoftware/Brave-Browser",
                  HOME / "snap/brave/current/.config/BraveSoftware/Brave-Browser",
                  HOME / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser"],
        "Darwin": [MAC_AS / "BraveSoftware/Brave-Browser"],
        "Windows": [LOCALAPPDATA / "BraveSoftware/Brave-Browser/User Data"],
    },
}

FIREFOX_BASE_DIRS: Dict[str, List[Path]] = {
    "Linux": [HOME / ".mozilla/firefox",
              HOME / ".config/mozilla/firefox",            # newer XDG layout
              HOME / "snap/firefox/common/.mozilla/firefox",
              HOME / ".var/app/org.mozilla.firefox/.mozilla/firefox"],
    "Darwin": [MAC_AS / "Firefox"],
    "Windows": [APPDATA / "Mozilla/Firefox"],
}

DISPLAY = {"chrome": "Chrome", "chromium": "Chromium", "edge": "Edge",
           "brave": "Brave", "firefox": "Firefox"}

# --------------------------------------------------------------------------- #
#  Neutral bookmark tree                                                      #
# --------------------------------------------------------------------------- #

ROOTS = ("toolbar", "other", "mobile")
SEPARATOR_URL = "\x00separator"          # Firefox-only; Chrome has no separators
CHROME_EPOCH_OFFSET_US = 11_644_473_600 * 1_000_000   # 1601-01-01 → 1970-01-01


@dataclass
class Node:
    title: str
    url: Optional[str] = None             # None means folder
    children: List["Node"] = field(default_factory=list)
    added_us: int = 0                     # Unix epoch, microseconds

    @property
    def is_folder(self) -> bool:
        return self.url is None

    def signature(self) -> tuple:
        """Structure used for equality: titles, URLs, order. Ignores ids/dates and
        leading/trailing spaces in titles (Firefox trims them; Chrome keeps them)."""
        if self.is_folder:
            return ("F", self.title.strip(), tuple(c.signature() for c in self.children))
        return ("B", self.title.strip(), self.url)


Tree = Dict[str, Node]   # root key → folder Node


def tree_signature(tree: Tree, roots=ROOTS) -> tuple:
    """Contents of each top-level folder. The top-level folders' own names are
    left out: each browser names them itself (Edge: "Favorites bar")."""
    return tuple(tree[r].signature()[2] if r in tree else () for r in roots)


def flatten(tree: Tree, roots=ROOTS) -> set:
    """Set of (path, title, url) used to describe differences to the user."""
    out = set()

    def walk(n: Node, path: str):
        for c in n.children:
            if c.is_folder:
                walk(c, f"{path}/{c.title.strip()}")
            elif c.url != SEPARATOR_URL:
                out.add((path, c.title.strip(), c.url))

    for r in roots:
        if r in tree:
            walk(tree[r], r)
    return out


def folder_contents(tree: Tree, roots=ROOTS) -> Dict[str, list]:
    """Folder path → ordered list of what it directly contains."""
    out: Dict[str, list] = {}

    def walk(n: Node, path: str):
        out[path] = [("F", c.title.strip()) if c.is_folder else ("B", c.title.strip(), c.url)
                     for c in n.children if c.url != SEPARATOR_URL]
        for c in n.children:
            if c.is_folder:
                walk(c, f"{path}/{c.title.strip()}")

    for r in roots:
        if r in tree:
            walk(tree[r], r)
    return out


def count(tree: Tree, roots=ROOTS) -> Tuple[int, int]:
    b = f = 0

    def walk(n: Node):
        nonlocal b, f
        for c in n.children:
            if c.is_folder:
                f += 1
                walk(c)
            elif c.url != SEPARATOR_URL:
                b += 1

    for r in roots:
        if r in tree:
            walk(tree[r])
    return b, f


SHOW_ALL = False      # set by --all: list every change instead of a sample


def describe_diff(name: str, current: Tree, wanted: Tree, roots=ROOTS, sample: int = 8):
    """Explain what a sync will change, sorted into four kinds:
         +  new      in Chrome, not in this browser
         -  removed  in this browser only — will be deleted
         >  moved    same title + URL, different folder
         ~  renamed  same folder + URL, different title
       plus folder-level changes: ↕ reordered, empty folders, ≠ duplicate copies"""
    cur, new = flatten(current, roots), flatten(wanted, roots)
    added, removed = new - cur, cur - new

    def pair_up(key_of):
        """Match removed items to added items that share key_of(item)."""
        pool: Dict[tuple, list] = {}
        for item in sorted(removed):
            pool.setdefault(key_of(item), []).append(item)
        pairs = []
        for item in sorted(added):
            olds = pool.get(key_of(item))
            if olds:
                pairs.append((olds.pop(0), item))
        for old, item in pairs:
            removed.discard(old)
            added.discard(item)
        return pairs

    moved = pair_up(lambda it: (it[1], it[2]))      # same title + url
    renamed = pair_up(lambda it: (it[0], it[2]))    # same folder + url

    # Folder-level differences that the bookmark comparison above can't see:
    # reordering, empty folders, duplicate copies of the same bookmark.
    cur_f, new_f = folder_contents(current, roots), folder_contents(wanted, roots)
    folders_added = sorted(p for p in new_f if p not in cur_f)
    folders_removed = sorted(p for p in cur_f if p not in new_f)
    reordered, dupes = [], []
    for p in sorted(set(cur_f) & set(new_f)):
        a, b = cur_f[p], new_f[p]
        if a != b:
            (reordered if sorted(a) == sorted(b) else dupes).append(p)
    # A folder whose contents changed for an already-listed reason isn't "reordered".
    explained = {it[0] for it in added | removed} | {o[0] for o, _ in moved + renamed} \
        | {n[0] for _, n in moved + renamed}
    dupes = [p for p in dupes if p not in explained and not any(
        f.startswith(p + "/") for f in folders_added + folders_removed)]

    extra = []
    if reordered:
        extra.append(f"↕{len(reordered)} folder(s) reordered")
    if folders_added or folders_removed:
        extra.append(f"folders +{len(folders_added)} -{len(folders_removed)}")
    if dupes:
        extra.append(f"≠{len(dupes)} with duplicate copies")
    log.info("  %s: +%d new, -%d removed, >%d moved, ~%d renamed%s", name,
             len(added), len(removed), len(moved), len(renamed),
             (", " + ", ".join(extra)) if extra else "")
    limit = None if SHOW_ALL else sample

    def show(tag, lines):
        for line in lines[:limit]:
            log.info("      %s %s", tag, line)
        if limit is not None and len(lines) > limit:
            log.info("      %s … and %d more (add --all to list every change)",
                     tag, len(lines) - limit)

    show("+", [f"{p}/{t or '(untitled)'}  <{u}>" for p, t, u in sorted(added)])
    show("-", [f"{p}/{t or '(untitled)'}  <{u}>" for p, t, u in sorted(removed)])
    show(">", [f"{t}:  {o[0]}  →  {n[0]}" for o, n in moved for t in [n[1] or "(untitled)"]])
    show("~", [f"{o[0]}:  \"{o[1]}\"  →  \"{n[1]}\"" for o, n in renamed])
    show("↕", [f"{p}  (put back in Chrome's order)" for p in reordered])
    show("+", [f"{p}/  (empty folder)" for p in folders_added
               if not any(it[0].startswith(p) for it in added)])
    show("-", [f"{p}/  (empty folder)" for p in folders_removed
               if not any(it[0].startswith(p) for it in removed)])
    show("≠", [f"{p}  (has a different number of copies of a bookmark)" for p in dupes])


# --------------------------------------------------------------------------- #
#  Saving bookmarks that only a target has (importable HTML)                  #
# --------------------------------------------------------------------------- #

ROOT_LABELS = {"toolbar": "Bookmarks bar", "other": "Other bookmarks",
               "mobile": "Mobile bookmarks", "menu": "Bookmarks menu"}


def urls_in(tree: Tree) -> set:
    return {u for _, _, u in flatten(tree, tuple(tree))}


def extras(tree: Tree, known_urls: set) -> Tree:
    """Copy of `tree` keeping only bookmarks whose URL is not in known_urls
    (with the folders that lead to them)."""
    def prune(n: Node) -> Node:
        kids = []
        for c in n.children:
            if c.is_folder:
                p = prune(c)
                if p.children:
                    kids.append(p)
            elif c.url != SEPARATOR_URL and c.url not in known_urls:
                kids.append(c)
        return Node(n.title, None, kids, n.added_us)
    return {r: prune(n) for r, n in tree.items()}


def write_bookmarks_html(tree: Tree, out: Path, heading: str) -> int:
    """Write the standard bookmarks.html format that every browser can import
    (Chrome: Bookmark manager ⋮ → Import bookmarks). Returns bookmarks written."""
    from html import escape
    lines = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
             '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
             "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>", "<DL><p>",
             f"    <DT><H3>{escape(heading)}</H3>", "    <DL><p>"]
    written = 0

    def emit(n: Node, depth: int):
        nonlocal written
        pad = "    " * depth
        for c in n.children:
            if c.is_folder:
                lines.append(f"{pad}<DT><H3>{escape(c.title)}</H3>")
                lines.append(f"{pad}<DL><p>")
                emit(c, depth + 1)
                lines.append(f"{pad}</DL><p>")
            else:
                added = (c.added_us or now_us()) // 1_000_000
                lines.append(f'{pad}<DT><A HREF="{escape(c.url)}" ADD_DATE="{added}">'
                             f"{escape(c.title or c.url)}</A>")
                written += 1

    for r, n in tree.items():
        if n.children:
            lines += [f"        <DT><H3>{escape(ROOT_LABELS.get(r, r))}</H3>", "        <DL><p>"]
            emit(n, 3)
            lines.append("        </DL><p>")
    lines += ["    </DL><p>", "</DL><p>", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return written


def save_removed(browser: str, current: Tree, master: Tree, opts: "Options") -> Optional[Path]:
    """Before a sync deletes bookmarks that exist only in `browser`, save them
    to an importable HTML file so nothing is lost by accident."""
    only_here = extras(current, urls_in(master))
    if not any(n.children for n in only_here.values()):
        return None
    out = opts.backup_dir / "removed" / f"{browser}-removed-{_stamp()}.html"
    n = write_bookmarks_html(only_here, out, f"Removed from {DISPLAY[browser]} {_stamp()}")
    log.info("  %s: %d bookmark(s) only it had were saved to %s", DISPLAY[browser], n, out)
    return out


# --------------------------------------------------------------------------- #
#  Chromium-family JSON format (Chrome, Chromium, Edge, Brave)               #
# --------------------------------------------------------------------------- #

CHROME_ROOT_KEYS = {"toolbar": "bookmark_bar", "other": "other", "mobile": "synced"}


def chrome_to_unix_us(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return n - CHROME_EPOCH_OFFSET_US if n > CHROME_EPOCH_OFFSET_US else 0


def unix_to_chrome_us(us: int) -> str:
    if not us:
        us = int(time.time() * 1_000_000)
    return str(us + CHROME_EPOCH_OFFSET_US)


def _from_chrome_json(d: dict) -> Node:
    if d.get("type") == "url":
        return Node(d.get("name", ""), d.get("url", ""), [], chrome_to_unix_us(d.get("date_added")))
    return Node(d.get("name", ""), None,
                [_from_chrome_json(c) for c in d.get("children", [])],
                chrome_to_unix_us(d.get("date_added")))


def read_chrome_json(path: Path) -> Tuple[Tree, dict]:
    """Returns (tree, raw_document)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    roots = doc.get("roots", {})
    tree: Tree = {}
    for r, key in CHROME_ROOT_KEYS.items():
        tree[r] = _from_chrome_json(roots[key]) if key in roots else Node(r)
    return tree, doc


def _dedupe(children: List[Node]) -> List[Node]:
    seen, out = set(), []
    for c in children:
        s = c.signature()
        if s not in seen:
            seen.add(s)
            out.append(c)
    return out


def merge_account_tree(local: Tree, account: Tree) -> Tree:
    """Chrome keeps 'saved to your Google Account' bookmarks in AccountBookmarks.
    The Chrome UI shows both; the mirror gets account items first, then local,
    with exact duplicates dropped."""
    merged: Tree = {}
    for r in ROOTS:
        lr, ar = local.get(r, Node(r)), account.get(r, Node(r))
        merged[r] = Node(lr.title or ar.title, None, _dedupe(ar.children + lr.children), lr.added_us)
    return merged


class _IdGen:
    def __init__(self, start: int):
        self.n = start

    def __call__(self) -> str:
        self.n += 1
        return str(self.n)


def _to_chrome_json(n: Node, next_id: _IdGen) -> dict:
    added = unix_to_chrome_us(n.added_us)
    base = {"date_added": added, "date_last_used": "0",
            "guid": str(uuid.uuid4()), "id": next_id(), "name": n.title}
    if n.is_folder:
        base.update(type="folder", date_modified=added,
                    children=[_to_chrome_json(c, next_id) for c in n.children
                              if c.url != SEPARATOR_URL])
    else:
        base.update(type="url", url=n.url)
    return base


DEFAULT_ROOT_META = {
    "bookmark_bar": {"id": "1", "name": "Bookmarks bar",
                     "guid": "0bc5d13f-2cba-5d74-951f-3f233fe6c908"},
    "other": {"id": "2", "name": "Other bookmarks",
              "guid": "82b081ec-3dd3-529c-8475-ab6c344590dd"},
    "synced": {"id": "3", "name": "Mobile bookmarks",
               "guid": "4cf2e351-0e85-532b-bb37-df045d8f8d0f"},
}


def build_chrome_document(tree: Tree, template_doc: Optional[dict]) -> dict:
    """Build a Bookmarks JSON document. Root folder metadata (id, guid, name)
    is copied from the target's own existing file when available so the
    browser recognises its permanent folders."""
    troots = (template_doc or {}).get("roots", {})
    roots_out = {}
    root_ids = []
    for key in CHROME_ROOT_KEYS.values():
        meta = {k: v for k, v in troots.get(key, {}).items() if k != "children"} \
            or dict(DEFAULT_ROOT_META[key])
        meta.setdefault("date_added", unix_to_chrome_us(0))
        meta.setdefault("date_last_used", "0")
        meta["date_modified"] = unix_to_chrome_us(0)
        meta["type"] = "folder"
        roots_out[key] = meta
        try:
            root_ids.append(int(meta.get("id", 0)))
        except ValueError:
            pass
    next_id = _IdGen(max(root_ids + [3]))
    for r, key in CHROME_ROOT_KEYS.items():
        roots_out[key]["children"] = [_to_chrome_json(c, next_id) for c in tree[r].children
                                      if c.url != SEPARATOR_URL]
    # No "checksum" key: Chromium skips verification when it is absent.
    # No "sync_metadata": that belongs to the target's own sync state.
    return {"roots": roots_out, "version": 1}


# --------------------------------------------------------------------------- #
#  Is a browser running?                                                      #
# --------------------------------------------------------------------------- #

def chromium_family_running(user_data_dir: Path) -> bool:
    """Chromium-family browsers hold a per-profile-directory lock while running."""
    if SYSTEM == "Windows":
        lock = user_data_dir / "lockfile"         # opened exclusively, deleted on exit
        if not lock.exists():
            return False
        try:
            with open(lock, "a"):
                return False                      # stale lock left by a crash
        except OSError:
            return True
    lock = user_data_dir / "SingletonLock"        # symlink → "hostname-pid"
    if not os.path.lexists(lock):
        return False
    try:
        target = os.readlink(lock)
    except OSError:
        return True
    host, _, pid = target.rpartition("-")
    if host and host != socket.gethostname():
        return True                               # can't check another host; be safe
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError):
        return True


def firefox_locked(places: Path) -> bool:
    """Firefox opens places.sqlite in exclusive locking mode while it runs."""
    try:
        con = sqlite3.connect(str(places), timeout=0.5, isolation_level=None)
        try:
            con.execute("BEGIN EXCLUSIVE")
            con.execute("ROLLBACK")
            return False
        finally:
            con.close()
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower() or "busy" in str(e).lower():
            return True
        raise


# --------------------------------------------------------------------------- #
#  Backups                                                                     #
# --------------------------------------------------------------------------- #

def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _prune(folder: Path, keep: int):
    files = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def backup_file(src: Path, backup_root: Path, browser: str, keep: int) -> Optional[Path]:
    if not src.exists():
        return None
    folder = backup_root / browser
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / f"{src.name}-{_stamp()}"
    shutil.copy2(src, dst)
    _prune(folder, keep)
    return dst


def backup_sqlite(src: Path, backup_root: Path, browser: str, keep: int) -> Path:
    folder = backup_root / browser
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / f"places-{_stamp()}.sqlite"
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(dst))
    try:
        s.backup(d)                               # consistent copy incl. WAL contents
    finally:
        d.close()
        s.close()
    _prune(folder, keep)
    return dst


# --------------------------------------------------------------------------- #
#  Firefox (places.sqlite)                                                    #
# --------------------------------------------------------------------------- #

FF_ROOT_GUIDS = {"toolbar": "toolbar_____", "other": "unfiled_____",
                 "mobile": "mobile______", "menu": "menu________"}
FF_TYPE_BOOKMARK, FF_TYPE_FOLDER, FF_TYPE_SEPARATOR = 1, 2, 3
FF_SYNC_STATUS_NEW, FF_SYNC_STATUS_NORMAL = 1, 2
_GOLDEN = 0x9E3779B9


def _moz_hash(data: bytes) -> int:
    """mozilla::HashString — golden-ratio rotate/xor/multiply over (signed) chars."""
    h = 0
    for c in data:
        if c >= 0x80:
            c |= 0xFFFFFF00                       # char is signed on Firefox builds
        h = (_GOLDEN * ((((h << 5) | (h >> 27)) & 0xFFFFFFFF) ^ c)) & 0xFFFFFFFF
    return h


def moz_url_hash(url: str) -> int:
    """Equivalent of Places' SQL hash(url): 16-bit scheme hash << 32 + 32-bit url hash."""
    data = url.encode("utf-8")[:1500]
    i = data.find(b":")
    if i == -1:
        return _moz_hash(data)
    return ((_moz_hash(data[:i]) & 0xFFFF) << 32) + _moz_hash(data)


def moz_guid() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(9)).decode("ascii")   # 12 chars


def now_us() -> int:
    return int(time.time() * 1_000_000)


def find_firefox_profile(base: Path) -> Optional[Path]:
    ini = base / "profiles.ini"
    if not ini.exists():
        return None
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read(ini, encoding="utf-8")

    def resolve(path: str, relative: bool) -> Path:
        return (base / path) if relative else Path(path)

    rel_of = {}
    candidates: List[Path] = []
    for sec in cp.sections():
        if sec.startswith("Profile") and cp.has_option(sec, "Path"):
            p = cp.get(sec, "Path")
            rel = cp.get(sec, "IsRelative", fallback="1") == "1"
            rel_of[p] = rel
            if cp.get(sec, "Default", fallback="0") == "1":
                candidates.insert(0, resolve(p, rel))
            else:
                candidates.append(resolve(p, rel))
    # Modern Firefox: the [Install<hash>] section names the profile actually used.
    for sec in cp.sections():
        if sec.startswith("Install") and cp.has_option(sec, "Default"):
            p = cp.get(sec, "Default")
            candidates.insert(0, resolve(p, rel_of.get(p, not os.path.isabs(p))))
    for c in candidates:
        if (c / "places.sqlite").exists():
            return c
    return None


class FirefoxDB:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self._cols: Dict[str, set] = {}

    def cols(self, table: str) -> set:
        if table not in self._cols:
            self._cols[table] = {r[1] for r in self.con.execute(f"PRAGMA table_info({table})")}
        return self._cols[table]

    def has_table(self, table: str) -> bool:
        return bool(self.cols(table))

    def insert(self, table: str, values: dict) -> int:
        v = {k: x for k, x in values.items() if k in self.cols(table)}
        sql = f"INSERT INTO {table} ({', '.join(v)}) VALUES ({', '.join('?' * len(v))})"
        return self.con.execute(sql, tuple(v.values())).lastrowid

    def root_id(self, guid: str) -> Optional[int]:
        row = self.con.execute("SELECT id FROM moz_bookmarks WHERE guid=?", (guid,)).fetchone()
        return row[0] if row else None

    # ---- read ------------------------------------------------------------- #
    def read_children(self, parent_id: int) -> List[Node]:
        rows = self.con.execute(
            "SELECT b.id, b.type, b.title, p.url, b.dateAdded FROM moz_bookmarks b "
            "LEFT JOIN moz_places p ON p.id = b.fk WHERE b.parent=? ORDER BY b.position, b.id",
            (parent_id,)).fetchall()
        out = []
        for bid, typ, title, url, added in rows:
            if typ == FF_TYPE_FOLDER:
                out.append(Node(title or "", None, self.read_children(bid), added or 0))
            elif typ == FF_TYPE_SEPARATOR:
                out.append(Node("", SEPARATOR_URL))
            else:
                out.append(Node(title or "", url or "", [], added or 0))
        return out

    def read_tree(self) -> Tree:
        tree: Tree = {}
        for r, guid in FF_ROOT_GUIDS.items():
            rid = self.root_id(guid)
            tree[r] = Node(r, None, self.read_children(rid) if rid else [])
        return tree

    # ---- delete ----------------------------------------------------------- #
    def clear_children(self, parent_id: int) -> set:
        rows = self.con.execute(
            "WITH RECURSIVE d(id) AS (SELECT id FROM moz_bookmarks WHERE parent=? "
            "UNION ALL SELECT b.id FROM moz_bookmarks b JOIN d ON b.parent = d.id) "
            "SELECT b.id, b.guid, b.fk, b.syncStatus FROM moz_bookmarks b JOIN d ON b.id = d.id",
            (parent_id,)).fetchall()
        if not rows:
            return set()
        ts = now_us()
        if self.has_table("moz_bookmarks_deleted"):
            # Tombstones so Firefox Sync propagates the deletions to other devices.
            self.con.executemany(
                "INSERT OR REPLACE INTO moz_bookmarks_deleted (guid, dateRemoved) VALUES (?, ?)",
                [(g, ts) for _, g, _, st in rows if st == FF_SYNC_STATUS_NORMAL and g])
        ids = [r[0] for r in rows]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            if self.has_table("moz_items_annos"):
                self.con.execute(f"DELETE FROM moz_items_annos WHERE item_id IN ({marks})", chunk)
            self.con.execute(f"DELETE FROM moz_bookmarks WHERE id IN ({marks})", chunk)
        return {r[2] for r in rows if r[2]}

    # ---- places ----------------------------------------------------------- #
    def origin_id(self, url: str) -> Optional[int]:
        if not self.has_table("moz_origins"):
            return None
        scheme, sep, rest = url.partition(":")
        if not sep:
            return None
        if rest.startswith("//"):
            prefix = scheme.lower() + "://"
            parts = urlsplit(url)
            host = (parts.hostname or "")
            if parts.port:
                host = f"{host}:{parts.port}"
        else:
            prefix, host = scheme.lower() + ":", ""
        row = self.con.execute("SELECT id FROM moz_origins WHERE prefix=? AND host=?",
                               (prefix, host)).fetchone()
        if row:
            return row[0]
        return self.insert("moz_origins", {"prefix": prefix, "host": host, "frecency": 1,
                                           "recalc_frecency": 1, "recalc_alt_frecency": 1})

    def place_id(self, url: str, title: str) -> int:
        h = moz_url_hash(url)
        row = self.con.execute("SELECT id FROM moz_places WHERE url_hash=? AND url=?",
                               (h, url)).fetchone()
        if row is None:  # tolerate rows written with an unexpected hash
            row = self.con.execute("SELECT id FROM moz_places WHERE url=?", (url,)).fetchone()
        if row:
            return row[0]
        host = (urlsplit(url).hostname or "")
        return self.insert("moz_places", {
            "url": url, "title": title or None, "rev_host": host[::-1] + ".",
            "visit_count": 0, "hidden": 0, "typed": 0, "frecency": 1,
            "foreign_count": 1, "url_hash": h, "guid": moz_guid(),
            "origin_id": self.origin_id(url),
            "recalc_frecency": 1, "recalc_alt_frecency": 1,
        })

    # ---- insert ----------------------------------------------------------- #
    def insert_children(self, parent_id: int, nodes: List[Node], places: set):
        for pos, n in enumerate(nodes):
            added = n.added_us or now_us()
            common = {"parent": parent_id, "position": pos, "title": n.title.strip(),
                      "dateAdded": added, "lastModified": now_us(), "guid": moz_guid(),
                      "syncStatus": FF_SYNC_STATUS_NEW, "syncChangeCounter": 1}
            if n.is_folder:
                fid = self.insert("moz_bookmarks", {"type": FF_TYPE_FOLDER, "fk": None, **common})
                self.insert_children(fid, n.children, places)
            elif n.url != SEPARATOR_URL:
                pid = self.place_id(n.url, n.title)
                places.add(pid)
                self.insert("moz_bookmarks", {"type": FF_TYPE_BOOKMARK, "fk": pid, **common})

    def fix_foreign_counts(self, place_ids: set):
        """Places' own triggers keep foreign_count right only while Firefox runs;
        a bookmarked page with foreign_count = 0 could be expired, so fix it here."""
        kw = "+ (SELECT COUNT(*) FROM moz_keywords k WHERE k.place_id = moz_places.id)" \
            if self.has_table("moz_keywords") else ""
        ids = list(place_ids)
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            self.con.execute(
                "UPDATE moz_places SET foreign_count = "
                f"(SELECT COUNT(*) FROM moz_bookmarks b WHERE b.fk = moz_places.id) {kw} "
                f"WHERE id IN ({','.join('?' * len(chunk))})", chunk)

    def touch_root(self, root_id: int):
        self.con.execute("UPDATE moz_bookmarks SET lastModified=?, "
                         "syncChangeCounter = syncChangeCounter + 1 WHERE id=?",
                         (now_us(), root_id))


# --------------------------------------------------------------------------- #
#  Sync operations                                                            #
# --------------------------------------------------------------------------- #

@dataclass
class Options:
    dry_run: bool = False
    backup_dir: Path = STATE_DIR / "backups"
    keep_backups: int = 10
    firefox_menu: str = "keep"          # keep | clear
    include_account: bool = True
    dirs: Dict[str, Path] = field(default_factory=dict)       # overrides
    profiles: Dict[str, str] = field(default_factory=dict)    # chromium-family profile names


RESULT_OK, RESULT_UNCHANGED, RESULT_SKIPPED, RESULT_MISSING, RESULT_ERROR = \
    "updated", "already in sync", "skipped (browser running)", "not found", "error"


def chromium_family_paths(browser: str, opts: Options) -> Tuple[Optional[Path], Optional[Path]]:
    """Returns (user_data_dir, profile_dir)."""
    if browser in opts.dirs:
        udd = opts.dirs[browser]
    else:
        udd = next((p for p in CHROMIUM_FAMILY_DIRS[browser].get(SYSTEM, []) if p.exists()), None)
    if udd is None:
        return None, None
    profile = udd / opts.profiles.get(browser, "Default")
    return udd, profile


def load_master(opts: Options) -> Tuple[Tree, Path]:
    udd, prof = chromium_family_paths("chrome", opts)
    if prof is None or not (prof / "Bookmarks").exists():
        raise FileNotFoundError(
            "Chrome's Bookmarks file was not found. Open Chrome once, or pass "
            "--dir chrome=PATH / --profile chrome=NAME.")
    tree, _ = read_chrome_json(prof / "Bookmarks")
    acct = prof / "AccountBookmarks"
    if opts.include_account and acct.exists():
        try:
            atree, _ = read_chrome_json(acct)
            if any(atree[r].children for r in ROOTS):
                tree = merge_account_tree(tree, atree)
                log.debug("Merged Chrome AccountBookmarks")
        except (ValueError, KeyError) as e:
            log.warning("Could not read Chrome AccountBookmarks (%s); using local only", e)
    return tree, prof / "Bookmarks"


def sync_chromium_family(browser: str, master: Tree, opts: Options) -> str:
    name = DISPLAY[browser]
    udd, prof = chromium_family_paths(browser, opts)
    if prof is None or not prof.exists():
        log.info("%s: profile not found — skipping", name)
        return RESULT_MISSING
    target = prof / "Bookmarks"
    current_doc = None
    current: Tree = {r: Node(r) for r in ROOTS}
    if target.exists():
        try:
            current, current_doc = read_chrome_json(target)
        except (ValueError, KeyError) as e:
            log.warning("%s: existing Bookmarks file unreadable (%s); will replace", name, e)
    if tree_signature(current) == tree_signature(master):
        log.info("%s: %s", name, RESULT_UNCHANGED)
        return RESULT_UNCHANGED
    describe_diff(name, current, master)
    if opts.dry_run:
        return RESULT_OK
    if chromium_family_running(udd):
        log.info("%s: is running — close it and the change will be applied", name)
        return RESULT_SKIPPED
    bak = backup_file(target, opts.backup_dir, browser, opts.keep_backups)
    if bak:
        log.debug("%s: backup → %s", name, bak)
    save_removed(browser, current, master, opts)
    doc = build_chrome_document(master, current_doc)
    tmp = target.with_name("Bookmarks.sync-tmp")
    tmp.write_text(json.dumps(doc, indent=3, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)                       # atomic swap
    log.info("%s: %s", name, RESULT_OK)
    return RESULT_OK


def firefox_profile(opts: Options) -> Optional[Path]:
    if "firefox" in opts.dirs:
        return opts.dirs["firefox"]
    for base in FIREFOX_BASE_DIRS.get(SYSTEM, []):
        p = find_firefox_profile(base)
        if p:
            return p
    return None


def sync_firefox(master: Tree, opts: Options) -> str:
    prof = firefox_profile(opts)
    places = prof / "places.sqlite" if prof else None
    if places is None or not places.exists():
        log.info("Firefox: profile not found — skipping")
        return RESULT_MISSING
    if firefox_locked(places):
        log.info("Firefox: is running — close it and the change will be applied")
        return RESULT_SKIPPED

    roots = list(ROOTS) + (["menu"] if opts.firefox_menu == "clear" else [])
    wanted = dict(master)
    wanted["menu"] = Node("menu")

    con = sqlite3.connect(str(places), timeout=2, isolation_level=None)
    try:
        db = FirefoxDB(con)
        current = db.read_tree()
        changed = [r for r in roots if current[r].signature()[2] != wanted[r].signature()[2]]
        if not changed:
            log.info("Firefox: %s", RESULT_UNCHANGED)
            return RESULT_UNCHANGED
        describe_diff("Firefox", current, wanted, roots)
        if opts.dry_run:
            return RESULT_OK
        con.close()
        bak = backup_sqlite(places, opts.backup_dir, "firefox", opts.keep_backups)
        log.debug("Firefox: backup → %s", bak)
        save_removed("firefox", {r: current[r] for r in roots}, wanted, opts)

        con = sqlite3.connect(str(places), timeout=2, isolation_level=None)
        db = FirefoxDB(con)
        con.execute("BEGIN EXCLUSIVE")
        try:
            touched: set = set()
            for r in changed:
                rid = db.root_id(FF_ROOT_GUIDS[r])
                if rid is None:
                    raise RuntimeError(f"Firefox root '{FF_ROOT_GUIDS[r]}' missing")
                touched |= db.clear_children(rid)
                db.insert_children(rid, wanted[r].children, touched)
                db.touch_root(rid)
            db.fix_foreign_counts(touched)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        log.info("Firefox: %s (%s)", RESULT_OK, ", ".join(changed))
        return RESULT_OK
    finally:
        con.close()


def run_once(targets: List[str], opts: Options) -> Dict[str, str]:
    master, path = load_master(opts)
    b, f = count(master)
    log.info("Chrome master: %d bookmarks in %d folders  (%s)", b, f, path)
    results = {}
    for t in targets:
        try:
            if t == "firefox":
                results[t] = sync_firefox(master, opts)
            else:
                results[t] = sync_chromium_family(t, master, opts)
        except Exception as e:                    # one bad target must not stop the rest
            log.error("%s: %s: %s", DISPLAY[t], type(e).__name__, e)
            results[t] = RESULT_ERROR
    return results


def _files_fingerprint(files: List[Path]) -> tuple:
    fp = []
    for p in files:
        try:
            st = p.stat()
            fp.append((p.name, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(fp)


def chrome_fingerprint(opts: Options) -> tuple:
    _, prof = chromium_family_paths("chrome", opts)
    return _files_fingerprint([prof / "Bookmarks", prof / "AccountBookmarks"] if prof else [])


def target_fingerprint(target: str, opts: Options) -> tuple:
    """Changes whenever the browser itself rewrites its bookmarks."""
    if target == "firefox":
        prof = firefox_profile(opts)
        return _files_fingerprint([prof / "places.sqlite", prof / "places.sqlite-wal"]
                                  if prof else [])
    _, prof = chromium_family_paths(target, opts)
    return _files_fingerprint([prof / "Bookmarks"] if prof else [])


def target_running(target: str, opts: Options) -> bool:
    try:
        if target == "firefox":
            prof = firefox_profile(opts)
            places = prof / "places.sqlite" if prof else None
            return bool(places and places.exists() and firefox_locked(places))
        udd, _ = chromium_family_paths(target, opts)
        return bool(udd and chromium_family_running(udd))
    except Exception:
        return False                 # let the sync itself report the problem


def watch(targets: List[str], opts: Options, interval: int):
    """Re-sync a browser when Chrome's bookmarks change, or when that browser
    rewrites its own bookmarks (e.g. its own cloud sync reshuffled them).
    A browser that is open is noted once and synced as soon as it closes."""
    log.info("Watching every %ds: Chrome → %s (Ctrl+C to stop)",
             interval, ", ".join(DISPLAY[t] for t in targets))
    last_chrome = None
    last_target: Dict[str, tuple] = {}
    pending = set(targets)           # check everything at start-up
    announced = set()                # browsers already reported as open
    while True:
        try:
            chrome_fp = chrome_fingerprint(opts)
            if chrome_fp != last_chrome:
                pending |= set(targets)
                last_chrome = chrome_fp
            for t in targets:
                fp = target_fingerprint(t, opts)
                if t in last_target and fp != last_target[t]:
                    pending.add(t)
                last_target[t] = fp

            due = []
            for t in sorted(pending):
                if target_running(t, opts):
                    if t not in announced:
                        log.info("%s is open — will check it when it closes", DISPLAY[t])
                        announced.add(t)
                else:
                    due.append(t)
            if due:
                for t, r in run_once(due, opts).items():
                    if r in (RESULT_SKIPPED, RESULT_ERROR):
                        pending.add(t)
                    else:
                        pending.discard(t)
                        announced.discard(t)
                    last_target[t] = target_fingerprint(t, opts)   # ignore our own write
        except FileNotFoundError as e:
            log.error("%s", e)
        except Exception as e:
            log.exception("Unexpected error: %s", e)
        time.sleep(interval)


# --------------------------------------------------------------------------- #
#  CLI                                                                        #
# --------------------------------------------------------------------------- #

def list_browsers(opts: Options):
    print(f"bookmark_sync {__version__} on {SYSTEM}\n")
    for b in ("chrome", "chromium", "edge", "brave"):
        udd, prof = chromium_family_paths(b, opts)
        if prof and (prof / "Bookmarks").exists():
            running = "running" if chromium_family_running(udd) else "closed"
            profiles = sorted(p.name for p in udd.iterdir()
                              if (p / "Bookmarks").exists()) if udd else []
            print(f"  {DISPLAY[b]:<9} {running:<8} {prof / 'Bookmarks'}")
            if len(profiles) > 1:
                print(f"  {'':<18}profiles with bookmarks: {', '.join(profiles)}")
        else:
            print(f"  {DISPLAY[b]:<9} {'—':<8} not found")
    prof = firefox_profile(opts)
    if prof:
        state = "running" if firefox_locked(prof / "places.sqlite") else "closed"
        print(f"  {'Firefox':<9} {state:<8} {prof / 'places.sqlite'}")
    else:
        print(f"  {'Firefox':<9} {'—':<8} not found")


def rescue(source: str, opts: Options) -> int:
    """Find bookmarks in a backup (or any bookmarks file) whose URL is not in
    Chrome, and save them to an HTML file that can be imported into Chrome."""
    if source in DISPLAY and source != "chrome":
        folder = opts.backup_dir / source
        files = sorted((p for p in folder.glob("*") if p.is_file()),
                       key=lambda p: p.name, reverse=True) if folder.exists() else []
        if not files:
            log.error("No %s backups found in %s", DISPLAY[source], folder)
            return 1
        path, label = files[0], DISPLAY[source]
    else:
        path = Path(source).expanduser()
        label = path.name
        if not path.exists():
            log.error("File not found: %s", path)
            return 1
    try:
        if path.name.endswith(".sqlite"):
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                tree = FirefoxDB(con).read_tree()
            finally:
                con.close()
        else:
            tree, _ = read_chrome_json(path)
    except (ValueError, KeyError, sqlite3.Error) as e:
        log.error("Could not read %s: %s", path, e)
        return 1

    master, _ = load_master(opts)
    found = extras(tree, urls_in(master))
    items = sorted(flatten(found, tuple(found)))
    log.info("Checked %s", path)
    if not items:
        log.info("Nothing to rescue: every bookmark in it is already in Chrome.")
        return 0
    out = HOME / f"rescued-bookmarks-{source if source in DISPLAY else 'file'}-{_stamp()}.html"
    write_bookmarks_html(found, out, f"Rescued from {label} {datetime.now():%Y-%m-%d}")
    log.info("%d bookmark(s) are not in Chrome:", len(items))
    for p, t, u in items:
        log.info("  • %s/%s", p, t or u)
    log.info("\nSaved to %s", out)
    log.info("To add them to Chrome: open chrome://bookmarks → ⋮ (top right) → "
             "Import bookmarks → choose that file.\nThey arrive in a folder under "
             "Other bookmarks; drag the ones you want where they belong and delete the rest.")
    return 0


def _kv(items: List[str], flag: str) -> Dict[str, str]:
    out = {}
    for it in items or []:
        k, sep, v = it.partition("=")
        if not sep or k not in DISPLAY:
            sys.exit(f"{flag} expects BROWSER=VALUE with BROWSER in {', '.join(DISPLAY)}")
        out[k] = v
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Mirror Google Chrome bookmarks into Chromium, Edge, Brave and Firefox.")
    ap.add_argument("--targets", default="chromium,firefox",
                    help="comma list from: chromium, edge, brave, firefox (default: chromium,firefox)")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    ap.add_argument("--rescue", metavar="SOURCE",
                    help="save bookmarks that are not in Chrome from a browser's newest backup "
                         "(e.g. edge) or a bookmarks file, as HTML you can import into Chrome")
    ap.add_argument("--all", action="store_true",
                    help="list every change (default shows 8 of each kind)")
    ap.add_argument("--watch", type=int, metavar="SECONDS",
                    help="keep running; re-sync when Chrome changes or a skipped browser closes")
    ap.add_argument("--list", action="store_true", help="show detected browsers and exit")
    ap.add_argument("--profile", action="append", metavar="BROWSER=NAME",
                    help="Chromium-family profile folder, e.g. chrome='Profile 1' (default Default)")
    ap.add_argument("--dir", action="append", metavar="BROWSER=PATH",
                    help="override location: Chromium-family 'User Data' dir, or Firefox profile dir")
    ap.add_argument("--firefox-menu", choices=("keep", "clear"), default="keep",
                    help="Firefox Bookmarks Menu has no Chrome equivalent (default: keep)")
    ap.add_argument("--no-account-bookmarks", action="store_true",
                    help="ignore Chrome's 'saved in Google Account' bookmarks")
    ap.add_argument("--backup-dir", type=Path, default=STATE_DIR / "backups")
    ap.add_argument("--keep-backups", type=int, default=10)
    ap.add_argument("--log-file", type=Path, default=STATE_DIR / "sync.log")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    global SHOW_ALL
    SHOW_ALL = a.all

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if a.log_file:
        a.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(a.log_file, encoding="utf-8"))
    handlers[0].setFormatter(logging.Formatter("%(message)s"))
    if len(handlers) > 1:
        handlers[1].setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, handlers=handlers)

    opts = Options(dry_run=a.dry_run, backup_dir=a.backup_dir, keep_backups=a.keep_backups,
                   firefox_menu=a.firefox_menu, include_account=not a.no_account_bookmarks,
                   dirs={k: Path(v).expanduser() for k, v in _kv(a.dir, "--dir").items()},
                   profiles=_kv(a.profile, "--profile"))

    if a.list:
        list_browsers(opts)
        return 0
    if a.rescue:
        return rescue(a.rescue, opts)

    targets = [t.strip().lower() for t in a.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in DISPLAY or t == "chrome"]
    if bad:
        sys.exit(f"Unknown or invalid target(s): {', '.join(bad)}")
    if a.dry_run:
        log.info("DRY RUN — nothing will be written")

    if a.watch:
        try:
            watch(targets, opts, max(5, a.watch))
        except KeyboardInterrupt:
            log.info("Stopped.")
        return 0

    try:
        results = run_once(targets, opts)
    except FileNotFoundError as e:
        log.error("%s", e)
        return 1
    if RESULT_ERROR in results.values():
        return 1
    return 2 if RESULT_SKIPPED in results.values() else 0


if __name__ == "__main__":
    sys.exit(main())
