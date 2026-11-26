---
name: samp-dev-router
description: Use when SA-MP work needs the right skill routed.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, navigation, index]
    category: samp
author: Hermes Agent
license: MIT
---

# SA-MP developer router

`samp/` holds more topics than one context window can carry, and `samp/_backlog/` holds
drafts that are **not loadable skills**. Route from the table below, then load one skill —
two only when the task crosses a boundary the first one names.

## When to Use

- A SA-MP/open.mp task is in front of you and you do not know which skill owns it.
- You are about to cite a skill name and are not sure it exists.
- A gate run failed and you need the owning skill plus the gate owner.

## Compatibility & Stack Matrix (2026)

The router carries no API of its own; it only names skills whose matrix rows are pinned.

| Layer | 2026 baseline | Pinned in |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 (1.5.8.3079 adds NPC, C API, `${VAR}` config) | `assets/versions.json` |
| Compiler | pawncc 3.10.10 | `assets/versions.json` |
| Legacy server | SA-MP 0.3.7-R2, 0.3.DL client | skill matrix rows |
| Natives allowlist | 1179 names (docs + omp-stdlib + plugins) | `assets/omp_natives.txt` |
| Script libs | YSI 5.x via sampctl, streamer 2.9.6 | `assets/versions.json` |
| Contract gate | `bin/audit.py` (section order, depth, sources) | repo `bin/` |

## Production Implementation

1. Find the closest row, then confirm the folder exists before loading or citing it:

```bash
test -f samp/omp-observability-metrics/SKILL.md && echo present
```

| Task | Load |
| --- | --- |
| Build flags, warnings, reproducible compile | `pawncc-cli-flags` |
| server.cfg to config.json, 2026 keys | `server-cfg-to-config-json` |
| Callback splitting, YSI timers | `ysi-y-hooks-modularization`, `ysi-y-timers-task-system` |
| Commands, dialogs, spoofed dialog replies | `pawncmd-sscanf2-command-pattern`, `dialog-spoofing-validation` |
| Crash log, runtime error 19 | `crashdetect-stacktrace-parser`, `runtime-error-19-plugin-fix` |
| Player state, async load/save | `state-machine-player-fsm`, `async-player-data-load-save` |
| Teleport, weapon and fake-kill abuse, RPC floods | `teleport-airbreak-detection`, `weapon-ammo-desync-anticheat`, `fake-kill-bullet-crasher-shield`, `raknet-incoming-rpc-filter` |
| Schema, migrations, slow queries | `database-schema-migration`, `mysql-slow-query-debugger`, `inventory-relational-schema` |
| Transactions, money duplication | `transaction-rollback-economy`, `money-duplication-prevention` |
| Inventory storage vs grid UI | `inventory-relational-schema`, `clickable-textdraw-inventory` |
| TextDraw lifecycle, hitboxes, pools, scaling | `player-textdraw-lifecycle`, `textdraw-clickable-hitbox-math`, `textdraw-limit-2048-optimizer`, `textdraw-widescreen-mobile-scaling` |
| Maps, streamer, materials, building removal | `dynamic-object-map-loader`, `incognito-streamer-tuning`, `dynamic-object-material-retexture`, `removebuilding-collision-fix` |
| Interiors and virtual worlds | `interior-virtualworld-routing` |
| Vehicles: state, damage, custom models, attachments | `vehicle-data-persistence`, `vehicle-damage-part-sync`, `omp-custom-vehicles-models`, `attached-object-bone-offsets` |
| 0.3.DL custom models | `custom-models-03dl-artconfig` |
| Leaks, tick metrics, log scanning | `memory-leak-timer-audit`, `omp-observability-metrics`, `server-log-anomaly-scanner` |
| Restart without dropping players | `zero-downtime-gmx-restart` |
| Writing or repairing a skill | `samp-skill-authoring` |

2. Load a second skill only when the task crosses a named boundary: mapping plus collision
   is `dynamic-object-map-loader` then `removebuilding-collision-fix`; persistence plus
   economy is `vehicle-data-persistence` then `transaction-rollback-economy`.

3. If the only match is a draft under `samp/_backlog/`, say the topic is unwritten. Do not
   paraphrase the draft and do not present it as an installed skill.

4. When two installed skills disagree, the owner wins: `pawncc-cli-flags` for the build,
   `ysi-y-hooks-modularization` for YSI wiring, `samp-economy-jobs`-class work belongs to
   `transaction-rollback-economy` for money, `memory-leak-timer-audit` for timers.

5. After editing any skill, run the contract gate scoped to the category:

```bash
python3 bin/audit.py --root . --only samp --names samp-dev-router
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Routing names a skill that will not load | topic lives in `samp/_backlog/` | `ls samp/<name>`; if absent, say unwritten |
| Two skills give different native names | duplicated ownership | owner table above wins; fix the other skill |
| `validate_library.py` reports two missing sections | it still checks the pre-contract headers (`2026 Compatibility & Architecture Matrix`, `Deprecated Traps`) | `bin/audit.py` decides; do not rename headers back |
| `check_natives.py` flags a real native | allowlist stale | rebuild per `references/library-gates.md`; never edit the snippet to a guess |
| Standalone compile of a snippet fails on `playerid` | snippets are fragments, not units | use `assets/harness/compile_harness.py` |
| Router row drifts after a rename | table edited by hand | the verification below prints the missing names |
| Ten skills loaded for one task | no routing step | one skill, then one boundary skill |

## Verification

Every backticked name in the routing table must resolve to a folder:

```bash
python3 - <<'PY'
import pathlib, re
lines = pathlib.Path("samp/samp-dev-router/SKILL.md").read_text().splitlines()
start = lines.index("| Task | Load |") + 2
rows = []
for line in lines[start:]:
    if not line.startswith("|"):
        break
    rows.append(line)
names = {n for r in rows for n in re.findall(r"`([a-z0-9-]+)`", r)}
have = {p.parent.name for p in pathlib.Path("samp").glob("*/SKILL.md")}
print(f"{len(names)} routed, {len(have)} present, missing={sorted(names - have)}")
PY
```

Expected on a healthy pack (the present count includes this router itself):

```text
39 routed, 40 present, missing=[]
```

Then the contract gate for this skill alone:

```bash
python3 bin/audit.py --root . --only samp --names samp-dev-router
```

```text
skills: 1  categories: 1  lines: 128  avg: 128
per category: samp=1

OK    all skills pass structure and depth gates
```

## Sources (2026)

- https://open.mp/docs
- https://open.mp/docs/changelog
- https://github.com/openmultiplayer/omp-stdlib
