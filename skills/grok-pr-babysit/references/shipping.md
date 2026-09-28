# Ship cycle

Load this file when the command is `ship`, `ship on`, or `ship off`, or when a check cycle sees any watched PR with `ship: true`.

Babysit still stops at merge-ready. This cycle is the opt-in half that lands a PR. The live gates below are the only ship criteria; there is no separate external verdict.

Default stays no merge. The check-cycle fix subagent never merges. Only this cycle merges, and only the frontier.

## Commands

| Command | Behavior |
|---------|----------|
| `ship on [number...]` | Set `ship: true`. With no numbers, enable every watched PR in this repo. If a listed PR has a non-null `stack_id`, enable every PR that shares that `stack_id`. Do not fan out on `stack_id: null`. Do not run a cycle. |
| `ship off [number...]` | Disarm first, then set `ship: false` and clear `ship_status` / `ship_blocked_reason`. For every targeted PR that is armed on GitHub or Graphite (below), run **Disarm** and confirm the queue is off before clearing local state. Same non-null `stack_id` fan-out as `on`. |
| `ship [number...]` | If numbers are given, add any that are not watched (same add flow as `add --ship`), then set `ship: true` on that stack or PR. Then run one ship cycle. With no numbers, run one ship cycle on PRs that already have `ship: true`. If none do, print usage and stop. |

`add --ship <number>` sets `ship: true` on every PR registered in that invocation, including the rest of a detected stack.

A group is ship-enabled when any of its PRs has `ship: true`. Enabling one member of a stack enables the whole stack only when `stack_id` is a non-null string. `stack_id: null` is standalone. Never treat two standalones as the same stack.

## State

`ship`, `ship_status`, and `ship_blocked_reason` live on the PR entry in SKILL.md. `last_status` values used here are `"ship_armed"` and `"ship_blocked"`. MERGED or CLOSED still reports `removed: true`.

Migration is in the check-cycle state step. Missing `ship` becomes `false`. Missing `ship_status` or `ship_blocked_reason` becomes `null`.

## Who runs it

The check-cycle fix subagents never ship. After every group has finished the decision tree and the orchestrator has merged `pr_results`, the orchestrator runs the ship cycle as a second pass.

For each ship-enabled group, in order, one at a time:

- If `groups[group_key].subagent_id` exists, resume that subagent with this file and a ship-only prompt.
- If it does not, launch a fresh `spawn_subagent` with `isolation: "worktree"` and the same ship-only prompt. Store the new `subagent_id` and `worktree_path`. This is the path for `ship <number>` when no check cycle has run yet.

Never run `gt checkout` or `gt submit` in the main workspace. Do not launch the next group's ship until the current one has finished. `gt submit --merge-when-ready` must never run in two worktrees at once.

A `ship` command with no check work still uses this sequential pass.

Re-query GitHub live before every arm or merge. Do not trust `last_status` from this cycle or a prior one. A push from the same cycle leaves jobs pending. Pending fails the job gate. The next loop iteration ships.

## Ship-ready

A PR is ship-ready only when every gate below passes on a fresh query. Completion criterion: you can point at the command output that proves each gate.

### 1. Open and mergeable

```bash
gh pr view <number> --json state,isDraft,mergeable,mergeStateStatus,reviewDecision,baseRefName,headRefName,statusCheckRollup,author
```

Fail the gate when any of these hold:

- `state` is not `OPEN`
- `isDraft` is true
- `mergeable` is not `MERGEABLE`
- `mergeStateStatus` is `DIRTY` or `CONFLICTING`
- `reviewDecision` is `CHANGES_REQUESTED`

`UNKNOWN` mergeable is not ready. Wait. Do not ship.

### 2. Every job passed

Read `statusCheckRollup`. Every check must have finished with `SUCCESS`, `NEUTRAL`, or `SKIPPED`.

Fail the gate when any check is `IN_PROGRESS`, `QUEUED`, `PENDING`, or has conclusion `FAILURE`, `ERROR`, `CANCELLED`, `TIMED_OUT`, `STARTUP_FAILURE`, or `STALE`. Pending is not passed.

### 3. No open comments of any type

Re-run the review-thread pagination from SKILL.md "Unresolved Review Comments" and the issue-comment fetch from "Bot and automated comments". Do not reuse a dump from earlier in the cycle.

**Review threads.** Paginate every thread. Fail the gate if any thread has `isResolved == false`. Author does not matter. Human, `Bot`, `*[bot]`, Bugbot, Copilot, CodeRabbit, Semgrep, Dependabot, Renovate, Graphite, or anyone else. One unresolved thread blocks ship.

**Review decision.** `CHANGES_REQUESTED` already failed gate 1. Still fail here if a later query sees it.

**Issue comments (conversation tab).** Paginate `GET repos/{OWNER}/{REPO}/issues/{number}/comments`. Skip a comment before the open-comment test when any of these hold:

