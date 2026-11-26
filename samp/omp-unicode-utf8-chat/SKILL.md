---
name: omp-unicode-utf8-chat
description: Use when UTF-8 names or chat render as mojibake.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, i18n]
    category: samp
---

# UTF-8 in chat and names

## When to Use

- Cyrillic, Greek or CJK names show as boxes or `????` on one client and fine on another.
- A nickname of 20 visible characters is rejected as "too long".
- Validation or truncation cuts a multi-byte character in half and the tail renders as a stray glyph.
- MySQL stores `????` after `SetPlayerName` or a registration.
- A chat line under 144 characters is dropped by the client anyway.

## Compatibility & Stack Matrix (2026)

| Component | Version | Notes |
| --- | --- | --- |
| open.mp server | 1.x | forwards text as raw bytes, no transcoding, no normalisation |
| open.mp client (launcher) | 1.x | renders UTF-8 natively |
| SA-MP 0.3.7 client | R5 | renders the local codepage; UTF-8 Cyrillic arrives as mojibake |
| `fwrite` / file IO | open.mp 1.x | documented as UTF-8 |
| Pawn string | unpacked `new s[24]` | one byte per cell, so `strlen` returns bytes, not characters |
| MySQL column | `utf8mb4` | needed for 4-byte sequences; `utf8` (3-byte) truncates emoji |
| Name limit | `MAX_PLAYER_NAME` = 24 | `SetPlayerName` allows 24 characters, the browser allows 3-20 |
| Text limits | input 128 cells (512 bytes), output 144 cells, textdraw 1024 | from the open.mp limits page |

## Production Implementation

1. Fix storage before touching code; a `latin1` column destroys the bytes on write, so no script fix
   helps afterwards:

```sql
ALTER TABLE accounts CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE accounts MODIFY name VARCHAR(24) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;
```

`utf8mb4_bin` keeps uniqueness byte-exact, which is what you want for names.

2. Count characters, not bytes. This returns the code point count and rejects an invalid lead or a
   stray continuation byte:

```pawn
stock Utf8CharCount(const s[])
{
    new count, i = 0;
    while (s[i])
    {
        new c = s[i];
        if (c < 0x80) i += 1;                 // 0xxxxxxx
        else if ((c & 0xE0) == 0xC0) i += 2;  // 110xxxxx
        else if ((c & 0xF0) == 0xE0) i += 3;  // 1110xxxx
        else if ((c & 0xF8) == 0xF0) i += 4;  // 11110xxx
        else return -1;                       // malformed sequence
        count++;
    }
    return count;
}
```

3. Truncate on a boundary; never `dest[max] = '\0'` after copying bytes, which cuts a character:

```pawn
stock Utf8Truncate(dest[], size, const src[], max_chars)
{
    new i = 0, chars = 0, len = 0;
    while (src[i] && chars < max_chars)
    {
        new c = src[i], step = 1;
        if (c >= 0xF0) step = 4;
        else if (c >= 0xE0) step = 3;
        else if (c >= 0xC0) step = 2;
        if (i + step > size - 1) break;
        i += step;
        len = i;
        chars++;
    }
    for (new k = 0; k < len; k++) dest[k] = src[k];
    dest[len] = '\0';
    return chars;
}
```

4. Validate the nickname where it enters the server, with the character count and the byte size both
   bounded:

```pawn
public OnPlayerConnect(playerid)
{
    new name[MAX_PLAYER_NAME + 1];
    GetPlayerName(playerid, name, sizeof(name));
    new chars = Utf8CharCount(name);
    if (chars < 1 || chars > MAX_PLAYER_NAME)
    {
        SendClientMessage(playerid, 0xFFFFFFFF, "Your name is not a valid character length.");
        return 1;
    }
    return 1;
}
```

5. Re-read the name from the native after a rename. A case-only rename is silently refused, and you
   would otherwise cache the name the player asked for instead of the name the server kept:

```pawn
SetPlayerName(playerid, requested);
new actual[MAX_PLAYER_NAME + 1];
GetPlayerName(playerid, actual, sizeof(actual));
```

6. Keep the output budget in characters: 144 for chat output and bubbles, 1024 for a textdraw
   string. A 128-character Cyrillic line is up to 256 bytes and the client drops it without an error.

7. Decide the mixed-client policy up front. `GetPlayerVersion` says which build connected, so a 0.3.7
   client can get a transliterated fallback while the open.mp client gets the real string:

```pawn
new version[64];
GetPlayerVersion(playerid, version, sizeof(version));
```

8. Never pass user text as the format string; `%` inside an argument is harmless, `%` as the format is
   a crash: `format(line, sizeof(line), "%s", userText);`

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Text is correct on open.mp clients, mojibake on 0.3.7 | the old client renders the local codepage | transliterate a fallback for that build, or restrict the charset at registration |
| `????` appears after an UPDATE | column or connection is `latin1` | `CONVERT TO utf8mb4`, then fix the connection charset |
| 20-character Cyrillic nick rejected | validation counts bytes with `strlen` | use `Utf8CharCount`, keep the 24-character limit |
| Trailing glyph is a replacement box | string cut at a byte offset | truncate with `Utf8CharCount`/`Utf8Truncate` |
| Chat line vanishes with no error | output over 144 cells after encoding | trim in characters before sending |
| Two accounts look identical but both register | byte-exact uniqueness plus lookalike letters | fold the alphabet you allow into a lookup key |

## Verification

```bash
mysql -N -B -e "SELECT COLUMN_NAME, CHARACTER_SET_NAME FROM information_schema.COLUMNS \
  WHERE TABLE_SCHEMA='ucp' AND TABLE_NAME='accounts' AND COLUMN_NAME='name';"
python3 -c "s='Привет'; print(len(s), len(s.encode()))"
```

Expected output — the column is 4-byte capable, and the sample is 6 characters but 12 bytes, which is
why a byte-based limit fails:

```text
name	utf8mb4
6 12
```

Then confirm the script compiles with the helpers in place — `pawncc -i./includes -d3 -ogamemodes/main.amx gamemodes/main.pwn`
prints `utf8 helpers compiled` only when the helpers type-check.

## Sources (2026)

- https://open.mp/docs/tutorials/stringmanipulation
- https://open.mp/docs/scripting/resources/limits
- https://open.mp/docs/scripting/functions/SetPlayerName
