# Rencana Induk: ferzdevz-skills

Pack skill untuk Hermes Agent (dan agent lain yang paham spec Agent Skills / SKILL.md).
Cakupan: web development, web design, UI/UX, mobile development, mobile design,
machine learning, plus ops dan meta-tooling.

Dokumen ini adalah kontrak. Skill yang tidak memenuhi gate di bagian 6 tidak masuk pack.

---

## 1. Prinsip yang dipakai

1. Satu skill = satu keputusan teknis yang mahal kalau salah. Bukan satu library, bukan satu folder.
2. Progresif: `description` (<= 60 char) adalah pemicu; isi lengkap baru dibaca saat relevan.
3. Setiap skill wajib punya perintah yang bisa dijalankan dan tabel `failure -> cause -> fix`.
4. Sumber harus benar-benar dibuka penulis skill, dan diverifikasi ulang oleh `bin/audit.py --net`.
5. Tidak ada skill duplikat. Kemiripan judul/isi > 0.86 ditolak auditor.
6. Depth minimum 60 baris isi; kode contoh harus compile/run atau jelas ditandai pseudo.

---

## 2. Peta domain (target 71 skill)

### web-dev (11)
| Skill | Inti |
| --- | --- |
| nextjs-app-router-production | Boundary Server/Client Component, caching, streaming, checklist produksi |
| typescript-strict-project-setup | tsconfig strict, project references, path alias, resolusi modul |
| api-contract-first-openapi | OpenAPI sebagai kontrak, codegen client, validasi runtime |
| react-server-state-data-fetching | Cache key, staleTime, optimistic update, error boundary |
| web-performance-core-vitals | Budget LCP/INP/CLS, RUM vs lab, perbaikan per penyebab |
| auth-session-cookie-hardening | httpOnly/SameSite/CSRF, rotasi refresh, OAuth PKCE |
| postgres-query-and-index-tuning | EXPLAIN, index komposit, N+1, connection pool |
| background-jobs-and-queues | Idempotency key, retry backoff, transactional outbox |
| e2e-testing-playwright | Fixture, isolasi data, flake control, sharding CI |
| seo-technical-foundations | Metadata, sitemap, structured data, i18n hreflang |
| node-service-structure | Layering, DI, error taxonomy, graceful shutdown |

### web-design (8)
| Skill | Inti |
| --- | --- |
| design-tokens-dtcg-pipeline | DTCG JSON -> Style Dictionary -> CSS/Tailwind/iOS/Android |
| color-system-accessible-palette | OKLCH, kontras APCA/WCAG, dark mode, state color |
| typography-scale-web | Modular scale, variable font, fallback metric, clamp() |
| layout-grid-and-spacing-scale | Skala 4/8pt, grid 12 kolom, fluid spacing |
| component-api-design | Varian vs prop, slot/composition, forwardRef, kontrol a11y |
| motion-and-microinteraction | Durasi/easing, reduced-motion, animasi yang tidak bikin CLS |
| responsive-breakpoints-container-queries | Breakpoint berbasis isi, bukan device |
| landing-page-conversion-structure | Hero, proof, CTA hierarchy, above-the-fold budget |

### ui-ux (9)
| Skill | Inti |
| --- | --- |
| ux-research-interview-guide | Script wawancara, JTBD, sintesis jadi keputusan |
| usability-testing-moderated | Task, metrik, think-aloud, SUS, laporan temuan |
| information-architecture-card-sorting | Struktur navigasi dari data, bukan selera |
| forms-ux-validation-patterns | Validasi inline, copy error, urutan field, autofill |
| accessibility-wcag22-audit | Kriteria AA 2.2, alat, jebakan ARIA |
| design-handoff-spec | Token, state matrix, redline, QA desain-ke-kode |
| onboarding-first-run-experience | Time-to-value, empty state, progressive disclosure |
| empty-states-and-error-ux | Empty/loading/error/partial sebagai state kelas satu |
| design-review-rubric | Rubrik review desain dengan skor dan bukti |

