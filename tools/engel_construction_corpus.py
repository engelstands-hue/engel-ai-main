#!/usr/bin/env python3
"""Construction code corpus: the aec discipline's ground truth.

(2026-08-08, operator-supplied training data) The Construction curriculum was the one
discipline with no correctness-class gate -- math has the CAS, engineering has artifact
citations + code execution, communication has the voice gate, but an aec answer could
cite "Section 1607.12" of a building code and nothing could say whether that section
exists. The operator supplies the actual code volumes (building / residential / existing
building codes + supplements) as PDFs; this module turns them into a page-level corpus
and a section index so cited sections become CHECKABLE.

Flow:
  1. Operator drops the PDFs into  memory/training/construction_env/source_pdfs/
  2. `python tools/engel_construction_corpus.py --ingest`  extracts every page to JSONL
     (fitz, pypdf fallback), builds CONSTRUCTION_SECTION_INDEX.json mapping normalized
     section ids -> [{doc, page}], and writes a manifest with sha256 per source so
     re-ingest only touches changed files.
  3. The trainer's aec admission branch calls grade_reply(). A missing id can be
     refuted only when the index is demonstrably complete; an existing id is exactly
     verified only when the citing sentence's claims and quantities are supported by
     the local section evidence. Everything else stays undecidable and is excluded
     from fail-closed AEC training admission.

No-C rule: everything lives under the Engel App tree on D:.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "memory" / "training" / "construction_env"
SOURCE_DIR_NAME = "source_pdfs"
EXTRACT_DIR_NAME = "extracted"
INDEX_NAME = "CONSTRUCTION_SECTION_INDEX.json"
MANIFEST_NAME = "CONSTRUCTION_CORPUS_MANIFEST.json"
MANIFEST_SCHEMA = "engel_construction_corpus_manifest_v2"
INDEX_SCHEMA = "engel_construction_section_index_v2"
BUNDLE_VERIFY_SCHEMA = "engel_construction_corpus_bundle_verification_v2"
CORPUS_ROOT_ENV = "ENGEL_CONSTRUCTION_CORPUS_ROOT"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

# A section id as building codes print them: 1607.12, R301.2.1, 105.1. Indexing accepts
# dotted ids and chapter headings; REFUTATION later demands the stricter dotted form.
_SECTION_IN_TEXT = re.compile(r"\b(?:SECTION\s+)?([A-Z]{0,2}\d{3,4}(?:\.\d{1,3}){1,4})\b")
_CHAPTER_IN_TEXT = re.compile(r"\bCHAPTER\s+(\d{1,2})\b", re.IGNORECASE)
# What a REPLY must write for a citation to be judged at all: the explicit word
# Section/§ plus a dotted id. Bare numbers in prose are never judged.
_CITED_SECTION = re.compile(r"(?:\bSection\b|§)\s*([A-Z]{0,2}\d{3,4}(?:\.\d{1,3}){1,4})", re.IGNORECASE)
# California-amendment ids as CALDAG/CBC chapters 11A/11B print them: 11B-208.2,
# 11B-404.2.4 (2,490 such references in the ingested CALDAG volume alone). A second
# pass alongside the dotted form, never a replacement -- every key the dotted regex
# produced still exists after re-ingest, so prefix-stripped citations keep verifying.
_CA_SECTION_IN_TEXT = re.compile(r"\b(\d{1,2}[A-Z]-\d{3,4}(?:\.\d{1,3}){1,4})\b")
_CA_CITED_SECTION = re.compile(
    r"(?:\bSection\b|§)\s*(\d{1,2}[A-Z]-\d{3,4}(?:\.\d{1,3}){1,4})", re.IGNORECASE)

# Refutation requires a corpus that is plainly a real code library, not a stub: below
# this many distinct sections the index cannot prove absence, only presence.
MIN_SECTIONS_FOR_REFUTATION = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _atomic_write_text(path: Path, value: str) -> None:
    """Publish one corpus control file without exposing a half-written version."""
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def _safe_relative_path(value: Any) -> str | None:
    """Return one canonical POSIX bundle path, or None for an unsafe spelling."""
    raw = str(value or "")
    if not raw or raw != raw.strip() or "\\" in raw:
        return None
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return None
    if any(part in ("", ".", "..") for part in posix.parts):
        return None
    canonical = posix.as_posix()
    return canonical if canonical == raw else None


def _safe_source_name(value: Any) -> str | None:
    raw = str(value or "")
    if not raw or raw != raw.strip() or "/" in raw or "\\" in raw:
        return None
    if PureWindowsPath(raw).drive or raw in (".", ".."):
        return None
    return raw if Path(raw).name == raw else None


def _candidate_path(root: Path, relative_path: str) -> Path | None:
    safe = _safe_relative_path(relative_path)
    if safe is None:
        return None
    root_resolved = root.resolve(strict=False)
    candidate = root.joinpath(*PurePosixPath(safe).parts)
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None
    return candidate


def _is_link_or_reparse(path: Path) -> bool:
    """Reject POSIX symlinks and Windows junction/reparse-point aliases."""
    if path.is_symlink():
        return True
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0) or 0)
    except OSError:
        return False
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & reparse_flag)


def _has_symlink_component(root: Path, relative_path: str) -> bool:
    if _is_link_or_reparse(root):
        return True
    current = root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if _is_link_or_reparse(current):
            return True
    return False


def _binding_payload(index_record: dict[str, Any], docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Canonical non-circular bundle identity stored by the v2 manifest."""
    return {
        "schema": MANIFEST_SCHEMA,
        "index": {
            "relative_path": str(index_record["relative_path"]),
            "bytes": int(index_record["bytes"]),
            "sha256": str(index_record["sha256"]).upper(),
        },
        "docs": [
            {
                "file": str(item["file"]),
                "sha256": str(item["sha256"]).upper(),
                "source_bytes": int(item["source_bytes"]),
                "pages": int(item["pages"]),
                "extracted_jsonl": str(item["extracted_jsonl"]),
                "extracted_bytes": int(item["extracted_bytes"]),
                "extracted_sha256": str(item["extracted_sha256"]).upper(),
            }
            for item in sorted(docs, key=lambda entry: str(entry["file"]).casefold())
        ],
    }


_BUNDLE_CACHE: dict[str, dict[str, Any]] = {}


def _bundle_stat_signature(root: Path) -> tuple[Any, ...]:
    """Cheap cache invalidator; public verification always re-hashes every bound file."""
    records: list[tuple[Any, ...]] = []
    try:
        root_stat = root.lstat()
        records.append(
            ("__root__", root_stat.st_size, root_stat.st_mtime_ns, _is_link_or_reparse(root), root.is_dir())
        )
    except OSError:
        records.append(("__root__", None, None, _is_link_or_reparse(root), False))
    for relative in (MANIFEST_NAME, INDEX_NAME):
        path = root / relative
        try:
            stat = path.lstat()
            records.append((relative, stat.st_size, stat.st_mtime_ns, _is_link_or_reparse(path)))
        except OSError:
            records.append((relative, None, None, _is_link_or_reparse(path)))
    extracted = root / EXTRACT_DIR_NAME
    if extracted.is_dir() and not _is_link_or_reparse(extracted):
        try:
            entries = sorted(extracted.rglob("*"), key=lambda item: item.as_posix())
        except OSError:
            entries = []
        for path in entries:
            try:
                stat = path.lstat()
                relative = path.relative_to(root).as_posix()
                records.append(
                    (relative, stat.st_size, stat.st_mtime_ns, _is_link_or_reparse(path), path.is_dir())
                )
            except OSError:
                records.append((str(path), None, None, _is_link_or_reparse(path), False))
    return tuple(records)


