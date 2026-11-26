---
name: linux-samp-omp-systemd
description: Use when omp-server must survive crashes and reboots.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, linux, systemd, deployment, ops]
    category: samp
---

# omp-server under systemd: one unit, journal logs, real restarts

## When to Use

- The server runs inside `screen` or `tmux` and does not come back after a reboot or an OOM kill.
- You need logs that survive the SSH session and a restart policy you can point at.
- You are migrating a VPS from a manual launch script to a supervised service.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 reality | What it means for the unit |
| --- | --- | --- |
| Binary | `omp-server`, a single foreground process reading `config.json` and `components/` | `Type=simple`, one `ExecStart`, no forking wrapper |
| Working directory | relative paths for `components/`, `models/`, `scriptfiles/` | set `WorkingDirectory=` or nothing resolves |
| Journal | `StandardOutput=journal` + `SyslogIdentifier=` | logs are queryable with `journalctl -u omp` |
| Restart | `Restart=always` with `RestartSec=` | a crash restarts, a crash loop needs `StartLimitBurst=` |
| File descriptors | hundreds of players plus plugins | `LimitNOFILE=65535` |
| Sandboxing | `ProtectSystem=strict` makes the tree read-only | every writable path needs `ReadWritePaths=` |
| Shutdown | `KillSignal=` + `TimeoutStopSec=` | verify in the journal that the gamemode exits before SIGKILL |

## Production Implementation

1. Create a service user and the tree it owns. Never run the server as `root`: every component and plugin inherits that privilege.

```bash
sudo useradd --system --home-dir /srv/omp --shell /usr/sbin/nologin omp
sudo install -d -o omp -g omp /srv/omp /srv/omp/scriptfiles /srv/omp/components /srv/omp/models
sudo tar xf omp-server-linux-x64.tar.gz -C /srv/omp --strip-components=1
sudo chown -R omp:omp /srv/omp
```

2. Write the unit. `StartLimitIntervalSec` and `StartLimitBurst` live in `[Unit]`, process settings in `[Service]`, `WantedBy=` in `[Install]`; a key in the wrong section is a silent no-op. If the server writes its own log file next to the binary, add that directory to `ReadWritePaths=` as well.

```ini
[Unit]
Description=open.mp server
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=omp
Group=omp
WorkingDirectory=/srv/omp
ExecStart=/srv/omp/omp-server
Restart=always
RestartSec=5
TimeoutStopSec=15
KillSignal=SIGTERM
LimitNOFILE=65535
StandardOutput=journal
StandardError=journal
SyslogIdentifier=omp
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/omp/scriptfiles /srv/omp/logs

[Install]
WantedBy=multi-user.target
```

3. Validate before you enable. `systemd-analyze verify` parses the unit and reports unknown keys and missing executables, which is the difference between a five-second fix and a server that never starts.

```bash
sudo install -m 0644 omp.service /etc/systemd/system/omp.service
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/omp.service
```

4. Enable and start in one step, then read the journal rather than guessing. `enable --now` is what makes the unit survive a reboot; `start` alone does not.

```bash
sudo systemctl enable --now omp
systemctl is-active omp
journalctl -u omp -n 40 --no-pager
```

5. Confirm the socket, not just the process. A `active (running)` state with a failed bind looks healthy in `systemctl status` and dead in the browser:

```bash
ss -lunp | grep -F ':7777'
```

6. Change configuration through a restart, not a reload. `systemctl reload` needs `ExecReload=`, and `omp-server` re-reads `config.json` only at start, so a reload request without one either errors or does nothing:

```bash
sudo systemctl restart omp
journalctl -u omp -f
```

7. Keep journal growth bounded on small VPS disks, and confirm the restart policy actually stored:

```bash
sudo journalctl --vacuum-time=14d
systemctl show -p Restart -p RestartUSec -p LimitNOFILE omp
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Server is gone after a reboot | unit started with `systemctl start`, never enabled | `systemctl enable omp` |
| Restart every 5 s with no players | bad `config.json` or a missing include | `journalctl -u omp -n 100`; `StartLimitBurst=5` stops the churn |
| `active (running)` but the server is not listed | port bind failed or wrong interface | `ss -lunp \| grep 7777`, check `network.bind` and `network.port` |
| Server cannot write `scriptfiles` | `ProtectSystem=strict` without `ReadWritePaths=` | add the path, `daemon-reload`, restart |
| Every plugin runs as root | no `User=` in `[Service]` | `User=omp`, re-chown the tree |
| Stops take 90 s or lose player data | SIGTERM ignored, default stop timeout | raise `TimeoutStopSec=`, check the journal for the shutdown lines |
| Too many open files under load | default `LimitNOFILE` (1024) | `LimitNOFILE=65535`, verified with `systemctl show` |

## Verification

```bash
systemctl is-active omp
systemctl show -p Restart -p LimitNOFILE omp
ss -lunp | grep -F ':7777'
journalctl -u omp -n 20 --no-pager | grep -iE 'loaded|gamemode|version'
```

Expected: `active`; `Restart=always` and `LimitNOFILE=65535` in the `systemctl show` output; one `UNCONN` line on `0.0.0.0:7777`; and journal lines naming the server version and the loaded gamemode, which is the proof the working directory and `components/` resolved. Then `sudo systemctl restart omp` twice: the second start must reuse the same port with no "address in use" error, which means the previous process exited cleanly inside `TimeoutStopSec`.

## Sources (2026)

- https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html
- https://www.freedesktop.org/software/systemd/man/latest/systemctl.html
