---
name: forms-ux-validation-patterns
description: Use when form errors appear after submit or confuse.
version: "2026.1.0"
metadata:
  hermes:
    tags: [forms, validation, ux, accessibility]
    category: ui-ux
---

# Validate when the user can act, not while they are still typing

Most form frustration is a timing bug, not a copy bug. Validating on the first keystroke
says "wrong" before the answer is finished; validating only on submit hides the fix until
the work is over. The rule that holds: validate on blur, revalidate on input once the
field has errored, and on submit move focus to the first field that is still invalid.

## When to Use

- You are building signup, checkout, settings or any multi-step flow with server-side rules.
- Support tickets say "the form will not let me continue" and nobody can reproduce it.
- Inline errors, a success state and server validation must be mapped to fields in one pass.
- Do not use for search-as-you-type relevance; that is a ranking problem, not a form problem.

## Compatibility & Stack Matrix (2026)

| Component | Version | Note |
| --- | --- | --- |
| React | 19.x | the hook below works unchanged in 18.x |
| Zod | 4.x | one schema for client and server keeps messages identical |
| Native constraint validation | Chrome 13x, Firefox 14x, Safari 26 | browser messages are localised and cannot be styled |
| Playwright | 1.4x | assert focus target and live-region text, not pixels |
| axe-core | 4.10+ | label, `aria-describedby` and contrast on the error state |

## Production Implementation

1. Pick the input type and the `autocomplete` token before writing a rule; wrong tokens are the top cause of autofill filling the wrong box.

| Field | `type` | `autocomplete` | Why |
| --- | --- | --- | --- |
| Email | `email` | `email` | triggers the right keyboard on mobile |
| Postal code | `text` | `postal-code` | alphanumeric in most countries (1.3.5) |
| Card number | `text` + `inputmode="numeric"` | `cc-number` | enables payment autofill |

2. Put the requirement in the label, not in a colour or an asterisk alone, and wire the
   hint and the error into one description chain.

```html
<label for="email">Work email (required)</label>
<p id="email-hint">We send the receipt here. No marketing.</p>
<input id="email" name="email" type="email" autocomplete="email"
       aria-describedby="email-hint email-error" aria-invalid="true"
       value="ana@exmaple">
<p id="email-error" class="error" role="alert">
  Add the part after "@", like ana@example.com.
</p>
```

3. Implement the timing rule once, in a hook, so every field behaves the same.

```tsx
import { useState } from "react";

type Rule = (value: string) => string | null;

export function useField(id: string, rules: Rule[]) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const check = (v: string) => rules.map((r) => r(v)).find(Boolean) ?? null;

  return {
    value,
    error,
    fieldProps: {
      id,
      name: id,
      value,
      "aria-invalid": touched && error !== null,
      "aria-describedby": `${id}-error`,
      onBlur: () => {
        setTouched(true);
        setError(check(value)); // first verdict happens here
      },
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        setValue(e.target.value);
        if (touched) setError(check(e.target.value)); // live only after it has errored
      },
    },
  };
}
```

4. Write error copy as constraint plus example. "Invalid input" fails 3.3.3 because it
   names no fix; "Email must include an @, like ana@example.com" passes. Keep the
   entered value, keep the message under the field, never signal with colour alone.

5. On submit, validate everything, then move the person to the first failure.

```tsx
export function focusFirstInvalid(form: HTMLFormElement) {
  const field = form.querySelector<HTMLElement>('[aria-invalid="true"]');
  field?.scrollIntoView({ block: "center", behavior: "smooth" });
  field?.focus();
}
```

6. Map server issues to fields with an explicit alias table; API names and DOM names
   drift, and a silent mismatch turns a field error into a banner nobody reads.

```ts
type Issue = { field?: string; message: string };

const FIELD_ALIASES: Record<string, string> = {
  email_address: "email",
  postal_code: "postalCode",
  card_number: "cardNumber",
};

export function mapServerIssues(issues: Issue[]) {
  const fields: Record<string, string> = {};
  const form: string[] = [];
  for (const issue of issues) {
    const key = issue.field ? (FIELD_ALIASES[issue.field] ?? issue.field) : undefined;
    if (key) fields[key] = issue.message;
    else form.push(issue.message);
  }
  return { fields, form };
}
```

7. In multi-step flows keep answers across Back (3.3.7 Redundant Entry), show the step
   count as text ("Step 2 of 4"), and add a review screen. For login steps permit paste
   and password managers: blocking paste is a 3.3.8 Accessible Authentication failure.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| People abandon after the first character | validation fired on the first keystroke | validate on blur, revalidate on input only after `touched` |
| Screen reader never announces the error | message rendered outside the field's `aria-describedby` | wire the message id into `aria-describedby`; use `role="alert"` for async and server errors |
| User cannot find the field that failed | only a summary banner is shown | focus the first invalid control and keep the message adjacent (3.3.1) |
| Back button wipes step one | step data lives only in component state | keep a draft in a store or `sessionStorage`; restore on mount (3.3.7) |
| Payment fails and the form is empty again | the error path re-renders a fresh form | return submitted values with the error response and repopulate |
| Autofill fills the wrong boxes | missing or wrong `autocomplete` tokens | use the spec tokens from step 1 (1.3.5) |
| Message is correct but nobody understands it | copy names the rule, not the fix | constraint plus a concrete example built from real data |

## Verification

```bash
npx playwright test tests/forms.spec.ts --reporter=line
# expected: 4 passed (blur timing, server mapping, focus on first invalid, draft on Back)
```

```bash
npx @axe-core/cli http://localhost:3000/signup --tags wcag22aa --exit; echo "exit=$?"
# expected: exit=0, including the rendered error state
```

Manual check: submit the empty form once. Focus must land on the first invalid field,
the message must be read after the label and hint, and typed values must survive a
failed server round trip.

## Sources (2026)

- https://www.w3.org/WAI/tutorials/forms/ (labels, instructions, validation, multi-page)
- https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html (3.3.3, Level AA)
- https://web.dev/learn/forms/validation (onblur real-time validation, `aria-describedby` for rules)
- https://design-system.service.gov.uk/components/error-message/ (error copy and description wiring)