def verify_corpus_bundle(corpus_root: Path | str | None = None) -> dict[str, Any]:
    """Verify the complete v2 grading bundle without trusting manifest paths.

    ``files`` is the exact deployment allowlist: the manifest, its bound index, and
    every bound extracted JSONL. Source PDFs are deliberately not deployment files;
    their immutable name/hash/page provenance is carried on each extraction record.
    This function never raises and never follows a symlink for a bound artifact.
    """
    root = Path(corpus_root) if corpus_root is not None else CORPUS_ROOT
    blockers: list[str] = []
    files: list[dict[str, Any]] = []
    bundle_sha256 = ""

    def block(message: str) -> None:
        if message not in blockers and len(blockers) < 100:
            blockers.append(message)

    def result() -> dict[str, Any]:
        report = {
            "schema": BUNDLE_VERIFY_SCHEMA,
            "ok": not blockers,
            "root": str(root),
            "files": files,
            "bundle_sha256": bundle_sha256,
            "blockers": blockers,
        }
        try:
            signature = _bundle_stat_signature(root)
        except Exception:
            signature = ()
        _BUNDLE_CACHE[str(root.resolve(strict=False))] = {
            "signature": signature,
            "report": report,
        }
        return report

    try:
        if not root.exists():
            block("corpus root does not exist")
            return result()
        if not root.is_dir():
            block("corpus root is not a directory")
            return result()
        if _is_link_or_reparse(root):
            block("corpus root must not be a symlink")
            return result()

        manifest_path = root / MANIFEST_NAME
        if _is_link_or_reparse(manifest_path):
            block(f"{MANIFEST_NAME} must not be a symlink")
            return result()
        if not manifest_path.is_file():
            block(f"missing {MANIFEST_NAME}")
            return result()
        try:
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            block(f"unreadable corpus manifest: {type(exc).__name__}")
            return result()
        files.append({
            "role": "manifest",
            "relative_path": MANIFEST_NAME,
            "bytes": len(manifest_bytes),
            "sha256": hashlib.sha256(manifest_bytes).hexdigest().upper(),
        })
        if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
            schema = manifest.get("schema") if isinstance(manifest, dict) else None
            block(f"manifest schema {schema!r} is not {MANIFEST_SCHEMA}")
            return result()

        raw_index = manifest.get("index")
        raw_docs = manifest.get("docs")
        if not isinstance(raw_index, dict):
            block("manifest index binding is missing or malformed")
            raw_index = {}
        if not isinstance(raw_docs, list) or not raw_docs:
            block("manifest must bind at least one source document extraction")
            raw_docs = []

        index_relative = _safe_relative_path(raw_index.get("relative_path"))
        index_bytes = raw_index.get("bytes")
        index_sha = str(raw_index.get("sha256") or "")
        if index_relative != INDEX_NAME:
            block(f"index relative_path must be exactly {INDEX_NAME}")
        if not isinstance(index_bytes, int) or isinstance(index_bytes, bool) or index_bytes < 1:
            block("index bytes must be a positive integer")
        if not _SHA256_RE.fullmatch(index_sha):
            block("index sha256 must be 64 hexadecimal characters")

        canonical_docs: list[dict[str, Any]] = []
        seen_docs: set[str] = set()
        seen_extractions: set[str] = set()
        for ordinal, raw_doc in enumerate(raw_docs, start=1):
            if not isinstance(raw_doc, dict):
                block(f"manifest docs[{ordinal}] is not an object")
                continue
            source_name = _safe_source_name(raw_doc.get("file"))
            source_sha = str(raw_doc.get("sha256") or "")
            source_bytes = raw_doc.get("source_bytes")
            pages = raw_doc.get("pages")
            extracted_relative = _safe_relative_path(raw_doc.get("extracted_jsonl"))
            extracted_bytes = raw_doc.get("extracted_bytes")
            extracted_sha = str(raw_doc.get("extracted_sha256") or "")
            if source_name is None:
                block(f"manifest docs[{ordinal}] has an unsafe source PDF name")
            elif source_name in seen_docs:
                block(f"source PDF {source_name!r} appears more than once")
            else:
                seen_docs.add(source_name)
            if not _SHA256_RE.fullmatch(source_sha):
                block(f"manifest docs[{ordinal}] has an invalid source PDF sha256")
            if (
                not isinstance(source_bytes, int)
                or isinstance(source_bytes, bool)
                or source_bytes < 1
            ):
                block(f"manifest docs[{ordinal}] source_bytes must be positive")
            if not isinstance(pages, int) or isinstance(pages, bool) or pages < 1:
                block(f"manifest docs[{ordinal}] pages must be a positive integer")
            expected_parts = PurePosixPath(extracted_relative).parts if extracted_relative else ()
            if (
                extracted_relative is None
                or len(expected_parts) != 2
                or expected_parts[0] != EXTRACT_DIR_NAME
                or not expected_parts[1].endswith(".jsonl")
            ):
                block(
                    f"manifest docs[{ordinal}] extracted_jsonl must be a direct relative "
                    f"{EXTRACT_DIR_NAME}/*.jsonl path"
                )
            elif extracted_relative in seen_extractions:
                block(f"extracted file {extracted_relative!r} appears more than once")
            else:
                seen_extractions.add(extracted_relative)
            if (
                not isinstance(extracted_bytes, int)
                or isinstance(extracted_bytes, bool)
                or extracted_bytes < 1
            ):
                block(f"manifest docs[{ordinal}] extracted_bytes must be positive")
            if not _SHA256_RE.fullmatch(extracted_sha):
                block(f"manifest docs[{ordinal}] has an invalid extracted sha256")
            if (
                source_name is not None
                and _SHA256_RE.fullmatch(source_sha)
                and isinstance(source_bytes, int)
                and not isinstance(source_bytes, bool)
                and source_bytes > 0
                and isinstance(pages, int)
                and not isinstance(pages, bool)
                and pages > 0
                and extracted_relative is not None
                and isinstance(extracted_bytes, int)
                and not isinstance(extracted_bytes, bool)
                and extracted_bytes > 0
                and _SHA256_RE.fullmatch(extracted_sha)
            ):
                canonical_docs.append({
                    "file": source_name,
                    "sha256": source_sha.upper(),
                    "source_bytes": source_bytes,
                    "pages": pages,
                    "extracted_jsonl": extracted_relative,
                    "extracted_bytes": extracted_bytes,
                    "extracted_sha256": extracted_sha.upper(),
                })

        if raw_docs and len(canonical_docs) == len(raw_docs) and index_relative == INDEX_NAME:
            canonical_index = {
                "relative_path": index_relative,
                "bytes": index_bytes,
                "sha256": index_sha.upper(),
            }
            try:
                bundle_sha256 = _canonical_sha256(
                    _binding_payload(canonical_index, canonical_docs)
                )
            except (KeyError, TypeError, ValueError):
                bundle_sha256 = ""
            declared_bundle = str(manifest.get("bundle_sha256") or "")
            if not _SHA256_RE.fullmatch(declared_bundle):
                block("manifest bundle_sha256 is missing or malformed")
            elif declared_bundle.casefold() != bundle_sha256.casefold():
                block("manifest bundle_sha256 does not match its file bindings")

        def verify_bound_file(
            *,
            role: str,
            relative_path: str | None,
            expected_bytes: Any,
            expected_sha256: str,
            source: dict[str, Any] | None = None,
        ) -> Path | None:
            if relative_path is None:
                return None
            candidate = _candidate_path(root, relative_path)
            if candidate is None:
                block(f"{role} path is outside the corpus root: {relative_path!r}")
                return None
            if _has_symlink_component(root, relative_path):
                block(f"{role} must not use a symlink: {relative_path}")
                return None
            if not candidate.is_file():
                block(f"missing bound {role}: {relative_path}")
                return None
            try:
                actual_bytes = candidate.stat().st_size
                actual_sha = _sha256(candidate)
            except OSError as exc:
                block(f"could not hash bound {role} {relative_path}: {type(exc).__name__}")
                return None
            if actual_bytes != expected_bytes:
                block(
                    f"bound {role} byte count changed for {relative_path}: "
                    f"expected {expected_bytes}, got {actual_bytes}"
                )
            if not _SHA256_RE.fullmatch(expected_sha256) or actual_sha.casefold() != expected_sha256.casefold():
                block(f"bound {role} sha256 changed for {relative_path}")
            record = {
                "role": role,
                "relative_path": relative_path,
                "bytes": int(expected_bytes) if isinstance(expected_bytes, int) else -1,
                "sha256": str(expected_sha256).upper(),
            }
            if source:
                record.update(source)
            files.append(record)
            return candidate

        index_path = verify_bound_file(
            role="index",
            relative_path=index_relative,
            expected_bytes=index_bytes,
            expected_sha256=index_sha,
        )

        extracted_paths: dict[str, Path] = {}
        for doc in canonical_docs:
            relative = doc["extracted_jsonl"]
            path = verify_bound_file(
                role="extracted",
                relative_path=relative,
                expected_bytes=doc["extracted_bytes"],
                expected_sha256=doc["extracted_sha256"],
                source={
                    "source_pdf_name": doc["file"],
                    "source_pdf_sha256": doc["sha256"],
                    "source_pdf_bytes": doc["source_bytes"],
                    "source_pdf_pages": doc["pages"],
                },
            )
            if path is not None:
                extracted_paths[relative] = path

        extract_dir = root / EXTRACT_DIR_NAME
        actual_extracted: set[str] = set()
        if _is_link_or_reparse(extract_dir):
            block(f"{EXTRACT_DIR_NAME} must not be a symlink")
        elif not extract_dir.is_dir():
            block(f"missing {EXTRACT_DIR_NAME} directory")
        else:
            try:
                entries = sorted(extract_dir.rglob("*"), key=lambda item: item.as_posix())
            except OSError as exc:
                block(f"could not enumerate extracted files: {type(exc).__name__}")
                entries = []
            for path in entries:
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    block(f"extracted entry escaped corpus root: {path}")
                    continue
                if _is_link_or_reparse(path):
                    block(f"extracted entry must not be a symlink: {relative}")
                elif path.is_dir():
                    block(f"unexpected nested directory in extracted set: {relative}")
                elif path.is_file():
                    actual_extracted.add(relative)
                else:
                    block(f"unsupported extracted entry type: {relative}")
        declared_extracted = set(seen_extractions)
        for relative in sorted(actual_extracted - declared_extracted):
            block(f"unbound file is present in extracted set: {relative}")
        for relative in sorted(declared_extracted - actual_extracted):
            block(f"manifest-bound extracted file is absent: {relative}")

        doc_inventory = {
            doc["file"]: {"sha256": doc["sha256"], "pages": doc["pages"]}
            for doc in canonical_docs
        }

        # Source PDFs are local-ingest provenance, not CT deployment dependencies. When
        # source_pdfs/ is present, however, its PDF set must exactly match the manifest and
        # every byte must still hash to the bound source identity. Omitting the directory on
        # a deployment-only grading bundle remains valid by design.
        source_dir = root / SOURCE_DIR_NAME
        if source_dir.exists() or _is_link_or_reparse(source_dir):
            if _is_link_or_reparse(source_dir):
                block(f"{SOURCE_DIR_NAME} must not be a symlink")
            elif not source_dir.is_dir():
                block(f"{SOURCE_DIR_NAME} is not a directory")
            else:
                try:
                    source_entries = sorted(source_dir.iterdir(), key=lambda item: item.name)
                except OSError as exc:
                    block(f"could not enumerate source PDFs: {type(exc).__name__}")
                    source_entries = []
                actual_pdf_names: set[str] = set()
                for source_path in source_entries:
                    if source_path.suffix.casefold() != ".pdf":
                        continue
                    actual_pdf_names.add(source_path.name)
                    relative = f"{SOURCE_DIR_NAME}/{source_path.name}"
                    if _is_link_or_reparse(source_path):
                        block(f"source PDF must not be a symlink: {relative}")
                declared_pdf_names = set(doc_inventory)
                for name in sorted(actual_pdf_names - declared_pdf_names):
                    block(f"unbound source PDF is present: {SOURCE_DIR_NAME}/{name}")
                for name in sorted(declared_pdf_names - actual_pdf_names):
                    block(f"manifest-bound source PDF is absent: {SOURCE_DIR_NAME}/{name}")
                for doc in canonical_docs:
                    name = doc["file"]
                    if name not in actual_pdf_names:
                        continue
                    relative = f"{SOURCE_DIR_NAME}/{name}"
                    source_path = _candidate_path(root, relative)
                    if source_path is None:
                        block(f"source PDF path is outside the corpus root: {relative}")
                        continue
                    if _has_symlink_component(root, relative):
                        block(f"source PDF must not use a symlink: {relative}")
                        continue
                    if not source_path.is_file():
                        block(f"source PDF is not a regular file: {relative}")
                        continue
                    try:
                        actual_bytes = source_path.stat().st_size
                        actual_sha = _sha256(source_path)
                    except OSError as exc:
                        block(f"could not read source PDF {relative}: {type(exc).__name__}")
                        continue
                    if actual_bytes != doc["source_bytes"]:
                        block(
                            f"source PDF byte count changed for {relative}: "
                            f"expected {doc['source_bytes']}, got {actual_bytes}"
                        )
                    if actual_sha.casefold() != doc["sha256"].casefold():
                        block(f"source PDF sha256 changed for {relative}")
        if index_path is not None:
            try:
                index_payload = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                block(f"bound index is unreadable JSON: {type(exc).__name__}")
                index_payload = {}
            if not isinstance(index_payload, dict) or index_payload.get("schema") != INDEX_SCHEMA:
                block(f"bound index schema is not {INDEX_SCHEMA}")
            index_docs = index_payload.get("documents") if isinstance(index_payload, dict) else None
            expected_index_docs = [
                {"file": name, **values}
                for name, values in sorted(doc_inventory.items(), key=lambda item: item[0].casefold())
            ]
            normalized_index_docs = []
            if isinstance(index_docs, list):
                for item in index_docs:
                    if isinstance(item, dict):
                        normalized_index_docs.append({
                            "file": str(item.get("file") or ""),
                            "sha256": str(item.get("sha256") or "").upper(),
                            "pages": item.get("pages"),
                        })
                normalized_index_docs.sort(key=lambda item: item["file"].casefold())
            inventory_matches = normalized_index_docs == expected_index_docs
            if not inventory_matches:
                block("bound index document inventory does not match the manifest")
            sections = index_payload.get("sections") if isinstance(index_payload, dict) else None
            if not isinstance(sections, dict):
                block("bound index sections field is malformed")
                sections = {}
            declared_distinct = manifest.get("distinct_sections")
            if (
                not isinstance(declared_distinct, int)
                or isinstance(declared_distinct, bool)
                or declared_distinct != len(sections)
                or index_payload.get("distinct_sections") != len(sections)
            ):
                block("manifest/index distinct section counts do not match indexed sections")
            if inventory_matches:
                for section_id, locations in sections.items():
                    if not isinstance(section_id, str) or not isinstance(locations, list):
                        block("bound index contains a malformed section entry")
                        break
                    for location in locations:
                        doc = str(location.get("doc") or "") if isinstance(location, dict) else ""
                        page = location.get("page") if isinstance(location, dict) else None
                        if (
                            doc not in doc_inventory
                            or not isinstance(page, int)
                            or isinstance(page, bool)
                            or page < 1
                            or page > doc_inventory.get(doc, {}).get("pages", 0)
                        ):
                            block(f"bound index location is outside its source document: {section_id}")
                            break
                chapters = index_payload.get("chapters")
                if not isinstance(chapters, dict):
                    block("bound index chapters field is malformed")
                else:
                    for chapter, names in chapters.items():
                        if (
                            not isinstance(chapter, str)
                            or not isinstance(names, list)
                            or any(str(name) not in doc_inventory for name in names)
                        ):
                            block("bound index chapter inventory references an unknown document")
                            break

        for doc in canonical_docs:
            relative = doc["extracted_jsonl"]
            path = extracted_paths.get(relative)
            if path is None:
                continue
            rows_seen = 0
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        if not line.strip():
                            block(f"blank line in extracted file {relative}:{line_number}")
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            block(f"invalid JSON in extracted file {relative}:{line_number}")
                            continue
                        rows_seen += 1
                        if (
                            not isinstance(row, dict)
                            or row.get("doc") != doc["file"]
                            or row.get("page") != rows_seen
                            or not isinstance(row.get("text"), str)
                        ):
                            block(f"invalid page binding in extracted file {relative}:{line_number}")
                if rows_seen != doc["pages"]:
                    block(
                        f"extracted page count mismatch for {relative}: "
                        f"expected {doc['pages']}, got {rows_seen}"
                    )
            except (OSError, UnicodeDecodeError) as exc:
                block(f"could not validate extracted file {relative}: {type(exc).__name__}")
    except Exception as exc:  # verifier must fail closed, never strand a caller
        block(f"corpus bundle verification failed closed: {type(exc).__name__}: {exc}")
    return result()