- it is a status notice (CI, queue, rebase, merge notification)
- its body starts with `Automated fix:` or `Addressed in `
- it is a bot aggregate summary whose findings are already represented as review threads (trust `isResolved` on those threads)

A remaining conversation comment is open when the author is not the PR author and no later closer exists.

A closer is a later conversation comment from the PR author or the authenticated `gh` user whose body starts with `Addressed in `. `Automated fix:` notes never close a finding. When the check cycle addresses a human conversation-tab finding, post `Addressed in <sha>: ...` after a fix or after a no-fix reply. The check cycle must apply this same later-closer skip so it does not reprocess a closed comment.

When unsure whether a bot comment is a summary or a real finding, treat it as open.

Any open conversation comment fails the gate.

There is no "almost ready". One open thread, one unanswered conversation comment, or one pending job blocks the frontier and therefore the stack.

## Frontier

Capture the group's PR list once, ordered by ascending `stack_position` (0 = closest to trunk). This list stays frozen for the rest of the cycle. Do not rediscover the stack after a parent merges. Drop a PR from the working list only when its live `state` is `MERGED` or `CLOSED`, and report `removed: true`.

The frontier is the first PR still on the working list.

Only the frontier may be shipped this cycle. If the frontier is not ship-ready, stop. Do not arm, merge, or enable auto-merge on any PR above it.

If the frontier is already armed and the failed gate is a wait state (`UNKNOWN` mergeable, pending jobs, merge-queue jobs), leave `ship_status` `"armed"`. Do not overwrite it with `"blocked"`.

If the frontier is not armed, or the failed gate is durable, set `ship_status` to `"blocked"` and `last_status` to `"ship_blocked"`. Write `ship_blocked_reason` from the failed gate.

A ready PR above a blocked or unmerged frontier is not landable. Merging it would pull the gap in underneath.

Standalone PRs (`stack_id` is null) are each their own frontier.

## Drain

If the frontier is armed (`ship_status` `"armed"`, `last_status` `"ship_armed"`, or live `isInMergeQueue`):

1. Re-query the ship-ready gates.
2. If the PR is MERGED, report `removed: true` and stop the ship cycle for this group. Do not arm the new frontier in this invocation. The next loop re-queries gates first. Do not run `gt sync`, `gt restack`, `gt submit --stack`, or any force-push.
3. If the gates still pass, leave it armed. Do not re-submit. Do not mutate the stack. Watch only.
4. If a **durable** gate fails, disarm (below), then resume the normal check-cycle decision tree. Durable means unresolved comments, `CHANGES_REQUESTED`, `CONFLICTING` / `DIRTY`, or a failed/error/cancelled/timed-out check. Do not disarm on wait states: `UNKNOWN` mergeable, pending/queued/in-progress jobs, or jobs that exist only because the merge queue is running. Leave the PR armed and watch.

While any PR in the group is armed, the check cycle makes no git mutation except disarm. No restack. No `gt submit --stack`. No `gt sync`. No speculative push. Bases retarget and `graphite-base/*` refs get cut as Graphite merges. That is the queue working, not damage.

## How to ship the frontier

Confirm local Graphite parentage before any `gt` command. The frontier's parent must be the repo default branch, or the next-lower stack branch that has already merged. If parentage is wrong, set `ship_blocked` and stop. Do not `gt submit` from a worktree whose parentage you have not just checked.

Never enable GitHub auto-merge on a PR whose `baseRefName` is not the repo default branch. Only the root targets protected trunk. Every child targets its unprotected parent and already reads `CLEAN`, so GitHub would merge the child into the parent and collapse the stack. If `autoMergeRequest` is set on such a child, run `gh pr merge <n> --disable-auto` and confirm it is off. Do not read `autoMergeRequest` as proof that Graphite merge-when-ready is armed. It stays off until Graphite reaches that PR at the queue front.

### Graphite (`stack_type` is `"graphite"`)

From the group worktree, on the frontier branch only:

```bash
gt checkout <headRefName> || git checkout -B <headRefName> origin/<headRefName>
CURRENT=$(git branch --show-current)
if [ "$CURRENT" != "<headRefName>" ]; then
  echo "ship blocked: wanted <headRefName>, HEAD is ${CURRENT:-detached}"
  # set ship_blocked; do not submit
  exit 1
fi
gt submit --merge-when-ready --always --update-only --no-interactive --no-stack
```

`--always` is required. A no-op submit skips the Graphite update and silently arms nothing. `--no-stack` is required. `--stack` would reach into unready upstack PRs. `--update-only` keeps this from opening new PRs.

Confirm arming from the `gt submit` output (it must mention merge-when-ready). If the output does not confirm it, do not set `ship_status` to `"armed"`. Set `ship_status` to `"blocked"` and `ship_blocked_reason` to `graphite mwr unconfirmed`. Say so. Do not infer success from GitHub `autoMergeRequest`.

Then make sure GitHub auto-merge is off:

```bash
gh pr merge <number> --disable-auto
```

