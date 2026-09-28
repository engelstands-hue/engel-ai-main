---
name: pr-babysit
description: >-
  Monitor PRs, fix CI failures, address review comments (human and bot/automated),
  resolve merge conflicts, and restack stacks. Supports independent PRs, Graphite
  stacks, and GitHub stacked PRs (gh-stack). Optional ship lands a ready PR
  bottom-up when every job has passed and no comments remain open.
when-to-use: Triggers on "/pr-babysit".
argument-hint: "add [--ship] <number> | remove <number> | list | check | ship [on|off] [number...]"
disable-model-invocation: true
---

# PR Babysitter

You are a PR babysitter agent. Your job is to monitor GitHub pull requests, detect issues (CI failures, human and bot/automated review comments, merge conflicts), and fix them autonomously. Fixes and commits happen **only** inside subagents (spawned via `spawn_subagent`) with worktree isolation — never as direct orchestrator edits on the main workspace. You support three PR topologies:

1. **Independent PRs** — standalone PRs targeting the default branch.
2. **Graphite stacks** — stacked PRs managed by the Graphite CLI (`gt`). Detected via `gt` metadata or API-based chain walking.
3. **GitHub stacked PRs** — stacked PRs managed by the `gh stack` CLI extension. Detected via `gh stack checkout` or API-based chain walking.

Designed for use with `/loop`: `/loop 5m /pr-babysit check`. To also land ready PRs, add with `--ship` (or run `ship on`) so each check cycle ends in the ship cycle. Shipping is opt-in. The default still stops at merge-ready.

Load `references/shipping.md` when the command is `ship`, `ship on`, or `ship off`, or when a check cycle sees any watched PR with `ship: true`.

## Todo Scaffold

For each PR being babysat, create three todos:
- `pr-<n>:ci-green` — all CI checks passing
- `pr-<n>:comments-addressed` — all open review comments (human and bot/automated) either fixed+resolved or replied to substantively
- `pr-<n>:merge-ready` — labels applied, base up to date, ready to merge

When `ship` is true, also create `pr-<n>:shipped`. That todo completes only when the PR is MERGED.

Terminal state: all `pr-<n>:merge-ready` complete, or all `pr-<n>:shipped` complete when shipping is on. Persist polling between turns via background subagents or scheduler tasks. **Note on backing:** the gate's heuristic requires `|in_progress_todos| ≤ count(live backing tasks)` for backing to apply (see `<task_completion_discipline>` Rule 4 for the full backing-detection rules). For `/pr-babysit` this means one polling subagent per PR you're babysitting, not one shared poller for all of them — otherwise the gate correctly classifies the excess in_progress todos as unbacked and will nudge.

**Reseed after compaction** — the harness no longer emits a pre-compaction todo snapshot, so if a compaction lands mid-cycle the orchestrator must rebuild its todo scaffold from the persisted PR list (see §State File of this skill). Reseed before doing anything else: read the state file, regenerate the per-PR `pr-<n>:ci-green` / `pr-<n>:comments-addressed` / `pr-<n>:merge-ready` triples for every watched PR, plus `pr-<n>:shipped` when that PR has `ship: true`.

## Commands

Dispatch based on the first argument. If no arguments are provided, show usage help.

| Command | Behavior |
|---------|----------|
| `add [--ship] <number> [<number>...]` | Add PR(s) to the watchlist. Auto-detect stack membership (Graphite or GitHub stacked PRs) and register the entire stack. `--ship` sets `ship: true` on every PR registered in this invocation. |
| `remove <number>` | Remove the specified PR from the watchlist. Only removes that single PR, even if it belongs to a stack. |
| `list` | Show all watched PRs grouped by stack, with status, last checked time, fix count, and ship flag. |
| `check` | Run one check cycle — query each PR, detect issues (CI, human + bot review, conflicts), fix them. If any PR has `ship: true`, run the ship cycle after every group finishes, one group at a time. |
| `ship on [number...]` | Enable shipping. See `references/shipping.md`. |
| `ship off [number...]` | Disable shipping. See `references/shipping.md`. |
| `ship [number...]` | Enable if numbers are given, then run one ship cycle. See `references/shipping.md`. |

## State File

The state file is **per-session** so that concurrent Grok sessions do not interfere with each other. Subagent IDs and worktree paths are session-scoped and cannot be shared across sessions.

Path: `~/.grok/plugin-data/pr-babysit/watched-prs-<INSTANCE_ID>.json`

The `<INSTANCE_ID>` is a UUID generated once per session on the first `add` command and stored inside the state file. This avoids relying on any external session ID (which is not exposed to the model).

### State file lifecycle

1. **First `add` in a session**: Resolve `HOST_PY` as `<dirname of this SKILL.md>/../shared/scripts/host.py`. Find a real Python 3 interpreter (`python`, then `py -3`, then `python3`; reject `WindowsApps`). Generate a UUID via `<python> <HOST_PY> uuid --full`. Create the state file with that UUID embedded, and persist the filename. Hold the `INSTANCE_ID` in memory for the rest of the session.
2. **Subsequent `add` / `remove` / `list` / `check` / `ship` calls in the same session**: The agent already knows the `INSTANCE_ID` from the first `add` call (it is in the conversation context). Use the same filename.
3. **`/loop` scheduled calls**: The `/loop` scheduler fires within the same session, so the agent's conversation context retains the `INSTANCE_ID`. If for any reason the `INSTANCE_ID` is not in context (e.g., after context compaction), scan `~/.grok/plugin-data/pr-babysit/` for `watched-prs-*.json` files and select the one whose `instance_id` field matches a file modified recently, or whose PRs match the current repo. If exactly one file matches the current repo, use it.

Create the directory and file if they do not exist:

Create `~/.grok/plugin-data/pr-babysit` if needed (file tool or `New-Item -ItemType Directory -Force` / `mkdir`). Then:

```
<PYTHON> <HOST_PY> uuid --full
```

Initialize with:

```json
{
  "instance_id": "<INSTANCE_ID>",
  "prs": [],
  "groups": {}
}
```

Full schema for a watched PR entry:

```json
{
  "number": 170734,
  "repo": "xai-org/xai",
  "branch": "skory/feature-part-1",
  "stack_id": "abc123",
  "stack_type": "graphite",
  "stack_position": 0,
  "added_at": "2026-04-13T12:00:00Z",
  "last_checked": "2026-04-13T12:05:00Z",
  "last_status": "healthy",
  "check_count": 12,
  "fix_count": 2,
  "ship": false,
  "ship_status": null,
  "ship_blocked_reason": null
}
```

Fields:
- `number` — GitHub PR number.
- `repo` — Repository in `owner/name` format.
- `branch` — Head branch name.
- `stack_id` — Shared identifier for PRs in the same stack (`null` if standalone). For Graphite stacks, this is the bottom branch name. For GitHub stacked PRs, this is `"gh-stack-<bottom_pr_number>"`.
- `stack_type` — One of: `"graphite"`, `"github"` (GitHub stacked PRs via `gh stack`), or `null` (standalone/plain git). Determines which CLI tool is used for restack/push operations.
- `stack_position` — Distance from trunk (0 = closest to trunk, i.e. bottom of stack).
- `added_at` — ISO 8601 timestamp when the PR was added.
- `last_checked` — ISO 8601 timestamp of last check cycle.
- `last_status` — One of: `"healthy"`, `"ci_failed"`, `"ci_needs_attention"`, `"changes_requested"`, `"review_comments"`, `"conflicts"`, `"pending"`, `"mergeable_unknown"`, `"error"`, `"ship_armed"`, `"ship_blocked"`.
- `check_count` — Total number of check cycles run against this PR.
- `fix_count` — Total number of automated fixes applied.
- `ship` — `true` when the ship cycle may land this PR. Default `false`. Enabling ship on any PR that has a non-null `stack_id` sets `ship: true` on every PR that shares that `stack_id`. Do not fan out when `stack_id` is `null`.
- `ship_status` — `null`, `"armed"` (merge-when-ready is on and the queue may drain), or `"blocked"` (frontier failed a ship-ready gate).
- `ship_blocked_reason` — short reason when `ship_status` is `"blocked"`, else `null`.

Full schema for the `groups` map (tracks subagents and worktrees per non-overlapping group):

```json
{
  "groups": {
    "<group_key>": {
      "subagent_id": "019d91b8-21e0-7c41-91a0-2b163d2c5481",
      "worktree_path": "/path/to/worktree"
    }
  }
}
```

- `<group_key>` — the `stack_id` for stacks or `"pr-<number>"` for standalone PRs.
- `subagent_id` — ID of the last subagent that processed this group. Used with `resume_from` to continue the subagent's conversation across check cycles.
- `worktree_path` — absolute path to the worktree created by `spawn_subagent`. Referenced for cleanup when all PRs in the group are removed.

When a group is cleaned up (all PRs removed), delete its `groups[group_key]` entry.

**Multi-repo safety**: The check cycle determines the current repo via:

```bash
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

Only process PRs whose `repo` field matches this value. Split `nameWithOwner` into `OWNER` and `REPO` for API calls.

## Adding PRs

When the user runs `/pr-babysit add [--ship] <number> [<number>...]`:

If `--ship` is present, set `ship: true` on every PR registered in this invocation (the whole stack when a stack is detected). Otherwise leave `ship` at the default `false`.

### Step 1: Verify authentication

```bash
gh auth status
```

If not authenticated, report the error and stop.

### Step 2: Fetch PR details

For each PR number:

```bash
gh pr view <number> --json headRefName,baseRefName,url,title,state,number
```

Verify the PR exists and is open. If MERGED or CLOSED, inform the user and skip.

Determine the current repository:

```bash
gh repo view --json nameWithOwner --jq '.nameWithOwner'
```

Store this value as the `repo` field for all PR entries created in this invocation.

### Step 3: Detect stack membership

Stack detection determines whether the PR is standalone or part of a stack (Graphite or GitHub stacked PRs). Three methods are tried in order; the first one that finds a multi-branch stack wins.

#### Method A: API-based chain detection (universal, always runs first)

This method works regardless of which tool created the stack. It detects any chain of PRs where each PR's base branch is another PR's head branch.

```bash
# Get the default branch for the repo
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')

