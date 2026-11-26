---
name: encoding-crlf-ansi-guard
description: Keep Pawn sources UTF-8 and line endings stable.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, encoding]
    category: samp
---

# encoding and line endings

## When to Use
- Windows editors introduce CRLF or CP1251 characters that break chat text.
- A file compiles locally but shows mojibake on the server.

## 2026 Compatibility & Architecture Matrix
- open.mp reads UTF-8; legacy 0.3.7 clients may render CP1251 depending on the client build.
- Git `text=auto` plus `.gitattributes` keeps LF in the repo.

## Production Implementation
1. Add `.gitattributes` with `*.pwn text eol=lf` and `*.inc text eol=lf`.
2. Convert existing files once and commit the conversion separately from logic changes.
3. Keep non-ASCII strings in one include so they can be audited.

```gitattributes
*.pwn text eol=lf
*.inc text eol=lf
```

## Deprecated Traps & Edge Cases (2026)
- Converting encoding inside a logic commit hides the real diff.
- A BOM at the start of an include is a compile error in some compilers.

## Verification
- `file *.pwn` reports UTF-8/ASCII and no CRLF.
- Chat text with accents renders correctly on the target client.
