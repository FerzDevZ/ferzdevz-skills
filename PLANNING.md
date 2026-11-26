# Rencana Induk: ferzdevz-skills

Pack skill untuk Hermes Agent (dan agent lain yang paham spec Agent Skills / `SKILL.md`).
Cakupan: web development, web design, UI/UX, mobile development, mobile design,
machine learning, ops, productivity, SA-MP/open.mp game development, SA-MP client C++,
plus meta-tooling.

Dokumen ini adalah kontrak. Skill yang tidak memenuhi gate di bagian 5 tidak masuk pack.

---

## 1. Prinsip

1. Satu skill = satu keputusan teknis yang mahal kalau salah. Bukan satu library, bukan satu folder.
2. Progresif: `description` (<= 60 char) adalah pemicu; isi lengkap baru dibaca saat relevan.
3. Setiap skill wajib punya perintah yang bisa dijalankan dan tabel `symptom -> cause -> fix`.
4. Sumber harus benar-benar dibuka penulis skill, dan diverifikasi ulang oleh `bin/audit.py --net`.
5. Tidak ada skill duplikat. Kemiripan deskripsi > 0.86 ditolak auditor.
6. Depth minimum 60 baris isi; target 100-160. Kode contoh harus runnable atau jelas ditandai pseudo.

---

## 2. State saat ini

| Kategori | Jumlah skill | Cakupan |
| --- | ---: | --- |
| web-dev | 12 | Next.js, TypeScript, API, auth, Postgres, performa, testing, security |
| web-design | 4 | token, warna, tipografi, API komponen |
| ui-ux | 4 | a11y, form, empty/error state, usability test |
| mobile-dev | 4 | Android, Flutter, React Native, offline sync |
| mobile-design | 4 | navigasi, tap target, layout adaptif, HIG vs M3 |
| ml | 5 | framing, RAG, eval, prompt injection, context LLM app |
| ops | 8 | CI, kontainer, observability, flag, Kafka, k6, dbt, supply chain |
| productivity | 1 | PRD & scope cut |
| samp | 134 | open.mp/Pawn: gameplay, DB, sync, anticheat, streamer, YSI, mapping, tooling |
| samp-client | 3 | klien SA-MP C++: RPC handler, object lifecycle, menu RPC |
| meta | 4 | audit library, router, eval, depth upgrade |
| **Total** | **183** | |

Distribusi ini dijaga oleh `bin/catalog.py` (output: `CATALOG.md`) dan divalidasi
oleh `bin/audit.py`, `bin/route_audit.py`, `bin/doctor.py`.

---

## 3. Kontrak skill

Setiap skill adalah folder `<kategori>/<nama>/SKILL.md`:

```yaml
---
name: nama-sama-dengan-folder
description: Use when <pemicu>. <aksi>.   # <= 60 char, trigger bukan ringkasan
version: "2026.1.0"
metadata:
  hermes:
    tags: [tag1, tag2]
    category: web-dev
---
```

Bagian wajib (urutan tetap): `When to Use`, `Compatibility`/stack matrix (tabel),
`Implementation`/langkah konkret, `Failure Modes` (tabel >= 3 baris data),
`Verification` (perintah atau cek nyata), `Sources (2026)` (>= 2 URL hidup).

---

## 4. Tooling

| Tool | Fungsi | Dipakai di CI |
| --- | --- | --- |
| `bin/audit.py` | struktur, kedalaman, duplikat, sumber (`--net`) | ya |
| `bin/check_natives.py` | native SA-MP/open.mp sesuai allowlist | ya |
| `bin/catalog.py` | generate/cek `CATALOG.md` | ya (`--check`) |
| `bin/route_audit.py` | tabrakan/generik deskripsi routing | ya |
| `bin/route_check.py` | floor recall routing | ya |
| `bin/eval.py` | lint/jalankan case evaluasi | ya (lint) |
| `bin/check_claims.py` | klaim versi vs registry | ya |
| `bin/doctor.py` | konsistensi profile vs repo | ya |
| `bin/export_pack.py` | export flat + zip | ya |
| `bin/install.sh` | install ke profile Hermes | ya (dry-run) |
| `bin/usage_report.py` | laporan pemakaian skill | manual |

---

## 5. Gate penerimaan

| Gate | Yang dicek | Lulus |
| --- | --- | --- |
| frontmatter | name == folder, description <= 60 char, versi/metadata ada | wajib |
| section | semua bagian wajib hadir | wajib |
| kedalaman | >= 60 baris isi, target 100-160 | wajib |
| tabel | Failure Modes >= 3 baris data; Compatibility tabel | wajib |
| sumber | >= 2 URL, hidup saat `--net` | wajib |
| duplikat | kemiripan deskripsi > 0.86 ditolak | wajib |
| native allowlist | API SA-MP/open.mp yang dipakai terdaftar | wajib (samp) |
| routing | tidak ada deskripsi duplikat/generik | wajib |
| catalog | `CATALOG.md` segar | wajib |

---

## 6. Menambah skill baru

1. `mkdir -p <kategori>/<nama> && cp TEMPLATE.md <kategori>/<nama>/SKILL.md`
2. Isi semua bagian wajib, jangan ada TODO.
3. `python3 bin/audit.py --root . --only <kategori> --names <nama> --net`
4. `python3 bin/catalog.py`
5. Commit; pastikan `validate.yml` hijau.

## 7. Cara pakai

```bash
git clone https://github.com/ferzdevz/ferzdevz-skills.git ~/ferzdevz-skills
~/ferzdevz-skills/bin/install.sh --backup
# restart Hermes agar indeks skill dimuat ulang
```

Setelah install, skill muncul di indeks Hermes dan dipilih lewat `description`.
