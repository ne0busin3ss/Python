# bookmark_sync — Chrome → Chromium + Firefox mirror

One-way bookmark mirror. **Chrome is the master**; Chromium (and optionally
Edge / Brave) and Firefox are made to match it. Chrome is only ever *read*.

Python 3.8+, standard library only. Linux, macOS, Windows.

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
  removes them. Import that file into Chrome (chrome://bookmarks → ⋮ → Import
  bookmarks) to keep any of them.
* **Log:** `~/.bookmark_sync/sync.log`.

Dry-run symbols: `+` new from Chrome · `-` removed (only in that browser) ·
`>` moved to another folder · `~` renamed.

> ⚠️ It's a mirror: anything that exists **only** in Chromium or Firefox will be
> removed. Run `--dry-run` first and move anything you want to keep into Chrome.

## Quick start

```bash
chmod +x bookmark_sync.py
./bookmark_sync.py --list        # what was detected, and whether each browser is open
./bookmark_sync.py --dry-run     # preview changes, write nothing
./bookmark_sync.py               # close Chromium + Firefox, then sync
```

Exit codes: `0` ok · `1` error · `2` a target was skipped because it was running.

## Options

| Option | Purpose |
|---|---|
| `--targets chromium,firefox` | Default. Add `edge`, `brave` as wanted. |
| `--rescue edge` | From that browser's newest backup, save every bookmark Chrome doesn't have to `~/rescued-bookmarks-*.html`, ready to import into Chrome. Also accepts a file path. |
| `--all` | With `--dry-run`, list every change instead of 8 of each kind. |
| `--watch 60` | Stay running; re-sync when Chrome changes or a skipped browser closes. |
| `--profile chrome="Profile 1"` | Non-default Chromium-family profile folder (see `--list`). |
| `--dir firefox=/path/to/profile` | Override auto-detection (Firefox profile dir, or a Chromium-family "User Data" dir). |
| `--firefox-menu clear` | Empty Firefox's Bookmarks Menu so Firefox is a pure mirror. |
| `--no-account-bookmarks` | Ignore Chrome's Google-Account bookmarks. |
| `--keep-backups N`, `--backup-dir PATH`, `--log-file PATH`, `-v` | Housekeeping. |

Auto-detected locations include native, Snap and Flatpak installs on Linux.

## Run it automatically

### Linux — systemd user service (recommended)

`~/.config/systemd/user/bookmark-sync.service`
```ini
[Unit]
Description=Mirror Chrome bookmarks to Chromium and Firefox

[Service]
ExecStart=/usr/bin/python3 %h/bin/bookmark_sync.py --watch 60
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

Prefer a timer over a long-running watcher? Use cron instead:
`*/15 * * * * /usr/bin/python3 $HOME/bin/bookmark_sync.py >/dev/null 2>&1`

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
