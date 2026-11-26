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

## 5. Eksperimen tiga arm (money-concurrency, 2026-11-26)

Satu case, tiga kondisi, satu run per kondisi, model sama:

| Arm | Skor | Catatan |
| --- | --- | --- |
| Direktori skill dikosongkan total | 0/5, 0% | `transfer-fixed.pwn` tidak pernah dibuat; agent hanya menulis `verify/schema.sql` |
| Hanya skill tetangga (skill `transaction-rollback-economy` disembunyikan) | 5/5, 100% | `money-duplication-prevention` dan skill ekonomi lain menutupi peran skill yang dihapus |
| Pack penuh | 4/5, 78% | Gagal satu grader: tidak memakai `FOR UPDATE`, lock-nya lewat urutan `UPDATE` bertingkat |

**Bacaan:** efek yang terukur ada di level "ada skill vs tidak ada skill", bukan
"satu skill vs tetangganya". Pada pack padat, ablasi satu skill tidak bermakna karena
skill lain di kategori yang sama memuat panduan yang sama. Karena itu:

- Jangan mengklaim satu skill menyelamatkan sesuatu hanya dari uji satu-skill.
- Untuk mengukur nilai pack, bandingkan direktori skill kosong vs terisi (arm 1 vs 3).
- Skor pack penuh yang lebih rendah dari tetangga murni menunjukkan jawabannya panjang
  dan menyimpang dari satu pola wajib; grader `FOR UPDATE` sebaiknya menerima urutan
  lock eksplisit sebagai alternatif.

## 6. Cara mengulang

```bash
python3 bin/eval.py score --case fake-kill-shield \
  --dir /tmp/evals/without --compare /tmp/evals/with
```

Untuk arm "without", keluarkan skill terkait dari profil selama run, dan pastikan tidak
ada salinan bernama sama di direktori skill lain — kontaminasi itulah yang membuang dua
run pertama di atas.
