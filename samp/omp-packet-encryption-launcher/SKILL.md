---
name: omp-packet-encryption-launcher
description: Use when enabling open.mp packet encryption without outages.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, security, network, launcher, config]
    category: samp
---

# Turn on packet encryption without turning players away

open.mp can encrypt the session traffic between server and client. The switch is one
boolean in `config.json`, there is no key to mint and no keystore to ship — and that is
exactly why it gets enabled carelessly: the negotiated path only exists for clients that
speak it, so the rollout is a client-distribution problem, not a crypto problem.

## When to Use

- You are about to set `network.use_omp_encryption` for the first time.
- Players report the server as "offline" right after a security change.
- You must decide whether closing the 0.3.7 path (`network.allow_037_clients`) is safe yet.
- An audit asks what protects the wire between client and server.

## Compatibility & Stack Matrix (2026)

| Item | 2026 state | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | key exists since the network rework, v1.4.0.2779 |
| Switch | `network.use_omp_encryption` (bool, default `false`) | the only knob; no key, no cert, no shared secret |
| Encrypted clients | open.mp launcher | negotiates the encrypted session |
| Vanilla clients | SA-MP 0.3.7 and Android forks | cannot speak it; served by the plain protocol |
| `network.allow_037_clients` | bool, default `true` | `false` + encryption = vanilla clients locked out |
| Reload | restart required | it is a boot-time network setting, not hot-reloadable |
| Proxy / tunnel | UDP forwards in front of the server | a proxy that rewrites payloads breaks the session |

Read the pair together. Encryption protects the clients that support it; `allow_037_clients`
decides whether everyone else may still connect in the clear. Enabling encryption alone does
not lock anyone out, and closing the 0.3.7 path alone does not encrypt anything.

## Production Implementation

1. Measure the fleet before you touch the config. Count connections by reported client
   version so the decision is based on numbers, not on a guess about who runs mobile:

```pawn
public OnPlayerConnect(playerid)
{
    new version[32];
    GetPlayerVersion(playerid, version, sizeof version);
    printf("[client] %d version=%s", playerid, version);
    return 1;
}
```

2. Take the baseline off the log, then keep it as the "before" column of the rollout:

```bash
grep -o 'version=.*' server_log.txt | sort | uniq -c | sort -rn
```

3. Edit `config.json`. Keep the change to the two network keys; everything else in the file
   is unrelated and a bad merge there is a separate outage:

```json
{
  "network": {
    "use_omp_encryption": true,
    "allow_037_clients": true
  }
}
```

4. Stage the rollout in two restarts. First restart keeps `allow_037_clients` at `true`, so
   vanilla players stay connected over the plain protocol while launcher clients pick up the
   encrypted path. Watch for a day; only then decide on the hard lockout:

```bash
# after the restart: confirm the setting the process actually booted with
python3 -c "import json;n=json.load(open('config.json'))['network'];print(n['use_omp_encryption'], n['allow_037_clients'])"
# and watch who still arrives in the clear
tail -f server_log.txt | grep -i 'version=\|encrypt\|reject'
```

5. To lock vanilla clients out, set `"allow_037_clients": false` and restart again. From
   that point every accepted client is a launcher client on the encrypted path; a 0.3.7
   client is refused at connect and sees a version error, not a timeout. Announce it with the
   launcher download first — from the player's side this change is indistinguishable from the
   server being down.

6. Publish the launcher link in the server description and the Discord before step 5. The
   failure of every encryption rollout is communication, not protocol.

7. Keep the rollback in the same commit as the change: set `use_omp_encryption` back to
   `false`, restart, done. Nothing is persisted per player, so no data migration is involved.

8. Do not treat encryption as validation. A packet can be encrypted and still lie about a
   player's position or weapon; the checks in `pawn-raknet-packet-guard` and
   `raknet-incoming-rpc-filter` stay in place and stay mandatory.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Whole mobile player base gone after restart | `allow_037_clients: false` with no launcher build for Android | revert the flag, ship the launcher, then close the path |
| Server appears offline to everyone | UDP proxy in front rewriting payloads | bypass the proxy or terminate it before the server, do not inspect session bytes |
| Setting appears to do nothing | edited a different `config.json` than the one the process boots | check the working directory, then re-read the key with the python one-liner |
| Launcher client cannot connect, vanilla can | client launcher older than the server's protocol revision | update the launcher build, pin both versions in the changelog |
| Connect succeeds then drops mid-session | session keys renegotiated across a server restart mid-connection | restart only when empty, or accept the drop window |
| Bans and firewall rules still applied to wrong IP | expecting encryption to hide endpoints | encryption protects payloads, not addressing; keep CIDR bans (`omp-ban-ip-cidr-management`) |

## Verification

Three facts have to hold on the running host: the process booted with the key set, the
launcher client is accepted, and a vanilla client is refused once the 0.3.7 path is closed.

```bash
python3 -c "import json;n=json.load(open('config.json'))['network'];print('enc',n['use_omp_encryption'],'legacy',n.get('allow_037_clients',True))"
grep -ci 'encrypt' server_log.txt
```

Expected after the second restart — encryption on, vanilla path closed, and the log carries
the session lines:

```text
enc True legacy False
1
```

The `1` is a count, not a constant: it only has to be non-zero on a server that has served at
least one launcher client. A `0` with players online means you edited a config the process
did not load.

## Sources (2026)

- https://open.mp/docs/server/config.json — `network.use_omp_encryption` (default `false`), `network.allow_037_clients`, and the note that the default protocol runs alongside.
- https://github.com/openmultiplayer/launcher — the client that negotiates the encrypted session.
- https://open.mp/docs/changelog — network and protocol revisions per server release.