Set `ship_status` to `"armed"` and `last_status` to `"ship_armed"` only after the submit output confirmed merge-when-ready.

If `gt` is missing or submit fails, fall back to the GitHub path only when `baseRefName` equals the repo default branch. Otherwise block.

Do not run `gt submit --no-merge-when-ready` as a disable. Graphite's submit API only *enables* merge-when-ready when the flag is true. A false or omitted flag skips enable. It does not turn MWR off. The public `gt` CLI has no disable-MWR command. Disarm is the **Disarm** section below.

### GitHub stacked PRs and plain chains (`stack_type` is `"github"` or `null`)

Ship only when `baseRefName` equals the repo default branch. That is the current bottom. After it merges, the next PR retargets onto trunk and becomes the frontier on a later cycle.

```bash
gh pr merge <number> --auto
```

Do not pass a strategy flag first. If the repo merge queue owns the method, `--squash` / `--merge` / `--rebase` is rejected and may fail to enqueue. If `gh` requires a method and there is no queue, query `gh repo view --json squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed` and pick squash when allowed, then merge, then rebase.

`--auto` waits for remaining merge requirements. Do not pass `--admin`. Do not merge a PR whose base is another PR branch.

If merge is refused (reviews, rulesets), set `ship_blocked` with the refusal. Do not bypass.

After a successful `--auto` (including "already queued"), set `ship_status` to `"armed"` and `last_status` to `"ship_armed"`. A queued PR that never got those fields still counts as armed. Treat live merge-queue membership as armed even when local state is null.

### Disarm

Run this before `ship off` clears state, and when Drain sees a durable failed gate on a PR **this babysitter armed**. A PR is armed for Drain / `ship off` / `remove` only when `ship` is `true` and any of these hold:

- `ship_status` is `"armed"` or `last_status` is `"ship_armed"`
- `gh pr merge <n>` reports it is already queued
- GraphQL `pullRequest.isInMergeQueue` is true

If `ship` is `false`, do not dequeue. Someone else may own that queue. Live `isInMergeQueue` alone is not a license to disarm.

```bash
# Always turn GitHub auto-merge off.
gh pr merge <number> --disable-auto

# If the repo uses a merge queue, dequeue. autoMergeRequest can be null while
# the PR is still queued. Trust isInMergeQueue / the gh pr merge "already queued" text.
PR_NODE=$(NO_COLOR=1 gh api graphql -f query='
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) { id isInMergeQueue }
  }
}' -f owner="<OWNER>" -f name="<REPO>" -F number=<number> | sed 's/\x1b\[[0-9;]*m//g')
IN_QUEUE=$(echo "$PR_NODE" | jq -r '.data.repository.pullRequest.isInMergeQueue')
PR_ID=$(echo "$PR_NODE" | jq -r '.data.repository.pullRequest.id')
if [ "$IN_QUEUE" = "true" ]; then
  NO_COLOR=1 gh api graphql -f query='
  mutation($id: ID!) {
    dequeuePullRequest(input: {id: $id}) { mergeQueueEntry { state } }
  }' -f id="$PR_ID"
fi
```

Then re-query `isInMergeQueue`. It must be false before you clear `ship_status`.

Graphite merge-when-ready is a separate toggle. `gt submit --no-merge-when-ready` does not disable it. After the GitHub dequeue above, turn MWR off in the Graphite dashboard (the toggle next to the merge button on that PR). Confirm it is off there, or say you could not confirm. Do not clear local `ship` / `ship_status` until dequeue succeeded. If Graphite MWR is still on and you cannot toggle it, leave `ship_status` `"armed"`, set `ship_blocked_reason` to that, and stop.

After a confirmed disarm:

- `ship off` sets `ship: false`, `ship_status: null`, and `last_status` to `"healthy"`.
- Drain after a failed gate keeps `ship: true`, sets `ship_status` to `"blocked"` and `last_status` to `"ship_blocked"`, then lets the check cycle fix the blocker. The next healthy cycle must still run Step 6b.

### Already armed

If this cycle would arm a frontier that is already armed and still ship-ready, do nothing to it. Idempotent.

## After a merge

The parent agent removes `removed: true` PRs from the watchlist, same as a MERGED check cycle. If the group still has PRs, keep the worktree. If the group is empty, Step 7 cleanup applies.

Do not extend the run above the old frontier in the same cycle. If this cycle merged or removed a PR, skip Step 6b for the rest of that group. The new frontier is the next loop's job, after a fresh gate query.

## Output

Each ship subagent ends with:

```json
{"ship_results": [
  {"number": 123, "last_status": "ship_armed", "ship_status": "armed", "ship_blocked_reason": null, "removed": false, "fix_count_delta": 0}
]}
```

Merge these into state the same way as `pr_results`. A ship-only invocation may omit `pr_results` when no check-cycle work ran.

Report to the user: the frontier, whether it was armed, merged, or blocked, the failed gate when blocked, and the next PR that is waiting.
