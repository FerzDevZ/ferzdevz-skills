---
name: typescript-strict-project-setup
description: Use when a TS repo needs a strict, fast type gate.
version: "2026.1.0"
metadata:
  hermes:
    tags: [typescript, tsconfig, project-references, ci, monorepo]
    category: web-dev
---

# Make strict TypeScript a CI gate, not a style preference

A repo is only as strict as its weakest tsconfig. This setup turns on the flags that
catch runtime bugs, splits the build into referenced projects, and gates CI on the same command developers run locally.

## When to Use

- Loose TypeScript lets `any` and unchecked array access reach production.
- One giant `tsc` run takes minutes and every package re-checks on each edit.
- CI passes on a stale build while the editor reports cross-package type errors.
- You want type-aware lint rules without the compiler upgrade breaking ESLint.
- Skip for a single-file script: `"strict": true` is the whole job there.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| TypeScript | 7.0.x (current) | Native compiler, 8-12x faster full builds; 7.0 ships no programmatic API |
| TypeScript | 6.0.x | Compiler API host for typescript-eslint, Vue, Astro and Svelte tooling |
| Node.js | 22 LTS or 24 LTS | Use `module` and `moduleResolution` = `nodenext` |
| Bundled apps | Next.js 16, Vite 7 | `module: preserve` + `moduleResolution: bundler` |
| ESLint | 9.x flat config | Pair with `typescript-eslint` 8.74.x |
| CI | GitHub Actions | Cache `**/*.tsbuildinfo`, never `node_modules` |

## Production Implementation

1. Install the compiler lane that matches your tooling.

```bash
npm i -D typescript@7.0.2 @types/node@24
```

If ESLint uses type information, keep the 6.0 API visible to it with npm aliases.
`npx tsc` then runs the native 7.0 binary while `typescript-eslint` imports 6.0.

```json
{
  "devDependencies": {
    "@typescript/native": "npm:typescript@^7.0.2",
    "typescript": "npm:@typescript/typescript6@^6.0.2"
  }
}
```

2. Write one base config with the flags that catch runtime bugs.

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "lib": ["ES2023"],
    "module": "nodenext",
    "moduleResolution": "nodenext",
    "types": ["node"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "skipLibCheck": true
  }
}
```

`verbatimModuleSyntax` plus `nodenext` requires `"type": "module"` in the nearest
`package.json`; without it, every ESM export fails with TS1287 or TS1295.
`noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` are the two flags that
change code shape, so budget a migration pass for them.

3. Make every shared package a composite project that emits declarations.

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "composite": true,
    "declaration": true,
    "declarationMap": true,
    "rootDir": "src",
    "outDir": "dist",
    "tsBuildInfoFile": "dist/.tsbuildinfo"
  },
  "include": ["src"]
}
```

4. Add a solution tsconfig and build only through `tsc -b`.

```json
{
  "files": [],
  "references": [
    { "path": "packages/core" },
    { "path": "packages/ui" },
    { "path": "apps/web" }
  ]
}
```

```bash
npx tsc -b --verbose
```

`tsc -b` orders the graph, skips up-to-date projects, and treats errors as fatal for
downstream builds. `tsc -p` on one project does none of that and produces TS6305 as
soon as a dependency has not been built.

5. Add path aliases for editor ergonomics, then mirror them in the bundler.

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

`paths` only changes type resolution. Next.js reads it automatically; Vite needs
`vite-tsconfig-paths`; plain Node needs `imports` in `package.json` or a runtime
resolver. A missing runtime mirror shows up as `ERR_MODULE_NOT_FOUND` in production.

6. Put the exact local commands in CI.

```yaml
- run: npm ci
- run: npx tsc -b --pretty false
- run: npx eslint . --max-warnings=0
```

Pin TypeScript exactly. A caret range lets CI and laptops resolve different compilers,
which is how a green pipeline ships code that fails on the next install.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `TS6305: Output file ... has not been built from source file` | Ran `tsc -p` on a project whose reference was never built | Build with `tsc -b` from the solution config; never typecheck a leaf alone |
| `TS1287` / `TS1295` on every export under `verbatimModuleSyntax` | `package.json` has no `"type": "module"` while `module` is `nodenext` | Add `"type": "module"`, or switch module settings for that package |
| `Cannot find name 'console'` or `'process'` | `lib` excludes DOM and `types` omits Node | Add `@types/node` and `"types": ["node"]` |
| `TS2375` when spreading optional props | `exactOptionalPropertyTypes` rejects `{ retries: undefined }` for `retries?: number` | Declare `retries?: number \| undefined`, or omit the key |
| Enabling `noUncheckedIndexedAccess` creates hundreds of errors | Flag applied repo-wide on day one | Enable it in library packages first, fix call sites, then promote to apps |
| ESLint throws after the compiler upgrade | TypeScript 7.0 has no programmatic API for type-aware rules | Alias `typescript` to `@typescript/typescript6`; keep `tsc` 7 for the gate |
| Editor shows cross-package errors CI does not | Editor redirects to source while CI consumes stale `dist` | Run `tsc -b` after clone; avoid checking in `dist` without `--force` rebuilds |

## Verification

- `npx tsc -b` exits 0 with no output; `npx tsc -b --dry` prints `A non-dry build would build project` only for out-of-date projects.
- `npx tsc -p packages/core --showConfig | grep '"strict": true'` prints `"strict": true,`, proving the extended config is live.
- Negative test: a file containing `const rows: string[] = []; const first: string = rows[0]` must fail with `error TS2322: Type 'string | undefined' is not assignable to type 'string'`.
- `npx eslint . --max-warnings=0` exits 0; a new `any` fails the same command.

## Sources (2026)

- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/docs/handbook/project-references.html
- https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/