# Get the base branch of the added PR
BASE=$(gh pr view <number> --json baseRefName --jq '.baseRefName')
HEAD=$(gh pr view <number> --json headRefName --jq '.headRefName')
```

If `BASE == DEFAULT_BRANCH`, the PR might still be mid-stack (other PRs could target its head branch). Check both directions:

Fetch all open PRs in the repo once and reuse for both directions:

```bash
# Fetch all open PRs in the repo (used for both downstack and upstack walks)
ALL_PRS=$(gh pr list --state open --json number,headRefName,baseRefName --limit 200)
```

**Walk downstack** (toward trunk): Starting from the added PR, follow `baseRefName` by looking up which open PR’s `headRefName` matches the current PR’s `baseRefName`. Repeat until `baseRefName == DEFAULT_BRANCH`.

**Walk upstack** (away from trunk): Find open PRs whose `baseRefName` matches the current PR’s `headRefName`, and continue upward. Repeat until no more PRs are found.
The result is an ordered list of `(number, headRefName, baseRefName)` tuples, sorted bottom-up (closest to trunk first).

If only one PR was found (no chain), this PR is standalone. Proceed to Step 4.

If multiple PRs were found, this is a stack. Continue to Method B/C to determine the stack type and tool.

#### Method B: Graphite CLI detection

Run only if the API chain detected multiple PRs.

```bash
# Check if graphite CLI is available
gt --help 2>/dev/null | grep -qi graphite
```

If graphite is available:

```bash
git fetch origin <headRefName>
gt checkout <headRefName> 2>/dev/null
```

If `gt checkout` succeeds (the branch is tracked by graphite locally), verify the stack by walking:

```bash
# Go to the bottom of the stack
gt bottom 2>/dev/null

# Collect branches bottom-up
STACK_BRANCHES=()
while true; do
  BRANCH=$(git branch --show-current)
  STACK_BRANCHES+=("$BRANCH")
  # Try to move up; if gt up fails, we're at the top
  gt up 2>/dev/null || break
done
```

If `gt checkout` fails (branch not tracked — **common when the PR was created on a different machine**), import the stack into graphite using the API-detected chain:

```bash
# Sync graphite metadata from remote.
# Warning: --force overwrites all local Graphite metadata. This is safe in the
# cross-machine scenario but could disrupt other locally-tracked Graphite stacks.
# Log whether this succeeds or fails for debugging.
gt sync --force --no-interactive 2>/dev/null || true

# Try checkout again after sync
gt checkout <headRefName> 2>/dev/null
```

If checkout still fails, manually track each branch in the chain using the API-detected topology:

```bash
# Save current branch to restore after tracking
ORIG_BRANCH=$(git branch --show-current || echo "main")

# For each branch in the API-detected chain (bottom-up order):
# First branch's parent is the default branch
git fetch origin
for i in "${!CHAIN_BRANCHES[@]}"; do
  BRANCH="${CHAIN_BRANCHES[$i]}"
  if [ $i -eq 0 ]; then
    PARENT="$DEFAULT_BRANCH"
  else
    PARENT="${CHAIN_BRANCHES[$((i-1))]}"
  fi
  git checkout -B "$BRANCH" "origin/$BRANCH" 2>/dev/null
  gt track --parent "$PARENT" --no-interactive 2>/dev/null || true
done

