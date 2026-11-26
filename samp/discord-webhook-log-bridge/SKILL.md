---
name: discord-webhook-log-bridge
description: Use when server events must reach Discord reliably.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops, discord, webhook, observability]
    category: samp
---

# Queue server events, drain them into one webhook

Pawn has no HTTP client and the tick must never wait on Discord. The working
shape is a one-way bridge: the gamemode appends one JSON line per event and a
drainer posts batches with `?wait=true`, advancing its offset only after a 2xx.

## When to Use

- Admins learn about a crash, a ban wave or a failed backup hours later.
- You want one channel per severity instead of mixing it into chat.
- Discord rate-limits you because every event opened its own request.
- The webhook URL leaked and you need a path that survives rotation.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | file writes from the main thread only |
| Pawn output | `fopen(..., io_append)` + `fwrite` | one line per event, no HTTP in the gamemode |
| Endpoint | `POST /webhooks/{id}/{token}?wait=true` | `wait=true` returns the message, so 200 proves delivery |
| Payload keys | `content`, `username`, `avatar_url`, `allowed_mentions` | as documented for Execute Webhook |
| Limits | 2000 chars `content`, 10 embeds, 6000 chars per embed set | violating them returns 400 |
| Rate limit | 429 plus `retry_after` (float seconds) | also read `Retry-After` and `X-RateLimit-*` |

## Production Implementation

1. Write the event from Pawn as NDJSON. Escape `"` and `\` yourself, or the
   line is invalid JSON and the drainer drops the whole batch.

```pawn
stock DiscordLog(const tag[], const text[])
{
    new File:f = fopen("discord-queue.ndjson", io_append);
    if (!f) return 0;
    new line[600], safe[420];
    JsonEscape(text, safe, sizeof safe);
    format(line, sizeof line, "{\"tag\":\"%s\",\"text\":\"%s\"}\n", tag, safe);
    fwrite(f, line);
    fclose(f);
    return 1;
}

stock JsonEscape(const src[], dest[], size)
{
    new o = 0;
    for (new i = 0; src[i] != EOS && o < size - 2; i++)
    {
        switch (src[i])
        {
            case '"', '\\': { dest[o++] = '\\'; dest[o++] = src[i]; }
            default: if (src[i] >= 0x20) dest[o++] = src[i];
        }
    }
    dest[o] = EOS;
}
public OnGameModeInit()
{
    DiscordLog("boot", "gamemode loaded");   // account ids, never IPs or emails
    return 1;
}
```

2. Log only what a human must act on: crash, ban with reason, failed backup,
   reload. A per-kill feed is what gets the channel muted.

3. Drain with an offset file and no retry storm. Delivery is at-least-once, so
   a batch can repost after a crash.

```python
import json, os, time, urllib.error, urllib.request

HOOK  = os.environ["DISCORD_WEBHOOK"]
QUEUE = os.environ.get("QUEUE", "/srv/omp/scriptfiles/discord-queue.ndjson")
STATE = os.environ.get("STATE", "/srv/omp/state/discord.offset")

def post(payload):
    req = urllib.request.Request(
        HOOK + "?wait=true", data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "omp-bridge/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(min(float(e.headers.get("Retry-After", 1)), 30))
                continue
            if 500 <= e.code < 600:
                time.sleep(2 ** attempt)
                continue
            raise                     # 400/401/404 never succeed: fail loudly

def main():
    offset = int(open(STATE).read()) if os.path.exists(STATE) else 0
    with open(QUEUE, "rb") as f:
        f.seek(offset)
        chunk = f.read()
    end = chunk.rfind(b"\n") + 1          # consume complete lines only
    if end == 0: return 0
    events = [json.loads(l) for l in chunk[:end].splitlines() if l.strip()][-10:]
    text = "\n".join(f"[{e['tag']}] {e['text']}" for e in events)[:1900]
    if post({"content": text, "username": "omp-bridge",
             "allowed_mentions": {"parse": []}}) in range(200, 300):
        open(STATE, "w").write(str(offset + end))
        return 0
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
```

4. Never let log text ping anyone: `allowed_mentions.parse` set to an empty list
   renders `@everyone` from a player name as plain text.

5. Keep the URL out of the repo. The drainer runs as its own service on a 5 s
   timer, so a Discord outage never reaches the server tick.

```ini
[Service]
EnvironmentFile=/etc/omp-bridge.env
ExecStart=/usr/bin/python3 /opt/omp-bridge/drain.py
User=omp
Nice=10

[Timer]
OnBootSec=30s
OnUnitActiveSec=5s
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `400 Bad Request` from Discord | `content` over 2000 chars or empty body | truncate to 1900, never post empty `content` |
| Events replayed after a restart | offset written before the POST | write the offset only after a 2xx |
| `@everyone` ping from a ban reason | no `allowed_mentions` | send `{"parse": []}` with every payload |
| Drainer spins on a deleted webhook | 404 treated as transient | treat 400/401/404 as fatal, log and exit non-zero |

## Verification

```bash
python3 -m py_compile /opt/omp-bridge/drain.py && echo "drainer compiles"
curl -sS -o /tmp/hook.json -w '%{http_code}\n' -X POST "$DISCORD_WEBHOOK?wait=true" \
  -H 'Content-Type: application/json' \
  -d '{"content":"bridge test","username":"omp-bridge","allowed_mentions":{"parse":[]}}'
python3 -c "import json;print('id' in json.load(open('/tmp/hook.json')))"
```

- `drainer compiles`, then `200`, then `True`: the documented keys are accepted
  and the channel received a message with a real id.
- Append two lines to the queue by hand and run the drainer: one message
  appears, `discord.offset` grows by exactly those bytes, and a second run with
  no new lines posts nothing.

## Sources (2026)

- https://docs.discord.com/developers/resources/webhook
- https://docs.discord.com/developers/resources/message
- https://docs.discord.com/developers/topics/rate-limits
