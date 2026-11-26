---
name: omp-packet-encryption-launcher
description: Enable open.mp encryption without locking players out.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, security, network]
    category: samp
---

# Packet encryption and launcher rollout

## When to Use

- Turning on `network.use_omp_encryption` for the first time.
- Legacy clients stop connecting after a security change.

## 2026 Compatibility & Architecture Matrix

| Item | 2026 state |
| --- | --- |
| Feature | open.mp packet encryption, introduced v1.4.0.2779 |
| Key | `network.use_omp_encryption` in `config.json` |
| Client | open.mp launcher (v1.6.x); plain SA-MP clients cannot speak it |
| Effect | encrypted session traffic; unencrypted clients are rejected |

## Production Implementation

1. Take a baseline before changing anything: how many players connect per day and with
   which client flags (`omp-client-capability-detection`).

```json
{
  "network": {
    "use_omp_encryption": true
  }
}
```

2. Roll out in two steps, not one:

```bash
# step 1: observe only - log clients that would fail
grep -c "connection" server_log.txt
# step 2: enable, then watch the reject rate for 24h
tail -f server_log.txt | grep -i "encrypt\|reject\|version"
```

3. Publish the launcher link in the server description before enabling; players on the old
   client will otherwise read the change as a server outage.

4. Keep a rollback line ready: set the key to `false` and restart. Encryption is a
   connection-level setting, not a data migration, so rollback is immediate.

## Deprecated Traps & Edge Cases (2026)

- Enabling encryption with a mobile-only player base: most Android clients are not the
  open.mp launcher, so the change reads as "server down" to them.
- Mixing encrypted and plain traffic behind a UDP proxy that inspects packets.
- Assuming encryption replaces validation: malformed-but-encrypted packets still need the
  guards in `pawn-raknet-packet-guard`.

## Verification

- Launcher client connects; plain SA-MP client is rejected with a version message.
- Log shows zero unexpected disconnects in the 24h after enable.
- `python3 -c "import json;print(json.load(open('config.json'))['network']['use_omp_encryption'])"`
  prints `True` on the running host.

## Sources (2026)

- https://open.mp/docs/changelog (v1.4.0.2779)
- https://github.com/openmultiplayer/launcher
