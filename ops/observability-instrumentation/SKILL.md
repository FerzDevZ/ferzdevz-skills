---
name: observability-instrumentation
description: Use when alerts fire late or traces break at a hop.
version: "2026.1.0"
metadata:
  hermes:
    tags: [observability, opentelemetry, tracing, slo, sampling]
    category: ops
---

# Instrument one request path so metrics, traces and logs name the same failure

Three signals that disagree are worse than one weak signal: the dashboard says
CPU is fine, the trace stops at the queue, and the log line has no request id.
Instrument the path once, and let every signal carry the same identifiers.

## When to Use

- Alerts fire on CPU or memory while users see 500s and slow pages.
- A trace ends at an async hop: queue consumer, cron job, or a second service.
- Log search is guesswork because lines carry no request or trace id.
- Sampling is on, and every incident trace turns out to be one of the dropped ones.
- Dashboards for two services use different metric names for the same concept.
- Skip this for a single-process script with no caller and no SLO.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| OpenTelemetry API/SDK | 1.x | traces and metrics stable; semconv mixed |
| W3C Trace Context | Level 1 Recommendation | `traceparent` + `tracestate` headers |
| OTel Collector (contrib) | 0.x | `probabilisticsampler`, `tailsampling` processors |
| HTTP semconv | `http.server.request.duration` | histogram, unit `s`, explicit buckets |
| Metrics backend | Prometheus 3.x or OTLP-native | dotted names become `_seconds` suffixes |

## Production Implementation

1. Name the signals before installing an SDK: RED for request paths (rate,
   errors, duration), USE for resources (utilization, saturation, errors). Every
   dashboard row maps to one user journey, and nothing pages on a cause metric.

2. Emit RED from the semconv HTTP histogram, not a hand-rolled counter: renaming
   it breaks every dashboard recipe and the default buckets.

```yaml
receivers:
  otlp:
    protocols: { grpc: {}, http: {} }
processors:
  batch: {}
exporters:
  otlphttp:
    endpoint: http://otel-collector.observability:4318
service:
  pipelines:
    traces:  { receivers: [otlp], processors: [batch], exporters: [otlphttp] }
    metrics: { receivers: [otlp], processors: [batch], exporters: [otlphttp] }
```

3. Propagate context with `traceparent`, never a bespoke request id header. The
   value is `version-trace-id-parent-id-flags`, all lowercase hex.

```text
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             version(2) trace-id(32) parent-id(16) flags(2): lowercase hex, ff is invalid
```
```ts
// Node: extract at the server boundary, inject on every outbound call.
import { propagation, context, trace } from "@opentelemetry/api";

const parent = propagation.extract(context.active(), req.headers);
const span = tracer.startSpan("handle_request", undefined, parent);
await context.with(trace.setSpan(parent, span), () => handler(req));
```

   Strip an inbound `traceparent` at the public edge and start a new trace there,
   or a client can forge internal traces. Inside the mesh every hop must extract
   and continue — a new trace id per hop is the bug.

4. Put the span identifiers in the log line, not just in the trace backend.

```python
import json, time
from opentelemetry import trace

def emit(level: str, msg: str, **fields):
    ctx = trace.get_current_span().get_span_context()
    rec = {
        "ts": time.time(), "level": level, "msg": msg,
        "trace_id": format(ctx.trace_id, "032x") if ctx.is_valid else None,
        "span_id": format(ctx.span_id, "016x") if ctx.is_valid else None,
        "service": "checkout-api",
    }
    rec.update(fields)
    print(json.dumps(rec, separators=(",", ":")), flush=True)
```

   Then one query returns the story: metric → exemplar trace id → trace → logs.

5. Sample twice: cheap head sampling to cut volume, tail sampling to keep the
   traces that matter. Head-only sampling at 1% is why incidents are invisible.

```bash
export OTEL_SERVICE_NAME=checkout-api
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod,service.version=2026.4.1
export OTEL_TRACES_SAMPLER=parentbased_traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.1
export OTEL_TRACES_EXPORTER=otlp
```
```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow
        type: latency
        latency: { threshold_ms: 750 }
      - name: baseline
        type: probabilistic
        probabilistic: { sampling_percentage: 5 }
```

   Tail sampling only sees complete traces, so route one trace to one collector
   (load-balance on `trace_id`, not round-robin).

6. Tie alerts to the SLO, not a guessed threshold. At 99.9% availability the
   budget is 0.1%: page at 14.4x burn over 1h, ticket at 6x over 6h. Both
   windows must fire, which kills single-spike pages.

```promql
(
  sum(rate(http_server_request_duration_seconds_count{job="checkout",http_response_status_code=~"5.."}[1h]))
  / sum(rate(http_server_request_duration_seconds_count{job="checkout"}[1h]))
) / 0.001 > 14.4
```

7. Make cardinality a review rule: no user id, email, raw path or error message
   in a metric label. Those go on the span, priced per trace not per series.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| No traces for any incident | head sampler at 1%, errors dropped before the collector | keep head at parentbased ratio, keep errors with tail sampling |
| One request shows five root spans | each hop starts a span without extracting `traceparent` | extract at the boundary, log the inbound trace id when it is absent |
| Alert fires, users are fine | paging on CPU or queue depth | page on SLO burn rate for error ratio and latency |
| Prometheus memory explodes | raw path or user id as a label | label with `http.route`; put identifiers on spans and logs |
| Latency p99 looks 1000x too high | milliseconds written into a seconds histogram | use the semconv unit `s`, buckets 0.005 to 10 |
| Logs cannot be joined to traces | logging from a different context than the active span | emit `trace_id`/`span_id` from the current span at log time |

## Verification

- `python3 -c "import yaml; yaml.safe_load(open('otel-collector.yaml'))"` exits 0
  with no output; a YAML error prints the offending line.
- `curl -s localhost:8888/metrics | grep -c '^http_server_request_duration_seconds_bucket'`
  returns a positive count — one line per explicit bucket plus `+Inf`.
- `curl -s -o /dev/null -D - http://localhost:8080/healthz | grep -i '^traceparent'`
  prints a header matching `^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$`.
- `jq -r 'select(.trace_id != null) | .trace_id' app.log | sort -u | wc -l`
  returns more than 0, proving logs carry span context.

## Sources (2026)

- https://opentelemetry.io/docs/concepts/signals/traces/
- https://opentelemetry.io/docs/concepts/sampling/
- https://www.w3.org/TR/trace-context/
