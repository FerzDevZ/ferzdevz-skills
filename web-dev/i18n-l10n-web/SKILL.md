---
name: i18n-l10n-web
description: Use when strings, plurals or RTL break in another locale.
version: "2026.1.0"
metadata:
  hermes:
    tags: [i18n, l10n, icu, rtl, intl]
    category: web-dev
---

# Treat every visible sentence as one translatable unit

Localisation breaks at the seams, not in the dictionary. A sentence assembled from
`"You have " + n + " items"` cannot be reordered, `toFixed(2)` is wrong in Jakarta and
Tokyo, and a layout built on `margin-left` mirrors into nonsense.

## When to Use

- UI code concatenates fragments, or interpolates a number into a sentence by hand.
- Counts render "1 items", or plurals are wrong in Polish, Russian or Arabic.
- You are adding `ar`, `he` or `fa` and the layout must mirror without a second stylesheet.
- Prices, dates or file sizes are formatted with `toFixed`, template strings or a hard-coded pattern.
- Skip when the product ships one locale with no roadmap for a second — ICU is overhead there.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| ICU MessageFormat | 1.x (`{arg, plural, ...}`) | `plural` and `select` are the supported complex arguments; `choice` is discouraged |
| `Intl.PluralRules` | Baseline | Returns `zero`, `one`, `two`, `few`, `many`, `other`; English uses 2 forms, Arabic 6 |
| `Intl.NumberFormat` | Baseline | Currency style derives the minor unit per currency (JPY has none) |
| Next.js | 16.x App Router | `app/[lang]`, `hasLocale()`, `notFound()`, `generateStaticParams()` |

## Production Implementation

1. One catalog per locale, one key per message, ICU syntax in the value.

```json
{
  "cart.summary": "{count, plural, =0 {Your cart is empty} one {# item in your cart} other {# items in your cart}}",
  "order.status": "{status, select, shipped {Shipped on {date}} cancelled {Cancelled} other {Processing}}",
  "checkout.total": "Total: {amount}"
}
```

The value is a whole sentence with placeholders. Never split it into `"Total:"` plus a
value in the component: German puts the colon differently and the translator never sees
the pair.

2. Load catalogs through one typed function, keyed by the source locale.

```ts
// lib/i18n.ts
import { IntlMessageFormat } from 'intl-messageformat';
import en from '@/messages/en.json';

export type MessageKey = keyof typeof en;

export function t(locale: string, key: MessageKey, values: Record<string, string | number> = {}) {
  const pattern = catalogs[locale]?.[key] ?? en[key];
  if (pattern === undefined) throw new Error(`missing message: ${key}`);
  return new IntlMessageFormat(pattern, locale).format(values) as string;
}
```

`IntlMessageFormat` applies the locale's own plural rules, so `{count, plural, one … other
…}` stays correct in Russian, where the same count selects `few` or `many`.

3. Format every number, date and currency through `Intl`, never through arithmetic.

```ts
// lib/format.ts
export const money = (locale: string, currency: string, minor: number) =>
  new Intl.NumberFormat(locale, { style: 'currency', currency }).format(minor / 100);

export const day = (locale: string, iso: string) =>
  new Intl.DateTimeFormat(locale, { dateStyle: 'long', timeZone: 'UTC' }).format(new Date(iso));
```

`ja-JP` with `JPY` returns `￥123,457` — no decimals, because yen has no minor unit —
while `de-DE` with `EUR` returns `123.456,79 €`. Dividing by 100 only works for
two-decimal currencies; read the exponent from `resolvedOptions()` for the rest.

4. Mirror the document, then mirror the CSS — in that order.

```tsx
// app/[lang]/layout.tsx
const RTL = new Set(['ar', 'he', 'fa', 'ur']);

