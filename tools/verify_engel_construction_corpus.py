#!/usr/bin/env python3
"""Gate for the construction code corpus (engel_construction_corpus + aec wiring).

The corpus makes aec citations CHECKABLE, so this gate proves both directions on a
synthetic code volume built with fitz -- no operator PDFs required:

  IT MUST CATCH FABRICATED CITATIONS once the index is large enough to prove absence.
  IT MUST NOT CALL A CONTRADICTED CLAIM "EXACTLY VERIFIED" merely because its id exists.
  IT MUST NOT REFUTE what it cannot prove: small index, loose references, no corpus.

Offline, self-contained, writes only under runtime/temp.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_construction_corpus as ccc  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


work = ROOT / "runtime" / "temp" / "construction_corpus_verify" / time.strftime("%Y%m%dT%H%M%S")
case_root = work.parent / (work.name + "_bundle_cases")
source = work / ccc.SOURCE_DIR_NAME
source.mkdir(parents=True, exist_ok=True)

# --- synthetic code volumes ---------------------------------------------------------
import fitz  # noqa: E402

big = fitz.open()
# >1000 distinct dotted sections so the index qualifies for refutation.
for chapter in range(1, 12):
    page = big.new_page()
    lines = [f"CHAPTER {chapter} GENERAL PROVISIONS"]
    for section in range(1, 100):
        lines.append(f"SECTION {chapter * 100 + section}.{section % 9 + 1} "
                     f"Requirements item {section} of chapter {chapter}.")
    page.insert_text((36, 36), "\n".join(lines[:60]), fontsize=6)
    page2 = big.new_page()
    page2.insert_text((36, 36), "\n".join(lines[60:]), fontsize=6)
ca_page = big.new_page()
ca_page.insert_text(
    (36, 36),
    "SECTION 11B-208.2 Parking spaces required.\n"
    "SECTION 11B-404.2.4 Door maneuvering clearances.\n"
    "SECTION 11B-405.2 Ramp runs shall have a running slope not steeper than 1:12.\n"
    "SECTION 1004.1 Design occupant load shall be determined by this section.\n"
    "SECTION 104.2 The building official shall determine compliance with this code.\n"
    "SECTION 1607.12 Impact loads require special design.",
    fontsize=8)
big.save(str(source / "synthetic_building_code.pdf"))
big.close()

# Exact production manifest filenames, backed by synthetic text only for this offline
# behavioral verifier. This lets the real eight-card renewal template exercise the same
# filename/anchor contract without opening or modifying the operator corpus.
for production_name in (
    "2024_caldag_1st_ptg.pdf",
    "2025_designer_collection_1st_printing.pdf",
    "designer_updated_2026_jan_errata.pdf",
):
    shutil.copy2(source / "synthetic_building_code.pdf", source / production_name)

small = fitz.open()
page = small.new_page()
page.insert_text((36, 36), "SECTION 1607.12 Live loads on decks. Decks shall support the required live load without exceeding allowable deflection.\nSECTION R301.2.1 Wind design.")
small.save(str(source / "synthetic_supplement.pdf"))
small.close()

manifest = ccc.ingest(corpus_root=work)
docs = {d["file"]: d for d in manifest["docs"]}
check("ingest_extracts_every_source_pdf",
      len(docs) == 5 and all(d["pages"] > 0 for d in docs.values()),
      f"{len(docs)} docs, pages {[d['pages'] for d in docs.values()]}")
check("index_finds_a_real_code_density_of_sections",
      manifest["distinct_sections"] >= ccc.MIN_SECTIONS_FOR_REFUTATION,
      f"distinct sections {manifest['distinct_sections']} "
      f"(refutation floor {ccc.MIN_SECTIONS_FOR_REFUTATION})")

# --- strict v2 bundle boundary ------------------------------------------------------
bundle = ccc.verify_corpus_bundle(work)
expected_relative = {
    ccc.MANIFEST_NAME,
    ccc.INDEX_NAME,
    *(str(item["extracted_jsonl"]) for item in manifest["docs"]),
}
observed_relative = {
    str(item.get("relative_path") or "") for item in bundle.get("files") or []
}
check(
    "v2_bundle_verifies_with_exact_deploy_allowlist",
    bundle.get("ok") is True
    and manifest.get("schema") == ccc.MANIFEST_SCHEMA
    and manifest.get("bundle_sha256") == bundle.get("bundle_sha256")
    and observed_relative == expected_relative
    and all(
        item.get("relative_path")
        and not Path(str(item["relative_path"])).is_absolute()
        and isinstance(item.get("bytes"), int)
        and len(str(item.get("sha256") or "")) == 64
        for item in bundle.get("files") or []
    ),
    f"ok={bundle.get('ok')}; files={sorted(observed_relative)}; blockers={bundle.get('blockers')}",
)
extracted_records = [item for item in bundle.get("files") or [] if item.get("role") == "extracted"]
check(
    "extractions_bind_source_pdf_name_hash_and_pages",
    len(extracted_records) == len(docs)
    and all(
        item.get("source_pdf_name") in docs
        and item.get("source_pdf_sha256") == docs[item["source_pdf_name"]]["sha256"]
        and item.get("source_pdf_bytes") == docs[item["source_pdf_name"]]["source_bytes"]
        and item.get("source_pdf_pages") == docs[item["source_pdf_name"]]["pages"]
        for item in extracted_records
    ),
    f"extracted records={extracted_records}",
)


def copy_deploy_bundle(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(work / ccc.MANIFEST_NAME, destination / ccc.MANIFEST_NAME)
    shutil.copy2(work / ccc.INDEX_NAME, destination / ccc.INDEX_NAME)
    shutil.copytree(work / ccc.EXTRACT_DIR_NAME, destination / ccc.EXTRACT_DIR_NAME)


def copy_local_bundle(destination: Path) -> None:
    copy_deploy_bundle(destination)
    shutil.copytree(work / ccc.SOURCE_DIR_NAME, destination / ccc.SOURCE_DIR_NAME)


deploy_only = case_root / "deploy_only"
copy_deploy_bundle(deploy_only)
deploy_verification = ccc.verify_corpus_bundle(deploy_only)
check(
    "source_pdfs_are_provenance_not_deployment_dependencies",
    deploy_verification.get("ok") is True
    and not (deploy_only / ccc.SOURCE_DIR_NAME).exists()
    and deploy_verification.get("bundle_sha256") == bundle.get("bundle_sha256"),
    f"deploy-only blockers={deploy_verification.get('blockers')}",
)

mutated_source = case_root / "mutated_source"
copy_local_bundle(mutated_source)
mutated_source_path = mutated_source / ccc.SOURCE_DIR_NAME / manifest["docs"][0]["file"]
with mutated_source_path.open("ab") as handle:
    handle.write(b"source provenance mutation")
mutated_source_verification = ccc.verify_corpus_bundle(mutated_source)
check(
    "mutated_local_source_pdf_is_rejected",
    mutated_source_verification.get("ok") is False
    and any(
        "source PDF" in item and ("sha256" in item or "byte count" in item)
        for item in mutated_source_verification.get("blockers") or []
    ),
    f"blockers={mutated_source_verification.get('blockers')}",
)

extra_source = case_root / "extra_source"
copy_local_bundle(extra_source)
shutil.copy2(
    extra_source / ccc.SOURCE_DIR_NAME / manifest["docs"][0]["file"],
    extra_source / ccc.SOURCE_DIR_NAME / "unbound_extra.pdf",
)
extra_source_verification = ccc.verify_corpus_bundle(extra_source)
check(
    "unbound_extra_source_pdf_is_rejected",
    extra_source_verification.get("ok") is False
    and any("unbound source PDF" in item for item in extra_source_verification.get("blockers") or []),
    f"blockers={extra_source_verification.get('blockers')}",
)

legacy = case_root / "legacy_v1"
copy_deploy_bundle(legacy)
legacy_manifest_path = legacy / ccc.MANIFEST_NAME
legacy_manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
legacy_manifest["schema"] = "engel_construction_corpus_manifest_v1"
legacy_manifest_path.write_text(json.dumps(legacy_manifest), encoding="utf-8")
legacy_verification = ccc.verify_corpus_bundle(legacy)
check(
    "v1_manifest_is_rejected",
    legacy_verification.get("ok") is False
    and any("schema" in item for item in legacy_verification.get("blockers") or []),
    f"blockers={legacy_verification.get('blockers')}",
)

partial = case_root / "partial"
copy_deploy_bundle(partial)
partial_target = partial / Path(manifest["docs"][0]["extracted_jsonl"])
partial_target.unlink()
partial_verification = ccc.verify_corpus_bundle(partial)
check(
    "partial_bundle_is_rejected",
    partial_verification.get("ok") is False
    and any("absent" in item or "missing bound" in item for item in partial_verification.get("blockers") or []),
    f"blockers={partial_verification.get('blockers')}",
)

tampered_index = case_root / "tampered_index"
copy_deploy_bundle(tampered_index)
with (tampered_index / ccc.INDEX_NAME).open("ab") as handle:
    handle.write(b" ")
tampered_index_verification = ccc.verify_corpus_bundle(tampered_index)
check(
    "tampered_index_is_rejected",
    tampered_index_verification.get("ok") is False
    and any("index" in item and ("sha256" in item or "byte count" in item)
            for item in tampered_index_verification.get("blockers") or []),
    f"blockers={tampered_index_verification.get('blockers')}",
)

tampered_extracted = case_root / "tampered_extracted"
copy_deploy_bundle(tampered_extracted)
tampered_relative = str(manifest["docs"][0]["extracted_jsonl"])
with (tampered_extracted / Path(tampered_relative)).open("ab") as handle:
    handle.write(b" ")
tampered_extracted_verification = ccc.verify_corpus_bundle(tampered_extracted)
check(
    "tampered_extracted_jsonl_is_rejected",
    tampered_extracted_verification.get("ok") is False
    and any("extracted" in item and ("sha256" in item or "byte count" in item)
            for item in tampered_extracted_verification.get("blockers") or []),
    f"blockers={tampered_extracted_verification.get('blockers')}",
)

tampered_source_binding = case_root / "tampered_source_binding"
copy_deploy_bundle(tampered_source_binding)
source_manifest_path = tampered_source_binding / ccc.MANIFEST_NAME
source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
source_manifest["docs"][0]["pages"] += 1
source_manifest_path.write_text(json.dumps(source_manifest), encoding="utf-8")
source_binding_verification = ccc.verify_corpus_bundle(tampered_source_binding)
check(
    "tampered_source_pdf_page_binding_is_rejected",
    source_binding_verification.get("ok") is False
    and any(
        "bundle_sha256" in item or "document inventory" in item
        for item in source_binding_verification.get("blockers") or []
    ),
    f"blockers={source_binding_verification.get('blockers')}",
)

extra = case_root / "extra_extracted"
copy_deploy_bundle(extra)
(extra / ccc.EXTRACT_DIR_NAME / "unbound.jsonl").write_text(
    json.dumps({"doc": "unbound.pdf", "page": 1, "text": "unbound"}) + "\n",
    encoding="utf-8",
)
extra_verification = ccc.verify_corpus_bundle(extra)
check(
    "exact_extracted_set_rejects_unbound_file",
    extra_verification.get("ok") is False
    and any("unbound file" in item for item in extra_verification.get("blockers") or []),
    f"blockers={extra_verification.get('blockers')}",
)

outside = case_root / "outside_path"
copy_deploy_bundle(outside)
outside_manifest_path = outside / ccc.MANIFEST_NAME
outside_manifest = json.loads(outside_manifest_path.read_text(encoding="utf-8"))
outside_manifest["docs"][0]["extracted_jsonl"] = "../outside.jsonl"
outside_manifest_path.write_text(json.dumps(outside_manifest), encoding="utf-8")
outside_verification = ccc.verify_corpus_bundle(outside)
check(
    "out_of_root_manifest_path_is_rejected",
    outside_verification.get("ok") is False
    and any("extracted_jsonl" in item or "outside" in item for item in outside_verification.get("blockers") or []),
    f"blockers={outside_verification.get('blockers')}",
)

empty = case_root / "empty"
empty.mkdir(parents=True, exist_ok=True)
empty_verification = ccc.verify_corpus_bundle(empty)
check(
    "empty_root_is_unverified_and_fail_closed",
    empty_verification.get("ok") is False
    and empty_verification.get("files") == []
    and ccc.grade_reply("Per Section 9999.99.", corpus_root=empty)["verdict"] == "undecidable",
    f"blockers={empty_verification.get('blockers')}",
)

symlink_case = case_root / "symlink"
copy_deploy_bundle(symlink_case)
symlink_relative = str(manifest["docs"][0]["extracted_jsonl"])
symlink_target = symlink_case / Path(symlink_relative)
outside_target = case_root / "outside_target.jsonl"
shutil.copy2(symlink_target, outside_target)
symlink_supported = True
try:
    symlink_target.unlink()
    os.symlink(outside_target, symlink_target)
except OSError:
    symlink_supported = False
symlink_verification = ccc.verify_corpus_bundle(symlink_case) if symlink_supported else {"ok": False, "blockers": []}
check(
    "symlinked_bundle_file_is_rejected",
    (not symlink_supported)
    or (
        symlink_verification.get("ok") is False
        and any("symlink" in item for item in symlink_verification.get("blockers") or [])
    ),
    "platform could not create a symlink; source check remains active"
    if not symlink_supported
    else f"blockers={symlink_verification.get('blockers')}",
)
known_live = ccc.grade_reply(
    'Per Section 1607.12: live loads on decks. '
    'Source excerpt: "SECTION 1607.12 Live loads on decks."', corpus_root=work,
    expected_documents=["synthetic_supplement.pdf"])
known_wind = ccc.grade_reply(
    'See Section R301.2.1: wind design. '
    'Source excerpt: "SECTION R301.2.1 Wind design."', corpus_root=work,
    expected_documents=["synthetic_supplement.pdf"])
check("known_sections_resolve",
      known_live["verdict"] == "verified" and known_wind["exactly_verified"],
      f"live={known_live['detail'][:100]}; wind={known_wind['detail'][:100]}")

missing_quote = ccc.grade_reply(
    "Per Section 1607.12: live loads on decks.", corpus_root=work,
    expected_documents=["synthetic_supplement.pdf"],
)
check("resolved_section_without_exact_quote_is_not_verified",
      missing_quote["verdict"] == "undecidable"
      and missing_quote["exactly_verified"] is False,
      f"resolved id without a matching quote remains unverified: {missing_quote['detail'][:100]}")

# (2026-08-10) Ledger-scope + excerpt-form fixes, fixtures from the first live
# evidence-packet run (80/80 rejected by over-strict binding; 56/80 admissible after).
ledger_ok = ccc.grade_reply(
    "Must not proceed until confirmed: deck live loads.\n"
    "Sourced facts:\n"
    '- Source document: "synthetic_supplement.pdf"; Section 1607.12; '
    '"Decks shall support the required live load"\n'
    "Open items:\n"
    "- Confirm Section R301.2.1 applicability -- owner: AHJ. Proof: full section text.",
    corpus_root=work, expected_documents=["synthetic_supplement.pdf"])
check("open_items_citing_sections_do_not_need_quotes",
      ledger_ok["verdict"] == "verified" and ledger_ok["claim_support_verified"],
      f"bare-quoted sourced fact + quoteless open item must verify: {ledger_ok['detail'][:90]}")
fabricated_open = ccc.grade_reply(
    "Sourced facts:\n"
    '- Source document: "synthetic_building_code.pdf"; Section 101.2; '
    '"SECTION 101.2 Requirements item 1 of chapter 1."\n'
    "Open items:\n- Confirm Section 9999.99 scope -- owner: AHJ.",
    corpus_root=work, expected_documents=["synthetic_building_code.pdf"])
check("fabricated_open_item_section_still_refutes",
      fabricated_open["refuted"] is True,
      f"open-item exemption must not shelter invented ids: {fabricated_open['detail'][:90]}")
hyphen_cleaned = ccc.grade_reply(
    "Sourced facts:\n"
    '- Source document: "synthetic_supplement.pdf"; Section 1607.12; '
    'exact excerpt: "Decks shall support the required live load"',
    corpus_root=work, expected_documents=["synthetic_supplement.pdf"])
check("packet_exact_excerpt_label_accepted",
      hyphen_cleaned["verdict"] == "verified",
      f"the packet's own label must parse: {hyphen_cleaned['detail'][:90]}")

contradicted = ccc.grade_reply(
    'Section 1607.12 requires a maximum ramp slope of 1:12. '
    'Source excerpt: "SECTION 1607.12 Live loads on decks."', corpus_root=work,
    expected_documents=["synthetic_supplement.pdf"],
)
check("existing_id_does_not_prove_the_claim",
      contradicted["verdict"] == "undecidable"
      and contradicted["exactly_verified"] is False
      and contradicted.get("claim_support_verified") is False,
      f"resolved id with unsupported quantity remains unverified: {contradicted['detail'][:100]}")

nearby_but_not_quoted = ccc.grade_reply(
    'Section 1607.12 requires wind design. '
    'Source excerpt: "SECTION 1607.12 Live loads on decks."', corpus_root=work,
    expected_documents=["synthetic_supplement.pdf"],
)
check("nearby_terms_outside_the_exact_quote_do_not_verify",
      nearby_but_not_quoted["verdict"] == "undecidable"
      and nearby_but_not_quoted["exactly_verified"] is False,
      "words elsewhere on the page cannot repair an unrelated exact excerpt")

# --- refutes fabricated citations ---------------------------------------------------
fabricated = ccc.grade_reply(
    "This is required by Section 9999.99 of the code.", corpus_root=work,
    expected_documents=["synthetic_building_code.pdf"],
)
check("fabricated_section_refuted",
      fabricated["refuted"] is True and "9999.99" in fabricated["detail"],
      f"detail: {fabricated['detail'][:90]}")

# --- California-amendment (CALDAG 11B-) citation form -------------------------------
known_parking = ccc.grade_reply(
    'Per Section 11B-208.2: parking spaces required. '
    'Source excerpt: "SECTION 11B-208.2 Parking spaces required."', corpus_root=work,
    expected_documents=["synthetic_building_code.pdf"])
known_doors = ccc.grade_reply(
    'See section 11b-404.2.4: door maneuvering clearances. '
    'Source excerpt: "SECTION 11B-404.2.4 Door maneuvering clearances."', corpus_root=work,
    expected_documents=["synthetic_building_code.pdf"])
check("california_amendment_sections_resolve",
      known_parking["verdict"] == "verified" and known_doors["exactly_verified"],
      f"parking={known_parking['detail'][:100]}; doors={known_doors['detail'][:100]}")
fabricated_ca = ccc.grade_reply(
    "Required by Section 11B-9999.99.", corpus_root=work,
    expected_documents=["synthetic_building_code.pdf"],
)
check("fabricated_california_section_refuted",
      fabricated_ca["refuted"] is True and "11B-9999.99" in fabricated_ca["detail"],
      f"detail: {fabricated_ca['detail'][:90]}")

# A mixed corpus is not one authority. The same section number can occur in a code book,
# supplement, calculation package, or another edition; exact verification requires one
# source document to be identified by the prompt or supplied explicitly.
ambiguous = ccc.grade_reply(
    'Per Section 1607.12: live loads on decks. '
    'Source excerpt: "SECTION 1607.12 Live loads on decks."', corpus_root=work
)
scoped_from_context = ccc.grade_reply(
    'Per Section 1607.12: live loads on decks. '
    'Source excerpt: "SECTION 1607.12 Live loads on decks."', corpus_root=work,
    context="Check the synthetic supplement before answering.",
)
check("mixed_corpus_requires_document_scope",
      ambiguous["verdict"] == "undecidable"
      and ambiguous.get("document_scope") == []
      and scoped_from_context["verdict"] == "verified"
      and scoped_from_context.get("document_scope") == ["synthetic_supplement.pdf"],
      "ambiguous library lookup is refused; distinctive prompt context binds one document")

# A comparison can cite the same section id in two editions. Document identity belongs to
# each claim line, not to the reply as a whole; quotes must never cross those identities.
multi_document = ccc.grade_reply(
    '- Source document: "synthetic_building_code.pdf"; Section 1607.12 states impact '
    'loads require special design. Source excerpt: "SECTION 1607.12 Impact loads require '
    'special design."\n'
    '- Source document: "synthetic_supplement.pdf"; Section 1607.12 states live loads '
    'on decks. Source excerpt: "SECTION 1607.12 Live loads on decks."',
    corpus_root=work,
    expected_documents=["synthetic_building_code.pdf", "synthetic_supplement.pdf"],
)
check(
    "multi_document_claims_bind_independently_even_with_same_section_id",
    multi_document.get("verdict") == "verified"
    and multi_document.get("document_scope")
    == ["synthetic_building_code.pdf", "synthetic_supplement.pdf"]
    and [item.get("document") for item in multi_document.get("support") or []]
    == ["synthetic_building_code.pdf", "synthetic_supplement.pdf"],
    json.dumps(multi_document, sort_keys=True),
)
cross_document_quote = ccc.grade_reply(
    '- Source document: "synthetic_building_code.pdf"; Section 1607.12 states live loads '
    'on decks. Source excerpt: "SECTION 1607.12 Live loads on decks."',
    corpus_root=work,
    expected_documents=["synthetic_building_code.pdf", "synthetic_supplement.pdf"],
)
check(
    "quote_from_one_document_cannot_verify_another_document_claim",
    cross_document_quote.get("verdict") == "undecidable"
    and cross_document_quote.get("exactly_verified") is False,
    json.dumps(cross_document_quote, sort_keys=True),
)
unbound_multi = ccc.grade_reply(
    'Section 1607.12 states live loads on decks. Source excerpt: "SECTION 1607.12 Live '
    'loads on decks."',
    corpus_root=work,
    expected_documents=["synthetic_building_code.pdf", "synthetic_supplement.pdf"],
)
check(
    "multi_document_answer_without_per_claim_filename_fails_closed",
    unbound_multi.get("verdict") == "undecidable"
    and "bound" in str(unbound_multi.get("detail") or ""),
    json.dumps(unbound_multi, sort_keys=True),
)
unknown_document = ccc.grade_reply(
    '- Source document: "plausible_but_absent_edition.pdf"; Section 1607.12 states live '
    'loads on decks. Source excerpt: "SECTION 1607.12 Live loads on decks."',
    corpus_root=work,
)
check(
    "unknown_source_filename_never_fuzzy_matches",
    unknown_document.get("verdict") == "undecidable"
    and "exact manifest filename" in str(unknown_document.get("detail") or ""),
    json.dumps(unknown_document, sort_keys=True),
)

prompt_packet = ccc.build_prompt_evidence_context(
    [
        {"document": "synthetic_building_code.pdf", "section": "1607.12"},
        {"document": "synthetic_supplement.pdf", "section": "1607.12"},
    ],
    corpus_root=work,
)
check(
    "prompt_evidence_packet_supplies_exact_multi_document_quotes",
    prompt_packet.get("ok") is True
    and len(prompt_packet.get("records") or []) == 2
    and 'Source document: "synthetic_building_code.pdf"' in prompt_packet.get("prompt_context", "")
    and 'Source document: "synthetic_supplement.pdf"' in prompt_packet.get("prompt_context", "")
    and prompt_packet.get("corpus_bundle_sha256") == bundle.get("bundle_sha256"),
    json.dumps(prompt_packet, sort_keys=True),
)
bad_prompt_packet = ccc.build_prompt_evidence_context(
    [{"document": "synthetic_supplement.pdf", "section": "9999.99"}],
    corpus_root=work,
)
check(
    "prompt_evidence_packet_fails_closed_on_missing_anchor",
    bad_prompt_packet.get("ok") is False and not bad_prompt_packet.get("prompt_context"),
    json.dumps(bad_prompt_packet, sort_keys=True),
)

# --- never refutes what it cannot prove ---------------------------------------------
check("no_citation_is_undecidable",
      ccc.grade_reply("Follow the local amendments and consult the AHJ.", corpus_root=work)
      ["refuted"] is False,
      "prose without explicit Section citations is never judged")
check("bare_numbers_never_judged",
      ccc.cited_sections("The 2022 edition, page 1607.12 of my notes") == []
      or ccc.grade_reply("The load is 1607.12 pounds", corpus_root=work)["refuted"] is False,
      "a dotted number without the word Section is not a citation")
missing_root = work / "nowhere"
check("missing_corpus_is_undecidable",
      ccc.grade_reply("Per Section 9999.99.", corpus_root=missing_root)["verdict"] == "undecidable",
      "no ingested corpus -> undecidable, never refuted")

# Small-index case: rebuild with only the supplement so absence cannot be proven.
small_work = work / "small_only"
(small_work / ccc.SOURCE_DIR_NAME).mkdir(parents=True, exist_ok=True)
shutil.copy2(source / "synthetic_supplement.pdf",
             small_work / ccc.SOURCE_DIR_NAME / "synthetic_supplement.pdf")
ccc.ingest(corpus_root=small_work)
check("small_index_cannot_prove_absence",
      ccc.grade_reply("Per Section 9999.99.", corpus_root=small_work)["refuted"] is False,
      "an index below the floor refuses to refute -- presence-only evidence")

# --- incremental ingest -------------------------------------------------------------
again = ccc.ingest(corpus_root=work)
check("unchanged_sources_reuse_extraction",
      all(d.get("reused_previous_extraction") for d in again["docs"]),
      "sha256-tracked sources are not re-extracted on every run")
current_bundle = ccc.verify_corpus_bundle(work)

# --- canonical eight-hour construction renewal is executable ------------------------
from engel_construction_renewal_curriculum import (  # noqa: E402
    ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1,
    ENGEL_CONSTRUCTION_RENEWAL_MATERIAL_VERSION,
    validate_renewal_cards,
)
from sync_engel_training_assets import build_template  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as training_runner  # noqa: E402

renewal_template = build_template(
    cards=ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1,
    version=ENGEL_CONSTRUCTION_RENEWAL_MATERIAL_VERSION,
    template_id="engel_main_construction_renewal_verifier",
    discipline="aec",
)
renewal_path = work / "CONSTRUCTION_RENEWAL_TEMPLATE.json"
renewal_path.write_text(json.dumps(renewal_template), encoding="utf-8")
previous_corpus_override = os.environ.get(ccc.CORPUS_ROOT_ENV)
try:
    os.environ[ccc.CORPUS_ROOT_ENV] = str(work)
    renewal_schedule = training_runner._load_training_schedule(
        str(renewal_path),
        "scheduled",
        1,
        8,
        "expert",
        10,
    )
finally:
    if previous_corpus_override is None:
        os.environ.pop(ccc.CORPUS_ROOT_ENV, None)
    else:
        os.environ[ccc.CORPUS_ROOT_ENV] = previous_corpus_override

check(
    "canonical_construction_renewal_is_eight_novel_substantive_cycles",
    validate_renewal_cards() == []
    and renewal_template.get("material_version")
    == ENGEL_CONSTRUCTION_RENEWAL_MATERIAL_VERSION
    and len(renewal_template.get("cycle_prompt_sets") or []) == 8
    and all(
        len(item.get("prompts") or []) == 10
        and item.get("material_card", {}).get("documents")
        and item.get("material_card", {}).get("evidence_anchors")
        for item in renewal_template.get("cycle_prompt_sets") or []
    )
    and len({
        prompt
        for item in renewal_template.get("cycle_prompt_sets") or []
        for prompt in item.get("prompts") or []
    }) == 80,
    f"cards={len(ENGEL_CONSTRUCTION_RENEWAL_CARDS_V1)} prompts="
    f"{sum(len(item.get('prompts') or []) for item in renewal_template.get('cycle_prompt_sets') or [])}",
)
check(
    "all_eighty_construction_prompts_receive_verified_evidence_before_ui",
    len(renewal_schedule.get("entries") or []) == 80
    and len(renewal_schedule.get("aec_evidence") or []) == 8
    and all(
        entry.get("aec_expected_documents")
        and entry.get("aec_evidence_bundle_sha256") == current_bundle.get("bundle_sha256")
        and entry.get("aec_evidence_records")
        and "Verified local evidence packet" in entry.get("prompt", "")
        and 'Source document: "' in entry.get("prompt", "")
        for entry in renewal_schedule.get("entries") or []
    ),
    f"entries={len(renewal_schedule.get('entries') or [])}; "
    f"evidence_hours={len(renewal_schedule.get('aec_evidence') or [])}; "
    f"with_docs={sum(bool(item.get('aec_expected_documents')) for item in renewal_schedule.get('entries') or [])}; "
    f"with_hash={sum(item.get('aec_evidence_bundle_sha256') == current_bundle.get('bundle_sha256') for item in renewal_schedule.get('entries') or [])}; "
    f"with_records={sum(bool(item.get('aec_evidence_records')) for item in renewal_schedule.get('entries') or [])}; "
    f"with_packet={sum('Verified local evidence packet' in item.get('prompt', '') for item in renewal_schedule.get('entries') or [])}; "
    f"with_source={sum(('Source document: ' + chr(34)) in item.get('prompt', '') for item in renewal_schedule.get('entries') or [])}; "
    f"expected_hash={current_bundle.get('bundle_sha256')}; actual_hash={(renewal_schedule.get('entries') or [{}])[0].get('aec_evidence_bundle_sha256')}",
)

# --- trainer wiring -----------------------------------------------------------------
trainer_source = (ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py").read_text(
    encoding="utf-8")
check("trainer_guards_aec_with_the_corpus",
      "_aec_citation_truth" in trainer_source
      and "_aec_evidence_for_card" in trainer_source
      and '"aec_citation_verdict"' in trainer_source
      and "context=prompt_context" in trainer_source
      and "expected_documents=expected_documents" in trainer_source
      and "manifest filename>" in trainer_source
      and "Source document:" in trainer_source
      and "Source excerpt:" in trainer_source
      and 'aec_truth.get("exactly_verified") is not True' in trainer_source,
      "AEC training supplies verified excerpts and binds each claim to one exact document")

shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(case_root, ignore_errors=True)

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_construction_corpus_verifier_v2",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
