---
name: review
description: >-
  Run a reviewer subagent against your whole branch vs main, your uncommitted
  working state, a named branch, a single GitHub PR, or an entire
  Graphite/stacked-PR stack (one reviewer subagent per PR). A bare /review
  defaults to reviewing your uncommitted working state when the tree is dirty,
  or your whole branch vs main when the tree is clean. Main, local, and
  branch modes write a review file plus a summary to disk. PR and stack modes
  post the findings as a PENDING GitHub review for the user to inspect and submit
  through the UI. Use --main for an explicit clean-tree branch review, --stack
  for stacked PRs, --submit to publish immediately as COMMENT, or --approve to
  publish and approve; the default remains PENDING.
when-to-use: "Use when asked to 'review', 'code review', 'review my changes', 'review my branch', 'review this PR', 'review a stack', '/review', '/review --main', '/review --stack', '/review --submit', or '/review --approve'."
argument-hint: "[--main | --local | --branch <name> | --pr <number-or-url> | --stack <number-or-url> | <auto-detect>] [--approve | --submit]"
---

# Review Skill

You are an orchestrator that runs reviewer subagents against one of five review targets. You coordinate only — **all** review findings are authored by a subagent whose prompt is seeded with the `reviewer` persona instructions, never by the orchestrator directly.

## Persona Injection

This skill uses the **reviewer** persona. The persona instructions are defined at:

```
<dirname of this SKILL.md>/../shared/personas/reviewer.md
```

Resolve this path once at the start of the run (the system context gives you the absolute path to this SKILL.md). Read the file with `read_file` and store its contents as `reviewer_persona_instructions`.

When launching the reviewer subagent, **prepend** the persona instructions to the prompt. Do NOT pass a `persona` parameter to `spawn_subagent` — that parameter is not supported. Instead, prefix the `description` with `[reviewer]` so the pager's subagent label renderer surfaces "Reviewer" at the top of the subagent row (see Step 2 below).

1. **Main mode** -- the committed diff of the current branch against its merge-base with the default branch (`origin/main`, or `origin/master`). The working tree must be clean.
2. **Local mode** -- uncommitted changes only (staged + unstaged + untracked).
3. **Branch mode** -- the diff between a *named* branch and its merge-base with the default base branch. Committed changes only.
4. **PR mode** -- a GitHub pull request. Findings are posted as a PENDING review for the user to inspect and submit through GitHub (default).
5. **Stack mode** -- every PR in a Graphite/stacked-PR stack, discovered from one starting PR; one reviewer subagent per PR, each posting its own review.

`--approve` and `--submit` are *modifiers*, not modes. They are valid only with PR and stack modes and are mutually exclusive. The default (no modifier) omits the `event` field so each review is created PENDING for the user to submit through the UI. `--submit` posts with `event: COMMENT` (published immediately, visible right away, no approval). `--approve` posts with `event: APPROVE` (publish + approve in one call).

The reviewer subagent is read-only with respect to source code. It must still write its review artifacts. The orchestrator never edits source either; the only artifacts produced are a review file, a summary file, and (in PR and stack modes) a GitHub review. In stack mode the per-PR subagents also post their own reviews (unlike single PR mode, where the orchestrator posts).

**Do not pass `capability_mode: read-only`.** That mode removes the `write` tool, so the reviewer cannot create `<review_file>`. Enforce source read-only behavior through the prompt.

## Invocation

The user runs one of:

| Command | Behavior |
|---|---|
| `/review` | default (local mode if the tree is dirty, main mode if it is clean) |
| `/review --main` | main mode (explicit) |
| `/review --local` | local mode (explicit) |
| `/review --branch <name>` | branch mode (explicit) |
| `/review --pr <number-or-url>` | PR mode (explicit; PENDING reviews) |
| `/review --stack <number-or-url>` | review every PR in the stack containing this PR (PENDING reviews) |
| `/review --pr <number-or-url> --submit` | review and publish immediately as COMMENT (no approval) |
| `/review --stack <number-or-url> --submit` | review + publish COMMENT on every PR in the stack |
| `/review --pr <number-or-url> --approve` | review, submit, and approve |
| `/review --stack <number-or-url> --approve` | review + submit + approve every PR in the stack |
| `/review <plain-arg>` | auto-detect; see disambiguation below |

### Argument parsing

Parse the raw argument tokens in **two phases**: first extract the `--approve` / `--submit` modifiers, then resolve the mode from the remaining tokens.

**Phase 1 -- modifier extraction.** Scan the raw argument tokens for standalone `--approve` and `--submit` tokens anywhere in the list. If `--approve` is present, set `APPROVE=true` and remove all its occurrences; otherwise `APPROVE=false`. If `--submit` is present, set `SUBMIT=true` and remove all its occurrences; otherwise `SUBMIT=false`. If BOTH are present, reject with `--approve and --submit are mutually exclusive.` and stop. All of Phase 2 operates on the REMAINING tokens.

**Phase 2 -- mode resolution.** First, reject input that contains more than one of the mode-selecting flags `--main` / `--local` / `--branch` / `--pr` / `--stack` (e.g. `--pr 1 --stack 2`) with `Only one of --main, --local, --branch, --pr, --stack may be given.` and stop. This cross-cutting check runs BEFORE the ordered rules below, because those rules stop at the first matching flag and would otherwise never see the second one. Then parse the remaining tokens with these deterministic rules, applied in order. The first rule that matches wins; do not fall through.

1. **Empty / whitespace-only**: run `git status --porcelain`. Non-empty (uncommitted changes) resolves `MODE=local`; empty (clean tree) resolves `MODE=main`. No target either way.
2. **Starts with `--main`**: `MODE=main`. Reject any extra positional argument with an error.
3. **Starts with `--local`**: `MODE=local`. Reject any extra positional argument with an error.
4. **Starts with `--branch <name>`**: `MODE=branch`, `TARGET=<name>`. The branch name is required -- if the flag appears with no following token (or only with another `--`-prefixed token), reject with `Flag --branch requires an argument: <branch-name>` and stop.
5. **Starts with `--pr <id-or-url>`**: `MODE=pr`, `TARGET=<id-or-url>`. The id or URL is required -- if the flag appears with no following token (or only with another `--`-prefixed token), reject with `Flag --pr requires an argument: <number-or-url>` and stop.
6. **Starts with `--stack <id-or-url>`**: `MODE=stack`, `TARGET=<id-or-url>`. The id or URL is required -- if the flag appears with no following token (or only with another `--`-prefixed token), reject with `Flag --stack requires an argument: <number-or-url>` and stop.
7. **Starts with `--` but does not match any of the above**: reject with `Unknown flag: <flag>. Valid flags: --main, --local, --branch <name>, --pr <number-or-url>, --stack <number-or-url>, --approve, --submit.` and stop. Do NOT fall through to auto-detect.
8. **Plain argument given (no flag prefix)**: auto-detect against the rules below, also applied in order:
   1. Matches the regex `^https?://github\.com/[^/]+/[^/]+/pull/\d+(?:[/?#].*)?$` -- treat as PR URL. `MODE=pr`, `TARGET=<url>`.
   2. Matches `^#?\d+$` (optional leading `#`, then pure digits) -- treat as PR number. `MODE=pr`, `TARGET=<digits without leading #>`. A bare number always stays single-PR mode -- stack review requires the explicit `--stack` flag.
   3. Resolves to a local or remote branch via `git rev-parse --verify --quiet <arg>` or `git rev-parse --verify --quiet origin/<arg>` -- treat as branch. `MODE=branch`, `TARGET=<arg>` (use the bare name, not `origin/<arg>`).
   4. None of the above -- ask the user whether the argument is a PR identifier or a branch name (use the appropriate ask/question tool if available). Provide three options: "PR (treat as PR identifier)", "Branch (treat as branch name)", and "Cancel". On Cancel, stop.

