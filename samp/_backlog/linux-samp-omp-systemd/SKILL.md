---
name: linux-samp-omp-systemd
description: Run omp-server under systemd on Linux.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, systemd]
    category: samp
---

# systemd unit

## When to Use
- Deploying to a VPS or migrating from screen/tmux.
- Server must restart after crash or reboot.

## 2026 Compatibility & Architecture Matrix
- omp-server is a single binary plus `components/` and `config.json`.
- `LimitNOFILE` matters with hundreds of players and many plugins.

## Production Implementation
1. Create a dedicated user and `/srv/omp` working directory.
2. Install the unit with `Restart=always` and `RestartSec=5`.
3. Enable, start, then read the journal for the startup banner.

```ini
[Service]
WorkingDirectory=/srv/omp
ExecStart=/srv/omp/omp-server
Restart=always
RestartSec=5
User=omp
LimitNOFILE=65535
```

## Deprecated Traps & Edge Cases (2026)
- Running as root makes every plugin a root process.
- `Type=simple` with a forking wrapper hides the real exit code.

## Verification
- `systemctl is-active omp` and the UDP port answers.
- `journalctl -u omp -n 50` shows the gamemode loaded.
