---
name: ufw-ddos-raknet-mitigation
description: Use when UDP floods keep dropping the server.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, security, ufw, ddos, netfilter]
    category: samp
---

# UDP flood defence: ufw for the base rules, open.mp for the rate limits

ufw is a front-end for host netfilter. It matches ports, protocols and sources — it
does not parse RakNet, so it cannot tell a flood datagram from a legit sync packet. Its
own rate limiter (`ufw limit`) is a new-connection counter (6 connections in 30 s) and
applied to `7777/udp` it blocks real players instead of attackers. Volumetric UDP needs
the provider; per-source abuse needs `nftables` counters or the server's own limits.

## When to Use

- The server times out, drops players, or the CPU sits at 100% during an attack.
- You are writing the firewall rules for a fresh open.mp box and want them correct the
  first time.
- Someone proposed `ufw limit 7777/udp` and you need to explain why that is wrong.
- Not a substitute for provider scrubbing: if the link is saturated, no host rule helps.

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | What it can and cannot do |
| --- | --- | --- |
| ufw | 0.36.x on Ubuntu 24.04 | allow/deny by port+proto+source; `limit` is connection-count based |
| netfilter backend | nftables (ufw uses it) | per-source meters, valid alongside ufw in a separate table |
| open.mp | 1.6.7.3218 | `network.messages_limit` 500, `network.message_hole_limit` 3000 |
| RakNet ban window | `network.limits_ban_time` 60000 ms | bans after acks/message limit is hit |
| Legit client rate | `network.on_foot_sync_rate` 30 ms | ~33 packets/s per player, before walking sync |
| Provider | any scrubbing tier | the only layer that absorbs volumetric floods |

## Production Implementation

1. Write the base policy. Dry-run first, then apply — `--dry-run` is ufw's own syntax
   check, so a typo never lands as a half-written ruleset:

```bash
ufw --dry-run allow 7777/udp comment 'open.mp game'
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'ssh'
ufw allow 7777/udp comment 'open.mp game'
ufw --force enable
ufw status numbered
```

2. Do **not** add `ufw limit 7777/udp`. A limit rule denies a source after 6 connections
in 30 seconds, and one player sends more UDP packets than that in under a second.
`limit` belongs on TCP services such as SSH:

```bash
ufw limit 22/tcp comment 'ssh brute force'
```

3. Move the actual flood work to open.mp's network keys, which count messages per
   client per second and ban the source at the RakNet level:

```json
{
  "network": {
    "messages_limit": 500,
    "message_hole_limit": 3000,
    "acks_limit": 3000,
    "limits_ban_time": 60000,
    "player_timeout": 10000
  }
}
```

Only during an active connection flood, also set `network.minimum_connection_time`
(e.g. `50` ms): the docs explicitly warn against it as a permanent setting, because it
delays every legitimate join.

4. If the provider does not scrub, add a per-source cap in a **separate** nftables table
   so ufw's own table stays untouched. Check the file before loading it:

```bash
cat > /etc/nftables-raknet.nft <<'EOF'
table inet raknet {
  set flood {
    type ipv4_addr
    flags dynamic,timeout
    timeout 60s
  }
  chain input {
    type filter hook input priority -5; policy accept;
    # nft >= 0.9.4; older builds: replace 'update' with 'add @flood { ip saddr }'
    udp dport 7777 update @flood { ip saddr limit rate over 150/second burst 300 packets } drop
  }
}
EOF
nft -c -f /etc/nftables-raknet.nft && nft -f /etc/nftables-raknet.nft
```

If the host's nft is too old for dynamic sets, the one-line fallback is a global cap —
less precise, still valid syntax and still no payload inspection:

```bash
nft add rule inet raknet input udp dport 7777 limit rate over 400/second burst 800 packets drop
```

`150/second` sits well above one honest client (~33/s) and well below a flood. Nothing
here inspects RakNet payloads — it caps datagrams per source address, nothing more.

5. Ban by source only as a last resort, and expect collateral damage: RakNet floods are
   usually source-spoofed, so an address ban can hit an innocent host. Use `BlockIpAddress`
   from the script for repeat offenders you have confirmed are not spoofed.

6. Watch packet rate, not player count: `sar -n UDP 5 3` and `ufw show raw | head -20`.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Players drop every 30 s under load | `ufw limit 7777/udp` counters real traffic | delete the rule, `ufw delete limit 7777/udp` |
| Nobody can connect after enabling ufw | rule added while `ufw` was inactive, or wrong proto | `ufw status verbose`, then `ufw allow 7777/udp` |
| Server unreachable but `ufw` says allowed | Docker or another tool inserted earlier iptables rules | check `ufw show raw`, put the container in host net or fix the chain order |
| CPU pegged with normal packet rate | per-packet work in `OnPlayerUpdate`, not a flood | profile the script |
| Flood survives every host rule | link saturated before the box | provider scrubbing; host filters cannot help |
| Legit players banned by RakNet limits | `messages_limit` set too low | keep the 500 default and fix the chatty script |

## Verification

Validate the rule syntax without touching the live ruleset:

```bash
ufw --dry-run allow 7777/udp comment 'open.mp game'
```

Expected: `Rules updated` and `Rules updated (v6)` with no error, and no change on
`ufw status`.

Then read the live state — the game rule must be `ALLOW` and there must be no `LIMIT`
row for 7777:

```bash
ufw status numbered
```

Expected:

```text
[ 1] 22/tcp                     LIMIT IN    Anywhere
[ 2] 7777/udp                   ALLOW IN    Anywhere
[ 3] 7777/udp (v6)              ALLOW IN    Anywhere (v6)
```

Finally confirm the flood cap loads and counts:

```bash
nft -c -f /etc/nftables-raknet.nft && nft list set inet raknet flood
```

Expected: the set exists with `size`/`timeout` shown, no syntax error from `-c`. Under a
test flood, legitimate clients keep their ping while `nft list set inet raknet flood`
fills with attacker addresses.

## Sources (2026)

- https://help.ubuntu.com/community/UFW
- https://open.mp/docs/server/config.json
- https://documentation.ubuntu.com/server/how-to/security/firewalls/
