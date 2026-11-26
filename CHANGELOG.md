# Changelog

Format: satu bagian per tag rilis, dikutip dari workflow `release`.
Skill bertambah = versi minor; perbaikan gate/teks = patch.

## v1.7.0

- Kategori baru `samp-client` (lapisan klien C++), dua skill dari kode nyata
  `samp-client-ferzdevz`:
  - `samp-client-object-entity-lifecycle`: `TryLoadModel` -> `ScriptCommand(create_object)`
    -> `GamePool_Object_GetAt` -> `SetPosn`/`Add`, plus urutan destroy dan 16 slot material.
  - `samp-client-menu-rpc-handling`: RPC 76/77/78, urutan wire `ScrInitMenu` yang sebenarnya
    (id, twoColumns, title, pos, widths, menuEnabled, 12 bit rowEnabled, header, counts,
    blob), batas `MAX_MENUS`/`MAX_MENU_ROWS`/`MENU_TEXT_LEN`, dan `TakeSelection()`.
- Routing eval naik ke 52 case (81% recall@1) dan mencakup gejala klien.
- Catatan: dua fakta di skill ini awalnya salah tulis (urutan wire dan tipe `rowEnabled`);
  keduanya dikoreksi setelah membaca `net/scriptrpc.cpp`, bukan dari ingatan.

## v1.6.0

- `bin/route_check.py` + `evals/routing.json`: 50 prompt nyata, recall@1 64% -> **80%**,
  recall@3 82% -> **94%** setelah 16 deskripsi ditulis ulang dengan kata yang dipakai user.
  CI menjalankan `--min-recall 0.75`.
- `evals/ROUTING.md`: metode, tabel hasil, dan 10 miss yang dibiarkan beserta alasannya.
- `bin/usage_report.py`: skill mana yang benar-benar dimuat, dibaca dari `state.db`
  (30 hari terakhir: 30 lookup, 7 skill pack, 173 belum pernah).
- `evals/DOGFOOD.md`: uji di `samp-client-ferzdevz`. Temuan: pack tidak punya skill untuk
  lapisan render klien C++ (`CObjectPool`/`m_pEntity`), jadi gejala "objek server tidak
  digambar" tidak bisa dijawab pack ini. Skill pengganti diusulkan, belum dibuat.

## v1.5.0

- 180 skill, 10 kategori. Tambah: `testing-pyramid-and-contract-tests`,
  `appsec-threat-model-asvs`, `load-testing-k6-budget`, `warehouse-modeling-dbt`,
  `prd-and-scope-cut`.
- `evals/*/prompt.md` mewajibkan file ditulis sebelum penjelasan; run tanpa file hilang
  (sebelumnya 3 dari 8), dan `money-concurrency` kini mengukur dua arm yang sama-sama
  menghasilkan file (100% vs 100%).
- Cron bulanan `ferzdevz-skills monthly gate` (tanggal 1, 09:00 WIB) menjalankan seluruh
  gate dan hanya commit kalau hijau.

## v1.4.0

- `bin/export_pack.py`: ekspor tree datar (`dist/skills/<name>/`) + zip
  `ferzdevz-skills-<versi>.zip` + `SHA256SUMS`, untuk agent yang hanya membaca satu
  direktori skill.
- Workflow rilis mengunggah zip dan checksum sebagai aset rilis.
- `LICENSE` (MIT) dan `CHANGELOG.md` ditambahkan; `doctor.py` kini mengenali layout datar.
- `bin/doctor.py` dipanggil otomatis setelah `install.sh` (tidak menimpa kegagalan install).

## v1.3.0

- `bin/doctor.py`: cek pohon skill bersarang, nama duplikat, skill pack yang belum terpasang,
  direktori tanpa `SKILL.md`, dan `name:` yang tidak cocok dengan folder.
- `bin/eval_arm.sh`: arm eval berjalan di HOME sementara; profil asli tidak dipindahkan lagi.
- `bin/install.sh`: tolak tujuan di dalam pack atau tujuan yang sudah punya `skills/` bersarang;
  tambah `--backup`.
- `evals/RESULTS.md`: catat sebaran run (3 dari 8 run tidak menulis file) dan tooling yang
  lahir dari dua insiden profil.

## v1.2.0

- 175 skill (9 kategori): tambah CSP/security headers, API versioning, i18n, payments
  idempotency, analytics taxonomy, Kafka consumers, feature flags, observability, prompt
  injection defense.
- `bin/check_claims.py`: bandingkan klaim versi di skill dengan npm, PyPI, GitHub, Docker Hub.
- Case eval `money-concurrency` + eksperimen tiga arm (0% tanpa skill, 100% dengan skill
  tetangga, 78% pack penuh).
- Workflow `release.yml`: rilis GitHub dibuat dari tag, setelah gate hijau.

## v1.1.0

- `meta/skill-router`: tabel gejala -> skill untuk seluruh pack.
- `bin/route_audit.py`: deteksi tabrakan deskripsi dan deskripsi generik.
- `evals/`: 6 case, `bin/eval.py` (skor dua arm), hasil tercatat.
- 166 skill; README punya jalur pakai di agent lain (`.claude/skills`, `.agents/skills`).

## v1.0.0

- 165 skill: web-dev, web-design, ui-ux, mobile-dev, mobile-design, ml, ops, meta, samp.
- Gate: `audit.py` (struktur, kedalaman, duplikat, sumber), `catalog.py`, `install.sh`.
- CI `validate.yml` menjalankan gate yang sama dengan lokal.
