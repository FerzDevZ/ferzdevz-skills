---
name: omp-json-config-env-vars
description: Use when secrets leak into config.json across environments.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, config]
    category: samp
---

# config.json in production

## When to Use

- The RCON password, server password or DSN sits in a committed `config.json`.
- Staging and production must differ only by environment, not by a forked file.
- You inherited a `server.cfg` and need the current open.mp keys.
- A setting changes on the console and silently reverts after a restart.
- An open.mp upgrade added keys and nobody noticed the new defaults.

## Compatibility & Stack Matrix (2026)

| Component | Version | Notes |
| --- | --- | --- |
| open.mp server | 1.x | reads `config.json` from the working directory; `server.cfg` is still honoured |
| `--default-config` | 1.x builds | writes a complete default `config.json` into the current directory |
| `--dump-config` | 1.x builds | converts an existing `server.cfg` into `config.json` (delete a stale `config.json` first) |
| Env expansion | 1.x | `${VAR}` and `${VAR:-default}` inside any string value; `$${VAR}` keeps the literal text |
| dotenv | not supported | open.mp has no `.env` parser, the process environment must already hold the values |
| systemd | 252+ | `EnvironmentFile=` with a `0600` file is the cheapest secret store |
| Docker | any | `env_file:` / `environment:` reach the `omp-server` process |

The only environment contract open.mp offers is `${VAR}` expansion inside `config.json` strings. There
are no magic `OMP_*` variables: if you need `OMP_RCON_PASSWORD`-style names, they are yours and you
expand them in the file yourself.

## Production Implementation

1. Commit a template with placeholders and keep the rendered file out of git. Only string keys can be
   expanded, so keep booleans and numbers literal:

```json
{
  "name": "${SERVER_NAME:-open.mp server}",
  "password": "${SERVER_PASSWORD:-}",
  "rcon": { "enable": true, "password": "${RCON_PASSWORD}" },
  "network": { "port": 7777 },
  "max_players": 100,
  "logging": { "log_sqlite": false, "use_timestamp": true }
}
```

2. Ignore the generated artefact, the environment file and the logs:

```bash
printf 'config.json\nomp.env\n*.log\n' >> .gitignore
git rm --cached config.json
```

3. Render at deploy time. Pass the variable list to `envsubst`; without it, every `$` in an unrelated
   value is rewritten too:

```bash
set -euo pipefail
envsubst '${SERVER_NAME} ${SERVER_PASSWORD} ${RCON_PASSWORD}' \
  < config.template.json > config.json
chmod 0600 config.json
jq -e . config.json > /dev/null   # refuses to deploy malformed JSON
```

4. Feed the values from the unit, never from an interactive shell:

```ini
[Service]
User=omp
WorkingDirectory=/srv/omp
EnvironmentFile=/etc/omp/omp.env
ExecStart=/srv/omp/omp-server
Restart=on-failure
```

```bash
install -m 0600 /dev/null /etc/omp/omp.env
printf 'RCON_PASSWORD=%s\n' "$(openssl rand -hex 16)" >> /etc/omp/omp.env
systemctl show omp -p Environment | grep -q RCON_PASSWORD && echo "env visible to the unit"
```

5. Containers use the same file, so one render step serves both targets:

```yaml
services:
  omp:
    image: omp-server:2026.1
    env_file: [./omp.env]
    working_dir: /srv/omp
    volumes: [./config.json:/srv/omp/config.json:ro]
    command: ["./omp-server"]
```

6. Diff the key set after every server upgrade; new keys ship with defaults that may still change your
   behaviour:

```bash
tmp=$(mktemp -d)
(cd "$tmp" && /srv/omp/omp-server --default-config)
jq -r 'paths(scalars)|join(".")' "$tmp/config.json" | sort > /tmp/keys.new
jq -r 'paths(scalars)|join(".")' config.json | sort > /tmp/keys.old
comm -13 /tmp/keys.old /tmp/keys.new
```

7. Respect the Read-only column of the open.mp key table. `network.port`, `network.bind`,
   `network.mtu`, `max_players`, `rcon.enable`, `rcon.allow_teleport`, `use_dyn_ticks` and the
   `network.*_sync_rate` trio cannot change at runtime — put them in the file and restart. Everything
   else can be set temporarily with `SendRconCommand` or from the console, which is fine for a debug
   toggle and wrong as a deployment mechanism.

8. Keep comments in the template only. The documentation's own example shows `//` comments, but `jq`,
   `python -m json.tool` and most CI validators reject them — render without comments so the deployed
   file stays machine-checkable.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Server refuses to boot, log complains about the RCON password | the default `rcon.password` is `changeme`, which blocks startup | render `rcon.password` from the environment |
| `/rules` still shows `${RCON_PASSWORD}` | variable missing from the process environment | `systemctl show omp -p Environment`, fix the unit, restart |
| A boolean key is enabled although the env var says `false` | `${VAR}` expands to the string `"false"`, not to a bool | keep booleans literal in the template |
| Settings look ignored, the old hostname is live | the server started from another working directory | `WorkingDirectory` must hold `config.json`; check with a `pwd` in the unit |
| `jq` fails on the deployed file | `//` comments copied from the docs example | strip comments at render, gate on `jq -e .` |
| Change reverts on restart | the key is read-only at runtime and was set from the console | move the value into `config.json` and restart |

## Verification

```bash
cd /srv/omp
jq -e '.rcon.password != "changeme" and (.rcon.password|length) > 12' config.json
jq -e '[paths(scalars) as $p | getpath($p) | strings | select(test("\\$\\{"))] | length == 0' config.json
grep -c '^RCON_PASSWORD=' /etc/omp/omp.env
```

Expected output — both guards pass and the secret is present in the env file without being echoed:

```text
true
true
1
```

Start the server once and confirm the log has no configuration complaint:

```bash
./omp-server > /tmp/omp.log 2>&1 & sleep 3
grep -iE 'invalid|parse error|failed to load' /tmp/omp.log || echo "config loaded clean"
```

```text
config loaded clean
```

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/server/server.cfg
- https://open.mp/docs/scripting/functions/SendRconCommand
