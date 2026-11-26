---
name: release-changelog-generator
description: Use when a tag needs player-readable release notes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops, release]
    category: samp
---

# Turn a tag range into release notes players can read

The release is a tag plus an `.amx` plus a list of what changed. Notes are generated from the
commit range, then rewritten: `git log` gives you the facts, not the wording.

## When to Use

- A tag is cut and the notes are still "various fixes and improvements".
- Players ask "what changed" and the only answer is a commit list with internal refactors.
- A breaking change (a command renamed, a save format changed) shipped without a warning.
- The published `.amx` cannot be tied to the source it was built from.
- Release notes and `CHANGELOG.md` disagree about what is in the build.

## Compatibility & Stack Matrix (2026)

| Item | Version / command | Notes |
| --- | --- | --- |
| git | 2.40+ | `git log --no-merges --format`, `--sort=-v:refname` |
| gh CLI | 2.x | `gh release create --notes-file` |
| Artifact | `gamemodes/<name>.amx` | build from the tagged commit, never from a dirty tree |
| Checksum | `sha256sum` (GNU) / `shasum -a 256` (macOS) | one line per shipped file |
| Commit style | Conventional Commits 1.0.0 | `feat`, `fix`, `perf`, `refactor`, `!`, `BREAKING CHANGE:` |
| Notes format | Keep a Changelog 1.1.0 | Added / Changed / Fixed / Removed / Security |
| Build record | `pawncc` version + commit sha | printed into the release body |

A tag is the source of truth only if it is an ancestor of `HEAD`; a tag on an unmerged branch
produces a range that silently omits or duplicates work.

## Production Implementation

1. Freeze both ends of the range and prove the tag is reachable. `git describe` gives the last
   tag, which is the correct lower bound unless you are backporting:

```bash
git fetch --tags --prune
PREV=$(git describe --tags --abbrev=0 HEAD^)
git merge-base --is-ancestor "$PREV" HEAD || echo "TAG_NOT_ANCESTOR $PREV"
git log -1 --format='%H %d' "$PREV"
```

2. Collect the commits once, into a file you can grep. Exclude merges or every PR appears
   twice, once as its title and once as its squashed content:

```bash
git log --no-merges --pretty=format:'%h%x09%s' "$PREV"..HEAD > /tmp/commits.tsv
wc -l < /tmp/commits.tsv
```

3. Classify by prefix, and keep an "Other" bucket so nothing is dropped by accident. A commit
   that matches no bucket is a note to yourself, not a reason to hide it:

```bash
for t in feat fix perf security refactor docs chore; do
  printf '\n== %s ==\n' "$t"
  grep -P "^\S+\t$t(\([^)]*\))?!?:" /tmp/commits.tsv | cut -f2 | sed -E "s/^$t(\([^)]*\))?!?: *//"
done
printf '\n== other ==\n'
grep -vP "^\S+\t(feat|fix|perf|security|refactor|docs|chore)(\([^)]*\))?!?:" /tmp/commits.tsv | cut -f2
```

4. Rewrite each line as a player-observable change. "fix: null check in OnPlayerDeath" ships as
   "Fixed the occasional server crash when a player died inside a vehicle". Internal-only work
   (`chore`, most `refactor`) stays out of the player notes and goes into `CHANGELOG.md`.

5. Pull the issue references out so players can read the report, and drop the ones that only
   make sense to staff:

```bash
grep -oiE '#[0-9]+' /tmp/commits.tsv | sort -u | tr '\n' ' '
```

6. Detect breaking changes before writing prose. Both the `!` marker and the footer count:

```bash
git log --no-merges --pretty=format:'%h %s%n%b' "$PREV"..HEAD \
  | grep -nE '^[0-9a-f]+ [a-z]+(\([^)]*\))?!:|^BREAKING CHANGE:' || echo "none"
```

   If that prints anything, the first section of the notes is "Breaking changes" with the
   migration step for each - a renamed command, a rewritten save column, a new required
   include. Skipping it is the single most expensive note error.

7. Build the artifact from the tag, then checksum exactly what you ship. A rebuild after the
   checksum invalidates the release:

```bash
git checkout -q v1.4.0
pawncc gamemodes/rp.pwn -i./includes -o gamemodes/rp.amx -;+ -(+ -d3
sha256sum gamemodes/rp.amx | tee /tmp/rp.sha256
stat -c '%s bytes' gamemodes/rp.amx
```

8. Publish, then read the release back. `gh release create` accepts a notes file, so the body
   is the file you reviewed rather than a shell-quoted string:

```bash
gh release create v1.4.0 gamemodes/rp.amx \
  --title "v1.4.0" --notes-file /tmp/notes.md
gh release view v1.4.0 --json name,body,assets --jq '.assets[].name'
```

9. Append the same grouping to `CHANGELOG.md` under `## [1.4.0] - YYYY-MM-DD`, newest first,
   so the repository alone tells the history without the forge UI.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Notes miss commits you merged | range built from a tag on an unmerged branch | `git merge-base --is-ancestor`, rebase or retag |
| Every PR listed twice | merge commits included | `--no-merges` |
| Players report "no such command" | breaking change not in a leading section | grep `!` and `BREAKING CHANGE:`, add migration |
| Checksum does not match the download | `.amx` rebuilt after `sha256sum` | checksum the exact uploaded file, re-upload |
| Notes describe unshipped code | noted from `HEAD`, built from the tag | build after `git checkout vX.Y.Z` |
| Notes are unreadable | raw commit subjects published | rewrite per bullet, keep `chore` out |
| `CHANGELOG.md` diverges | hand-edited separately | generate one file, copy into both places |

## Verification

Every commit in the range must be accounted for in the notes. This fails loudly on the one
that was dropped:

```bash
while IFS=$'\t' read -r sha subj; do
  grep -qF "$(printf '%s' "$subj" | sed -E 's/^[a-z]+(\([^)]*\))?!?: *//')" /tmp/notes.md \
    || echo "MISSING $sha $subj"
done < /tmp/commits.tsv
echo "commits=$(wc -l < /tmp/commits.tsv) notes=$(grep -c '^- ' /tmp/notes.md)"
```

```text
commits=37 notes=37
```

No `MISSING` line, and the two counts equal. Then confirm the release body and asset are the
ones verified above:

```bash
gh release view v1.4.0 --json body,assets --jq '.assets[].name, (.body | length)'
sha256sum -c /tmp/rp.sha256
```

```text
rp.amx
1842
gamemodes/rp.amx: OK
```

## Sources (2026)

- https://git-scm.com/docs/git-log
- https://keepachangelog.com/en/1.1.0/
- https://www.conventionalcommits.org/en/v1.0.0/
