---
name: docker-omp-mariadb-setup
description: Use when a team needs one reproducible omp+MariaDB stack.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, docker, mariadb, devops]
    category: samp
---

# One compose file for the server and its database

The stack that "works on my machine" is usually the one whose database was
installed by hand three years ago. A compose file pins the server release, the
MariaDB version and the schema together, so the YAML is the easy half.

## When to Use

- A team needs the same open.mp and MariaDB versions locally and in CI.
- You want a disposable environment: `down -v` returns to an empty schema.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | asset `open.mp-linux-x86.tar.gz`, extracted to `Server/` |
| Server binary | 32-bit x86 PIE | needs `libc6:i386`, `libstdc++6:i386`, `libatomic1:i386` |
| Base image | `debian:bookworm-slim` | slim is fine once the i386 runtimes are added |
| Database | `mariadb:11.4` LTS | `healthcheck.sh --connect --innodb_initialized` ships in the image |
| Ports | 7777/udp + 7777/tcp | the server binds both; UDP carries game traffic |

## Production Implementation

1. Build from the official release tarball. Its `omp-server` is a 32-bit PIE
   binary, so i386 loaders are mandatory even on amd64; without them the
   container dies with a misleading `no such file or directory`.

```dockerfile
FROM debian:bookworm-slim
ARG OMP_VERSION=1.6.7.3218
RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl libc6:i386 libstdc++6:i386 libatomic1:i386 \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /tmp/omp.tar.gz \
      "https://github.com/openmultiplayer/open.mp/releases/download/v${OMP_VERSION}/open.mp-linux-x86.tar.gz" \
 && mkdir -p /omp \
 && tar -xzf /tmp/omp.tar.gz -C /omp --strip-components=1 \
 && rm /tmp/omp.tar.gz
WORKDIR /omp
EXPOSE 7777/udp 7777/tcp
STOPSIGNAL SIGINT
CMD ["./omp-server"]
```

2. Compose both services; the DB port stays unpublished and the game waits for
   a health check, not for container start.

```yaml
services:
  db:
    image: mariadb:11.4
    environment:
      MARIADB_ROOT_PASSWORD: root-dev-only
      MARIADB_DATABASE: server
      MARIADB_USER: omp
      MARIADB_PASSWORD: omp-dev-only
    volumes:
      - db_data:/var/lib/mysql
      - ./db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 20
  omp:
    build: {context: ., args: {OMP_VERSION: 1.6.7.3218}}
    depends_on:
      db: {condition: service_healthy}
    ports: ["7777:7777/udp", "7777:7777/tcp"]
    volumes:
      - ./gamemodes:/omp/gamemodes:ro
      - ./config.json:/omp/config.json:ro
    restart: unless-stopped
volumes:
  db_data:
```

3. Keep `config.json` explicit: `pawn.main_scripts` uses the `name 1` form and
   `network.port` must match the published port.

```json
{
  "name": "omp dev stack",
  "max_players": 32,
  "announce": false,
  "pawn": { "main_scripts": ["test 1"], "side_scripts": [], "legacy_plugins": [] },
  "network": { "port": 7777, "allow_037_clients": true }
}
```

4. Seed from `db/init`; MariaDB runs those files once, on the first boot of an
   empty data volume.

```sql
CREATE TABLE IF NOT EXISTS blueprint (
  id INT UNSIGNED PRIMARY KEY, output_item VARCHAR(32) NOT NULL,
  output_qty INT UNSIGNED NOT NULL, station TINYINT UNSIGNED NOT NULL,
  craft_ms INT UNSIGNED NOT NULL) ENGINE=InnoDB;
INSERT IGNORE INTO blueprint VALUES (1,'bandage',2,0,4000);
```

5. Compile on the host or in CI, not inside the image: a `pawncc` in the runtime
   image would pin a second compiler version. Mount the `.amx` under `gamemodes/`.

```bash
pawncc -i$HOME/samp-sdk/omp-stdlib -d3 '-;+' '-(' test.pwn -ogamemodes/test.amx
```

6. Start, then read the log: the component load and your `OnGameModeInit` output
   are the proof, not the container status.

```bash
docker compose up -d --build
docker compose logs --no-color omp | grep -E 'Loaded .* component|gamemode init'
```

7. Treat the volume as the state: `down` keeps the database, `down -v` drops it.

```bash
docker compose down      # keeps db_data
docker compose down -v   # next up replays the seed
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `exec ./omp-server: no such file or directory` | 32-bit PIE without i386 runtimes | install `libc6:i386 libstdc++6:i386` |
| `libatomic.so.1: cannot open shared object file` | 32-bit libatomic missing | add `libatomic1:i386` to the same apt line |
| `failed to bind host port 7777/tcp: address already in use` | a host server or another stack owns the port | remap the host side, e.g. `"7788:7777/tcp"` |
| Server starts before the DB accepts connections | publishing order instead of health | `depends_on` with `condition: service_healthy` |
| Container exits immediately after start | `main_scripts` names an `.amx` that is not mounted | check `gamemodes/` and the script name in `config.json` |

## Verification

```bash
docker compose up -d --build
docker compose ps --format '{{.Service}} {{.Status}}'
docker compose logs --no-color omp | grep 'gamemode init'
docker compose exec -T db mariadb -uomp -pomp-dev-only -N \
  -e "SELECT COUNT(*) FROM server.blueprint;"
docker compose down && docker compose up -d
docker compose exec -T db mariadb -uomp -pomp-dev-only -N \
  -e "SELECT COUNT(*) FROM server.blueprint;"
```

- `ps` shows `db Up (healthy)` and `omp Up`; the log contains `[stack] gamemode
  init`, printed from `OnGameModeInit`.
- Both `SELECT COUNT(*)` calls print `1`: the seed ran once and survived `down`.

## Sources (2026)

- https://open.mp/docs/server/Installation
- https://hub.docker.com/_/mariadb
- https://github.com/openmultiplayer/open.mp/releases
