# money-concurrency

Prompt given to the agent (identical for both arms):

> Two /transfer requests running at the same time sometimes debit the sender twice and
> sometimes drive a balance negative, and MySQL logs a deadlock now and then. Harden the
> transfer so it is safe under concurrency. Write `transfer-fixed.pwn` into the working
> directory.
> Write the file(s) before explaining anything. If you run out of budget, the file must already exist and be complete.

Answer directory must contain `transfer-fixed.pwn`.
