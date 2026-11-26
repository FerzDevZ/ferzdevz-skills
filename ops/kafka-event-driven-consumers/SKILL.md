---
name: kafka-event-driven-consumers
description: Use when Kafka consumers duplicate, stall or lag.
version: "2026.1.0"
metadata:
  hermes:
    tags: [kafka, consumers, exactly-once, dlq, lag]
    category: ops
---

# Make the consumer idempotent before you make it fast

Kafka gives you ordering per partition and at-least-once delivery by default.
Everything else — no duplicates, no stuck partitions, no silent lag — is your
consumer's job. Fix the offset contract first, then the throughput.

## When to Use

- Order rows appear twice after a deploy, a broker bounce or a rebalance.
- Lag climbs in `kafka-consumer-groups.sh --describe` while consumer CPU is flat.
- The group logs `Rebalance in progress` in a loop and no records move.
- One malformed record blocks a partition forever and every retry burns the same event.
- A design doc claims "exactly-once" but the downstream is a payment or email API.
- Skip this for a nightly batch export that reads a topic once and exits.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| Apache Kafka broker | 4.2.x (supported release) | 4.0 removed ZooKeeper; KRaft only |
| Legacy broker | 3.9.x | ZooKeeper mode still valid for staged upgrades |
| Java client | `org.apache.kafka:kafka-clients` 4.2.x | configs below apply to 3.7+ |
| Spring Kafka | 3.x | `ErrorHandlingDeserializer`, `DefaultErrorHandler` |
| Python client | `confluent-kafka` 2.x | librdkafka drives rebalance callbacks |
| CLI | `kafka-consumer-groups.sh` | ships with the broker distribution |

## Production Implementation

1. Pin the offset contract. Auto-commit hides failures, and `read_uncommitted`
   makes an "exactly-once" pipeline read aborted records.

```java
Properties p = new Properties();
p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "broker-1:9092,broker-2:9092");
p.put(ConsumerConfig.GROUP_ID_CONFIG, "orders-projector");
p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
p.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
p.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, "100");
p.put(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, "300000");
p.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, "45000");
p.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, "3000");
p.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
       "org.apache.kafka.clients.consumer.CooperativeStickyAssignor");
```

   `max.poll.interval.ms` must exceed your worst-case batch, not your average.
   Keep `heartbeat.interval.ms` near one third of `session.timeout.ms`.

2. Record consumption in the same transaction as the business write. The offset
   is the natural idempotency key for a replay; `event_id` covers producer retries.

```sql
CREATE TABLE consumed_event (
  consumer_group text  NOT NULL,
  topic          text  NOT NULL,
  partition      int   NOT NULL,
  offset         bigint NOT NULL,
  event_id       uuid  NOT NULL,
  processed_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (consumer_group, topic, partition, offset)
);
```

```java
@Transactional
public void handle(ConsumerRecord<String, OrderEvent> r) {
    int inserted = jdbc.update("""
        INSERT INTO consumed_event (consumer_group, topic, partition, offset, event_id)
        VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING""",
        GROUP, r.topic(), r.partition(), r.offset(), r.value().eventId());
    if (inserted == 0) return;      // replay: already applied, commit and move on
    ledger.apply(r.value());        // business write, same transaction
}
```

   Commit offsets only after this transaction returns. That is at-least-once
   delivery with effectively-once effects, and it survives a crash anywhere.

3. Commit a safe point on revoke instead of losing in-flight work.

```java
consumer.subscribe(List.of("orders.v1"), new ConsumerRebalanceListener() {
    @Override public void onPartitionsRevoked(Collection<TopicPartition> parts) {
        drainInFlight();                          // finish or hand back
        consumer.commitSync(currentOffsets());    // last durable point
    }
    @Override public void onPartitionsAssigned(Collection<TopicPartition> parts) {
        log.info("assigned {} partition(s)", parts.size());
    }
});
```

   `CooperativeStickyAssignor` moves single partitions instead of stopping the
   whole group, so a 40-partition topic does not reprocess 40 partitions per deploy.

4. Quarantine poison messages after a bounded number of attempts, and commit past
   them. A retry loop on a permanently bad record is a stalled partition.

```java
DefaultErrorHandler handler = new DefaultErrorHandler(
    new DeadLetterPublishingRecoverer(kafkaTemplate,
        (rec, ex) -> new TopicPartition("orders.v1.dlq", rec.partition())),
    new FixedBackOff(2_000L, 3L));         // 3 attempts, 2s apart
handler.addNotRetryableExceptions(JsonParseException.class);
```

   Deserialization failures never reach the listener, so wrap the value
   deserializer in `ErrorHandlingDeserializer` or those records stall forever.

5. Use transactions only where they actually apply: Kafka in, Kafka out.

```java
producer.initTransactions();
producer.beginTransaction();
producer.send(new ProducerRecord<>("orders.enriched", key, enriched));
producer.sendOffsetsToTransaction(consumerOffsets, consumer.groupMetadata());
producer.commitTransaction();
```

   This is atomic across the output topic and the offset, nothing more. A call to
   Stripe inside the same block is not transactional; give it an idempotency key.

6. Alert on time lag, not record count. `records-lag-max` (JMX,
   `consumer-fetch-manager-metrics`) tells you depth; `records-consumed-rate`
   turns depth into "minutes behind". Page when catch-up time exceeds 15 minutes
   for 10 minutes, not when lag crosses a fixed number that traffic inflates.

7. Verify against a real group before calling it done.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Duplicates after a pod restart | side effect committed, offset commit lost | dedupe on `(group, topic, partition, offset)` inside the same transaction |
| Group stuck in `Rebalance in progress` | handler runtime exceeds `max.poll.interval.ms` | lower `max.poll.records` or move slow work to an internal queue |
| Lag grows, consumer CPU near zero | one poison record retried forever | bounded retries + DLQ, then commit past the offset |
| "Exactly-once" still duplicates | consumer left on `read_uncommitted` | set `isolation.level=read_committed` on every consumer |
| DLQ reprocessed endlessly | DLQ topic subscribed by the same group | give the DLQ no consumer group; replay by hand |
| Rebalance storm every deploy | `session.timeout.ms` shorter than a GC pause | raise session timeout; set heartbeat to one third of it |
| Keyed events out of order after scaling | partition count raised mid-stream | rekey or pin partition count at topic creation |

## Verification

- `kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group orders-projector`
  prints a row per partition with `LAG`; when caught up every `LAG` is `0`.
- `kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list` shows the
  group exactly once (a second entry means a typo'd `group.id`).
- `kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic orders.v1`
  shows `ReplicationFactor: 3` and `min.insync.replicas=2`.
- Replay test: `kill -9` the pod mid-batch, restart, then
  `SELECT count(*) FROM consumed_event;` must equal the producer's event count.

## Sources (2026)

- https://kafka.apache.org/42/configuration/consumer-configs/
- https://kafka.apache.org/42/operations/monitoring/
- https://kafka.apache.org/documentation/
