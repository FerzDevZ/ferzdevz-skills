# nextjs-dynamic-layout

Copy `fixture/` into a working directory, then answer in that same directory.

Prompt given to the agent (identical for both arms):

> Every route in this App Router app reports as dynamic since we added the cart badge in the
> root layout. Keep the layout static, keep pages as Server Components, and still show the
> per-user cart count rendered on the server. Do not add a client component that fetches a
> route handler. Return the changed files, not a description.
> Write the file(s) before explaining anything. If you run out of budget, the file must already exist and be complete.

The answer directory must contain `app/layout.tsx` and `app/components/cart-badge.tsx`.
