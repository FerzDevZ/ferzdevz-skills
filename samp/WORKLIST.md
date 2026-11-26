# SA-MP/open.mp dev skills: upgrade worklist

Total: 134 skills di `samp/`. Gate pack ini butuh section lengkap, >=60 baris, tabel Failure Modes, dan >=2 sumber hidup.

Status awal (impor dari ~/.hermes/skills/samp): 0 dari 134 lulus gate; rata-rata 32 baris.

Skill yang belum di-upgrade dipindah ke `samp/_backlog/<nama>/` sehingga tidak ikut gate
dan tidak ikut `bin/install.sh`. Setelah lulus gate, pindahkan kembali ke `samp/<nama>/`
dan centang barisnya di bawah.

## Wave 1 (40 skill, sedang dikerjakan)

### w1-textdraw-ui
- [x] `textdraw-clickable-hitbox-math`
- [x] `player-textdraw-lifecycle`
- [x] `textdraw-limit-2048-optimizer`
- [x] `clickable-textdraw-inventory`
- [x] `textdraw-widescreen-mobile-scaling`
### w1-streamer-objects
- [x] `incognito-streamer-tuning`
- [x] `dynamic-object-map-loader`
- [x] `dynamic-object-material-retexture`
- [x] `removebuilding-collision-fix`
- [x] `interior-virtualworld-routing`
### w1-data-economy
- [x] `transaction-rollback-economy`
- [x] `inventory-relational-schema`
- [x] `database-schema-migration`
- [x] `mysql-slow-query-debugger`
- [x] `money-duplication-prevention`
### w1-anticheat-net
- [x] `fake-kill-bullet-crasher-shield`
- [x] `weapon-ammo-desync-anticheat`
- [x] `teleport-airbreak-detection`
- [x] `raknet-incoming-rpc-filter`
- [x] `dialog-spoofing-validation`
### w1-build-ops
- [x] `server-cfg-to-config-json`
- [x] `pawncc-cli-flags`
- [x] `runtime-error-19-plugin-fix`
- [x] `crashdetect-stacktrace-parser`
- [x] `zero-downtime-gmx-restart`
### w1-vehicles
- [x] `vehicle-data-persistence`
- [x] `vehicle-damage-part-sync`
- [x] `attached-object-bone-offsets`
- [x] `custom-models-03dl-artconfig`
- [x] `omp-custom-vehicles-models`
### w1-commands-state
- [x] `pawncmd-sscanf2-command-pattern`
- [x] `state-machine-player-fsm`
- [x] `ysi-y-hooks-modularization`
- [x] `ysi-y-timers-task-system`
- [x] `async-player-data-load-save`
### w1-router-meta
- [x] `samp-dev-router`
- [x] `samp-skill-authoring`
- [x] `memory-leak-timer-audit`
- [x] `server-log-anomaly-scanner`
- [x] `omp-observability-metrics`

## Wave 2 (47 skill)

- [ ] `3d-text-label-streaming`
- [ ] `actor-npc-shopkeeper-setup`
- [ ] `admin-action-audit-trail`
- [ ] `amx-decompilation-audit`
- [ ] `android-mobile-client-sync-guard`
- [ ] `automated-ci-pawncc-github`
- [ ] `automated-db-backup-cron`
- [ ] `backup-recovery-disaster-plan`
- [ ] `blueg-mysql-r41-threaded`
- [ ] `client-crash-opcode-lookup`
- [ ] `component-ci-testing`
- [ ] `crafting-blueprint-system`
- [ ] `custom-dff-txd-model-converter-pipeline`
- [ ] `custom-include-api-design`
- [ ] `custom-interior-shell-builder`
- [ ] `custom-speedometer-td`
- [ ] `custom-weapon-damage-config`
- [ ] `death-injury-knockdown-state`
- [ ] `discord-webhook-log-bridge`
- [ ] `docker-omp-mariadb-setup`
- [ ] `dynamic-faction-turf-war`
- [ ] `dynamic-object-material-text-signs`
- [ ] `dynamic-pagination-dialog`
- [ ] `dynamic-zone-area-triggers`
- [ ] `economy-inflation-analytics`
- [ ] `encoding-crlf-ansi-guard`
- [ ] `exterior-world-lod-drawdistance`
- [ ] `fcnpc-legacy-to-omp-port`
- [ ] `git-gamemode-workflow`
- [ ] `global-vs-player-td-budget`
- [ ] `housing-basebuilding-streamer`
- [ ] `include-dependency-resolver`
- [ ] `interior-exterior-portal-streaming`
- [ ] `inventory-weight-slot-engine`
- [ ] `k8s-omp-fleet`
- [ ] `legacy-to-openmp-migration`
- [ ] `linux-samp-omp-systemd`
- [ ] `live-hotfix-filterscript`
- [ ] `mapandreas-colandreas-raycast`
- [ ] `mapping-collision-colandreas-bake`
- [ ] `mission-quest-objective-tracker`
- [ ] `modular-map-file-parser-cfg-json`
- [ ] `multi-world-instance-sharding`
- [ ] `nicks-td-editor-export-refactor`
- [ ] `notification-toast-queue`
- [ ] `ntd-project-to-modular-include`
- [ ] `omp-ban-ip-cidr-management`

## Wave 3 (47 skill)

- [ ] `omp-built-in-npc-scripting`
- [ ] `omp-c-api-gdk`
- [ ] `omp-client-capability-detection`
- [ ] `omp-component-load-order`
- [ ] `omp-custom-models-setup`
- [ ] `omp-json-config-env-vars`
- [ ] `omp-legacy-plugin-bridge`
- [ ] `omp-mysql-component-setup`
- [ ] `omp-npc-pathfinding-combat`
- [ ] `omp-packet-encryption-launcher`
- [ ] `omp-pawn-component-sdk-cpp`
- [ ] `omp-postgresql-component`
- [ ] `omp-server-query-api`
- [ ] `omp-unicode-utf8-chat`
- [ ] `pawn-profiler-optimization`
- [ ] `pawn-raknet-packet-guard`
- [ ] `player-report-ticket-system`
- [ ] `progress-bar-hud-rendering`
- [ ] `raknet-packet-desync-debug`
- [ ] `redis-cross-server-cache`
- [ ] `release-changelog-generator`
- [ ] `runtime-error-4-bounds-check`
- [ ] `samp-map-editor-pipelines`
- [ ] `samp-model-selection-ui`
- [ ] `samp-third-party-anticheat-integration`
- [ ] `samp-voice-bridge`
- [ ] `sampctl-package-manager`
- [ ] `speedhack-vehicle-physics-check`
- [ ] `sql-injection-escape-audit`
- [ ] `sqlite-local-db-patterns`
- [ ] `stress-test-bot-simulation`
- [ ] `survival-vitals-hunger-infection`
- [ ] `tablist-headers-formatting`
- [ ] `textdraw-color-gradient-palettes`
- [ ] `textdraw-preview-model-3d-rigging`
- [ ] `textdraw-radial-wheel-menu`
- [ ] `textdraw-scrollbar-list-grid`
- [ ] `textdraw-txd-sprite-atlas-guide`
- [ ] `textdraw-zorder-layer-stacking`
- [ ] `texture-studio-export-optimizer`
- [ ] `ufw-ddos-raknet-mitigation`
- [ ] `weather-time-sync-system`
- [ ] `ysi-y-bit-bitarray-flags`
- [ ] `ysi-y-ini-legacy-storage`
- [ ] `ysi-y-inline-callbacks`
- [ ] `ysi-y-iterate-foreach`
- [ ] `ysi-y-va-variadic-args`