export default async function LangLayout({ children, params }: LayoutProps<'/[lang]'>) {
  const { lang } = await params;
  return <html lang={lang} dir={RTL.has(lang) ? 'rtl' : 'ltr'}><body>{children}</body></html>;
}
```

Logical properties mirror on their own; `margin-left` and `left` do not. Leave
user-generated text on `dir="auto"` so a Hebrew name on an English page still reads
correctly, wrap phone numbers and code in `dir="ltr"` spans, and size the layout for
German, which runs roughly a third longer than English.

5. Route by locale in the path and resolve the locale on the server.

```ts
// proxy.ts — send / and unknown prefixes to a supported locale
const LOCALES = ['en', 'id', 'ar', 'ja'];
export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const first = req.headers.get('accept-language')?.split(',')[0]?.split('-')[0] ?? 'en';
  if (new RegExp(`^/(${LOCALES.join('|')})(/|$)`).test(pathname)) return NextResponse.next();
  return NextResponse.redirect(new URL(`/${LOCALES.includes(first) ? first : 'en'}${pathname}`, req.url));
}
```

The page narrows `params.lang` with `hasLocale()` and calls `notFound()` otherwise, so
`/xx` 404s instead of rendering English; `generateStaticParams()` lists the four locales.

6. Gate the catalog in CI: same keys everywhere, valid ICU, no orphans.

```ts
// scripts/check-locales.ts
import { readFileSync, readdirSync } from 'node:fs';
import { parse } from '@formatjs/icu-messageformat-parser';

const files = readdirSync('messages').filter((f) => f.endsWith('.json'));
const load = (f: string) => JSON.parse(readFileSync(`messages/${f}`, 'utf8')) as Record<string, string>;
const reference = new Set(Object.keys(load('en.json')));
let failed = false;

for (const file of files) {
  const catalog = load(file);
  for (const key of reference) if (!(key in catalog)) { console.error(`${file} missing ${key}`); failed = true; }
  for (const key of Object.keys(catalog)) if (!reference.has(key)) { console.error(`${file} orphan ${key}`); failed = true; }
  for (const [key, value] of Object.entries(catalog)) {
    try { parse(value); } catch (e) { console.error(`${file} ${key}: ${(e as Error).message}`); failed = true; }
  }
}
process.exit(failed ? 1 : 0);
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| "1 items" on the cart page | Plural handled with `count === 1 ? a : b` | Use an ICU `plural` argument; a ternary only covers two-form languages |
| Correct in English, wrong case ending in Polish | The sentence was assembled from translated fragments | Translate the whole sentence as one key with placeholders |
| Prices show `1234.50` everywhere | `toFixed(2)` instead of a formatter | `Intl.NumberFormat(locale, { style: 'currency', currency })` |
| Hydration mismatch on a date | Server formatted in UTC, client in the browser locale | Format on the server and pass the string, or give both sides an explicit `locale` and `timeZone` |
| Arabic mirrors the text but not the buttons | `margin-left` / `left` in the stylesheet | `margin-inline-start`, `inset-inline-start`, `text-align: start` |
| Unknown locale renders the English page at `/xx` | The route accepts any segment | Narrow with `hasLocale()` and call `notFound()` |
| Page weight jumps after adding locales | The whole catalog is imported into a client component | Load catalogs in Server Components and pass rendered strings down |

## Verification

- `npx tsx scripts/check-locales.ts` exits `0` with equal key counts per locale; an unbalanced brace must print `en <key>: ...` and exit `1`.
- Confirm the plural forms the runtime actually has. `en` must print only `one`/`other`, `ru` must mix `one few many`, `ar` must reach `zero`/`two`, `ja` only `other`:

```bash
node -e "for (const l of ['en','ru','ar','ja']) console.log(l, [0,1,2,5,11].map(n => new Intl.PluralRules(l).select(n)).join(' '))"
```

- `curl -s https://example.com/ar/ | grep -o 'dir="rtl"'` prints `dir="rtl"` (`/en/` prints nothing), and `curl -s https://example.com/ja/ | grep -c '￥'` returns at least `1` when a price is on the page.

## Sources (2026)

- https://unicode-org.github.io/icu/userguide/format_parse/messages/
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/PluralRules
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat
- https://nextjs.org/docs/app/guides/internationalization