def _verified_bundle(corpus_root: Path | str | None = None) -> dict[str, Any]:
    root = Path(corpus_root) if corpus_root is not None else CORPUS_ROOT
    key = str(root.resolve(strict=False))
    signature = _bundle_stat_signature(root)
    cached = _BUNDLE_CACHE.get(key)
    if cached and cached.get("signature") == signature:
        return cached["report"]
    return verify_corpus_bundle(root)


def _normalize(section_id: str) -> str:
    return section_id.strip().upper()


def _extract_pages(pdf_path: Path) -> list[str]:
    """Per-page text. fitz first (fast, robust on big code volumes), pypdf fallback."""
    try:
        import fitz

        with fitz.open(str(pdf_path)) as doc:
            return [page.get_text() or "" for page in doc]
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return [(page.extract_text() or "") for page in reader.pages]


def ingest(corpus_root: Path | None = None, force: bool = False) -> dict[str, Any]:
    root = Path(corpus_root) if corpus_root else CORPUS_ROOT
    source_dir = root / SOURCE_DIR_NAME
    extract_dir = root / EXTRACT_DIR_NAME
    if (
        _is_link_or_reparse(root)
        or _is_link_or_reparse(source_dir)
        or _is_link_or_reparse(extract_dir)
    ):
        raise RuntimeError("corpus root, source_pdfs, and extracted must not be symlinks")
    extract_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / MANIFEST_NAME
    index_path = root / INDEX_NAME

    previous: dict[str, Any] = {}
    previous_verification = verify_corpus_bundle(root) if manifest_path.is_file() and not force else {}
    if previous_verification.get("ok") is True and not force:
        try:
            previous = {
                entry["file"]: entry
                for entry in json.loads(manifest_path.read_text(encoding="utf-8")).get("docs", [])
            }
        except Exception:
            previous = {}

    pdfs = sorted(source_dir.glob("*.pdf")) if source_dir.is_dir() else []
    if any(_is_link_or_reparse(pdf) for pdf in pdfs):
        raise RuntimeError("source PDFs must not be symlinks")
    docs: list[dict[str, Any]] = []
    index: dict[str, list[dict[str, Any]]] = {}
    chapters: dict[str, list[str]] = {}
    started = time.perf_counter()

    expected_extracted: set[str] = set()
    used_slugs: set[str] = set()
    for pdf in pdfs:
        sha = _sha256(pdf)
        slug = re.sub(r"[^A-Za-z0-9]+", "_", pdf.stem).strip("_").lower()
        if not slug or slug in used_slugs:
            raise RuntimeError(f"source PDF names collide after safe extraction naming: {pdf.name}")
        used_slugs.add(slug)
        jsonl = extract_dir / f"{slug}.jsonl"
        extracted_relative = jsonl.relative_to(root).as_posix()
        expected_extracted.add(extracted_relative)
        prev = previous.get(pdf.name)
        if (
            prev
            and prev.get("sha256") == sha
            and prev.get("extracted_jsonl") == extracted_relative
            and jsonl.is_file()
            and not _is_link_or_reparse(jsonl)
            and jsonl.stat().st_size == prev.get("extracted_bytes")
            and _sha256(jsonl).casefold() == str(prev.get("extracted_sha256") or "").casefold()
            and not force
        ):
            pages = int(prev.get("pages") or 0)
            reused = True
        else:
            page_texts = _extract_pages(pdf)
            if not page_texts:
                raise RuntimeError(f"source PDF has no extractable pages: {pdf.name}")
            temp_jsonl = jsonl.with_name(jsonl.name + ".tmp")
            with temp_jsonl.open("w", encoding="utf-8", newline="\n") as fh:
                for number, text in enumerate(page_texts, start=1):
                    fh.write(json.dumps(
                        {"doc": pdf.name, "page": number, "text": text},
                        ensure_ascii=False) + "\n")
            os.replace(temp_jsonl, jsonl)
            pages = len(page_texts)
            reused = False
        sections_in_doc = 0
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            text = str(row.get("text") or "")
            upper = text.upper()
            for pattern in (_SECTION_IN_TEXT, _CA_SECTION_IN_TEXT):
                for match in pattern.finditer(upper):
                    sid = _normalize(match.group(1))
                    bucket = index.setdefault(sid, [])
                    if len(bucket) < 20:
                        bucket.append({"doc": row["doc"], "page": row["page"]})
                    sections_in_doc += 1
            for match in _CHAPTER_IN_TEXT.finditer(text):
                chapters.setdefault(match.group(1), [])
                if row["doc"] not in chapters[match.group(1)]:
                    chapters[match.group(1)].append(row["doc"])
        docs.append({
            "file": pdf.name,
            "sha256": sha,
            "source_bytes": pdf.stat().st_size,
            "pages": pages,
            "extracted_jsonl": extracted_relative,
            "extracted_bytes": jsonl.stat().st_size,
            "extracted_sha256": _sha256(jsonl),
            "section_hits": sections_in_doc,
            "reused_previous_extraction": reused,
        })

    # A removed source must remove its old extraction; any other unbound entry makes the
    # build ambiguous and is discarded only inside this owned extraction directory.
    for path in sorted(extract_dir.iterdir(), key=lambda item: item.name.casefold()):
        if _is_link_or_reparse(path) or path.is_dir():
            raise RuntimeError(f"unexpected extracted entry: {path.name}")
        relative = path.relative_to(root).as_posix()
        if relative not in expected_extracted:
            path.unlink()

    index_payload = {
        "schema": INDEX_SCHEMA,
        "generated_at_utc": _now(),
        "distinct_sections": len(index),
        "documents": [
            {"file": item["file"], "sha256": item["sha256"], "pages": item["pages"]}
            for item in sorted(docs, key=lambda entry: entry["file"].casefold())
        ],
        "chapters": chapters,
        "sections": index,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(index_path, json.dumps(index_payload, ensure_ascii=False))
    index_record = {
        "relative_path": INDEX_NAME,
        "bytes": index_path.stat().st_size,
        "sha256": _sha256(index_path),
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at_utc": _now(),
        "source_dir": SOURCE_DIR_NAME,
        "index": index_record,
        "docs": docs,
        "distinct_sections": len(index),
        "ingest_seconds": round(time.perf_counter() - started, 1),
    }
    manifest["bundle_sha256"] = _canonical_sha256(_binding_payload(index_record, docs))
    _atomic_write_text(
        manifest_path,
        json.dumps(manifest, indent=2, ensure_ascii=False),
    )
    verification = verify_corpus_bundle(root)
    if verification.get("ok") is not True:
        raise RuntimeError(
            "new construction corpus bundle failed verification: "
            + " | ".join(verification.get("blockers") or [])
        )
    return manifest


_INDEX_CACHE: dict[str, Any] = {}
_PAGE_CACHE: dict[tuple[str, str, str, int], str] = {}

# Existence is not entailment.  These helpers intentionally implement a narrow,
# deterministic support check rather than pretending to be a general language
# model: a training row is exactly verified only when the words and quantities in
# the sentence that cites a section can be found beside that section in the local
# source text.  Anything less remains undecidable and therefore cannot be admitted
# by the fail-closed AEC training gate.
_CLAIM_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "minimum", "maximum", "must", "of", "on", "or",
    "per", "section", "shall", "should", "that", "the", "this", "to", "under",
    "with", "sourced", "fact", "facts", "code", "caldag", "cbc", "require",
    "required", "requires", "say", "says", "state", "states", "govern", "governs",
    "source", "excerpt", "evidence", "quote", "quoted", "supporting", "see",
    "exact",  # the packet's own label ("exact excerpt:") is citation boilerplate too
    # (2026-08-14) more citation boilerplate observed leaking into claims from
    # faithful copies of packet/contract wording - never claim substance:
    "page", "claim",
}
_RATIO_OR_DIMENSION = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?::|\bper\b|[x\u00d7])\s*"
    r"\d+(?:\.\d+)?(?:\s*(?:in(?:ch(?:es)?)?\.?|mm|cm|ft|feet|foot|%))?",
    re.IGNORECASE,
)
_NUMBER_WITH_UNIT = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:in(?:ch(?:es)?)?\.?|mm|cm|ft|feet|foot|percent|%)\b",
    re.IGNORECASE,
)
_SUPPORT_QUOTE = re.compile(
    # "exact excerpt" is the label the runner's OWN evidence packet prints
    # (2026-08-10: models copying the packet's label verbatim were failing the
    # gate that demanded a synonym -- the packet and the gate must agree).
    r"(?:source\s+excerpt|evidence\s+quote|supporting\s+quote|exact\s+excerpt)\s*:\s*"
    r"[\"\u201c]([^\"\u201d]{20,600})[\"\u201d]",
    re.IGNORECASE | re.DOTALL,
)
_SOURCE_DOCUMENT = re.compile(
    r"source\s+document\s*:\s*[\"\u201c]([^\"\u201d\r\n]{1,255})[\"\u201d]",
    re.IGNORECASE,
)

