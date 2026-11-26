---
name: custom-include-api-design
description: Use when a Pawn include is called by other scripts.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, include, api]
    category: samp
---

# Design a Pawn include callers never have to read

## When to Use

- Two scripts copy the same helper and the copies drift.
- One added parameter breaks every caller, so nobody wants to touch the file.
- An include leaks globals or redefines a native and the build starts warning.
- You need one include that works on open.mp and still compiles for a 0.3.7 target.
- Not for resolving include search paths; that is `include-dependency-resolver`.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| Compiler | `pawncc` 3.10.10 | `-;+` and `-(+` are what expose sloppy signatures |
| Guard | `#if defined _name_included` + `#endinput` | a second include must cost zero symbols |
| Visibility | `stock` for functions | unused `stock` emits no code and no warning |
| Tags | one declarator per handle | `new Text:a, b;` tags only `a` |
| Optional deps | `#tryinclude` + `#error` on a feature macro | hard `#include` forces every caller to ship the dep |
| Deprecation | comment + `stock` alias | `#pragma deprecated` is sticky for the rest of the unit |

## Production Implementation

1. Start with the guard and the version macros. The guard must be unique to the file, not the folder:

```pawn
// ferz_tag.inc - player tag API, v1.1.0
#if defined _ferz_tag_included
    #endinput
#endif
#define _ferz_tag_included

#define FERZ_TAG_VERSION        (10100)     // 10000*major + 100*minor + patch
#define FERZ_TAG_VERSION_STR    "1.1.0"
#define FERZ_TAG_LEN            (24)
```

2. Keep optional dependencies optional, and fail loudly when the feature macro is set but the
   dependency is missing:

```pawn
#if defined FERZ_TAG_WITH_STREAMER
    #tryinclude <streamer>
    #if !defined _streamer_included
        #error FERZ_TAG_WITH_STREAMER is set but <streamer> is not on the include path
    #endif
#endif
```

3. Give the caller a real enum instead of magic numbers, and write the API as `stock` functions with
   `const` inputs and a fixed output buffer declared in the signature. The caller cannot pass the
   wrong size, and an unused function costs nothing:

```pawn
enum E_FERZ_TAG_STYLE
{
    ferzTagPlain = 0,
    ferzTagBracket,
    ferzTagColour
};

stock FerzTag_Version()
{
    return FERZ_TAG_VERSION;
}

stock FerzTag_Format(dest[FERZ_TAG_LEN], const name[], E_FERZ_TAG_STYLE:style = ferzTagPlain)
{
    switch (style)
    {
        case ferzTagBracket: format(dest, FERZ_TAG_LEN, "[%s]", name);
        case ferzTagColour:  format(dest, FERZ_TAG_LEN, "{FFFFFF}%s", name);
        default:             format(dest, FERZ_TAG_LEN, "%s", name);
    }
    return strlen(dest);
}
```

4. Rename without breaking callers. The alias stays, and the warning lives in the changelog, not
   in `#pragma deprecated` - the pragma applies to every symbol declared after it, including the
   caller's own `main`:

```pawn
// Renamed in 1.1.0. No #pragma deprecated: it is sticky for the rest of the
// translation unit and marks the caller's next function (warning 234).
stock FerzTag_Build(dest[FERZ_TAG_LEN], const name[])
{
    return FerzTag_Format(dest, name);
}
```

5. Prove the contract from the caller side, including a double include. If the second line
   produces any symbol, the guard is wrong:

```pawn
#include <open.mp>
#include <ferz_tag>
#include <ferz_tag>     // must be a no-op

main()
{
    new tag[FERZ_TAG_LEN];
    FerzTag_Format(tag, "Aegis", ferzTagBracket);
    printf("api=%d str=%s tag=%s", FerzTag_Version(), FERZ_TAG_VERSION_STR, tag);
}
```

6. Compile it exactly the way the pack compiles gamemodes, then repeat with the optional feature on
   to prove the error path. A command-line define is `sym=val`; `-D` is the active directory, not a
   define:

```bash
pawncc -i"$HOME/samp-sdk/omp-stdlib" -iincludes -d3 '-;+' '-(+' -oprobe_api.amx probe_api.pwn
pawncc -i"$HOME/samp-sdk/omp-stdlib" -iincludes 'FERZ_TAG_WITH_STREAMER=1' probe_api.pwn   # must #error
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `symbol already defined` on the second include | guard missing or guard name differs from the file | `#if defined _x_included` + `#endinput` first |
| `warning 234: function is deprecated (symbol "main")` | `#pragma deprecated` used before the alias | drop the pragma, keep the alias and a changelog note |
| `warning 213: expected tag none, found "Text"` | array of tagged handles, element is untagged | cast on assignment: `g[i] = Text:TextDrawCreate(...)` |
| `warning 213` on the second handle of a list | `new Text:a, b;` tags only the first name | one declarator per handle |
| `#error` fires for every caller | optional dependency made mandatory | guard it with `#if defined` and `#tryinclude` |
| Command-line `-DFOO` is ignored | `-D` sets the active directory, not a symbol | pass the bare `FOO=1` argument instead |
| Include compiles alone, fails in a gamemode | it declares a native no plugin provides | keep natives behind a feature macro, ship a `stock` fallback |

## Verification

```bash
cd "$HOME/.hermes/cache/scratch/skillprobe"
pawncc -i/home/aegisx/samp-sdk/omp-stdlib -iincludes -d3 '-;+' '-(+' \
       -oprobe_api.amx probe_api.pwn; echo "exit=$?"
```

Expected output for a correct API - zero diagnostics, a full compile report, exit `0`:

```text
Pawn compiler 3.10.10	 	 	 	Copyright (c) 1997-2006, ITB CompuPhase

Header size:            260 bytes
Code size:              604 bytes
Data size:              216 bytes
Stack/heap size:      16384 bytes; estimated max. usage=73 cells (292 bytes)
Total requirements:   17464 bytes
exit=0
```

Any `warning 213` here means a tag is being dropped between the include and the caller. Run the
`FERZ_TAG_WITH_STREAMER=1` variant afterwards: it must stop with
`fatal error 111: user error: FERZ_TAG_WITH_STREAMER is set but <streamer> is not on the include path`
and exit `1`, not compile.

## Sources (2026)

- https://compuphase.com/pawn/pawn.htm
- https://open.mp/docs/scripting/language/reference/Appendices
- https://github.com/pawn-lang/compiler