# Restore original branch to avoid polluting the main workspace
git checkout "$ORIG_BRANCH" 2>/dev/null || git checkout "$DEFAULT_BRANCH" 2>/dev/null
```

After tracking, verify with `gt bottom` / `gt up` as above. If the walk succeeds and matches the API-detected chain, set `stack_type: "graphite"`.

If graphite tracking still fails (e.g., `gt track` rejects the branch, repo not initialized), fall through to Method C.

#### Method C: GitHub Stacked PRs detection

Run only if Method B did not claim the stack (graphite not available or tracking failed).

**Note**: GitHub Stacked PRs (`gh stack`) is currently in private preview. If the repository does not have the feature enabled, `gh stack` commands will fail even if the extension is installed. In that case, Method C falls through and the stack is treated as a plain git chain.

```bash
# Check if gh-stack extension is installed (don't use `gh stack view` — it exits
# non-zero (code 2) when the current branch isn't in a tracked stack, giving
# false negatives even when the extension is installed)
gh extension list 2>/dev/null | grep -q gh-stack
```

If `gh stack` is installed:

```bash
# Try to check out the stack from the PR number
# Exit code 2 = not a GitHub stack (fall through)
# Exit code 4 = API failure (log error, fall through)
# Exit code 0 = success
gh stack checkout <number> 2>/dev/null
```

If `gh stack checkout` succeeds (exit code 0):

```bash
# Get the stack structure
STACK_JSON=$(gh stack view --json 2>/dev/null)
```

Parse `STACK_JSON` to extract the ordered list of branches and their PR numbers. Set `stack_type: "github"`.

If `gh stack checkout` exits with code 2 (not a GitHub stack), fall through silently. If it exits with code 4 (API failure), log a warning and fall through. For any other non-zero exit code, log and fall through.

If `gh stack` is not installed, fall through.

#### Final classification

| Condition | `stack_type` | `stack_id` |
|-----------|-------------|------------|
| Method B succeeded (graphite tracks the stack) | `"graphite"` | Bottom branch name |
| Method C succeeded (GitHub stacked PR) | `"github"` | `"gh-stack-<bottom_pr_number>"` |
| API chain found multiple PRs but neither tool claims them | `null` | `"chain-<bottom_pr_number>"` |
| Only one PR found (no chain) | `null` | `null` |

For all stack types, assign `stack_position` by index: 0 = bottom (closest to trunk), incrementing upward.

For each branch in the stack, resolve its PR number:

```bash
gh pr view <branch> --json number --jq '.number'
```

If `gh pr view <branch>` fails for a branch (no associated PR, or PR is closed), skip that branch and warn the user.

### Step 4: Register PR(s)

Register the PR(s) determined by Step 3:
- **Stack detected**: Register **all** PRs in the stack with the appropriate `stack_id`, `stack_type`, and `stack_position`.
- **No stack detected**: Register the single PR with `stack_id: null`, `stack_type: null`, and `stack_position: 0`.

### Step 5: Write state and report

- Deduplicate: skip any PR number + repo combination already in the watchlist. If `--ship` was passed and the PR is already watched, set `ship: true` on that PR. If that PR's `stack_id` is a non-null string, also set `ship: true` on every other PR that shares that `stack_id`. Do not match other PRs when `stack_id` is `null`.
- Write the updated state file.
- Report what was added, including stack information if applicable.

For multiple PR numbers (`add 123 456 789`): process each number, dedup across all of them.

## Removing PRs

When the user runs `/pr-babysit remove <number>`:

1. Read the state file.
2. Determine the current repo.
3. Find the PR entry matching both `number` and `repo`. If none, report "not found" and stop.
4. If that PR is armed under `ship: true` (see Drain), load `references/shipping.md` and run **Disarm** first. Confirm the queue is off before dropping the entry. If disarm cannot be confirmed, leave the entry in the watchlist and report `ship_blocked`.
5. Remove the PR entry. Write the updated state file.
6. Report confirmation.

## Listing PRs

When the user runs `/pr-babysit list`:

1. Read the state file.
2. Determine the current repo. Filter to PRs matching the current repo.
3. Display a table: Number | Branch | Status | Last Checked | Fixes | Ship.
4. Group by `stack_id`. Show standalone PRs separately.
5. Ship column: `off` when `ship` is false, `on` when `ship` is true and `ship_status` is null, `armed` when `ship_status` is `"armed"`, `blocked` when `ship_status` is `"blocked"`.

## Shipping

Load `references/shipping.md` and follow it. That file owns the ship-ready gates, the bottom-up frontier, Graphite merge-when-ready, and the ban on GitHub auto-merge for stacked children.

The check-cycle fix subagent never merges. Only the ship cycle merges, and only the frontier, and only when every gate passes on a fresh query.

## Check Cycle

This is the core loop. It runs on manual `/pr-babysit check` and on scheduled triggers via `/loop`.

### Step 1: Prerequisites

1. Verify authentication:
   ```bash
   gh auth status
   ```

2. Determine the current repo:
   ```bash
   gh repo view --json nameWithOwner --jq '.nameWithOwner'
   ```
   Split into `OWNER` and `REPO` for API calls.

3. Fetch latest refs:
   ```bash
   git fetch origin
   ```

### Step 2: Read state and validate

1. Read the state file. If it does not exist, create the default and exit.
   **State migration**: After reading, check each PR entry for missing fields added in later versions (`stack_id`, `stack_type`, `stack_position`, `ship`, `ship_status`, `ship_blocked_reason`). If any field is missing, backfill with defaults: `stack_id: null`, `stack_type: null`, `stack_position: 0`, `ship: false`, `ship_status: null`, `ship_blocked_reason: null`. Also ensure `groups` key exists (default `{}`). Re-persist the state file after migration. This ensures backward compatibility with legacy state files created before stack support was added.
2. Filter `prs` to only those matching the current repo.
3. If the filtered list is empty: clean up any stale `groups` entries (run Step 7 cleanup for all remaining groups that no longer have associated PRs, then clear the `groups` map and re-persist the state file). Then call `scheduler_list`. If any scheduled task's prompt contains `pr-babysit`, call `scheduler_delete` with that task's ID to self-terminate the loop. Report "No PRs in watchlist" and exit.

### Step 3: Group, order, and identify non-overlapping groups

Group PRs by `stack_id`. Process stacks **bottom-up** (ascending `stack_position`). Process standalone PRs (`stack_id: null`) in any order.

Identify **non-overlapping groups** for parallel processing:
- Each stack (set of PRs sharing the same `stack_id`, regardless of `stack_type`) is one group.
- Each standalone PR (`stack_id: null`) is its own group.
- These groups are independent and will be processed in parallel via separate worktrees and subagents.
- The `stack_type` field determines which CLI tool the subagent uses for restack/push operations within each group.

### Step 4: Parallel Processing with Worktrees

For each non-overlapping group identified in Step 3, launch a subagent to process it in parallel. `spawn_subagent`'s `isolation: "worktree"` parameter handles worktree creation automatically.

#### 4a. Subagent dispatch

Launch one subagent per non-overlapping group by calling `spawn_subagent`. Use a `group_key` to identify each group: the `stack_id` for stacks or `"pr-<number>"` for standalone PRs.

**Launch order**: Launch subagents one at a time (sequentially), but do NOT wait for any subagent's output before launching the next one. All subagents use `background: true`, so each launch returns immediately with a `task_id`. Collect all `task_id`s first, then move to Step 4b to wait for results. This ensures all groups run concurrently.

**Max concurrency**: Launch at most **8** subagents concurrently. If there are more than 8 non-overlapping groups, process them in batches: launch the first 8 groups, wait for all to complete (Step 4b), then launch the next batch. This prevents resource exhaustion (CPU, memory, disk from worktrees, GitHub API rate limits) at scale.

**Resumption logic**: Before launching, check if `groups[group_key]` exists in the state file (see State File section for schema).

- **If `groups[group_key].subagent_id` exists**: Resume the previous subagent using `resume_from: <stored_subagent_id>`. The resumed subagent is expected to inherit its previous worktree and full conversation context (verify this behavior on first use). Pass the new cycle's PR list and instructions as the prompt. **Fallback**: If resumption fails (subagent not found, session expired, tool rejects the ID), log a warning, discard the stale `subagent_id` from `groups[group_key]`, and launch a fresh subagent instead. Update `groups[group_key]` with the new `subagent_id` and `worktree_path`.
- **If no prior subagent exists**: Launch a fresh subagent.

In both cases, use these `spawn_subagent` parameters:

- `subagent_type: "general-purpose"`
- `isolation: "worktree"` (`spawn_subagent` creates and manages the worktree automatically)
- `background: true` (to process groups in parallel)
- `description: "[pr-babysit] <group_key>"` (e.g., `"[pr-babysit] pr-12345"` or `"[pr-babysit] stack-abc123"`). The `[pr-babysit]` prefix is parsed by the pager's subagent label renderer (see `format_subagent_label` in `xai-grok-pager`) so the subagent row shows "Pr-babysit" at the top instead of the generic "General" fallback. Keep the same description on `resume_from` follow-ups so the label stays stable across cycles.

The subagent prompt must include:
- The list of PRs in this group (with stack ordering if applicable)
- The `stack_type` for this group (`"graphite"`, `"github"`, or `null`) so the subagent knows which CLI tool to use for restack/push
- The repo `OWNER` and `REPO` values
- The full subagent logic from Step 5 below (Query + Decision Tree)
- The required JSON output format from Step 4b (the `pr_results` summary block that the subagent must emit at the end of its output)
- Do not instruct the check-cycle subagent to merge or to run the ship cycle. Shipping is the orchestrator's sequential pass after every group finishes.

Each subagent handles its group's PRs end-to-end: query, diagnose, fix, commit, push.

**Launch failure handling**: If the `spawn_subagent` call itself fails for a group (e.g., quota exceeded, invalid `resume_from` ID, network error), do NOT abort the entire cycle. Instead: log the error, set `last_status` to `"error"` for all PRs in that group, clear `groups[group_key].subagent_id` (so the next cycle retries with a fresh subagent), and continue launching subagents for the remaining groups. Only successfully launched subagents (those with valid `task_id`s) are added to the `task_id`/`group_key` mapping for Step 4b collection.

#### 4b. Watch progress and collect results

**Only begin this step after ALL subagents from Step 4a have been launched.** Do not call `get_command_or_subagent_output` for any subagent until every group's subagent has been started and you have all `task_id`s in hand.

**Maintain a `task_id` to `group_key` mapping**: As you launch each subagent in Step 4a, record the returned `task_id` alongside its `group_key` (e.g., in a list of `{task_id, group_key}` pairs). Use this mapping to associate each snapshot with the correct group for state updates.

Keep a last-seen progress fingerprint per `task_id` in orchestrator memory for this cycle. The fingerprint is `status` plus the Progress counters (turn, tool-call count, tokens) — not elapsed time, not the wait-hint, and not raw output. A still-running snapshot (`status` `initializing` or `running`) is that summary only; `output_file` is empty and the child transcript is not available. `pr_results` appear only on `status: completed`.

Each poll, pass every still-unfinished `task_id` in a single `get_command_or_subagent_output` `task_ids` array. After a slice expires or a completion wake, drop ids that are completed, failed, cancelled, or stuck, and poll the rest together. There is no `block` parameter:
- `timeout_ms` omitted or `0` — non-blocking peek (status + current output). A peek is **not** stuck evidence.
- A positive `timeout_ms` waits until **all** listed ids complete, capped at 600000 (10 min) by the tool. Watching uses a positive `timeout_ms`.
- Completion later auto-wakes the parent.

On each snapshot, judge from `status` and the Progress counters:

- **No prior fingerprint** — record the baseline only. This cannot be **Stuck**.
- **Progress** — keep waiting; replace the fingerprint when counters move. The first snapshot(s) with `status` `initializing` are Progress. Or `status` is `running` and the Progress counters moved, or a long command is clearly in flight (build, test, rebase, fetch, `gh run view`) even if counters are frozen. Elapsed wall time alone is not stuck.
- **Stuck** — kill with `kill_command_or_subagent(<task_id>)`, clear `groups[group_key].subagent_id` (so the next cycle launches a fresh subagent), set `last_status` to `"error"` for all PRs in that group, and continue other groups. Requires more than one still-`running` snapshot of no meaningful work after the last real move. Do not kill on the recording snapshot or the next same-counter snapshot alone if a long tool is in flight. Later snapshots still `initializing` with no advance (worktree setup wedged) are Stuck. Peeks (`timeout_ms` omitted or `0`) are not stuck evidence.
- **Completed** (`status: completed`) — parse the `pr_results` JSON below, merge into state, and store `subagent_id` / `worktree_path` as below.
- **Failed** (`status` is `failed` or `cancelled` — already terminal) — log the error, set `last_status` to `"error"` for all PRs in that group, and continue other groups. Store `subagent_id` / `worktree_path` as below so the next cycle can `resume_from`. Do not kill. A still-running snapshot with `Errors: N` is **Progress** or **Stuck**, never **Failed**.

Kill only after a stuck judgment. A poll slice expiring is not stuck; re-poll and re-judge. One failed or stuck group does not block the rest of the cycle.

This step is done when every launched group is completed, failed, cancelled, or judged stuck. It is not done while any group is still making progress.

Each subagent must conclude its output with a structured JSON summary block for reliable parsing:

```json
{"pr_results": [
  {"number": 123, "last_status": "healthy", "fix_count_delta": 1, "removed": false},
  {"number": 124, "last_status": "ci_failed", "fix_count_delta": 2, "removed": false}
]}
```

Fields per PR:
- `last_status` — the status after processing
- `fix_count_delta` — number of fixes applied this cycle
- `removed` — `true` if the PR was merged/closed and removed from the watchlist
- `ship_status` / `ship_blocked_reason` — persist when present

Merge the results from all subagents into the main state.

**After a Completed or terminal Failed snapshot**, update `groups[group_key]` in the state. Both values come from `spawn_subagent`'s return value (not from the subagent's JSON output):
- `subagent_id`: The `task_id` returned by the `spawn_subagent` call. Store this for use with `resume_from` on the next cycle.
- `worktree_path`: When `isolation: "worktree"` is used, `spawn_subagent`'s result includes a `worktree_path` field with the absolute path to the created worktree. Store this for use in Step 7 cleanup.

After **Stuck**, leave `subagent_id` cleared. Do not write the killed id back. Still store `worktree_path` if `spawn_subagent` returned one.

### Step 5: Subagent Logic — Query and Decision Tree

This section defines the logic each subagent executes for its assigned group of PRs.

#### Drain (ship-armed stacks)

A PR is armed for Drain only when `ship` is `true` and any of `ship_status` is `"armed"`, `last_status` is `"ship_armed"`, or live GraphQL `pullRequest.isInMergeQueue` is true. Query `isInMergeQueue` for every ship-enabled PR in the group before any git mutation. If `ship` is `false`, do not dequeue even if the PR is in a merge queue. If any ship-enabled PR is armed, load `references/shipping.md` and follow **Drain**. Re-query the ship-ready gates. Leave the stack untouched while the frontier is still ready or only in a wait state. Disarm only on a durable failed gate. A failed-gate disarm keeps `ship: true`. Merged PRs are reported `removed: true`.

#### Worktree initialization

`spawn_subagent`'s `isolation: "worktree"` parameter provides a clean worktree automatically. The subagent is already running inside the worktree; no `cd` or manual setup is needed.

**Warning**: `git checkout <branch>` will fail if that branch is already checked out in the main workspace or another worktree (git prohibits the same branch ref in multiple worktrees). To avoid this, use `git checkout -B <branch> origin/<branch>` which force-creates the local branch at the remote tracking ref, or use detached HEAD via `git checkout --detach origin/<branch>`. This is uncommon in normal usage since the main workspace is typically on `main`, but if it occurs, log a specific warning identifying the branch conflict and advise the user to switch branches in the main workspace.

**Fetch remote refs before any fix action, not unconditionally at startup.** If the PR is healthy, pending, merged, or in an unknown mergeable state, no git operations are needed and fetching wastes time and creates lock contention. Instead, track a boolean `has_fetched` flag (initially false) per subagent. Before the first operation that requires up-to-date refs (any `git checkout`, `git rebase`, or `gt restack`), check `has_fetched` -- if false, run the fetch and set it to true. Note: `gh stack rebase` handles its own fetch internally, so the `has_fetched` guard is not needed before it.

```bash
git fetch origin || (sleep 2 && git fetch origin) || FETCH_FAILED=true
```

If `FETCH_FAILED` is set, the subagent must set `last_status` to `"error"` for the current PR, log that both fetch attempts failed, and skip all git operations for this PR. Do not attempt checkout, rebase, or restack with stale refs.

The retry handles transient lock contention when multiple subagents fetch in parallel. This fetch is critical -- without fresh refs, `git rebase origin/<baseRefName>` or `gt restack` will rebase onto stale history and either fail or produce incorrect results. (`gh stack rebase` fetches internally and does not require this pre-fetch.)

Initialize a per-cycle fix counter for each PR assigned to this subagent (in memory, not persisted). Set each to 0. The counter is an observational metric for `fix_count_delta` — it does not limit how many code changes may be applied.

Also initialize in-memory lists of thread GraphQL ids for this cycle:
- `PROCESSED_THREAD_IDS` — fully handled: reply succeeded **and** resolve succeeded. The bot/automated pass must skip these so it does not re-process them.
- `REPLIED_UNRESOLVED_THREAD_IDS` — reply succeeded but `resolveReviewThread` failed (or the latest comment is already a closing babysitter reply and resolve still failed). The bot pass must retry **resolve only** (no second reply) for these ids.
- `REPLY_FAILED_THREAD_IDS` — both GraphQL and REST reply paths failed. Leave the thread open for the **next** cycle. The bot pass must skip these (no second code change, no second reply this cycle).
- `FIX_FAILED_THREAD_IDS` — a code-change attempt for this thread failed this cycle (checkout, edit, commit, or push). Do not reply (the fix was never pushed). Leave the thread open for the **next** cycle. The bot pass must skip these (no second code change, no reply this cycle). Before continuing other work on this PR, restore the worktree (see below) so leftover edits or an unpushed commit cannot be scooped up by the next `git add -A`.

```bash
PROCESSED_THREAD_IDS=()
REPLIED_UNRESOLVED_THREAD_IDS=()
REPLY_FAILED_THREAD_IDS=()
FIX_FAILED_THREAD_IDS=()
```

**Worktree recovery after a failed code-change attempt** — run this before any further edit/commit/push on the same PR (next CI check, review-body fix, or review thread). `git add -A` is mandatory on success and will otherwise stage leftover partial edits or include an unpushed commit that was marked `FIX_FAILED` and never replied to.

Abort any **in-progress** stack operation first. `gt restack` / `gh stack rebase` leave tool-specific state that `git merge --abort` / `git rebase --abort` do not clear; leaving it mid-operation desyncs stack metadata from the branch tip and later same-cycle `gt` / `gh stack` commands fail.

Then restore based on **what actually failed**. Do **not** always `git reset --hard origin/<headRefName>`:

1. **Checkout never succeeded** — `git branch --show-current` is a *named* branch other than `<headRefName>`. Do **not** reset: that rewrites the other shared stack branch HEAD is still on. `git clean -fd` for untracked junk only, log that HEAD is still on `$CURRENT`, and continue. The next fix on this PR must checkout first (`git checkout -B <headRefName> origin/<headRefName>`, or `gt checkout` / `gh stack checkout`). Detached HEAD is safe to reset — it does not move a named ref.
2. **Stack restack/rebase completed**, and only `gt submit` / `gh stack push` / `git push` failed. Abort is a no-op. Do **not** rewind the current branch to `origin/<headRefName>`: sibling / upstack branches stay at post-restack tips and later same-cycle stack ops would run desynced. Discard **uncommitted** changes only (`git restore --staged --worktree .` then `git clean -fd`), leave local branch tips as they are, and retry submit/push on the next successful fix or next cycle.
3. **Otherwise** (HEAD is `<headRefName>` or detached; restack/rebase was interrupted or never ran; edit/commit failed): abort in-progress ops, then `git reset --hard origin/<headRefName>` + `git clean -fd`.

```bash
# Abort in-progress stack ops (no-op if none), then restore branch-aware.
if [ "<stack_type>" = "graphite" ]; then
  gt abort --force --no-interactive 2>/dev/null || true