_DOCUMENT_TOKEN_STOPWORDS = {
    "pdf", "first", "printing", "ptg", "the", "and", "for", "from", "with",
    "guide", "guidebook", "package", "document", "volume", "source",
}


def load_index(corpus_root: Path | None = None) -> dict[str, Any]:
    root = Path(corpus_root) if corpus_root else CORPUS_ROOT
    verification = _verified_bundle(root)
    if verification.get("ok") is not True:
        return {}
    key = str(root)
    cached = _INDEX_CACHE.get(key)
    index_path = root / INDEX_NAME
    bundle_sha = str(verification.get("bundle_sha256") or "")
    if cached and cached.get("bundle_sha256") == bundle_sha:
        return cached["payload"]
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict) or payload.get("schema") != INDEX_SCHEMA:
        return {}
    _INDEX_CACHE[key] = {"bundle_sha256": bundle_sha, "payload": payload}
    return payload


def _corpus_documents(root: Path) -> list[str]:
    """Return exact document names only from a verified v2 bundle."""
    verification = _verified_bundle(root)
    if verification.get("ok") is not True:
        return []
    manifest_path = root / MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return [
        str(item.get("file") or "")
        for item in payload.get("docs") or []
        if isinstance(item, dict) and str(item.get("file") or "").strip()
    ]


