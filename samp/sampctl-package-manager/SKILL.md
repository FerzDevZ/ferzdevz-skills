---
name: sampctl-package-manager
description: Use when includes drift from the manifest.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, sampctl, build]
    category: samp
---

# Make the build reproducible with sampctl and a committed lockfile

sampctl reads one manifest, `pawn.json` or `pawn.yaml`, resolves declared GitHub packages into
`dependencies/`, and compiles `entry` to `output`. Anything copied into the include path by hand
is invisible to that manifest, so it survives on your disk and disappears on the build host.

## When to Use

- Includes were copied by hand and the build only works on one machine.
- You need a pinned YSI, streamer or MySQL version per project instead of "latest".
- CI must produce the same `.amx` as the release you tested.

## Compatibility & Stack Matrix (2026)

| Manifest field | Meaning in the docs | Example value |
| --- | --- | --- |
| `user`, `repo` | GitHub owner and repository name; required for `sampctl release` | `"ferz"`, `"gamemode"` |
| `entry` / `output` | source to compile, `.amx` to write | `gamemodes/main.pwn` |
| `dependencies` | GitHub packages to download for build and run | `pawn-lang/YSI-Includes@5.x` |
| `dev_dependencies` | packages needed only for build and test | test harness includes |
| `include_path` | subfolder holding Pawn sources | `gamemodes` |
| `overrides` | map from a dependency string to its replacement | pin one PawnPlus version |
| `runtime` / `runtimes` | one or several named runtime configs | port, hostname, maxplayers |
| `runtime.plugins` | binaries loaded from `plugins/` | `streamer.so` |
| `preset` | defaults for compiler and runtime | `samp` or `openmp` |
| `pawn.lock` | resolved revisions, committed beside the manifest | written by `sampctl ensure` |

Pin syntax is `user/repo:1.2.3` for a tag, `user/repo@branch` for a branch, and `user/repo#sha1`
for a commit. There is no manifest key named `path`: the repo is identified by `user` and `repo`,
and local layout is set with `include_path` and `runtime_dir`.

## Production Implementation

1. Declare everything the source includes, with tags. A branch is a moving target; a tag is a
   fact you can rebuild from in a year.

```json
{
  "user": "ferz",
  "repo": "gamemode",
  "entry": "gamemodes/main.pwn",
  "output": "gamemodes/main.amx",
  "preset": "openmp",
  "include_path": "gamemodes",
  "dependencies": [
    "pawn-lang/YSI-Includes@5.x",
    "samp-incognito/samp-streamer-plugin:2.8.2"
  ],
  "runtime": {
    "version": "1.4.0.2779",
    "port": 7777,
    "rcon_password": "change-me",
    "maxplayers": 50
  }
}
```

2. Add and remove dependencies through the CLI so the manifest and downloads stay in step.
   `sampctl install` writes the declaration; `sampctl ensure` installs what is declared.

```bash
sampctl install pawn-lang/YSI-Includes@5.x
sampctl uninstall pawn-lang/YSI-Includes
sampctl ensure
```

3. Use a dependency scheme when the package ships binaries rather than sources. A plain
   `user/repo` entry downloads the repo; `plugin://` and `component://` also place the built
   binary in `plugins/` or `components/` and add it to the generated runtime config.

```json
{
  "dependencies": [
    "plugin://samp-incognito/samp-streamer-plugin:2.8.2",
    "component://openmultiplayer/omp-stdlib"
  ]
}
```

4. Build with `sampctl build`. The `sampctl package build` form in older tutorials is not in the
   current command reference, and a CI script that still calls it fails with "unknown command".

```bash
sampctl ensure
sampctl build
sampctl check
```

5. Commit `pawn.lock` next to the manifest. It records resolved revisions plus the compiler and
   runtime that produced the last good build, which is what makes CI and production agree.

```bash
git add pawn.json pawn.lock
git commit -m "pin includes"
```

6. In CI, refuse to silently re-resolve. `sampctl ensure --lock-only` refreshes pins without
   installing; `--no-lock` is for throwaway experiments, never for a release build.

```bash
set -euo pipefail
sampctl ensure --lock-only
git diff --exit-code pawn.lock
sampctl build
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Build works on one machine only | includes copied by hand beside the sources | declare each package in `dependencies`, delete the copies |
| Yesterday's build cannot be reproduced | dependency pinned to a branch or `master` | pin a tag or a commit sha |
| `unknown command "package"` in CI | tutorial-era `sampctl package build` | run `sampctl build` |
| Plugin binaries missing at runtime | repo listed without a scheme | use `plugin://user/repo` or `component://user/repo` |
| `pawn.lock` rewritten on every run | CI resolves unpinned deps | commit the lock and gate with `--lock-only` |
| Duplicate symbol or redefinition | sampctl includes plus a hand-copied include | remove the copy; keep one owner per include |
| Source not found during compile | `entry` or `include_path` points at the wrong level | fix `include_path` relative to the package root |

## Verification

A clean checkout must build from the manifest alone:

```bash
git clean -xdf dependencies plugins
sampctl ensure >/dev/null && sampctl build >/dev/null && echo BUILD_OK
```

```text
BUILD_OK
```

Then prove the lockfile is stable and the compiler agrees with it:

```bash
git status --porcelain pawn.lock
sampctl check >/dev/null; echo "check_exit=$?"
```

```text
check_exit=0
```

Empty `git status` output means `ensure` resolved to the committed pins. A non-empty line means
something is still unpinned and the next machine may compile different code.

## Sources (2026)

- https://github.com/Southclaws/sampctl/blob/master/docs/packages.md
- https://github.com/Southclaws/sampctl/blob/master/docs/dependencies.md
- https://github.com/Southclaws/sampctl/blob/master/docs/package-definition-reference.md