elif [ "<stack_type>" = "github" ]; then
  gh stack rebase --abort 2>/dev/null || true
fi
git merge --abort 2>/dev/null || true
git rebase --abort 2>/dev/null || true

CURRENT=$(git branch --show-current)  # empty when detached
# Set from this attempt: true only when gt restack / gh stack rebase exited 0
# and the subsequent submit/push failed.
RESTACK_COMPLETED_PUSH_FAILED=<true|false>

if [ -n "$CURRENT" ] && [ "$CURRENT" != "<headRefName>" ]; then
  echo "HEAD is ${CURRENT}, not <headRefName>; skip reset (would rewrite ${CURRENT})."
  git clean -fd
elif [ "$RESTACK_COMPLETED_PUSH_FAILED" = true ]; then
  git restore --staged --worktree . 2>/dev/null || true
  git clean -fd
else
  git reset --hard "origin/<headRefName>"
  git clean -fd
fi
```

Do **not** use `git clean -x` / `-xfd` (that wipes ignored build artifacts). After a successful push this cycle, `origin/<headRefName>` is that push; after no successful push, it is the start-of-cycle remote tip. For `stack_type` null, skip the `gt` / `gh stack` abort; `RESTACK_COMPLETED_PUSH_FAILED` is always false; still skip reset when HEAD is a different named branch.


#### Query each PR

```bash
gh pr view <number> --json state,mergeable,mergeStateStatus,statusCheckRollup,reviewDecision,headRefName,baseRefName
```

If `gh pr view` fails (network error, rate limit, auth expired), log the error, set `last_status` to `"error"`, and continue to the next PR.

#### Decision tree

Evaluate the PR state in this order:

1. Handle critical actions in order: MERGED/CLOSED, CONFLICTS, CI FAILED. If MERGED/CLOSED matched, skip all remaining steps for this PR. CONFLICTS and CI FAILED are **not** exclusive — after resolving conflicts, continue to CI failures in the same cycle. `mergeable` being `"UNKNOWN"` does **not** block processing; proceed with all other checks normally.
2. Then, **always** check for (a) changes-requested review-level bodies, (b) unresolved inline review threads from **humans and bots alike**, and (c) new bot/automated findings (COMMENTED reviews, issue-comment summaries) — regardless of whether a critical action was handled above. A PR can have CI failures AND review comments simultaneously. Re-scan **every cycle**; bots often re-post after a push even when the previous cycle was clean. Do not privilege human comments over automated ones, or one bot over another.
3. Finally, determine the terminal status: if CI checks are cancelled/timed-out (with no failures), set `"ci_needs_attention"`. If checks are still pending (no failures or cancellations), set `"pending"`. If everything is green (mergeable, no failed/cancelled checks, no changes requested, no unresolved human or bot threads), set `"healthy"`. If no branch matched at all, set `"error"`.
4. Apply every reasonable code change this cycle. The per-cycle fix counter is observational only — it does **not** gate or skip any code change. Increment it once after each successful code-change fix, only where the section closer says to increment (conflicts, each CI check fix, review-body, each review-thread code fix).
5. Replying to comment threads (questions/clarifications or false-positive / out-of-scope explanations) does not increment the counter.

**`last_status` precedence**: When multiple sections match for the same PR (e.g., conflicts resolved, then review comments processed), each section may set `last_status`. The last section to execute wins. The evaluation order defined above determines precedence — review-related statuses take priority over CI/conflict statuses because they run later.

#### MERGED or CLOSED

`state` is `"MERGED"` or `"CLOSED"`.

Report this PR as removed by setting `removed: true` in the JSON output. The parent agent handles the actual state file update. Log that it was removed and why.

#### Mergeable Unknown

`mergeable` is `"UNKNOWN"`. GitHub has not yet computed mergeability.

Note this state but **do not block**. Continue processing the PR normally — check for CI failures, review comments, and other actionable items. Mergeability often resolves itself after a push or a short delay. Only set `last_status` to `"mergeable_unknown"` as a fallback if no other status was assigned during processing (no CI failures, no review comments, no conflicts).

#### Merge Conflicts

`mergeable` is `"CONFLICTING"` or `mergeStateStatus` is `"DIRTY"`.

Resolve conflicts first before attempting any other fixes, since conflicts are often the root cause of CI failures.

**Graphite-managed branches** (`stack_type` is `"graphite"`):

```bash
gt checkout <branch>
gt restack --no-interactive
```

If `gt restack` encounters conflicts:
1. Identify the conflicting files from the restack output.
2. Read each conflicting file **in full** (not just the conflict region). Conflict markers look like:
   ```
   <<<<<<< HEAD
   (parent branch version -- the branch being restacked onto)
   =======
   (current branch version -- the commit being replayed)
   >>>>>>> <commit-hash>
   ```
   `gt restack` performs a rebase internally, so `HEAD` (top section) is the **parent** branch and the bottom section is the **current** branch's changes.

   Resolution strategy:
   - Read surrounding context beyond the markers to understand each side's intent.
   - If both sides added non-overlapping code (e.g., different functions, different imports), keep both additions in logical order.
   - If both sides modified the same lines, combine the changes or prefer the current branch's version when it represents the intended new behavior.
   - Remove **all** conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) -- leftover markers will break compilation.
   - After resolving each file, re-read it to verify it is syntactically valid and logically consistent with the rest of the codebase.
3. Stage the resolved files:
   ```bash
   git add <resolved_files>
   ```
4. Continue the restack:
   ```bash
   gt continue
   ```
5. After all conflicts are resolved and the restack completes, verify the result builds. Run the appropriate build/lint command for the affected files (e.g., `cargo check` for Rust, `python -m py_compile <file>` for Python, `npx tsc --noEmit` for TypeScript). If the build fails, fix the issue before submitting -- pushing broken code triggers CI failures that consume another fix cycle.

After restacking, submit the entire stack:

```bash
gt submit --stack --no-edit --no-interactive
```

**GitHub stacked PRs** (`stack_type` is `"github"`):

```bash
# Use the PR number (not branch name) to ensure the stack is locally tracked
# in this worktree context — branch-name checkout only resolves against
# locally tracked stacks, which may not exist if the add step ran in a
# different worktree.
# Retry on exit code 8 (stack locked by another process) per Safety Guardrails.
gh stack checkout <number> || { EXIT=$?; if [ $EXIT -eq 8 ]; then sleep 2 && gh stack checkout <number>; fi; }
gh stack rebase || { EXIT=$?; if [ $EXIT -eq 8 ]; then sleep 2 && gh stack rebase; fi; }
```

If `gh stack rebase` encounters conflicts:
1. The rebase pauses and prints the conflicted files with line numbers. Resolve them using the same strategy as Graphite conflicts above (read full file, understand both sides, combine changes, remove markers).
2. Stage resolved files:
   ```bash
   git add <resolved_files>
   ```
3. Continue the rebase:
   ```bash
   gh stack rebase --continue
   ```
4. If the rebase cannot be resolved, abort and report:
   ```bash
   gh stack rebase --abort
   ```
5. After all conflicts are resolved, verify the result builds (same as Graphite section above).

After rebasing, push the entire stack:

```bash
gh stack push || { EXIT=$?; if [ $EXIT -eq 8 ]; then sleep 2 && gh stack push; fi; }
```

For stacks without conflicts, `gh stack sync` can replace the separate rebase + push steps as a single command (fetch + rebase + push + PR state sync). However, using separate commands gives more control for conflict handling, so prefer the explicit flow when conflicts are possible.

**Plain git branches** (`stack_type` is `null` or standalone PR):

```bash
git checkout <branch>
git rebase origin/<baseRefName>
```

If the rebase encounters conflicts:
1. Identify the conflicting files from the rebase output.
2. Read each conflicting file **in full** (not just the conflict region). Conflict markers look like:
   ```
   <<<<<<< HEAD
   (base branch version -- during rebase, HEAD is the branch being rebased onto)
   =======
   (PR branch version -- the commit being replayed)
   >>>>>>> <commit-hash>
   ```
   **Important**: During `git rebase`, the sides are swapped compared to `git merge`. `HEAD` (above `=======`) is the *base* branch's code (e.g., `origin/main`), and the bottom section is the PR's incoming changes being replayed on top.

   Resolution strategy:
   - Read surrounding context beyond the markers to understand each side's intent.
   - If both sides added non-overlapping code (e.g., different functions, different imports), keep both additions in logical order.
   - If both sides modified the same lines, combine the changes or prefer the PR's version when it represents the intended new behavior.
   - Remove **all** conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) -- leftover markers will break compilation.
   - After resolving each file, re-read it to verify it is syntactically valid and logically consistent with the rest of the codebase.
3. Stage the resolved files:
   ```bash
   git add <resolved_files>
   ```
4. Continue the rebase:
   ```bash
   git rebase --continue
   ```
5. After all conflicts are resolved and the rebase completes, verify the result builds. Run the appropriate build/lint command for the affected files (e.g., `cargo check` for Rust, `python -m py_compile <file>` for Python, `npx tsc --noEmit` for TypeScript). If the build fails, fix the issue before pushing -- pushing broken code triggers CI failures that consume another fix cycle.

After resolving, push:

```bash
git push --force-with-lease
```

Post a summary comment:

```bash
gh pr comment <number> --body "Automated fix: resolved merge conflicts and rebased."
```

Set `last_status` to `"conflicts"`. Increment the per-cycle fix counter for this PR.

#### CI Failed

`statusCheckRollup` contains one or more checks with `conclusion` of `"FAILURE"` or `"ERROR"`. Process each failed check.

1. List failed checks with their run IDs:
   ```bash
   gh pr checks <number> --json name,state,link
   ```
   Extract the run ID from the `link` field URL. The URL format is `https://github.com/<owner>/<repo>/actions/runs/<run_id>/...` — parse `<run_id>` from it. Alternatively:
   ```bash
   gh run list --branch <headRefName> --json databaseId,name,conclusion \
     --jq '.[] | select(.conclusion == "failure")'
   ```

