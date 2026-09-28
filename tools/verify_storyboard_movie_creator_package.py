#!/usr/bin/env python3
"""Verify a staged Storyboard Movie Creator tester package without launching it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


REQUIRED = {
    "storyboard_movie_creator.exe",
    "README-FIRST.txt",
    "TEST-CHECKLIST.md",
    "ISSUE-REPORT-TEMPLATE.md",
    "RELEASE-NOTES.md",
    "RUN-TESTER.cmd",
    "VERSION.txt",
    "BUILD-MANIFEST.json",
    "SHA256SUMS.txt",
    "data/flutter_assets/assets/branding/engel-winged-orbital-mark.png",
    "data/flutter_assets/assets/branding/engel-desktop-bg.png",
}
MANIFEST_EXCLUSIONS = {"BUILD-MANIFEST.json", "SHA256SUMS.txt"}
CHECKSUM_EXCLUSIONS = {"SHA256SUMS.txt"}
TEXT_SUFFIXES = {".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".manifest", ".cmd"}
PRIVATE_PATTERNS = (
    re.compile(r"C:\\Users\\", re.IGNORECASE),
    re.compile(r"D:\\b\.WorkSpace", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret|password)\s*[:=]\s*[^\s\"']+", re.IGNORECASE),
    re.compile(
        r"(?<!\d)(?:10\.|127\.0\.0\.1|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)"
        r"\d{1,3}(?:\.\d{1,3}){2}(?!\d)"
    ),
)
VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CHECKSUM_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
EXPECTED_GATES = {
    "dart_format": "passed",
    "flutter_analyze": "passed",
    "flutter_test": "passed",
    "flutter_windows_release": "passed",
}
EXPECTED_BRANDING = {
    "company_name": "Engel AI Labs",
    "file_description": "Engel Storyboard Movie Creator",
    "product_name": "Engel Storyboard Movie Creator",
    "internal_name": "storyboard_movie_creator",
    "original_filename": "storyboard_movie_creator.exe",
    "legal_copyright": "Copyright (C) 2026 Engel AI Labs. All rights reserved.",
    "window_title": "Engel Storyboard Movie Creator",
    "approved_icon_sha256": "171e758d1b99b9b09b4d4ad90eac16960ff62c3f4b0403c2c3c4045672dbad5d",
    "approved_winged_orbital_mark_path": "data/flutter_assets/assets/branding/engel-winged-orbital-mark.png",
    "approved_winged_orbital_mark_sha256": "0b98aa6dc8334c7242f565558f2ce4313b467bea8ad4a03bdeb4d26ae39df270",
    "approved_desktop_background_path": "data/flutter_assets/assets/branding/engel-desktop-bg.png",
    "approved_desktop_background_sha256": "6cb92c93913ca6b7a76b8c625b208588be0dc87254718e45c4e4a4197af51cbe",
}
APPROVED_BRAND_ASSETS = {
    EXPECTED_BRANDING["approved_winged_orbital_mark_path"]: EXPECTED_BRANDING[
        "approved_winged_orbital_mark_sha256"
    ],
    EXPECTED_BRANDING["approved_desktop_background_path"]: EXPECTED_BRANDING[
        "approved_desktop_background_sha256"
    ],
}


class VerificationError(RuntimeError):
    """Raised when a package fails a deterministic release contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> int:
    print(f"FAIL verify_storyboard_movie_creator_package: {message}", file=sys.stderr)
    return 1


def safe_version_slug(version: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]", "_", version)


def package_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }


