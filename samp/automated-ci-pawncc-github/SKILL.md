---
name: automated-ci-pawncc-github
description: Use when a Pawn build must gate a deploy in CI.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ci, github-actions]
    category: samp
---

# Gate a Pawn build in Actions before anything ships

## When to Use

- Compiles on your machine, fails on a teammate's, and nobody can say which include set was used.
- A warning-only build reaches production because `pawncc` exited `0`.
- The `.amx` on the server is older than the commit that was tested.
- Not for a C++ open.mp component; that is `component-ci-testing`.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| Runner | `ubuntu-24.04` | the linux tarball is glibc-linked, no musl image |
| Compiler | `pawncc` 3.10.10 (`pawn-lang/compiler`) | release asset `pawnc-3.10.10-linux.tar.gz` |
| Shared lib | `libpawnc.so` beside the binary | tarball has no `RPATH`; `LD_LIBRARY_PATH` is mandatory |
| Include set | `openmultiplayer/omp-stdlib` (`master`) | pin a commit SHA for a reproducible build |
| Warning policy | `-E` | turns `warning 2xx` into `error 2xx`, exit code `1` |
| Action majors | `checkout@v4`, `cache@v4`, `upload-artifact@v4`, `setup-python@v5` | newer major tags exist; bump them deliberately |

## Production Implementation

1. Fetch the compiler by pinned version and put its own `lib` on the loader path. Measured here:
   without it, `pawncc` dies with `error while loading shared libraries: libpawnc.so`.

2. Wire it into a workflow. The cache key carries the compiler version, so a bump invalidates the
   cache instead of restoring a half-extracted toolchain. `GITHUB_PATH` only covers `bin`, so the
   shared library goes into `GITHUB_ENV` separately:

```yaml
name: build
on: [push, pull_request, workflow_dispatch]
permissions:
  contents: read
env:
  PAWNCC_VERSION: "3.10.10"
jobs:
  compile:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4      # includes, as a second checkout
        with:
          repository: openmultiplayer/omp-stdlib
          path: deps/omp-stdlib
      - name: Cache pawncc
        uses: actions/cache@v4
        with:
          path: ~/pawncc
          key: pawncc-${{ runner.os }}-${{ env.PAWNCC_VERSION }}
      - name: Install pawncc
        run: |
          set -euo pipefail
          mkdir -p "$HOME/pawncc"
          if [ ! -x "$HOME/pawncc/bin/pawncc" ]; then
            curl -fsSL -o /tmp/pawnc.tar.gz \
              "https://github.com/pawn-lang/compiler/releases/download/v${PAWNCC_VERSION}/pawnc-${PAWNCC_VERSION}-linux.tar.gz"
            tar -xzf /tmp/pawnc.tar.gz -C "$HOME/pawncc" --strip-components=1
          fi
          echo "$HOME/pawncc/bin" >> "$GITHUB_PATH"
          echo "LD_LIBRARY_PATH=$HOME/pawncc/lib" >> "$GITHUB_ENV"
          "$HOME/pawncc/bin/pawncc" | head -n 1
```

3. Compile with `-E`, plus a log guard. Both must fail the job: `pawncc` exits `0` on a warning.

```yaml
      - name: Compile
        run: |
          set -euo pipefail
          mkdir -p gamemodes
          pawncc -i"deps/omp-stdlib" -d3 -O2 '-;+' '-(+' -E \
                 -ogamemodes/main.amx gamemodes/main.pwn | tee build.log
          if grep -qE ':[0-9]+ (warning|error) [0-9]+:' build.log; then
            echo "compiler emitted diagnostics" >&2
            exit 1
          fi
```

4. Prove the artefact is an AMX and not a stale or zero-byte file. A compiler exit code is not
   evidence that the binary is loadable:

```python
import pathlib, struct, sys

path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "gamemodes/main.amx")
raw = path.read_bytes()
magic = struct.unpack("<H", raw[4:6])[0]
if magic != 0xF1E0:
    sys.exit(f"not an AMX: magic {magic:#06x}")
if len(raw) < 1024:
    sys.exit(f"suspiciously small AMX: {len(raw)} bytes")
print(f"amx ok bytes={len(raw)} magic={magic:#06x}")
```

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Check AMX header
        run: python tools/check_amx.py gamemodes/main.amx
```

5. Publish only what passed the header check, on every ref, so a reviewer can download the PR
   build:

```yaml
      - uses: actions/upload-artifact@v4
        with:
          name: main-amx
          path: gamemodes/main.amx
          if-no-files-found: error
          retention-days: 14
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error while loading shared libraries: libpawnc.so` | tarball ships no `RPATH` | `export LD_LIBRARY_PATH=$HOME/pawncc/lib` |
| Job green with `1 Warning.` in the log | `pawncc` exits `0` on warnings | add `-E` plus the log grep |
| `fatal error 100: cannot read from file: ".../omp-stdlib.p"` | `-i /path` with a space is read as a file name | attach it: `-i"deps/omp-stdlib"` |
| `bash: syntax error near unexpected token '('` | unquoted `-;+` or `-(+` | quote both flags inside `run:` |
| Artifact step succeeds, download is empty | no `if-no-files-found` and no header check | keep both guards in the job |
| `warning 203: symbol is never used` from a third-party include | strict `-E` over code you do not own | pass `-w203` for that file only |
| Cache hit restores a broken toolchain | key ignores the compiler version | key on `PAWNCC_VERSION`, probe with `-v` first |

## Verification

```bash
set -euo pipefail
pawncc -i/home/aegisx/samp-sdk/omp-stdlib -d3 -O2 '-;+' '-(+' -E \
       -ogamemodes/main.amx gamemodes/main.pwn | tee build.log
grep -qE ':[0-9]+ (warning|error) [0-9]+:' build.log && exit 1 || true
python3 tools/check_amx.py gamemodes/main.amx
```

Expected output from the run that produced this skill:

```text
Pawn compiler 3.10.10	 	 	 	Copyright (c) 1997-2006, ITB CompuPhase

Header size:            228 bytes
Code size:               48 bytes
Data size:               44 bytes
Stack/heap size:      16384 bytes; estimated max. usage=73 cells (292 bytes)
Total requirements:   16704 bytes
amx ok bytes=1385 magic=0xf1e0
```

Add one unused local to `main()` and re-run: with `-E` it prints `error 204: symbol is assigned a
value that is never used` and exits `1`; without `-E`, `warning 204` and exit `0`. That is the gate.

## Sources (2026)

- https://github.com/pawn-lang/compiler
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://github.com/actions/checkout