2. For each failed check, read logs:
   ```bash
   gh run view <run_id> --log-failed 2>/dev/null | tail -100
   ```

3. Checkout the branch (the worktree initialization fetch ensures refs are current):
   ```bash
   git checkout <headRefName>
   git rebase origin/<headRefName>
   ```

4. Diagnose the failure from the logs. Read relevant source files.

5. Fix the code.

6. Commit and push:
   ```bash
   git add -A && git commit -m "fix: address CI failure in <check_name>"
   ```
   If graphite-managed (`stack_type: "graphite"`):
   ```bash
   gt submit --stack --no-edit --no-interactive
   ```
   If GitHub stacked PR (`stack_type: "github"`):
   ```bash
   gh stack push || { EXIT=$?; if [ $EXIT -eq 8 ]; then sleep 2 && gh stack push; fi; }
   ```
   If plain git (`stack_type: null`):
   ```bash
   git push
   ```

Post a summary comment:

```bash
gh pr comment <number> --body "Automated fix: addressed CI failure in <check_name>."
```

Set `last_status` to `"ci_failed"`. Increment the per-cycle fix counter for this PR after each individual check fix.

#### Changes Requested

`reviewDecision` is `"CHANGES_REQUESTED"`.

This section handles the **review-level body** only (the top-level summary the reviewer wrote when requesting changes). Individual inline comment threads are handled separately in "Unresolved Review Comments" below to avoid double-processing.

1. Fetch reviews:
   ```bash
   NO_COLOR=1 gh api repos/{OWNER}/{REPO}/pulls/{number}/reviews \
     --jq '.[] | select(.state == "CHANGES_REQUESTED")'
   ```

2. Read the review body text (not individual inline comments — those are handled by the "Unresolved Review Comments" section). If the review body contains actionable high-level feedback that is not already covered by inline threads, address it.

3. Checkout the branch, address the review-body feedback in code.

4. Commit with a descriptive message and push:
   ```bash
   git add -A && git commit -m "fix: address review feedback"
   ```
   If graphite-managed (`stack_type: "graphite"`):
   ```bash
   gt submit --stack --no-edit --no-interactive
   ```
   If GitHub stacked PR (`stack_type: "github"`):
   ```bash
   gh stack push || { EXIT=$?; if [ $EXIT -eq 8 ]; then sleep 2 && gh stack push; fi; }
   ```
   If plain git (`stack_type: null`):
   ```bash
   git push
   ```

Post a summary comment:

```bash
gh pr comment <number> --body "Automated fix: addressed review feedback."
```

If the review body contained actionable feedback that was addressed, set `last_status` to `"changes_requested"` and increment the per-cycle fix counter. If the review body was empty or contained no actionable feedback beyond what inline threads cover, leave `last_status` unchanged.

**Note:** Many bots (and some humans) post `COMMENTED` reviews rather than `CHANGES_REQUESTED`, so this section will not see them. The bot/automated-comment check below always scans those review bodies and issue comments alongside human threads.

#### Unresolved Review Comments (ALWAYS check)

**Always run this check**, even if a previous branch (CI, conflicts, changes requested) already matched. A PR can have both CI failures AND unresolved review threads. Skip this only if the PR was MERGED/CLOSED (removed). **Every single unresolved thread must be evaluated and acted upon. Do not silently skip any thread for any reason.**

1. Fetch review threads. **Important**: `gh api graphql` injects ANSI escape codes into its output even when piped. Set `NO_COLOR=1` and strip remaining escapes with `sed` before parsing JSON. Write the output file under the OS temp dir from `<PYTHON> <HOST_PY> scratch` (not a bare `/tmp` `mktemp`). Inline that absolute path as `scratch_dir`.
   ```bash
   THREADS_FILE="<scratch_dir>/pr_review_threads.json"
   CURSOR=""
   ALL_THREADS="[]"
   while true; do
     AFTER_ARG=""
     if [ -n "$CURSOR" ]; then
       AFTER_ARG="-f cursor=$CURSOR"
     fi
     PAGE=$(NO_COLOR=1 gh api graphql -f owner="<OWNER>" -f name="<REPO>" -F number=<number> $AFTER_ARG -f query='
     query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
       repository(owner: $owner, name: $name) {
         pullRequest(number: $number) {
           reviewThreads(first: 50, after: $cursor) {
             pageInfo { hasNextPage endCursor }
             nodes {
               id
               isResolved
               comments(last: 100) {
                 nodes {
                   author { __typename login }
                   path
                   line
                   body
                   databaseId
                   url
                 }
               }
             }
           }
         }
       }
     }' | sed 's/\x1b\[[0-9;]*m//g')
     PAGE_NODES=$(echo "$PAGE" | jq '.data.repository.pullRequest.reviewThreads.nodes')
     ALL_THREADS=$(echo "$ALL_THREADS" "$PAGE_NODES" | jq -s '.[0] + .[1]')
     HAS_NEXT=$(echo "$PAGE" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage')
     if [ "$HAS_NEXT" != "true" ]; then
       break
     fi
     CURSOR=$(echo "$PAGE" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor')
   done
   echo "$ALL_THREADS" > "$THREADS_FILE"
   ```

   The pagination loop fetches all review threads, not just the first 50. This is required to satisfy the mandate that every thread must be processed.

   Fetch thread comments with `comments(last: 100)` — **not** `comments(first: 10)`. GitHub returns that window oldest→newest, so `comments.nodes[-1]` is the newest comment. `comments(first: 10)` is the 10 oldest; treating its last node as "latest" misses a closing babysitter reply on long threads and causes a duplicate reply. If `comments.pageInfo.hasPreviousPage` is true (more than 100 comments), paginate the comments connection (or raise `last`) until the newest comment is included. Do not detect "latest" from a truncated `first:` page.

