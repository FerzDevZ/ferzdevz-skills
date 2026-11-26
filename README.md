# ferzdevz-skills

Skill pack untuk Hermes Agent (dan agent lain yang mendukung format Agent Skills /
`SKILL.md`). Isinya keputusan teknis yang mahal kalau salah — bukan tutorial panjang.

Cakupan: web development, web design, UI/UX & accessibility, mobile development,
mobile design, machine learning & LLM, ops, SA-MP/open.mp game development, dan
meta-tooling untuk merawat pack ini.

## Status

- 165 skill terbit, 9 kategori: web-dev, web-design, ui-ux, mobile-dev, mobile-design, ml, samp, ops, meta.
- 134 skill SA-MP/open.mp sudah lulus kontrak penuh; `samp/_backlog/` kosong.
- Setiap skill wajib lulus gate struktur, kedalaman tabel kegagalan, sumber hidup, dan allowlist native.
- `CATALOG.md` dihasilkan otomatis; jangan diedit tangan.

## Struktur

```
web-dev/        Next.js, TypeScript, API, performa, auth, Postgres
web-design/     design token, warna, tipografi, API komponen
ui-ux/          riset, usability, form, empty state, WCAG 2.2
mobile-dev/     Flutter, React Native, Android/iOS release, offline sync
mobile-design/  HIG vs Material 3, navigasi, touch target, layout adaptif
ml/             framing, RAG, evaluasi, context engineering
samp/           SA-MP/open.mp: TextDraw, streamer, data, anticheat, build, kendaraan, YSI
  _backlog/     94 skill lama yang belum lolos gate (tidak di-install, tidak diaudit)
ops/            Docker, CI gate, supply chain
meta/           auditor pack, publish, depth upgrade, evals
```

Satu skill = satu folder:

```
<kategori>/<nama-skill>/
  SKILL.md        # wajib
  scripts/        # opsional, stdlib-only
  references/     # opsional
  assets/         # opsional
```

## Install ke Hermes

```bash
./bin/install.sh --dry-run      # lihat apa yang akan disalin
./bin/install.sh                # copy ke ~/.hermes/skills/<kategori>/
./bin/install.sh --dest /path   # profil lain
```

Script menjalankan audit dulu dan berhenti kalau ada skill yang gagal.

## Pakai di agent lain

Formatnya standar Agent Skills: satu folder berisi `SKILL.md`. Agent lain tidak butuh
`bin/`, cukup foldernya.

```bash
# Claude Code / Codex style skill directories
mkdir -p .claude/skills && cp -r web-dev/nextjs-app-router-production .claude/skills/
# atau
mkdir -p .agents/skills && cp -r ml/rag-evaluation-harness .agents/skills/
```

Kalau agent tersebut hanya membaca satu direktori skill, salin `<kategori>/<skill>/`
tanpa struktur kategori.

## Gate

```bash
python3 bin/audit.py --root .            # struktur, kedalaman, duplikat
python3 bin/audit.py --root . --net      # + cek semua URL sumber
python3 bin/catalog.py                   # regenerate CATALOG.md
python3 bin/catalog.py --check           # CI: gagal kalau katalog basi
python3 bin/eval.py lint                 # case eval valid (grader, regex, prompt)
python3 bin/route_audit.py               # tabrakan deskripsi + deskripsi terlalu generik
python3 bin/eval.py score --case nextjs-dynamic-layout --dir <jawaban> --compare <jawaban-lain>
bash bin/install.sh --dry-run
```

Aturan yang ditegakkan:

| Gate | Ambang |
| --- | --- |
| frontmatter | `name` == nama folder, `description` <= 60 karakter |
| section | When to Use, Compatibility, Implementation, Failure Modes, Verification, Sources |
| kedalaman | >= 60 baris isi (target 100-160) |
| tabel | Failure Modes >= 3 baris data, Compatibility berupa tabel |
| sumber | >= 2 URL, dan hidup saat `--net` |
| duplikat | kemiripan deskripsi > 0.86 ditolak |

## Menambah skill

1. `mkdir -p <kategori>/<nama> && cp TEMPLATE.md ...` lalu isi.
2. Isi 5 bagian, jangan ada TODO.
3. `python3 bin/audit.py --root . --only <kategori> --net`
4. `python3 bin/catalog.py`
5. Commit. CI menjalankan gate yang sama.

## Lisensi dan sumber

Isi skill ditulis ulang dari dokumentasi resmi; setiap skill mencantumkan sumber
yang benar-benar dibuka. URL sumber ikut diverifikasi di CI.