### mobile-dev (8)
| Skill | Inti |
| --- | --- |
| flutter-project-architecture | Feature-first, state management, flavor, golden test |
| react-native-new-architecture | Fabric/TurboModules, Hermes, jalur upgrade |
| kotlin-multiplatform-shared-logic | Layout modul KMP, expect/actual, boundary |
| android-release-hardening | R8, signing, baseline profile, kebijakan Play |
| ios-release-hardening | Signing, TestFlight, jebakan review App Store |
| mobile-offline-sync-queue | Local DB, queue, resolusi konflik, idempotensi |
| push-notifications-fcm-apns | Token lifecycle, topic, deep link, kegagalan senyap |
| mobile-ci-fastlane-github-actions | Build matrix, cache, signing di CI |

### mobile-design (6)
| Skill | Inti |
| --- | --- |
| ios-hig-vs-material3 | Pemetaan konvensi platform, bukan satu desain untuk dua OS |
| mobile-navigation-patterns | Tab/stack/sheet, deep link, restore state |
| touch-targets-and-thumb-zones | 44/48pt, zona jempol, gesture conflict |
| mobile-typography-and-density | Dynamic type, skala, line-height di layar kecil |
| adaptive-layouts-foldables-tablets | Window size class, dual pane, fold posture |
| mobile-motion-and-haptics | Transisi, haptic, reduced motion |

### ml (10)
| Skill | Inti |
| --- | --- |
| ml-problem-framing-baseline | Rules of ML, metrik produk vs model, baseline heuristik |
| feature-store-training-serving-skew | Definisi fitur tunggal, point-in-time join, deteksi skew |
| model-evaluation-offline-online | Leakage, split waktu, metrik offline vs A/B |
| experiment-tracking-mlflow | Run, artefak, registry, reproduksibilitas |
| llm-app-context-engineering | Struktur prompt, output terstruktur, tool use, evaluasi |
| rag-retrieval-pipeline | Chunking, hybrid search, rerank, sitasi, akses |
| rag-evaluation-harness | Golden set, faithfulness, regresi, biaya eval |
| fine-tuning-vs-prompting-decision | Kapan fine-tune benar-benar menang |
| inference-cost-latency-budget | Batching, caching, kuantisasi, SLO latency |
| model-monitoring-drift | Data drift, performa, alert, rollback model |

### ops (6)
| Skill | Inti |
| --- | --- |
| docker-image-hardening | Multi-stage, non-root, digest pin, scan |
| ci-pipeline-gates | Lint/type/test/security sebagai gate yang tak bisa dilewati |
| observability-logs-metrics-traces | RED/USE, korelasi trace-log, sampling |
| secrets-and-env-management | Rotasi, scope, no-secret-in-repo, CI OIDC |
| dependency-supply-chain-security | Lockfile, SBOM, audit, pinning |
| incident-runbook-and-postmortem | Runbook, severity, timeline, aksi yang dicek |

### meta (4)
| Skill | Inti |
| --- | --- |
| skill-library-auditor | Audit pack: stub, duplikat, sumber mati, gate |
| skill-pack-publish | Ekspor ke repo git + CI + install.sh |
| skill-depth-upgrade | Naikkan stub jadi skill penuh tanpa mengarang |
| skill-selection-evals | Buktikan skill benar-benar mengubah output agent |

Total: 11 + 8 + 9 + 8 + 6 + 10 + 6 + 4 = 62. Target akhir 62 skill berkualitas, bukan 200 stub.

---

## 3. Gelombang pengerjaan

| Gelombang | Isi | Alasan urutan |
| --- | --- | --- |
| W0 | meta/ (4) + tooling + CI | Tanpa auditor, pack membusuk seperti library lama |
| W1 | web-dev + web-design inti (6) | Paling sering dipakai, paling mahal kalau salah |
| W2 | ui-ux + a11y (5) | Menentukan kualitas W1 |
| W3 | mobile-dev + mobile-design (8) | Paralel, dependensi rendah |
| W4 | ml (6 inti) | Butuh cerita eval yang matang dulu |
| W5 | ops (6) + sisa ml | Menutup jalur produksi |
| W6 | sisa semua domain | Pengayaan, bukan fondasi |

