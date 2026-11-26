---
name: encoding-crlf-ansi-guard
description: Use when Pawn sources pick up CRLF, BOM or ANSI.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, encoding, ci]
    category: samp
---

# UTF-8 without BOM, LF endings, enforced by a gate

## When to Use

- A Windows editor commits CRLF and every line shows as changed in review.
- Chat or a dialog shows `?` or mojibake for accented and Cyrillic text.
- A map or config row read with `fread` carries a stray byte at the end of the last field.
- A file compiles for one developer and fails for another with error 077.
- You are adding a CI step and need the exact detection commands.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| pawncc | 3.10.10+ | accepts UTF-8 source; expands wide chars to UCS-4 in unpacked strings |
| source encoding | UTF-8, **no BOM** | BOM is optional for the compiler but breaks grep/awk and our own readers |
| line endings | LF (`\n`) everywhere | CRLF leaves `\r` on the last field of every `fread` line |
| legacy text | CP1251 / CP1252 | must be converted once, in its own commit |
| git | 2.4+ for `--renormalize`, `ls-files --eol` | `.gitattributes` is the only durable fix |
| CI | any Linux runner with `file`, `grep`, `iconv` | no extra tooling needed |

Pawn source files are UTF-8 (ASCII is a valid subset). The compiler only interprets UTF-8 inside unpacked strings and character constants; packed strings stay raw bytes, which is why a converted file can change packed-string output length.

## Production Implementation

1. Write the policy down once, in the repo, next to the code — not in a chat message:

```markdown
Sources are UTF-8 without BOM, LF line endings. Non-ASCII text lives in
`gamemodes/lang.inc` and nowhere else. Convert in a dedicated commit.
```

2. Pin the endings in `.gitattributes` so a Windows checkout cannot reintroduce CRLF. `text=auto` alone is not enough: it normalises on commit but leaves the working tree in the platform default.

```gitattributes
* text=auto eol=lf
*.pwn text eol=lf
*.inc text eol=lf
*.cfg text eol=lf
*.map text eol=lf
*.amx binary
```

3. Renormalise the existing tree once, after the attribute file is committed:

```bash
git add .gitattributes
git commit -m "chore: pin LF in gitattributes"
git add --renormalize .
git status --short
git commit -m "chore: renormalise line endings (no logic change)"
```

4. Detect the three defects with the tools already on the box. `file` classifies, `grep -Il` lists the offenders:

```bash
file --mime-encoding -b gamemodes/*.pwn gamemodes/*.inc | sort -u
grep -Il $'\r' gamemodes/*.pwn gamemodes/*.inc
grep -Il $'\xEF\xBB\xBF' gamemodes/*.pwn gamemodes/*.inc
```

The first command must print only `us-ascii` and/or `utf-8`. `iso-8859-1` or `unknown-8bit` is an ANSI file; the two greps must print nothing.

5. Convert only what the detection flagged, and keep the conversion out of logic commits. `iconv` fails loudly on bytes that are not valid CP1251, which is the point — a silent conversion is how strings get mangled.

```bash
iconv -f CP1251 -t UTF-8 gamemodes/old.pwn > /tmp/old.pwn && mv /tmp/old.pwn gamemodes/old.pwn
dos2unix gamemodes/*.pwn gamemodes/*.inc
```

6. Guard the runtime side. Bytes arriving from a file or a client are not the compiled literals: `fread` gives raw bytes, so a BOM or `\r` survives into your parser. Drop the three leading `0xEF 0xBB 0xBF` bytes in the reader, and reject invalid UTF-8 before it reaches the database or chat.

```pawn
stock bool:IsValidUtf8(const s[])
{
    for (new i = 0; s[i]; )
    {
        new c = s[i] & 0xFF;

        if (c < 0x80) { i++; continue; }
        if (c < 0xC2 || c > 0xF4) return false;   // overlong, surrogate or > U+10FFFF

        new need = (c < 0xE0) ? 1 : (c < 0xF0) ? 2 : 3;
        for (new k = 1; k <= need; k++)
        {
            new cc = s[i + k] & 0xFF;
            if (cc < 0x80 || cc > 0xBF) return false;
        }
        i += need + 1;
    }
    return true;
}

stock bool:CleanTextInput(const src[], dest[], size)
{
    if (!IsValidUtf8(src)) return false;

    new j;
    for (new i = 0; src[i] != '\0' && j < size - 1; i++)
    {
        new c = src[i] & 0xFF;
        if (c == 0x0D || c == 0x0A || c == 0x09) continue;   // CR, LF, TAB
        if (c < 0x20) continue;                              // other control bytes
        dest[j++] = src[i];
    }
    dest[j] = '\0';
    return true;
}
```

7. Put step 4 in CI and fail the build. A gate that only prints is ignored after the second week.

```bash
set -e
if grep -Il $'\r' gamemodes/*.pwn gamemodes/*.inc | grep -q .; then
  echo "CRLF found:"; grep -Il $'\r' gamemodes/*.pwn gamemodes/*.inc; exit 1
fi
if grep -Il $'\xEF\xBB\xBF' gamemodes/*.pwn gamemodes/*.inc | grep -q .; then
  echo "BOM found:"; grep -Il $'\xEF\xBB\xBF' gamemodes/*.pwn gamemodes/*.inc; exit 1
fi
for f in gamemodes/*.pwn gamemodes/*.inc; do
  iconv -f UTF-8 -t UTF-8 "$f" > /dev/null || { echo "invalid UTF-8: $f"; exit 1; }
done
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| every line marked changed in review | CRLF committed from a Windows editor | `.gitattributes` + `git add --renormalize .` in its own commit |
| `?` where an accent should be | file saved as CP1251/CP1252 | `iconv -f CP1251 -t UTF-8`, then re-check with `file` |
| rewrite of every string in a logic PR | conversion mixed into a feature commit | convert first, merge, then the logic change |
| first row of a map/config ignored | UTF-8 BOM before the first token | strip BOM on read; ban it in CI |
| last numeric field fails to parse | `\r` left by CRLF, `fread` keeps it | LF policy, plus strip `\r` at the reader |
| error 077 on one machine only | file contains invalid UTF-8 bytes | `iconv -f UTF-8 -t UTF-8` to locate, then fix the source bytes |
| chat accepts line breaks | input copied straight into `SendClientMessage` | `CleanTextInput` before formatting |

## Verification

```bash
file --mime-encoding -b gamemodes/*.pwn gamemodes/*.inc | sort -u
```

Expected on a clean tree: only `us-ascii` and/or `utf-8`. `iso-8859-1` is the ANSI defect and must not appear.

```bash
grep -Il $'\r' gamemodes/*.pwn gamemodes/*.inc; grep -Il $'\xEF\xBB\xBF' gamemodes/*.pwn gamemodes/*.inc
git ls-files --eol gamemodes/ | grep -v "i/lf" | grep -v "i/none"
```

Expected: no output from either command — no CRLF, no BOM, and index plus working tree at `i/lf`. On a dirty tree the first command prints the CRLF file and `git ls-files` prints `i/crlf` or `w/crlf` for the same path.

## Sources (2026)

- [open.mp — Pawn language appendices](https://open.mp/docs/scripting/language/reference/Appendices) — UTF-8 input support, optional BOM, error 077 for malformed UTF-8.
- [open.mp — Assorted tips](https://open.mp/docs/scripting/language/reference/Assorted-tips) — UTF-8 source expands to UCS-4 in unpacked strings, packed strings stay UTF-8 bytes.
- [Git — gitattributes](https://git-scm.com/docs/gitattributes) — `text`, `eol=lf`, and renormalisation semantics.
