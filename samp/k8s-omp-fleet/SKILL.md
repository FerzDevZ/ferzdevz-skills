---
name: k8s-omp-fleet
description: Use when several open.mp servers run under Kubernetes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, ops, kubernetes, deploy, containers, udp]
    category: samp
---

# Run open.mp as a fleet of stateful pods

An open.mp server is a UDP process with a writable `scriptfiles/` directory and
no HTTP endpoint, so web-service recipes fail: a TCP `Service` never connects, an
HTTP probe never returns, and two pods on one volume corrupt saves. Model it as
one Deployment replica per shard plus one UDP `LoadBalancer` per replica.

## When to Use

- You run more than one open.mp instance and want one manifest per shard.
- You are moving a systemd unit into containers without losing `scriptfiles/`.
- Rolling updates must not announce a half-started server to the masterlist.
- Pods are Ready but players cannot connect because the Service speaks TCP.

## Compatibility & Stack Matrix (2026)

| Concern | Kubernetes answer | open.mp detail |
| --- | --- | --- |
| Game port | `Service` `type: LoadBalancer`, `protocol: UDP` | RakNet is UDP only; TCP gives timeouts |
| Health | `exec` probe on the bound UDP socket | there is no HTTP endpoint to probe |
| Config | `ConfigMap` mounted as `config.json` | strings expand `${VAR}` at startup |
| Secrets | `Secret` to env, referenced as `${RCON_PASSWORD}` | never bake passwords into the ConfigMap |
| State | `PersistentVolumeClaim`, `ReadWriteOnce` | `scriptfiles/` and logs live here |
| Scale unit | one Deployment replica per shard | two replicas on one volume corrupt saves |

## Production Implementation

1. Build a 32-bit-capable image. Without the i386 runtime libs the server exits
   on a loader error before it ever binds the port.

```dockerfile
FROM debian:bookworm-slim
RUN dpkg --add-architecture i386 && apt-get update \
 && apt-get install -y --no-install-recommends libc6:i386 libstdc++6:i386 iproute2 procps \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/omp
COPY --chown=1000:1000 omp/ ./
RUN mkdir -p scriptfiles
USER 1000:1000
EXPOSE 7777/udp
ENTRYPOINT ["./omp-server"]
```

2. Keep the config in a ConfigMap and let the server expand the environment. The
   `${VAR}` form resolves at startup, so the Secret never lands on disk.

```yaml
apiVersion: v1
kind: ConfigMap
metadata: { name: omp-config }
data:
  config.json: |
    {
      "name": "${SERVER_NAME:-omp shard 01}",
      "announce": false,
      "network": { "port": 7777 },
      "rcon": { "enable": true, "password": "${RCON_PASSWORD}" }
    }
```

3. One replica, one volume, one Service. `Recreate` is deliberate: a rolling
   update would run two copies of one shard against the same accounts.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: omp-01, labels: { app: omp, shard: "01" } }
spec:
  replicas: 1
  strategy: { type: Recreate }
  selector: { matchLabels: { app: omp, shard: "01" } }
  template:
    metadata: { labels: { app: omp, shard: "01" } }
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 1000 }
      containers:
        - name: omp
          image: registry.example/omp:1.6.7.3218
          ports: [{ name: game, containerPort: 7777, protocol: UDP }]
          env:
            - name: RCON_PASSWORD
              valueFrom: { secretKeyRef: { name: omp-secrets, key: rcon } }
          resources:
            requests: { cpu: 500m, memory: 512Mi }
            limits: { cpu: "2", memory: 2Gi }
          readinessProbe:
            exec: { command: ["/bin/sh", "-c", "ss -lun | grep -q ':7777 '"] }
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            exec: { command: ["/bin/sh", "-c", "ss -lun | grep -q ':7777 '"] }
            periodSeconds: 30
            failureThreshold: 4
          volumeMounts:
            - { name: data, mountPath: /srv/omp/scriptfiles }
            - { name: cfg, mountPath: /srv/omp/config.json, subPath: config.json }
      volumes:
        - { name: data, persistentVolumeClaim: { claimName: omp-01-data } }
        - { name: cfg, configMap: { name: omp-config } }
```

4. Expose one shard per Service and keep traffic local, so the pod that answers
   is the pod that owns the UDP socket.

```yaml
apiVersion: v1
kind: Service
metadata: { name: omp-01 }
spec:
  type: LoadBalancer
  externalTrafficPolicy: Local
  selector: { app: omp, shard: "01" }
  ports: [{ name: game, protocol: UDP, port: 7777, targetPort: 7777 }]
```

5. Provision the volume per shard. `ReadWriteOnce` is the honest mode for a game
   server that writes its own saves and nobody else touches them.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata: { name: omp-01-data }
spec:
  accessModes: [ReadWriteOnce]
  resources: { requests: { storage: 5Gi } }
```

6. Treat SIGTERM as best effort: Pawn shutdown code is not guaranteed to run, so
   saves must be written as they change and not only in `OnGameModeExit`.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Pods Ready, players time out | `Service` port left on TCP | set `protocol: UDP`, check `.spec.ports[0].protocol` |
| Pod restarts with a loader error | image missing `libc6:i386` / `libstdc++6:i386` | install the i386 runtime libs in the Dockerfile |
| Readiness never passes | probe uses HTTP or `/dev/tcp` (TCP) | `exec` probe with `ss -lun` on the game port |
| RCON password visible in Git | password hard-coded in the ConfigMap | `${RCON_PASSWORD}` from a `Secret` |
| Server announced twice during a rollout | `RollingUpdate` with `maxSurge: 1` | `Recreate`, or `announce: false` until drained |

## Verification

```bash
kubectl apply -f k8s/
kubectl rollout status deployment/omp-01
kubectl get svc omp-01 -o jsonpath='{.spec.ports[0].protocol}{"\n"}'
kubectl exec deploy/omp-01 -- ss -lun | grep 7777
```

- `rollout status` prints `deployment "omp-01" successfully rolled out`.
- The `jsonpath` prints `UDP`, not `TCP`.
- `ss` shows `UNCONN 0 0 0.0.0.0:7777`: the process in the pod owns the socket
  the Service forwards to; deleting the pod keeps `scriptfiles/` on the PVC.

## Sources (2026)

- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://kubernetes.io/docs/concepts/services-networking/service/
- https://open.mp/docs/server/config.json