def _document_tokens(value: str, *, filename: bool = False) -> set[str]:
    raw = Path(str(value or "")).stem if filename else str(value or "")
    normalized = _normalise_search_text(raw)
    return {
        _word_stem(token)
        for token in re.findall(r"[a-z0-9]+(?:x[0-9]+)?", normalized)
        if token not in _DOCUMENT_TOKEN_STOPWORDS and len(token) > 1
    }


def _resolve_document_scope(
    root: Path,
    *,
    context: str = "",
    expected_documents: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[str], str]:
    """Bind evidence to one declared source document, never to the mixed library.

    ``expected_documents`` is the strongest legacy whole-answer contract and must use
    one exact manifest name. Multi-document answers are bound per claim by
    ``Source document: "<exact manifest filename>"`` in :func:`grade_reply` instead.
    Otherwise a prompt/context may identify one document by distinctive filename tokens
    (for example ``2024 CALDAG`` or ``Structural Calcs V1``).  If several corpus files
    remain plausible, exact verification is unavailable and admission stays closed.
    """
    documents = _corpus_documents(root)
    if not documents:
        return [], "construction corpus manifest has no document inventory"
    if expected_documents is not None:
        requested = [str(item or "").strip() for item in expected_documents if str(item or "").strip()]
        unknown = [item for item in requested if item not in documents]
        if len(requested) != 1 or unknown:
            return [], (
                "exact verification requires exactly one requested document/edition"
                if len(requested) != 1
                else "requested document(s) are not in the corpus manifest: " + ", ".join(unknown)
            )
        return requested, "document scope supplied explicitly"
    if len(documents) == 1:
        return documents, "single-document corpus"

    context_tokens = _document_tokens(context)
    if not context_tokens:
        return [], "source document/edition is not identified in the prompt context"
    tokens_by_doc = {doc: _document_tokens(doc, filename=True) for doc in documents}
    frequency: dict[str, int] = {}
    for tokens in tokens_by_doc.values():
        for token in tokens:
            frequency[token] = frequency.get(token, 0) + 1

    ranked: list[tuple[int, int, str]] = []
    for doc, tokens in tokens_by_doc.items():
        overlap = context_tokens & tokens
        distinctive = {token for token in overlap if frequency.get(token) == 1}
        # Distinctive terms (CALDAG, 2024, errata, 120x40, V1) dominate generic overlap.
        ranked.append((len(distinctive) * 3 + len(overlap), len(distinctive), doc))
    ranked.sort(reverse=True)
    best_score, best_distinctive, best_doc = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else -1
    if best_score <= 0 or best_score == runner_up or (
        best_distinctive == 0 and best_score < 2
    ):
        return [], "prompt context does not identify one unique corpus document/edition"
    return [best_doc], "document scope resolved from prompt context"


def _context_documents(context: str, documents: list[str]) -> list[str]:
    """Return exact manifest filenames explicitly present in the prompt context."""
    text = str(context or "")
    return [document for document in documents if document in text]


def corpus_ready(corpus_root: Path | None = None) -> bool:
    root = Path(corpus_root) if corpus_root else CORPUS_ROOT
    return _verified_bundle(root).get("ok") is True and bool(load_index(root).get("sections"))


def cited_sections(reply: str) -> list[str]:
    text = str(reply or "")
    cited = [_normalize(match.group(1)) for match in _CITED_SECTION.finditer(text)]
    cited.extend(_normalize(match.group(1)) for match in _CA_CITED_SECTION.finditer(text))
    # A required exact quote normally repeats the section id.  Count distinct governing
    # sections, not textual occurrences, so the quote cannot make an otherwise complete
    # support record look incomplete.
    return list(dict.fromkeys(cited))


def _normalise_search_text(value: str) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"\bin(?:ch(?:es)?)?\.?\b", "inch", text)
    text = re.sub(r"\b(?:ft|feet|foot)\b", "foot", text)
    text = text.replace("\u00d7", "x")
    return " ".join(re.sub(r"[^a-z0-9:%]+", " ", text).split())


