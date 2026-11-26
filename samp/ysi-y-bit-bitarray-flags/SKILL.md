---
name: ysi-y-bit-bitarray-flags
description: Use when per-player booleans waste memory.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi, memory]
    category: samp
---

# Pack per-player flags into a y_bit BitArray

Four booleans per player is four cells, sixteen bytes, times `MAX_PLAYERS`. The same data as bits
is one cell per thirty-two flags. y_bit exposes that as `BitArray`, addressed by a flat slot index,
so the arithmetic mapping player plus flag to slot is the whole design.

## When to Use

- A dozen booleans per player are spread across modules and the struct keeps growing.
- You need one bit per player per feature and want it cheap to scan across files.

## Compatibility & Stack Matrix (2026)

| API | Signature | Effect |
| --- | --- | --- |
| declaration | `new BitArray:name<100>;` | 100 bits, roughly 20 bytes |
| `Bit_Get` | `(BitArray:array, slot)` | returns 0 or 1 |
| `Bit_Set` | `(BitArray:array, slot, bool:set, size = sizeof (array))` | set or clear one bit |
| `Bit_Let` | `(BitArray:array, slot)` | set to 1, faster than `Bit_Set` |
| `Bit_Vet` | `(BitArray:array, slot)` | set to 0, faster than `Bit_Set` |
| `Bit_SetAll` | `(BitArray:array, bool:set, size = sizeof (array))` | every bit at once |
| `Bit_Count` | `(BitArray:array, size = sizeof (array))` | number of bits set to 1 |
| include | `#include <YSI_Data/y_bit>` | path is `YSI_Data`, not `YSI_Coding` |

The declared size is in bits, not cells: `new BitArray:x<MAX_PLAYERS>;` is one bit per player,
with nothing left for a second flag.

## Production Implementation

1. Declare one array for the server and one enum for the flags. A slot is
   `playerid * FLAG_COUNT + flag`, so enum values start at 0 and stay dense.

```pawn
#include <YSI_Data/y_bit>

enum E_FLAG
{
    FLAG_JAILED = 0,
    FLAG_MUTED,
    FLAG_DUTY,
    FLAG_WANTED,
    FLAG_COUNT          // always last, always the count
};

#define FLAG_SLOTS (MAX_PLAYERS * _:FLAG_COUNT)
new BitArray:g_Flags<FLAG_SLOTS>;
```

2. Wrap the arithmetic in helpers so every read and write goes through one place. A later layout
   change is then one edit, not a hunt for magic indexes.

```pawn
stock Flag_Slot(playerid, E_FLAG:flag)
{
    return playerid * _:FLAG_COUNT + _:flag;
}

stock bool:Flag_Get(playerid, E_FLAG:flag)
{
    if (playerid < 0 || playerid >= MAX_PLAYERS) return false;
    return Bit_Get(g_Flags, Flag_Slot(playerid, flag)) != 0;
}
```

3. Set through `Bit_Set` when the value is computed, and through `Bit_Let` or `Bit_Vet` when it
   is a literal. Log only on a real transition, otherwise the log becomes write-only.

```pawn
stock Flag_Set(playerid, E_FLAG:flag, bool:value)
{
    if (playerid < 0 || playerid >= MAX_PLAYERS) return 0;

    new slot = Flag_Slot(playerid, flag);
    if ((Bit_Get(g_Flags, slot) != 0) == (_:value != 0)) return 1;   // already there

    Bit_Set(g_Flags, slot, value);
    if (flag == FLAG_JAILED || flag == FLAG_MUTED)
        printf("FLAG player=%d flag=%d value=%d", playerid, _:flag, _:value);
    return 1;
}

stock Flag_Jail(playerid)   { Bit_Let(g_Flags, Flag_Slot(playerid, FLAG_JAILED)); return 1; }
stock Flag_Unjail(playerid) { Bit_Vet(g_Flags, Flag_Slot(playerid, FLAG_JAILED)); return 1; }
```
4. Reset the player's bits on connect. Bits are not attached to the player struct, so a jail flag
   survives a disconnect unless something clears it.

```pawn
stock Flag_ResetPlayer(playerid)
{
    for (new f = 0; f < _:FLAG_COUNT; f++)
        Bit_Set(g_Flags, Flag_Slot(playerid, E_FLAG:f), false);
    return 1;
}

public OnPlayerConnect(playerid)
{
    Flag_ResetPlayer(playerid);
    return 1;
}
```
5. Clear the array once at boot with `Bit_SetAll`, documented as 32 times faster than a loop, and
   report totals with `Bit_Count` (set bits, not players, so divide by flags per player).

```pawn
public OnGameModeInit()
{
    Bit_SetAll(g_Flags, false);
    printf("FLAGSMOKE slots=%d bytes=%d", FLAG_SLOTS, (FLAG_SLOTS + 31) / 32 * 4);
    return 1;
}
```

6. Record the cost where the array is declared: `FLAG_SLOTS` bits is `(FLAG_SLOTS + 31) / 32`
   cells, against four bytes per flag per player for the `bool:` equivalent.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `cannot read from file: YSI_Coding/y_bit` | YSI 5.x moved the include | `#include <YSI_Data/y_bit>` |
| Two players share a flag | slot computed as `playerid + flag` | multiply: `playerid * FLAG_COUNT + flag` |
| Second flag overwrites the first player's data | declared `<MAX_PLAYERS>` instead of total bits | size the array in bits |
| Other players randomly lose flags | slot past the declared size, `Bit_Set` writes into the next cell | check `playerid`, keep the enum dense |
| Jail flag survives rejoin | nothing clears the bit on connect | reset the player's flags in `OnPlayerConnect` |

## Verification

Compile and read the boot line; the byte figure proves the declared size is what you think:

```bash
sampctl build 2>&1 | tail -2
grep -m1 "FLAGSMOKE" log.txt
```

```text
Build complete; written to gamemodes/main.amx
FLAGSMOKE slots=4000 bytes=500
```

Then round-trip one flag and read it back beside an untouched one:

```pawn
Flag_Set(0, FLAG_JAILED, true);
printf("FLAGTEST jailed=%d muted=%d", Flag_Get(0, FLAG_JAILED), Flag_Get(0, FLAG_MUTED));
```

```text
FLAG player=0 flag=0 value=1
FLAGTEST jailed=1 muted=0
```

The untouched flag reading 0 is the proof the two slots do not overlap. If both read 1, the slot
arithmetic is missing the `FLAG_COUNT` multiplier.

## Sources (2026)

- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Data/y_bit.md
- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Data/y_bit/quick-start.md