As enforced by the pre-check at the top of Phase 2, the mode-selecting flags `--main` / `--local` / `--branch` / `--pr` / `--stack` are mutually exclusive -- input containing more than one is rejected before the ordered rules run.

**Modifier validation.** After resolving `MODE`, if `APPROVE` or `SUBMIT` is true and `MODE` is `main`, `local`, or `branch` (including an auto-detected branch), reject with `--approve/--submit are only valid with --pr or --stack (PR-based modes).` and stop.

If the user passes both a mode flag and a positional argument (e.g., `/review --local somebranch`), reject with a clear error message and stop -- the mode flags are mutually exclusive and take no free positional. This rejection does NOT apply to `--approve`/`--submit`, which are co-flags rather than modes: `/review 1234 --approve`, `/review --pr 1234 --approve`, `/review --pr 1234 --submit`, and `/review --stack 1234 --submit` are all valid.

## Setup

Host commands must work in bash **and** PowerShell. Do not run `python3`, `umask`, `id -u`, `chmod`, `jq`, `wc`, `rm -f`, `sort -u`, or write to `/tmp`. Use `run_terminal_command`.

1. Confirm cwd is a git work tree with `git rev-parse --is-inside-work-tree`. If this fails, report that cwd is not a git repository and stop.
2. Resolve `HOST_PY` as `<dirname of this SKILL.md>/../shared/scripts/host.py`.
3. Find a real Python 3 interpreter. Try in order: `python`, `py -3`, `python3`. Reject any path containing `WindowsApps`. If none works, tell the user to install Python 3 and stop.
4. Run `<python> <HOST_PY> setup` and parse the JSON stdout. Store `python` as `PYTHON`, `scratch_dir` as `scratch_dir`, and `run_id` as `REVIEW_ID`.

Validate that `REVIEW_ID` is exactly 8 hexadecimal characters. If setup failed or any required value is empty, report the error and stop.

**Inline the resolved absolute `scratch_dir` and `PYTHON`** into every later command and subagent prompt. Do not rely on shell variables surviving across `run_terminal_command` calls. Also inline the absolute `HOST_PY` path where cleanup is delegated.

Define these paths once and reuse them:

- `summary_file`: `${scratch_dir}/grok-review-summary-${REVIEW_ID}.md` (main, local, and branch modes only).
- `review_file`: `${scratch_dir}/grok-review-${REVIEW_ID}.md` (main, local, branch, and single-PR modes).
- `diff_file`: `${scratch_dir}/grok-review-diff-${REVIEW_ID}.diff` (main, local, branch, and single-PR modes).
- `files_file`: `${scratch_dir}/grok-review-files-${REVIEW_ID}.txt`.
- `pending_review_payload`: `${scratch_dir}/grok-review-pending-${REVIEW_ID}.json` (single-PR mode only).
- `prmeta_file`: `${scratch_dir}/grok-review-prmeta-${REVIEW_ID}.json` (single-PR mode only).
- `post_file` and `post_error_file`: `${scratch_dir}/grok-review-post-${REVIEW_ID}.json` and `${scratch_dir}/grok-review-post-${REVIEW_ID}.err`.

In stack mode the orchestrator does not write single-target artifacts. Each reviewer receives the absolute `scratch_dir`, `PYTHON`, and `HOST_PY` and owns per-PR paths such as `${scratch_dir}/grok-review-${REVIEW_ID}-pr<num>.diff`, `${scratch_dir}/grok-review-${REVIEW_ID}-pr<num>.md`, and `${scratch_dir}/grok-review-${REVIEW_ID}-pr<num>.json`.

Initialize state:

- `mode`: one of `main`, `local`, `branch`, `pr`, `stack`.
- `target`: branch name, PR number, or PR URL; empty in main/local mode.
- `approve` and `submit`: booleans from argument parsing, both false by default.
- `head_sha`, `base_sha`, `owner`, `repo`, `pr_number`, `pr_url`, `pr_title`: populated for PR mode.
- `changed_files`: populated during diff collection.
- `stack_prs`: stack mode only, ordered base-to-tip objects `{number, url, owner, repo, headRefName, baseRefName, title}`.

## Step 1: Resolve target & collect diff

The diff collection commands differ per mode.

### Main mode

Main mode reviews the committed diff of the current branch against its merge-base with the default branch. It is the clean-tree path selected by a bare `/review`.

1. Run `git status --porcelain`. If the tree is dirty, do not assemble a mixed diff with shell loops. Tell the user to use `/review --local` for the working state or clean the tree before `/review --main`, then stop. Local changes must always be collected by `COLLECT_PY` as described below.
2. Determine `BASE`. Check `origin/main`, then `origin/master`, with separate `git rev-parse --verify --quiet <ref>` calls. If neither exists, ask the user which base ref to use, offering the name from `git symbolic-ref refs/remotes/origin/HEAD` when available plus an "Other" option.
3. Compute `MERGE_BASE` with `git merge-base <BASE> HEAD`. Collect the diff and changed-file names with commands whose absolute output paths have been inlined:

   ```text
   git -c color.ui=false -c color.diff=false -c core.quotepath=false diff <MERGE_BASE>..HEAD
   git -c color.ui=false -c color.diff=false -c core.quotepath=false diff --name-only <MERGE_BASE>..HEAD
   ```

   Persist their stdout to `<diff_file>` and `<files_file>` with `run_terminal_command` redirection that is valid for the active shell. Read the resulting diff size from file metadata or `read_file`; do not invoke a byte-counting utility. Apply the local size gates. For a >10 MB main diff, suggest a narrower `--pr <number>` or named `--branch` target.
4. If `<diff_file>` is empty or whitespace-only, print "Branch has no changes vs `<BASE>`." Skip the reviewer, run main/local/branch cleanup, and use the matching empty-diff Final report. Otherwise read `changed_files` from `<files_file>`.

### Local mode

1. Run `git status --porcelain`. If it is empty, print "No local changes to review (working tree clean)." Skip the reviewer, run main/local/branch cleanup, and use the matching empty-diff Final report.
2. Resolve `COLLECT_PY` as `<dirname of this SKILL.md>/scripts/collect_local_diff.py`. Run:

   ```text
   <PYTHON> <COLLECT_PY> --diff <diff_file> --files <files_file>
   ```

   Inline the absolute interpreter and paths. Parse the JSON stdout fields `bytes`, `files`, and `empty`. This helper is the required path for staged, unstaged, and untracked local changes. Do not replace it with shell `git diff` plus untracked-file loops, and do not mutate the index.
