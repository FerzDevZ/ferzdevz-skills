---
name: economy-inflation-analytics
description: Measure economy health from the ledger.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, economy]
    category: samp
---

# inflation analytics

## When to Use
- Prices drift and new players cannot progress.
- No data on money supply.

## 2026 Compatibility & Architecture Matrix
- The ledger is the source of truth for flows.
- Separate faucets (income) from sinks (purchases).

## Production Implementation
1. Aggregate daily income per source and spend per sink.
2. Alert when the faucet/sink ratio exceeds a threshold.
3. Adjust rates from data.

```sql
SELECT reason, SUM(delta) FROM ledger WHERE ts > NOW() - INTERVAL 1 DAY GROUP BY reason;
```

## Deprecated Traps & Edge Cases (2026)
- Measuring only balances, not flows.
- A faucet with no sink.

## Verification
- The daily report lists faucets/sinks and the ratio; a price change is traceable to data.
