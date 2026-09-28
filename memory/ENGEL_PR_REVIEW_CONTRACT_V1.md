# Engel pull-request contract v1

Status: pilot. The collab branch is the pull request for the whole Engel AI Main tree. It is not a review of the phone worker app alone.

Authority: Josh > Guardian > Engel/runtime.

## Repository

- Git directory on this laptop: `D:\b.WorkSpace\engel-app-git-backup`
- Review work tree: `D:\b.WorkSpace\engel-app-reviews`
- Remote name: `ct246`
- Bare repo: `/opt/engel/backups/engel-app.git`
- Protected branch: `main`
- The workspace folder `D:\b.WorkSpace\Engel App\.git` stays empty. This contract does not put that git directory back.
- GitHub account `engelstands-hue` is the public source snapshot, repository `engel-ai-main`. It is not the CT246 history remote and it is not the live body. Nothing is pushed until Josh says to push. The git commands stay the same.

The bare repo symbolic HEAD on CT246 still says `refs/heads/master`. `refs/heads/main` is the commit this pilot branches from. This contract does not retarget that symbolic HEAD.

## What a pull request is

A pull request is a real git branch named `collab/<date>-<slug>` on the Engel AI Main repository. The branch contains that whole tree: chat, Discord, desks, skills, agents, the phone worker, and the rest of `main`. A review may name any path in the tree. The phone worker is one path, not the boundary of the review.

- `collab/<slug>/BRIEF.md` is the first commit. It names the job. Later agents do not edit it.
- Each later turn is a new file `collab/<slug>/turns/<utc>-<agent>.md` and its own commit.
- The commit author is the agent. `git log` is the canonical order.
- Agents do not edit another agent's turn file.
- Several agents may commit on the same branch at once. Push is fetch, rebase, push. Force-push is refused.
- `git diff main...collab/<date>-<slug>` is the review.
- Josh accepts the branch with `git merge --no-ff` into `main`. Squash is not the default.
- A receipt may point at the branch. The receipt is not the pull request.

## Who may write

A dispatched agent, local or cloud, may open a collab branch or add one turn file. That includes Engel Pstack Poteto, Engel Pstack Comment Sicko, Engel Pstack Benny, and a Discord desk that was dispatched onto the branch.

An agent may not merge, force-push, push over `main`, copy files into live `/opt/engel`, restart a service, or start a watcher that opens the next branch.

Benny does not post to Slack. A Benny verdict is a turn file.

Discord mouths, the Meeting Room, and phone sandboxes may quote the branch name. They are not a second collab log.

## Before merge

- Run the verifier that matches the touched files.
- When more than one agent was dispatched, the branch has at least two turn files.
- Secrets, tokens, SSH keys, and Discord credentials are not in the commit.
- Merge does not restart services and does not copy files into `/opt/engel`.
- A push of a collab branch to the bare repo is the shared record. It is not permission to rearrange `/opt/engel/backups/`.

## Cloud agents later

A Cloud Agent uses the same branch, the same turn files, and the same commands once it can clone the remote. Turn files do not contain a laptop path, an SSH key, or a Discord token.

## Related agents

- `agents/engel-pstack-poteto.md`
- `agents/engel-pstack-comment-sicko.md`
- `agents/engel-pstack-benny.md`
- `memory/agents/ENGEL_PSTACK_AGENT_BINDINGS.json`