3. Apply the size gate from `bytes`:
   - Above 10 MB, abort and point the user to `git status --porcelain` and an appropriate platform-native size inspection to find generated or untracked data that belongs in `.gitignore`. Run cleanup and stop.
   - Above 1 MB, ask for confirmation. On decline, run cleanup and stop.
   - Otherwise proceed silently.
4. Read `changed_files` from the collector's `files` array. The helper handles repositories without `HEAD`, expected nonzero `git diff --no-index` results, untracked files, and symlinks without modifying the worktree or index.

### Branch mode

1. Determine `BASE` exactly as in main mode: probe `origin/main`, then `origin/master`, with separate commands. Ask for a base ref if neither exists.
2. Verify `<target>` with `git rev-parse --verify --quiet <target>`, then `origin/<target>`. If neither resolves, report the error and stop.
3. Compute `MERGE_BASE` with `git merge-base <BASE> <target>`. Collect `MERGE_BASE..<target>` with color disabled and `core.quotepath=false`, persisting the diff to `<diff_file>` and names to `<files_file>`. Inline all resolved paths rather than relying on shell variables across calls.
4. If `<diff_file>` is empty or whitespace-only, print "Branch `<target>` has no changes vs `<BASE>`." Skip the reviewer, run main/local/branch cleanup, and use the matching Final report. Otherwise read `changed_files` from `<files_file>`.

### PR mode

1. Run `gh auth status`. If it fails, tell the user to run `gh auth login` and stop.
2. Fetch metadata in one call and persist it to `<prmeta_file>`:

   ```text
   gh pr view <target> --json number,title,body,headRefOid,baseRefOid,headRefName,baseRefName,url,headRepository,headRepositoryOwner,isCrossRepository,files
   ```

   Parse the JSON yourself. Populate `pr_number`, `pr_title`, `pr_url`, `head_sha`, `base_sha`, and `.files[].path`. Parse `owner` and `repo` from `pr_url` with `^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/\d+`; the URL identifies the upstream even for cross-repository PRs. Persist the changed-file paths to `<files_file>` with the `write` tool or retain them as structured state. Do not invoke a separate JSON parser binary. Validate `pr_number`, `head_sha`, `base_sha`, `owner`, and `repo`; on missing data show the parsed metadata and stop.
3. Run `gh pr diff <target>` and persist stdout to `<diff_file>`.
4. If the diff is empty, print "PR #<pr_number> has no changes." If `approve` is true, add "Nothing to review or approve; not approved." Never auto-approve an empty diff. Skip the reviewer, run the PR no-reviewer cleanup, and use the matching Final report.

### Stack mode

Stack mode reviews every PR in a Graphite/stacked-PR stack. Step 1 only **discovers** the stack; the per-PR diffs are collected by each subagent in Step 2 (the orchestrator collects no diff itself in this mode).

**Discovery algorithm** (deterministic):

1. Verify `gh` authentication with `gh auth status` (same as PR mode). If it exits non-zero, stop with the same guidance -- warn that the stack cannot be fetched without `gh` auth and tell the user to run `gh auth login`.
2. Resolve the start PR (works for both numeric IDs and full URLs):

   Run `gh pr view <target> --json number,headRefName,baseRefName,url,title,state`.

   Parse `owner`/`repo` from the start PR's `url` (same regex as PR mode: `^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/\d+`). The `target` may be a full URL (or `GH_REPO` may be set), so the start PR can live in a different repository than the current checkout. Inline the resolved `<owner>/<repo>` in every subsequent discovery call and hand it to each per-PR subagent. Do not rely on a `REPO` shell variable surviving across commands.

3. Determine the repo default branch with `gh repo view <owner>/<repo> --json defaultBranchRef --jq '.defaultBranchRef.name'`. If the result is empty, fall back to whichever of `origin/main` / `origin/master` resolves via separate `git rev-parse --verify --quiet` calls, else `main`.
4. Fetch all open PRs once with `gh pr list --repo <owner>/<repo> --state open --limit 1000 --json number,headRefName,baseRefName,url,title` and build a map keyed by `headRefName`.

   `gh pr list` returns at most `--limit` PRs. If the number returned equals the limit, the list was truncated and stack neighbors beyond that window may be missing -- warn the user that stack discovery may be incomplete (rerun with a higher `--limit`) before proceeding with whatever was fetched.

