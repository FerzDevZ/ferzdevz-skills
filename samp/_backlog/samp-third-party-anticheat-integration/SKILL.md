---
name: samp-third-party-anticheat-integration
description: Run a community anticheat without double bans.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, anticheat, security, integration]
    category: samp
---

# Third-party anticheat integration

## When to Use

- Adding Nex-AC, SAMP_AC_v2 or a Pawn anticheat to an existing gamemode.
- Two anticheats ban the same player with different evidence.

## 2026 Compatibility & Architecture Matrix

| Project | Type | Note |
| --- | --- | --- |
| Nex-AC (`nexiustailer/nex-ac`) | Pawn anticheat | open.mp capable fork exists |
| SAMP_AC_v2 (`Whitetigerswt`) | client + server | needs a client plugin, mobile clients excluded |
| anticheat-samp / open.mp forks | Pawn | lightweight, fewer checks |

## Production Implementation

1. Audit before installing:

```bash
grep -n "OnPlayerUpdate\|Kick\|Ban" ac/*.pwn | head -40
```

If it hooks `OnPlayerUpdate` per tick, measure the cost first (`pawn-profiler-optimization`).

2. Decide one authority for bans. Make the community AC report into your pipeline rather
   than kick directly:

```pawn
// adapter: convert AC verdict into your evidence record
public OnAnticheatDetect(playerid, const reason[])
{
    AddEvidence(playerid, reason, GetPlayerPos, GetPlayerWeapon(playerid));
    return 1;   // do not Kick here; the policy layer decides
}
```

3. Keep false-positive policy explicit: warnings first, kick on repeat, ban only with two
   independent signals (AC + server-side invariant).

4. Never let a client-side AC gate economy actions; the server check stays authoritative.

## Deprecated Traps & Edge Cases (2026)

- Two ACs both banning: the second ban overwrites the first reason and destroys evidence.
- Client-side AC needs a client plugin; Android users will simply not be covered, so your
  server-side invariants must do the work.
- AC that teleports players back on suspicion without logging breaks support tickets.
- Installing an AC that hooks callbacks you also use can swallow your return values.

## Verification

- Trigger a known cheat from a test account: one ban record, with evidence, no duplicate.
- Tick cost before/after install differ by a measured number, not a guess.
- Android test client is still playable with the server-side checks active.

## Sources (2026)

- https://github.com/nexiustailer/nex-ac
- https://github.com/Whitetigerswt/SAMP_AC_v2
- https://github.com/glarceny/anticheat-samp
