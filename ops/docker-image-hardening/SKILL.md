---
name: docker-image-hardening
description: Use when hardening a container image for production.
version: "2026.1.0"
metadata:
  hermes:
    tags: [docker, containers, security, supply-chain]
    category: ops
---

# Harden a container image until a scan gate can pass it

A hardened image is not a smaller image with a `USER` line. It is an image whose
base is immutable, whose build context cannot leak secrets, whose final layer has
no compiler or shell, and whose digest is signed and reproducible. Each step
below removes a class of failure, and the last step proves it with a scanner.

## When to Use

- An image runs as root, ships a full OS toolchain, or is built from `:latest`.
- Trivy/Grype reports HIGH findings in base-image packages you never installed.
- A rebuild of the same commit produces a different image digest.
- A deploy needs a signed, attested artifact before it reaches production.
- Skip this when the image is a local throwaway, never pushed to a registry.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| Docker Engine | 27.x / 28.x | BuildKit is the default builder |
| BuildKit | v0.15+ | `--attest type=sbom,type=provenance` needs it |
| Base image | `gcr.io/distroless/static-debian12:nonroot` | uid/gid 65532, no shell |
| Trivy | 0.6x | `--exit-code`, `--severity`, `--ignore-unfixed` |
| cosign | 3.x | keyless OIDC signing, `--certificate-identity` on verify |
| CI runner | `ubuntu-24.04` | buildx and cosign preinstalled on hosted runners |

Distroless has no package manager and no shell: every `RUN` must happen in an
earlier stage, and `HEALTHCHECK` must exec the application binary itself.

## Production Implementation

1. Resolve the base tag to a digest and pin that. Tags move; digests do not.

```bash
export BASE=gcr.io/distroless/static-debian12:nonroot
export BASE_DIGEST=$(docker buildx imagetools inspect "$BASE" --format '{{.Manifest.Digest}}')
printf '%s@%s\n' "$BASE" "$BASE_DIGEST"
```

2. Cut the build context down before it carries a `.env` or a `.git` directory
   into a layer. `.dockerignore` is read before the daemon receives context.

```gitignore
.git
.github
node_modules
dist
coverage
*.log
.env*
Dockerfile*
docker-compose*.yml
README.md
```

3. Write a two-stage Dockerfile: build with a toolchain image, ship only the
   binary on distroless. `-trimpath` and an empty build id remove host paths and
   make the output stable across builders.

```dockerfile
# syntax=docker/dockerfile:1.7
FROM golang:1.24-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -buildid=" -o /out/app ./cmd/app

ARG BASE_DIGEST
FROM gcr.io/distroless/static-debian12:nonroot@${BASE_DIGEST}
COPY --from=build /out/app /app
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["/app", "healthcheck"]
ENTRYPOINT ["/app"]
```

4. Build with a fixed timestamp and both attestations. `SOURCE_DATE_EPOCH`
   normalises file and config timestamps; provenance records how it was built.

```bash
SOURCE_DATE_EPOCH=0 docker buildx build \
  --platform linux/amd64 \
  --build-arg BASE_DIGEST="$BASE_DIGEST" \
  --attest type=provenance,mode=max \
  --attest type=sbom \
  --tag registry.example.com/app:1.4.2 \
  --push .
```

5. Gate the build on a scan. `--ignore-unfixed` keeps the gate honest: a CVE with
   no patched version is not actionable and should not block every release.

```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed \
  --exit-code 1 --format table registry.example.com/app:1.4.2
```

6. Prove the runtime contract instead of assuming it.

```bash
docker image inspect registry.example.com/app:1.4.2 --format '{{.Config.User}}'
docker run --rm --entrypoint /app registry.example.com/app:1.4.2 version
```

7. Sign the pushed digest and verify it the way a deployer will: identity and
   issuer, not just "a signature exists".

```bash
cosign sign --yes registry.example.com/app@sha256:$IMAGE_DIGEST
cosign verify registry.example.com/app@sha256:$IMAGE_DIGEST \
  --certificate-identity=https://github.com/acme/app/.github/workflows/release.yml@refs/heads/main \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```

8. Rebuild the same commit twice and compare digests. A mismatch means a
   timestamp, a package index, or an unpinned download crept in.

```bash
docker buildx build --no-cache --build-arg BASE_DIGEST="$BASE_DIGEST" -q . | tee /tmp/a
docker buildx build --no-cache --build-arg BASE_DIGEST="$BASE_DIGEST" -q . | tee /tmp/b
diff /tmp/a /tmp/b && echo reproducible
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `COPY failed: no source files` after adding `.dockerignore` | pattern excludes a path a later stage needs | keep negations (`!src/`) or narrow the pattern to the artifact dir |
| Image still has `apk`/`apt` and 300 MB of base packages | final stage inherits the builder image | start the last stage from distroless or `scratch`, copy only the artifact |
| `HEALTHCHECK` never turns healthy | distroless has no shell, `CMD-SHELL` syntax silently fails | use exec form and a real subcommand on the binary |
| Scan gate fails only in CI, passes locally | local cache served an older Trivy DB | run `trivy image --download-db-only` or let `--skip-db-update=false` refresh |
| Two builds of one commit differ in digest | build timestamps or `-buildid` left in | set `SOURCE_DATE_EPOCH`, build with `-trimpath -buildid=` |
| `cosign verify` fails in deploy despite a signature | wrong `--certificate-identity` (workflow path or ref) | match the identity string exactly, including `@refs/heads/main` |

## Verification

- `docker buildx imagetools inspect "$BASE" --format '{{.Manifest.Digest}}'` prints a `sha256:` digest, and the Dockerfile `FROM` contains that literal digest.
- `docker image inspect IMAGE --format '{{.Config.User}}'` prints `65532:65532`.
- `trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 IMAGE` exits 0 and prints a table with zero HIGH/CRITICAL rows.
- `cosign verify IMAGE --certificate-identity=... --certificate-oidc-issuer=...` prints the signature payload containing the verified digest and identity.
- The double-build `diff` prints `reproducible`.

## Sources (2026)

- https://docs.docker.com/build/building/multi-stage/
- https://docs.docker.com/dhi/explore/security-concepts/digests/
- https://trivy.dev/docs/latest/guide/references/configuration/cli/trivy_image/
