# TEMPLATE SKILL

Salin folder ini, ganti nama, lalu isi. Auditor menolak apa pun yang belum lengkap.

```markdown
---
name: nama-skill-sama-dengan-folder
description: Use when <pemicu konkret>. <aksi singkat>.   # <= 60 karakter total
version: "2026.1.0"
metadata:
  hermes:
    tags: [domain, topik]
    category: web-dev
---

# Judul yang menjelaskan keputusan, bukan topik

## When to Use

- Gejala/pemicu konkret #1.
- Gejala/pemicu konkret #2.
- Jangan pakai skill ini kalau <kondisi lain>.

## Compatibility & Stack Matrix (2026)

| Komponen | Versi/varian | Catatan |
| --- | --- | --- |
| framework | 15.x / 16.x | fitur X hanya di 16 |
| runtime | Node 22 LTS | |

## Production Implementation

1. Langkah pertama, dengan perintah yang bisa dijalankan.

```bash
npm ci
npx tsc --noEmit
```

2. Langkah kedua, dengan kode.

```ts
// kode nyata, bukan placeholder
export const revalidate = 60;
```

3. Langkah verifikasi manual yang tersisa.

## Failure Modes & Fixes

| Gejala | Sebab | Perbaikan |
| --- | --- | --- |
| build gagal `X is not a function` | impor client-only di server component | pindahkan ke file `"use client"` |

## Verification

- Perintah: `...` -> output yang diharapkan.
- Cek manual: ...

## Sources (2026)

- https://... (dibuka saat menulis skill ini)
- https://...
```

## Aturan penulisan

1. `description` adalah satu-satunya bagian yang selalu dibaca agent. Tulis pemicunya, bukan ringkasan.
2. Setiap klaim teknis harus bisa dilacak ke bagian Sources atau ke perintah di Verification.
3. Tabel Failure Modes minimal 3 baris, dan barisnya harus berasal dari kegagalan nyata.
4. Kode: bahasa eksplisit di fence, tanpa `...` yang menyembunyikan bagian penting.
5. Panjang isi 80-180 baris. Di bawah 60 ditolak auditor, di atas 220 dipecah jadi dua skill.
6. Bahasa: Inggris untuk isi teknis (portabel), nama file dan folder lowercase-hyphen.
