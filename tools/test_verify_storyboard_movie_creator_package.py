#!/usr/bin/env python3
"""Focused tests for the Storyboard tester-package verifier."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import verify_storyboard_movie_creator_package as verifier


class StoryboardPackageVerifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="Storyboard Package Tests With Spaces ")
        self.root = Path(self.temporary.name)
        self.package = self.root / "staged package"
        self.package.mkdir()
        self.version = "1.1.0+2"
        self.zip_path = self.root / "StoryboardMovieCreator-1.1.0_2-win-x64.zip"
        self._write_initial_files()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_initial_files(self) -> None:
        text_files = {
            "README-FIRST.txt": "Local-first tester instructions.\n",
            "TEST-CHECKLIST.md": "# Checklist\n",
            "ISSUE-REPORT-TEMPLATE.md": "# Issue report\n",
            "RELEASE-NOTES.md": "# Release notes\n",
            "RUN-TESTER.cmd": "@echo off\r\nexit /b 0\r\n",
            "VERSION.txt": self.version + "\n",
        }
        for relative, content in text_files.items():
            (self.package / relative).write_text(content, encoding="utf-8")
        (self.package / "storyboard_movie_creator.exe").write_bytes(b"synthetic-test-exe")
        approved_root = Path(__file__).resolve().parents[1] / "assets" / "branding" / "final"
        approved_sources = {
            "data/flutter_assets/assets/branding/engel-winged-orbital-mark.png": (
                approved_root / "engel-winged-orbital-mark.png"
            ),
            "data/flutter_assets/assets/branding/engel-desktop-bg.png": (
                approved_root / "engel_desktop_bg_final.png"
            ),
        }
        for relative, source in approved_sources.items():
            destination = self.package / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

    def _manifest(self) -> dict[str, object]:
        rows = []
        for relative, path in sorted(verifier.package_files(self.package).items()):
            rows.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": verifier.sha256(path),
                }
            )
        return {
            "schema": "engel_storyboard_movie_creator_release_manifest_v1",
            "product": "Engel Storyboard Movie Creator",
            "publisher": "Engel AI Labs",
            "version": self.version,
            "version_slug": verifier.safe_version_slug(self.version),
            "platform": "windows-x64",
            "packaged_at_utc": "2026-08-22T00:00:00Z",
            "signed": False,
            "publisher_warning": "Unsigned tester build; Windows may show Unknown Publisher.",
            "local_first": True,
            "private_project_data_included": False,
            "branding": dict(verifier.EXPECTED_BRANDING),
            "gates": dict(verifier.EXPECTED_GATES),
            "files": rows,
        }

    def _finish_package(
        self,
        *,
        mutate_manifest=None,
        extra_unlisted_file: bool = False,
        zip_override: tuple[str, bytes] | None = None,
    ) -> None:
        manifest = self._manifest()
        if mutate_manifest is not None:
            mutate_manifest(manifest)
        (self.package / "BUILD-MANIFEST.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        if extra_unlisted_file:
            (self.package / "unlisted.txt").write_text("not in manifest\n", encoding="utf-8")

        sums = []
        for relative, path in sorted(verifier.package_files(self.package).items()):
            sums.append(f"{verifier.sha256(path)}  {relative}")
        (self.package / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")

        with zipfile.ZipFile(self.zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative, path in sorted(verifier.package_files(self.package).items()):
                if zip_override is not None and relative == zip_override[0]:
                    archive.writestr(relative, zip_override[1])
                else:
                    archive.write(path, relative)
        digest = hashlib.sha256(self.zip_path.read_bytes()).hexdigest()
        Path(str(self.zip_path) + ".sha256.txt").write_text(
            f"{digest}  {self.zip_path.name}\n", encoding="ascii"
        )

    def test_accepts_full_version_and_extracts_in_path_with_spaces(self) -> None:
        self._finish_package()
        verifier.verify(self.package, self.zip_path)

    def test_accepts_prerelease_and_build_version_without_truncation(self) -> None:
        self.version = "2.4.0-rc.3+build.17"
        self.zip_path = self.root / "StoryboardMovieCreator-2.4.0-rc.3_build.17-win-x64.zip"
        (self.package / "VERSION.txt").write_text(
            self.version + "\n", encoding="utf-8"
        )
        self._finish_package()
        verifier.verify(self.package, self.zip_path)

    def test_branding_contract_requires_graph_studio_assets_only(self) -> None:
        self.assertEqual(
            verifier.APPROVED_BRAND_ASSETS,
            {
                "data/flutter_assets/assets/branding/engel-winged-orbital-mark.png": (
                    "0b98aa6dc8334c7242f565558f2ce4313b467bea8ad4a03bdeb4d26ae39df270"
                ),
                "data/flutter_assets/assets/branding/engel-desktop-bg.png": (
                    "6cb92c93913ca6b7a76b8c625b208588be0dc87254718e45c4e4a4197af51cbe"
                ),
            },
        )
        self.assertNotIn(
            "data/flutter_assets/assets/branding/engel-mark-192.png",
            verifier.REQUIRED,
        )
        self.assertNotIn("approved_brand_mark_sha256", verifier.EXPECTED_BRANDING)

    def test_rejects_tampered_winged_orbital_mark(self) -> None:
        mark = self.package / (
            "data/flutter_assets/assets/branding/engel-winged-orbital-mark.png"
        )
        mark.write_bytes(b"not-the-approved-winged-orbital-mark")
        self._finish_package()
        with self.assertRaisesRegex(
            verifier.VerificationError, "winged-orbital-mark.png"
        ):
            verifier.verify(self.package, self.zip_path)

    def test_rejects_tampered_desktop_background(self) -> None:
        background = self.package / (
            "data/flutter_assets/assets/branding/engel-desktop-bg.png"
        )
        background.write_bytes(b"not-the-approved-desktop-background")
        self._finish_package()
        with self.assertRaisesRegex(verifier.VerificationError, "engel-desktop-bg.png"):
            verifier.verify(self.package, self.zip_path)

    def test_rejects_legacy_constellation_manifest_contract(self) -> None:
        def use_legacy_branding(manifest: dict[str, object]) -> None:
            branding = dict(manifest["branding"])
            branding.pop("approved_winged_orbital_mark_path")
            branding.pop("approved_winged_orbital_mark_sha256")
            branding.pop("approved_desktop_background_path")
            branding.pop("approved_desktop_background_sha256")
            branding["approved_brand_mark_sha256"] = (
                "88c25b5aaf020012db7955b733b8169a56f9e2723008c7bf55864d1e5b6f8f99"
            )
            manifest["branding"] = branding

        self._finish_package(mutate_manifest=use_legacy_branding)
        with self.assertRaisesRegex(verifier.VerificationError, "branding contract"):
            verifier.verify(self.package, self.zip_path)

    def test_rejects_non_exact_green_gate_keys(self) -> None:
        def add_gate(manifest: dict[str, object]) -> None:
            manifest["gates"] = {**verifier.EXPECTED_GATES, "unexpected_gate": "passed"}

        self._finish_package(mutate_manifest=add_gate)
        with self.assertRaisesRegex(verifier.VerificationError, "build-gate keys"):
            verifier.verify(self.package, self.zip_path)

    def test_rejects_manifest_roster_omission(self) -> None:
        self._finish_package(extra_unlisted_file=True)
        with self.assertRaisesRegex(verifier.VerificationError, "manifest roster"):
            verifier.verify(self.package, self.zip_path)

    def test_rejects_extracted_zip_hash_difference(self) -> None:
        self._finish_package(
            zip_override=("README-FIRST.txt", b"different bytes in the archive\n")
        )
        with self.assertRaisesRegex(verifier.VerificationError, "extracted ZIP hash mismatch"):
            verifier.verify(self.package, self.zip_path)


if __name__ == "__main__":
    unittest.main()