Aturan: satu gelombang selesai = `bin/audit.py` hijau + `bin/catalog.py` di-commit.

---

## 4. Anatomi satu skill

```
<kategori>/<nama-skill>/
  SKILL.md            # wajib
  scripts/            # opsional, stdlib-only, harus runnable
  references/         # opsional, dimuat on-demand
  assets/             # opsional, template
```

Urutan section wajib (lihat TEMPLATE.md):

1. `# Judul`
2. `## When to Use` - 3-5 pemicu konkret
3. `## Compatibility & Stack Matrix (2026)` - versi, platform, tabel dukungan
4. `## Production Implementation` - langkah bernomor + perintah + kode
5. `## Failure Modes & Fixes` - tabel gejala -> sebab -> perbaikan
6. `## Verification` - perintah/cek yang membuktikan hasil
7. `## Sources (2026)` - >= 2 URL yang benar-benar dibuka

---

## 5. Standar isi

- Perintah shell harus copy-paste-able, tanpa placeholder yang tidak dijelaskan.
- Kode harus minimal bisa di-parse; kalau tidak bisa dijalankan, beri label `pseudo`.
- Angka harus punya ambang jelas (contoh: INP < 200 ms p75, bukan "cepat").
- Versi library disebut eksplisit (contoh: Next.js 15/16, RN 0.7x, Flutter 3.3x).
- Larangan: "best practice" tanpa alasan, daftar tautan tanpa isi, klaim benchmark tanpa sumber.

---

## 6. Gate penerimaan

| Gate | Alat | Gagal jika |
| --- | --- | --- |
| Struktur | `bin/audit.py` | frontmatter kurang, nama != folder, section wajib hilang |
| Kedalaman | `bin/audit.py --min-body 60` | isi < 60 baris, tidak ada tabel kegagalan |
| Sumber | `bin/audit.py --net` | < 2 URL, atau URL 404/410 |
| Duplikat | `bin/audit.py` | kemiripan judul/deskripsi > 0.86 |
| Katalog | `bin/catalog.py --check` | CATALOG.md tidak sinkron |
| CI | `.github/workflows/validate.yml` | salah satu di atas gagal di PR |

---

## 7. Sumber rujukan yang dipakai untuk menyusun pack

- Agent Skills spec: https://agentskills.io/home
- Microsoft Agent Framework skills (progressive disclosure): https://learn.microsoft.com/en-us/agent-framework/agents/skills
- Next.js production checklist: https://nextjs.org/docs/app/guides/production-checklist
- Style Dictionary design tokens: https://styledictionary.com/info/tokens/
- WCAG 2.2 Quick Reference: https://www.w3.org/WAI/WCAG22/quickref/
- web.dev INP: https://web.dev/articles/inp
- Chrome Modern Web Guidance 1.0: https://developer.chrome.com/blog/modern-web-guidance-v1
- React Native New Architecture: https://reactnative.dev/architecture/landing-page
- Google Rules of ML: https://developers.google.com/machine-learning/guides/rules-of-ml
- Anthropic prompt engineering: https://claude.com/resources/articles/best-practices-for-prompt-engineering
- Kubernetes production readiness: https://learnkube.com/production-best-practices
- MLflow MLOps pipeline practices: https://mlflow.org/articles/mlops-pipeline-automation-best-practices-in-2026/

---

## 8. Cara pakai pack ini

```bash
git clone <repo> ~/ferzdevz-skills
~/ferzdevz-skills/bin/audit.py --root ~/ferzdevz-skills
~/ferzdevz-skills/bin/install.sh            # copy ke ~/.hermes/skills/<kategori>/
```

Setelah install, skill muncul di indeks Hermes dan dipilih lewat `description`.
