---
name: k8s-omp-fleet
description: Run several open.mp instances under Kubernetes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, ops, kubernetes, deploy]
    category: samp
---

# open.mp fleet on Kubernetes

## When to Use

- More than one server instance, or a need for rolling updates without downtime.
- Moving from a single systemd unit to containers.

## 2026 Compatibility & Architecture Matrix

| Concern | Kubernetes answer | open.mp detail |
| --- | --- | --- |
| Game port | `Service` type LoadBalancer, `protocol: UDP` | one port per instance |
| Health | query the server port, not HTTP | no HTTP endpoint exists |
| Config | ConfigMap + env overrides | env vars override config.json since v1.5.8.3079 |
| State | PVC for `scriptfiles/` and logs | gamemode writes there |
| Secrets | Secret → env | never bake RCON/DB passwords into config.json |

## Production Implementation

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: omp }
spec:
  replicas: 1
  selector: { matchLabels: { app: omp } }
  template:
    metadata: { labels: { app: omp } }
    spec:
      containers:
        - name: omp
          image: registry.example/omp:1.6.7.3218
          ports: [{ containerPort: 7777, protocol: UDP }]
          env:
            - { name: RCON_PASSWORD, valueFrom: { secretKeyRef: { name: omp, key: rcon } } }
          resources:
            limits: { cpu: "2", memory: 2Gi }
          volumeMounts: [{ name: data, mountPath: /srv/omp/scriptfiles }]
          readinessProbe:
            exec: { command: ["/bin/sh","-c","timeout 2 bash -c '</dev/tcp/127.0.0.1/7777' || exit 1"] }
            initialDelaySeconds: 10
      volumes:
        - name: data
          persistentVolumeClaim: { claimName: omp-data }
```

Rules:

- UDP has no connection handshake for probes; use a query packet or an exec probe that
  checks the process log line "server started".
- One instance per PVC; two pods sharing `scriptfiles/` corrupt saves.
- Rolling update needs a drain: stop accepting new players, wait for empty, then replace.

## Deprecated Traps & Edge Cases (2026)

- `Service` with TCP: players time out, logs look healthy.
- Readiness probe on HTTP: nothing answers, pod never ready.
- Replica >1 without sharding: same player data written twice.
- Baking secrets into the image because "it is just a game server".

## Verification

- `kubectl get svc` shows UDP and a real external IP.
- Rollout replaces a pod and players reconnect to the new one.
- Deleting a pod keeps `scriptfiles/` intact on the PVC.

## Sources (2026)

- https://open.mp/docs/server/CommonServerIssues
- https://open.mp/docs/changelog (v1.5.8.3079 env overrides)
