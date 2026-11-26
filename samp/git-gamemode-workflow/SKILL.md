---
name: git-gamemode-workflow
description: Use when several devs ship one Pawn gamemode.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, git, ci, release]
    category: samp
---

# Gamemode git workflow: sources in git, AMX in releases

## When to Use

- Two or more developers edit `OnGameModeInit` and every merge is a conflict.
- A bad live build needs a rollback to a known tag, not a scramble through a shared folder.
- Your repo has committed `.amx` files, `scriptfiles` player data, or database passwords in it.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 reality | Rule |
| --- | --- | --- |
| Source | `.pwn` and `.inc` are text, diffs are reviewable | sources live in git, always |
| Build artefact | `pawncc` emits `.amx`, a binary nobody can review | build in CI, attach to a release, never commit |
| Includes | `pawncc -i include` resolves from the file tree | vendor includes as a pinned submodule or a committed `include/` |
| Player data | `scriptfiles/*.db`, `*.ini`, `*.log` | ignore, back up outside the repo |
| Credentials | DB password in `mysql.inc` calls or `config.json` | env vars in the unit, `.env` gitignored |
| Line endings | Pawn sources with CRLF break `grep`-based CI checks | `* text eol=lf` in `.gitattributes` |
| Releases | tag `vX.Y.Z`, attach the `.amx` plus changelog | the tag is the deployable unit |

## Production Implementation

1. Layout the tree so a build is reproducible from a clean clone: `gamemodes/`, `include/` (vendored, pinned), `filterscripts/`, `models/`, `scriptfiles/` ignored, `config.json` generated from a template.

```bash
git rm -r --cached gamemodes/*.amx 2>/dev/null; git rm -r --cached scriptfiles 2>/dev/null
printf '%s\n' '*.amx' 'scriptfiles/' 'config.json' '.env' '*.log' > .gitignore
printf '%s\n' '* text=auto eol=lf' '*.pwn text eol=lf' '*.inc text eol=lf' > .gitattributes
git add .gitignore .gitattributes && git commit -m "build: ignore artefacts, normalise line endings"
```

2. Protect `main` and work on short branches named for the subsystem, because `OnGameModeInit` is the file everyone touches. One owner per subsystem, merged by PR, keeps conflicts in one small hunk.

```bash
git switch -c feat/turf-capture
git commit -m "feat(turf): occupancy counters and capture timer"
git push -u origin feat/turf-capture
gh pr create --fill --base main
```

3. Gate merges on a compile, not on a human reading a diff. Vendor the compiler tarball under `tools/` so CI runs the same build as the host, and let a non-zero `pawncc` exit fail the job:

```yaml
name: build
on: [push, pull_request]
jobs:
  pawn:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y gcc-multilib
      - run: |
          tar xf tools/pawnc-linux.tar.gz -C tools/compiler
          tools/compiler/bin/pawncc gamemodes/main.pwn -i include -o /tmp/main.amx -d3
```

4. Tag releases from the merge commit and attach the artefact, so "what is live" is a tag plus a checksum rather than a file with a date in its name:

```bash
git switch main && git pull --ff-only
git tag -a v1.4.0 -m "turf capture, toast queue"
git push origin v1.4.0
gh release create v1.4.0 /tmp/main.amx --title "v1.4.0" --notes-from-tag
sha256sum /tmp/main.amx | tee main.amx.sha256
```

5. Deploy by checkout of the tag on the host, and verify the artefact hash before restarting the service. A rollback is then `git switch` back one tag and a service restart, not a restore from a backup:

```bash
cd /srv/omp && git fetch --tags && git switch --detach v1.4.0
sha256sum -c main.amx.sha256
sudo systemctl restart omp
```

6. Catch the two mistakes that actually happen with a hook, kept in the repo so it is not a per-clone ritual:

```bash
git config core.hooksPath .githooks
cat > .githooks/pre-commit <<'EOF'
#!/bin/sh
git diff --cached --name-only | grep -qE '\.(amx|db|env)$' && {
  echo "refusing to commit build artefacts or data files"; exit 1; }
exit 0
EOF
chmod +x .githooks/pre-commit
```

7. Ship the changelog from the commit log rather than writing it twice: `git log --oneline v1.3.0..v1.4.0` is the release note body, and conventional prefixes (`feat:`, `fix:`) make it readable without editing.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every merge conflicts in `OnGameModeInit` | everyone edits the same callback file | split callbacks per subsystem and merge small PRs |
| `main` does not compile | no build gate on the PR | required status check from the CI job in step 3 |
| Binary `.amx` conflicts | artefact committed | remove from the index, ignore it, ship it in releases |
| Live build cannot be identified | deployed from a working copy | deploy a tag, check `git describe --tags` on the host |
| CI passes locally, fails on the runner | case-sensitive include path or CRLF | lowercase include names, `eol=lf` attributes |
| DB password in the repo | config edited in place on the host | template `config.json` from env vars, never commit it |

## Verification

```bash
git tag -l 'v*' --sort=-v:refname | head -3
git describe --tags --always
git ls-files '*.amx' 'scriptfiles/*' | wc -l
git check-ignore -v scriptfiles/players.db config.json
```

Expected: the tag list starts with the newest release (`v1.4.0`), `git describe` prints a tag and not a bare hash, the tracked-artefact count is `0`, and `git check-ignore` names both the `scriptfiles/` and `config.json` rules with exit code 0, which is the proof that neither can be committed again.

## Sources (2026)

- https://git-scm.com/book/en/v2/Git-Basics-Tagging
- https://git-scm.com/docs/git-tag
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
