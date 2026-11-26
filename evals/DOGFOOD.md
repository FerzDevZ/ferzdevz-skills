# Dogfood: apakah pack membantu di repo nyata

Repo uji: `/home/aegisx/samp-client-ferzdevz` (klien SA-MP Android, C++/JNI).
Tugas: gejala yang sudah tercatat di repo — object dari server dilacak tetapi tidak pernah
digambar.

## Apa yang dilakukan pack

1. `bin/route_check.py` dipakai dengan prompt "Server objects are created but never drawn
   for players". Skill yang diharapkan: `dynamic-object-map-loader`.
2. Hasil: pemilihan meleset, dan yang lebih penting, `dynamic-object-map-loader` tidak
   muncul di top-3 (yang menang: `server-log-anomaly-scanner`, `omp-server-query-api`,
   `server-cfg-to-config-json`).
3. Pencarian korpus: **nol** skill menyebut `CObjectPool`, `m_pEntity`, atau `CEntityGTA`.

## Apa yang ada di repo

- `client/app/src/main/cpp/samp/net/objectpool.{h,cpp}` — `CObjectPool` dengan
  `New/Delete/Process`, `GetAt`, dan `m_pObjects[id]->m_pEntity`.
- Jadi lapisan yang bermasalah adalah pembuatan entity engine di klien (C++), bukan RPC
  server dan bukan sisi Android/Java.

## Putusan

Pack ini punya 134 skill SA-MP untuk sisi **server** (Pawn) dan beberapa untuk sisi
**aplikasi Android**, tetapi tidak punya satu pun untuk lapisan **render klien C++** —
tepat area tempat repo ini bekerja. Prompt di atas bukan salah tulis; pack-nya memang tidak
punya jawaban. Itu temuan yang berguna: satu-satunya domain tempat dogfood ini gagal adalah
domain yang paling sering Anda kerjakan.

Karena itu saya tidak memaksakan skill yang ada (mis. `dynamic-object-map-loader`, yang
mengatur streamer di server) untuk menjawab masalah klien: jawaban yang dihasilkan akan
terdengar benar dan salah sasaran.

## Skill yang perlu dibuat (belum dibuat)

`samp-client-object-rendering`, kategori baru `samp-client`. Isi minimal:

1. Jalur pembuatan entity: dari `CObjectPool::New` ke entity engine, urutan streaming
   model (`CStreaming::RequestModel` → `LoadAllRequestedModels` → `SetModelIndex`), dan
   kenapa urutan itu penting.
2. Perbedaan objek statis vs dinamis (material, draw distance, parent).
3. Siklus hidup: hapus entity sebelum slot dipakai ulang, jangan hanya `delete`.
4. Verifikasi yang bisa dijalankan: log satu baris per objek (`id`, model, entity pointer,
   jarak), plus cek bahwa jumlah entity di pool game naik setelah `New`.
5. Tabel kegagalan: objek tak terlihat, crash saat `SetModelIndex`, model hilang setelah
   `RemoveBuildingForPlayer`, entity yatim setelah reconnect.

Kriteria lulus: skill ini harus bisa menjawab gejala di atas tanpa menyebut streamer
server, dan harus menyebut satu perintah/log yang membuktikan entity benar-benar dibuat.

## Catatan metode

Dogfood ini statis: membaca kode dan korpus, bukan menjalankan build Android (butuh
`libGame.so` + emulator/perangkat). Itu cukup untuk pertanyaan "apakah pack punya
jawaban?", bukan untuk pertanyaan "apakah patch-nya bekerja".
