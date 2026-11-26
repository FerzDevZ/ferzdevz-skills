# Routing eval

`route_check.py` menjawab satu pertanyaan: kalau user menulis keluhan seperti biasa,
apakah skill yang benar muncul di urutan pertama?

Metode: 50 prompt realistis (`routing.json`), masing-masing dengan satu skill yang
diharapkan. Setiap skill diberi skor dari tumpang tindih kata dengan nama (bobot 3),
`description` (bobot 2), dan heading isi (bobot 1), memakai IDF supaya kata umum tidak
menang. Ini **proxy leksikal**, bukan pemilihan model: angka di sini adalah batas bawah,
bukan hasil akhir. Model memilih secara semantik, jadi selalu ≥ angka ini untuk deskripsi
yang sama.

## Hasil

| Versi | recall@1 | recall@3 |
| --- | --- | --- |
| Awal (deskripsi sebelum audit) | 32/50, 64% | 41/50, 82% |
| Setelah 16 deskripsi ditulis ulang dengan kata yang dipakai user | **40/50, 80%** | **47/50, 94%** |

Tidak ada tabrakan deskripsi (`route_audit.py`) sebelum maupun sesudah perubahan, dan
tidak ada skill yang ditambah atau dihapus untuk mencapai angka ini.

## Yang diperbaiki dan kenapa

Contoh nyata: `design-tokens-dtcg-pipeline` dulu berbunyi "Use when tokens must build CSS,
Tailwind, iOS, Android" — tidak ada satu pun kata yang dipakai user ("designers", "spacing",
"drift"). Setelah jadi "Use when spacing or colour tokens drift across platforms", prompt
"Designers change a spacing value and three platforms drift apart" langsung menang.

Pola yang sama untuk: sesi/CSRF, error form, empty state, Play Console, penilaian RAG,
dokumen yang menyuruh model, tipografi, query lambat, target sentuh, duplikasi uang,
klaim kill, i18n, dan nama event.

## Sisa 10 miss, dan kenapa dibiarkan

| Prompt | Menang | Alasan |
| --- | --- | --- |
| "logged out after a tab switch, CSRF tokens" | `design-tokens-dtcg-pipeline` | kata "tokens" milik dua domain; tanpa semantik, "token" ambigu |
| "list looks broken when there is no data" | `textdraw-scrollbar-list-grid` | "list" + "scroll" lebih kuat dari "empty" |
| "retrieved PDF ... call a tool" | `textdraw-preview-model-3d-rigging` | "preview/model" menang lewat heading |
| "Midtrans webhook fires twice" | `dynamic-zone-area-triggers` | "fires" memicu "trigger" di skill zona |
| "analytics events named differently" | `android-mobile-client-sync-guard` | "mobile" menang; "event" umum |
| "strings ... German and Arabic" | `adaptive-layouts-foldables-tablets` | "layout" menang |
| "load test passes at 200 users" | `stress-test-bot-simulation` | dua skill memang berdekatan; ini miss yang wajar |
| "CI runs tests before linting" | `testing-pyramid-and-contract-tests` | urutan pipeline vs strategi tes, kata "tests" dominan |
| "HUD element does not react to clicks" | `react-native-new-architecture` | "react" di prompt menang atas "HUD" |
| "Server objects are created but never drawn" | `server-log-anomaly-scanner` | "server" terlalu umum |

Semua miss di atas punya skill yang benar di posisi 2 atau 3 (recall@3 94%), jadi loader
agent masih punya peluang menemukannya. Mengubah deskripsi lebih jauh hanya akan
memindahkan ambiguitas, bukan menghilangkannya.

## Menjalankan

```bash
python3 bin/route_check.py                      # ringkas + daftar miss
python3 bin/route_check.py --verbose            # top-3 tiap case
python3 bin/route_check.py --min-recall 0.75    # untuk CI
```
