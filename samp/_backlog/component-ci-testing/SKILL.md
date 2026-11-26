---
name: component-ci-testing
description: Test a C++ component before it reaches a server.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, cpp, ci]
    category: samp
---

# Component CI testing

## When to Use

- A component must be proven to load, not just to compile.
- Two contributors build against different SDK versions.

## 2026 Compatibility & Architecture Matrix

| Check | Tool | Fails when |
| --- | --- | --- |
| Compile | CMake + compiler matrix | include/ABI drift |
| Interface version | SDK header constant | server refuses the component |
| Load smoke test | headless server + log grep | missing export or dependency |
| Memory safety | ASan/UBSan build | latent crash on unload |

## Production Implementation

```yaml
name: component
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-24.04
    strategy:
      matrix:
        sdk: [1.5.8.3079, latest]
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y cmake g++ libssl-dev
      - run: cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo
      - run: cmake --build build -j
      - name: smoke load
        run: |
          mkdir -p srv/components
          cp build/libmycomponent.so srv/components/
          ./srv/omp-server --config srv/config.json > srv/log.txt 2>&1 &
          sleep 5
          grep -q "mycomponent loaded" srv/log.txt
          grep -qv "failed to load" srv/log.txt
```

Rules that keep this green:

- Pin the SDK as a submodule or a released tarball, never `latest` only.
- Fail the job on the first `failed to load` line; a component that does not load is worse
  than a build error because it is silent in production.
- Run one job with `-fsanitize=address` and a connect/disconnect cycle.

## Deprecated Traps & Edge Cases (2026)

- Testing only on Windows; `RTLD_GLOBAL` and symbol visibility differ on Linux.
- Using `latest` SDK in CI and a pinned one in production: the mismatch ships.
- No unload test: destructors that free while a callback is queued crash at shutdown.

## Verification

- CI fails when you remove `OnLoad` from the component.
- The smoke job's log contains the loaded line and no `failed to load`.
- ASan job is clean across start, one player connect, shutdown.

## Sources (2026)

- https://github.com/openmultiplayer/open.mp
- https://open.mp/docs/changelog (v1.5.8.3079)
