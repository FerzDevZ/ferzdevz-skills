---
name: mobile-offline-sync-queue
description: Use when offline edits must sync without duplicates.
version: "2026.1.0"
metadata:
  hermes:
    tags: [offline-first, sync, outbox, idempotency, sqlite, workmanager]
    category: mobile-dev
---

# Sync with an outbox and idempotency keys, not retries

The failure that matters is not "the request failed"; it is "the request
succeeded and we sent it again". The fix is structural: the local database is the
source of truth, every write becomes an immutable outbox row with a client key,
and the server arbitrates order.

## When to Use

- Users create or edit records on a flaky connection and nothing may be lost.
- A retried POST has already produced duplicates in production.
- You need "2 changes waiting to sync" instead of a silent spinner.
- Multiple devices or a web client can edit the same row.
- Skip this for read-only apps or ephemeral state; a cache is enough there.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Local store | SQLite 3.8+ (Room, SQLDelight, Drift) | partial unique index is required for the dedupe rule |
| Android scheduling | WorkManager `OneTimeWorkRequest` with backoff | survives process death and reboot |
| Transport | HTTP with an `Idempotency-Key` header | server persists the key with the result |
| Clock | server-issued version or HLC | never trust device time for conflict order |

## Production Implementation

1. Model the outbox as an append-only log: one row per intent, never per field.

```sql
CREATE TABLE outbox (
  id              TEXT PRIMARY KEY,          -- UUIDv7, reused as Idempotency-Key
  entity_id       TEXT NOT NULL,
  op              TEXT NOT NULL CHECK (op IN ('create','update','delete')),
  payload         TEXT NOT NULL,             -- JSON patch, never the whole row
  base_version    INTEGER NOT NULL,          -- server version the edit was based on
  attempts        INTEGER NOT NULL DEFAULT 0,
  next_attempt_at INTEGER NOT NULL,          -- epoch ms
  lease_until     INTEGER,                   -- epoch ms, crash recovery
  state           TEXT NOT NULL DEFAULT 'pending'
                  CHECK (state IN ('pending','inflight','dead'))
);
CREATE UNIQUE INDEX outbox_one_pending ON outbox(entity_id, op) WHERE state = 'pending';
CREATE INDEX outbox_due ON outbox(state, next_attempt_at);
```

2. Write the local row and the outbox row in one transaction, or the UI shows a
   change the server will never hear about.

```kotlin
suspend fun addLine(invoiceId: String, sku: String, qty: Int) = db.withTransaction {
  val lineId = newId()
  lineDao.insert(Line(lineId, invoiceId, sku, qty))
  outboxDao.insert(OutboxRow(
    id = uuidV7(),                       // generated ONCE, reused on every retry
    entityId = lineId, op = "create",
    payload = """{"sku":"$sku","qty":$qty}""",
    baseVersion = invoiceDao.version(invoiceId), nextAttemptAt = now(),
  ))
}
```

3. Claim work with a lease, not a flag. A process killed mid-request must not
   strand rows in `inflight`; sweep expired leases before the first claim.

```kotlin
@Transaction
suspend fun claim(now: Long, batch: Int): List<OutboxRow> {
  val due = dao.selectDue(now, batch)                  // pending AND due
  dao.markInflight(due.map { it.id }, leaseUntil = now + 30_000)
  return due
}
suspend fun recover(now: Long) = dao.releaseExpired(now)  // inflight AND lease<now
```

4. Send the row id as the idempotency key and classify the response: only
   transient failures may be retried, and 4xx outside 408/409/429 is permanent.

```kotlin
sealed interface Outcome {
  data class Ok(val version: Int) : Outcome
  data class Conflict(val serverVersion: Int, val body: String) : Outcome
  data object Retry : Outcome
  data class Fatal(val code: Int, val body: String) : Outcome
}

fun classify(code: Int, version: Int?, body: String): Outcome = when {
  code in 200..299 -> Outcome.Ok(version ?: 0)
  code == 409 -> Outcome.Conflict(version ?: 0, body)
  code == 408 || code == 429 || code >= 500 -> Outcome.Retry
  else -> Outcome.Fatal(code, body)
}
```

5. Back off exponentially with jitter, capped. Without jitter, every device that
   lost signal in the same tunnel retries in lockstep.

```kotlin
fun nextDelayMs(attempts: Int, rnd: Double): Long {
  val capped = (1_000L shl attempts.coerceAtMost(10)).coerceAtMost(15 * 60_000L)
  return (capped * (0.5 + rnd * 0.5)).toLong()   // 50-100% of the cap
}
```

6. Resolve conflicts with a three-way rule: the server returns 409 plus its body,
   and only the fields the user patched may win.

```kotlin
suspend fun resolve(row: OutboxRow, c: Outcome.Conflict) {
  val mine = json.decodeFromString<Map<String, JsonElement>>(row.payload)
  val theirs = json.decodeFromString<Map<String, JsonElement>>(c.body)
  outboxDao.replace(row.copy(payload = json.encodeToString(theirs + mine),
    baseVersion = c.serverVersion, attempts = 0, state = "pending"))
  uiState.emit(SyncStatus.Conflict(row.entityId))  // Synced | Pending(n) | Failed(n, why)
}
```

7. Drain from a scheduler that survives the process, and derive the badge from
   queue depth so the UI can say `Pending(2)` instead of spinning.

```kotlin
val request = OneTimeWorkRequestBuilder<SyncWorker>()
  .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
  .build()
WorkManager.getInstance(ctx).enqueueUniqueWork("outbox", ExistingWorkPolicy.KEEP, request)
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Duplicate record after a timeout retry | new key generated per attempt | generate the id once when the row is created and send it as `Idempotency-Key` on every retry |
| Rows stuck in `inflight` after a kill | boolean-style claim with no expiry | `lease_until` plus a recovery sweep on start, before any claim |
| Server 500s drain the battery | fixed short retry with no cap | exponential backoff with jitter capped at 15 minutes, scheduled by WorkManager |
| Offline edit silently disappears | last-write-wins overwrote it | send `base_version`, treat 409 as a merge, surface the conflict when fields disagree |
| Same bad payload retried forever | every failure treated as transient | map 4xx to `dead` except 408/409/429 and keep the error text for the UI |

## Verification

```bash
adb exec-out run-as com.example.app cat databases/app.db > /tmp/app.db
sqlite3 /tmp/app.db "SELECT state, COUNT(*) FROM outbox GROUP BY state;"
sqlite3 /tmp/app.db "SELECT entity_id, op FROM outbox WHERE state='pending' GROUP BY 1,2 HAVING COUNT(*)>1;"
```

- After a drain with the network up, `GROUP BY state` returns no `pending` or
  `inflight` rows for happy-path data.
- The duplicate query returns zero rows: that is the local half of the guarantee,
  the `Idempotency-Key` header is the remote half.
- Kill the app mid-sync (`adb shell am force-stop com.example.app`), reopen it,
  and confirm the sweep moved `inflight` back to `pending` instead of stranding it.
- Replay one outbox row twice against staging and confirm the server returns the
  original record, and that one writer connection in WAL mode keeps `SQLITE_BUSY`
  out of the drain path.

## Sources (2026)

- https://developer.android.com/topic/architecture/data-layer/offline-first
- https://developer.android.com/develop/background-work/background-tasks/persistent
- https://developer.android.com/training/data-storage/room
