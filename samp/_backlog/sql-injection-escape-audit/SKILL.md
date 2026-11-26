---
name: sql-injection-escape-audit
description: Remove SQL injection paths from a gamemode.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security]
    category: samp
---

# SQL injection audit

## When to Use
- User input reaches a query string.
- A security review asks for proof.

## 2026 Compatibility & Architecture Matrix
- Prepared statements or `mysql_format` with typed placeholders are the baseline.
- Names and reasons are the common injection vectors.

## Production Implementation
1. Search every query construction and classify string vs formatted.
2. Replace `%s` from user input with validated values or bound parameters.
3. Add a test with quotes and semicolons in a name.

```pawn
// bad:  "... WHERE name = '%s'", name
mysql_format(g_DB, q, sizeof q, "SELECT id FROM accounts WHERE name = '%e'", name);
```

## Deprecated Traps & Edge Cases (2026)
- `%e` escapes but does not replace bound parameters for every case.
- Validating only length and not characters.

## Verification
- A name containing `' OR 1=1 --` stores literally and matches nothing.
- Grep shows no raw `%s` inside SQL strings.
