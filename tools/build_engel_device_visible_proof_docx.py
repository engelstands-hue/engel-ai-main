#!/usr/bin/env python3
"""Build the Engel device-visible proof status DOCX.

This uses only Python's standard library so it does not depend on python-docx.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Engel_Device_Visible_Proof_Status_GoogleDocs.docx"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def para(text: str, style: str = "Normal") -> str:
    return (
        "<w:p>"
        f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>"
        f"<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r>"
        "</w:p>"
    )


def title_para(text: str) -> str:
    return (
        "<w:p>"
        "<w:pPr><w:pStyle w:val=\"DocTitle\"/><w:spacing w:before=\"0\" w:after=\"60\" w:line=\"276\" w:lineRule=\"auto\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\"/><w:sz w:val=\"52\"/><w:color w:val=\"000000\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r>"
        "</w:p>"
    )


def body_xml() -> str:
    content: list[str] = []
    content.append(title_para("Engel Device Visible Proof Status"))
    content.append(para(f"Saved UTC: {utc_stamp()}", "Subtitle"))
    content.append(para("Preset: google_docs_default. Purpose: live shared operator note for the Windows Sub-Engel visibility issue and fix.", "Subtitle"))

    sections = [
        ("What The Two-Hour Test Proved", [
            "The Engel cluster UI soak ran from 2026-05-31T00:23:28Z to 2026-05-31T02:23:44Z for 7216.3 seconds.",
            "The test submitted 64 UI prompts through Engel AI Main and observed 66 agents and 68 skills in the Agent Meeting Room order flow.",
            "The current Sub-Engel desktop lane returned allowlisted diagnostic probes through the paired controller route.",
            "The retired desktop is excluded from Engel AI Main routing and is kept only as disabled history. DESKTOP-UE5A6GG remains the current Sub-Engel desktop lane when paired.",
        ]),
        ("Why Nothing Appeared On The Devices", [
            "The test proved controller-to-node diagnostics and Engel AI Main transcript routing, but the node agent that was already running on both devices returned results silently to Engel Main.",
            "That older running agent did not print every paired controller command in the foreground PowerShell window.",
            "The current connected nodes are real and reachable, but their in-memory allowlist does not yet include ui.visible_status.",
        ]),
        ("Change Made Here", [
            "Added ui.visible_status as a pair-gated, allowlisted Windows Sub-Engel action.",
            "Updated the node agent so paired controller commands print in the foreground node window.",
            "Updated the long soak harness so future heartbeats call ui.visible_status.",
            "Added tools/run_windows_sub_engel_visible_proof.py to test visible device proof directly.",
            "Updated the node verifier so this visibility route is required by future checks.",
        ]),
        ("Current Device Check", [
            "Retired desktop: excluded from active Engel AI Main routing.",
            "DESKTOP-UE5A6GG: active Sub-Engel desktop lane when paired; visible proof requires the current foreground agent.",
            "This is a one-time transition from the silent agent to the visible-proof agent, not something that should be repeated for every normal connected test.",
        ]),
        ("Safety Boundary Preserved", [
            "No raw shell, SSH, reboot, shutdown, service install, firewall modification, provider runtime, model runtime, remote package install, or remote disk install/format/partition action was added.",
            "The new visible action prints status proof only and writes normal node state/receipt records.",
            "Future tests should not claim device-visible proof unless the node advertises and successfully executes ui.visible_status.",
        ]),
        ("Proof Files", [
            r"Main soak report: D:\b.WorkSpace\Engel App\reports\codex_bridge\ENGEL_CLUSTER_UI_SOAK_TEST_20260531T002328Z.md",
            r"Main transcript: D:\b.WorkSpace\Engel App\reports\cluster_ui_soak\20260531T002328Z\engel_ai_main_chat_transcript.txt",
            r"Meeting Room transcript: D:\b.WorkSpace\Engel App\reports\cluster_ui_soak\20260531T002328Z\meeting_room_order_flow_transcript.txt",
            r"Visible proof check: D:\b.WorkSpace\Engel App\reports\codex_bridge\ENGEL_WINDOWS_SUB_ENGEL_VISIBLE_PROOF_20260531T023437Z.md",
        ]),
    ]
    for heading, paragraphs in sections:
        content.append(para(heading, "Heading1"))
        for item in paragraphs:
            content.append(para(item))

    sect = (
        "<w:sectPr>"
        "<w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
        "</w:sectPr>"
    )
    return "".join(content) + sect


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>
"""


STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="DocTitle">
    <w:name w:val="DocTitle"/>
    <w:pPr><w:spacing w:before="0" w:after="60" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="52"/><w:color w:val="000000"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/><w:color w:val="555555"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="400" w:after="120"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="40"/><w:color w:val="000000"/></w:rPr>
  </w:style>
</w:styles>
"""


SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
  <w:defaultTabStop w:val="720"/>
</w:settings>
"""


APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>
"""


def main() -> int:
    created = utc_stamp()
    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Engel Device Visible Proof Status</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>
"""
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body_xml()}</w:body>
</w:document>
"""
    with ZipFile(OUT, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/styles.xml", STYLES)
        zf.writestr("word/settings.xml", SETTINGS)
        zf.writestr("docProps/core.xml", core)
        zf.writestr("docProps/app.xml", APP)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
