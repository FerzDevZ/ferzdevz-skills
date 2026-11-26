---
name: docker-omp-mariadb-setup
description: Containerise open.mp with MariaDB for reproducible dev.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, docker]
    category: samp
---

# docker compose stack

## When to Use
- A team needs the same server and DB version locally.
- You want a disposable environment for tests.

## 2026 Compatibility & Architecture Matrix
- open.mp runs on Linux amd64/arm64; MariaDB 10.11+ matches MySQL R41-4 behaviour closely.
- Mount the gamemode and config as volumes, not baked images.

## Production Implementation
1. Write a compose file with `omp` and `db` services on an internal network.
2. Seed the schema in `docker-entrypoint-initdb.d`.
3. Expose only the game UDP port to the host.

```yaml
services:
  db:
    image: mariadb:11
    environment: {MARIADB_ROOT_PASSWORD: dev, MARIADB_DATABASE: server}
  omp:
    image: ghcr.io/openmultiplayer/open.mp:1.6.7
    ports: ["7777:7777/udp"]
    volumes: ["./gamemodes:/omp/gamemodes", "./config.json:/omp/config.json"]
```

## Deprecated Traps & Edge Cases (2026)
- Publishing the DB port exposes it to the host network.
- A container without a volume loses the database on `down`.

## Verification
- `docker compose up -d` then a client connects and the gamemode logs DB connected.
- `docker compose down && up` keeps data.