def _word_stem(word: str) -> str:
    """Small deterministic stemmer sufficient for code-book wording comparisons."""
    token = str(word or "").casefold()
    for suffix in ("ments", "ment", "ances", "ance", "ences", "ence", "ingly", "ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _claim_records(reply: str) -> list[dict[str, str]]:
    """Parse one deterministic evidence-ledger record per cited source-fact line.

    A record may contain one governing section and one exact manifest filename. The
    section repeated inside its exact quote is deduplicated by :func:`cited_sections`.
    Two different governing sections or two document labels on one physical line are
    ambiguous and fail closed; comparisons must use one line per document/claim.

    An omitted document label remains valid only through the pre-existing single-document
    scope path (one-file corpus, one explicit ``expected_documents`` item, or uniquely
    identifying context). This preserves reviewed single-document answers while making a
    multi-volume answer bind every claim independently.
    """
    text = str(reply or "")
    fragments = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    records: list[dict[str, str]] = []
    # (2026-08-10) Ledger scope. The evidence-ledger contract ITSELF divides a reply:
    # "Sourced facts:" lines assert supported claims and must be quote-bound; "Open
    # items:" (and header) lines DECLARE things unsupported -- an open item that names
    # the section it needs confirmed is instructed honesty, not an unsupported claim.
    # The first live evidence-packet run failed 80/80 because open items citing their
    # own confirmation targets were graded as quoteless claims. Open/header-scope
    # section ids remain EXISTENCE-checked (a fabricated id still refutes); they are
    # exempt only from quote-binding. A line that carries a Source-document label or a
    # support quote self-declares as sourced regardless of position.
    scope = "header"
    for fragment in fragments:
        low = fragment.casefold()
        if "sourced facts" in low:
            scope = "sourced"
        elif "open items" in low:
            scope = "open"
        ids = cited_sections(fragment)
        if not ids:
            continue
        document_labels = [match.group(1) for match in _SOURCE_DOCUMENT.finditer(fragment)]
        self_declared = bool(document_labels) or bool(_SUPPORT_QUOTE.search(fragment))
        record = {
            "section": ids[0] if len(ids) == 1 else "",
            "claim": fragment.strip(" -;"),
            "source_document": document_labels[0] if len(document_labels) == 1 else "",
            "binding_error": "",
            "scope": "sourced" if (scope == "sourced" or self_declared) else "open",
        }
        if len(ids) != 1:
            record["binding_error"] = (
                "each sourced-fact line must cite exactly one governing Section <id>"
            )
        elif len(document_labels) > 1:
            record["binding_error"] = (
                "each sourced-fact line must name exactly one Source document"
            )
        records.append(record)
    return records


def _claim_fragments(reply: str) -> list[tuple[str, str]]:
    """Backward-compatible view of the deterministic claim records."""
    return [
        (record["section"], record["claim"])
        for record in _claim_records(reply)
        if record.get("section")
    ]


def _extracted_path(root: Path, doc: str) -> Path | None:
    verification = _verified_bundle(root)
    if verification.get("ok") is not True:
        return None
    manifest_path = root / MANIFEST_NAME
    try:
        for item in json.loads(manifest_path.read_text(encoding="utf-8")).get("docs", []):
            if str(item.get("file") or "") != doc:
                continue
            relative = _safe_relative_path(item.get("extracted_jsonl"))
            candidate = _candidate_path(root, relative or "")
            if (
                candidate is not None
                and not _has_symlink_component(root, relative or "")
                and candidate.is_file()
            ):
                return candidate
    except (OSError, ValueError, TypeError):
        pass
    return None


def _page_text(root: Path, doc: str, page: int) -> str:
    verification = _verified_bundle(root)
    if verification.get("ok") is not True:
        return ""
    key = (
        str(root.resolve()),
        str(verification.get("bundle_sha256") or ""),
        str(doc),
        int(page),
    )
    if key in _PAGE_CACHE:
        return _PAGE_CACHE[key]
    path = _extracted_path(root, doc)
    if path is None:
        _PAGE_CACHE[key] = ""
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if int(row.get("page") or 0) == int(page):
                    value = str(row.get("text") or "")
                    _PAGE_CACHE[key] = value
                    return value
    except OSError:
        pass
    _PAGE_CACHE[key] = ""
    return ""


def _section_evidence(section_id: str, locations: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    sid_pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(section_id)}(?![A-Z0-9])", re.IGNORECASE)
    for location in locations[:12]:
        doc = str(location.get("doc") or "")
        page = int(location.get("page") or 0)
        page_text = _page_text(root, doc, page)
        if not page_text:
            continue
        matches = list(sid_pattern.finditer(page_text))
        if not matches:
            continue
        # Include nearby sub-sections and wrapped lines while keeping unrelated pages
        # out of the comparison.  Multiple occurrences are retained because tables often
        # cite the id before printing the governing text later on the same page.
        excerpts = []
        for match in matches[:6]:
            start = max(0, match.start() - 120)
            end = min(len(page_text), match.end() + 900)
            excerpts.append(page_text[start:end])
        evidence.append({"doc": doc, "page": page, "text": "\n".join(excerpts)})
    return evidence


def _prompt_quote(section_id: str, evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select one bounded, deterministic, quotable excerpt for a training prompt.

    Indexes and tables of contents often mention a section before the governing text.
    Prefer an occurrence with normative prose (``shall``, ``required``) and an explicit
    heading, then return a short slice starting at the cited id. Punctuation and whitespace
    are left as source text except for collapsing OCR line breaks; the admission checker
    applies the same whitespace normalization when it verifies a copied quote.
    """
    candidates: list[tuple[int, int, dict[str, Any], str]] = []
    section_pattern = re.compile(
        rf"(?<![A-Z0-9]){re.escape(section_id)}(?![A-Z0-9])", re.IGNORECASE
    )
    for item in evidence:
        raw = str(item.get("text") or "")
        for match in section_pattern.finditer(raw):
            nearby = " ".join(raw[match.start() : match.start() + 900].split())
            if not nearby:
                continue
            lowered = nearby.casefold()
            score = 0
            if re.search(
                rf"\bsection\s+{re.escape(section_id)}\b", nearby, re.IGNORECASE
            ):
                score += 8
            if re.search(
                rf"^{re.escape(section_id)}\s+[A-Za-z]", nearby, re.IGNORECASE
            ):
                score += 6
            score += 3 * sum(
                marker in lowered
                for marker in (" shall ", " required", " requirement", " permitted")
            )
            # Penalize index/table rows made mostly of comma-separated section numbers.
            score -= min(6, nearby[:300].count(",") // 4)
            candidates.append((score, len(nearby), item, nearby))
    if not candidates:
        return None
    _score, _length, source, nearby = max(
        candidates, key=lambda value: (value[0], value[1], -int(value[2].get("page") or 0))
    )
    limit = min(420, len(nearby))
    quote = nearby[:limit].strip()
    # Prefer the first complete sentence that clears the five-word exact-quote gate.
    # Do not leak the next section into a short but already sufficient sentence.
    for sentence_end in re.finditer(r"[.!?](?:\s|$)", quote):
        candidate = quote[: sentence_end.end()].strip()
        if len(candidate.split()) >= 5:
            quote = candidate
            break
    if len(quote.split()) < 5:
        return None
    return {
        "document": str(source.get("doc") or ""),
        "section": section_id,
        "page": int(source.get("page") or 0),
        "quote": quote,
    }


def build_prompt_evidence_context(
    evidence_anchors: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    corpus_root: Path | None = None,
) -> dict[str, Any]:
    """Build a bounded verified excerpt packet before an AEC prompt is delivered.

    Each anchor must name one exact manifest filename and one indexed section. The packet
    is deliberately extractive: it never asks a model to retrieve or invent evidence.
    Any absent, ambiguous, or unquotable anchor blocks the packet as a whole, allowing the
    runner to refuse the session before it opens the UI or writes training state.
    """
    root = Path(corpus_root) if corpus_root else CORPUS_ROOT
    bundle = _verified_bundle(root)
    blockers: list[str] = []
    records: list[dict[str, Any]] = []
    anchors = list(evidence_anchors or [])
    documents = _corpus_documents(root) if bundle.get("ok") is True else []
    payload = load_index(root) if bundle.get("ok") is True else {}
    sections = payload.get("sections") or {}
    if bundle.get("ok") is not True:
        blockers.append(
            "construction corpus bundle is unavailable or invalid: "
            + str((bundle.get("blockers") or ["verification did not pass"])[0])
        )
    if not anchors:
        blockers.append("AEC material supplies no verified evidence anchors")
    if len(anchors) > 8:
        blockers.append("AEC evidence packet exceeds the eight-anchor bound")
    seen: set[tuple[str, str]] = set()
    for ordinal, anchor in enumerate(anchors, start=1):
        if not isinstance(anchor, dict):
            blockers.append(f"evidence anchor {ordinal} is not an object")
            continue
        document = str(anchor.get("document") or "")
        section_id = _normalize(str(anchor.get("section") or ""))
        identity = (document, section_id)
        if not document or document not in documents:
            blockers.append(
                f"evidence anchor {ordinal} does not name an exact manifest document"
            )
            continue
        if not section_id or identity in seen:
            blockers.append(
                f"evidence anchor {ordinal} has an empty or duplicate document/section"
            )
            continue
        seen.add(identity)
        locations = [
            item
            for item in sections.get(section_id) or []
            if str(item.get("doc") or "") == document
        ]
        if not locations:
            blockers.append(
                f"evidence anchor {ordinal} is absent from {document}: Section {section_id}"
            )
            continue
        selected = _prompt_quote(
            section_id, _section_evidence(section_id, locations, root)
        )
        if selected is None:
            blockers.append(
                f"evidence anchor {ordinal} has no bounded quotable source text"
            )
            continue
        records.append(selected)
    ok = not blockers and len(records) == len(anchors)
    prompt_context = ""
    if ok:
        lines = [
            "Verified local evidence packet (use only these records for Sourced facts; ",
            "copy one exact excerpt per claim and put any unsupported point under Open items):",
        ]
        lines = ["".join(lines)]
        for item in records:
            quote = str(item["quote"]).replace('"', "'")
            # (2026-08-14) The packet line and the admissible ledger line must AGREE:
            # models copy this record verbatim, and the old 'page N; exact excerpt:'
            # tokens injected non-stopword words ("page") into the claim that the
            # 100%-term-overlap gate then demanded from the quote - a faithful copy
            # failed by one token (live: 5 near-miss rejections on 2026-08-14). Page
            # stays in the JSON record for receipts; the copyable line drops it.
            lines.append(
                f'- Source document: "{item["document"]}"; Section {item["section"]}; '
                f'Source excerpt: "{quote}"'
            )
        prompt_context = "\n".join(lines)
    return {
        "schema": "engel_construction_prompt_evidence_v1",
        "ok": ok,
        "corpus_bundle_sha256": bundle.get("bundle_sha256") or "",
        "documents": list(dict.fromkeys(item["document"] for item in records)),
        "records": records,
        "prompt_context": prompt_context,
        "blockers": blockers,
    }


def _claim_supported(section_id: str, claim: str, evidence: list[dict[str, Any]]) -> tuple[bool, str]:
    if not evidence:
        return False, "section resolved but no local source excerpt could be loaded"
    # The exact manifest filename is binding metadata, not part of the factual claim.
    # Remove it before lexical entailment so a truthful line is not required to find its
    # own filename inside the quoted code prose.
    claim_without_id = _SOURCE_DOCUMENT.sub(" ", claim)
    claim_without_id = re.sub(re.escape(section_id), " ", claim_without_id, flags=re.IGNORECASE)
    claim_normal = _normalise_search_text(claim_without_id)
    evidence_normal = _normalise_search_text("\n".join(item["text"] for item in evidence))

    quotes = [_normalise_search_text(match.group(1)) for match in _SUPPORT_QUOTE.finditer(claim)]
    usable_quotes = [quote for quote in quotes if len(quote.split()) >= 5]
    if not usable_quotes:
        # (2026-08-10) A sourced-fact line may carry its excerpt as a BARE quoted span
        # right after the citation ('Section 1004.1; "1004.1 Clear floor space..."') --
        # 69 of the first evidence-packet run's 80 replies did exactly that and were
        # rejected for missing a label the curriculum never mandated. The document
        # filename cannot masquerade here: claim_without_id already strips the whole
        # 'Source document: "..."' span. The entailment + in-corpus checks below stay
        # unchanged -- the label was decoration; the quote's TRUTH is the contract.
        bare = [
            _normalise_search_text(match.group(1))
            for match in re.finditer(r"[\"“]([^\"”]{20,600})[\"”]", claim_without_id)
        ]
        usable_quotes = [quote for quote in bare if len(quote.split()) >= 5]
    usable_quotes = list(dict.fromkeys(usable_quotes))
    if not usable_quotes:
        return False, (
            "claim has no short exact supporting quote; add Source excerpt: \"...\" "
            "from the scoped document"
        )
    if len(usable_quotes) != 1:
        return False, "each cited claim must carry exactly one short supporting quote"
    quote_normal = usable_quotes[0]
    # (2026-08-10) PDF extraction leaves hyphenation artifacts in the page text
    # ("posi- tioned"); a model that faithfully copies the packet excerpt but cleans
    # the break was rejected against the raw page. The squashed comparison (all
    # non-alphanumerics removed from BOTH sides) is insensitive to hyphen/space
    # artifacts while still demanding the same characters in the same order.
    def _squash(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value)

    if quote_normal not in evidence_normal \
            and _squash(quote_normal) not in _squash(evidence_normal):
        return False, "the quoted source excerpt was not found beside the cited section"

    quantities = [
        _normalise_search_text(match.group(0))
        for pattern in (_RATIO_OR_DIMENSION, _NUMBER_WITH_UNIT)
        for match in pattern.finditer(claim_without_id)
    ]
    missing_quantities = [quantity for quantity in quantities if quantity not in quote_normal]
    if missing_quantities:
        return False, f"claim quantity is not supported beside the cited section: {missing_quantities[0]}"

    claim_words = {
        _word_stem(word)
        for word in re.findall(r"[a-z]{3,}", claim_normal)
        if word not in _CLAIM_STOPWORDS
    }
    quote_words = {_word_stem(word) for word in re.findall(r"[a-z]{3,}", quote_normal)}
    overlap = sorted(claim_words & quote_words)
    # This flag is named *exactly* verified and is allowed to admit model-training
    # material, so partial topical similarity is not enough.  After removing citation
    # boilerplate and normative/reporting verbs, every substantive claim term and every
    # quantity must be present in the local evidence.  Paraphrases that need semantic
    # judgment stay undecidable for human review.
    required = len(claim_words)
    if required == 0:
        return False, "citation has no substantive claim to verify"
    if len(overlap) < required:
        return False, f"claim text is not supported beside the cited section ({len(overlap)}/{required} terms)"
    return True, f"claim supported by {len(overlap)} terms in the exact source excerpt"


def grade_reply(
    reply: str,
    corpus_root: Path | None = None,
    *,
    context: str = "",
    expected_documents: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Admission verdict for an aec answer, mirroring the other disciplines' graders.

    verified    - every cited claim is independently bound to one exact source
                  document/edition, its section exists in that document, and its short
                  exact quote supports the claim's words and quantities. A legacy
                  unlabeled answer may still use one unambiguous whole-answer document.
    wrong       - a citation in the strict "Section <dotted id>" form is absent from an
                  index large enough to prove absence. Fabricated code citations are the
                  aec twin of fabricated file paths.
    undecidable - no explicit citations, corpus missing/too small, or anything else.
    Never raises."""
    try:
        root = Path(corpus_root) if corpus_root else CORPUS_ROOT
        bundle = _verified_bundle(root)
        if bundle.get("ok") is not True:
            blockers = bundle.get("blockers") or []
            detail = str(blockers[0]) if blockers else "bundle verification did not pass"
            return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                    "claim_support_verified": False, "corpus_bundle_verified": False,
                    "detail": f"construction corpus bundle is unavailable or invalid: {detail}"}
        payload = load_index(root)
        sections = payload.get("sections") or {}
        cited = cited_sections(reply)
        if not cited:
            return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                    "claim_support_verified": False,
                    "detail": "no explicit Section citations to check"}
        if not sections:
            return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                    "claim_support_verified": False,
                    "detail": "construction corpus not ingested yet"}
        documents = _corpus_documents(root)
        requested: list[str] | None = None
        if expected_documents is not None:
            requested = list(dict.fromkeys(
                str(item or "").strip()
                for item in expected_documents
                if str(item or "").strip()
            ))
            unknown = [item for item in requested if item not in documents]
            if not requested or unknown:
                detail = (
                    "expected_documents supplies no exact manifest filename"
                    if not requested
                    else "requested document(s) are not in the corpus manifest: "
                    + ", ".join(unknown)
                )
                return {"verdict": "undecidable", "refuted": False,
                        "exactly_verified": False, "claim_support_verified": False,
                        "document_scope": [], "detail": detail}
        context_documents = _context_documents(context, documents)
        allowed_documents = set(requested or context_documents or documents)

        # The fallback exists only for the reviewed single-document answer contract.
        # A list of several expected/context documents deliberately cannot act as a
        # whole-answer scope: each claim must carry its own exact filename.
        fallback_documents: list[str] = []
        fallback_detail = "source document/edition is not bound on each cited claim"
        if requested is None or len(requested) == 1:
            fallback_documents, fallback_detail = _resolve_document_scope(
                root,
                context=context,
                expected_documents=requested,
            )

        claim_records = _claim_records(reply)
        if not claim_records:
            return {"verdict": "undecidable", "refuted": False,
                    "exactly_verified": False, "claim_support_verified": False,
                    "document_scope": [],
                    "detail": "no sourced-fact line could be parsed"}
        bound_claims: list[dict[str, str]] = []
        open_scope_missing: list[str] = []
        for record in claim_records:
            if record.get("scope") == "open":
                # Open-item/header honesty: existence-checked only. A fabricated id
                # here still refutes; a real id needs no quote because the line
                # declares the point UNRESOLVED rather than asserting it.
                section_id = record.get("section") or ""
                if section_id and section_id not in sections \
                        and len(sections) >= MIN_SECTIONS_FOR_REFUTATION:
                    open_scope_missing.append(section_id)
                continue
            if record.get("binding_error"):
                return {"verdict": "undecidable", "refuted": False,
                        "exactly_verified": False, "claim_support_verified": False,
                        "document_scope": [], "detail": record["binding_error"]}
            document = str(record.get("source_document") or "")
            if document:
                if document not in documents:
                    return {"verdict": "undecidable", "refuted": False,
                            "exactly_verified": False,
                            "claim_support_verified": False,
                            "document_scope": [],
                            "detail": f"Source document is not an exact manifest filename: {document}"}
                if document not in allowed_documents:
                    return {"verdict": "undecidable", "refuted": False,
                            "exactly_verified": False,
                            "claim_support_verified": False,
                            "document_scope": [],
                            "detail": f"Source document was not supplied for this prompt: {document}"}
            elif len(fallback_documents) == 1:
                document = fallback_documents[0]
            else:
                return {"verdict": "undecidable", "refuted": False,
                        "exactly_verified": False, "claim_support_verified": False,
                        "document_scope": [],
                        "detail": fallback_detail}
            bound_claims.append({**record, "source_document": document})

        document_scope = list(dict.fromkeys(
            item["source_document"] for item in bound_claims
        ))
        support: list[dict[str, Any]] = []
        unresolved_missing: list[str] = []
        refuted_missing: list[str] = []
        for record in bound_claims:
            section_id = record["section"]
            document = record["source_document"]
            locations = [
                item
                for item in sections.get(section_id) or []
                if str(item.get("doc") or "") == document
            ]
            if not locations:
                document_section_count = sum(
                    1
                    for locations_for_id in sections.values()
                    if any(
                        str(item.get("doc") or "") == document
                        for item in locations_for_id
                    )
                )
                identity = f"{document} Section {section_id}"
                if document_section_count >= MIN_SECTIONS_FOR_REFUTATION:
                    refuted_missing.append(identity)
                else:
                    unresolved_missing.append(identity)
                continue
            excerpts = _section_evidence(section_id, locations, root)
            supported, detail = _claim_supported(section_id, record["claim"], excerpts)
            support.append({
                "document": document,
                "section": section_id,
                "supported": supported,
                "detail": detail,
                "evidence": [
                    {"doc": item["doc"], "page": item["page"]} for item in excerpts[:5]
                ],
            })
        if refuted_missing:
            return {"verdict": "wrong", "refuted": True,
                    "exactly_verified": False, "claim_support_verified": False,
                    "document_scope": document_scope, "support": support,
                    "detail": "cited section(s) absent from the bound document: "
                    + ", ".join(refuted_missing[:5])}
        if unresolved_missing:
            return {"verdict": "undecidable", "refuted": False,
                    "exactly_verified": False, "claim_support_verified": False,
                    "document_scope": document_scope, "support": support,
                    "detail": "bound document is too small to prove this citation absent: "
                    + ", ".join(unresolved_missing[:5])}
        if open_scope_missing:
            return {"verdict": "wrong", "refuted": True,
                    "exactly_verified": False, "claim_support_verified": False,
                    "document_scope": document_scope, "support": support,
                    "detail": "open-item cites section(s) absent from the corpus: "
                    + ", ".join(open_scope_missing[:5])}
        if not bound_claims:
            return {"verdict": "undecidable", "refuted": False,
                    "exactly_verified": False, "claim_support_verified": False,
                    "document_scope": [],
                    "detail": "only open-item/header citations present; no sourced-fact "
                    "line asserts a supported claim"}
        all_supported = len(support) == len(bound_claims) and all(
            item["supported"] for item in support
        )
        if all_supported:
            first_evidence = support[0].get("evidence") or [{}]
            first = first_evidence[0] if first_evidence else {}
            return {"verdict": "verified", "refuted": False,
                    "exactly_verified": True, "claim_support_verified": True,
                    "support": support, "corpus_bundle_verified": True,
                    "corpus_bundle_sha256": bundle.get("bundle_sha256"),
                    "document_scope": document_scope,
                    "detail": "each cited claim is bound to and supported by its exact "
                    f"local document (e.g. {support[0]['section']} in "
                    f"{first.get('doc', '?')} p.{first.get('page', '?')})"}
        failed = next((item for item in support if not item["supported"]), None)
        return {"verdict": "undecidable", "refuted": False,
                "exactly_verified": False, "claim_support_verified": False,
                "citation_resolved": len(support) == len(bound_claims),
                "document_scope": document_scope, "support": support,
                "detail": (failed or {}).get("detail")
                or "section id exists, but the cited claim was not supported"}
    except Exception as exc:  # pragma: no cover
        return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                "claim_support_verified": False,
                "detail": f"corpus grading unavailable: {exc}"}