def require_exact_manifest_roster(
    manifest: dict[str, object], relative_files: dict[str, Path]
) -> None:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise VerificationError("manifest files value is not a list")

    manifest_files: dict[str, dict[str, object]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise VerificationError(f"manifest row {index} has an unexpected schema")
        relative = row.get("path")
        length = row.get("bytes")
        digest = row.get("sha256")
        if not isinstance(relative, str) or not relative:
            raise VerificationError(f"manifest row {index} has no valid path")
        if relative in manifest_files:
            raise VerificationError(f"manifest contains duplicate path: {relative}")
        if not isinstance(length, int) or isinstance(length, bool) or length < 0:
            raise VerificationError(f"manifest row has invalid byte count: {relative}")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise VerificationError(f"manifest row has invalid SHA-256: {relative}")
        manifest_files[relative] = row

    expected = set(relative_files) - MANIFEST_EXCLUSIONS
    actual = set(manifest_files)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if extra:
            details.append(f"extra={','.join(extra)}")
        raise VerificationError("manifest roster differs from staged package: " + " ".join(details))

    for relative, row in manifest_files.items():
        path = relative_files[relative]
        if path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
            raise VerificationError(f"manifest hash mismatch: {relative}")


def require_exact_checksums(relative_files: dict[str, Path]) -> None:
    checksum_path = relative_files["SHA256SUMS.txt"]
    checksum_rows: dict[str, str] = {}
    for number, raw_line in enumerate(
        checksum_path.read_text(encoding="ascii").splitlines(), start=1
    ):
        match = CHECKSUM_LINE_PATTERN.fullmatch(raw_line)
        if not match:
            raise VerificationError(f"invalid SHA256SUMS.txt line {number}")
        digest, relative = match.groups()
        if relative in checksum_rows:
            raise VerificationError(f"duplicate SHA256SUMS.txt path: {relative}")
        checksum_rows[relative] = digest

    expected = set(relative_files) - CHECKSUM_EXCLUSIONS
    if set(checksum_rows) != expected:
        raise VerificationError("SHA256SUMS.txt roster differs from staged package")
    for relative, digest in checksum_rows.items():
        if sha256(relative_files[relative]) != digest:
            raise VerificationError(f"SHA256SUMS.txt hash mismatch: {relative}")


def checked_zip_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        raw_name = info.filename
        posix_name = PurePosixPath(raw_name)
        normalized = posix_name.as_posix()
        if (
            not raw_name
            or "\\" in raw_name
            or raw_name.startswith("/")
            or posix_name.is_absolute()
            or not posix_name.parts
            or raw_name != normalized
            or any(part in {"", ".", ".."} for part in posix_name.parts)
            or ":" in posix_name.parts[0]
        ):
            raise VerificationError(f"ZIP contains unsafe path: {raw_name}")
        unix_type = (info.external_attr >> 16) & 0o170000
        if unix_type == stat.S_IFLNK:
            raise VerificationError(f"ZIP contains a symbolic link: {raw_name}")
        if normalized in members:
            raise VerificationError(f"ZIP contains duplicate path: {normalized}")
        members[normalized] = info
    return members


def require_extractable_zip(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    relative_files: dict[str, Path],
) -> None:
    with tempfile.TemporaryDirectory(prefix="Engel Storyboard Verify With Spaces ") as temporary:
        extract_root = Path(temporary) / "extracted package"
        if " " not in str(extract_root):
            raise VerificationError("internal extraction test path does not contain spaces")
        extract_root.mkdir(parents=True)
        archive.extractall(extract_root)
        extracted_files = package_files(extract_root)
        if set(extracted_files) != set(relative_files):
            raise VerificationError("extracted ZIP roster differs from staged package")
        for relative in members:
            if sha256(extracted_files[relative]) != sha256(relative_files[relative]):
                raise VerificationError(f"extracted ZIP hash mismatch: {relative}")


def verify(package: Path, zip_path: Path) -> None:
    package = package.resolve()
    zip_path = zip_path.resolve()
    if not package.is_dir():
        raise VerificationError("package directory is missing")
    if not zip_path.is_file():
        raise VerificationError("ZIP is missing")

    relative_files = package_files(package)
    missing = sorted(REQUIRED - set(relative_files))
    if missing:
        raise VerificationError(f"required files missing: {', '.join(missing)}")

    version = relative_files["VERSION.txt"].read_text(encoding="utf-8-sig").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise VerificationError("VERSION.txt is not a supported pubspec semantic version")
    version_slug = safe_version_slug(version)
    expected_zip_name = f"StoryboardMovieCreator-{version_slug}-win-x64.zip"
    if zip_path.name != expected_zip_name:
        raise VerificationError(
            f"ZIP filename does not preserve the safe version slug: expected {expected_zip_name}"
        )

    try:
        manifest = json.loads(
            relative_files["BUILD-MANIFEST.json"].read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"BUILD-MANIFEST.json is unreadable: {error}") from error
    if not isinstance(manifest, dict):
        raise VerificationError("BUILD-MANIFEST.json root is not an object")
    if manifest.get("schema") != "engel_storyboard_movie_creator_release_manifest_v1":
        raise VerificationError("unexpected manifest schema")
    if manifest.get("product") != "Engel Storyboard Movie Creator":
        raise VerificationError("unexpected manifest product")
    if manifest.get("publisher") != "Engel AI Labs":
        raise VerificationError("unexpected manifest publisher")
    if manifest.get("version") != version:
        raise VerificationError("VERSION.txt does not match BUILD-MANIFEST.json")
    if manifest.get("version_slug") != version_slug:
        raise VerificationError("manifest version_slug is not the safe form of the full version")
    if manifest.get("platform") != "windows-x64":
        raise VerificationError("unexpected manifest platform")
    if manifest.get("signed") is not False:
        raise VerificationError("tester manifest must state unsigned status honestly")
    if manifest.get("local_first") is not True:
        raise VerificationError("manifest does not assert local-first operation")
    if manifest.get("private_project_data_included") is not False:
        raise VerificationError("manifest does not reject private project data")
    if manifest.get("branding") != EXPECTED_BRANDING:
        raise VerificationError("manifest branding contract is incomplete or unexpected")
    if manifest.get("gates") != EXPECTED_GATES:
        raise VerificationError("manifest build-gate keys or values are not exact")

    for relative, approved_hash in APPROVED_BRAND_ASSETS.items():
        if sha256(relative_files[relative]) != approved_hash:
            raise VerificationError(
                f"packaged Engel branding asset is not approved: {relative}"
            )

    require_exact_manifest_roster(manifest, relative_files)
    require_exact_checksums(relative_files)

    for relative, path in relative_files.items():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(text):
                raise VerificationError(f"privacy marker found in {relative}")

    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = checked_zip_members(archive)
            if set(members) != set(relative_files):
                raise VerificationError("ZIP file roster differs from staged package")
            require_extractable_zip(archive, members, relative_files)
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, VerificationError):
            raise
        raise VerificationError(f"ZIP is unreadable: {error}") from error

    sidecar = Path(str(zip_path) + ".sha256.txt")
    expected_sidecar = f"{sha256(zip_path)}  {zip_path.name}"
    try:
        actual_sidecar = sidecar.read_text(encoding="ascii").strip()
    except OSError as error:
        raise VerificationError("ZIP checksum sidecar is missing") from error
    if actual_sidecar != expected_sidecar:
        raise VerificationError("ZIP checksum sidecar is incorrect or names another archive")

    print(
        "PASS verify_storyboard_movie_creator_package "
        f"files={len(relative_files)} zip={zip_path.name} version={version} "
        "extraction_path_with_spaces=passed"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.package, args.zip_path)
    except VerificationError as error:
        return fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
