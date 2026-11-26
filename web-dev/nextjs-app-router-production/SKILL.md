---
name: nextjs-app-router-production
description: Use when Next.js App Router pages are slow or stale.
version: "2026.1.0"
metadata:
  hermes:
    tags: [nextjs, app-router, caching, streaming, react]
    category: web-dev
---

# Ship App Router pages that cache on purpose and stream early

App Router failures are boundary mistakes: a hook leaks into a Server Component, a
`cookies()` call makes the route dynamic, or a mutation never invalidates its tag.

## When to Use

- A route flips to dynamic after someone adds `cookies()`, `headers()` or reads `searchParams`.
- Users still see stale prices or inventory after a successful mutation.
- Client JavaScript grew after a layout received `"use client"`; p75 LCP is above 2.5s on a data-heavy route.
- Skip for Pages Router apps: `use cache`, `cacheLife` and `cacheTag` do not exist there.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| Next.js | 16.4.x (current) | Cache Components on in new apps; `use cache` stabilized in 16.0 |
| Next.js | 15.x | `unstable_cache` / fetch cache model; no `cacheComponents` flag |
| React | 19.3.x | Required by Next 16; Server Components are the default |
| Node.js | 22 LTS or 24 LTS | Node 20 reached end-of-life in April 2026 |

## Production Implementation

1. Pin the runtime and turn on the cache model explicitly.

```bash
npm i next@16.4.6 react@19.3.1 react-dom@19.3.1
```

```ts
// next.config.ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
}

export default nextConfig
```

2. Keep the page a Server Component; push `"use client"` to the interactive leaf.

```tsx
// app/products/[id]/page.tsx — no directive, runs on the server
import { AddToCart } from './add-to-cart'
import { getProduct } from '@/lib/catalog'

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const product = await getProduct(id)
  return (
    <main>
      <h1>{product.name}</h1>
      <AddToCart id={product.id} priceCents={product.priceCents} />
    </main>
  )
}
```

```tsx
'use client'
import { useState } from 'react'

export function AddToCart({ id, priceCents }: { id: string; priceCents: number }) {
  const [added, setAdded] = useState(false)
  return <button onClick={() => setAdded(true)} disabled={added}>{added ? 'Added' : `Add ${id} for ${priceCents / 100} USD`}</button>
}
```

3. Give every cached read a lifetime and a tag; never rely on the implicit default.

```ts
// lib/catalog.ts
import { cacheLife, cacheTag } from 'next/cache'

export async function getProduct(id: string) {
  'use cache'
  cacheLife('hours')
  cacheTag(`product-${id}`, 'products')
  const res = await fetch(`${process.env.CATALOG_URL}/products/${id}`)
  if (!res.ok) throw new Error(`catalog responded ${res.status}`)
  return (await res.json()) as { id: string; name: string; priceCents: number }
}
```

4. Invalidate at the mutation: `updateTag` for read-your-own-writes, `revalidateTag` elsewhere.

```ts
// app/actions.ts
'use server'
import { updateTag } from 'next/cache'
import { db } from '@/lib/db'

export async function renameProduct(id: string, name: string) {
  await db.product.update({ where: { id }, data: { name } })
  updateTag(`product-${id}`)
  updateTag('products')
}
```

Route Handlers use `revalidateTag('products', 'max')` to serve stale data while
revalidating; `updateTag` is legal only in a Server Action and blocks the next read.

5. Stream request-time reads inside Suspense so the static shell ships first.

```tsx
// app/components/cart-badge.tsx
import { Suspense } from 'react'
import { cookies } from 'next/headers'
import { countItems } from '@/lib/cart'

async function CartCount() {
  const session = (await cookies()).get('sid')?.value
  return <span>{session ? await countItems(session) : 0} items</span>
}

export function CartBadge() {
  return <Suspense fallback={<span>0 items</span>}><CartCount /></Suspense>
}
```

Read cookies outside a `use cache` scope and pass the value as an argument: captured
arguments join the cache key, keeping one user's data out of another user's entry.

6. Measure the LCP/INP impact on the real route before and after.

```bash
npx lighthouse http://localhost:3000/products/1 --preset=desktop --only-categories=performance \
  --output=json --output-path=./lh-after.json --chrome-flags="--headless=new"
node -e "const r=require('./lh-after.json'); console.log('LCP ms', r.audits['largest-contentful-paint'].numericValue, 'TBT ms', r.audits['total-blocking-time'].numericValue)"
```

Lab numbers only prove the route can be fast. The number that counts is field p75
LCP/INP over 28 days after deploy, compared separately for mobile and desktop.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Build error: `You're importing a component that needs useState` | A client hook reached a Server Component graph | Move the hook into a leaf file with `"use client"`; pass data as props |
| Every route prints as dynamic after adding a header | `cookies()` or `headers()` read in the root layout | Read them in a Suspense-wrapped leaf; keep the layout static |
| Edited record still stale on the next visit | Cache entry has no tag, or the action only calls `revalidatePath('/')` | Tag the read with `cacheTag` and call `updateTag` for that tag in the action |
| `"use cache" cannot be used on a synchronous function` | Directive placed on a sync helper | Make the function `async` and await the data source |
| Client bundle doubles after a refactor | `"use client"` sits at page or layout level | Keep the page server-only; import interactive leaves individually |
| One user sees another user's cached data | Session read inside a `use cache` scope | Read cookies outside the scope and pass `userId` as an argument |
| GET route handler returns stale JSON | With Cache Components, GET handlers prerender like pages | Call `revalidateTag(tag, 'max')`, or read request data to make it dynamic |

## Verification

- `npx next build` exits 0 and the route table lists each path with its intended mode.
- `npx tsc --noEmit` prints nothing and exits 0.
- `curl -s -o /tmp/p.html -w '%{http_code}\n' http://localhost:3000/products/1` returns `200`, and `grep -c USD /tmp/p.html` returns at least `1`.

## Sources (2026)

- https://nextjs.org/docs/app/getting-started/server-and-client-components
- https://nextjs.org/docs/app/api-reference/directives/use-cache
- https://nextjs.org/docs/app/api-reference/functions/revalidateTag