def status(corpus_root: Path | None = None) -> dict[str, Any]:
    root = Path(corpus_root) if corpus_root else CORPUS_ROOT
    verification = verify_corpus_bundle(root)
    manifest_path = root / MANIFEST_NAME
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    source_dir = root / SOURCE_DIR_NAME
    return {
        "source_dir": str(source_dir),
        "pdfs_present": sorted(p.name for p in source_dir.glob("*.pdf")) if source_dir.is_dir() else [],
        "ingested_docs": len(manifest.get("docs") or []),
        "distinct_sections": manifest.get("distinct_sections", 0),
        "ready_for_refutation": verification.get("ok") is True
        and (manifest.get("distinct_sections") or 0) >= MIN_SECTIONS_FOR_REFUTATION,
        "generated_at_utc": manifest.get("generated_at_utc"),
        "bundle_verified": verification.get("ok") is True,
        "bundle_sha256": verification.get("bundle_sha256") or "",
        "bundle_blockers": verification.get("blockers") or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--check-section", default="")
    parser.add_argument(
        "--corpus-root",
        default=str(os.environ.get(CORPUS_ROOT_ENV) or ""),
        help=f"corpus bundle root (or set {CORPUS_ROOT_ENV})",
    )
    args = parser.parse_args(argv)
    corpus_root = Path(args.corpus_root) if str(args.corpus_root).strip() else CORPUS_ROOT
    if args.ingest:
        print(json.dumps(ingest(corpus_root=corpus_root, force=args.force), indent=2))
    elif args.verify:
        verification = verify_corpus_bundle(corpus_root)
        print(json.dumps(verification, indent=2))
        return 0 if verification.get("ok") is True else 1
    elif args.check_section:
        payload = load_index(corpus_root)
        sid = _normalize(args.check_section)
        print(json.dumps({"section": sid, "exists": sid in (payload.get("sections") or {}),
                          "where": (payload.get("sections") or {}).get(sid, [])[:5]}, indent=2))
    else:
        print(json.dumps(status(corpus_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
