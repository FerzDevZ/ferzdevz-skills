---
name: payments-idempotency-webhook
description: Use when payment webhooks double-charge or go missing.
version: "2026.1.0"
metadata:
  hermes:
    tags: [payments, webhooks, idempotency, midtrans, xendit, doku]
    category: web-dev
---

# Make a payment webhook exactly-once, then reconcile what never arrived

Every PSP delivers at least once and none deliver in order, so the handler is not "apply
the status" — it is "record this event once, then move the order forward if the transition
is legal". Anything that only waits for a callback leaves a paying customer in `pending`.

## When to Use

- One payment produces two fulfilments, two invoices or two ledger rows.
- The handler applies whatever `status` the body says without checking the signature.
- An order is paid at the provider but still `pending` in your database hours later.
- You are adding a second PSP and want one state machine instead of two code paths.
- Skip for a single synchronous card capture — but add the event table the day you add VA, QRIS or e-wallet.

## Compatibility & Stack Matrix (2026)

| Provider | Authenticity signal | Notes |
| --- | --- | --- |
| Midtrans | `signature_key` = `SHA512(order_id + status_code + gross_amount + ServerKey)` | Concatenated exactly as received; `gross_amount` is a string like `"10000.00"` |
| Xendit | `x-callback-token` header compared to Dashboard → Webhook settings | Retries up to six times with exponential backoff; no guaranteed event order |
| DOKU (non-SNAP) | `Signature: HMACSHA256=<base64>` over newline-joined `Client-Id`, `Request-Id`, `Request-Timestamp`, `Request-Target`, `Digest` | `Digest` is base64(SHA256(body)); SNAP endpoints sign differently |

Midtrans statuses: `capture`, `settlement`, `pending`, `deny`, `cancel`, `expire`,
`failure`, `refund`, `partial_refund`, `authorize`. Fulfil only on `settlement`, or on
`capture` for a card, and only when `fraud_status` is `accept`; low-risk methods such as
Indomaret omit it.

## Production Implementation

1. Verify first, in constant time, against the raw body: a global `express.json()`
   re-encodes the JSON, DOKU's `Digest` never matches, and that is the usual false alarm.

```ts
app.post('/webhooks/:provider', express.raw({ type: 'application/json', limit: '256kb' }), handler);
app.use(express.json()); // everywhere else

const eq = (a: string, b: string) => {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
};
export const verifyMidtrans = (b: Record<string, string>, key: string) => eq(
  createHash('sha512').update(`${b.order_id}${b.status_code}${b.gross_amount}${key}`).digest('hex'),
  b.signature_key ?? '');

export function verifyDoku(h: Record<string, string | undefined>, rawBody: string, path: string, secret: string) {
  const digest = createHash('sha256').update(rawBody).digest('base64');
  const payload = [`Client-Id:${h['client-id']}`, `Request-Id:${h['request-id']}`,
    `Request-Timestamp:${h['request-timestamp']}`, `Request-Target:${path}`, `Digest:${digest}`].join('\n');
  return eq(createHmac('sha256', secret).update(payload).digest('base64'),
    (h.signature ?? '').replace(/^HMACSHA256=/, ''));
}
```

`Request-Target` is the path of your notification URL (`/webhooks/doku`), not the full
URL, and the component order matters. Xendit is the same compare on its `x-callback-token`.

3. Record the event before doing anything financial — the unique key *is* the dedupe.

```sql
CREATE TABLE payment_event (
  provider text NOT NULL, event_id text NOT NULL,  -- event id, or sha256 of the raw body
  order_id text NOT NULL, payload_hash text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, event_id)
);
```

```ts
const r = await db.query(`INSERT INTO payment_event (provider, event_id, order_id, payload_hash)
  VALUES ($1,$2,$3,$4) ON CONFLICT (provider, event_id) DO NOTHING RETURNING 1`,
  [provider, eventId, orderId, sha256(rawBody)]);
if (r.rowCount === 0) return ack(); // replay: answer 2xx, change nothing
```

Answer `2xx` to replays: a `409` makes the provider retry harder, and that storm is what
takes the endpoint down.

4. Move the order with a conditional update, never read-then-write. The same rule covers
   the outbound charge: one `Idempotency-Key` (V4 UUID) per attempt, stored on the order.

