---
name: sql-injection-escape-audit
description: Use when user text reaches a SQL string in Pawn.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security, mysql]
    category: samp
---

# Audit every query for injection, then fix the path that carries user text

In a Pawn gamemode the injection point is always the same shape: a player name, a reason, a
search box or a `/pm` body concatenated into SQL with `format` or with `%s`. The fix is one
call - `mysql_format` with `%e` for text - plus a grep that keeps it that way.

## When to Use

- Any `/command` argument, dialog `inputtext`, or player name is written into a query.
- A security review asks for evidence that no string concatenation reaches the database.
- A name like `O'Brien` breaks a query with a syntax error: that is the same bug, benign sample.
- A `LIKE '%search%'` box lets a player match every row by typing `%`.
- You are migrating from `format` + `mysql_real_escape_string` habits to the R41-4 API.

## Compatibility & Stack Matrix (2026)

| Item | Behaviour | Consequence |
| --- | --- | --- |
| MySQL R41-4 `%s` | inserts the string **raw** | never use it for player text |
| MySQL R41-4 `%e` | escapes via `mysql_escape_string` on the connection charset | the default for text |
| `%d`, `%i`, `%f` | numbers, not strings | pass an int, never a quoted string |
| `mysql_escape_string` | escapes into a buffer with the handle's charset | use when you must pre-escape |
| `mysql_samp` / other forks | `%s` escapes, `%r` is raw | check which plugin the build links |
| Identifiers (table, column, `ORDER BY`) | cannot be escaped | strict allowlist |
| `LIKE` patterns | `%e` escapes quotes, not wildcards | escape `%` and `_` yourself |
| `NO_BACKSLASH_ESCAPES` | changes what escaping means | do not hand-roll escapes |

Escaping is the compatibility path, not the ideal one: bind or escape values, and never let a
value decide the structure of the statement.

## Production Implementation

1. Inventory first. One grep finds every place a query is built, including the ones written
   with `format` years ago:

```bash
grep -rnE "(format|mysql_format|mysql_tquery|mysql_query)\(" gamemodes/ --include='*.pwn' > /tmp/sql_sites.txt
wc -l < /tmp/sql_sites.txt
```

2. Classify each site: literal SQL with no arguments, numeric-only SQL, and SQL carrying text.
   Only the third group can be injected, and it is usually under a dozen sites.

3. Fix text with `%e` on the plugin formatter. The bad line and the good line differ by one
   letter, which is exactly why the grep in Verification exists:

```pawn
// UNSAFE: a name containing a quote rewrites the statement
format(query, sizeof query, "SELECT id FROM accounts WHERE name = '%s'", name);

// SAFE: escaped for this connection's charset before it reaches the string
mysql_format(gDB, query, sizeof query,
    "SELECT id, cash FROM accounts WHERE name = '%e' LIMIT 1", name);
mysql_tquery(gDB, query, "OnAccountLoaded", "i", playerid);
```

4. When the value is already in a buffer and you need it escaped for several statements,
   escape once into a second buffer. Order is source, destination, size, handle:

```pawn
new escaped[MAX_PLAYER_NAME * 2];
mysql_escape_string(name, escaped, sizeof escaped, gDB);
mysql_format(gDB, query, sizeof query, "UPDATE bans SET reason = '%s' WHERE id = %d", escaped, banid);
```

5. Numbers must arrive as numbers. `%d` with a string argument, or a quoted `'%s'` around an
   account id, turns a validation bug into an injection:

```pawn
new accountid = strval(params);              // "12 OR 1=1" -> 12
if (accountid <= 0 || accountid > 999999) return SendClientMessage(playerid, 0xFF4444FF, "Bad id.");
mysql_format(gDB, query, sizeof query, "SELECT name FROM accounts WHERE id = %d", accountid);
```

6. Identifiers cannot be parameterised. A sort column or table name from input must be mapped
   through a fixed list, never inserted:

```pawn
stock bool:OrderClause(const key[], out[], len)
{
    if (!strcmp(key, "cash", true))  return strcat(out, "cash DESC", len) != 0;
    if (!strcmp(key, "score", true)) return strcat(out, "score DESC", len) != 0;
    return false;                             // unknown key: reject, do not default silently
}
```

7. `LIKE` needs its own escaping. `%e` keeps the quote safe but `%` and `_` typed by a player
   still act as wildcards, so a search for `%` matches the whole table:

```pawn
stock EscapeLike(const in[], out[], len)
{
    new j;
    for (new i = 0; in[i] && j < len - 2; i++)
    {
        if (in[i] == '%' || in[i] == '_' || in[i] == '\\') out[j++] = '\\';
        out[j++] = in[i];
    }
    out[j] = '\0';
    return j;
}
```

8. Record the fix as a regression test, not a comment: insert the hostile string through the
   normal path and prove it is stored literally and matches nothing else.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `O'Brien` causes a syntax error | `format`/`%s` used for text | `mysql_format` with `%e` |
| Login bypass with `' OR 1=1 --` | quoted `%s` in a `WHERE` clause | `%e`, plus a row-count check before trusting the result |
| Escaped string still breaks the query | value escaped on a different handle/charset | pass `gDB` to `mysql_escape_string` |
| Double escaping (`\\'` in the table) | `%e` applied to an already escaped value | escape in exactly one place |
| Search box returns every row | `%` and `_` not escaped for `LIKE` | `EscapeLike` before `%e` |
| `ORDER BY` injection | column name taken from input | allowlist mapping, reject unknown |
| Audit passes but a fork still injects | `%s` is safe in `mysql_samp`, raw in R41-4 | pin the plugin, encode the rule per plugin |

## Verification

The audit grep: any `format`/`mysql_format` call whose SQL text contains `%s` is a candidate
and must be justified. Template strings and `%d` hits are fine, `%s` around text is not:

```bash
grep -rnE "(format|mysql_format)\([^;]*\"[^\"]*(SELECT|INSERT|UPDATE|DELETE|REPLACE)[^\"]*%s" \
  gamemodes/ --include='*.pwn'
```

```text
(no output: no SQL string uses a raw %s)
```

Then prove the stored value is data, not syntax. Run the test account through the real code
path and check the row:

```bash
mysql --defaults-file=/etc/samp.cnf -N -e \
  "SELECT COUNT(*) FROM samp.accounts WHERE name = \"' OR 1=1 -- \"" samp
mysql --defaults-file=/etc/samp.cnf -N -e \
  "SELECT COUNT(*) FROM samp.accounts WHERE name = \"O'Brien\"" samp
```

```text
0
1
```

`0` for the injection string means no row outside the literal name, `1` for `O'Brien` means
the apostrophe round-tripped. A `1` on the first query means a name column matched a
condition, and the site is still concatenating.

## Sources (2026)

- https://github.com/pBlueG/SA-MP-MySQL/wiki
- https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- https://dev.mysql.com/doc/refman/8.4/en/string-comparison-functions.html
