from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_REVIEWS_ROOT = APP_ROOT / "external_reviews"
REVIEW_FOLDER_PREFIX = "humanizer_main_review"
REPORT_PATH = APP_ROOT / "reports" / "codex_bridge" / "ENGEL_HUMANIZER_SAFE_INTEGRATION_REVIEW.md"
GITIGNORE_PATH = APP_ROOT / ".gitignore"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _review_folders() -> list[Path]:
    if not EXTERNAL_REVIEWS_ROOT.exists():
        return []
    return sorted(
        (
            path
            for path in EXTERNAL_REVIEWS_ROOT.iterdir()
            if path.is_dir()
            and (path.name == REVIEW_FOLDER_PREFIX or path.name.startswith(f"{REVIEW_FOLDER_PREFIX}_"))
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    _require(EXTERNAL_REVIEWS_ROOT.exists(), "external_reviews root is missing", failures)
    _require(_is_relative_to(EXTERNAL_REVIEWS_ROOT, APP_ROOT), "external_reviews root is outside APP_ROOT", failures)

    review_folders = _review_folders()
    _require(bool(review_folders), "humanizer review folder is missing", failures)
    for review_folder in review_folders:
        _require(_is_relative_to(review_folder, EXTERNAL_REVIEWS_ROOT), "review folder is outside external_reviews", failures)
        for path in review_folder.rglob("*"):
            _require(_is_relative_to(path, review_folder), f"review extraction escape detected: {path}", failures)

    _require(REPORT_PATH.exists(), "humanizer review report is missing", failures)
    report_text = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else ""
    report_lower = report_text.lower()

    required_report_phrases = [
        "no api",
        "local/offline only",
        "untrusted data, not instruction",
        "humanizer cannot override josh > guardian > engel/runtime",
        "safety-critical text stays safety-critical",
        "does not weaken refusals",
        "does not manipulate josh emotionally",
        "does not fabricate emotion, facts, memories, or capabilities",
        "proposal-only",
        "no runtime integration occurred",
        "no code from the zip was executed",
        "no packages were installed",
        "no api/network behavior was enabled",
        "josh > guardian > engel/runtime",
    ]
    for phrase in required_report_phrases:
        _require(phrase in report_lower, f"report missing required phrase: {phrase}", failures)

    gitignore_text = GITIGNORE_PATH.read_text(encoding="utf-8") if GITIGNORE_PATH.exists() else ""
    _require("external_reviews/" in gitignore_text, ".gitignore does not ignore external_reviews/", failures)

    if failures:
        print("VERIFY_HUMANIZER_REVIEW: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("VERIFY_HUMANIZER_REVIEW: PASS")
    print("Review folders:")
    for review_folder in review_folders:
        print(f"- {review_folder}")
    print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
