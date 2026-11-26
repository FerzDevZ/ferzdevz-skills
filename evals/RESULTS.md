# Results

Model untuk semua run di bawah: `deepseek-v4.1-flash` lewat Hermes CLI
(`hermes chat -q <prompt> --oneshot --in <workdir>`), satu run per arm. Tugas Pawn
dikompilasi dengan pawncc 3.10.x + open.mp stdlib.

## 1. Harness self-test (bukan hasil agent)

Membuktikan grader bisa membedakan jawaban naif dari jawaban berpola skill. Kedua arm
adalah jawaban sintetis yang saya tulis tangan, jadi angka ini **tidak** mengukur efek
skill.

| Case | Arm A (fixture apa adanya) | Arm B (pola sesuai skill) | Delta |
| --- | --- | --- | --- |
| nextjs-dynamic-layout | 1/4 grader, 17% | 4/4 grader, 100% | +83% |

## 2. Hasil agent: pengukuran bersih

| Tanggal | Case | Tanpa skill | Dengan skill | Delta | Catatan |
| --- | --- | --- | --- | --- | --- |
| 2026-11-26 | fake-kill-shield | 4/4, 100% | 4/4, 100% | 0% | Model dasar sudah memakai `OnPlayerTakeDamage`, cek kepemilikan senjata, `return 0`, dan menyebut trust boundary RPC |

**Bacaan jujur:** pada case yang pengukurannya bersih, skill tidak menambah skor. Itu
bukan bukti skill tidak berguna, tapi bukti dua hal:

1. Case ini menguji pengetahuan yang model sudah punya, jadi tidak bisa membedakan arm.
   Case harus menguji hal non-obvious (ambang pool 2048/256, nomor kriteria WCAG,
   protokol eval RAG), bukan pola anti-cheat umum.
2. Nilai skill pada model kuat lebih ke konsistensi dan bukti (perintah verifikasi,
   tabel kegagalan), bukan kemampuan menebak jawaban.

## 3. Run yang dibuang (kontaminasi profil)

| Case | Angka mentah | Alasan dibuang |
| --- | --- | --- |
| nextjs-dynamic-layout | with 50% dan 17% (dua run), without 67% | Profil masih memuat 134 skill lama di `samp-legacy/` dengan nama identik, jadi arm "with" bisa memuat versi lama dan arm "without" tidak bersih |
| textdraw-pool-budget | with 33%, without 33% | Kontaminasi yang sama; kedua arm juga tidak menulis `budget.md` sehingga dua grader tidak pernah bisa lulus |

Setelah itu `samp-legacy` dipindah keluar dari `~/.hermes/skills` (sekarang di
`~/samp-legacy-backup`), sehingga 232 skill tersisa tanpa nama kembar.

## 4. Yang memperbaiki case ini

- `nextjs-dynamic-layout`: prompt melarang route handler + client fetch, dan path grader
  memakai glob (`app/**/cart-badge.tsx`) karena agent memilih nama file sendiri.
- `fake-kill-shield`: grader `notes-trust-boundary` menerima penjelasan di header
  `kill-fixed.pwn`, bukan hanya `notes.md` yang sering tidak ditulis.
- `textdraw-pool-budget`: grader budget menerima file `*.md` apa pun, bukan hanya
  `budget.md`.

## 5. Cara mengulang

```bash
python3 bin/eval.py score --case fake-kill-shield \
  --dir /tmp/evals/without --compare /tmp/evals/with
```

Untuk arm "without", keluarkan skill terkait dari profil selama run, dan pastikan tidak
ada salinan bernama sama di direktori skill lain — kontaminasi itulah yang membuang dua
run pertama di atas.
