---
name: warehouse-modeling-dbt
description: Use when a dbt model must scale without full refreshes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [dbt, warehouse, star-schema, incremental, data-tests]
    category: ops
---

# Declare the grain before you write the join

Every modeling bug in a warehouse is either a grain bug (one row means two things)
or a cost bug (rebuilding history to add one day). Both are decided in the first
ten lines of the model.

## When to Use

- A dashboard number disagrees with finance and nobody can say what one row of the mart is.
- Every model is materialized as `table`, so `dbt run` gets slower each week.
- A late-arriving event never lands: the partition was written before the event arrived.
- Skip this when the warehouse holds a few million rows and a full rebuild takes under two minutes.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| dbt Core | v1.x (1.10+ for `arguments:` in tests) | `dbt build`, `dbt test`, `dbt ls` |
| dbt platform | v1 tracks (Latest/Compatible) and v2 | v2 requires `arguments:` on generic tests |
| Adapters | postgres, redshift, bigquery, snowflake, databricks, spark | strategy support differs per adapter |
| Incremental strategies | `append`, `merge`, `delete+insert`, `insert_overwrite`, `microbatch` | `insert_overwrite` and `microbatch` do not use `unique_key` |
| `dbt_utils` | 1.x package | `generate_surrogate_key` |

## Production Implementation

1. Write the grain as one sentence above the `select`, then encode it as a test.
   "One row per order line per day" is a contract; `select *` is not.

```sql
-- grain: one row per order_id + line_item_id
{{ config(materialized='incremental', unique_key='order_line_key') }}

select
    {{ dbt_utils.generate_surrogate_key(['order_id', 'line_item_id']) }} as order_line_key,
    order_id,
    line_item_id,
    ordered_at,
    net_revenue
from {{ ref('stg_orders__lines') }}
{% if is_incremental() %}
where ordered_at >= (select coalesce(max(ordered_at), '1900-01-01') from {{ this }})
  and ordered_at >= dateadd('day', -3, current_timestamp)  -- late-arrival lookback
{% endif %}
```

2. Pick star or wide table by query shape, not taste: a conformed star wins when
   several marts reuse the same dims; a wide table when one consumer wants one grain.

| Situation | Model shape | Reason |
| --- | --- | --- |
| 4+ dashboards join the same customer/date/product dims | star schema, conformed dims | join logic written and tested once |
| One consumer, 8 columns, aggregation only | wide table | avoids joins the warehouse then re-optimizes |
| Facts at different grains (order vs line item) | separate facts | never join two grains then aggregate |

3. Generate the surrogate key, never trust a natural key. Composite business keys
   change format, and nulls in a `unique_key` make dbt fail to match rows and
   insert duplicates. `generate_surrogate_key` hashes a non-null tuple.

4. Set `unique_key` and the strategy together in the config block: without a key
   dbt falls back to `append` even when you asked for `merge`, so every run adds a
   second copy of the same day. `delete+insert` plus
   `on_schema_change='append_new_columns'` is the cheap default for facts.

5. Know what `is_incremental()` returns: true only when the target exists as a
   table, `--full-refresh` is absent, and the model is `materialized='incremental'`.
   The SQL must work in both branches, so never reference the target outside the guard.

6. Handle late data with either a lookback window (step 1) or `microbatch` (dbt
   1.9+), which reprocesses whole time batches and can retry them independently.

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='microbatch',
    unique_key='sale_id',
    event_time='transaction_date',
    begin='2023-01-01',
    batch_size='day',
    full_refresh=false
) }}
```

7. Backfill deliberately; `--full-refresh` alone does not reload a microbatch
   model without a `begin` value, so bind the window instead:

```bash
dbt run --full-refresh --event-time-start "2024-01-01" --event-time-end "2024-02-01" --select fct_sales
```

8. Decide the schema-change policy once. `ignore` (the default) silently drops a
   new column from the target and fails when a column is removed; `fail` is the
   honest choice for a fact table. No policy backfills old rows.

9. Test the grain and the relationships, not the row count.

```yaml
models:
  - name: fct_orders
    columns:
      - name: order_line_key
        data_tests: [unique, not_null]
      - name: customer_id
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_customers')
                field: customer_id
      - name: status
        data_tests:
          - accepted_values:
              arguments: {values: [placed, shipped, completed, returned]}
```

10. Keep the layout boring so `dbt ls` selectors stay predictable, and set the
    default materialization per folder instead of per file.

```text
models/
  staging/       stg_<source>__<table>.sql   1:1 with sources, view
  intermediate/  int_<entity>_<verb>.sql     ephemeral or view
  marts/         fct_*.sql, dim_*.sql        table or incremental
```

```yaml
name: analytics
config-version: 2
profile: analytics
model-paths: ["models"]

models:
  analytics:
    staging:
      +materialized: view
    marts:
      +materialized: table
      +on_schema_change: "fail"
```

11. Price the choice per model: a full refresh scans all history and rewrites the
    table, an incremental run scans the lookback window. Measure both — the gap is
    linear in table size, so it grows silently.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `unique` test fails on the fact key after a join | dimension has multiple rows per key, fan-out duplicated the fact | dedupe the dim to its grain first, then join |
| Same day appears twice in the mart | no `unique_key`, so the adapter appended | add `unique_key` as a list of non-null columns |
| Yesterday's rows never arrive | filter set to `> max(ts)` with no lookback | widen the window or use `microbatch` with `lookback` |
| New column absent from the table after `dbt run` | `on_schema_change: ignore` is the default | `append_new_columns` or `sync_all_columns`, then full-refresh for history |
| `dbt build` skips half the DAG | a failed test on an upstream model skips its children | fix or downgrade that test's `severity`, never mute the whole selector |

## Verification

- `dbt build --select +fct_orders` ends with `Completed successfully` and
  `Done. PASS=n WARN=0 ERROR=0 SKIP=0 TOTAL=n`; any `SKIP` means an upstream test failed.
- `dbt test --select fct_orders` lists `unique_fct_orders_order_line_key` and
  `relationships_fct_orders_customer_id__customer_id__ref_dim_customers_` as `PASS`.
- `dbt ls -s config.materialized:incremental --resource-type model` returns only
  the facts you intended to make incremental, not the staging folder.
- Run `dbt run --select fct_orders` twice; the second run leaves the row count
  unchanged and `select max(ordered_at) from fct_orders` never moves backwards.
- `dbt test --select test_type:data` runs data tests only, excluding unit tests.

## Sources (2026)

- https://docs.getdbt.com/docs/build/incremental-models
- https://docs.getdbt.com/docs/build/data-tests
- https://docs.getdbt.com/docs/build/incremental-strategy
