---
name: runtime-error-4-bounds-check
description: Use when error 4 kills the script on one bad index.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, crash]
    category: samp
---

# Run time error 4: array index out of bounds

## When to Use

- The server log shows `[debug] Run time error 4: "Array index out of bounds"` and the mode stops.
- An id that came from a dialog `listitem`, a packet field, a config file or a DB row indexes a fixed
  array.
- The crash reproduces only with one argument, one slot or one vehicle model.
- You patched one site and the next tick dies on a different array fed by the same id.
- A lookup that can fail returns `-1` and the caller indexes with it.

## Compatibility & Stack Matrix (2026)

| Component | Version | Notes |
| --- | --- | --- |
| open.mp server | 1.x | the AMX traps the bad index and prints run time error 4 |
| crashdetect | 4.x | prints the error plus a backtrace with `file.pwn:line` and argument values |
| crashdetect load order | first plugin | otherwise it logs that it must be loaded before the others |
| pawncc | 3.10.10+ | `-d3` keeps symbols, without it the frame is a hex address |
| pawncc | `-O0` | keeps the failing access at the line you wrote while you hunt |
| Pawn arrays | language | fixed length, and a negative index is as fatal as an oversized one |
| `sizeof` | language | on an array *parameter* it is not the caller's length — pass the count |

## Production Implementation

1. Build a debug AMX and reproduce with the exact input recorded in the backtrace:

```bash
pawncc -i./includes -d3 -O0 -ogamemodes/main.amx gamemodes/main.pwn
```

2. Read the first frame that lives in your own script. In this example line 812 is the array access,
   and `cmdtext[]="give 999"` is the input that produced the index:

```text
[debug] Run time error 4: "Array index out of bounds"
[debug] AMX backtrace:
[debug] #0 00002c4c in public OnPlayerCommandText (playerid=0, cmdtext[]="give 999") at gamemodes/main.pwn:812
```

3. Guard where the index is *created*, not only where the array is read. A guard at the read site
   leaves the bad value alive for the next array:

```pawn
#define SLOT_COUNT (64)
#define INVALID_SLOT (-1)

new gSlotOwner[SLOT_COUNT];

stock bool:ValidSlot(slot)
{
    if (slot < 0 || slot >= SLOT_COUNT)
    {
        printf("[bounds] slot=%d outside 0..%d", slot, SLOT_COUNT - 1);
        return false;
    }
    return true;
}
```

4. Refuse, do not clamp. A `%` or a `min()` turns a crash into a silent write to the wrong row, and
   the wrong row is harder to find than the crash was:

```pawn
new slot = strval(params);
if (!ValidSlot(slot))
{
    SendClientMessage(playerid, 0xFFFFFFFF, "No such slot.");
    return 1;
}
gSlotOwner[slot] = playerid;
```

5. Route every read of a sparse table through one accessor so the check cannot be forgotten:

```pawn
stock GetSlotOwner(slot)
{
    return ValidSlot(slot) ? gSlotOwner[slot] : INVALID_SLOT;
}
```

6. Check the loops, which are the other half of error 4. `<=` on a `sizeof` bound reads one cell past
   the end every single time the loop completes:

```pawn
for (new i = 0; i < sizeof(gSlotOwner); i++)   // right
// for (new i = 0; i <= sizeof(gSlotOwner); i++) // error 4 on the last pass
```

7. Look at the five producers that account for almost every report before you touch the array:

- dialog `listitem` used as an entity id without consulting the list that produced it;
- `strval` / `sscanf` output used directly as an index;
- a "not found" helper returning `-1`, then indexed;
- a table indexed by weapon id or model id with holes in the valid range;
- `sizeof` of an array parameter, which is one element and not the caller's array length.

8. Replay the recorded input after the fix, keep the guard in place as the regression test, and count
   the signature so a repeat is provable:

```bash
grep -c 'Run time error 4' log.txt
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Backtrace shows only hex addresses | AMX built at `-d1`/`-d2` | rebuild with `-d3`, redeploy the `.amx` |
| The reported frame is inside a native | reading the stack upwards from the wrong end | start at the first frame that names your `.pwn` file |
| Error persists with index 0 | a second index on the same line, e.g. `arr[a][b]` | check both dimensions, not just the first |
| Fixed one site, crash moves one function down | the bad id is reused | guard at the producer of the id |
| Crash only with the optimiser on | `-O2` reshaping the surrounding code | keep `-d3 -O0` for the hunt, then fix the index maths |
| Loop finishes without tripping the guard but still crashes | `<=` against `sizeof` | use `<` |
| `sizeof(arr)` inside a function returns 1 | `arr` is a parameter, not the array | pass the length as an argument |

## Verification

```bash
pawncc -i./includes -d3 -O0 -ogamemodes/main.amx gamemodes/main.pwn && echo "debug build ok"
: > log.txt          # truncate, then replay the exact command from the backtrace
grep -c 'Run time error 4' log.txt
grep -nE '\[[a-z_]*id\]|\[slot\]|\[listitem\]' gamemodes/*.pwn | grep -v ValidSlot
```

Expected output — the build keeps symbols, the replay adds no error, and the grep lists only the
index sites that still need a guard:

```text
debug build ok
0
```

```text
gamemodes/main.pwn:812:    gSlotOwner[slot] = playerid;
```

## Sources (2026)

- https://github.com/AmyrAhmady/samp-plugin-crashdetect
- https://github.com/AmyrAhmady/samp-plugin-crashdetect/wiki/Compiling-scripts-with-debug-info
- https://open.mp/docs/server/CommonServerIssues
