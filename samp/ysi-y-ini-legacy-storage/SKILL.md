---
name: ysi-y-ini-legacy-storage
description: Use when legacy Y_INI accounts must keep working.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi, storage]
    category: samp
---

# y_ini: keep the file format, replace the storage behind it

## When to Use

- Accounts live in `scriptfiles/users/*.ini` written by Y_INI and other tools still read them.
- You are migrating to SQL but cannot take the server down to convert 20k files.
- A write disappears after a restart, or `INI_Open` returns `INI_NO_FILE`.
- Do not use this for new accounts — start them in SQL and read legacy only during migration.

## Compatibility & Stack Matrix (2026)

| Piece | Value | Note |
| --- | --- | --- |
| Include | `#include <YSI_Storage/y_ini>` (YSI 5.x) | `y_ini` is a Pawn include, not a plugin |
| Write handle | `INI:INI_Open(const filename[])` | returns `INI_NO_FILE` (`INI:-1`) when 4 handles are already open |
| Open handles | `INI_MAX_WRITES` = 4 | the buffer is per handle, so close before opening the next file |
| Flush point | `INI_Close(INI:file)` | nothing reaches disk until close or an explicit flush |
| Section | `INI_SetTag(INI:file, const tag[])` | tags must not contain spaces; a space logs an error and drops the buffer |
| Writers | `INI_WriteString`, `INI_WriteInt`, `INI_WriteFloat`, `INI_WriteBool`, `INI_WriteHex`, `INI_WriteBin` | `INI_WriteFloat` takes `accuracy = 6` |
| Reader | `INI_ParseFile(fname, fmt, bFileFirst, bExtra, extra)` | callback-driven; `INI_Int` / `INI_String` / `INI_Float` / `INI_Bool` live inside it |
| Key read by name | **does not exist** | there is no `INI_ReadString` in YSI 5.x; any code calling it will not compile |

## Production Implementation

1. Write with an explicit tag and a close. The close is the flush, so a crash between the writes and
   the close loses the whole account:

```pawn
#include <open.mp>
#include <YSI_Storage/y_ini>

stock bool:SaveLegacyAccount(playerid, const name[], money, level)
{
    new path[64];
    format(path, sizeof path, "users/%s.ini", name);

    new INI:file = INI_Open(path);
    if (file == INI_NO_FILE)
    {
        printf("[ini] no free write handle for %s (INI_MAX_WRITES reached)", path);
        return false;
    }
    INI_SetTag(file, "Account");            // writes [Account]
    INI_WriteString(file, "Name", name);
    INI_WriteInt(file, "Money", money);
    INI_WriteInt(file, "Level", level);
    INI_WriteFloat(file, "PosX", 0.0, 3);   // accuracy, so the format stays 3 decimals
    INI_Close(file);                        // flush + release the handle
    return true;
}
```

2. Read with `INI_ParseFile`, never with a per-key getter. The format string is a template; `%s` is
   replaced with the tag found in the file, and `bExtra` passes your extra value through:

```pawn
new g_Money[MAX_PLAYERS];
new g_Level[MAX_PLAYERS];
new g_Name[MAX_PLAYERS][MAX_PLAYER_NAME + 1];

stock LoadLegacyAccount(playerid, const name[])
{
    new path[64];
    format(path, sizeof path, "users/%s.ini", name);
    return INI_ParseFile(path, "OnAccountTag_%s", .bExtra = true, .extra = playerid);
}

forward OnAccountTag_Account(playerid, entry[], value[]);
public OnAccountTag_Account(playerid, entry[], value[])
{
    INI_String("Name", g_Name[playerid], MAX_PLAYER_NAME + 1);
    INI_Int("Money", g_Money[playerid]);
    INI_Int("Level", g_Level[playerid]);
    return 1;
}
```

The callback name is `OnAccountTag_` + the tag, so a file containing `[Account]` reaches
`OnAccountTag_Account`. A file with `[Player]` silently reaches nothing — check the tags in a sample
file before writing the callbacks.

3. Migrate in one pass, file by file, with a row per file and a source path, so a failed import can be
   retried without duplicating accounts:

```pawn
stock ImportOne(playerid, const file[], const name[])
{
    if (!INI_ParseFile(file, "OnImportTag_%s", .bExtra = true, .extra = playerid)) return 0;
    return SqlUpsertPlayer(name, g_Money[playerid], g_Level[playerid]);   // keyed by name
}
```

4. Keep the legacy writer alive while any external tool still reads the files, and make SQL the reader.
   Write both for one release, then delete the `.ini` writer once nothing reads it:

```text
release N   : read SQL, write INI + SQL
release N+1 : read SQL, write SQL           (files frozen, kept for rollback)
release N+2 : files archived, INI writer deleted
```

5. Freeze the source files read-only after the import (`chmod 444 users/*.ini`) so a stray tool cannot
   create a second source of truth while you are still able to roll back.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `INI_NO_FILE` on a valid path | 4 handles already open, or `INI_Close` missing on an earlier file | close every handle, one open at a time |
| Section header written with a space | tag passed as `"My Account"` | spaces are rejected; use `My_Account` |
| Values lost after a restart | writes were buffered and the process died before `INI_Close` | close, or save on `OnPlayerDisconnect` and on gmx |
| File grows duplicate keys | two saves appended instead of rewriting | one writer per file; the tag buffer rewrites on close |
| Callback never fires | tag in the file is not the tag in the callback name | list the tags (`grep -h '^\[' users/*.ini | sort -u`) and match them |
| Accented names mangled after import | file written by a CP1251 tool, read as UTF-8 | convert on import, then store UTF-8 in SQL |
| Money off by rounding | `INI_WriteFloat` default accuracy used for money | money as int; floats only for coordinates |

## Verification

```bash
find scriptfiles/users -name '*.ini' | wc -l
mysql -N -B -e "SELECT COUNT(*) FROM samp.players;"
grep -h '^\[' scriptfiles/users/*.ini | sort -u
grep -c '^Money = ' scriptfiles/users/Ferz.ini
```

Expected: the file count and the row count agree, one tag name is reported, and every account file has
exactly one `Money` key:

```text
20114
20114
[Account]
1
```

- Manual: load one account through `INI_ParseFile`, print money and level, then compare with
  `grep -E '^(Money|Level) = ' scriptfiles/users/Ferz.ini` — the numbers must match the log line.

## Sources (2026)

- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Storage/y_ini/api.md — function list for the
  include, including the writer family and the absence of a per-key reader.
- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Storage/y_ini/y_ini_impl.inc — `INI_Open`,
  `INI_Close`, `INI_SetTag`, `INI_ParseFile` signatures, `INI_MAX_WRITES` buffer limits.
