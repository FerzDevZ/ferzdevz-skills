---
name: server-log-anomaly-scanner
description: Use when server logs need a daily anomaly scan.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# Server log anomaly scan

`log.txt` is the only telemetry an open.mp server gives you for free, and it is noisy by
design: every timeout, every ack overrun, every `[Info]` line lands in the same file. The
job is not reading it — it is bucketing signatures per hour and reporting only what changed.

## When to Use

- You want a daily five-line summary instead of 200k lines of `[Info]`.
- A signature appeared that was not in yesterday's baseline.
- Players report "the server lagged at 21:00" and you need the matching window.

## Compatibility & Stack Matrix (2026)

| Source | File | Line shape | Hour bucket |
| --- | --- | --- | --- |
| open.mp 1.6.x | `logging.file`, default `log.txt` | `[2026-11-26T10:02:11+0000] [Warning] ...` | `substr($0,2,13)` |
| open.mp, prefix off | `log.txt` | timestamp only, no `[Info]` tag | same |
| SA-MP 0.3.7-R2 | `server_log.txt` | `[10:02:11] ...` | no date, use file mtime |

Both defaults come from `config.json`: `logging.file` is `log.txt` and
`logging.timestamp_format` is `[%Y-%m-%dT%H:%M:%S%z]`. If the operator changed the format,
the scanner mis-buckets silently — print one line before trusting the output.

## Production Implementation

1. Read the log path from the live config instead of assuming it:

```bash
python3 -c "import json;print(json.load(open('config.json'))['logging']['file'])"
```

```text
log.txt
```

2. Write the signature table once, as a file the cron job and the operator both run.
   Specific patterns come first: a `messageholelimit` line also contains `out-of-order`
   text in some builds, and the first matching branch wins:

```bash
cat > scan.awk <<'AWK'
{
  line = $0
  ts = ""
  if (substr(line, 1, 1) == "[") ts = substr(line, 2, 13)
  if (line ~ /client exceeded .messageslimit/)   sig = "ratelimit-messages"
  else if (line ~ /client exceeded .ackslimit/)  sig = "ratelimit-acks"
  else if (line ~ /exceeded .messageholelimit/)  sig = "ratelimit-hole"
  else if (line ~ /out-of-order messages/)       sig = "out-of-order"
  else if (line ~ /Packet was modified/)         sig = "packet-modified"
  else if (line ~ /Run time error/)              sig = "amx-error"
  else if (line ~ /Failed to load|Failed to init/) sig = "load-failure"
  else next
  if (ts == "") ts = "no-timestamp"
  count[ts, sig]++
}
END { for (k in count) { split(k, p, SUBSEP); printf "%s %-20s %d\n", p[1], p[2], count[k] } }
AWK

awk -f scan.awk log.txt | sort > today.txt
```

3. Keep the first run as the baseline and diff the signature column each day:

```bash
cut -d' ' -f2 today.txt | sort -u > today.sig
comm -13 baseline.sig today.sig
```

Empty output is the healthy answer. A new signature is the alert; a signature that tripled
its count is the second alert.

4. Whitelist what is known benign, in a file next to the scanner, not inside the awk:

```bash
printf '%s\n' packet-modified >> benign.sig
comm -13 baseline.sig <(comm -23 today.sig benign.sig)
```

5. Run it on a timer, outside the game thread, before log rotation. Cron uses `sh`, so no
   process substitution — write the signature set to a file first:

```bash
0 6 * * * cd /srv/omp && awk -f scan.awk log.txt | sort > today.txt && cut -d' ' -f2 today.txt | sort -u > today.sig && comm -13 baseline.sig today.sig && cp today.sig baseline.sig
```

6. Alert on the delta, never on a raw count. `packet-modified` fires for every player who
   times out; ten of them at 03:00 is a residential ISP, ten of them at prime time is not.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| One bucket absorbs the whole day | log format without a date (0.3.7 `server_log.txt`) | bucket by file mtime, or migrate to `log.txt` |
| `out-of-order` never reported | earlier `messageholelimit` branch swallowed the line | put specific patterns above general ones |
| Daily alert storm | alerting on every timeout or `packet-modified` | alert on new signature or a 3x rise |
| Scanner sees nothing | rotation ran first, `log.txt` is fresh | scan the rotated file or run before `logrotate` |
| All lines land in `no-timestamp` | `logging.timestamp_format` changed | read the format from config and adjust `substr` |
| `Run time error` counted as a crash | it is a script error, not a process death | pair with `crashinfo.txt` before paging anyone |
| Ad-hoc greps disagree with the report | signature list drifted between scripts | one awk, one signature table, versioned |

## Verification

Run the scanner against a fixture with one injected line of each class:

```bash
awk -f scan.awk log.txt | sort
```

```text
2026-11-26T10 amx-error            1
2026-11-26T10 out-of-order         1
2026-11-26T10 packet-modified      2
2026-11-26T10 ratelimit-acks       1
2026-11-26T10 ratelimit-messages   2
```

Then prove the alert path, not just the parser — append one `[Error]` line and re-run:

```bash
echo '[2026-11-26T11:00:00+0000] [Error] Run time error 19: "File or function not found"' >> log.txt
awk -f scan.awk log.txt | sort | tail -1
```

```text
2026-11-26T11 amx-error            1
```

A new hour bucket with a count of 1 is exactly what the daily diff is supposed to surface.

## Sources (2026)

- https://open.mp/docs/server/CommonServerIssues
- https://open.mp/docs/server/config.json
- https://open.mp/docs/changelog
