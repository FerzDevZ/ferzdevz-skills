# Skill evals

Gate struktur membuktikan sebuah skill **ada**. Eval di sini membuktikan skill itu
**mengubah jawaban agent**. Satu case = satu prompt yang sama, dijalankan dua kali,
lalu dinilai grader yang deterministik (regex atas file hasil), bukan penilaian selera.

```
evals/<case>/
  prompt.md      prompt identik untuk kedua arm
  fixture/       file awal yang dicopy ke workdir sebelum agent mulai
  graders/*.md   satu cek per file (id, weight, path, must_match / must_not_match)
```

## Protokol dua arm

1. Buat dua workdir dari fixture yang sama:

```bash
mkdir -p /tmp/evals/without /tmp/evals/with
cp -r evals/nextjs-dynamic-layout/fixture/. /tmp/evals/without/
cp -r evals/nextjs-dynamic-layout/fixture/. /tmp/evals/with/
```

2. Jalankan agent yang sama pada prompt yang sama, dengan beda satu hal:

- arm `without`: skill terkait tidak terpasang (atau profil bersih).
- arm `with`: skill terpasang di `~/.hermes/skills/<kategori>/<nama>/`.

Prompt diambil apa adanya dari `prompt.md`; jangan dipersingkat di salah satu arm.

3. Nilai kedua direktori:

```bash
python3 bin/eval.py score --case nextjs-dynamic-layout \
  --dir /tmp/evals/without --compare /tmp/evals/with
```

4. Catat hasilnya di `RESULTS.md`: tanggal, model, dan delta. Satu run per arm bukan
bukti statistik; ulangi 3 kali kalau delta kecil, dan simpan jawaban mentahnya.

## Menulis grader yang jujur

- Satu grader = satu klaim yang bisa dibantah. "File memuat `Suspense`" bisa dibantah;
  "kode terlihat bagus" tidak.
- `must_not_match` lebih kuat daripada `must_match`: ia menangkap pola yang salah,
  bukan sekadar pola yang diinginkan.
- Bobot (`weight`) dipakai untuk hal yang fatal. Jangan menaikkan bobot untuk menutupi
  grader yang lemah.
- Jangan menilai prosa dengan panjang jawaban. Case `wcag22-audit` menilai nomor
  kriteria dan bukti `Expected`, bukan jumlah paragraf.

## Batasan

- Grader regex tidak memahami semantik: jawaban yang menyebut `Suspense` di komentar
  tetap lolos. Karena itu hasil eval dipakai untuk membandingkan dua arm, bukan
  sebagai sertifikat mutu.
- Eval ini tidak memanggil model sendiri. Ia menilai direktori jawaban yang Anda
  hasilkan, jadi bisa dijalankan di CI tanpa API key.
