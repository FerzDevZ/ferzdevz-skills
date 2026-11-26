# Library gates: build, refresh, triage

## Native whitelist

The gate compares identifiers used in `pawn` blocks against three lists in `assets/`.
Rebuild them when open.mp or a plugin version changes.

```bash
# 1. documented functions (authoritative list of what exists)
curl -s https://open.mp/sitemap.xml \
  | grep -oE "docs/scripting/functions/[A-Za-z_][A-Za-z0-9_]+" \
  | awk -F/ '{print $4}' | sort -u > /tmp/docs_fns.txt

# 2. declared natives in the stdlib you actually compile against
grep -rhoE "native[[:space:]]+[A-Za-z_][A-Za-z0-9_]*" ~/samp-sdk/omp-stdlib/*.inc \
  | awk '{print $2}' | sort -u > /tmp/inc_fns.txt

cat /tmp/docs_fns.txt /tmp/inc_fns.txt assets/plugin_natives.txt | sort -u \
  > assets/omp_natives.txt
```

Plugin natives (streamer, MySQL, Pawn.RakNet, ColAndreas, MapAndreas, FCNPC, profiler) live
in `assets/plugin_natives.txt` because they are not in the open.mp docs. Skill-local helpers
(`AddMoney`, `ValidSlot`, callbacks) go in `assets/helpers.txt` so the gate stops reporting
them.

## Triaging a gate hit

1. Name is in the docs list -> the gate is stale, rebuild the whitelist.
2. Name is a plugin native -> add it to `plugin_natives.txt`.
3. Name is a helper the snippet defines conceptually -> add it to `helpers.txt`.
4. None of the above -> the snippet invented an API. Rewrite it to the documented function
   or to a verification step (`grep -n <topic> includes/omp_<x>.inc`) instead of guessing.

## Include gate

`compile_snippets.py` only treats `fatal error 100` as a defect: a `#include` that does not
resolve against omp-stdlib. Everything else it compiles out of context is noise. `YSI_*`
includes are exempt because YSI is a separate `sampctl` package; those are proven by
`sampctl ensure` / `pawncc -i.sdk/ysi`, not by this gate.

## Third-party API additions

Sequence for a skill built around a community library or component:

```bash
curl -sL <raw include url> -o /tmp/lib.inc
grep -oE "native[[:space:]]+[A-Za-z_][A-Za-z0-9_]*" /tmp/lib.inc | awk '{print $2}' | sort -u
```

1. Write the skill against exactly those names, and quote the include path it ships in.
2. If the repository layout or default branch differs from what a README claims, the fetch
   fails; do not fill the gap from memory. Make the skill's first implementation step the
   grep above.
3. Append the same names to `assets/plugin_natives.txt`; add callbacks that only the library
   declares (selection handlers, detection handlers) to `assets/helpers.txt`.
4. Re-run `validate_library.py`, `check_natives.py`, `compile_snippets.py` in that order.

A skill that cannot name a callable function and cannot name the grep that finds it is a
blog post, not an instruction.

## Adding a gate assertion

A rule that matters belongs in a script, not in prose. When a defect class recurs, add the
check that catches it and re-run all gates; a skill-library rule without a failing check does
not exist yet.
