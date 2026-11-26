# ferzdevz-skills

Skill pack untuk Hermes Agent (dan agent lain yang mendukung format Agent Skills /
`SKILL.md`). Isinya keputusan teknis yang mahal kalau salah — bukan tutorial panjang.

Cakupan: web development, web design, UI/UX & accessibility, mobile development,
mobile design, machine learning & LLM, ops, productivity, SA-MP/open.mp game
development, SA-MP client C++, dan meta-tooling untuk merawat pack ini.

## Status

- 183 skill terbit, 11 kategori: web-dev, web-design, ui-ux, mobile-dev, mobile-design, ml, ops, productivity, samp, samp-client, meta.
- 134 skill SA-MP/open.mp ada di `samp/`; 3 skill klien C++ ada di `samp-client/`.
- Setiap skill wajib lulus gate struktur, kedalaman tabel kegagalan, sumber hidup, dan allowlist native.
- `CATALOG.md` dihasilkan otomatis; jangan diedit tangan.

## Struktur

```
web-dev/        Next.js, TypeScript, API, performa, auth, Postgres
web-design/     design token, warna, tipografi, API komponen
ui-ux/          aksesibilitas, form, state kosong/error, usability test
mobile-dev/     Android, Flutter, React Native, offline sync
mobile-design/  navigasi, tap target, layout adaptif, HIG vs M3
ml/             framing, RAG, evaluasi, prompt injection, context LLM app
ops/            CI, kontainer, observability, feature flag, Kafka, k6, dbt
productivity/   PRD & scope cut
samp/           open.mp/Pawn: auth, database, sync, anticheat, streamer, YSI
samp-client/    klien SA-MP C++: RPC handler, object lifecycle, menu RPC
meta/           audit library, router, eval, depth upgrade
bin/            audit, catalog, doctor, eval, export, install, routing check
evals/          case evaluasi skill dan routing
.github/        CI gate
```

## Pakai dengan Hermes

```bash
git clone https://github.com/ferzdevz/ferzdevz-skills.git ~/ferzdevz-skills
~/ferzdevz-skills/bin/install.sh --backup   # salin ke ~/.hermes/skills + backup
# restart Hermes agar indeks skill dimuat ulang
```

`install.sh` menjalankan audit dulu dan berhenti kalau ada skill yang gagal gate.

## Pakai dengan agent lain (Agent Skills / SKILL.md)

Format skill di pack ini mengikuti konvensi Agent Skills: satu folder per skill,
file `SKILL.md` dengan frontmatter `name` + `description`.

```bash
# Claude Code (project-local)
mkdir -p .claude/skills
cp -r ~/ferzdevz-skills/web-dev/* .claude/skills/

# Atau symlink satu kategori
ln -s ~/ferzdevz-skills/samp .claude/skills/samp
```

Untuk agent yang hanya membaca satu direktori datar, salin isi kategori, bukan
folder kategori itu sendiri (setiap skill harus menjadi anak langsung dari
direktori skills agent).

## Cek kualitas

```bash
python3 bin/audit.py --root .            # struktur + kedalaman
python3 bin/audit.py --root . --net      # + cek URL sumber hidup
python3 bin/check_natives.py --root .    # native SA-MP/open.mp sesuai allowlist
python3 bin/catalog.py --check           # CATALOG.md masih segar
python3 bin/route_audit.py --fail-on-dupes
python3 bin/doctor.py --profile . --repo .
python3 bin/eval.py lint                 # case evaluasi valid
```

Semua perintah di atas juga dijalankan di GitHub Actions (`.github/workflows/validate.yml`).

## Kontrak skill

Setiap `*/SKILL.md` wajib punya frontmatter YAML dan bagian berikut:

| Gate | Aturan |
| --- | --- |
| frontmatter | `name` == nama folder, `description` <= 60 karakter |
| section | When to Use, Compatibility/Stack, Implementation, Failure Modes, Verification, Sources |
| kedalaman | >= 60 baris isi (target 100-160) |
| tabel | Failure Modes >= 3 baris data, Compatibility berupa tabel |
| sumber | >= 2 URL, dan hidup saat `--net` |
| duplikat | kemiripan deskripsi > 0.86 ditolak |

## Menambah skill

1. `mkdir -p <kategori>/<nama> && cp TEMPLATE.md <kategori>/<nama>/SKILL.md` lalu isi.
2. Isi semua bagian wajib, jangan ada TODO.
3. `python3 bin/audit.py --root . --only <kategori> --net`
4. `python3 bin/catalog.py`
5. Commit. CI menjalankan gate yang sama.

## Lisensi dan sumber

Isi skill ditulis ulang dari dokumentasi resmi; setiap skill mencantumkan sumber
yang benar-benar dibuka. URL sumber ikut diverifikasi di CI.
