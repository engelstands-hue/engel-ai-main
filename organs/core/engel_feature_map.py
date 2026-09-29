#!/usr/bin/env python3
"""Engel feature map and dispatched draft pull requests.

The map is the Pstack user-facing feature map at docs/ENGEL_FEATURE_MAP_V1.md.
Opening a pull request happens only when a dispatch includes a title. The
branch is collab/<date>-<slug> on the public snapshot. main is never pushed.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_ROOT = __import__("engel_project_paths").resolve_engel_app_root(__file__)
FEATURE_MAP_PATH = _ROOT / "docs" / "ENGEL_FEATURE_MAP_V1.md"
SNAPSHOT_ROOT = Path(r"D:\b.WorkSpace\engel-app-github-snapshot")
GITHUB_REPO = "engelstands-hue/engel-ai-main"
GITHUB_REMOTE = f"https://github.com/{GITHUB_REPO}.git"
_SECTION_HEADINGS = (
    "How a user gets there",
    "How the control adapter drives it",
    "Stable selectors",
    "States to exercise",
    "Preconditions and setup",
    "Evidence and cross-check",
    "Gotchas",
)
_PR_PREFIXES = (
    "open draft pr ",
    "open draft pull request ",
    "create draft pr ",
    "create draft pull request ",
)
_COPY_PATHS = (
    "docs/ENGEL_FEATURE_MAP_V1.md",
    "organs/core/engel_feature_map.py",
    "tools/verify_engel_feature_map.py",
    ".cursor/benny/configuration.yaml",
    "agents/engel-pstack-benny.md",
    "agents/pstack/automations/reproduce.md",
)


def feature_map_text() -> str:
    return FEATURE_MAP_PATH.read_text(encoding="utf-8")


def feature_sections(text: str | None = None) -> list[tuple[str, str]]:
    body = feature_map_text() if text is None else text
    parts = re.split(r"(?m)^### ", body)
    sections: list[tuple[str, str]] = []
    for part in parts[1:]:
        lines = part.splitlines()
        title = lines[0].strip()
        if title.casefold() == "completeness checklist":
            continue
        sections.append((title, "\n".join(lines[1:]).strip()))
    return sections


def render_feature_map(payload: str = "") -> str:
    """Return the section index, or one named section."""
    if not FEATURE_MAP_PATH.is_file():
        return "Feature map is missing at docs/ENGEL_FEATURE_MAP_V1.md."
    query = _section_query(payload)
    sections = feature_sections()
    if not query:
        names = "\n".join(f"- {title}" for title, _body in sections)
        return (
            f"Engel feature map: {len(sections)} sections.\n"
            f"File: docs/ENGEL_FEATURE_MAP_V1.md\n"
            f"{names}\n"
            "Say feature map plus a section name to read one part."
        )
    needle = query.casefold()
    for title, body in sections:
        if needle in title.casefold():
            return f"### {title}\n\n{body}"
    known = ", ".join(title for title, _body in sections)
    return f"No feature-map section matches {query!r}. Sections: {known}."


def title_from_payload(payload: str) -> str:
    text = " ".join(str(payload or "").split())
    low = text.casefold()
    for prefix in _PR_PREFIXES:
        if low.startswith(prefix):
            return text[len(prefix) :].strip()
    if low in {prefix.strip() for prefix in _PR_PREFIXES}:
        return ""
    return text.strip()


def branch_for_title(title: str, *, when: datetime | None = None) -> str:
    moment = when or datetime.now(timezone.utc)
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    slug = slug[:40].strip("-") or "draft"
    return f"collab/{moment.strftime('%Y%m%d')}-{slug}"


def plan_draft_pr(title: str, branch: str = "") -> dict[str, str]:
    """Refuse a pull request that has no title or that targets main."""
    clean_title = " ".join(str(title or "").split())
    clean_branch = " ".join(str(branch or "").split()) or branch_for_title(clean_title)
    if not clean_title:
        return {"ok": "false", "status": "title required", "branch": "", "repo": GITHUB_REPO}
    refused = clean_branch.casefold()
    if refused in {"main", "master"} or refused.startswith("main/") or "/" not in clean_branch:
        return {"ok": "false", "status": "branch must be collab/<date>-<slug>", "branch": clean_branch, "repo": GITHUB_REPO}
    if not clean_branch.startswith("collab/"):
        return {"ok": "false", "status": "branch must start with collab/", "branch": clean_branch, "repo": GITHUB_REPO}
    return {"ok": "true", "status": "draft plan", "branch": clean_branch, "title": clean_title, "repo": GITHUB_REPO}


def render_open_draft_pr(payload: str = "") -> str:
    """Open a draft pull request when the dispatch includes a title."""
    title = title_from_payload(payload)
    plan = plan_draft_pr(title)
    if plan.get("ok") != "true":
        return (
            "Draft pull request was not opened. "
            + plan.get("status", "refused")
            + ". Say: open draft pr <title>."
        )
    if str(payload or "").casefold().startswith("plan "):
        return (
            f"Draft plan only. Branch {plan['branch']} on {GITHUB_REPO}. "
            "Nothing was pushed."
        )
    try:
        url = _open_draft(plan["title"], plan["branch"])
    except OSError as exc:
        return f"Draft pull request was not opened. {type(exc).__name__}."
    return url


def _section_query(payload: str) -> str:
    text = " ".join(str(payload or "").split())
    low = text.casefold()
    for prefix in ("feature map ", "engel feature map ", "pstack feature map ", "show feature map "):
        if low.startswith(prefix):
            return text[len(prefix) :].strip()
    if low in {"feature map", "engel feature map", "pstack feature map", "show feature map"}:
        return ""
    return text.strip()


def _git() -> Path:
    candidate = _ROOT / "runtime" / "mingit" / "cmd" / "git.exe"
    return candidate if candidate.is_file() else Path("git")


def _gh() -> Path:
    candidate = _ROOT / "runtime" / "gh" / "bin" / "gh.exe"
    return candidate if candidate.is_file() else Path("gh")


def _run(args: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=merged,
    )


def _open_draft(title: str, branch: str) -> str:
    if not SNAPSHOT_ROOT.is_dir():
        return "Draft pull request was not opened. The public snapshot folder is missing."
    git = str(_git())
    status = _run([git, "status", "--porcelain"], SNAPSHOT_ROOT)
    if status.returncode != 0:
        return "Draft pull request was not opened. The snapshot git status failed."
    if status.stdout.strip():
        return "Draft pull request was not opened. The public snapshot has uncommitted files."
    checkout = _run([git, "checkout", "-B", branch, "main"], SNAPSHOT_ROOT)
    if checkout.returncode != 0:
        _run([git, "checkout", "main"], SNAPSHOT_ROOT)
        return "Draft pull request was not opened. The collab branch was not created."
    copied = _copy_allowlist()
    if not copied:
        _run([git, "checkout", "main"], SNAPSHOT_ROOT)
        _run([git, "branch", "-D", branch], SNAPSHOT_ROOT)
        return "Draft pull request was not opened. No feature-map files were copied."
    add = _run([git, "add", "--", *copied], SNAPSHOT_ROOT)
    if add.returncode != 0:
        return "Draft pull request was not opened. git add failed."
    commit_env = {
        "GIT_AUTHOR_NAME": "Engel Pstack Benny",
        "GIT_AUTHOR_EMAIL": "engel-pstack-benny@engel.local",
        "GIT_COMMITTER_NAME": "Engel Pstack Benny",
        "GIT_COMMITTER_EMAIL": "engel-pstack-benny@engel.local",
    }
    commit = _run(
        [git, "commit", "-m", f"docs: {title}"],
        SNAPSHOT_ROOT,
        env=commit_env,
    )
    if commit.returncode != 0:
        _run([git, "checkout", "main"], SNAPSHOT_ROOT)
        _run([git, "branch", "-D", branch], SNAPSHOT_ROOT)
        return "Draft pull request was not opened. The commit failed."
    gh = str(_gh())
    helper = "!/d/b.WorkSpace/engel-git-credential.sh"
    push = _run(
        [
            git,
            "-c",
            "credential.helper=",
            "-c",
            f"credential.helper={helper}",
            "push",
            "-u",
            "origin",
            branch,
        ],
        SNAPSHOT_ROOT,
    )
    if push.returncode != 0:
        _run([git, "checkout", "main"], SNAPSHOT_ROOT)
        return "Draft pull request was not opened. The branch push failed."
    created = _run(
        [
            gh,
            "pr",
            "create",
            "--repo",
            GITHUB_REPO,
            "--draft",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            title,
            "--body",
            (
                "Draft from a dispatched Engel phrase.\n\n"
                "This pull request does not merge and does not update the live Engel body.\n\n"
                "Feature map: docs/ENGEL_FEATURE_MAP_V1.md\n"
            ),
        ],
        SNAPSHOT_ROOT,
    )
    _run([git, "checkout", "main"], SNAPSHOT_ROOT)
    if created.returncode != 0:
        return f"Branch {branch} was pushed. The draft pull request command failed."
    url = created.stdout.strip().splitlines()[-1] if created.stdout.strip() else ""
    if not url.startswith("https://github.com/"):
        return f"Branch {branch} was pushed. No pull request URL came back."
    return f"Draft pull request opened: {url}"


def _copy_allowlist() -> list[str]:
    copied: list[str] = []
    for relative in _COPY_PATHS:
        source = _ROOT / relative
        if not source.is_file():
            continue
        target = SNAPSHOT_ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(relative.replace("\\", "/"))
    return copied