5. **Walk down** (toward the base): start at the start PR. While its `baseRefName` is the `headRefName` of another open PR in the map, AND that base is not the default branch, AND it has not already been visited, prepend that base PR and continue the walk from it.
6. **Walk up** (toward the tip): traverse outward from the start PR over all open PRs. Maintain a frontier of already-included heads (initially just the start PR's `headRefName`); repeatedly add every not-yet-visited open PR whose `baseRefName` matches any already-included head, adding each newly added PR's `headRefName` to the frontier, until no open PR matches. This collects every reachable descendant -- a single child in the common linear chain, or all branches of a *branching* stack -- ordered by base-depth (distance from the start PR), rather than following only one child.
7. Produce `stack_prs` ordered base->tip, de-duplicated, always including the start PR. For each entry, parse `owner` and `repo` from its `url` with the same regex PR mode uses (`^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/\d+`) so every subagent has a defined owner/repo source. If no neighbors are found, proceed with a single-element stack and note: "starting PR has no detected stack neighbors; reviewing it alone."
8. Report the discovered stack to the user as an ordered list (`#<num> -- <title>`) BEFORE launching any subagents.

There is no orchestrator-side empty-diff or zero-issue short-circuit in stack mode -- each subagent makes those decisions for its own PR.

After Step 1, report progress: "Collected diff for <mode> target <summary>. Launching reviewer..." (in stack mode there is no single diff -- report the discovered stack instead, per the Stack mode subsection above and In-Progress Reporting.)

## Step 2: Launch reviewer subagent

In main, local, branch, and single-PR modes, launch a single reviewer subagent by calling `spawn_subagent` (this section). In **stack mode**, skip the single-reviewer flow and use the **Stack mode** subsection at the end of this step instead, which launches one reviewer subagent per PR in parallel. Emit the `spawn_subagent` tool call before producing any "reviewer is starting" narration; the post-launch progress message ("Review complete. Processing findings...") belongs in a later assistant message after the tool result is in hand.

`spawn_subagent` parameters:

- `subagent_type`: `"general-purpose"`
- `background`: `false`
- `description`: `"[reviewer] <mode> <target-summary>"` (e.g., `"[reviewer] pr #4221"` or `"[reviewer] branch feature/foo"` or `"[reviewer] main"` or `"[reviewer] local changes"`). The `[reviewer]` prefix is parsed by the pager's subagent label renderer (see `format_subagent_label` in `xai-grok-pager`) so the subagent row shows "Reviewer" instead of the generic "General" fallback. The bracketed prefix is stripped from the displayed description.
- Do **not** pass `capability_mode`. The reviewer needs `write` for `<review_file>`; the prompt keeps it off source files.

Build the prompt with the mode-specific context. **Prepend the reviewer persona instructions** (loaded during setup) to the prompt. Use this template:

```
<reviewer_persona_instructions>

---

You are reviewing code changes. Mode: <mode>.

Target: <target-summary-line>
<if PR mode: PR URL: <pr_url>>
<if PR mode: head SHA: <head_sha>, base SHA: <base_sha>>
<if branch mode: base: <BASE>, merge-base: <MERGE_BASE>, head: <target>>
<if main mode: base: <BASE>, merge-base: <MERGE_BASE>, head: HEAD (clean working tree)>

The unified diff is at: <diff_file>
The list of changed files is at: <files_file>

Read the diff first to understand the scope. The diff alone is often not enough
context, so you should also `read_file` the source files referenced in the diff
to understand call sites, types, and surrounding logic before flagging issues.

Diff-review scope (overrides any conflicting persona Scope text):
- Report issues in ADDED or MODIFIED diff lines. Also flag breakages from
  deleted/renamed symbols even when call sites are outside the diff, after
  verifying those call sites.
- Do not report pre-existing problems in untouched code unless the diff newly
  depends on them in a way that will break.
- If a high-risk finding is the clearly intended, well-constrained purpose of
  the change, do not report it. Report it only if the author likely missed
  downstream impact or the change looks unconstrained/malicious.
- Flag feature-flag / internal-only gate leaks (new user-visible paths that
  skip an existing gate, or gates removed without a matching product intent).

Write your structured findings to: <review_file>

Format:

## Summary

<2 to 4 sentence overall assessment of the changes -- what they do, whether
they look correct, the dominant risk areas. This goes at the very top of the
file, before any individual issues.>

## Issues

### Issue 1 -- Severity: bug
- File: path/to/file.ext:LINE
- Description: <what is wrong>
- Suggestion: <how to fix>
- Status: open

### Issue 2 -- Severity: suggestion
- File: path/to/file.ext:LINE
- Description: ...
- Suggestion: ...
- Status: open

Severity must be one of: bug, suggestion, nit. Each issue's Status field must be set to "open" (as shown in the example above).

<if PR mode, include this paragraph verbatim:>
IMPORTANT: For each issue, the File line MUST reference a single line number on
the RIGHT side of the diff (the line number in the new/post-change file, not
the pre-change file). If a finding spans a range, pick the most representative
single line on the RIGHT side. This requirement is mandatory because the
orchestrator will post these findings as inline comments on the GitHub PR, and
the GitHub API rejects comments that do not target a line present in the diff.
<end if>

If the diff is genuinely fine and you have no issues, write the Summary and an
empty `## Issues` section (or omit the Issues section entirely). Do not invent
issues to fill space.
```

Wait for the subagent to complete. If it fails, report the error to the user and stop.

After it completes, verify that `<review_file>` exists and is non-empty. If it does not, report the error and stop.

Save the returned `subagent_id` for the report. The reviewer is not resumed; this is a one-shot review.

Report progress: "Review complete. Processing findings..."

### Stack mode (one reviewer subagent per PR)

Spawn one reviewer subagent per `stack_prs` entry with `background: true` so all PRs are reviewed in parallel. Use `subagent_type: "general-purpose"`, `description: "[reviewer] pr #<num>"`, and prepend `reviewer_persona_instructions`.

**Do not pass `capability_mode: read-only`.** It removes the `write` tool needed for each per-PR review and payload. Enforce read-only source behavior in the prompt instead.

Substitute the per-PR values plus the resolved absolute `scratch_dir`, `PYTHON`, `HOST_PY`, run-wide `<approve>`, and run-wide `<submit>` into this prompt:

```
<reviewer_persona_instructions>

---

Review ONE pull request in a stack. Review only this PR's delta, not the whole stack.

PR: #<num> -- <title>
PR URL: <url>
Repo: <owner>/<repo>
REVIEW_ID: <REVIEW_ID>
Approve after review: <approve>
Submit as COMMENT after review: <submit>
Scratch directory: <absolute scratch_dir>
Python: <absolute PYTHON>
Host helper: <absolute HOST_PY>

Treat the three values above as already resolved absolute paths. Inline them in every command. Do not rely on shell variables between `run_terminal_command` calls.

Parallel-safety constraints:
- Run only read-only git and gh commands. Never checkout, switch, reset, stash,
  run `gh pr checkout`, or fetch into a branch. Do not modify the worktree,
  index, or HEAD.
- Write only under the resolved scratch directory. Every filename must include
  both REVIEW_ID and the PR number. Use:
  - <scratch_dir>/grok-review-<REVIEW_ID>-pr<num>.diff
  - <scratch_dir>/grok-review-<REVIEW_ID>-pr<num>.md
  - <scratch_dir>/grok-review-<REVIEW_ID>-pr<num>.json
  - <scratch_dir>/grok-review-<REVIEW_ID>-pr<num>-post.json
  - <scratch_dir>/grok-review-<REVIEW_ID>-pr<num>-post.err
- Pass `--repo <owner>/<repo>` to every `gh pr` call. The `gh api` endpoint
  must include `repos/<owner>/<repo>`.

Steps:
1. Fetch the diff with `gh pr diff <num> --repo <owner>/<repo>` and persist it
   to the per-PR diff file. Fetch `headRefOid` with `gh pr view ... --json
   headRefOid` and parse the JSON yourself or use `gh --jq`. If the diff is
   empty, post nothing, clean up all per-PR artifacts with `<PYTHON> <HOST_PY>
   cleanup`, and report NO CHANGES. Empty diffs are never approved.
2. Read the diff. The shared worktree may be on another branch. Fetch full
   post-change files with `gh api "repos/<owner>/<repo>/contents/<path>?ref=<headSha>"
   -H "Accept: application/vnd.github.raw+json"`; do not checkout the PR.
3. Write structured findings to the per-PR markdown file. Use `## Summary` and
   `## Issues`; severities are bug, suggestion, or nit. Each issue has a
   right-side `File: path:line`, Description, Suggestion, and `Status: open`.
4. Parse right-side diff positions exactly as documented in single-PR mode.
   Inline valid positions and promote missing or out-of-diff findings to the
   review body. Construct the payload as structured data, then persist valid
   JSON with the `write` tool. Do not hand-concatenate JSON and do not use a
   Python heredoc. Set `commit_id` to <headSha>.
5. Post one review:
   - Default, zero issues: post nothing and report NO REVIEW.
   - Default, issues: omit `event` for PENDING and report the `/files` URL.
   - Submit true, zero issues: post nothing and report NO REVIEW.
   - Submit true, issues: set `event` to `COMMENT` and report COMMENTED.
   - Approve true: compare the PR author's login with `gh api user`. If they
     match, do not post; preserve the review markdown, payload, and diff, and
     report ERROR with the self-approval cause. Otherwise set `event` to
     `APPROVE`, including an empty comments array when there are zero issues,
     and report APPROVED.
   On an HTTP 422 caused by an inline position, fold inline findings into the
   body and retry once. Do not retry other failures.
6. On success or a no-post outcome, clean up every per-PR artifact with the
   resolved `<PYTHON> <HOST_PY> cleanup` command. On post failure, preserve the
   review markdown, payload, and diff; clean only post capture files and report
   every preserved path.

Report PR number, verdict, bug/suggestion/nit counts, inline/body counts, final
state (APPROVED, COMMENTED, PENDING, NO CHANGES, NO REVIEW, or ERROR), exact
error text, and preserved paths when applicable.
```

After all launches, call `get_command_or_subagent_output` for all task IDs and wait for every reviewer. Record a failed subagent as ERROR for that PR and continue aggregating the rest.

## Step 3: Handle output based on mode

The post-processing differs by mode: main/local/branch mode writes a summary to disk, single-PR mode posts a review to GitHub, and stack mode aggregates the reviews its subagents already posted.

### Main / Local / Branch mode

1. Read `<review_file>` via `read_file`.
2. Count issues by counting heading lines that match the regex `^### Issue \d+ -- Severity: (bug|suggestion|nit)$` and bucket them by the captured severity. Issues whose heading does not match this pattern (typo'd severity, missing severity field, malformed heading) are malformed -- log a one-line warning to the user listing the heading line and treat them as uncounted. Do not attempt to re-parse the body for a `Severity:` field; the heading is the canonical source. The same regex governs the parsing in Step 3 PR mode below.
3. Compute diff stats:

   ```text
   git -c color.ui=false -c color.diff=false diff --shortstat <range>
   ```

   For local mode, run `git -c color.ui=false -c color.diff=false diff --shortstat HEAD` and also count untracked files separately. For branch mode, inline the resolved merge base and target in `git -c color.ui=false -c color.diff=false diff --shortstat <MERGE_BASE>..<target>`. For main mode, inline the merge base in `git -c color.ui=false -c color.diff=false diff --shortstat <MERGE_BASE>..HEAD`.

   **Color-off on every git diff.** All `git diff` / `git diff --name-only` / `git diff --shortstat` / `git diff --no-index` invocations in this skill MUST pass `-c color.ui=false -c color.diff=false` (or equivalent `NO_COLOR=1` / `GIT_CONFIG_COUNT` overrides). ANSI color codes from a user-enabled `color.ui=always` frequently break agent parsing and force retries; never rely on ambient git color config.

4. Use the `write` tool to create `<summary_file>` with this structure:

   ```markdown
   # Review Summary

   - **Mode**: <mode>
   - **Target**: <target-summary>
   - **Files reviewed**: <count> (<list, truncated to 10 if longer>)
   - **Diff stats**: <shortstat-line>
   - **Issue counts**: <X> bugs, <Y> suggestions, <Z> nits

   ## Top issues

   <First 5 issue titles, one per line, in the form "[severity] file:line -- description (truncated to ~100 chars)">

   See the full review at: <review_file>
   ```

5. Print to the user:
   - Inline issue counts and the file paths to `<review_file>` and `<summary_file>`.

Do NOT delete `<review_file>` or `<summary_file>` in main/local/branch modes -- those files ARE the deliverable.

### PR mode

1. Read `<review_file>` via `read_file` and parse it into a structured representation:
   - Extract the `## Summary` section -- everything after the `## Summary` heading and before the next `## ` heading.
   - Extract each issue by matching heading lines against `^### Issue \d+ -- Severity: (bug|suggestion|nit)$` (same regex as Step 3 Main/Local/Branch mode). For each matched block, capture:
     - `severity` -- the captured group from the heading regex
     - `file` and `line` -- parsed from the `- File: path:line` field. If `:line` is missing, the issue cannot become an inline comment; it must be promoted to the body.
     - `description` -- from the `- Description:` field
     - `suggestion` -- from the `- Suggestion:` field (may be empty)

   **Early-exit on zero issues**: behavior depends on `approve` / `submit`:
   - **`approve` is false and `submit` is false (default):** do NOT walk the diff, build a payload, or post. Print "Reviewer found no issues on PR #<pr_number>. No PENDING review created." Then run no-reviewer cleanup and produce the Final report.
   - **`submit` is true (and `approve` is false):** do not post an empty COMMENT review. Print "Reviewer found no issues on PR #<pr_number>. No COMMENT review created." Then run no-reviewer cleanup and produce the Final report.
   - **`approve` is true:** do NOT skip -- the user asked to approve. Build a payload with `comments: []` and a `body` carrying the `## Summary` and the (zero) issue counts, then post it with `"event": "APPROVE"` (items 4-7 below) so the approval still happens. Continue to item 2 (the diff walk produces an empty inline-comment set, which is fine).

2. Read `<diff_file>` via `read_file` and walk it to determine which `(file, line)` pairs are present on the RIGHT side of any hunk. The line is on the RIGHT side when:
   - It is an added line (prefix `+`, but not the `+++ b/...` header line), OR
   - It is a context line (prefix ` `).

   Walk the diff file by file:
   - Each file section starts with `+++ b/<path>` (treat `+++ /dev/null` as a deletion -- skip).
   - Within a file, each hunk starts with `@@ -<old>[,<oldcount>] +<new>[,<newcount>] @@`. The `,<count>` parts are optional and default to `1` when omitted (so `@@ -42 +42 @@` is a valid single-line hunk that `git diff` and `gh pr diff` both emit). A regex like `^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@` matches both forms; capture `<new>` from the second group. Reset the right-side line counter to `<new>`. (The regex is intentionally unanchored at the end -- real diffs frequently carry trailing context after the second `@@`, e.g. `@@ -10,5 +15,3 @@ def my_function():`, and `re.match` succeeds on the prefix without a `$` anchor. Do NOT add `$`; it would reject every hunk header that includes a function/class hint.)
   - Walk the hunk body. For ` ` (context) and `+` lines (excluding `+++` headers), record the current right-side line and increment the counter. For `-` lines (excluding `---` headers), do not increment the right-side counter.
   - Lines starting with `\ ` (a literal backslash followed by a space) are diff metadata, not file content -- e.g., `\ No newline at end of file`. Skip them: do not increment the right-side counter, and do not contribute a `(file, line)` pair.

   Build a set of `(file, line)` pairs.

3. Partition the parsed issues into two groups:
   - **Inline comments**: issues whose `(file, line)` is in the diff set.
   - **Promoted to body**: issues whose `(file, line)` is missing or not in the diff set.

4. Build the JSON payload via the `write` tool, saving to `<pending_review_payload>`:

   ```json
   {
     "commit_id": "<head_sha>",
     "body": "<assembled body, see below>",
     "comments": [
       {
         "path": "src/foo.rs",
         "line": 42,
         "side": "RIGHT",
         "body": "**[bug]** description text\n\n**Suggestion:** suggestion text"
       }
     ]
   }
   ```

   **The `event` field is conditional on `approve` / `submit`:**
   - If `approve` is false and `submit` is false (default): do NOT include `event`. Omitting it causes the GitHub API to create the review in PENDING state -- the user reviews and submits it through the GitHub UI.
   - If `submit` is true (and `approve` is false): add `"event": "COMMENT"` to the dict. The single `POST .../reviews` call publishes the inline comments + body immediately without approving the PR.
   - If `approve` is true: add `"event": "APPROVE"` to the dict. The single `POST .../reviews` call then publishes the inline comments + body AND approves the PR in one shot.

   The top-level `body` is constructed as:

   ```
   ## Summary

   <verbatim text of the ## Summary section from the review_file>

   ## Issue counts by severity

   - bugs: <X>
   - suggestions: <Y>
   - nits: <Z>

   <if any promoted issues exist, append:>
   ## Issues outside the diff

   These findings reference lines that are not present in the diff and could not be posted as inline comments:

   - **[severity]** file:line -- description
     - **Suggestion:** suggestion text
   <repeat for each promoted issue>
   <end if>
   ```

   Each inline comment body has the form `**[severity]** description\n\n**Suggestion:** suggestion`. If the suggestion is empty, drop the suggestion line.

   **Construct the payload as structured data, then persist it with the `write` tool as valid JSON.** Do not concatenate JSON strings by hand. Do not use a `python <<'PY'` heredoc because `<<` is reserved in PowerShell. Serialize the in-memory object and pass the resulting JSON as the `content` argument for `<pending_review_payload>`. The default object has no `event`; add it only for `submit` or `approve` as specified above.

5. Post the review.

   **Self-approval pre-check (`approve` only):** fetch the PR author with `gh pr view <target> --json author` and the authenticated user with `gh api user`. Parse both JSON responses yourself, or use `--jq` as part of those `gh` commands. If the logins are equal, stop before posting, explain that GitHub forbids self-approval, preserve `<review_file>`, and run failed-post cleanup for the other artifacts. Do not send a knowingly invalid APPROVE request.

   Post with `gh api "repos/<owner>/<repo>/pulls/<pr_number>/reviews" -X POST --input <pending_review_payload>`. Inline the validated owner, repo, PR number, payload path, `<post_file>`, and `<post_error_file>` in a shell-appropriate `run_terminal_command` call that captures stdout and stderr.

6. **Error handling**: if the `gh api` call exits non-zero, surface the captured stderr verbatim to the user along with the HTTP status code (parseable from `gh api`'s stderr message). Do not retry. Common cases by status:
   - **422 Unprocessable Entity**: comments reference lines outside the diff (the diff-line filter missed something, e.g., the reviewer hallucinated a file path), `commit_id` is stale (the PR was force-pushed between Step 1 and now), or the `side` value was rejected. When `approve` is true, a 422 can ALSO mean GitHub refused to let you approve your own PR -- if the stderr says the author cannot approve their own pull request, surface that specific cause clearly (you cannot approve a PR you authored; ask a different reviewer or drop `--approve`) and keep the review file.
   - **403 Forbidden**: authenticated user lacks permission to comment on the PR (read-only collaborator on the repo, archived repo).
   - **404 Not Found**: PR does not exist (the user passed a wrong number, or the URL is in a private repo the user cannot see).
   - **5xx**: GitHub-side outage or transient failure.

   On any error, also keep `<review_file>` on disk (skip the PR-mode review_file deletion in Step 4) so the user can see what would have been posted and either re-run with corrected inputs or submit the notes through some other channel. Mention the preserved path in the error message.

7. On success, the message depends on `approve` / `submit`. In all cases the response is parsed for the review `id`, which is recorded in the Final report; the `html_url` field is not used.

   **`approve` is false and `submit` is false (PENDING):** the user-facing pending-review URL is the PR Files tab, where pending reviews surface and where the "Finish your review" / "Submit review" button lives:

   ```
   https://github.com/<owner>/<repo>/pull/<pr_number>/files
   ```

   Construct this URL from the already-validated `owner`, `repo`, and `pr_number` -- do NOT use the `html_url` field from the GitHub response. The response's `html_url` points at a deep link to the review object that does not surface the submit button as cleanly as the Files tab.

   Print to the user as a structured block (not a wall of text):

   ```
   A PENDING review has been created on PR #<pr_number>.
   - Inline comments: <N>
   - Body findings (outside the diff): <M>
   - Submit at: https://github.com/<owner>/<repo>/pull/<pr_number>/files
     (scroll to "Finish your review" -> click "Submit review").
   Until you submit, the comments are visible only to you.
   ```

   **`submit` is true (COMMENTED):** the review was submitted (published) as a COMMENT review -- comments are visible immediately, the PR is not approved, and there is no PENDING state. Print the PR URL (not the Files-tab submit link):

   ```
   Submitted a COMMENT review on PR #<pr_number> -- comments are visible immediately.
   - Inline comments: <N>
   - Body findings (outside the diff): <M>
   - PR: <pr_url>
   ```

   **`approve` is true (APPROVED):** the review was submitted (published) and the PR approved in the same call -- there is no PENDING state to submit. Print the PR URL instead of the Files-tab submit reminder:

   ```
   Submitted an APPROVING review on PR #<pr_number> -- the PR is now approved.
   - Inline comments: <N>
   - Body findings (outside the diff): <M>
   - PR: <pr_url>
   ```

### Stack mode

In stack mode each subagent already posted its own review in Step 2, so the orchestrator does NOT read review files, build payloads, or post anything in this step. Instead, collect the structured result each subagent reported back and aggregate:

1. For each PR in `stack_prs`, record from its subagent's report: verdict, issue counts by severity, inline-comment count, body-finding count, final state (APPROVED / COMMENTED / PENDING / NO CHANGES / NO REVIEW / ERROR), and any error text.
2. Carry these into the Final report's stack summary table (Step 5).

The orchestrator wrote no per-PR review/diff/payload files in this mode, so there is nothing for it to read or clean up beyond what each subagent already removed (see Step 4).

## Step 4: Cleanup

Cleanup is asymmetric by mode and outcome:

- **Main, local, and branch:** keep `<review_file>` and `<summary_file>`. Remove only `<diff_file>` and `<files_file>`.
- **PR successful post:** remove `<review_file>`, `<diff_file>`, `<pending_review_payload>`, `<prmeta_file>`, `<files_file>`, `<post_file>`, and `<post_error_file>`.
- **PR failed post:** keep `<review_file>` and remove the other PR artifacts. Mention the preserved review path.
- **PR no reviewer output:** remove `<review_file>`, `<diff_file>`, `<pending_review_payload>`, `<prmeta_file>`, and `<files_file>`. Missing files are harmless.
- **Stack:** each subagent owns cleanup of its per-PR paths. It removes them after a successful post or no-post result and preserves the review, payload, and diff after a failed post. The orchestrator has no stack artifacts to remove.

For every cleanup, run the resolved `<PYTHON> <HOST_PY> cleanup <paths...>` command with absolute paths. Missing files are allowed. Do not use a shell deletion command. `--approve` and `--submit` use the same successful-post cleanup as the default PR path.

## Step 5: Final report

Present a final report to the user. Item 1 is always included; item 2 is omitted on empty-diff exits; item 3 is omitted on empty-diff exits and on PR zero-issue early-exits; item 4 is always included. In **stack mode**, items 2-3 are subsumed by the per-PR table in item 4 (the orchestrator collected no single combined diff); item 1 still names the mode and lists the stack.

1. **Mode + target** -- e.g., "Current branch vs origin/main" (main mode) or "Local changes" or "Branch feature/foo vs origin/main" or "PR #4221: <pr_title>".
2. **Files reviewed** -- count and (if 10 or fewer) the list. Omit on empty-diff exits.
3. **Issues by severity** -- the bug/suggestion/nit counts. Omit on empty-diff exits and on PR zero-issue early-exits (counts are all zero by construction; the mode-specific bullet says so).
4. **Mode-specific output**:
   - Main / local / branch (successful review): full paths to `<review_file>` and `<summary_file>`, plus a one-line copy of the summary's top-issues list.
   - Main / local / branch (empty-diff exit): "No changes to review." (local mode) or "Branch has no changes vs <BASE>." (main mode) or "Branch <target> has no changes vs <BASE>." (branch mode). No file paths -- nothing was written.
   - PR (successful post): the structured block from Step 3 PR mode item 7, plus the review `id` from the response (for traceability). Default: the PENDING submit block (PR number, inline-comment count, body-findings count, Files-tab URL, submit reminder). If `submit` was true: the COMMENTED block (PR URL, comments already visible, no submit reminder). If `approve` was true: the APPROVED block stating the review was submitted (published) and the PR approved, with the PR URL and no submit reminder.
   - PR (zero-issue early-exit, no approve, no submit): "Reviewer found no issues on PR #<pr_number>. No PENDING review created."
   - PR (zero-issue, submit): "Reviewer found no issues on PR #<pr_number>. No COMMENT review created."
   - PR (zero-issue, approve): "Reviewer found no issues on PR #<pr_number>. Submitted an empty APPROVING review -- the PR is now approved."
   - PR (empty-diff exit): "PR #<pr_number> has no changes. Nothing to review." (if `--approve` was passed, add "Not approved -- an empty-diff PR has no changes to approve.")
   - PR (failed post): the verbatim stderr from `gh api` plus the HTTP status code, plus the preserved path to `<review_file>` so the user can recover the findings. If the failure was a self-approval 422, state that cause explicitly.
   - Stack (all PRs reviewed): a summary table over every PR in `stack_prs`, one row each, plus a totals line:

     ```
     PR    | Title              | bugs/sugg/nits | State    | Error
     #4221 | Add foo to bar     | 1/2/0          | APPROVED | -
     #4222 | Wire bar into baz  | 0/0/1          | APPROVED | -
     #4223 | Update callers     | 0/0/0          | APPROVED | -
     Totals: 3 PRs, 1 bug, 2 suggestions, 1 nit; 3 approved, 0 commented, 0 pending, 0 errored.
     ```

     Each row's State reflects that PR's own outcome: APPROVED (reviewed with `--approve`), COMMENTED (issues found and submitted with `--submit`), PENDING (issues found, no modifier -- default), NO CHANGES (empty diff -- never auto-approved), NO REVIEW (zero issues and not approving -- nothing posted), or ERROR (subagent failed to post; put the exact error text in the Error column). The totals line counts approved / commented / pending / errored PRs; NO CHANGES and NO REVIEW rows are shown but fall outside those buckets. (Because the modifiers are run-wide, APPROVED, COMMENTED, and PENDING do not mix within one run -- but errored / no-change / no-review rows can still appear alongside any.)

## In-Progress Reporting

Give the user a brief status update after each phase:

- After argument parsing: "Reviewing <mode> target: <target-summary>." (omit target for local mode -- "Reviewing local changes." -- and for main mode -- "Reviewing this clean branch vs its base branch."; the exact base ref is not resolved until Step 1, so do not template a specific ref into this line). When no flag was given, say which mode the default chose and why (e.g. "Working tree is clean, so reviewing the whole branch vs its base branch.").
- After Step 1 (diff collection): "Collected diff (<N> files, <M> changed lines). Launching reviewer..."
- After Step 1 (empty diff): "No changes to review. Proceeding to final report."
- After Step 1 (stack discovery): "Discovered N-PR stack: #a, #b, #c (base->tip). Launching reviewers..."
- After Step 2 (stack launch): "Launched N reviewers (one per PR) in parallel."
- After all stack subagents complete: "All stack reviewers complete. Aggregating results..."
- After Step 2 (reviewer complete): "Review complete. Processing findings..."
- After Step 3 (main / local / branch): "Found N issues (X bugs, Y suggestions, Z nits). Wrote <review_file> and <summary_file>."
- After Step 3 (PR, zero issues, no approve, no submit): "Reviewer found no issues on PR #<pr_number>. No PENDING review created."
- After Step 3 (PR, zero issues, submit): "Reviewer found no issues on PR #<pr_number>. No COMMENT review created."
- After Step 3 (PR, zero issues, approve): "Reviewer found no issues on PR #<pr_number>. Submitted an empty APPROVING review; PR approved."
- After Step 3 (PR, success, no approve, no submit): "Posted PENDING review with N inline comments and M body findings. Visit <url> to submit."
- After Step 3 (PR, success, submit): "Submitted COMMENT review on PR #<pr_number> with N inline comments and M body findings."
- After Step 3 (PR, success, approve): "Submitted and APPROVED review on PR #<pr_number> with N inline comments and M body findings."
- After Step 3 (PR, error -- 422 or any other non-zero exit): "Failed to post review. HTTP <status>. GitHub returned: <verbatim stderr>. Review notes preserved at <review_file>."
- After Step 3 (stack): one line per PR -- "PR #<num>: <APPROVED | COMMENTED | PENDING | NO CHANGES | NO REVIEW> -- X bugs, Y suggestions, Z nits." (or that PR's error) -- followed by "Stack review complete: <P> PRs, <A> approved, <C> commented, <Pn> pending, <E> errored."

## Rules

- **Reviewer is read-only** -- the reviewer subagent must never modify source files (it only writes its review/diff/payload artifacts under `scratch_dir`). The orchestrator must never modify source files either. The only writes are to `<review_file>`, `<summary_file>`, `<diff_file>`, `<pending_review_payload>`, the per-PR artifacts under `scratch_dir` in stack mode, and the GitHub review (PENDING by default; COMMENT with `--submit`; APPROVED with `--approve`).
- **Inject the reviewer persona into the prompt** -- always prepend the `reviewer` persona instructions (from the shared personas file) to the subagent prompt. Do NOT pass a `persona` parameter to `spawn_subagent`.
- **Prefix `description` with `[reviewer]`** -- the pager's subagent label renderer parses the first `[tag]` of the description and uses it as the row label (the bracketed prefix is stripped from the displayed description). Without it, the row falls through to the generic "General" label because `subagent_type` is `general-purpose` and no persona/role is plumbed through the spawn args.
- **Include context in the reviewer prompt** -- the reviewer needs the conversation context (the user's framing, any constraints, etc.) passed through the task prompt.
- **One reviewer per PR** -- main, local, branch, and single-PR modes run exactly one reviewer. Stack mode runs one reviewer per PR in the stack, in parallel. Multi-reviewer runs during an implement-fix loop are `/implement --effort N`.
- **Disambiguation is deterministic** -- the auto-detect rules in argument parsing are applied in order. Do not second-guess them. If the rules do not match, ask the user; do not guess.
- **Empty diffs short-circuit** -- never launch the reviewer with an empty diff. Report "no changes", run cleanup, and produce a Final report (using the appropriate "empty-diff exit" bullet). An empty-diff PR is never auto-approved, even with `--approve` (no changes to review = nothing to approve). In stack mode the orchestrator cannot pre-check diffs, so each subagent short-circuits its own empty-diff PR (posts nothing, reports NO CHANGES).
- **Zero issues short-circuits PR mode (unless approving)** -- if the reviewer finds nothing on a PR and `--approve` was NOT passed, do not post an empty review (PENDING or COMMENT); print a "no issues found" message, clean up, and stop. If `--approve` WAS passed, still post an APPROVE review with empty `comments` and a body summary so the approval happens. Each stack subagent applies this same rule to its own PR (reporting NO REVIEW when it skips the post).
- **PR and stack modes require `gh` auth** -- if `gh auth status` fails, stop with a clear instruction to run `gh auth login`. Do not try to work around it.
- **PENDING reviews are the default; `--submit` and `--approve` opt in to published events** -- by default the review payload omits the `event` field, so the review lands in PENDING state and the user submits it via the GitHub UI (print the Files-tab URL plus the submit-via-UI reminder). `--submit` posts with `event: COMMENT` (publish immediately, no approval). `--approve` posts with `event: APPROVE` (publish + approve). In single-PR mode the orchestrator sets the event; in stack mode each subagent sets it (and MUST receive both `<approve>` and `<submit>` substitutions -- never leave either placeholder unsubstituted).
- **Git diffs must disable color** -- every `git diff` (including `--name-only`, `--shortstat`, `--no-index`) MUST run with `-c color.ui=false -c color.diff=false` (or equivalent `NO_COLOR=1`). Colored diffs break agent parsers and cause retries.
- **Filter inline comments to lines actually in the diff** -- GitHub returns 422 for comments on lines outside the diff. The orchestrator (single-PR mode) or each subagent (stack mode) parses the diff itself to validate `(file, line)` pairs and promotes any out-of-diff issues to the top-level body as bullet points.
- **Stack mode is read-only and parallel-safe** -- stack subagents share one working tree, so they must run only read-only git/gh commands (never checkout/switch/reset/stash/`gh pr checkout`/`git fetch ...:branch`) and write only under the resolved `scratch_dir` using per-PR-unique filenames that embed BOTH the `REVIEW_ID` and the PR number. Each subagent reads post-change file content via `gh api .../contents?ref=<headSha>` rather than checking out the branch, and removes its own temp files when done.
- **`--approve` forbids self-approval** -- GitHub rejects approving your own PR. Single-PR mode and every stack reviewer compare the PR author with the authenticated user before posting. On a match, do not post, surface the cause, and preserve the review artifacts.
- **`--approve` and `--submit` are PR-only and mutually exclusive** -- both modifiers are valid only with `--pr` and `--stack`; combining either with main, local, or branch mode (including an auto-detected branch) is rejected during argument parsing. Passing both together is rejected with `--approve and --submit are mutually exclusive.`
- **Surface every `gh api` error verbatim** -- if the GitHub API call exits non-zero (422, 403, 404, 5xx, anything else), do not retry, with one exception: a stack subagent may perform the single documented fold-into-body retry on a 422 (per Step 2 Stack mode) before reporting failure. Show the user the raw stderr plus the HTTP status code so they can debug, and preserve `<review_file>` on disk so the findings are not lost.
- **Helpers stay host-focused** -- use `shared/scripts/host.py` for setup and cleanup and `scripts/collect_local_diff.py` for local changes. Keep review markdown parsing and payload assembly inline.
- **Cleanup is asymmetric by mode and outcome** -- main/local/branch modes keep `<review_file>` and `<summary_file>` (they are the deliverable). PR mode removes `<review_file>` on a successful post (the GitHub review -- PENDING, COMMENT, or APPROVED -- is the deliverable) and on a no-reviewer-output exit (zero issues OR empty diff -- nothing actionable to preserve), but preserves it on a failed post so the user can recover the findings. In stack mode each subagent cleans up its own per-PR temp files and the orchestrator has nothing extra to remove.
- **Thread the same file paths** across all steps -- never regenerate paths between steps. The `REVIEW_ID` is fixed for the run.
- **Error handling** -- if the reviewer subagent fails, the diff collection fails, or the GitHub API call fails, report the error to the user and stop. Do not silently continue with missing results. EXCEPTION (stack mode): a single per-PR subagent failure does NOT abort the run -- record it against that PR, show it as `ERROR` in the stack table, and keep aggregating the other PRs (per Step 2 Stack mode).
- **No emojis in output** -- match the conventions of the `reviewer` persona instructions and the surrounding skills.

## Design notes

These are background notes that explain the rationale behind some of the choices above. They are NOT rules; they are pointers for future maintainers.

- **Main mode reviews the current branch tip.** It is selected only when the working tree is clean and compares `MERGE_BASE..HEAD`. Local mode remains the owner of staged, unstaged, and untracked changes through `collect_local_diff.py`; named branch mode compares `MERGE_BASE..<target>`.
- **The bare `/review` default trades one previously-empty case for a useful one.** Before this change a bare `/review` always meant local mode, so on a clean tree (everything committed) it reported "no changes to review" and did nothing. The default keeps local mode whenever the tree is dirty (no regression for the common mid-edit gut-check) and only switches to main mode when local mode would otherwise have been a no-op. GitHub-writing modes stay strictly opt-in: a bare `/review` never resolves to `--pr` or `--stack`, so it can never post to GitHub on its own.
- **Host helpers do not own review parsing.** `shared/scripts/host.py` owns portable setup and cleanup. `scripts/collect_local_diff.py` owns portable local diff collection. Review markdown parsing, unified-diff hunk walking, and GitHub payload assembly stay inline.
- **Owner/repo are derived from the PR `url`, not from a `baseRepository` field.** `gh pr view --json baseRepository` returns `Unknown JSON field: "baseRepository"` -- only `headRepository`, `headRepositoryOwner`, and `isCrossRepository` are exposed. Parsing the URL is the simplest universal approach and works correctly for cross-repo PRs.
- **The constructed `/files` URL is used for PENDING output only, not the response's `html_url`.** The Files tab is where the "Finish your review" / "Submit review" button surfaces in the GitHub UI; that is what the user needs for a PENDING review. The response's `html_url` deep-links to the review object and is less useful for this workflow. When `--submit` or `--approve` is used there is no PENDING state and no submit button, so the user output reports the PR URL instead.
- **Default stays PENDING; `--submit` opts into COMMENT (2026-07-27).** Changing the default would surprise users who open GitHub to iterate on draft reviews before publishing. `--submit` mirrors `--approve` as an explicit opt-in for a published event (`event: COMMENT` vs `event: APPROVE`) without flipping the default.
- **Color-off on git diffs.** Agents parse unified diffs as plain text; ANSI color sequences from `color.ui=always` corrupt that parse and force retries. The skill pins `-c color.ui=false -c color.diff=false` on every `git diff` invocation rather than relying on ambient config.
- **Stack subagents post their own reviews; the orchestrator does not.** A stack can be 8+ PRs; collecting every diff and posting every review from the orchestrator would serialize the work and bloat its context. Spawning one read-only subagent per PR parallelizes the reviews. Because they share one working tree, each subagent reads post-change content via `gh api .../contents?ref=<headSha>` instead of checking the branch out, and writes only per-PR-unique files under `scratch_dir` (REVIEW_ID + PR number) so concurrent subagents never collide.
- **Stack discovery is a deterministic walk over open PRs.** Rather than depend on the `gh` Graphite extension (not guaranteed installed), the skill fetches all open PRs once and walks the `baseRefName`->`headRefName` chain down to the base and up to the tip. This needs only core `gh` and degrades gracefully (a PR with no neighbors is reviewed alone; a branching stack includes all reachable descendants).