```sql
UPDATE payments SET status = 'paid', paid_at = now()
WHERE order_id = $1 AND status IN ('pending', 'authorized')
RETURNING id;
```

Zero rows means already paid (fine, `2xx`) or an illegal jump such as `expired → paid`
(log and alert, still `2xx`). Keep the table in one module — `pending → {paid, failed,
expired}`, `paid → {refunded, chargeback}` — so a late `settlement` cannot regress a
fulfilled order.

5. Acknowledge fast, reject mismatched amounts, process after. A valid signature proves
   origin, not that the customer paid the right figure, so compare before enqueuing.

```ts
export async function handler(req, res) {
  const rawBody = req.body as Buffer;
  if (!verify(provider, req, rawBody)) return res.status(401).json({ error: 'bad_signature' });
  const event = JSON.parse(rawBody.toString('utf8'));
  if (!(await recordOnce(provider, event, rawBody))) return res.sendStatus(200); // replay
  if (paidMinor(event) !== await getOrderAmountMinor(event.order_id)) {
    await alert('payment_amount_mismatch', { orderId: event.order_id });
    return res.sendStatus(200); // acknowledge, never fulfil
  }
  await queue.publish('payment.event', { provider, payload: event }); // worker transitions
  return res.sendStatus(200);
}
```

6. Reconcile what never arrived: poll orders past their SLA and ask the provider directly
   — Midtrans documents its Get Status API as exactly this failover.

```ts
// jobs/reconcile.ts — every 10 minutes
const stuck = await db.query(`SELECT order_id FROM payments WHERE status = 'pending'
  AND created_at < now() - interval '15 minutes' ORDER BY created_at LIMIT 200`);
const PAID = ['settlement', 'capture'], DEAD = ['expire', 'cancel', 'deny', 'failure'];
for (const { order_id } of stuck.rows) {
  const { transaction_status: s } = await provider.getStatus(order_id);
  if (PAID.includes(s)) await apply(order_id, 'paid', 'reconcile');
  if (DEAD.includes(s)) await apply(order_id, 'failed', 'reconcile');
}
```

Log `source` so a race between reconcile and a webhook is visible, and keep the loop
idempotent. Where a provider sends a timestamp (DOKU `Request-Timestamp`, ISO 8601 UTC),
reject anything outside ±5 minutes; event-id uniqueness is the second line of defence.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every DOKU notification fails signature check | The body was parsed and re-serialised before hashing | Hash the raw buffer; mount `express.raw()` on the webhook path only |
| Midtrans signature fails for one method only | `gross_amount` was normalised (`10000` vs `"10000.00"`) before hashing | Concatenate the exact strings from the payload; never `Number()` them |
| Duplicate delivery creates two fulfilments | Status applied with no unique event record | `payment_event` key on `(provider, event_id)` plus `UPDATE ... WHERE status IN (...)` |
| Order flips back to `pending` after settlement | Out-of-order event applied blindly | Allow-list transitions per current status; drop and log the illegal ones |
| Endpoint times out and the provider keeps retrying | Email, ERP and ledger writes done inside the request | Verify → insert event → enqueue → `2xx`; do the rest in a worker |
| Card payment fulfilled before 3DS resolves | `capture` treated as success without `fraud_status` | Fulfil on `settlement`, or on `capture` with `fraud_status === 'accept'` |

## Verification

- Replay one captured payload twice; the second call must return `200` and insert nothing.

```bash
for i in 1 2; do curl -s -o /dev/null -w '%{http_code}\n' -X POST https://staging.example.com/webhooks/midtrans \
  -H 'content-type: application/json' --data-binary @fixtures/settlement.json; done
psql "$DATABASE_URL" -tAc "select count(*) from payment_event where event_id='fixture-settlement'"
```

Expected: two `200` lines, then `1`. Flip one byte of `gross_amount`: the same `curl`
returns `401` and the count does not change. Orders stuck `pending` for over an hour must
return `0` after the reconcile job runs twice.

## Sources (2026)

- https://docs.midtrans.com/docs/https-notification-webhooks
- https://docs.xendit.co/docs/handling-webhooks
- https://developers.doku.com/get-started-with-doku-api/notification/best-practice
- https://docs.stripe.com/api/idempotent_requests
