# bookmark_sync — Chrome → Chromium, Edge and Firefox mirror

One-way bookmark mirror. **Chrome is the master**; Chromium, Microsoft Edge and
Firefox (and optionally Brave) are made to match it. Chrome is only ever *read*.
Browsers that aren't installed are simply skipped.

Python 3.8+, standard library only. **Tested on Linux.** macOS and Windows support is
written (browser locations, Task Scheduler and launchd setup below) but not yet tested.

📄 **[Command cheat sheet (PDF)](Bookmark_Sync_Cheat_Sheet.pdf)**: service, log, and script commands on two printable pages.

## How it works

| Chrome folder     | Chromium / Edge / Brave | Firefox                 |
|-------------------|-------------------------|-------------------------|
| Bookmarks bar     | Bookmarks bar           | Bookmarks Toolbar       |
| Other bookmarks   | Other bookmarks         | Other Bookmarks         |
| Mobile bookmarks  | Mobile bookmarks        | Mobile Bookmarks        |
| —                 | —                       | Bookmarks Menu (kept by default; `--firefox-menu clear` empties it) |

* **Chrome source:** `Default/Bookmarks` JSON, plus `AccountBookmarks` (bookmarks
  "saved in your Google Account") merged in, duplicates dropped.
* **Chromium-family targets:** the `Bookmarks` JSON file is rebuilt and swapped in
  atomically. The browser keeps its own root-folder IDs; no checksum is written
  (Chromium skips verification when it's absent).
* **Firefox target:** `places.sqlite` is edited in one transaction — existing
  history entries are reused (visit counts kept), `url_hash`, `moz_origins` and
  `foreign_count` are maintained, and Firefox Sync tombstones are written for
  removed items so deletions propagate to your other Firefox devices.
* **Only writes when different.** A target that already matches Chrome is untouched.
* **Never writes to a running browser** (it would overwrite the file on exit).
  Running targets are reported and retried in `--watch` mode once they close.
* **Backups first:** `~/.bookmark_sync/backups/<browser>/`, newest 10 kept.
* **Nothing deleted silently:** bookmarks that only a target browser had are saved to
  `~/.bookmark_sync/backups/removed/<browser>-removed-<time>.html` before the sync
  removes them (newest 10 per browser kept, like backups). Import that file into
  Chrome (chrome://bookmarks → ⋮ → Import bookmarks) to keep any of them.
* **Log:** `~/.bookmark_sync/sync.log`.

Dry-run symbols: `+` new from Chrome · `-` removed (only in that browser) ·
`>` moved to another folder · `~` renamed · `↕` folder put back in Chrome's order ·
`≠` folder has a different number of copies of a bookmark.

> ⚠️ It's a mirror: anything that exists **only** in Chromium or Firefox will be
> removed. Run `--dry-run` first and move anything you want to keep into Chrome.

## Quick start

```bash
chmod +x bookmark_sync.py
./bookmark_sync.py --list        # what was detected, and whether each browser is open
./bookmark_sync.py --dry-run     # preview changes, write nothing
./bookmark_sync.py               # close Chromium + Firefox, then sync
```

With Edge as well, name all three targets:

```bash
./bookmark_sync.py --targets chromium,edge,firefox --dry-run
./bookmark_sync.py --targets chromium,edge,firefox
```

Exit codes: `0` ok · `1` error · `2` a target was skipped because it was running.

## Options

| Option | Purpose |
|---|---|
| `--targets chromium,firefox` | Default. Add `edge`, `brave` as wanted. |
| `--rescue edge` | From that browser's newest backup, save every bookmark Chrome doesn't have to `~/rescued-bookmarks-*.html`, ready to import into Chrome. Also accepts a file path. |
| `--all` | With `--dry-run`, list every change instead of 8 of each kind. |
| `--watch 60` | Stay running. Re-checks a browser when Chrome's bookmarks change, when that browser rewrites its own bookmarks, or when an open browser closes. An open browser is reported once, not every minute. |
| `--profile chrome="Profile 1"` | Non-default Chromium-family profile folder (see `--list`). |
| `--dir firefox=/path/to/profile` | Override auto-detection (Firefox profile dir, or a Chromium-family "User Data" dir). |
| `--firefox-menu clear` | Empty Firefox's Bookmarks Menu so Firefox is a pure mirror. |
| `--no-account-bookmarks` | Ignore Chrome's Google-Account bookmarks. |
| `--keep-backups N`, `--backup-dir PATH`, `--log-file PATH`, `-v` | Housekeeping. `N` must be at least 1. |

Auto-detected locations include native, Snap and Flatpak installs on Linux.

## Adding Microsoft Edge on Linux

Use Microsoft's own RPM or DEB package rather than a Flatpak or Snap: it keeps
its bookmarks in `~/.config/microsoft-edge`, where the script looks, and the
script's "is it open?" check is untested with sandboxed browsers.

**Fedora / RHEL:**

```bash
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo tee /etc/yum.repos.d/microsoft-edge.repo <<'REPO'
[microsoft-edge]
name=Microsoft Edge
baseurl=https://packages.microsoft.com/yumrepos/edge
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
REPO
sudo dnf install microsoft-edge-stable
```

**Ubuntu / Debian:** download the `.deb` from microsoft.com/edge and install it;
it adds Microsoft's repository for updates.

Then:

1. **Open Edge once and close it.** Its bookmark folder exists only after the first launch.
2. **Turn off Favorites sync** at `edge://settings/profiles/sync` if you sign in with a
   Microsoft account, so its cloud copy doesn't compete with Chrome.
3. **Add `edge` to `--targets`** (the service example below already includes it), then
   `systemctl --user restart bookmark-sync`. Edge receives Chrome's bookmarks within a
   minute of closing. If Edge already had favorites of its own, run `--dry-run` first:
   anything only Edge has is removed (after being saved to an importable file).

## Run it automatically

### Linux — systemd user service (recommended)

`~/.config/systemd/user/bookmark-sync.service`
```ini
[Unit]
Description=Mirror Chrome bookmarks to Chromium, Edge and Firefox

[Service]
ExecStart=/usr/bin/python3 %h/bin/bookmark_sync.py --targets chromium,edge,firefox --watch 60
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
```
```bash
mkdir -p ~/bin && cp bookmark_sync.py ~/bin/
systemctl --user daemon-reload
systemctl --user enable --now bookmark-sync.service
journalctl --user -u bookmark-sync -f      # watch it work
```

No Edge? Drop `edge,` from `--targets`, or leave it: a missing browser is just reported as not found.

Prefer a timer over a long-running watcher? Use cron instead:
`*/15 * * * * /usr/bin/python3 $HOME/bin/bookmark_sync.py --targets chromium,edge,firefox >/dev/null 2>&1`

### Windows — Task Scheduler
Action: `pythonw.exe` · Arguments: `C:\Tools\bookmark_sync.py --watch 60` ·
Trigger: *At log on*.

### macOS — launchd
`~/Library/LaunchAgents/local.bookmark-sync.plist` with `ProgramArguments`
`/usr/bin/python3`, `/Users/you/bin/bookmark_sync.py`, `--watch`, `60` and
`RunAtLoad = true`, then `launchctl load ~/Library/LaunchAgents/local.bookmark-sync.plist`.

## Notes & limits

* **Favicons** aren't copied; each browser fetches them on the next visit.
* **Chromium with Google Sync on** (rare) may pull its server copy back over
  the mirror — turn bookmark sync off in Chromium.
* **Edge signed in with a Microsoft account** may sync its cloud copy of
  Favorites back over the mirror. Turn off Favorites in
  `edge://settings/profiles/sync` before adding Edge as a target.
* **Firefox Sync** is fine: mirrored changes upload as normal edits.
* Chrome has no separators or keywords, so Firefox-only separators are removed.
* **Restore a backup:** close the browser and copy the file back —
  `Bookmarks-<stamp>` → `<profile>/Bookmarks`, or
  `places-<stamp>.sqlite` → `<profile>/places.sqlite` (delete any
  `places.sqlite-wal` beside it first).
* If Firefox ever complains, *about:support → Places Database → Verify Integrity*
  repairs index-level issues.
