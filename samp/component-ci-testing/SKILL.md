---
name: component-ci-testing
description: Use when a C++ component must be proven to load in CI.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, cpp, ci, github-actions, cmake]
    category: samp
---

# Prove the component loads, not just that it compiles

A component that fails to compile is a red build; one that compiles but is not
loaded is a silent outage where Pawn hits runtime error 19 on first join. CI has
to check three things in order - the build is 32-bit, it exports
`ComponentEntryPoint`, and the real server loads it and logs a line you own.

## When to Use

- A C++ component or legacy plugin is about to be deployed to a live server.
- Two contributors build against different SDK commits and "works on my machine".
- The server starts but Pawn reports runtime error 19 for your natives.
- A crash appears only at shutdown, when components are freed.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218, `open.mp-linux-x86.tar.gz` | x86 build only, so components must be 32-bit |
| SDK | `open.mp-sdk` git submodule | pin by commit; `latest` is not a version |
| Compiler | clang 18 on `ubuntu-24.04` | clang ships an i386 `compiler-rt`, so ASan works with `-m32` |
| Build | CMake 3.19+, Ninja | template passes `-m32` through `CMAKE_C_FLAGS` and `CMAKE_CXX_FLAGS` |
| Entry point | `COMPONENT_ENTRY_POINT()` | expands to `extern "C" IComponent* ComponentEntryPoint` |
| Smoke test | real server tarball + `grep` on its log | a build that never loads is not tested |
| Sanitizer | `-fsanitize=address,undefined` | separate job, run start/connect/stop |

## Production Implementation

1. Pin the SDK as a submodule. A floating branch means CI and production can
   compile different headers with the same commit hash in your repo.

```bash
git submodule add https://github.com/openmultiplayer/open.mp-sdk sdk
git -C sdk checkout "$(git -C sdk rev-parse HEAD)"   # record the exact commit
git add .gitmodules sdk && git commit -m "pin open.mp SDK"
```

2. Keep CMake doing the 32-bit switch, not the workflow, so a local build
   matches CI exactly.

```cmake
cmake_minimum_required(VERSION 3.19)
project(mycomponent LANGUAGES C CXX VERSION 1.0.0)
set(CMAKE_CXX_STANDARD 17)
add_subdirectory(sdk)
add_library(mycomponent SHARED main.cpp component.cpp)
target_link_libraries(mycomponent PRIVATE OMP-SDK)
```

3. Log a line you own from `onLoad`. Do not grep for the server's generic
   "component loaded" text; own the assertion.

```cpp
void MyComponent::onLoad(ICore* c)
{
    core_ = c;
    core_->logLn(LogLevel::Info, "mycomponent ready v1.0.0");
}
```

4. Build and smoke-test on the real binary. The tarball name and tag are the
   release asset names, not guesses.

```yaml
name: component
on:
  push: { branches: [main] }
  pull_request:
jobs:
  build:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
        with: { submodules: recursive }
      - name: toolchain
        run: |
          sudo apt-get update
          sudo apt-get install -y clang cmake ninja-build g++-multilib libstdc++6:i386
      - name: configure
        env: { CC: clang, CXX: clang++ }
        run: >-
          cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
          -DCMAKE_C_FLAGS=-m32 -DCMAKE_CXX_FLAGS=-m32
      - name: build
        run: cmake --build build --parallel
      - name: assert 32-bit export
        run: |
          file build/libmycomponent.so | grep -q 'ELF 32-bit'
          nm -D --defined-only build/libmycomponent.so | grep -q ' ComponentEntryPoint$'
      - name: smoke load
        run: |
          set -euo pipefail
          curl -fsSL -o omp.tar.gz https://github.com/openmultiplayer/open.mp/releases/download/v1.6.7.3218/open.mp-linux-x86.tar.gz
          mkdir -p srv && tar -xzf omp.tar.gz -C srv
          mkdir -p srv/components
          cp build/libmycomponent.so srv/components/
          cd srv
          ./omp-server --config config.json > server.log 2>&1 &
          sleep 8
          grep -q 'mycomponent ready' server.log
          ! grep -qi 'failed to load\|Failed to load' server.log
```

5. Give the smoke run a real config: `rcon.password` may not stay `changeme`,
   and `announce` must be off so CI does not register a public server.

```json
{ "name": "ci", "announce": false,
  "network": { "port": 7777 },
  "rcon": { "enable": false, "password": "ci-not-a-real-password" } }
```

6. Add a sanitizer job with the same flags but clang's own runtime. GCC needs a
   separately installed 32-bit `libasan`; clang's `compiler-rt` ships i386.

```bash
CC=clang CXX=clang++ cmake -S . -B build-asan -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_FLAGS="-m32 -fsanitize=address,undefined" \
  -DCMAKE_CXX_FLAGS="-m32 -fsanitize=address,undefined" \
  -DCMAKE_SHARED_LINKER_FLAGS="-m32 -fsanitize=address,undefined"
cmake --build build-asan --parallel
```

7. Upload `build/libmycomponent.so` with `actions/upload-artifact@v4`, named
   with the SDK commit. A green job with no artifact hides which binary ran.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Server starts, native missing at runtime | component not loaded | grep your own `onLoad` line, fail the job if absent |
| `wrong ELF class: ELFCLASS64` in the log | built without `-m32` | pass `-m32` in both C and CXX flags, assert with `file` |
| `undefined symbol: _ZTV...` at load | SDK and component built by different compilers/STL | build both in the same job with the same clang |
| Component loads locally, not in CI | SDK submodule not checked out | `submodules: recursive` on `actions/checkout` |
| Smoke job passes while the server crashed | `grep` ran before the log flushed | assert the log line, then assert no `failed to load`, then kill |
| ASan link error on `-m32` | gcc without 32-bit `libasan` | use clang, whose `compiler-rt` includes the i386 runtime |

## Verification

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS=-m32 -DCMAKE_CXX_FLAGS=-m32
cmake --build build --parallel
file build/libmycomponent.so
nm -D --defined-only build/libmycomponent.so | grep ComponentEntryPoint
```

- `file` prints `build/libmycomponent.so: ELF 32-bit LSB shared object, Intel
  80386, version 1 (SYSV), dynamically linked`.
- `nm` prints one line ending in `T ComponentEntryPoint`.
- The CI log contains `mycomponent ready` and no `failed to load`; removing the
  export or the `-m32` flag turns both into a red job.

## Sources (2026)

- https://github.com/openmultiplayer/full-template
- https://open.mp/docs/tutorials/PluginDevelopmentGuide
- https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions
