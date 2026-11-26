---
name: component-api-design
description: Use when a component's props keep growing and refs break
version: "2026.1.0"
metadata:
  hermes:
    tags: [react, component-api, accessibility, typescript, composition]
    category: web-design
---

# Design the prop surface so it cannot be used wrong

Every component that fails review failed at the API, not the CSS: `isPrimary` and
`isSecondary` both true, a `variant` attribute leaking into the DOM, a ref that stays
`null` because the wrapper never forwarded it. Four decisions decide the primitive —
variant, slot, control mode, keyboard contract — and TypeScript should reject the rest.

## When to Use

- A component has 12 boolean props and the combinations are not all valid.
- You are about to add `forwardRef` in a React 19 codebase.
- Design asks for "a button that is sometimes a link" and `isLink` appears.
- A modal or tabs component works with a mouse and fails with a keyboard.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| React | 19.3.x | `ref` is a normal prop; `forwardRef` deprecated |
| React | 18.x | `forwardRef` still required for refs |
| TypeScript | 7.0.x | Unions on props; `@ts-expect-error` as a compile-time test |
| ARIA APG | Button / Tabs / Dialog | Keyboard contract source of truth |
| Testing | `react-dom/server` + `tsc --noEmit` | Fast enough for every commit |

## Production Implementation

1. Model variants as a union, sizes as a second union, never as booleans. Two
   orthogonal axes give 9 valid combinations instead of 4 flags with 16 states.

```tsx
import { type ComponentPropsWithRef, type Ref } from "react";
type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md";

export interface ButtonProps extends Omit<ComponentPropsWithRef<"button">, "className"> {
  variant?: Variant; size?: Size;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ variant = "primary", size = "md", type = "button", ...rest }: ButtonProps) {
  return <button type={type} data-variant={variant} data-size={size} {...rest} />;
}
```

2. Style from `data-*`, not from generated class strings; `className` stays for layout
   only, and the variant never becomes a DOM attribute.

```css
.btn[data-size="sm"] { padding: 0.375rem 0.75rem; font-size: 0.875rem; }
.btn[data-variant="ghost"] { background: transparent; border: 1px solid currentColor; }
.btn[data-variant="primary"] { background: var(--ds-color-action-bg); color: var(--ds-color-action-fg); }
```

3. Compose with children and context instead of adding props: a compound `Tabs` keeps
   one state and gives each part its contract; `isTab`/`isPanel` props do not.

```tsx
const TabsCtx = createContext<{ value: string; onValueChange: (v: string) => void } | null>(null);
export function Tabs({ value, onValueChange, children }: {
  value: string; onValueChange: (v: string) => void; children: ReactNode;
}) {
  return <TabsCtx.Provider value={{ value, onValueChange }}><div role="tablist">{children}</div></TabsCtx.Provider>;
}

export function Tab({ value, children }: { value: string; children: ReactNode }) {
  const ctx = useContext(TabsCtx)!;
  const selected = ctx.value === value;
  return <button role="tab" id={`tab-${value}`} aria-selected={selected}
      aria-controls={`panel-${value}`} tabIndex={selected ? 0 : -1}
      onClick={() => ctx.onValueChange(value)}>{children}</button>;
}
```

4. Support controlled and uncontrolled through one hook, and type the controlled form
   so it requires `onChange`. `value` without `onChange` renders a read-only input.

```tsx
export function useControllableState<T>(opts: {
  value?: T; defaultValue: T; onChange?: (next: T) => void;
}): [T, (next: T) => void] {
  const [internal, setInternal] = useState(opts.defaultValue);
  const controlled = opts.value !== undefined;
  const current = controlled ? (opts.value as T) : internal;
  const set = useCallback((next: T) => {
    if (!controlled) setInternal(next); opts.onChange?.(next);
  }, [controlled, opts.onChange]);
  return [current, set];
}
type Controlled = { value: string; onChange: (v: string) => void };
type Uncontrolled = { value?: undefined; defaultValue?: string; onChange?: (v: string) => void };
export type FieldProps = (Controlled | Uncontrolled) & { label: string };
```

5. In React 19, take `ref` from props and pass it to the node. Keep `forwardRef` only
   for packages that still support React 18; its second argument is no longer the path.

```tsx
export function Input({ ref, ...props }: ComponentPropsWithRef<"input">) {
  return <input ref={ref} {...props} />;
}
```

6. Write the keyboard and ARIA contract down first; native elements cover most of it,
   anything built from a `div` covers none of it.

| Primitive | Keys | ARIA that must be present |
| --- | --- | --- |
| Button | Enter, Space | `aria-pressed` only if toggle; `aria-disabled` when unavailable |
| Tabs | Arrow keys move, Home/End jump | `role="tab"`, `aria-selected`, `aria-controls`, roving `tabIndex` |
| Dialog | Esc closes, focus trapped, focus returns to opener | `role="dialog"`, `aria-modal`, `aria-labelledby` |
| Toggle | Enter, Space | `aria-pressed`; label text must not change with state |

7. Add compile-time tests: `@ts-expect-error` fails the build the moment a bad usage
   starts compiling, which is the regression you actually care about.

```tsx
export const ok = <Button variant="ghost" size="sm">Save</Button>;
// @ts-expect-error unknown variant must not compile
export const badVariant = <Button variant="tertiary">Save</Button>;
// @ts-expect-error booleans are not part of the API
export const badBoolean = <Button isGhost>Save</Button>;
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `isPrimary` and `isSecondary` both render primary | Boolean props encode one axis many times | Single `variant` union; delete the flags |
| DOM shows `variant="ghost"` and React warns about an unknown prop | Whole props object spread onto the element | Destructure API props first, spread only `...rest` |
| Ref is `null` after migrating to React 19 | `forwardRef` render still reading its second argument | Read `ref` from props and pass it to the node |
| Typing in a controlled input does nothing | `value` passed without `onChange` | Type props as a controlled/uncontrolled union; throw in dev when only `value` is set |
| Toggle announces "Mute toggle button pressed", then the label flips to "Unmute" | `aria-pressed` plus a changing label | Keep the label stable, or drop `aria-pressed` and change the label |

## Verification

- `npx tsc --noEmit` → exit 0 with both `@ts-expect-error` lines needed. If a bad usage
  starts compiling, TS reports "unused '@ts-expect-error'" and the gate fails.
- Render the built component and assert the DOM shape:

```bash
npx esbuild src/Button.tsx --bundle --format=esm --jsx=automatic \
  --external:react --external:react/jsx-runtime --outfile=.tmp/button.mjs
node --input-type=module -e "import {createElement as h} from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {Button} from './.tmp/button.mjs'; const html = renderToStaticMarkup(h(Button,{variant:'ghost',type:'submit'},'Save')); console.log(html); if (/\s(variant|size)=/.test(html)) process.exit(1);"
```

```text
<button type="submit" data-variant="ghost" data-size="md">Save</button>
```

- `grep -rn "forwardRef" src/components` → no output in a React 19 codebase.
  `grep -rn 'role="button"' src` → no output; a native `<button>` gives Enter and Space.
- Manual: unplug the mouse. Tab through every control, activate with Enter and Space,
  confirm focus is visible at 3:1 and returns to the opener after Esc.

## Sources (2026)

- https://react.dev/reference/react/forwardRef
- https://www.w3.org/WAI/ARIA/apg/patterns/button/
- https://www.w3.org/TR/WCAG22/
