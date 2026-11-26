# Changelog

Format: satu bagian per tag rilis, dikutip dari workflow `release`.
Skill bertambah = versi minor; perbaikan gate/teks = patch.

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