2. Filter to unresolved threads (`isResolved == false`). This set is **author-agnostic**: humans, GitHub `Bot` accounts, and any other automated reviewer. Do not drop a thread because the author is a bot, because the login ends in `[bot]`, or because the body is HTML-heavy.

3. Process **every** unresolved thread. No thread may be skipped. Keep both the thread GraphQL `id` (`PRRT_...`, required for reply + resolve) and the comment `databaseId`. For each thread:

   **Reply helper** — use this for every thread reply. **Never** resolve unless the reply succeeded. A failed GraphQL reply plus the REST 404 fallback must leave the thread open for the next cycle. After a successful reply, always attempt `resolveReviewThread` (capture exit/status and the `isResolved` payload; retry resolve once). Append to `PROCESSED_THREAD_IDS` only when reply **and** resolve succeeded.
   If reply succeeded but resolve failed: do **not** mark PROCESSED. Add the id to `REPLIED_UNRESOLVED_THREAD_IDS` so the bot pass retries **resolve only** (no second reply).

   ```bash
   # THREAD_ID, DATABASE_ID, REPLY_BODY
   # gh api often exits 0 on GraphQL errors — require thread.isResolved == true.
   resolve_review_thread() {
     local out
     if ! out=$(NO_COLOR=1 gh api graphql -f query='
     mutation($id: ID!) {
       resolveReviewThread(input: {threadId: $id}) {
         thread { isResolved }
       }
     }' -f id="$THREAD_ID"); then
       return 1
     fi
     echo "$out" | sed 's/\x1b\[[0-9;]*m//g' | jq -e '.data.resolveReviewThread.thread.isResolved == true' >/dev/null
   }

   # Resolve only (no reply). Use when a babysitter reply already landed.
   resolve_only() {
     if resolve_review_thread || resolve_review_thread; then
       PROCESSED_THREAD_IDS+=("$THREAD_ID")
       local kept=() id
       for id in "${REPLIED_UNRESOLVED_THREAD_IDS[@]}"; do
         [ "$id" != "$THREAD_ID" ] && kept+=("$id")
       done
       REPLIED_UNRESOLVED_THREAD_IDS=("${kept[@]}")
       return 0
     fi
     echo "Resolve-only failed for ${THREAD_ID}; track in REPLIED_UNRESOLVED_THREAD_IDS (no second reply)."
     local already=false id
     for id in "${REPLIED_UNRESOLVED_THREAD_IDS[@]}"; do
       if [ "$id" = "$THREAD_ID" ]; then already=true; break; fi
     done
     [ "$already" != true ] && REPLIED_UNRESOLVED_THREAD_IDS+=("$THREAD_ID")
     return 1
   }

   reply_and_resolve() {
     local reply_ok=false
     if NO_COLOR=1 gh api graphql -f query='
     mutation($threadId: ID!, $body: String!) {
       addPullRequestReviewThreadReply(input: {
         pullRequestReviewThreadId: $threadId,
         body: $body
       }) { comment { url } }
     }' -f threadId="$THREAD_ID" -f body="$REPLY_BODY"; then
       reply_ok=true
     elif NO_COLOR=1 gh api repos/{OWNER}/{REPO}/pulls/{number}/comments/${DATABASE_ID}/replies \
            -X POST -f body="$REPLY_BODY"; then
       reply_ok=true
     fi
     if [ "$reply_ok" != true ]; then
       echo "Reply failed for ${THREAD_ID}; not resolving. Track in REPLY_FAILED_THREAD_IDS; leave open for next cycle. Do not re-process this cycle."
       REPLY_FAILED_THREAD_IDS+=("$THREAD_ID")
       return 1
     fi
     if resolve_review_thread || resolve_review_thread; then
       PROCESSED_THREAD_IDS+=("$THREAD_ID")
       return 0
     fi
     echo "Reply succeeded but resolve failed for ${THREAD_ID}; not marking PROCESSED. Retry resolve-only later this cycle / next cycle."
     REPLIED_UNRESOLVED_THREAD_IDS+=("$THREAD_ID")
     return 1
   }
   ```

   **Failed-resolve / next-cycle guard** — before posting a new reply, inspect the **newest** comment on the thread. That is the last entry in `comments.nodes` **only when** comments were fetched with `comments(last: N)` (or a fully paginated comments connection). Never use `comments(first: 10).nodes[-1]` as latest — that is the 10th-oldest comment.
   - If `THREAD_ID` is already in `FIX_FAILED_THREAD_IDS` or `REPLY_FAILED_THREAD_IDS`: skip the thread for the rest of this cycle (no second code change, no reply).
   - If `THREAD_ID` is already in `REPLIED_UNRESOLVED_THREAD_IDS` (this-cycle reply succeeded, resolve failed): call `resolve_only`. Do **not** post another reply.
   - If the newest comment is already a successful babysitter reply that was *meant to close* the thread (cites a fix commit SHA, or is a false-positive / out-of-scope / clarification explanation): call `resolve_only`. Do **not** post another reply.
   - If the newest comment is a babysitter note that is **not** a closer — including any prior-cycle "Fix cap reached…", "will be addressed in the next check cycle", or similar deferral text — it is **not** closing. Do **not** `resolve_only`. The original reviewer finding still needs a code change or a substantive FP/OOS/clarification reply: if a code change is reasonable, apply it this cycle, push, post a SHA reply, then resolve.
   - Only post a new reply when the newest comment is still unanswered reviewer text (human or bot), or a non-closing babysitter note (previous bullet).

   **If a code change is reasonable** (the comment points out a bug, requests a refactor, suggests an improvement, or is otherwise actionable):
   - Checkout the branch, make the code change, then commit and push:
     ```bash
     git add -A && git commit -m "fix: address review comment on <path>"
     ```
     If graphite-managed (`stack_type: "graphite"`):
     ```bash
     gt submit --stack --no-edit --no-interactive
     ```
     If GitHub stacked PR (`stack_type: "github"`):
     ```bash
     gh stack push || { EXIT=$?; if [ $EXIT -eq 8 ]; then sleep 2 && gh stack push; fi; }
     ```
     If plain git (`stack_type: null`):
     ```bash
     git push
     ```
   - If checkout, the code change, commit, or push fails: log the error, run the worktree recovery above (branch-aware: abort in-progress stack ops; `reset --hard origin/<headRefName>` only when HEAD is `<headRefName>` or detached **and** a completed restack did not leave unpushed sibling tips; otherwise clean-only / skip reset), append `THREAD_ID` to `FIX_FAILED_THREAD_IDS`, do **not** reply, do **not** increment the counter, and continue to the next thread. Do not retry this thread later in the same cycle (including the bot pass).


   - **Never** reply before the fix is pushed. The reply must reference a commit that already contains the fix.
   - After the fix is pushed, reply then resolve **only if the reply succeeded**:
     ```bash
     COMMIT_SHA=$(git rev-parse HEAD)
     THREAD_ID="<thread.id>"
     DATABASE_ID="<comment.databaseId>"
     REPLY_BODY="Addressed in ${COMMIT_SHA}: <brief description of what was changed>"
     reply_and_resolve
     ```
   - Increment the per-cycle fix counter for this PR.

   **If the comment is a genuine question, discussion point, or out of scope** (the current code is correct, the suggestion is out of scope, or the comment asks for clarification):
   - Reply with a **substantive** explanation. Explain *why* the current code is correct, *why* the suggestion is out of scope, or provide the requested clarification with technical detail. Resolve **only if the reply succeeded**.
     ```bash
     THREAD_ID="<thread.id>"
     DATABASE_ID="<comment.databaseId>"
     REPLY_BODY="<substantive explanation>"
     reply_and_resolve
     ```

   **Never** reply with phrases like "Will fix", "Acknowledged", "Acked", "Noted", "Good point", "Good follow-up", "Makes sense", "Thanks for the feedback", or any reply that merely acknowledges a comment or defers a fix to a follow-up PR. If a comment points out a reasonable issue, fix it **now** in this cycle — do not defer to a follow-up PR or a future cycle. Every reply must either reference a commit SHA where the fix was already made, or provide a detailed technical explanation of why no code change is needed.

   **Bot-specific reply commands** (only when that bot documents them): When dismissing a `semgrep-code-scan` finding that is a false positive or not actionable, reply with `/fp <comment>`, `/ar <comment>`, or `/other <comment>`. Do **not** invent slash commands for other bots (Cursor Bugbot, Copilot, CodeRabbit, etc. have none). For those, a normal GraphQL reply + resolve is correct.

Keep `$THREADS_FILE` until after the bot/automated-comment section below (it reuses the dump). Do not delete it yet.

If any unresolved threads were found and processed (code change or substantive reply), set `last_status` to `"review_comments"`. If the filter above found zero unresolved threads, leave `last_status` unchanged from any earlier section.

#### Bot and automated comments (ALWAYS check, alongside humans)

**Always run this check every cycle**, even when CI is green, checks are pending, or human review looks clean. Automated reviewers re-run after new pushes and can leave *new* unresolved threads. Handling only human review is not sufficient — and neither is handling only one bot.

Treat **every** bot/automated finding as first-class review feedback, same rules as humans: fix if valid, reply with the fix commit SHA (never a bare ack), then resolve the thread. Do not rank or skip by vendor.

