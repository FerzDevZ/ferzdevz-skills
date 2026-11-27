---
name: auth-session-cookie-hardening
description: Use when tab switch logs out or CSRF tokens expire.
version: "2026.1.0"
metadata:
  hermes:
    tags: [auth, cookies, sessions, oauth, csrf, security]
    category: web-dev
---

# Harden cookie sessions before an audit finds them

Most session bugs are one attribute away from a breach: no `HttpOnly`, a `__Host-`
cookie dropped because `Domain` was set, or a state cookie stripped by `SameSite=Strict`.

## When to Use

- Login state lives in a cookie and the attributes were copied from a blog post.
- The app uses OAuth/OIDC without PKCE, or sessions survive logout and password change.
- A review found CSRF, session fixation, or refresh tokens without rotation.
- Skip when a managed identity provider owns the session and you only verify its JWTs.

## Compatibility & Stack Matrix (2026)

| Component | Version / spec | Notes |
| --- | --- | --- |
| Cookies | RFC 6265bis behavior | `__Host-` requires `Secure`, `Path=/`, and no `Domain` |
| SameSite | Lax is the browser default | `None` requires `Secure`; `Strict` breaks OAuth returns |
| OAuth BCP | RFC 9700 (January 2025) | PKCE for all clients; rotate or sender-constrain public-client refresh tokens |
| Session store | PostgreSQL 16-19 or Redis | Store only a hash of the token, revoke server-side |

## Production Implementation

1. Issue an opaque token and persist only its hash.

```ts
import { createHash, randomBytes } from 'node:crypto'

export function issueToken() {
  const token = randomBytes(32).toString('base64url') // 256 bits, 43 chars
  const id = createHash('sha256').update(token).digest()
  return { token, id }
}
```

2. Set the cookie with the strictest prefix that still fits the deployment.

```ts
export function sessionCookie(token: string, maxAgeSeconds: number) {
  return [
    `__Host-sid=${token}`,
    'Path=/',
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
    `Max-Age=${maxAgeSeconds}`,
  ].join('; ')
}
```

`__Host-` forbids `Domain` and requires `Path=/`; add a `Domain` and the browser drops
the cookie silently. `SameSite=Lax` still carries the session on top-level navigation.

3. Model sessions with idle expiry, absolute expiry and a rotation family.

```sql
create table sessions (
  id                  bytea primary key,
  user_id             bigint not null references users(id) on delete cascade,
  family_id           uuid not null,
  created_at          timestamptz not null default now(),
  last_seen_at        timestamptz not null default now(),
  idle_expires_at     timestamptz not null,
  absolute_expires_at timestamptz not null,
  revoked_at          timestamptz,
  ip_hash             bytea,
  user_agent_hash     bytea
);
create index sessions_user_active_idx on sessions (user_id, last_seen_at desc)
  where revoked_at is null;
create index sessions_expiry_idx on sessions (idle_expires_at)
  where revoked_at is null;
```

4. Validate and rotate in one transaction; treat a replayed rotated token as theft.

```sql
create or replace function rotate_session(old_id bytea, new_id bytea) returns void language plpgsql as $$
declare s sessions;
begin
  select * into s from sessions where id = old_id for update;
  if s.revoked_at is not null then  -- replayed token: kill the whole family
    update sessions set revoked_at = now() where family_id = s.family_id and revoked_at is null;
    return;
  end if;
  insert into sessions (id, user_id, family_id, idle_expires_at, absolute_expires_at)
  values (new_id, s.user_id, s.family_id, now() + interval '30 minutes', s.absolute_expires_at);
  update sessions set revoked_at = now() where id = old_id;
end $$;
```

5. Reject cross-site mutations explicitly; SameSite alone is not a CSRF strategy.

```ts
export function rejectCrossSite(req: Request): Response | null {
  if (req.headers.get('sec-fetch-site') !== 'same-origin') {
    return new Response('cross-site request blocked', { status: 403 })
  }
  if (req.headers.get('origin') !== process.env.PUBLIC_ORIGIN) {
    return new Response('bad origin', { status: 403 })
  }
  return null
}
```

Every state change is a POST; a GET handler that mutates is a CSRF hole regardless of
cookie attributes.

6. Run OAuth with PKCE S256, `state`, and an exact redirect URI.

```ts
import { createHash, randomBytes } from 'node:crypto'

const verifier = randomBytes(32).toString('base64url')
const challenge = createHash('sha256').update(verifier).digest('base64url')
const state = randomBytes(16).toString('base64url')

const authorize = new URL('https://idp.example.com/authorize')
authorize.search = new URLSearchParams({
  response_type: 'code',
  client_id: process.env.CLIENT_ID!,
  redirect_uri: process.env.REDIRECT_URI!,
  scope: 'openid profile email',
  state,
  code_challenge: challenge,
  code_challenge_method: 'S256',
}).toString()
```

Store `state` and `verifier` in a 10-minute `HttpOnly` cookie with `SameSite=Lax`.
`Strict` would omit the cookie when the provider redirects back cross-site, and the
callback then fails state validation for every user.

7. Rotate refresh tokens and detect replay. RFC 9700 requires public clients to
   sender-constrain refresh tokens or rotate them; rotation without reuse detection
   only limits the damage window, it does not close it.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| OAuth callback always fails `state` validation | State/verifier cookie set with `SameSite=Strict` | Use `SameSite=Lax`, `Path=/`, and a 10-minute `Max-Age` for that cookie |
| `__Host-sid` never appears in DevTools | Cookie carries `Domain` or a non-root `Path` | Remove `Domain`, set `Path=/`, keep `Secure` |
| Users are logged out at random | Token rotated on every request while tabs race | Rotate on login and refresh only; allow a short grace for the previous token |
| Session survives logout or password change | Only the browser cookie is cleared | Delete or revoke rows server-side, then expire the cookie with `Max-Age=0` |
| CSRF still reproduces with `SameSite=Lax` | State-changing GET, or an attacker on a sibling subdomain | POST-only mutations plus `Origin`/`Sec-Fetch-Site` checks |
| Stolen refresh token works indefinitely | No rotation and no reuse detection | Rotate per use; revoke the family when a revoked token is presented |

## Verification

- `curl -sI https://app.example.com/login | grep -i '^set-cookie'` shows `__Host-sid=`, `Path=/`, `HttpOnly`, `Secure`, `SameSite=Lax`, and no `Domain`.
- Replay an old cookie after a refresh: the request returns `401`, and `select count(*) from sessions where family_id = '<uuid>' and revoked_at is null` returns `0`.

## Sources (2026)

- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://www.rfc-editor.org/rfc/rfc9700.html
