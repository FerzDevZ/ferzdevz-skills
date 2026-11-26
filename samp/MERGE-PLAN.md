# Merge plan

A token-similarity scan (Jaccard on words, threshold 0.22) returns 1406 pairs, but that
number is an artifact: every skill shares the same section headings and vocabulary, so
similarity measures the template, not redundancy. Merging on that signal would delete
distinct content.

Merge rule that actually holds: merge skill B into A only when B adds **no new command,
no new URL, and no new native** that A does not already have. Anything else is depth, not
duplication.

Until that review happens, overlap is governed by ownership (see `samp-dev-router`):

| Topic | Owner |
| --- | --- |
| Build, compiler | `pawncc-cli-flags` |
| YSI | `ysi-y-hooks-modularization` |
| Commands and dialogs | `samp-command-dialog-system` |
| TextDraw / NTD | `samp-textdraw-ui` |
| Mapping and streamer | `samp-mapping-streamer` |
| Anti-cheat | `samp-anticheat-server` |
| Persistence and SQL | `transaction-rollback-economy` |
| NPC | `omp-built-in-npc-scripting` |
| Server operations | `samp-server-ops` |

When two skills disagree, the owner wins and the other one links to it.