**Identity** — treat a comment/review as automated if any of these hold (non-exhaustive; when unsure, treat it as a normal review comment and still process it):
- GraphQL `author.__typename == "Bot"`, or REST `user.type == "Bot"`
- `author.login` / `user.login` ends with `[bot]`
- Known automation logins, including but not limited to: `cursor` / `cursor[bot]` (Cursor Bugbot), `copilot` / `copilot-pull-request-reviewer`, `coderabbitai`, `github-actions`, `renovate`, `dependabot`, `semgrep-code-scan`, `graphite-app`

Do **not** write a Cursor-only filter and stop there. A cycle that only scanned `cursor[bot]` while leaving Copilot, CodeRabbit, Dependabot, Semgrep, or any other bot thread open is incomplete.

1. **Re-scan only dump threads that were unresolved at fetch time and not fully handled this cycle.** `$THREADS_FILE` was captured **before** any `resolveReviewThread` calls this cycle, so `isResolved` is stale **only** for ids in `PROCESSED_THREAD_IDS` (reply succeeded and resolve succeeded). Flags on every other dump entry are still correct (including threads resolved in prior cycles).
   - **Never** reply to a dump entry with `isResolved == true`. A reply on a resolved GitHub thread reopens it and will churn `/loop` forever.
   - Skip any thread whose GraphQL `id` is already in `PROCESSED_THREAD_IDS`.
   - Skip any thread whose GraphQL `id` is in `REPLY_FAILED_THREAD_IDS`. A first-pass reply that failed must **not** be reworked or re-replied later in the same cycle; leave it open for the next cycle.
   - Skip any thread whose GraphQL `id` is in `FIX_FAILED_THREAD_IDS`. A first-pass code-change attempt that failed must **not** be retried later in the same cycle; leave it open for the next cycle.
   - For ids in `REPLIED_UNRESOLVED_THREAD_IDS`, **retry resolve only** (`resolve_only`) — do **not** post another reply. On success, the id moves into `PROCESSED_THREAD_IDS`. On failure, leave it in `REPLIED_UNRESOLVED_THREAD_IDS` for the next cycle.
   - Remaining candidates (`isResolved == false`, id not in `PROCESSED_THREAD_IDS`, id not in `REPLIED_UNRESOLVED_THREAD_IDS`, id not in `REPLY_FAILED_THREAD_IDS`, id not in `FIX_FAILED_THREAD_IDS`) are threads the first pass may have skipped because a naive `jq` filter treated an HTML-wrapped body as empty, or `author.login` was missing/`null`. Process those with the same `reply_and_resolve` path. If the newest comment (last node of `comments(last: N)`, not `comments(first: 10)`) is already a successful *closing* babysitter reply (fix SHA or false-positive / out-of-scope explanation), use **resolve only** instead of posting a duplicate reply. Prior-cycle "Fix cap reached" / "will be addressed in the next check cycle" notes are **not** closing — do not `resolve_only`; apply the fix (or a substantive FP/OOS reply), then SHA reply + resolve.
   - If in doubt, re-fetch `reviewThreads` and use live `isResolved`; still skip `PROCESSED_THREAD_IDS`, `REPLY_FAILED_THREAD_IDS`, and `FIX_FAILED_THREAD_IDS`; still resolve-only for `REPLIED_UNRESOLVED_THREAD_IDS`.

2. **Strip markup before judging bot findings.** Automated reviewers often wrap the real issue in HTML, HTML comments, and dashboard footers. `jq` filters on the raw JSON string often miss or mis-parse these bodies — that is **not** "no comments".
   - Dump the raw `body` to a file.
   - Strip `<!-- ... -->`, HTML tags (`<sup>`, `<a>`, `<p>`, `<br>`, …), and vendor footers ("Reviewed by …", "Fix in Cursor", Copilot/CodeRabbit chrome, etc.).
   - Read the heading + first paragraph as the actual finding.
   - Example strip (HTML + **trailing** vendor chrome only — do **not** DOTALL-delete from mid-body phrases like "generated by the template"). Do not use a shell heredoc (`<<` is reserved in PowerShell) and do not call bare `python3`. Write this script to `<scratch_dir>/strip_bot_body.py` with the `write` tool, then run `<PYTHON> <scratch_dir>/strip_bot_body.py <BODY_FILE>`:

     ```python
     import re, sys
     text = open(sys.argv[1], encoding="utf-8").read()
     text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
     text = re.sub(r"<[^>]+>", " ", text)
     lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
     footer = re.compile(
         r"^(Reviewed by\b.*Bugbot|Fix in Cursor\b|Configure here\b)",
         re.I,
     )
     while lines and (not lines[-1] or footer.match(lines[-1])):
         lines.pop()
     print(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip())
     ```

3. **Also fetch bot review bodies and issue comments** (usually `COMMENTED`, not `CHANGES_REQUESTED` — the Changes Requested section will miss them). These are **discovery aids only**; they are often stale after a prior cycle already fixed the inline threads.
   ```bash
   NO_COLOR=1 gh api --paginate repos/{OWNER}/{REPO}/pulls/{number}/reviews \
     --jq '.[] | select(.user != null and (.user.type == "Bot" or (.user.login != null and (.user.login | test("\\[bot\\]$|^(cursor|copilot|semgrep-code-scan|coderabbitai|graphite-app)$"))))) | {user: .user.login, state, body, submitted_at, html_url}'
   NO_COLOR=1 gh api --paginate repos/{OWNER}/{REPO}/issues/{number}/comments \
     --jq '.[] | select(.user != null and (.user.type == "Bot" or (.user.login != null and (.user.login | test("\\[bot\\]$|^(cursor|copilot|semgrep-code-scan|coderabbitai|graphite-app)$"))))) | {user: .user.login, body, created_at, html_url}'
   ```
   `--paginate` is required: without it only the first page is returned and newer bot summaries on busy PRs are missed. Also include known automation logins that sometimes appear as `User` rather than `Bot` (e.g. `cursor`, `copilot`, `semgrep-code-scan`). When a login is ambiguous, fetch it rather than skip it.
   - If a summary lists a finding as open, verify against GraphQL `reviewThreads[].isResolved` for that file/line. **Trust per-thread `isResolved`, not the aggregate summary.**
   - If the summary mentions a finding with **no** matching thread, look harder (pagination, HTML-wrapped body, more comment pages) before ignoring it.
   - Address any still-actionable summary-only feedback the same way as a review body: code change, push, then a conversation comment `Addressed in ${SHA}: <what changed>`. Do not use the `Automated fix:` prefix on that comment. `Automated fix:` notes do not close the ship-ready conversation gate. Do not defer it.

4. **Never mark `healthy` while unresolved bot or human threads remain.** New findings posted after this cycle's push are picked up on the next scheduled check — that is expected.

5. **Human conversation comments.** Also paginate `GET repos/{OWNER}/{REPO}/issues/{number}/comments` with no bot filter. Skip a comment when any of these hold: the author is the PR author; the body is a closer (`Addressed in ` / `Automated fix:`) or a status notice; a later closer already exists (same test as ship-ready: a later conversation comment from the PR author or the authenticated `gh` user whose body starts with `Addressed in `). Remaining comments are review-body findings. Fix or reply substantively. Then post `Addressed in ${SHA}: ...` on the conversation tab, using the pushed fix SHA or `git rev-parse HEAD` when there was no code change. Do not use `Automated fix:` for that closer.

If any bot/automated thread or summary finding was processed this cycle, set `last_status` to `"review_comments"`. If any human conversation comment was processed, set `last_status` to `"review_comments"`.

After the bot pass, clean up the shared dump with `<PYTHON> <HOST_PY> cleanup <scratch_dir>/pr_review_threads.json` (do not `rm -f`, do not write to `/tmp`).

#### Cancelled / Timed-Out CI Checks

`statusCheckRollup` contains one or more checks with `conclusion` of `"CANCELLED"`, `"TIMED_OUT"`, `"STARTUP_FAILURE"`, or `"STALE"`, and no checks have `conclusion` of `"FAILURE"` or `"ERROR"`.

Set `last_status` to `"ci_needs_attention"` and skip. Do not attempt fixes — these checks need manual re-triggering or investigation.

#### Checks Pending

Any check in `statusCheckRollup` has `status` of `"IN_PROGRESS"` or `"QUEUED"`, and no checks have failed or been cancelled.

Set `last_status` to `"pending"`. Do **not** let pending CI block action on already-identified issues — human review comments, bot/automated findings, known failures from previous runs, and other actionable items must still be addressed even while checks are in progress.

#### All Green

Verify all of the following are true:
- `mergeable` is `"MERGEABLE"` (not `"CONFLICTING"` or `"UNKNOWN"`)
- No checks have `conclusion` of `"FAILURE"`, `"ERROR"`, `"CANCELLED"`, `"TIMED_OUT"`, `"STARTUP_FAILURE"`, or `"STALE"`
- `reviewDecision` is not `"CHANGES_REQUESTED"`
- No unresolved review threads exist — human or bot/automated (confirmed by the review-comments and bot/automated checks above)

If all conditions are met, update `last_status` to `"healthy"`. No action needed.

If none of the above decision branches matched (unexpected API state), set `last_status` to `"error"` and log a warning with the raw PR state for debugging.

### Step 6: Update state file

Write the updated state file with new values for `last_checked`, `last_status`, `check_count`, `fix_count`, `ship`, `ship_status`, and `ship_blocked_reason` for each processed PR. Also persist the updated `groups` map with current `subagent_id` and `worktree_path` values for each group. Persist state before worktree cleanup so that a crash during cleanup does not lose cycle results or subagent tracking.

### Step 6b: Ship cycle (opt-in, sequential)

If any watched PR in this repo has `ship: true`, load `references/shipping.md` and run the ship cycle now. Do this after every check-cycle group has finished, not inside those subagents.

