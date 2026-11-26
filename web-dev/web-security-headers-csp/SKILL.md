---
name: web-security-headers-csp
description: Use when a CSP or HSTS header breaks the checkout.
version: "2026.1.0"
metadata:
  hermes:
    tags: [security, csp, hsts, headers, reporting]
    category: web-dev
---

# Enforce a strict CSP without white-screening checkout

A CSP fails in two directions: too loose to protect anything, or enforced one deploy
too early and the payment page dies. Both are fixed the same way — one header owner, a
nonce per response, and a report-only window that must empty before promotion.

## When to Use

- You are adding `Content-Security-Policy` to an app that still ships inline scripts, GTM or `dangerouslySetInnerHTML`.
- The policy has sat in `Report-Only` for months and nobody can say when enforcing it is safe.
- HSTS, `Referrer-Policy` or `Permissions-Policy` differ between the CDN and the app, or are missing.
- A security review wants evidence that violations are collected and triaged, not just blocked.
- Skip for a static site with no third-party JS — a hash-based policy needs no per-request nonce.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| CSP | Level 3 (`w3c.github.io/webappsec-csp`) | `'strict-dynamic'`, `report-to`, `frame-ancestors` are CSP3 only |
| `report-to` | Reporting API | Not broadly supported yet; MDN keeps `report-uri` in the same policy for that reason |
| HSTS | RFC 6797 | `preload` requires `max-age` >= 31536000 **and** `includeSubDomains` |
| `Permissions-Policy` | current MDN reference | `()` disables a feature, `(self)` allows the same origin |
| Next.js | 16.x middleware | The nonce must also be set on the **request** headers or the renderer cannot read it |
| Node.js | 22 / 24 LTS | `crypto.randomUUID()` and `createHash` are stdlib |

## Production Implementation

1. Put every header in one module so the CDN and the app cannot disagree. Count inline
   code first — `curl -s $HOST/checkout | grep -o '<script[^>]*>' | grep -vc 'src='` —
   because every hit beyond `0` needs a nonce or hash, while `onclick=` attributes never
   can be covered and must become `addEventListener`.

```ts
// lib/security-headers.ts
export function securityHeaders(nonce: string): Record<string, string> {
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https://cdn.example.com",
    "connect-src 'self' https://api.example.com",
    "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
    'upgrade-insecure-requests', 'report-uri /api/csp-report', 'report-to csp',
  ].join('; ');

  return {
    'Content-Security-Policy': csp,
    'Reporting-Endpoints': 'csp="/api/csp-report"',
    'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(self)',
    'X-Content-Type-Options': 'nosniff',
    'Cross-Origin-Opener-Policy': 'same-origin',
  };
}
```

The name in `report-to csp` must match the key in `Reporting-Endpoints`.
`style-src 'unsafe-inline'` is the deliberate compromise: CSS injection is a far smaller
problem than breaking every CSS-in-JS library on day one.

3. Mint the nonce per request and forward it to the renderer.

```ts
// middleware.ts
import { NextResponse, type NextRequest } from 'next/server';
import { securityHeaders } from './lib/security-headers';

export function middleware(req: NextRequest) {
  const nonce = crypto.randomUUID().replaceAll('-', '');
  const requestHeaders = new Headers(req.headers);
  requestHeaders.set('x-nonce', nonce);

  const res = NextResponse.next({ request: { headers: requestHeaders } });
  for (const [k, v] of Object.entries(securityHeaders(nonce))) res.headers.set(k, v);
  // A shared HTML cache would replay one nonce to every user.
  if (req.nextUrl.pathname.startsWith('/checkout')) res.headers.set('Cache-Control', 'private, no-store');
  return res;
}

export const config = { matcher: '/((?!_next/static|_next/image|favicon.ico).*)' };
```

4. Attach it in the layout: `const nonce = (await headers()).get('x-nonce')` then
   `<script nonce={nonce} src="/boot.js" />`. A tag rendered outside that tree needs the
   nonce passed as a prop.

5. Roll out in report-only, then promote on an empty report table. Reports arrive as
   `POST application/reports+json` — an array of entries with `type: "csp-violation"`
   and a `body` carrying `effectiveDirective`, `blockedURL`, `documentURL` and `sample`.
   Legacy `report-uri` sends one object under `csp-report`, so accept both.

```http
Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self' 'nonce-{RANDOM}' 'strict-dynamic'; report-uri /api/csp-report; report-to csp
Reporting-Endpoints: csp="/api/csp-report"
```

```ts
// app/api/csp-report/route.ts
export async function POST(req: Request) {
  const raw = await req.text();
  if (raw.length > 64_000) return new Response(null, { status: 413 });
  const parsed = JSON.parse(raw);
  for (const r of Array.isArray(parsed) ? parsed : [parsed['csp-report'] ?? parsed]) {
    const b = r.body ?? r;
    await db.cspViolation.insert({
      directive: b.effectiveDirective ?? b['effective-directive'],
      blocked: b.blockedURL ?? b['blocked-uri'],
      document: b.documentURL ?? b['document-uri'],
      sample: String(b.sample ?? '').slice(0, 200),
    });
  }
  return new Response(null, { status: 204 });
}
```

6. Decide promotion with a query. Rows still on `script-src-elem` with
   `blocked_uri = 'inline'` are script tags missing their nonce.

```sql
SELECT effective_directive, blocked_uri, count(*) AS hits
FROM csp_violation
WHERE created_at > now() - interval '7 days'
GROUP BY 1, 2 ORDER BY hits DESC LIMIT 20;
```

7. Ship HSTS in three steps — `max-age=300`, then `31536000`, then `includeSubDomains;
   preload` — because shortening it is not instant. Add `preload` only when every
   subdomain answers `301` to `https`.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `script-src-elem` violation with `blocked_uri: inline` after adding a nonce | The component rendering the tag never read `x-nonce` | Read `headers()` there or pass the nonce as a prop; a nonce set only on the response is invisible to the renderer |
| One nonce reused across users | HTML cached by the CDN while the policy is per-request | Send `Cache-Control: private, no-store` on documents carrying a nonce, or use hashes |
| Inline `onclick=` still blocked although the script has a nonce | Nonces cover `<script>` elements, not attributes | Move the handler to `addEventListener`; `script-src-attr` cannot use a per-request nonce usefully |
| Policy passes staging, breaks production ads | The allowlist was built from staging traffic only | Run report-only in production for a full week including paid traffic before enforcing |
| Two `Content-Security-Policy` headers on one response | CDN injects one, the app sets another | Browsers intersect them, so the effective policy is the stricter union — keep one owner |
| `includeSubDomains` locks out a tool still on HTTP | Preload was enabled before every subdomain had TLS | Test each subdomain first; removal needs a preload-list request and browser releases |

## Verification

- `curl -sI https://staging.example.com/checkout | grep -i -E 'content-security-policy|strict-transport-security|referrer-policy'` prints all three; the CSP contains `'nonce-` and no `'unsafe-inline'` inside `script-src`.
- Two requests must yield two different nonces; `1` means the document was cached.

```bash
for i in 1 2; do curl -sI https://staging.example.com/ | grep -io 'nonce-[a-f0-9]*'; done | sort -u | wc -l
```

Expected output: `2`. The same host over `http` must answer `301` with an `https://` `Location`.
- Paste the production header into `https://csp-evaluator.withgoogle.com/`; no high-severity `script-src` finding should remain.

## Sources (2026)

- https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy
