---
name: skill-router
description: Use when unsure which pack skill applies. Route by symptom.
version: "2026.1.1"
metadata:
  hermes:
    tags: [meta, routing, skills, index]
    category: meta
---

# Route a symptom to one skill

With 183 skills, the expensive mistake is not missing knowledge, it is loading the
wrong file or two files that disagree. This router turns a symptom into exactly one
skill name. Load that skill, follow its Verification, and only then add a second one.

## When to Use

- The user describes a symptom ("pages are stale", "taps miss", "kill money appears
  without a shot") and several skills look plausible.
- You are about to load three skills "just in case"; the third one usually contradicts
  the second.
- A skill you loaded does not apply: come back here instead of improvising.
- Not for trivia inside one domain: if the symptom has an obvious owner below, go
  straight to it.

## Compatibility & Stack Matrix (2026)

| Component | Version | Note |
| --- | --- | --- |
| Pack layout | `<category>/<skill>/SKILL.md` | 11 categories, 183 skills |
| Discovery | name + description only | routing quality = description quality |
| Router audit | `bin/route_audit.py` | collision + generic-description detector |
| Catalog | `CATALOG.md` | generated; the full list with line counts |

## Production Implementation

1. Match the symptom, not the technology. "Slow page" is a performance problem before
   it is a Next.js problem.

2. First table: symptom -> owner skill.

| Symptom | Skill |
| --- | --- |
| Route flips dynamic, stale data after a mutation | `nextjs-app-router-production` |
| p75 LCP/INP/CLS regressed | `web-performance-core-vitals` |
| Slow query that only hurts at scale | `postgres-query-and-index-tuning` |
| Login/session lost, CSRF or rotation doubt | `auth-session-cookie-hardening` |
| Type errors only in CI, slow type check | `typescript-strict-project-setup` |
| Colours fail contrast or dark mode remaps everything | `color-system-accessible-palette` |
| Tokens drift between Figma, CSS and mobile | `design-tokens-dtcg-pipeline` |
| Type sizes ad hoc, layout shifts on font load | `typography-scale-web` |
| Component props keep growing, refs break | `component-api-design` |
| Form validation timing, copy, server errors | `forms-ux-validation-patterns` |
| Empty/loading/error states missing | `empty-states-and-error-ux` |
| Accessibility verdict needed with evidence | `accessibility-wcag22-audit` |
| Usability test with real users | `usability-testing-moderated` |
| Flutter app outgrew `main.dart` | `flutter-project-architecture` |
| RN crashes only in release, Fabric doubts | `react-native-new-architecture` |
| Android R8/signing/Play rejection | `android-release-hardening` |
| Offline edits duplicate after sync | `mobile-offline-sync-queue` |
| Same design forced onto iOS and Android | `ios-hig-vs-material3` |
| Taps miss, targets under 44pt/48dp | `touch-targets-and-thumb-zones` |
| LLM app loops, overflows, drifts | `llm-app-context-engineering` |
| RAG misses exact terms or cites wrong passage | `rag-retrieval-pipeline` |
| "Is this RAG change better?" needs a gate | `rag-evaluation-harness` |
| ML idea needs a metric and a baseline | `ml-problem-framing-baseline` |
| Image is 1.2 GB and runs as root | `docker-image-hardening` |
| CI order, caching, required checks drift | `ci-pipeline-gates` |
| Dependency pins or SBOM missing | `dependency-supply-chain-security` |
| TextDraw pool near 2048/256 | `textdraw-limit-2048-optimizer` |
| HUD element overlaps or misses clicks | `textdraw-clickable-hitbox-math` |
| Objects pop, flicker or lag when loading | `incognito-streamer-tuning` |
| Fake kill, bullet crasher, free kill money | `fake-kill-bullet-crasher-shield` |
| Damage/ammo numbers disagree with the server | `weapon-ammo-desync-anticheat` |
| Player crosses the map without a warp | `teleport-airbreak-detection` |
| Dialog answers the client invented | `dialog-spoofing-validation` |
| MySQL/MariaDB deadlock or doubled money | `transaction-rollback-economy` |
| Server crashes with "file or function not found" | `runtime-error-19-plugin-fix` |
| Server restarts drop every player | `zero-downtime-gmx-restart` |
| Skill pack drifting into stubs | `skill-library-auditor` |

3. If two rows match, take the narrower one: the skill about a specific symptom beats
   the skill about the category. `textdraw-clickable-hitbox-math` beats
   `player-textdraw-lifecycle` when clicks miss.

4. Not in the table? Search the catalog rather than guessing.

```bash
grep -i "textdraw" CATALOG.md
python3 bin/route_audit.py --json | head -40
```

5. After loading, run the skill's own Verification before believing the fix. A skill
   that cannot be verified is a hypothesis.

## Failure Modes & Fixes

| Gejala | Sebab | Perbaikan |
| --- | --- | --- |
| Two skills give opposite advice | both loaded, one is narrower | keep the narrower skill; unload the general one |
| Correct skill loaded, answer still wrong | its Verification was skipped | run the command in the skill's Verification section |
| No skill ever matches a recurring task | the description lacks the user's words | edit the description, then rerun `bin/route_audit.py` |
| Router table names a skill that does not exist | table written by hand after a rename | check the name against `CATALOG.md` / `ls <category>` |
| 183 skills feel slow to search | catalog not regenerated | `python3 bin/catalog.py` then grep it |
| Pack feels like a dump again | no collision gate in CI | add `bin/route_audit.py --fail-on-dupes` to CI |

## Verification

```bash
python3 bin/route_audit.py                 # expect 0 collisions, 0 generic
python3 bin/catalog.py --check             # catalog matches the tree
grep -c '^- `' CATALOG.md                  # entry count
```

- Every skill named in the table above appears in `CATALOG.md`:

```bash
for s in nextjs-app-router-production rag-evaluation-harness fake-kill-bullet-crasher-shield; do
  grep -q "^- \`$s\`" CATALOG.md && echo "ok $s" || echo "MISSING $s"
done
```

## Sources (2026)

- https://agentskills.io/home
- https://learn.microsoft.com/en-us/agent-framework/agents/skills