Collect the ship-enabled groups. For each group, resume `groups[group_key].subagent_id` if it exists. If it does not, launch a fresh `spawn_subagent` with `isolation: "worktree"` and a ship-only prompt, then store `subagent_id` and `worktree_path`. Wait for that subagent to finish and merge its `ship_results` before starting the next group. Never run two ship subagents at once. Never run `gt` in the main workspace.

A `ship` command with no check work uses this same sequential pass.

If any PR in the group was `removed: true` this cycle (merged or closed), do not ship a new frontier in this invocation.

After every ship subagent finishes, write the state file again with the merged `ship_results`. Step 6 ran before this pass. Without this second write, `ship_status` is lost on compaction.

### Step 7: Worktree cleanup (conservative)

Worktrees persist across cycles for subagent resumption. Do **not** aggressively clean up worktrees between cycles.

Only clean up a worktree when **all PRs in the group have been removed** (merged, closed, or explicitly removed from the watchlist) or when the user explicitly requests cleanup. Use `grok worktree rm` (not `git worktree remove`):

```bash
grok worktree rm --force <worktree_path>
```

The `<worktree_path>` comes from `groups[group_key].worktree_path` in the state file. After removing the worktree, also delete the `groups[group_key]` entry from the state file and re-persist the state.

Note: `grok worktree rm` is the preferred cleanup command. If `spawn_subagent` gains its own worktree cleanup mechanism in the future, prefer that instead to avoid inconsistencies with the tool's internal tracking.

### Step 8: Self-terminate if empty

After state persistence and worktree cleanup are complete: if all PRs for this repo were removed (merged/closed) during this cycle, call `scheduler_list`. If any scheduled task's prompt contains `pr-babysit`, call `scheduler_delete` with that task's ID to self-terminate the loop. Report and exit.

## Safety Guardrails

Follow these rules strictly:

- **Never force-push without `--force-with-lease`**. Always use `git push --force-with-lease`, never `git push --force`. Note: `gh stack push` and `gt submit` handle `--force-with-lease` internally, so no extra flags are needed when using those commands.
- **Never modify files outside the PR's branch**. Always verify you are on the correct branch before making changes.
- **All fix work happens in worktrees, never in the main workspace.** The main workspace tree must not be modified during a check cycle. Each non-overlapping group gets its own worktree via `isolation: "worktree"` on `spawn_subagent`.
- **Worktrees persist across cycles for subagent resumption.** Do not clean up worktrees unless all PRs in the group are removed. Use `grok worktree rm --force <path>` for cleanup, not `git worktree remove`.
- **No per-cycle fix cap.** Apply every reasonable code change this cycle (conflicts, each failed CI check, review-body feedback, every actionable unresolved thread — human or bot). Track a per-cycle counter in memory as an observational metric for `fix_count_delta` only: initialize to 0 for each PR at the start of the cycle, increment once after each *successful* code-change fix (at the section closer). Replies do not increment the counter. The counter does **not** gate or skip any code change. Failed fix attempts still do not retry in the same cycle (continue remaining work on the same PR).
- **Never skip or ignore review comments — human or bot/automated.** Every unresolved thread must be evaluated and either addressed with a code change or responded to with a substantive reply, regardless of author (`Bot`, `*[bot]`, Cursor Bugbot, Copilot, CodeRabbit, Semgrep, Dependabot, Renovate, Graphite, or a human). Silently skipping a thread is never acceptable. Re-scan **every cycle**; do not assume a prior cycle covered newly posted findings, and do not stop after checking only one bot.
- **Never reply to review comments with "will fix", "acknowledged", "acked", "good follow-up", or similar platitudes.** If a comment requires a code change, make the change **now** — do not defer to a follow-up PR or a future cycle. Make the fix first, then reply referencing the commit. If the comment is a question, provide a substantive answer. Empty acknowledgments and deferred fixes are never acceptable.
- **Resolve threads after they are fully addressed — and only after the reply succeeded.** After a fix+SHA reply or a false-positive/out-of-scope explanation, run GraphQL `resolveReviewThread` on the thread `id` (`PRRT_...`) **iff** `addPullRequestReviewThreadReply` (or the REST fallback) returned success. Capture resolve success (command exit **and** `thread.isResolved == true`); retry resolve once if it fails. Append to `PROCESSED_THREAD_IDS` only after reply **and** resolve succeeded. If reply succeeded but resolve failed, do **not** mark PROCESSED — add the id to `REPLIED_UNRESOLVED_THREAD_IDS` and retry **resolve only** (no second reply) in the bot pass and the next cycle. If the latest comment on an unresolved thread is already a successful *closing* babysitter reply (fix SHA or substantive false-positive / out-of-scope explanation), resolve only — never post a duplicate reply. A leftover prior-cycle "Fix cap reached" / "will address next cycle" note is **not** closing: do not `resolve_only`; apply the code change this cycle (or a substantive FP/OOS reply), then post the SHA reply and resolve. If both reply paths fail, add the id to `REPLY_FAILED_THREAD_IDS`, leave the thread open, and do **not** re-process it later in the same cycle (no second code change, no second reply) — retry on the next cycle. If a review-thread code change fails before a reply, add the id to `FIX_FAILED_THREAD_IDS` and skip it for the rest of this cycle the same way. Replies do not auto-resolve, especially bot threads.
- **Strip markup on automated comments before parsing.** Do not trust a failed `jq` match on an HTML-wrapped body as "no bot comments". Dump the raw body, strip tags/`<!-- ... -->`, then drop only **trailing** vendor chrome lines — never a mid-body `Generated by` / `Reviewed by` DOTALL cut. Trust per-thread `isResolved` (dump flag is valid except for ids in `PROCESSED_THREAD_IDS`; ids in `REPLIED_UNRESOLVED_THREAD_IDS` are still unresolved and must be resolve-only retries; ids in `REPLY_FAILED_THREAD_IDS` or `FIX_FAILED_THREAD_IDS` stay open and must be skipped for the rest of this cycle), not a bot's aggregate summary comment. Never reply to an already-resolved thread.
- **If a fix attempt fails**, log the error and do **not** retry that same attempt in this cycle. Restore the worktree **before** continuing other work on this PR. Abort in-progress stack ops (`gt abort --force --no-interactive` when `stack_type` is `"graphite"`, `gh stack rebase --abort` when `"github"`), then `git merge --abort` / `git rebase --abort` if needed. Then: if `git branch --show-current` is a named branch other than `<headRefName>` (checkout never succeeded), do **not** `git reset --hard origin/<headRefName>` — that rewrites the other shared branch tip; `git clean -fd` only. If a `gt restack` / `gh stack rebase` **completed** and only submit/push failed, do **not** rewind the current branch to origin (siblings stay at post-restack tips); discard uncommitted files only and leave local tips. Otherwise `git reset --hard origin/<headRefName>` and `git clean -fd`. Plain git abort is not enough after an interrupted `gt restack` / `gh stack rebase`. Reset-when-safe prevents the next `git add -A` from committing leftover partial edits or pushing an earlier unpushed commit that was marked `FIX_FAILED` and never replied to. For a failed **review-thread** code change, also append the thread GraphQL `id` to `FIX_FAILED_THREAD_IDS` so the bot pass does not retry it. Continue with remaining failed CI checks and unresolved review threads on the **same** PR, then proceed to the next PR. Next-cycle retry applies only to that failed item (or to `REPLY_FAILED` / `FIX_FAILED` / `REPLIED_UNRESOLVED`).
- **Always use `git add -A`** before committing to ensure new files are included. Only run it after recovery: either on the last successfully pushed tip (reset ran), or on the intact post-restack local tip when restack completed and push failed (reset skipped). Never `git add -A` on leftover dirty state from a failed attempt.
- **If the state file is corrupted or unreadable**, start fresh with `{"instance_id": "<INSTANCE_ID>", "prs": [], "groups": {}}`. Log that the state was reset.
- **Merge only from the ship cycle**, and only when `ship` is true. Follow `references/shipping.md`. The fix half of the decision tree never merges. Ship only the frontier. Never enable GitHub auto-merge on a PR whose base is not the repo default branch. While a frontier is armed, do not restack, `gt sync`, or `gt submit --stack`.
- **Graphite operations may race across parallel worktrees.** All worktrees share a single `.git` directory, and `gt` stores metadata in shared git refs/config. If multiple subagents run `gt restack` or `gt submit` concurrently on different stacks, they may corrupt graphite's internal state. Mitigation: if a `gt` command fails with an unexpected error, retry once after a 2-second pause. If graphite race issues are observed in practice, fall back to processing graphite stacks sequentially (only parallelize standalone PRs).
- **GitHub stacked PRs (`gh stack`) use explicit locking** (exit code 8: "Stack is locked by another process"). All worktrees share the same `.git` directory, and `gh stack` stores state in `.git/gh-stack`, so concurrent `gh stack` operations from different worktrees will hit lock contention — even when operating on different stacks. Mitigation: if a `gh stack` command fails with exit code 8 (locked), retry once after a 2-second pause. If lock contention is frequent, fall back to processing GitHub stacks sequentially (same guidance as Graphite above). If `gh stack` is not installed, fall back to plain git operations for GitHub-style stacked PRs.
- **Cross-machine stack detection**: When a PR was created with Graphite or `gh stack` on a different machine, local CLI metadata may not exist. The API-based chain detection (Method A in Step 3) is the primary detection mechanism and works regardless of local tool state. Tool-specific methods (B and C) are used to determine the correct CLI for operations, with fallback to plain git if neither tool is available.
- **GitHub Stacked PRs do not support cross-fork stacks.** All branches in a GitHub stack must be in the same repository. This is unlikely to be hit since the babysitter operates within a single repo, but be aware of this constraint during detection.
- **Set `NO_COLOR=1`** when using `gh api` to avoid ANSI escape codes in output.
