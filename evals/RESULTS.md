# Results

## Harness self-test (bukan hasil agent)

Dijalankan untuk membuktikan grader bisa membedakan jawaban naif dan jawaban sesuai
skill. Kedua arm di sini adalah jawaban sintetis yang saya tulis tangan, bukan output
model, jadi angka ini **tidak boleh** dikutip sebagai efek skill.

| Case | Arm A (fixture apa adanya) | Arm B (pola sesuai skill) | Delta |
| --- | --- | --- | --- |
| nextjs-dynamic-layout | 1/4 grader, 17% | 4/4 grader, 100% | +83% |

Reproduksi:

```bash
python3 bin/eval.py score --case nextjs-dynamic-layout --dir /tmp/evals/without --compare /tmp/evals/with
```

## Hasil agent

Belum ada. Isi tabel ini setelah menjalankan protokol di `evals/README.md`, dan
sebutkan model, tanggal, jumlah run, serta path jawaban mentah.

| Tanggal | Case | Model | Tanpa skill | Dengan skill | Delta | Catatan |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |
