---
name: client-crash-opcode-lookup
description: Use when a client crash address repeats.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, crash, diagnostics]
    category: samp
---

# Read the crash block, match the address, never guess the opcode

## When to Use

- Two or more players report a freeze-to-desktop at the same place or after the same action.
- You have a crash block and need to turn it into a script change.
- A player pastes "Exception At Address: 0x…" with no context and someone proposes a fix.
- A crash appears only after a map, skin, vehicle upgrade or dialog change shipped.
- You need to separate a server-side fault (crashdetect) from a client-side one before touching code.

This skill is client-side triage. A server stack trace from crashdetect is a different artefact; use the crashdetect skill for those.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| SA-MP client | 0.3.7-R5, 0.3.DL-R1 | same block layout; DL builds add custom-model crashes |
| open.mp client | 1.x launcher | block still starts with `SA-MP` / `Exception At Address` |
| log fields | `Exception At Address`, `Base`, registers, stack, `SCM Op`, `Game Version` | parse them, do not retype them |
| crash address table | open.mp `docs/client/CrashAddresses` | published addresses with cause and fix |
| server-side | crashdetect 4.22+ | separate artefact; keeps the AMX stack |
| evidence rule | one full block per signature | a fix without the block is a guess |

## Production Implementation

1. Capture one complete block per signature, not a screenshot of the title bar. This is a real block, copied from open.mp forum thread 2767 (registers and stack lines elided, everything else verbatim):

```text
SA-MP 0.3.DL-R1
Exception At Address: 0x52EF7D90
Base: 0x036C0000
Registers:
EAX: 0x00000000 EBX: 0x0000002F ECX: 0x04A67F38 EDX: 0x00000708
...
SCM Op: 0x0, lDbg: 0 LastRendObj: 0
Game Version: US 1.0
```

The only trustworthy keys here are the faulting address and the module `Base`. Everything else is context.

2. Normalise the block into one line per crash so identical signatures group together. This awk pass is the whole parser:

```bash
awk -F': *' '
  /Exception At Address/ {addr=$2}
  /^Base/                {base=$2}
  /^SCM Op/              {scm=$2; sub(/,.*/, "", scm); obj=$4}
  END {printf "addr=%s base=%s scm=%s obj=%s\n", addr, base, scm, obj}
' crash.log
```

On the block above it prints `addr=0x52EF7D90 base=0x036C0000 scm=0x0 obj=0`. Group by `addr`: a signature that appears once is noise, one that repeats is a bug.

3. Look the address up in the published table before forming any theory. The entries that decide most object, skin and vehicle tickets:

| Address | Frequency | Cause | Fix |
| --- | --- | --- | --- |
| `0x00544BC8` | Frequent | more objects streamed to the client than it can hold | streamer with a lower visible-object distance/count |
| `0x00415D47`, `0x00536DF4` | Frequent | too many object textures loaded | remove or group objects until the signature stops |
| `0x007F0BF7` | Frequent | invalid vehicle upgrade applied by the server | validate the component against the model before adding |
| `0x006E3D17` | Rare | skin changed while entering/exiting or inside a vehicle | only change skin while on foot |

4. Treat `SCM Op` as evidence to quote, never as a cause to infer. In the block above it is `0x0` — no script operation was in flight — while the crash still happened. So a non-zero opcode is not required for a client crash, and a number alone proves nothing. If the field is non-zero, keep it in the ticket verbatim next to the action the player had just performed; do not map it to a native from memory.

5. Bisect the content, not the client build. Turn off one map group, one custom model set or one dialog branch at a time and re-run the same player on the same route. The address either changes (you removed the real trigger) or stays (you have not found it).

6. Convert the finding into a guard in Pawn. Skin-change and upgrade crashes both have cheap server-side guards:

```pawn
stock SafeSetSkin(playerid, skin)
{
    if (IsPlayerInAnyVehicle(playerid))
    {
        printf("[crash] refused skin=%d player=%d (in vehicle)", skin, playerid);
        return 0;
    }
    SetPlayerSkin(playerid, skin);
    return 1;
}
```

```pawn
// Component ids from your own parts list, keyed by the model they were fitted to.
stock bool:UpgradeFitsModel(modelid, componentid)
{
    switch (modelid)
    {
        case 562:
        {
            switch (componentid)
            {
                case 1000, 1001, 1002, 1003: return true;
            }
        }
        case 565:
        {
            switch (componentid)
            {
                case 1008, 1009, 1010: return true;
            }
        }
    }
    return false;
}
```

7. Close the ticket with the before/after signature: same player count, same route, the address gone from the grouped list for 48 hours. A drop in report volume is not proof; the missing signature is.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| "fixed" crash returns next restart | fix applied to the map file but not to the export the server loads | regenerate the map from source, restart, re-check the address |
| every crash looks unique | full stack pasted into the ticket, no normalised line | group with the awk parser first |
| server blamed for a client mod | `Base` points into a module range, not the game | ask for a clean client before touching the gamemode |
| object crash after a map update | stream distance raised together with the new objects | lower stream distance or split the map |
| crash only for one player | local files, not the script | reproduce on a second clean install |
| "opcode 0x… is the bug" claim | number taken from a thread, not from the block | require the log line; without it the claim is dropped |
| skin crash during vehicle entry | `SetPlayerSkin` called from a timer while entering | gate with `IsPlayerInAnyVehicle`, retry on foot |

## Verification

```bash
awk -F': *' '/Exception At Address/{a=$2} /^Base/{b=$2} /^SCM Op/{s=$2; sub(/,.*/,"",s); o=$4} END{printf "addr=%s base=%s scm=%s obj=%s\n", a, b, s, o}' crash.log
```

Expected on the block above: `addr=0x52EF7D90 base=0x036C0000 scm=0x0 obj=0`.

```bash
grep -c "Exception At Address" crash.log; grep -c "SCM Op" crash.log
```

Expected: `1` and `1`. Two addresses in one file means two crashes were concatenated; split them before grouping, or the signature count is wrong.

## Sources (2026)

- [open.mp — Client Crash Addresses](https://open.mp/docs/client/CrashAddresses) — published address table with cause and fix, plus the chatbox "Exception" codes.
- [open.mp forum — thread 2767](https://forum.open.mp/showthread.php?tid=2767) — a complete 0.3.DL-R1 crash block, including the `SCM Op: 0x0` case quoted above.
