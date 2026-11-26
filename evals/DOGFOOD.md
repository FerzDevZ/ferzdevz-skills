# Dogfood: apakah pack membantu di repo nyata

Repo uji: `/home/aegisx/samp-client-ferzdevz` (klien SA-MP Android, C++/JNI).
Tugas: gejala yang sudah tercatat di repo — object dari server dilacak tetapi tidak pernah
digambar, dan menu SA-MP tidak muncul.

Tanggal: 2026-05 (diperbarui setelah v1.7.0/v1.8.0 menambah kategori `samp-client`).

## Sinyal tugas

- "server objects are tracked but not drawn" / "CObject tidak dibuat entity-nya"
- "SA-MP menu tidak muncul" / "InitMenu/ShowMenu/HideMenu belum diregistrasi"
- "bagaimana urutan RPC handler di klien C++"
- "kenapa object RPC diterima tapi tidak ada yang tampil di dunia"

## Yang dipakai

| Artefak | Peran | Terpakai? |
| --- | --- | --- |
| `samp-client/samp-client-object-entity-lifecycle` | siklus hidup entity CObject, urutan create/attach/material | ya |
| `samp-client/samp-client-menu-rpc-handling` | registrasi RPC menu, lifecycle Show/Hide/Init | ya |
| `samp-client/samp-client-rpc-handler-registry` | pola registrasi handler RPC, tabel ID/nama | ya |
| skill `samp/*` (server-side Pawn) | pengetahuan server; tidak menjawab gejala client | sebagian (konteks) |

## Temuan

**Gap yang dulu ada (sebelum v1.7.0) tertutup.** Sebelum rilis ini, pack berisi 134 skill
SA-MP sisi server (Pawn) dan hampir tidak punya panduan sisi klien C++. Routing ke topik
client mengembalikan skill server (mis. streaming, raknet filter) yang benar secara domain
tetapi tidak menjawab "di mana entity dibuat di klien Android".

Sejak v1.7.0/v1.8.0, kategori `samp-client/` ditambahkan dengan 3 skill berbasis kode
nyata klien (`samp-client-ferzdevz`):

1. **`samp-client-object-entity-lifecycle`** — menjawab gejala "tracked but not drawn":
   mencakup urutan `CModelInfo::GetModelInfo` → `RequestModel` → `LoadAllRequestedModels`
   → `SetModelIndex`, perbedaan objek statis/dinamis, dan cleanup saat slot dipakai ulang.
2. **`samp-client-menu-rpc-handling`** — menjawab gejala menu tidak muncul: registrasi
   `InitMenu`/`ShowMenu`/`HideMenu`, state di `CMenuPool`, dan verifikasi RPC ID.
3. **`samp-client-rpc-handler-registry`** — panduan menambah handler RPC baru tanpa
   tabrakan ID/nama, dipakai sebagai fondasi dua skill di atas.

## Apa yang masih belum ter-cover (jujur)

- Pack ini tidak bisa memverifikasi patch di perangkat Android nyata; verifikasi runtime
  tetap dilakukan oleh pemilik repo di ponselnya sendiri.
- Gejala client di luar tiga topik di atas (mis. voice, custom models 0.3.DL, crash
  triage libGame yang lebih dalam) masih butuh skill tambahan atau investigasi langsung.
- Skill samp-client ditulis dari satu codebase referensi; klien SA-MP lain (PC, fork lain)
  bisa punya struktur berbeda — cek sumber yang dicantumkan di tiap skill.

## Kesimpulan

Dogfood awal mengidentifikasi celah nyata (tidak ada skill client-side). Celah itu sudah
ditutup oleh 3 skill `samp-client/*` yang lolos gate dan dipakai pada investigasi yang sama.
Skill-server tetap relevan untuk konteks protokol, tapi bukan jawaban langsung untuk gejala
render/RPC di klien.
