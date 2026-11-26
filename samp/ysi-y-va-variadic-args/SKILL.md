---
name: ysi-y-va-variadic-args
description: Use when one printf-style wrapper must serve every caller.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi, strings, varargs]
    category: samp
---

# Forward `...` with y_va instead of duplicating format calls

## When to Use

- A helper needs to accept a format string plus a variable tail, like `printf` does.
- You are copy-pasting `format(); SendClientMessage();` at every call site because a `stock` cannot
  forward its own `...` to `format`.
- `va_formatex` or an old YSI version is throwing a deprecation warning.
- Not for sizing a chat buffer for one fixed message; that is `pawn-development`.

## Compatibility & Stack Matrix (2026)

| API | Declared form | What it actually does |
| --- | --- | --- |
| `va_format` | `native va_format(output[], len, const format[], ...) = format` | alias of `format`: forwards the tail, `len` stays the hard cap |
| `va_printf` | `native va_printf(const format[], ...) = printf` | alias of `printf` |
| `va_CallLocalFunction` | `native va_CallLocalFunction(const function[], const format[], ...)` | alias of `CallLocalFunction` |
| `va_SetTimerEx` | `native va_SetTimerEx(const function[], interval, bool:repeating, const format[], ...)` | alias of `SetTimerEx` |
| `va_SendClientMessage` | open.mp build only | formats and sends in one call, no user buffer |
| `va_ShowPlayerDialog`, `va_TextDrawCreate`, `va_PlayerTextDrawSetString` | open.mp build only | same pattern for the other string natives |
| `va_args<>`, `va_start<n>`, `___` | macros | pass the tail on; `n` is the count of **named** parameters |
| `va_formatex` | `forward`, marked deprecated | kept for old code, use `formatex` |

It does not make a buffer bigger. `va_format` is `format` with a forwarding mechanism (the PUSH.C rewrite
Zeex documented), so an oversized payload is still cut silently at `len`.

## Production Implementation

1. Include the library once, at the top of the file that defines the wrapper:

```pawn
#include <open.mp>                 // first: y_va only exposes the omp aliases once this is defined
#include <YSI_Coding/y_va>
```

2. Write the wrapper with `va_args<>` in the signature and `va_start<n>` at the call, where `n` is the
   number of parameters **before** the `...` — here `playerid`, `colour`, `fmt`:

```pawn
stock SendFormatted(playerid, colour, const fmt[], va_args<>)
{
    new buf[144];
    va_format(buf, sizeof buf, fmt, va_start<3>);
    SendClientMessage(playerid, colour, buf);
    return 1;
}

// SendFormatted(playerid, 0xFFFFFFFF, "%s joined with %d score", name, score);
```

3. Size for the payload, not for the format string. A chat line is 144 cells on the legacy client, so the
   buffer is 144 and the payload budget is what remains after the fixed text:

```pawn
#define CHAT_CELLS      (144)
#define NAME_CELLS      (24 + 1)
#define PKT_TEXT_CELLS  (128)
```

4. When the caller has nothing to interpolate, YSI takes a fast path and passes the string straight through
   instead of running `format`; that is why the no-argument case must still be tested. The public aliases
   handle it internally, a hand-written wrapper does not:

```pawn
stock SendPlain(playerid, colour, const fmt[])
{
    SendClientMessage(playerid, colour, fmt);      // no format, no copy, no truncation
}

stock SendFormatted(playerid, colour, const fmt[], va_args<>)
{
    new buf[CHAT_CELLS];
    va_format(buf, sizeof buf, fmt, va_start<3>);
    SendClientMessage(playerid, colour, buf);
}
```

5. On open.mp, skip the buffer entirely for the natives that already have a `va_` alias:

```pawn
#if defined _INC_open_mp
    va_SendClientMessage(playerid, 0xFFFFFFFF, "%s joined", name);
#endif
```

6. Cut UTF-8 on a character boundary, never in the middle of a sequence, and cut the **input** before it
   reaches the format:

```pawn
stock Utf8Cut(dest[], size, const src[])
{
    new len = strlen(src);
    if (len < size - 1) { strcat(dest, src, size); return; }
    new cut = size - 1;
    while (cut > 0 && (src[cut] & 0xC0) == 0x80) cut--;   // skip continuation bytes
    strmid(dest, src, 0, cut, size);
}

stock SendName(playerid, const name[])
{
    new safe[NAME_CELLS];
    Utf8Cut(safe, sizeof safe, name);
    SendFormatted(playerid, 0xFFFFFFFF, "Player %s connected", safe);
}
```

7. Test the three shapes every wrapper has: no placeholders, one placeholder with a 24-character name, and
   a UTF-8 message that is longer than the buffer.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error 017: undefined symbol "va_start"` | `y_va` not included in that file | `#include <YSI_Coding/y_va>` |
| arguments arrive garbled, or the server crashes on the call | `va_start<n>` where `n` is the vararg count instead of the named count | count the parameters before `...` |
| `error 035: argument type mismatch` | wrapper declared with a bare `...` | declare `va_args<>` |
| message ends mid-name, no warning | `va_format` honoured `len`, exactly like `format` | size for the worst case and cut the inputs |
| works when formatting, crashes with a plain string | the wrapper always runs `format`, even with no arguments | add a `SendPlain` variant that skips `format` |
| a character is broken at the cut | truncation landed inside a UTF-8 sequence | cut on a boundary, or clamp the name first |
| deprecation warning on `va_formatex` | old include still forwards to it | replace with `formatex` or `va_format` |

## Verification

```bash
pawncc gamemodes/rp.pwn -iinclude -d3 -O1 -ogamemodes/rp.amx 2>&1 | tee build.log
grep -cE "warning 2(02|17|13)|error 0" build.log
```

Expected output: `exit=0` from the compiler and a zero count, which is the only reliable proof that the
tag list on the wrapper matches every call site:

```text
0
```

Then exercise the three shapes at runtime and read the log:

```bash
grep -E "\[va\]" server.log
```

```text
[va] plain="server restarting"
[va] long_name="Player ABCDEFGHIJKLMNOPQRSTUVWX connected"
[va] utf8="Player ТестТест connected"
```

## Sources (2026)

- https://raw.githubusercontent.com/pawn-lang/YSI-Includes/master/YSI_Coding/y_va/y_va_header.inc
- https://raw.githubusercontent.com/pawn-lang/YSI-Includes/master/YSI_Coding/y_va/y_va_impl.inc
- https://open.mp/docs/scripting/functions/format
