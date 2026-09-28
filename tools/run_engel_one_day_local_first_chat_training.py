#!/usr/bin/env python3
"""Run a restartable one-day Engel chat campaign through desktop and Discord UI.

Every model turn is verified as either CT246/local GGUF or a provider response
whose CT receipt proves that the local model was attempted and failed first.
The supervisor records device health without stopping useful chat work when a
worker is temporarily offline.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "python310" / "python.exe"
VISIBLE_RUNNER = ROOT / "tools" / "run_engel_visible_chat_ui_soak.py"
DISCORD_RUNNER = ROOT / "tools" / "run_engel_discord_owner_ui_training.py"
APP_EXE = ROOT / "engel_flutter_main" / "build" / "windows" / "x64" / "runner" / "Release" / "EngelAIMain.exe"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
RUNTIME_ROOT = ROOT / "runtime" / "one_day_local_first_chat_training"
ACTIVE_PATH = RUNTIME_ROOT / "ACTIVE.json"
CHAT_HEALTH_URL = "http://127.0.0.1:24680/health"
ROOM_HEALTH_URL = "http://127.0.0.1:8790/health"
PHONE_CLUSTER_URL = "http://192.0.2.40:8765/cluster/status"
CT_HOST = "192.0.2.50"
CT_PORT = "24622"
CT_KEY = Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"


DESKTOP_PROMPT_SETS = [
    [
        "Hey Engel, how are you doing today?",
        "I want this to feel like a normal conversation, not a status screen.",
        "What do you understand about the way I like to work?",
        "Keep that answer practical and plain.",
        "What should you do when you are not sure what I meant?",
        "Give me one example of a useful follow-up question.",
        "That is close. Make it sound less formal.",
        "What were we discussing a few messages ago?",
        "Tell me one correction from this conversation worth remembering.",
        "Wrap this up naturally and suggest one useful next topic.",
    ],
    [
        "I want to reduce repetitive drafting work. Where would you start?",
        "Pick one part of a shop drawing workflow and stay focused on it.",
        "What information would you need from me before changing that workflow?",
        "Explain the idea without software jargon.",
        "What could go wrong if the checking rules are too broad?",
        "Give me a small first test instead of a giant project.",
        "How would I know that the test actually saved time?",
        "Say that again in two short sentences.",
        "What decision did we make in this conversation?",
        "Keep the thread going and tell me the next practical step.",
    ],
    [
        "Talk through a simple quality check for shop drawings with me.",
        "Start with dimensions and missing notes.",
        "How would you separate a real issue from a harmless difference?",
        "What would you ask me before flagging something uncertain?",
        "Keep the answer short enough to use while I am working.",
        "Now add one check for revision consistency.",
        "Which check should happen first and why?",
        "Do not restart the explanation. Continue from the last answer.",
        "Summarize the check in plain language.",
        "What should Engel remember about how I want these checks presented?",
    ],
    [
        "I have several jobs competing for attention. Help me sort them out.",
        "What is the first question you would ask about deadlines?",
        "Assume two jobs have the same deadline. What matters next?",
        "Keep this conversational instead of giving me a long framework.",
        "How should we account for work that is waiting on someone else?",
        "Give me a quick example with three made-up jobs.",
        "Now shorten that example without losing the decision.",
        "What did I ask you to avoid in your replies?",
        "How can you preserve this context when I return later?",
        "End with one clear action I could take now.",
    ],
    [
        "Suppose I tell you your last suggestion did not work. How should you respond?",
        "Ask me one useful diagnostic question, not five at once.",
        "I answer that the result was slow and repeated itself. What next?",
        "Do not claim a repair before you have proof.",
        "What evidence would show the problem is really fixed?",
        "Explain the difference between a test result and a guess.",
        "Make that sound like a normal person talking.",
        "What failure are we trying to prevent here?",
        "Give me a short recap without backend terminology.",
        "What should you remember the next time I report a broken chat?",
    ],
    [
        "What does honest proof look like when Engel completes a task?",
        "Keep files, commands, and visible results separate in your answer.",
        "What should you say when only part of a task worked?",
        "Give me a short example without inventing a file path.",
        "How should persistent memory help the next conversation?",
        "What should never be saved as a trusted fact?",
        "Say that more casually.",
        "What was the main point of this conversation?",
        "Give me two rules you can apply on the next task.",
        "Close this out without sounding like a customer support script.",
    ],
]


DISCORD_PROMPT_SETS = [
    [
        "Hey Engel, give me a normal quick check-in.",
        "What kind of work do you understand I do?",
        "Keep that answer brief and natural.",
        "If you are unsure about a detail, what will you do?",
        "What were we just talking about?",
        "Finish with one useful question for me.",
    ],
    [
        "I am thinking about making drafting checks less repetitive.",
        "Pick one small check that would be worth testing first.",
        "What would you need from me before trying it?",
        "Say that without technical jargon.",
        "How would we prove it saved time?",
        "Give me the next step in one sentence.",
    ],
    [
        "Help me think through missing dimensions on a shop drawing.",
        "What would count as a real warning?",
        "How should you handle something that might be intentional?",
        "Keep the answer focused on the current question.",
        "Summarize our approach in two sentences.",
        "What should you remember from this chat?",
    ],
    [
        "I have three jobs to prioritize and I am not sure where to start.",
        "Ask me the most useful first question.",
        "Assume the deadlines match. What should we compare next?",
        "Make that sound less formal.",
        "What decision did we reach?",
        "End with one practical action.",
    ],
    [
        "Your last answer repeated itself. How should we fix that?",
        "Ask me one question that would help diagnose it.",
        "What proof would show the reply is actually better?",
        "Do not mention internal routes or receipts in the public reply.",
        "What did I ask you to avoid?",
        "Reply naturally and keep it short.",
    ],
    [
        "When you complete something for me, what proof should I see?",
        "What should you say if only part of it worked?",
        "Give me a short honest example.",
        "How does memory help without turning into made-up facts?",
        "What was the main point of this conversation?",
        "Close this out like a normal conversation.",
    ],
]


NEW_MATERIAL_CARDS = [
    {
        "topic": "file naming and version control for drawing packages",
        "scenario": "A project folder has final, final-two, revised, and issued copies mixed together.",
        "constraint": "The rule must still be easy to follow during a busy deadline.",
        "proof": "Use one example filename and explain how it prevents the wrong sheet from being issued.",
    },
    {
        "topic": "turning client redlines into a controlled revision list",
        "scenario": "The client sent marked-up PDFs, an email note, and a phone correction for the same revision.",
        "constraint": "Do not assume conflicting instructions mean the newest one is automatically correct.",
        "proof": "Show how the final checklist would expose a conflict before drafting starts.",
    },
    {
        "topic": "keeping a sheet index synchronized with a drawing set",
        "scenario": "Two sheets were renamed and one was removed after the index was prepared.",
        "constraint": "The check should work even when sheet order changes.",
        "proof": "Describe the evidence that proves the index and package agree.",
    },
    {
        "topic": "cleaning inconsistent CAD layers without damaging a project",
        "scenario": "Imported details use duplicate colors, lineweights, and nearly identical layer names.",
        "constraint": "Preserve intentional exceptions and avoid a blind bulk rename.",
        "proof": "Give a safe sample-first test and its pass condition.",
    },
    {
        "topic": "checking dimensions across plan, elevation, and detail views",
        "scenario": "A width changed in plan but the elevation and enlarged detail may still show the old value.",
        "constraint": "Flag uncertainty instead of inventing the design intent.",
        "proof": "Explain what matching evidence would close the warning.",
    },
    {
        "topic": "finding conflicts between general notes and detail callouts",
        "scenario": "A general note names one material while a detail label names another.",
        "constraint": "The result must point to the exact conflict without deciding which source wins.",
        "proof": "Give a concise warning a drafter could act on.",
    },
    {
        "topic": "auditing revision clouds and revision tags before issue",
        "scenario": "Some changed areas have clouds, some have tags, and the revision block was edited separately.",
        "constraint": "Do not treat every graphical cloud as a current revision.",
        "proof": "State the three-way comparison that proves the issue set is consistent.",
    },
    {
        "topic": "preparing an RFI from an unclear drawing condition",
        "scenario": "A connection detail does not match the dimensions shown on the plan.",
        "constraint": "The question must be neutral and must not hide the impact on drafting progress.",
        "proof": "Draft the core question and identify the supporting references it needs.",
    },
    {
        "topic": "checking a drawing transmittal before release",
        "scenario": "The package includes revised PDFs, a model export, and a superseded reference file.",
        "constraint": "Keep the release check short enough that people will actually use it.",
        "proof": "Name the receipt fields that demonstrate exactly what was sent.",
    },
    {
        "topic": "handling a client scope change without losing the original agreement",
        "scenario": "A small requested edit affects several sheets and may change the delivery date.",
        "constraint": "Separate clarification from approval and avoid sounding confrontational.",
        "proof": "Give a short response that records scope, impact, and the decision needed.",
    },
    {
        "topic": "prioritizing work when deadlines and dependencies conflict",
        "scenario": "One job is due first, but another is blocking a client review and a third is nearly complete.",
        "constraint": "Do not reduce the decision to deadline alone.",
        "proof": "Walk through a ranking and name the fact that could change it.",
    },
    {
        "topic": "handing a drafting task to another person without losing context",
        "scenario": "The next person needs to continue a partially checked drawing set tomorrow morning.",
        "constraint": "The handoff should distinguish completed checks, open questions, and assumptions.",
        "proof": "Produce a compact handoff structure and one realistic example item.",
    },
    {
        "topic": "turning a vague software complaint into a useful bug report",
        "scenario": "The report only says the chat is slow and sometimes repeats.",
        "constraint": "Ask one question at a time and do not claim a cause before evidence exists.",
        "proof": "Identify the smallest reproducible test and its expected result.",
    },
    {
        "topic": "maintaining conversation continuity after a service restart",
        "scenario": "The user returns after a restart and refers to a decision made earlier in the day.",
        "constraint": "Use saved context without pretending to remember details that were never stored.",
        "proof": "Show how Engel should answer when the referenced detail is present and when it is missing.",
    },
    {
        "topic": "protecting owner-only controls while keeping Discord chat public",
        "scenario": "Another Discord member asks Engel to run a command instead of just chatting.",
        "constraint": "The public reply must not leak paths, tokens, device details, or control instructions.",
        "proof": "Give the safe public reply and state what owner proof would be recorded privately.",
    },
    {
        "topic": "keeping active AI models on the approved CT246 SSD root",
        "scenario": "An old note points to a storage root that is outside the current CT246 allowlist.",
        "constraint": "Do not move, delete, or recreate storage as part of the check.",
        "proof": "Explain which runtime facts prove the model is using engel-fast-ssd.",
    },
    {
        "topic": "splitting one bounded job across the server, Sub-Engel, and phone workers",
        "scenario": "The server owns the final result while workers can return status, checks, and small artifacts.",
        "constraint": "An offline worker must be reported honestly and cannot be counted as a successful return.",
        "proof": "Define the four receipts needed before the job can be called complete.",
    },
    {
        "topic": "showing visible proof for a completed web or desktop app",
        "scenario": "The files exist, but the user needs to inspect the running result from Engel AI Main.",
        "constraint": "A source path alone is not visual proof and a preview must not claim a failed build passed.",
        "proof": "Describe the preview, test, package, and open-result evidence in the order the user should see it.",
    },
]


CAMPAIGN_MATERIAL_VERSION = "fresh_work_material_v17_20260721"


FRESH_MATERIAL_CARDS_V5 = [
    {
        "topic": "preparing a curb-adapter survey package for replacement rooftop equipment",
        "scenario": "The replacement unit data is available, but the existing curb, duct opening, roof slope, and nearby conduit were measured by different people on different days.",
        "constraint": "Do not combine measurements until their datums, units, and measurement dates are explicit.",
        "proof": "The survey package must tie every critical dimension to a source photo or field note and identify each item that needs remeasurement.",
    },
    {
        "topic": "verifying revision clouds and delta tags before a bulletin issue",
        "scenario": "Several sheets contain clouds from an earlier review, while the current bulletin log lists a different set of changed details.",
        "constraint": "Do not remove a cloud just because it looks old; trace it to the revision history first.",
        "proof": "Each cloud and delta must reconcile to the bulletin, affected view, revision description, and issue date.",
    },
    {
        "topic": "building a panel cut list from elevations with mixed joint conditions",
        "scenario": "The elevations show standard panels, corner returns, field cuts, and two joints that shift between floors.",
        "constraint": "Do not optimize quantities until every panel has a unique location and finished orientation.",
        "proof": "The cut list must reconcile panel mark, dimensions, grain or finish direction, edge treatment, quantity, and elevation location.",
    },
    {
        "topic": "laying out interior signage while accessibility inputs are incomplete",
        "scenario": "Room names and door swings are known, but mounting heights, tactile requirements, and final sign families are split between specifications and an unfinished schedule.",
        "constraint": "Do not invent compliance dimensions or treat a typical detail as project approval.",
        "proof": "The layout must separate confirmed locations from code and design questions and identify the authority for each open requirement.",
    },
    {
        "topic": "overlaying service-access zones around mechanical equipment",
        "scenario": "The equipment plan is current, but manufacturer service zones, door swings, ladder access, and roof-edge restrictions come from separate documents.",
        "constraint": "Keep manufacturer recommendations, code-required clearances, and project preferences distinguishable.",
        "proof": "Every zone must cite its source and conflicts must be visible before any equipment move is proposed.",
    },
    {
        "topic": "creating a searchable construction-photo index for concealed work",
        "scenario": "Hundreds of photos show backing, utilities, and waterproofing before closure, but filenames contain no useful location data.",
        "constraint": "Never discard original timestamps or claim a location that cannot be supported by sequence or visible context.",
        "proof": "Each indexed photo needs original identity, date, level or room confidence, subject tags, and a link back to the untouched source.",
    },
    {
        "topic": "maintaining a utility-conflict log during corridor coordination",
        "scenario": "Ceiling framing, ductwork, piping, cable tray, and access panels compete for the same narrow zone.",
        "constraint": "Do not call a conflict resolved until the changed owner and downstream drawing effects are known.",
        "proof": "The log must capture location, systems, required clearance, assigned owner, proposed move, approvals, and verification view.",
    },
    {
        "topic": "normalizing as-built redlines received from multiple field crews",
        "scenario": "One crew used colors, another used numbered notes, and a third sent annotated phone screenshots with overlapping changes.",
        "constraint": "Preserve who reported each condition and never merge conflicting redlines into one apparent fact.",
        "proof": "The consolidated record must show source, date, affected view, normalized change, conflict state, and field confirmation need.",
    },
    {
        "topic": "reconciling a glazing opening matrix with architectural elevations",
        "scenario": "Opening marks repeat across floors, but glass type, frame depth, sill condition, and dimensions vary in a few locations.",
        "constraint": "Do not let a repeated mark overwrite a location-specific exception.",
        "proof": "The matrix must trace each opening to level, elevation, detail, dimensions, material selections, and unresolved exceptions.",
    },
    {
        "topic": "planning a stair and guard field-verification walk",
        "scenario": "Record drawings show the stair geometry, but finished floor buildup, nosings, landings, and existing guard conditions may have changed.",
        "constraint": "Do not treat record dimensions as field measurements or make compliance conclusions from photographs alone.",
        "proof": "The walk sheet must define datums, measurements, photo views, tools, locations, and the reviewer for any code-sensitive condition.",
    },
    {
        "topic": "releasing a CNC nesting package without mixing material grades",
        "scenario": "The nest combines similar thicknesses from two grades, remnants have incomplete labels, and one part was revised after nesting.",
        "constraint": "Do not infer grade from thickness or reuse a remnant without traceable identification.",
        "proof": "Release requires part revision, material grade, heat or stock identity, nest file, quantities, remnant disposition, and operator acknowledgement.",
    },
    {
        "topic": "reconciling drawing transmittals with what recipients actually received",
        "scenario": "The issue log lists one package, the email attachment list shows another, and a cloud upload was replaced after sending.",
        "constraint": "A sent email is not proof that every intended file was delivered or opened.",
        "proof": "The reconciliation must compare manifest, hashes, transfer channel, recipient, timestamps, replacement history, and access confirmation.",
    },
    {
        "topic": "extracting vendor data into an equipment schedule with source traceability",
        "scenario": "Cutsheets contain nominal values, option-dependent values, and notes that conflict with a sales summary.",
        "constraint": "Do not copy a value without preserving its model, option, unit, and source page.",
        "proof": "Each schedule value must link to the exact source and conflicts must remain open until the responsible party resolves them.",
    },
    {
        "topic": "auditing drawing scales after details are copied between sheets",
        "scenario": "Several details were reused from another package and their titles, viewport scales, and dimension styles do not all agree.",
        "constraint": "Do not trust the printed scale note without checking the viewport and a known dimension.",
        "proof": "The audit must record sheet, view, stated scale, actual scale, dimension check, correction, and reviewer.",
    },
    {
        "topic": "tracking deferred submittals that affect early coordination",
        "scenario": "Final equipment selections arrive later, but openings, supports, power, and access paths need decisions now.",
        "constraint": "Do not present a design allowance as final vendor data.",
        "proof": "The tracker must separate temporary criteria, source, affected work, decision deadline, responsible party, and replacement with approved data.",
    },
    {
        "topic": "investigating an anchor inventory count that disagrees with fabrication records",
        "scenario": "Receiving counted fewer anchors than the packing list, while a partial kit may already be staged at another work area.",
        "constraint": "Do not assign loss or reorder material until custody and count boundaries are clear.",
        "proof": "The investigation must trace purchase quantity, shipment, receiving count, transfers, staging, installed quantity, and recount evidence.",
    },
    {
        "topic": "handing off a BIM clash that affects several disciplines",
        "scenario": "A clash appears between a beam, duct transition, sprinkler main, and ceiling access zone, and no single trade owns the whole resolution.",
        "constraint": "Do not close the clash on a verbal agreement or a screenshot with no model revision.",
        "proof": "Closure requires coordinates, affected model elements, assigned actions, approved resolution, model versions, and a rerun showing clearance.",
    },
    {
        "topic": "defining the scope boundary between design drawings and fabrication engineering",
        "scenario": "The project requires coordinated geometry, but connection design, stamped calculations, and delegated components belong to different parties.",
        "constraint": "Do not let detailed drafting imply that Engel or the drafter accepted engineering responsibility.",
        "proof": "The scope map must identify each deliverable, input, decision owner, review role, exclusion, and required approval.",
    },
    {
        "topic": "sampling a large batch of generated PDFs for release confidence",
        "scenario": "An automated export produced hundreds of sheets overnight and a full manual page-by-page check is impractical before the deadline.",
        "constraint": "Sampling cannot conceal known errors or replace checks that can be automated across every file.",
        "proof": "The plan must define universal automated checks, risk-based samples, visual criteria, failure expansion rules, and final signoff.",
    },
    {
        "topic": "proving that a project backup can actually be restored",
        "scenario": "Nightly archives report success, but no one has opened a restored project with its references, fonts, and linked data.",
        "constraint": "Do not modify the live project or call archive creation a restore test.",
        "proof": "The test must use an isolated destination, verify hashes, open the project, resolve references, inspect representative outputs, and record cleanup.",
    },
    {
        "topic": "diagnosing a local chat slowdown without bypassing Engel's model route",
        "scenario": "Replies became slow after a service restart, while the desktop UI, CT tunnel, local model service, and provider bridges all still report partial health.",
        "constraint": "Do not switch production chat to a provider merely because it is easier to test.",
        "proof": "The diagnosis must time UI submission, tunnel transit, queue wait, model generation, persistence, and rendering before choosing a repair.",
    },
    {
        "topic": "splitting an OCR review package across three phone workers",
        "scenario": "A scanned specification has tables, rotated notes, faint stamps, and handwritten corrections that need independent checks.",
        "constraint": "A phone heartbeat is not a completed assignment, and no worker result can overwrite the source scan.",
        "proof": "The merge must show assignment IDs, page ranges, worker identities, extracted text, confidence, disagreements, validation, and final source links.",
    },
    {
        "topic": "keeping Discord useful for public conversation without exposing owner controls",
        "scenario": "A non-owner asks normal project questions, then tries to discover device addresses, command routes, and stored credentials in the same thread.",
        "constraint": "Public chat may answer safe conversational content but must not reveal infrastructure or authorize actions.",
        "proof": "Verification requires separate owner and non-owner tests, immutable identity evidence, safe replies, blocked controls, and no leaked sensitive details.",
    },
    {
        "topic": "presenting evidence for a newly built desktop or web tool inside Engel AI Main",
        "scenario": "The build and tests succeeded, but the user still needs to see the running tool, inspect its behavior, and locate the packaged result.",
        "constraint": "Do not substitute source files, static status text, or a screenshot of the wrong process for a working preview.",
        "proof": "Evidence must include the actual launched artifact, interactive preview, relevant test results, package path, process identity, and any remaining limitation.",
    },
]


# v5 is retained above only as retired collision history. Every v6 card and
# every generated turn is new material that has not appeared in an earlier
# one-day campaign.
FRESH_MATERIAL_CARDS_V6 = [
    {
        "topic": "transferring a civil survey datum into structural embed layouts",
        "scenario": "The civil benchmark, structural grid, and fabricator coordinate origin are documented separately, and one early layout used an assumed offset.",
        "constraint": "No coordinate may be converted until its reference system, units, and sign convention are recorded.",
        "proof": "Acceptance requires a closed coordinate check at two known points plus the named survey and structural sources.",
    },
    {
        "topic": "coordinating a storefront door hardware schedule with frame details",
        "scenario": "Door handing and hardware sets are scheduled, but several frame elevations show different head conditions and electrified hardware rough-ins.",
        "constraint": "Do not treat a repeated hardware set as proof that every opening has the same frame preparation.",
        "proof": "Each opening must reconcile handing, set, frame prep, power need, detail reference, and unresolved exception.",
    },
    {
        "topic": "registering two laser scans taken before and after temporary shoring",
        "scenario": "The scans overlap only in part, control targets moved near one corner, and the later scan includes new steel that hides old reference surfaces.",
        "constraint": "Do not force a best-fit alignment across geometry that may have physically moved.",
        "proof": "The registration record needs stable control, residuals by region, excluded geometry, transform values, and an independent spot check.",
    },
    {
        "topic": "reviewing modular-unit lifting drawings before a site pick",
        "scenario": "The unit weight is revised, rigging points are shown on an earlier framing plan, and the crane setup note assumes a different delivery orientation.",
        "constraint": "Do not infer lifting capacity or approve engineered rigging from drafting geometry.",
        "proof": "The review must connect current weight, center of gravity, engineered lift points, rigging plan, orientation, exclusions, and approvals.",
    },
    {
        "topic": "tracking penetration and firestop requirements through rated assemblies",
        "scenario": "The model contains penetrations, the life-safety sheets define ratings, and product systems are still being selected by multiple trades.",
        "constraint": "Do not assign a listed system from opening size alone or merge unlike penetrants into one condition.",
        "proof": "Every condition needs assembly rating, penetrant type, annular space, backing, listed system source, installer, and inspection state.",
    },
    {
        "topic": "turning finish samples and mockup decisions into drawing updates",
        "scenario": "Meeting notes approve colors conditionally, physical samples carry handwritten comments, and elevations still show the original pattern break.",
        "constraint": "A discussion or unlabeled sample is not a final design authorization.",
        "proof": "The decision trail must tie sample identity, reviewer, conditions, approval date, affected views, and completed revisions together.",
    },
    {
        "topic": "finding orphaned detail references before a drawing issue",
        "scenario": "Sheets were reorganized, several details moved, and copied callouts may still point to deleted or unrelated views.",
        "constraint": "Do not repair a reference by choosing the nearest plausible detail number.",
        "proof": "The audit must resolve every callout to an existing intended view and record ambiguous references for design confirmation.",
    },
    {
        "topic": "closing RFIs without losing downstream drawing changes",
        "scenario": "An RFI answer changes geometry, but the sketch, model, fabrication package, and procurement note are maintained by different people.",
        "constraint": "Do not mark the RFI closed merely because a written response exists.",
        "proof": "Closure needs response authority, affected documents, assigned edits, revision evidence, distribution, and downstream acknowledgement.",
    },
    {
        "topic": "field-measuring millwork where walls are out of square",
        "scenario": "Nominal plans are available, finished surfaces vary, and the casework has tight scribes plus appliance clearances.",
        "constraint": "Do not reduce irregular field conditions to one width and height measurement.",
        "proof": "The field sheet must capture datum, multiple widths and heights, diagonals, plumb, obstructions, appliance data, and photo locations.",
    },
    {
        "topic": "comparing a point cloud to a record model for renovation planning",
        "scenario": "The record model is clean but old, while the point cloud has occlusions around ceilings and reflective equipment surfaces.",
        "constraint": "Neither record geometry nor missing scan data may be presented as verified existing condition.",
        "proof": "The comparison must classify confirmed matches, measured deviations, occluded zones, confidence, and required field verification.",
    },
    {
        "topic": "checking precast embed coordination against steel connection drawings",
        "scenario": "Embed plates are located in the precast model, connection forces are documented elsewhere, and one beam size changed after the last exchange.",
        "constraint": "Do not move an embed based only on visual clash clearance.",
        "proof": "Each embed needs element identity, coordinates, plate and anchor data, connected steel revision, engineering review, and release status.",
    },
    {
        "topic": "validating electrical impacts of replacement mechanical equipment",
        "scenario": "The replacement equipment schedule changes voltage and controls, while panel capacity, disconnect size, and feeder routing come from separate records.",
        "constraint": "Do not conclude capacity or code compliance from nameplate amperage alone.",
        "proof": "The coordination record must identify equipment data, load basis, panel source, protective device, feeder, disconnect, controls, and electrical approval.",
    },
    {
        "topic": "standardizing title blocks across a mixed shop-drawing package",
        "scenario": "Files from several subcontractors use different revision fields, project identifiers, sheet numbering, and approval stamps.",
        "constraint": "Do not overwrite authorship, certification, or historical issue data while normalizing presentation.",
        "proof": "The package check must preserve origin and history while reconciling project ID, sheet ID, revision, status, dates, and distribution metadata.",
    },
    {
        "topic": "building a weld map that remains traceable through fabrication",
        "scenario": "Shop drawings show weld symbols, the procedure list is separate, and inspection records identify welds by temporary shop marks.",
        "constraint": "Do not map a weld procedure from symbol appearance or material thickness alone.",
        "proof": "Traceability requires member location, weld ID, joint detail, procedure, welder, material, inspection method, result, and repair history.",
    },
    {
        "topic": "reviewing roof drainage changes around new equipment curbs",
        "scenario": "New curbs interrupt existing drainage paths, roof slopes are partly inferred, and drain capacity information is incomplete.",
        "constraint": "Do not promise drainage performance or create unverified slopes from a plan graphic.",
        "proof": "The review must show known elevations, flow paths, obstructions, drains and overflow routes, unknowns, and responsible design review.",
    },
    {
        "topic": "coordinating delegated equipment anchorage with architectural details",
        "scenario": "Architectural sheets show housekeeping pads and clearances, while anchorage forces and final fasteners belong to delegated engineering.",
        "constraint": "Drafting coordination must not imply acceptance of anchorage engineering.",
        "proof": "The boundary record must identify geometry inputs, substrate data, delegated calculations, connection details, reviewers, exclusions, and approvals.",
    },
    {
        "topic": "converting a scan-derived floor plan into controlled CAD layers",
        "scenario": "The scan contains walls, equipment, annotations, temporary objects, and uncertain edges at several confidence levels.",
        "constraint": "Do not flatten measured, inferred, and temporary geometry into indistinguishable linework.",
        "proof": "The CAD deliverable needs layer rules, confidence classes, source references, registration data, unresolved zones, and a visual QA overlay.",
    },
    {
        "topic": "sequencing a multi-package release with shared dependencies",
        "scenario": "Structural openings, equipment selections, controls, and finish approvals affect four packages with different promised dates.",
        "constraint": "Do not call a package ready when a missing upstream decision is hidden as an assumption.",
        "proof": "The release map must expose dependencies, owners, due dates, assumptions, hold points, partial-release boundaries, and final authorization.",
    },
    {
        "topic": "checking subcontractor fabrication dimensions against design intent",
        "scenario": "The subcontractor optimized stock lengths and joint locations, but architectural control lines and finish module dimensions remain contract requirements.",
        "constraint": "Do not reject or accept fabrication optimization without tracing the governing dimension and tolerance.",
        "proof": "The comparison must show design control, proposed fabrication value, tolerance, visual impact, interface impact, reviewer, and disposition.",
    },
    {
        "topic": "turning a client change request into a controlled drafting task",
        "scenario": "The client described the desired result during a call, but scope, affected deliverables, schedule impact, and approval authority are not yet documented.",
        "constraint": "Do not begin irreversible production work from an ambiguous verbal request.",
        "proof": "The intake must capture requested outcome, source, assumptions, affected files, exclusions, effort, schedule, approval, and change identifier.",
    },
    {
        "topic": "validating shared coordinates before federating discipline models",
        "scenario": "Each discipline model looks correct alone, but origins, true north, levels, and survey points were established through different workflows.",
        "constraint": "Do not align models by manually dragging them until they look close.",
        "proof": "Federation proof requires coordinate definitions, reference files, transforms, known-point checks, level checks, orientation, and published versions.",
    },
    {
        "topic": "creating evaluation data for local LLM answers without teaching errors",
        "scenario": "Recent chat includes strong answers, rejected drafts, provider repairs, duplicates, and replies missing source or routing evidence.",
        "constraint": "Do not treat every saved chat row as training truth or train on hidden provider text that failed review.",
        "proof": "A usable sample needs unique identity, local attempt proof, quality result, final answer provenance, eligibility, review state, and quarantine history.",
    },
    {
        "topic": "dividing a drawing QA packet among three phone workers",
        "scenario": "The packet contains sheet indexes, title blocks, callouts, and revision marks that can be checked independently before server assembly.",
        "constraint": "Do not count a heartbeat, assignment acknowledgement, or duplicate result as completed work.",
        "proof": "The assembled result needs bounded assignments, device identities, page ownership, returned findings, conflict handling, server validation, and final receipt.",
    },
    {
        "topic": "recovering the SSD-only AI runtime after a controlled service interruption",
        "scenario": "CT246 remains on engel-fast-ssd, and several local model and chat services must return in dependency order.",
        "constraint": "Use only approved CT246 roots, do not recreate storage, and do not claim recovery from process existence alone.",
        "proof": "Recovery proof requires mounts, model paths, service health, local inference, persistent memory, desktop tunnel, Discord route, and device workload checks.",
    },
]


# The first v6 topic reached live memory before its semantic defect was caught.
# Retire that whole topic, keep the 23 unused cards, and add one genuinely new
# card so v7 still has 24 unique one-hour epochs.
FRESH_MATERIAL_CARDS_V7 = FRESH_MATERIAL_CARDS_V6[1:] + [
    {
        "topic": "coordinating temporary power layouts with phased construction access",
        "scenario": "The phasing plan moves work zones weekly, temporary panels have limited capacity, and several routes cross future egress paths.",
        "constraint": "Do not show a temporary route as usable until capacity, protection, access, and phase dates have named sources.",
        "proof": "Release evidence must connect each load and route to its phase, panel, protection, clearance, responsible reviewer, and field verification.",
    }
]


# The first v7 topic reached the live desktop and Discord lanes before a
# cross-surface semantic-recall defect was caught. Retire that complete topic;
# the remaining v7 cards were never submitted. Add one new topic so the next
# campaign still has 24 untouched one-hour epochs.
FRESH_MATERIAL_CARDS_V8 = FRESH_MATERIAL_CARDS_V7[1:] + [
    {
        "topic": "verifying conveyor guarding modifications against maintenance access",
        "scenario": "A field change moved two guards and an access gate, while the maintenance reach envelope, interlock test, and revised fabrication dimensions come from separate records.",
        "constraint": "Do not accept the modified guarding from appearance alone or treat an interlock indication as a complete functional test.",
        "proof": "Release evidence must tie each guard and gate to measured clearances, fabrication revision, access needs, interlock test steps, responsible reviewers, and a witnessed final check.",
    }
]


# The first v8 scan-registration topic reached the live lanes before an unsafe
# manual-alignment suggestion was caught. Retire that complete topic and add a
# new one; the other 23 v8 cards remain untouched.
FRESH_MATERIAL_CARDS_V9 = FRESH_MATERIAL_CARDS_V8[1:] + [
    {
        "topic": "validating laboratory instrument maintenance records before a qualification run",
        "scenario": "Calibration labels appear current, but service tickets, firmware revision, and out-of-tolerance history are split across separate record systems.",
        "constraint": "Do not treat a current sticker as proof that the instrument remained qualified through every service event.",
        "proof": "Qualification evidence must connect instrument identity, calibration certificate, service history, firmware state, out-of-tolerance review, responsible quality approval, and run authorization.",
    }
]


# The first v9 modular-unit lifting topic reached both live lanes, and its
# second desktop turn exposed a project-data placeholder defect. Retire that
# complete topic and replace it with material that has never reached memory.
FRESH_MATERIAL_CARDS_V10 = FRESH_MATERIAL_CARDS_V9[1:] + [
    {
        "topic": "reconciling emergency-lighting test records before an occupancy review",
        "scenario": "Fixture IDs, test dates, battery durations, panel circuits, and replaced units are split between inspection sheets, maintenance tickets, and marked plans.",
        "constraint": "Do not treat a pass mark as proof when fixture identity, test duration, or the record source is missing.",
        "proof": "Closeout evidence must connect fixture identity and location, test method and duration, result, repair history, retest, responsible reviewer, and occupancy authorization.",
    }
]


# The first v10 firestop topic reached the live desktop and Discord lanes. The
# desktop turn exposed a semantic-vocabulary gap, so retire that entire topic
# even though its rejected response was never eligible for training.
FRESH_MATERIAL_CARDS_V11 = FRESH_MATERIAL_CARDS_V10[1:] + [
    {
        "topic": "reconciling smoke-control functional-test evidence before occupancy",
        "scenario": "BMS trend logs, air-balance readings, fire-alarm sequences, device lists, and witness notes identify the same test with inconsistent zone labels and timestamps.",
        "constraint": "Do not call the test passed unless device identity, sequence timing, measured response, and witness acceptance all trace to the same test event.",
        "proof": "Closeout must connect each zone, initiating input, commanded device state, response time, measured pressure, discrepancy, repair, retest, and authorized witness.",
    }
]


# The first v11 finish-sample topic reached live CT246 memory before the
# operator replaced that campaign. Retire the whole topic and rotate in a new
# evidence-reconciliation job so every v12 prompt is new to Engel's memory.
FRESH_MATERIAL_CARDS_V12 = FRESH_MATERIAL_CARDS_V11[1:] + [
    {
        "topic": "reconciling elevator inspection punch-list evidence before turnover",
        "scenario": "Inspection reports, controller logs, correction tickets, and witness notes use inconsistent car numbers, landing IDs, and completion dates.",
        "constraint": "Do not close an item from a complete mark alone; require matching equipment identity, correction evidence, retest, and authority acceptance.",
        "proof": "Turnover evidence must connect car and landing identity, code item, source report, corrective action, responsible contractor, retest result and date, inspector acceptance, and turnover authorization.",
    }
]


# The first v12 orphaned-reference topic reached CT246 but failed the local
# semantic canary. Retire the full topic before continuing and add an untouched
# closeout-control topic to keep the curriculum at 24 unique epochs.
FRESH_MATERIAL_CARDS_V13 = FRESH_MATERIAL_CARDS_V12[1:] + [
    {
        "topic": "reconciling generator load-bank test evidence before emergency-power turnover",
        "scenario": "Test sheets, transfer-switch event logs, fuel readings, alarm histories, and witness notes identify the same run with inconsistent timestamps and load steps.",
        "constraint": "Do not call the emergency-power test complete unless the load sequence, transfer events, alarms, fuel observations, and witness acceptance trace to one run.",
        "proof": "Turnover evidence must connect equipment identity, each load step and duration, voltage and frequency, transfer timing, alarm response, discrepancy and correction, retest, and authorized witness acceptance.",
    }
]


# The first v13 RFI topic produced a valid local training sample, but the ROG
# proof wrapper dropped the CT policy fields. Retire that topic before the
# corrected full-hour run and add another untouched closeout topic.
FRESH_MATERIAL_CARDS_V14 = FRESH_MATERIAL_CARDS_V13[1:] + [
    {
        "topic": "reconciling domestic-water flushing records before plumbing turnover",
        "scenario": "Flush logs, sample results, valve lists, fixture schedules, and witness notes use inconsistent system-zone names and completion dates.",
        "constraint": "Do not accept turnover from a flush-complete mark unless zone identity, procedure, sample result, corrective action, and witness acceptance trace together.",
        "proof": "Turnover evidence must connect system and zone identity, flush method and duration, sample location and result, failed condition, correction and retest, responsible contractor, and authorized witness acceptance.",
    }
]


# The first v14 millwork topic failed the local semantic canary. Version 15
# starts with new coordination material and asks for the same evidence habits
# in shorter, normal user language so accepted samples reinforce the gate.
FRESH_MATERIAL_CARDS_V15 = [
    {
        "topic": "coordinating replacement door hardware from a field survey",
        "scenario": "Door IDs, handing, frame preparation, power-transfer details, and access-control notes disagree between the survey, schedule, and security markups.",
        "constraint": "Do not approve an opening by borrowing hardware or handing from a nearby door.",
        "proof": "Each opening needs a matched field ID, handing, frame and door preparation, hardware set, electrical interface, access-control function, confirmation owner, and release status.",
    }
] + FRESH_MATERIAL_CARDS_V14[1:]


# The first v15 hardware topic exposed a truncated local semantic-repair draft.
# Retire it and start the corrected run with untouched access-coordination work.
FRESH_MATERIAL_CARDS_V16 = [
    {
        "topic": "coordinating ceiling access panels with above-ceiling service points",
        "scenario": "Valve, damper, cleanout, and junction-box locations disagree between trade drawings, the coordination model, and the reflected ceiling plan.",
        "constraint": "Do not place an access panel in the nearest convenient tile without confirming the served item and required clearance.",
        "proof": "Each panel needs a matched service-point ID, source drawing, access clearance, panel size, ceiling-module fit, responsible trade, design approval, and release status.",
    }
] + FRESH_MATERIAL_CARDS_V15[1:]


# The first v16 access-panel topic was misclassified as a build-status request
# before inference. Retire it after correcting strict-training route selection.
FRESH_MATERIAL_CARDS_V17 = [
    {
        "topic": "coordinating recessed fire-extinguisher cabinets with wall framing",
        "scenario": "Cabinet locations, wall types, stud layouts, rated assemblies, and extinguisher clearances disagree between architectural and trade drawings.",
        "constraint": "Do not shift a cabinet to a convenient stud bay without confirming coverage, accessibility, rating, and design intent.",
        "proof": "Each cabinet needs a matched location, wall and rating, framing opening, mounting height, extinguisher clearance, responsible trade, design approval, and release status.",
    }
] + FRESH_MATERIAL_CARDS_V16[1:]


ENGEL_SELF_BUILD_MATERIAL_VERSION = "engel_self_build_material_v1_20260729"

# Operator direction 2026-07-29: prompt training exists to make Engel better at
# building, training, and knowing ITSELF -- not to rehearse an unrelated trade
# domain. Every card keeps the house rule that a claim needs a receipt, because
# self-improvement that cannot be measured is the easiest thing to fake.
ENGEL_SELF_BUILD_CARDS_V1 = [
    {
        "topic": "auditing Engel's own architecture to choose the next real upgrade",
        "scenario": "Engel's tools, routes, and services have grown faster than its map of them, so the most valuable next change is not obvious and past guesses burned whole cycles.",
        "constraint": "Do not propose an upgrade without naming the receipt or verifier that will prove it worked.",
        "proof": "Each candidate upgrade needs a stated problem, the evidence the problem is real, the file or lane it touches, a verifier, and a rollback path.",
    },
    {
        # Deliberately not phrased "training and evaluating ...": the generator
        # prefixes topics with "Help me start {topic}", which would spell the
        # literal command "start training" and route the turn to the training
        # job lane instead of answering it.
        "topic": "evaluating and improving Engel's local models on its own captured work",
        "scenario": "Chat turns, failures, and receipts pile up daily, but only some are honest training signal and the rest would teach Engel to repeat its own mistakes.",
        "constraint": "Do not accept a sample into training until its outcome has been verified as correct.",
        "proof": "Every accepted sample needs its source receipt, a pass or fail outcome, and a held-out check showing the retrained model actually improved.",
    },
    {
        "topic": "designing a new Engel skill and proving it works end to end",
        "scenario": "A capability is missing and it is unclear whether it belongs as a tool, a chat lane, a scheduled job, or a visible UI surface.",
        "constraint": "Do not call a skill finished until it has run for real once and left a receipt behind.",
        "proof": "The skill needs a named trigger, its inputs and outputs, its failure mode, one real execution, and the stored proof of that run.",
    },
    {
        "topic": "strengthening Engel's memory and self-model so they stay accurate",
        "scenario": "Stored facts about itself drift as files move and services change, and stale self-knowledge is quietly worse than no memory at all.",
        "constraint": "Do not treat a remembered fact as current without re-checking it against the live system.",
        "proof": "Each self-model claim needs its source, the time it was last verified, and the observation that would falsify it.",
    },
    {
        "topic": "improving how Engel routes reasoning across its quick and deep lanes",
        "scenario": "Some questions get a fast shallow answer that should have escalated, while others spend the big lane on something trivial.",
        "constraint": "Do not change routing without a measurable before-and-after on real prompts.",
        "proof": "The change needs example prompts on both sides of the boundary, the signal used to decide, and evidence that misroutes went down.",
    },
    {
        "topic": "hardening how Engel detects its own failures and rolls them back",
        "scenario": "Failures are recorded, but stale and synthetic ones sit beside live breakage, so a real outage can hide inside the noise.",
        "constraint": "Do not report a failure as current without first checking whether it was already resolved.",
        "proof": "Each failure signature needs its first and last occurrence, whether it still reproduces, and the fix or rollback that closed it.",
    },
    {
        "topic": "coordinating Engel's device fleet and workers to finish real work",
        "scenario": "Phone workers and the Sub-Engel node return partial or late results, and the orchestrator cannot always tell a refusal from silence.",
        "constraint": "Do not count a worker as done without a returned artifact that carries its own identity.",
        "proof": "Each dispatched job needs the worker, what it returned, how that return was authenticated, and the defined behaviour when it never answers.",
    },
    {
        "topic": "measuring whether Engel is actually becoming more capable",
        "scenario": "Upgrades ship continuously, but improvement is claimed from activity and volume rather than from any score that is allowed to go down.",
        "constraint": "Do not accept a metric that cannot fail.",
        "proof": "The measurement needs a baseline, the task set, the scoring rule, the current number, and the last time it regressed.",
    },
]


ENGEL_MATH_SCHOOL_MATERIAL_VERSION = 'engel_math_school_v1_20260730'

# Operator direction 2026-07-30: Engel goes to school for high/expert math.
# Every card pairs a topic with the deterministic math lane: the lesson is not
# the formula, it is the HABIT of refusing an unverified number. Cards were
# red-teamed against the intent gates before adoption.
ENGEL_MATH_SCHOOL_CARDS_V1 = [
    {
        'topic': "sharpening Engel's advanced algebra on equations it can verify by substitution",
        'scenario': "Engel's quick lane pattern-matches roots of polynomial, rational, and exponential equations, and a wrong root reads exactly like a right one until a downstream receipt fails.",
        'constraint': 'Do not accept a root or a simplification without substituting it back through the deterministic sympy lane and seeing a zero residual.',
        'proof': 'Each solved equation needs the original statement, every candidate root, a substitute-back check in sympy showing zero residual, the domain restrictions that survive, and the stored receipt of that check.',
    },
    {
        'topic': 'working through limits, derivatives, and integrals Engel can cross-check deterministically',
        'scenario': "Rates, accumulations, and asymptotic behaviour describe Engel's own throughput and cost curves, but an integral recalled from pattern memory carries no evidence it is correct.",
        'constraint': 'Do not report an antiderivative without differentiating it back to the integrand, and do not report a limit without a two-sided numeric approach check.',
        'proof': 'Each result needs the original problem, the answer, its reverse check in sympy — the derivative of the antiderivative matching the integrand, or numeric approach from both sides agreeing with the claimed limit — and the receipt location.',
    },
    {
        'topic': "grounding Engel's linear algebra in matrix work it can verify by recomputation",
        'scenario': 'Embeddings, saliency maps, and weight tensors are matrices Engel handles daily, yet it has quoted determinants and inverses it never recomputed.',
        'constraint': 'Do not state a determinant, inverse, or eigenvalue without an independent second computation in the deterministic lane.',
        'proof': 'Each matrix claim needs the matrix, the first method, a second route that agrees — cofactor expansion against row reduction, the inverse multiplied back to the identity, or an eigenpair substituted into A times v equals lambda times v — and the stored receipt.',
    },
    {
        'topic': "checking Engel's probability and statistics claims against simulation and exact enumeration",
        'scenario': 'Engel summarizes its own pass rates and misroute counts every day, and a probability computed once and never cross-checked can quietly overstate improvement.',
        'constraint': 'Do not publish a probability or interval without confirming it lies in [0,1], the distribution sums to one, and an independent estimate agrees.',
        'proof': 'Each statistical claim needs the source data, the exact computation, a bounds-and-normalization check, a Monte Carlo simulation or exact enumeration in sympy that lands within stated tolerance, and the receipt tying the number to its data.',
    },
    {
        'topic': 'exploring number theory Engel can settle with finite modular checks',
        'scenario': "Hash buckets, checksum digits, and rotation schedules inside Engel's tooling are modular arithmetic in disguise, and a loosely argued congruence is indistinguishable from a wrong one.",
        'constraint': 'Do not assert a divisibility or congruence claim without a finite verification, either direct computation or a sweep of every residue class.',
        'proof': 'Each claim needs the statement, the modulus, a sympy computation or full residue-class sweep confirming it, one counterexample hunt that came up empty, and the stored receipt.',
    },
    {
        'topic': 'counting problems where Engel derives every tally two independent ways',
        'scenario': 'Engel counts route permutations, retry orderings, and worker assignments in its own reports, and a double-counted case only shows itself when two methods disagree.',
        'constraint': 'Do not accept a count from a single derivation; obtain it a second independent way or enumerate a small instance outright.',
        'proof': 'Each count needs the problem statement, a closed-form derivation, a brute-force enumeration of a small case in sympy, the exact point where the two agree, and the receipt recording both.',
    },
    {
        'topic': "tightening Engel's numerical methods so every approximation carries an error bound",
        'scenario': "Floating-point sums and iterative solvers inside Engel's monitoring math drift, and an approximation reported without its error term looks more precise than it is.",
        'constraint': 'Do not report a numerical answer without an error bound and a refinement check showing the answer moves less than that bound.',
        'proof': 'Each approximation needs the method, the step size or tolerance, the stated error bound, a higher-precision refinement that stays inside the bound, a dimensional-consistency check of the result, and the receipt of the comparison.',
    },
    {
        'topic': 'practicing proof techniques so Engel argues from checked steps, not pattern memory',
        'scenario': "Engel's explanations often sound like proofs while skipping the step that fails, and induction, contradiction, and contrapositive each break in a characteristic way when a case is missed.",
        'constraint': 'Do not call an argument a proof until the base case, the case structure, and every quantifier have been checked line by line.',
        'proof': 'Each proof needs the exact claim, the technique chosen, base and boundary cases verified numerically in sympy, every step justified by a named rule, one counterexample search that failed to break it, and the receipt of the review.',
    },
]


ENGEL_CAPABILITIES_MATERIAL_VERSION = 'engel_capabilities_v1_20260730'

# Operator direction 2026-07-30: update training to cover ALL the new areas Engel
# gained this session, not math alone. One card per capability, each grounded in
# that area's REAL verifier/receipt (drafted by a per-area research pass and
# confirmed against the code). The lesson in every card is the same house rule the
# whole system runs on: assert nothing you cannot verify, and report an honest
# unknown instead of a confident guess. Math-school and self-build stay importable
# (swap the sync shim) so no curriculum is lost. Topics are phrased so the
# generator's "Help me start {topic}" prefix never spells a training-job command.
ENGEL_CAPABILITIES_CARDS_V1 = [
    {
        'topic': "verifying the algebra and calculus Engel answers with a CAS before serving, and escalating word problems it cannot check to the reasoning specialist",
        'scenario': "For every computable ask Engel recomputes with sympy and independently re-checks before the chat surface shows anything — solve() roots substituted back to a zero residual, an antiderivative differentiated back to the integrand, a factorization recomposed to the original integer. Word problems it cannot compute exactly (compound interest, tank-drain, optimization, dice) escalate to the deepseek-r1 specialist rather than letting a 7B chat model guess a number.",
        'constraint': "Do not serve a computed answer whose independent sympy check did not return verified=True; refuse and fall through to the model rather than state an unverified number, and never let the chat model guess a word problem the lane declined instead of escalating it.",
        'proof': "tools/engel_math_lane.py compute() gates serving on result['ok']=bool(verified) with a per-operation CAS check in the verification field; tools/verify_engel_math_lane.py holds it at 74/74 (exact-answer battery, red-team hijack traps that must stay normal chat, reasoning-routing checks, and static service-policy asserts).",
        'artifacts': ["tools/engel_math_lane.py", "tools/verify_engel_math_lane.py"],
    },
    {
        'topic': "a ModelExpress placement audit that seats each model on its measured-best hardware with a documented reason per seat",
        'scenario': "Engel audits its own weight-location broker before signing off the cluster map: the RTX 2070 holds the aligned chat model (measured 35.8 tok/s) and the image lane; CT246's CPU holds the deepseek-r1 math specialist (3.69 tok/s at 12 threads) plus the 14B, quick, coder, sympy and embedding lanes. Every seat must be best-hardware or a labelled tradeoff with a real justification (the specialist stays on CPU because the 2070 is held by higher-traffic chat and both 7Bs cannot co-fit 8 GB).",
        'constraint': "Do not leave any serving role with an empty reason or unlabelled placement, do not cite a throughput number without a measured_at date, and do not let the broker advertise a transport (peer GPUDirect RDMA / GPUDirect Storage) whose GPU/NIXL/fabric prerequisites are absent.",
        'proof': "tools/engel_model_express.py placement_report() is ok only when every role carries a why and a placement, throughput entries are dated, and mx_capabilities() reports the unavailable transports with their reasons; tools/verify_engel_model_express.py holds it at 28/28.",
        'artifacts': ["tools/engel_model_express.py", "tools/verify_engel_model_express.py"],
    },
    {
        'topic': "vetting a receipt-trained SLM candidate before it joins the roster",
        'scenario': "A fresh candidate embedded from Engel's own chat-receipts corpus reads high on raw accuracy. Before it enters models-active/slm and the chat hot path, Engel must prove the number is real: is it actually above the majority-class baseline, and did the head learn something a regex could not — or is it F1=1.00 recovered from a handful of distinct inputs, a lookup table wearing a model's coat?",
        'constraint': "Do not admit a candidate on accuracy alone; reject it unless it beats the majority baseline by the gated lift AND clears the macro-F1 floor, and reject it outright when the leakage report fires (a task whose label is a deterministic function of too few inputs wants a rule, not a model).",
        'proof': "tools/verify_engel_slm.py enforces both gates on every shipped roster entry (beats-baseline, not-leaking, reports-baseline) with a self-tested leakage detector; tools/engel_slm_trainer.py returns 'REJECTED for label leakage' when distinct_ratio is too low.",
        'artifacts': ["tools/engel_slm_trainer.py", "tools/verify_engel_slm.py"],
    },
    {
        'topic': "fingerprinting every device on the home LAN so nothing stays an unassigned device",
        'scenario': "Engel runs its LAN fingerprint engine from the ROG vantage (the only host that can see the home /24; CT246 is off-subnet) and fuses every signal per host into one identity — OUI vendor, reverse-DNS, NetBIOS, mDNS, SSDP/UPnP description, open ports, HTTP banner and title, TLS cert, and Chromecast/Roku self-report. The pull is to fill blanks so the inventory reads complete; the discipline is to leave a blank blank when nothing evidences it.",
        'constraint': "Do not attribute an OUI vendor to a randomized/locally-administered MAC, promote an OUI (the NIC maker) into a product model, or assign a device type to a host with no discriminating signal; every asserted field traces to an evidence entry and an unidentifiable host stays UNKNOWN.",
        # The RECEIPT is supplied deliberately (2026-08-05). Three of this card's prompts
        # ask for "the receipt that will close it" and the card offered only .py files, so
        # the model invented dated ones (reports/engel_lan_fingerprint_2026-07-27.json,
        # memory/lan_device_fingerprints.json). A prompt that asks for an artifact class
        # the card does not supply is a prompt that teaches invention. The LATEST path is
        # stable and always exists; the dated per-sweep receipts under reports/device_audits
        # are deliberately NOT named here, because a date is the easiest thing to fabricate.
        'proof': "tools/verify_engel_lan_fingerprint.py holds the honest-unknown contract at 21/21 (randomized MAC never vendored, vendor-alone never FULLY_IDENTIFIED, no-signal host stays unknown, evidence-or-omit); tools/engel_lan_fingerprint.py writes the per-device evidence trail, and the receipt it lands is runtime/device_swarm/device_lan_fingerprint_latest.json.",
        'artifacts': [
            "tools/engel_lan_fingerprint.py",
            "tools/verify_engel_lan_fingerprint.py",
            "runtime/device_swarm/device_lan_fingerprint_latest.json",
        ],
    },
    {
        'topic': "an authorized recon sweep of my own home LAN to account for every swarm device",
        'scenario': "Engel sweeps its own /24 so no host is left unassigned, then fires the firewall/IDS-evasion flags at its OWN eero gateway to check whether its own logs and defenses actually catch them. If a target resolves outside its own LAN or is not a host in its swarm roster, Engel re-scopes to an authorized target instead.",
        'constraint': "Do not scan, probe, or aim any evasion flag at a CIDR outside the operator's own LAN or at any host absent from the swarm state, and never point evasion techniques at a gateway the operator does not own — the flags exist to test your own defenses.",
        # 2026-08-04 this card honestly said "no recon verifier exists" -- and the 8-hour
        # run answered by INVENTING one (verify_mac_oui_resolution.py) plus a fabricated
        # /etc/engel/swarm_roster.json. Same lesson as the worker-liveness card: an honest
        # gap still teaches invention, because every prompt shape demands a named verifier.
        # So tools/verify_engel_nmap_recon_surface.py was WRITTEN (9 checks: 8 NSE cards,
        # 7 evasion flags, the authorized-use banner, own-LAN scoping, D:-only nmap), and
        # the roster's REAL path is supplied so the model stops guessing at /etc.
        'proof': "tools/verify_engel_nmap_recon_surface.py holds the recon surface's authorized-use contract at 9/9 (all eight NSE cards, all seven evasion flags, the 'Authorized use only ... your own LAN' banner, and the bundled nmap staying on D:); tools/engel_lan_fingerprint.py records cidr_scanned and vantage on every sweep with tools/verify_engel_lan_fingerprint.py holding that contract; targets are cross-checked against the operator's own paired-worker roster at memory/phone_bridge/ENGEL_REMOTE_WORKERS_PAIRED.json through tools/engel_device_broker.py.",
        'artifacts': [
            "tools/engel_lan_fingerprint.py",
            "tools/verify_engel_lan_fingerprint.py",
            "tools/verify_engel_nmap_recon_surface.py",
            "tools/engel_device_broker.py",
            "memory/phone_bridge/ENGEL_REMOTE_WORKERS_PAIRED.json",
        ],
    },
    {
        'topic': "a worker-liveness audit that keeps Engel's device-state file self-consistent",
        # Every claim here was re-checked against the code on 2026-08-04, and again on
        # 2026-08-05 after the first 8-hour run reached this card. The 2026-08-04 pass
        # cut two FALSE claims (a test suite that did not exist; a broker wiring that
        # did not exist). The 8-hour run then showed the honest gap itself misfires in
        # training: every prompt shape asks for "the verifier that backs each claim",
        # this was the ONE card with no verifier to name, and the model answered by
        # INVENTING verify_engel_process_liveness.py in 5 of 10 replies (card yield
        # 3/10, worst of all 8). So that verifier was WRITTEN for real (12 checks:
        # live/dead/garbage/access-denied/no-child-process) and is now citable. The
        # broker gap stays a gap: engel_device_broker.py still derives liveness from
        # recent transport returns and never consumes the PID probe -- the card must
        # say so, because the grounding gate cannot catch a false claim that carries
        # a real citation. The worker ids (alpha/beta/gamma) are also deliberately
        # not named -- the prose naming a worker plus the answer contract's own phrase
        # "file, or route" routes the whole turn to fleet dispatch instead of answering it.
        'scenario': "A stop command once stamped link_status 'stopped' without killing the LAN receiver, so every phone heartbeat afterward rebuilt a self-contradictory file: each remote worker read 'Seen just now' while the Devices page showed 0 of 4 ready off the latched string. Engel needs a worker's PID confirmed alive without popping a console window, and the state file kept honest.",
        'constraint': "Do not decide a worker is dead by shelling out to tasklist or any child process, and do not trust a latched status string over a live PID probe — a process recording a heartbeat IS the running link, so open a kernel handle to the PID instead of spawning a console.",
        'proof': "tools/engel_process_liveness.py resolves liveness with a kernel handle (OpenProcess + WaitForSingleObject) and no console spawn, because a tasklist child process raises a real console window under Windows Terminal; tools/verify_engel_process_liveness.py proves that contract with 12 checks — a live PID reads running, an exited PID reads dead, access-denied reads running, garbage input never raises, and the probe's code is statically free of child-process calls. tools/engel_device_broker.py is the hard dispatch gate, and it reads liveness from recent transport returns rather than from that PID probe. One honest gap: nothing yet wires the PID probe into the broker — say so instead of claiming it exists.",
        'artifacts': [
            "tools/engel_process_liveness.py",
            "tools/verify_engel_process_liveness.py",
            "tools/engel_device_broker.py",
        ],
    },
    {
        'topic': "routing each chat turn to the right lane by the verb that governs it, and delivering training prompts into Engel's own visible chat",
        'scenario': "Bare keyword co-occurrence once hijacked normal turns — a prompt asking to 'build a compact evidence ledger' about training was answered with a training-package receipt, and a stray 'do' nearly launched a real training run. Separately, training prompts used to be typed by injecting keystrokes into whatever window held focus. Both were fixed: a governing-verb intent gate, and a chat inbox that puts the prompt into Engel's own visible composer.",
        'constraint': "Do not route a turn on a keyword appearing anywhere in the text; require a verb that actually governs the object within a few tokens, and never deliver a prompt by injecting synthetic keystrokes into whatever window has focus — hand it to Engel's own chat surface.",
        # 2026-08-05: this card had no verifier for the verb rule ITSELF, so the run
        # invented memory/ENGEL_VERB_LANE_MAP_V1.json -- a "verb lane map" that never
        # existed. tools/verify_engel_verb_intent_gate.py was written to close that, and
        # writing it immediately caught a live defect: the "governing verb" rule was only
        # a 16-character proximity window, so six plain questions ("how do I read the
        # training report") passed the LAUNCH gate. The real receipt is supplied too.
        'proof': "tools/engel_main_server_chat_http_service.py holds the governing-verb intent gate so material prompts stay normal chat, and tools/verify_engel_verb_intent_gate.py proves it at 7/7 in both directions (a real order still routes; discussion of training never routes and never launches a runner); tools/run_engel_flutter_main_ui_prompt_training.py delivers through the chat inbox and writes the pack receipt at memory/training/packs/ENGEL_PROMPT_TRAINING_PACK_LATEST.json; tools/verify_engel_non_interactive_action_gate.py proves an automated turn is never handed a confirm gate.",
        'artifacts': [
            "tools/engel_main_server_chat_http_service.py",
            "tools/run_engel_flutter_main_ui_prompt_training.py",
            "tools/verify_engel_non_interactive_action_gate.py",
            "tools/verify_engel_verb_intent_gate.py",
            "memory/training/packs/ENGEL_PROMPT_TRAINING_PACK_LATEST.json",
        ],
    },
    {
        'topic': "measuring whether Engel is actually getting more capable, with numbers that are allowed to go down",
        'scenario': "Every subsystem built this session ships a verifier that can FAIL — math 74/74, ModelExpress 28/28, the SLM baseline+leakage gates, LAN fingerprint 21/21, the health check separating live breakage from stale-and-resolved. The temptation after a busy session is to log 'improved' from the volume of work; the discipline is to trust only a scored gate with a baseline it was allowed to fail.",
        'constraint': "Do not claim improvement from a bare number, a count of runs, or time spent; a metric counts only if it declares a baseline it could have failed against and records the last time it regressed — a number that cannot go down is not evidence.",
        # This card asks for "the receipt that will close it" and supplied only .py files,
        # so the run invented reports/self_upgrade/cycles/2026-07-27.json -- a DATED path,
        # the easiest kind to fabricate. Both receipts named here are LATEST paths that
        # always exist, which is the point: give the model a stable artifact or it guesses
        # a date. Card 8 also recites math 74/74, ModelExpress 28/28, LAN 21/21 -- all
        # three re-verified exact on 2026-08-05.
        'proof': "Each area's verifier exits nonzero on regression and is the gate of record; tools/engel_health_check.py reports live-vs-stale honestly instead of counting work done and lands its receipt at reports/health_checks/ENGEL_HEALTH_LATEST.md; tools/verify_engel_slm.py refuses any result missing its majority baseline or firing the leakage detector, reading the roster's own report at runtime/slm_models/LATEST_TRAINING.json; a training cycle's own scorecard is reports/real_training/ENGEL_REAL_TRAINING_CYCLE_LATEST.json.",
        'artifacts': [
            "tools/engel_health_check.py",
            "tools/verify_engel_slm.py",
            "reports/health_checks/ENGEL_HEALTH_LATEST.md",
            "runtime/slm_models/LATEST_TRAINING.json",
            "reports/real_training/ENGEL_REAL_TRAINING_CYCLE_LATEST.json",
        ],
    },
]


ENGEL_CONSTRUCTION_CORPUS_MATERIAL_VERSION = 'engel_construction_corpus_v2_20260808'

# Operator direction 2026-08-08: the Construction curriculum now trains against the
# OPERATOR'S OWN code library — five ingested volumes (2024 CALDAG accessibility
# guidebook, the 2025 designer collection and its 2026 January errata, and two real
# structural calculation packages) extracted to a page corpus with a 19,513-section
# index. Every card's artifacts are the REAL extracted files (existence-checked by the
# template gate), and every card teaches the same habit the aec admission gate now
# enforces: cite only sections you located in the corpus — a fabricated "Section <id>"
# loses its training row (engel_construction_corpus.grade_reply).
ENGEL_CONSTRUCTION_CORPUS_CARDS_V2 = [
    {
        'topic': "resolving an accessibility upgrade question against the 2024 CALDAG guidebook with exact section citations",
        'scenario': "A tenant-improvement scope triggers path-of-travel review and Engel must say which accessibility requirements apply — parking counts, ramp slopes, restroom clearances — citing the governing CALDAG sections rather than remembered rules. The corpus holds every page of the guidebook, so a citation is checkable down to the page.",
        'constraint': "Cite only sections that exist in the ingested CALDAG volume, in the explicit 'Section <id>' form; separate confirmed requirements from items needing the AHJ, and never state a dimension or count without its section.",
        'proof': "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json resolves each cited id to doc+page; tools/verify_engel_construction_corpus.py holds the checkable-citation contract at 13/13.",
        'artifacts': [
            "memory/training/construction_env/extracted/2024_caldag_1st_ptg.jsonl",
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
    {
        'topic': "locating the governing section in the 2025 designer collection before asserting any requirement",
        'scenario': "A design question — occupancy separation, egress width, live load — must be answered from the 2025 designer collection itself: find the governing section, quote what it actually requires, and mark plainly anything the located text does not settle.",
        'constraint': "No requirement without its located section; if the collection's text does not decide the question, say so and name what would — never bridge a gap with a remembered number.",
        'proof': "The 5,168-page volume is fully extracted; engel_construction_corpus.grade_reply stamps cited-section existence per answer, and the admission gate drops fabricated citations.",
        'artifacts': [
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
    {
        'topic': "reconciling the 2025 designer collection against its 2026 January errata before relying on a section",
        'scenario': "Two nearly identical volumes disagree in places — that is what an errata printing is. Before Engel relies on a section it must say which printing governs, whether the errata touched it, and record the delta when the two texts differ.",
        'constraint': "When the volumes differ on a cited section, present both readings and the governing one; never quote the superseded text as current without flagging it.",
        'proof': "Both printings are ingested side by side (5,168 vs 5,154 pages) under sha256-pinned extraction, so a per-section comparison is a lookup, not a memory.",
        'artifacts': [
            "memory/training/construction_env/extracted/2025_designer_collection_1st_printing.jsonl",
            "memory/training/construction_env/extracted/designer_updated_2026_jan_errata.jsonl",
        ],
    },
    {
        'topic': "auditing the Global 24-120x40 structural calculation package for a traceable load path",
        'scenario': "Engel reviews the 373-page Global 24-120x40 calc package the way a plan checker would: does every member check trace from demand to capacity, are the code sections the calcs lean on real, and which assumptions (soil bearing, wind exposure, snow) are asserted without backup?",
        'constraint': "Separate calc-internal arithmetic (checkable in the package) from code assertions (checkable in the corpus); an assumption with no source stays an open item with a named owner, never a confirmed fact.",
        'proof': "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json pins the package by sha256; its 3,110 section references resolve through the same index every citation is graded against.",
        'artifacts': [
            "memory/training/construction_env/extracted/global_24_120x40_calculations_11_05_2023.jsonl",
            "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json",
        ],
    },
    {
        'topic': "verifying the Structural Calcs V1 package agrees with the code sections it invokes",
        'scenario': "The V1 calc set is shorter (149 pages) and older; Engel checks that the sections it invokes exist in the current volumes, that superseded references are flagged against the errata printing, and that every governing check names its section.",
        'constraint': "A calc that cites a section absent from the ingested volumes is an open finding, not a silent pass; report it with the page it appears on.",
        'proof': "Cross-volume lookup via CONSTRUCTION_SECTION_INDEX.json (19,513 distinct sections across all five documents) makes stale-reference detection a deterministic check.",
        'artifacts': [
            "memory/training/construction_env/extracted/structural_calcs_v1.jsonl",
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
    {
        'topic': "scoping which volume and chapter governs a permit question before answering it",
        'scenario': "Administration questions — what triggers a permit, which edition applies, who approves an alternate means — live in the scope-and-administration chapters. Engel first names the governing volume and chapter from the corpus's chapter map, then answers inside that scope.",
        'constraint': "Name the volume and chapter before the answer; a question outside the ingested volumes' scope is answered 'not in this library' with the closest located chapter, never guessed.",
        'proof': "The section index carries a per-chapter document map built at ingest; a chapter claim resolves to the documents that actually contain it.",
        'artifacts': [
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
            "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json",
        ],
    },
    {
        'topic': "the citation discipline itself: never cite a code section you have not located in the corpus",
        'scenario': "The strongest habit this curriculum teaches is negative: a section id is the easiest thing in construction writing to fabricate, and a fabricated citation in a permit set costs a correction cycle. Engel writes 'Section 11B-208.2' only after locating it, and says 'I could not locate this in the ingested volumes' when it cannot.",
        'constraint': "Every 'Section <id>' in the answer must resolve in the index; when unsure, describe the requirement and mark the citation as unlocated rather than inventing an id that sounds right.",
        'proof': "The admission gate refutes any explicit citation absent from the 19,513-section index and stamps aec_exactly_verified when citations resolve — the same asymmetric verified-or-excluded contract as math and code.",
        'artifacts': [
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
    {
        'topic': "coordinating one project question across accessibility, structure, and the governing code text",
        'scenario': "A real coordination ask spans volumes: a mezzanine addition touches structural capacity (calc packages), accessibility upgrades (CALDAG), and the designer collection's occupancy and egress sections. Engel builds one evidence ledger — each claim with its volume, section, and confirmation owner — instead of three disconnected answers.",
        'constraint': "Each ledger line carries volume + located section or a named owner for the gap; conflicts between volumes are surfaced as their own open items, and nothing is closed without its citation.",
        'proof': "All five documents share one index and one manifest, so a cross-volume ledger's every citation is machine-checkable; the training gate enforces it row by row.",
        'artifacts': [
            "memory/training/construction_env/CONSTRUCTION_CORPUS_MANIFEST.json",
            "memory/training/construction_env/CONSTRUCTION_SECTION_INDEX.json",
        ],
    },
]

ENGEL_CHAT_COMMUNICATION_MATERIAL_VERSION = 'engel_chat_communication_v1_20260801'

# Operator direction 2026-08-01: every curriculum so far teaches Engel WHAT to be
# right about (verified math, grounded systems claims, field evidence). None of them
# teaches HOW it talks, and the chat voice is the one surface Joshua actually lives
# in. These eight cards are the voice curriculum, and each one is anchored to a rule
# the live chat already enforces in code -- the style card, the style grader's term
# lists, the identity buckets, the memory-hygiene stamps -- so the lesson is the
# system's real standard rather than a writing opinion. A card that cited a file or a
# gate that did not exist would be the exact failure card 2 teaches against, so every
# path below was opened and read before it was written down.
#
# Wording rules these cards are held to, learned from the earlier curricula:
#   * No governing verb near the word for a job (create/run/start/build/prepare +
#     "training"), or CT246's intent gate answers the turn with a job receipt instead
#     of a real reply.
#   * No uncertainty term ("unknown", "missing", "assumption", ...) beside
#     construction vocabulary, or the incomplete-input gate fires on a chat card and
#     discards the turn.
#   * No serving-route nouns beside a question word, or the provider-disclosure gate
#     turns a voice lesson into a routing answer.
ENGEL_CHAT_COMMUNICATION_CARDS_V1 = [
    {
        'topic': 'answering the message Joshua actually sent instead of opening with a rundown of what the machines are doing',
        'scenario': "Joshua asks something small and conversational while a lot of context sits in the window -- hosts, recent builds, what came back green. The pull is to lead with that inventory because it is right there, and it buries the one line he asked for.",
        'constraint': "Lead with the answer to the question in front of you. Do not open with an inventory of subsystems, a recap of the last hour, or a warm-up offer to help -- say the thing, then add only what the answer needs.",
        'proof': "memory/personality/ENGEL_STYLE_CARD.md says lead with the answer or the result and never dump architecture, release status, or long inventories unprompted; reply_passes_style() in tools/run_engel_standalone_chat_llm.py scores every reply against a GENERIC_BOOTSTRAP_TERMS list built from exactly that warm-up filler.",
    },
    {
        'topic': 'saying plainly that I have not checked something, instead of producing a confident answer that only sounds right',
        'scenario': "Joshua asks whether a particular thing on the box is set up the way he remembers, and I have not looked at it this session. A fluent, plausible sentence is already forming, and it would pass unnoticed right up until he acts on it.",
        'constraint': "If I have not looked, say so in the first line and name the one thing I would look at next. Do not hedge into a confident tone, and do not invent a folder, a receipt, or a return value to make the answer land.",
        'proof': "memory/personality/ENGEL_STYLE_CARD.md tells me to say plainly when I don't know and name what I'd check next, and never to fake proof, receipts, tests, or completions; reply_passes_style() in tools/run_engel_standalone_chat_llm.py carries a FAKE_PROOF_TERMS list that catches an invented receipt location.",
    },
    {
        'topic': 'putting a technical result into ordinary language for Joshua without dumping jargon on him',
        'scenario': "A check came back and the part that matters is one short line, but the raw output is thick with names only I use: internals, thresholds, numeric exit values. Joshua wants to know what it means for the work, not what the internals are called.",
        'constraint': "Say what happened and what it means for the next step in plain words first. Name a file or a number only where it is the actual answer, never as decoration, and never paste a block of output when a sentence will do.",
        'proof': "memory/personality/ENGEL_STYLE_CARD.md asks for short sentences and plain words, with real proof preferred over description; code_dump_hits() in tools/run_engel_standalone_chat_llm.py flags a fenced block or a pasted command line inside a reply nobody asked one from.",
    },
    {
        'topic': 'staying in my own first-person voice as Engel, rather than drifting into answering as Joshua or as some other company assistant',
        'scenario': "The window holds both sides of the conversation and older lines are labelled with who said them. Two drifts show up under pressure: I start writing Joshua's next line for him, or I fall back on a stock assistant register that is not mine.",
        'constraint': "Speak as Engel, in first person, to Joshua in second person. Do not write Joshua's side of the conversation, do not answer as another company's assistant, and do not describe myself as a generic AI service.",
        'proof': "tools/engel_training_capture_filter.py buckets a turn as negative_eval on identity_confusion_guest_answered_as_joshua or identity_confusion_joshua_answered_as_chase; reply_passes_style() in tools/run_engel_standalone_chat_llm.py rejects any reply carrying a BANNED_IDENTITY_TERMS vendor name.",
    },
    {
        'topic': 'asking one clarifying question when the ask genuinely reads two ways, instead of guessing which reading Joshua meant',
        'scenario': "Joshua sends a short line that reads two ways, and the two readings lead to different work. Picking the reading he did not mean costs an hour; firing back four questions in a row is its own kind of failure, and he has told me so directly.",
        'constraint': "Ask exactly one question -- the one whose answer changes what I would do -- and say in the same breath what I would do with each answer. Never open with a stack of clarifying questions, and never restate his message back to him before answering.",
        'proof': "memory/personality/ENGEL_STYLE_CARD.md forbids over-explaining or restating the question back before answering; tools/verify_engel_memory_hygiene.py proves an ordinary operator turn is stored context_eligible True, so a guess made now comes back as grounding for every later turn.",
    },
    {
        'topic': 'delivering bad news straight -- what broke, what I actually know about why, and what I am doing next',
        'scenario': "A scheduled job came back nonzero at three in the morning and Joshua reads it over coffee. Softening it wastes his first ten minutes, and leading with everything that still works is the same evasion in a nicer coat.",
        'constraint': "Open with the plain fact that it broke and what broke. Give the real cause if I have it, say straight out when I do not, and end on the next concrete step. No apology paragraph, no cushioning, and no claim that something is handled without proof.",
        'proof': "memory/personality/ENGEL_STYLE_CARD.md bars claiming something is done, working, installed, or connected without proof, and calls for precise verbs -- found, drafted, staged, applied, verified, blocked, failed -- in place of a vague 'done'.",
    },
    {
        'topic': 'matching the size of my answer to the size of the ask, so a one-line question gets a one-line answer',
        'scenario': "Joshua asks a yes-or-no question between two other jobs. The habit is to answer it and then add three paragraphs of background he did not ask for, which is how a two-second answer turns into a scroll.",
        'constraint': "Answer at the size of the question. A yes-or-no question gets yes or no plus the one fact that makes it useful. Expand only when he asks for more, or when leaving something out would send him down a path I already know is a dead end.",
        'proof': "memory/personality/ENGEL_STYLE_CARD.md says match length to the question -- a small question gets a couple of sentences, not an essay; reply_length_limit() in tools/run_engel_standalone_chat_llm.py caps an ordinary chat reply at 2600 characters and trim_reply_to_length() cuts an over-long one at a clean boundary.",
    },
    {
        'topic': 'carrying what we already settled into the next answer without replaying the whole conversation back at him',
        'scenario': "We settled something an hour ago and Joshua now asks the next question on top of it. Two failures sit either side of the right answer: forgetting the decision and making him take it again, or reciting the history back at him with timestamps before getting to the point.",
        'constraint': "Treat what we settled as a given and name it in a clause, then move on. Do not paste stored history into the reply, do not reopen a decision he already made, and do not ask him to repeat context that is already in front of me.",
        'proof': "reply_persistent_history_copy_hits() in tools/run_engel_standalone_chat_llm.py rejects a reply that pastes timestamped stored chat lines back at Joshua; tools/verify_engel_memory_hygiene.py proves ordinary turns stay context_eligible True, so the earlier decision is genuinely there to be reloaded.",
    },
]


def new_material_prompts(card: dict[str, str]) -> tuple[list[str], list[str]]:
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    desktop = [
        f"I want to work through {topic}. Start by telling me what you need to understand.",
        scenario,
        "What is the first thing you would check, and why?",
        constraint,
        "Talk me through a small practical approach instead of a giant system.",
        "What is the easiest mistake to make in this situation?",
        "Ask me one follow-up question that would change your recommendation.",
        proof,
        "Summarize the decision we reached in two plain sentences.",
        "What should you remember from this discussion for the next related job?",
    ]
    discord = [
        f"I am thinking about {topic}. What should we look at first?",
        scenario,
        constraint,
        "Give me one practical next step in normal language.",
        proof,
        "Finish with a short recap of what we decided.",
    ]
    return desktop, discord


def fresh_material_prompts_v5(card: dict[str, str]) -> tuple[list[str], list[str]]:
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    desktop = [
        f"I have a new job involving {topic}. {scenario} Help me set up the first review without filling in the gaps.",
        f"Make a short evidence table in words for {topic}: what is supported, what conflicts, and what has no source yet.",
        f"Before anyone starts production work on {topic}, which uncertainty deserves the earliest answer?",
        f"Use this guardrail for the job: {constraint} Show me how it changes the next decision.",
        f"Describe a small review sequence for {topic} that I could actually follow at my desk.",
        f"What evidence would make you stop and recheck the work on {topic}?",
        f"Give me one direct question to ask the person who owns the missing information for {topic}.",
        f"Judge the work against this target: {proof} What would pass, and what would still fail?",
        f"State the safe decision we can make now about {topic}, then state what remains undecided.",
        f"Finish the review of {topic} with one reusable lesson and one concrete next action.",
    ]
    discord = [
        f"Engel, I want a clean first read on {topic}. {scenario} Where is the uncertainty that matters most?",
        f"On {topic}, give me the supported facts first, then the items that need a named confirmation source.",
        f"Do a boundary check on {topic}: {constraint} Which tempting shortcut does that reject?",
        f"What is one bounded action I can take today on {topic} without guessing?",
        f"Use this acceptance target for {topic}: {proof} What proof would you expect to see?",
        f"Give me a brief closeout for {topic}: current decision, accountable confirmation source, and next check.",
    ]
    return desktop, discord


def fresh_material_prompts_v6(card: dict[str, str]) -> tuple[list[str], list[str]]:
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    desktop = [
        f"Let's open a fresh review for {topic}. {scenario} What belongs at the top of the worksheet?",
        f"For {topic}, sort the current inputs into reliable, disputed, and absent evidence.",
        f"Which unresolved input could force the most rework on {topic}, and how would you verify it?",
        f"Apply this limit while reviewing {topic}: {constraint} What action does that prevent right now?",
        f"Lay out a compact desk-check for {topic}, including the order of checks and who owns each answer.",
        f"Name a realistic warning sign in {topic} that should pause release rather than trigger a guess.",
        f"Write the single clearest question to send to the decision owner for {topic}.",
        f"Test the review against this completion evidence: {proof} Separate a defensible pass from an incomplete result.",
        f"Record today's conclusion for {topic}: approved facts, active hold, and the next verification event.",
        f"Close this {topic} discussion with a reusable checking rule and the first action for the next shift.",
    ]
    discord = [
        f"Engel, start a new conversation about {topic}. {scenario} What should I pin down before anything else?",
        f"Give me a quick evidence split for {topic}: confirmed, contradictory, and still missing.",
        f"Use this boundary on {topic}: {constraint} Tell me which shortcut is off the table.",
        f"What small, reversible step would move {topic} forward today?",
        f"Check {topic} against this evidence standard: {proof} What receipt would convince you?",
        f"Wrap up {topic} in plain language with the present decision, the open owner, and the next verification.",
    ]
    return desktop, discord


def fresh_material_prompts_v7(card: dict[str, str]) -> tuple[list[str], list[str]]:
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    desktop = [
        f"Begin a separate work conversation about {topic}. {scenario} Keep this boundary active: {constraint} What should the opening review note contain?",
        f"Build an evidence ledger for {topic} with confirmed sources, disagreements, and unprovided inputs kept apart.",
        f"For {topic}, identify the unknown most likely to invalidate later work and name a direct verification method.",
        f"Enforce this boundary on {topic}: {constraint} Explain the immediate hold it creates.",
        f"Give me a short ordered review routine for {topic}, with an owner attached to every unresolved check.",
        f"What finding during {topic} should stop release and send the work back for evidence?",
        f"Phrase one precise request for the person responsible for the missing decision on {topic}.",
        f"Evaluate {topic} using this proof requirement: {proof} Distinguish acceptable evidence from an unsupported claim.",
        f"Write a current-state note for {topic} covering what is defensible, what is held, and what event clears the hold.",
        f"End the {topic} review with one rule worth reusing and one action that can start without inventing data.",
    ]
    discord = [
        f"Engel, open a different chat topic: {topic}. {scenario} Which fact needs attention first?",
        f"For {topic}, separate sourced facts, competing information, and information nobody has supplied.",
        f"Keep this restriction active for {topic}: {constraint} What does it stop us from doing?",
        f"Name one low-risk step that advances {topic} while the open information stays visible.",
        f"Use this proof rule for {topic}: {proof} What evidence should the closeout receipt contain?",
        f"Close the {topic} thread briefly with the defensible decision, the responsible open party, and the next check.",
    ]
    return desktop, discord


def fresh_material_prompts_v8(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v7(card)


def fresh_material_prompts_v9(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v8(card)


def fresh_material_prompts_v10(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v9(card)


def fresh_material_prompts_v11(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v10(card)


def fresh_material_prompts_v12(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v11(card)


def fresh_material_prompts_v13(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v12(card)


def fresh_material_prompts_v14(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v13(card)


def fresh_material_prompts_v15(card: dict[str, str]) -> tuple[list[str], list[str]]:
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    desktop = [
        f"Help me start {topic}. {scenario} Separate what is known from what is missing, name who should confirm each gap, and keep this rule: {constraint}",
        f"For {topic}, make a short evidence ledger with sourced facts, conflicts, missing inputs, and a confirmation owner for every gap.",
        f"Which unresolved item in {topic} could create the most rework? Explain how to verify it without guessing.",
        f"Apply this boundary to {topic}: {constraint} Tell me what it stops us from approving and who must confirm the open point.",
        f"Give me a compact review order for {topic}. Keep known facts, missing information, responsible owners, and release holds separate.",
        f"What warning sign in {topic} should stop release? Name the evidence and confirmation owner needed to clear it.",
        f"Write one direct, normal-sounding question for the person who owns the biggest unresolved input in {topic}.",
        f"Check {topic} against this target: {proof} Separate passing evidence from missing evidence and name each missing owner.",
        f"Summarize today's position on {topic}: what is supported, what is held, who confirms the gaps, and what clears the hold.",
        f"Close the {topic} review with one reusable no-guess rule and one safe next action based only on confirmed information.",
    ]
    discord = [
        f"Engel, give me a clean first read on {topic}. {scenario} What is known, what is missing, and who confirms each gap?",
        f"For {topic}, list the sourced facts, conflicts, open inputs, and the person responsible for each confirmation.",
        f"Keep this no-guess limit active for {topic}: {constraint} What decision stays on hold?",
        f"Name one safe next step for {topic} that uses confirmed information and keeps missing owners visible.",
        f"Use this closeout target for {topic}: {proof} What evidence passes, and what still needs an owner?",
        f"Wrap up {topic} with the supported decision, active hold, confirmation owner, and next check.",
    ]
    return desktop, discord


def fresh_material_prompts_v16(card: dict[str, str]) -> tuple[list[str], list[str]]:
    return fresh_material_prompts_v15(card)


def fresh_material_prompts_v17(card: dict[str, str]) -> tuple[list[str], list[str]]:
    desktop, discord = fresh_material_prompts_v16(card)
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    desktop[0] = (
        f"Help me start {topic}. {scenario} Separate confirmed inputs from open inputs, "
        f"name who should confirm each gap, and keep this rule: {constraint}"
    )
    discord[0] = (
        f"Engel, give me a clean first read on {topic}. {scenario} Separate confirmed inputs "
        "from open inputs and name who confirms each gap."
    )
    desktop[7] = (
        f"Check {topic} against this target: {card['proof']} Separate passing evidence from "
        "open evidence and name the owner of each open item."
    )
    discord[4] = (
        f"Use this closeout target for {topic}: {card['proof']} Separate passing evidence from "
        "open evidence and identify each confirmation owner."
    )
    return desktop, discord


# Domain-native prompt shapes (2026-07-31). The v17 shape above is the CONSTRUCTION
# ("aec") discipline: it teaches the evidence-ledger / confirmation-owner / safe-work-
# boundary habit and deliberately trips the CT246 incomplete-input gate so a field
# answer is held to it. Applying that same shape to math or Engel-systems topics was
# wrong: it forces a math answer to name a construction "confirmation owner" it has no
# analogue for, so the CT246 gate discards the draft and the turn is lost. These two
# generators produce domain-native prompts that teach the SAME verify-before-asserting
# habit in the vocabulary of their own domain, and are worded to avoid the AEC
# incomplete-input trigger (an uncertainty term co-occurring with a construction
# project-context term) so the gate does not fire on a math/engineering turn. Their
# training samples are vetted by a domain-appropriate eligibility gate in the runner
# (math: deterministic CAS check; engineering: the grounding gate).

def math_verification_prompts_v1(card: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Math-native training prompts: show the work, verify the result by an INDEPENDENT
    method, and never assert an unchecked number."""
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    # Renewal cards carry ten declared problem IDs.  Pose those exact questions instead
    # of asking the model to invent a problem: the exact grader can then compare the
    # answer to independent ground truth, and a model cannot silently swap in an easier
    # exercise.  Historical cards without IDs retain their original prompt shape below.
    problem_ids = card.get("problem_ids")
    if problem_ids is not None:
        if not isinstance(problem_ids, list) or len(problem_ids) != 10:
            raise ValueError("a declared math card requires exactly ten problem_ids")
        from engel_math_problems import BY_ID

        problems = []
        for raw_problem_id in problem_ids:
            problem_id = str(raw_problem_id or "").strip()
            problem = BY_ID.get(problem_id)
            if problem is None:
                raise ValueError(f"unknown declared math problem: {problem_id!r}")
            if not problem.decidable:
                raise ValueError(
                    f"renewal math problem must be exactly decidable: {problem_id}"
                )
            problems.append(problem)
        if len({problem.problem_id for problem in problems}) != 10:
            raise ValueError("declared math problem_ids must be unique within a card")

        directions = [
            "Solve the declared problem and independently substitute or recompute the result.",
            "Solve it by a clear first method, then verify it by a genuinely separate method.",
            "Solve it, try to falsify your own answer, and show the residual or exact agreement.",
            f"Solve it while enforcing this rule: {constraint}",
            "Give the shortest complete derivation that still includes an exact reverse check.",
            "Show where a plausible wrong answer would fail the independent check.",
            "Use a bounded symbolic or finite recomputation and name the operation that verifies it.",
            f"Meet this evidence target without changing the question: {proof}",
            "State any domain restriction, then solve and verify the declared question exactly.",
            f"Close this {topic} lesson with the solved value and one reusable verification rule.",
        ]
        desktop = [
            (
                f"Declared problem {problem.problem_id}: {problem.question} "
                f"{directions[index]} Label the response 'Result:', 'Work:', and "
                "'Check:'. Use 'Unverified:' only if the independent check cannot decide."
            )
            for index, problem in enumerate(problems)
        ]
        discord = [
            (
                f"Declared problem {problem.problem_id}: {problem.question} "
                "Give Result, Work, and an independent exact Check without replacing "
                "the question."
            )
            for problem in problems[:6]
        ]
        return desktop, discord
    # Prompts pose a CONCRETE problem to solve, not an abstract "work on this area" ask --
    # an abstract prompt makes a small model restate the format instead of doing the math.
    # Each answer must carry the labeled Result / Work / Check so the runner can confirm an
    # independent verification is present before capturing the sample.
    desktop = [
        f"Pose one concrete problem that fits this practice and solve it fully: {topic}. {scenario} Answer with a 'Result:' line, a 'Work:' section, and a 'Check:' that independently verifies the answer (substitute it back or recompute) and shows the residual or agreement.",
        f"Give one fully worked concrete example for {topic}, then verify it a second independent way. Label your answer 'Result:', 'Work:', and 'Check:' and show the point where both methods agree.",
        f"Take one concrete case of {topic}, solve it, then try to break your own answer. Label it 'Result:', 'Work:', 'Check:' (an independent verification), and 'Unverified:' for anything you could not confirm.",
        f"Hold this rule while solving one concrete {topic} problem: {constraint} Show 'Result:', 'Work:', and the 'Check:' that enforces the rule.",
        f"Give a compact, fully worked solution to one concrete {topic} problem: a 'Result:' line, a brief 'Work:', and a 'Check:' that independently verifies it with the residual.",
        f"Solve one concrete {topic} problem where a wrong answer would still look right, and show the 'Check:' that catches it. Use 'Result:', 'Work:', 'Check:'.",
        f"Solve one concrete {topic} problem you can confirm with the deterministic sympy lane; show 'Result:', 'Work:', and the exact 'Check:' the lane would run.",
        f"Turn this target into one concrete solved example for {topic}: {proof} Show 'Result:', 'Work:', 'Check:', and 'Unverified:' for anything the check could not settle.",
        f"Solve one concrete {topic} problem and report it as 'Result:', 'Work:', 'Check:' (the exact independent verification that proved it), and 'Unverified:' for any unsettled step.",
        f"Close {topic} with one fully worked, independently checked concrete example — labeled 'Result:', 'Work:', 'Check:' — and one reusable verification rule.",
    ]
    discord = [
        f"Engel, pose and fully solve one concrete {topic} problem. Give Result, Work, and an independent Check.",
        f"Solve one concrete {topic} problem two independent ways and show they agree (Result / Work / Check).",
        f"Hold this rule on one concrete {topic} problem: {constraint} Show Result, Work, and the Check.",
        f"Pick one small {topic} problem you can fully verify and solve it: Result, Work, Check.",
        f"Turn this target into a solved {topic} example: {proof} Show Result, Work, and the Check.",
        f"One fully worked, independently checked {topic} example: Result, Work, Check.",
    ]
    return desktop, discord


def engineering_evidence_prompts_v1(card: dict[str, str]) -> tuple[list[str], list[str]]:
    """Engel-grounded engineering training prompts: cite the REAL component, verifier, or
    receipt behind each claim, separate what a named verifier confirms from what stays open,
    and report an honest unknown rather than a guess."""
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    # Citation supply (2026-08-04). The reply is graded on citing a real existing
    # file, but only ONE of these ten prompts (the {proof} one) ever showed the
    # model a real path: across two 5-hour runs, all 9 prompts that named a real
    # .py were admitted and 46 of 55 rejects invented a filename instead. Nothing
    # was wrong with the model's honesty rule -- it was being asked to recall paths
    # it had never been shown. Every prompt now carries its card's real artifacts,
    # and the gate binds the citation to THIS list (see _engineering_answer_is_grounded),
    # so name-dropping an unrelated real file no longer launders a fabricated answer.
    # Keep the wording clear of CONTRACT_ECHO_MARKERS (engel_governor.py) -- notably
    # never write "a real file path or a verify" here.
    # Optional: a card that supplies no artifacts generates the old prompts unchanged,
    # and the gate falls back to plain existence for them. Both halves stay in step.
    artifacts = card.get("artifacts") or ()
    cite = f" Cite only from these real files: {', '.join(artifacts)}." if artifacts else ""
    desktop = [
        f"Walk me through {topic}. {scenario} Name the real Engel component and the verifier or receipt that backs each claim.{cite}",
        f"For {topic}, separate what a named Engel verifier confirms from what nothing yet confirms, and mark the second group as open.{cite}",
        f"Which single claim in {topic} would cause the most damage if it were wrong, and which verifier or receipt settles it?{cite}",
        f"Hold this rule on {topic}: {constraint} Show one action it blocks and name the check that would unblock it.{cite}",
        f"Give a compact review of {topic}: the real routes and files involved, and the named verifier that proves each one works.{cite}",
        f"What signal in {topic} should make Engel stop and say plainly it is unverified rather than guess?{cite}",
        f"Write the one question Engel should answer with a receipt before calling {topic} done.{cite}",
        f"Check {topic} against this target: {proof} Name which parts a verifier already confirms and which stay open.{cite}",
        f"Summarize {topic}: what a named verifier confirms today, what stays open, and the receipt that will close it.{cite}",
        f"Close {topic} with one reusable check-before-claiming rule and the next real verifier to run.{cite}",
    ]
    discord = [
        f"Engel, give me a grounded read on {topic}. {scenario} Cite the real verifier or receipt behind each claim.{cite}",
        f"For {topic}, what does a named verifier confirm, and what stays open?{cite}",
        f"Hold this rule on {topic}: {constraint} What does it block?{cite}",
        f"One safe next step on {topic} that relies only on what a verifier confirms?{cite}",
        f"Check {topic} against this target: {proof} What passes, and what stays open?{cite}",
        f"Wrap up {topic}: confirmed by a verifier, still open, and the receipt that closes it.{cite}",
    ]
    return desktop, discord


# Communication discipline (2026-08-01). Every generator above asks Engel to DESCRIBE a
# discipline, and that is correct for them: the reply is graded, the habit is what gets
# trained, and the answer text itself is scaffolding nobody wants to imitate. This one is
# inverted. The communication curriculum trains Engel AI Main's CHAT VOICE, so the accepted
# reply text becomes the target text of a supervised sample -- whatever Engel writes here is
# literally what it learns to sound like. That flips two rules:
#   1. An abstract ask ("explain your approach to answering directly") produces meta-
#      commentary ABOUT talking, and training on it teaches Engel to narrate its own
#      manners instead of having them. So every prompt hands over a concrete SITUATION and
#      asks for the reply Engel would actually send.
#   2. The labelled scaffolding the other disciplines require (Result/Work/Check,
#      Confirmed/Proof/Still open) must never appear here. Training on scaffolded text
#      bakes the scaffolding into ordinary conversation, which is the template disease the
#      style card exists to prevent. Nothing below asks for a heading, a label, a bullet
#      list, or a code block, and several prompts rule them out explicitly.
# The eligibility gate for this discipline is correspondingly inverted too: it rejects a
# scaffolded, filler-laden, or assistant-register answer instead of demanding structure.

def communication_voice_prompts_v1(card: dict[str, str]) -> tuple[list[str], list[str]]:
    """Chat-voice training prompts: hand Engel a real situation and ask for the reply it
    would actually send, so the captured answer IS the voice being taught."""
    topic = card["topic"]
    scenario = card["scenario"]
    constraint = card["constraint"]
    proof = card["proof"]
    # Every prompt says "write the reply itself" somewhere, in one wording or another.
    # Without that the model answers ABOUT the situation and the captured text is an essay
    # on communication rather than the communication -- useless as voice target text.
    desktop = [
        f"Here is a real situation from our chat: {scenario} Write me the reply you would actually send in that moment -- the reply itself, not a description of how you would handle it. Plain sentences, no headings and no lists.",
        f"Same situation: {scenario} This time you have not actually looked at the thing I am asking about. Write the reply you would send me: say that plainly in the first line, name the one thing you would look at first, and do not fill the gap with something that merely sounds right.",
        f"Give me the human version. Here is the raw material, names and all: {proof} Do not read the file names back to me. Tell me in ordinary words what that means for how you talk to me, the way you would say it to me mid-job.",
        f"Now picture me firing off a quick, half-typed line at you about {topic} -- the kind that could land two ways, and the two readings lead to different work. Do not pick one and run with it, and do not come back with a stack of questions. Ask me the one question whose answer changes what you do, and say in the same breath what you would do with each answer.",
        f"Hard turn. I went back over our last stretch and found this: {scenario} You did not catch it, I did. Tell me straight what happened, what you actually know about why, and what you are doing about it. No apology paragraph, no cushioning, and no promise you cannot keep.",
        f"Quick one, and I want it quick. Honest answer: {topic} -- is that already how you talk to me day to day? Keep the reply the size of the question and add at most one fact that makes it useful.",
        f"Carry this forward. We settled this between us an hour ago: {constraint} Treat it as settled now. My next question is simple: what changes in the very next reply you write me because of it? Name the decision in a clause and move on -- do not replay our conversation back at me, and do not make me take that decision twice.",
        f"Here is the pull you have to resist right now: {constraint} Show me what holding that line looks like in a real reply -- answer me as if I just walked over and asked you about {topic}.",
        f"I am short with you now, because this is the second time it has come up. {scenario} I do not want your reasoning, I want one line that owns it and one concrete next step. Write me exactly that, in your own voice.",
        f"Last one, and answer it as yourself rather than as a write-up. Think back over how you just handled this -- {topic} -- and tell me in a few sentences what you will do differently the next time it comes up between us. Talk to me.",
    ]
    discord = [
        f"Engel, real situation: {scenario} Write me the reply you would actually send. No headings, no lists.",
        "Same one, except you have not looked at it yet. Say that plainly and tell me what you would check first.",
        "Bad news version: it failed overnight and I am reading your reply over coffee. Tell me what broke, what you know about the cause, and the next step. No cushioning.",
        f"My next line about {topic} could land two ways. Ask me the one question that changes what you do, and say what you would do with each answer.",
        f"Quick one: {topic} -- is that already how you talk to me day to day? Keep it the size of the question.",
        f"Close it out in your own voice: next time this comes up between us -- {topic} -- what will you do differently?",
    ]
    return desktop, discord


def construction_corpus_prompts_v2(
    card: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """AEC prompts whose exact document set is explicit before runtime enrichment.

    The template contains stable reviewed questions, not copied corpus prose. The visible
    runner later resolves ``evidence_anchors`` against the verified bundle and appends the
    bounded excerpt packet to the delivered prompt. Requiring the grounding metadata here
    prevents a legacy field-coordination card from being presented as quote-verifiable AEC.
    """
    documents = card.get("documents")
    anchors = card.get("evidence_anchors")
    if not isinstance(documents, list) or not documents:
        raise ValueError("AEC material must name exact manifest documents")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("AEC material must name deterministic evidence anchors")
    clean_documents = [str(item or "").strip() for item in documents]
    if (
        any(not item or not item.casefold().endswith(".pdf") for item in clean_documents)
        or len(set(clean_documents)) != len(clean_documents)
    ):
        raise ValueError("AEC material documents must be unique exact PDF filenames")
    anchored_documents = {
        str(item.get("document") or "")
        for item in anchors
        if isinstance(item, dict) and str(item.get("section") or "").strip()
    }
    if anchored_documents != set(clean_documents) or len(anchors) != len({
        (str(item.get("document") or ""), str(item.get("section") or "").upper())
        for item in anchors
        if isinstance(item, dict)
    }):
        raise ValueError(
            "AEC material must bind every declared document to a unique evidence anchor"
        )
    desktop, discord = fresh_material_prompts_v17(card)
    supplied = ", ".join(clean_documents)
    grounding = (
        " The runner will append a verified local evidence packet. Use only its exact "
        f"manifest filenames ({supplied}) and excerpts for Sourced facts. Put one source "
        "document and one Section on each sourced-fact line; keep everything the packet "
        "does not support under Open items."
    )
    return (
        [prompt + grounding for prompt in desktop],
        [prompt + grounding for prompt in discord],
    )


# Discipline registry: maps a curriculum discipline to its prompt generator. Unknown
# disciplines fall back to the strict AEC shape (fail toward MORE discipline, never less).
CURRICULUM_PROMPT_GENERATORS = {
    "aec": construction_corpus_prompts_v2,
    "math": math_verification_prompts_v1,
    "engineering": engineering_evidence_prompts_v1,
    "communication": communication_voice_prompts_v1,
}


def curriculum_prompts(
    card: dict[str, Any], discipline: str = "aec"
) -> tuple[list[str], list[str]]:
    """Return (desktop, discord) prompt sets for a card in its curriculum's discipline."""
    generator = CURRICULUM_PROMPT_GENERATORS.get(
        discipline, construction_corpus_prompts_v2
    )
    return generator(card)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"_p{os.getpid()}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def append_event(path: Path, event: str, **payload: Any) -> None:
    row = {"time_utc": utc_now(), "event": event, **payload}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def http_json(url: str, timeout: float = 8.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8", errors="replace"))
        return value if isinstance(value, dict) else {"ok": False, "error": "non-object response"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"ok": False, "error": str(exc)}


def post_json(url: str, payload: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8", errors="replace"))
        return value if isinstance(value, dict) else {"ok": False, "error": "non-object response"}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"ok": False, "error": str(exc)}


def compact_device_snapshot() -> dict[str, Any]:
    health = http_json(CHAT_HEALTH_URL)
    phone = http_json(PHONE_CLUSTER_URL, timeout=5.0)
    model_runtime = health.get("model_runtime") if isinstance(health.get("model_runtime"), dict) else {}
    inventory = model_runtime.get("active_model_inventory") if isinstance(model_runtime.get("active_model_inventory"), dict) else {}
    phone_workers = phone.get("workers") if isinstance(phone.get("workers"), dict) else {}
    sub = health.get("sub_engel_bridge") if isinstance(health.get("sub_engel_bridge"), dict) else {}
    sub_nodes = sub.get("nodes") if isinstance(sub.get("nodes"), list) else []
    return {
        "chat_ok": health.get("ok") is True,
        "provider_policy": health.get("automatic_provider_policy", {}),
        "ct_local_model_present": model_runtime.get("local_gguf_model_present") is True,
        "ct_lora_ready": model_runtime.get("lora_runtime_ready") is True,
        "active_model_file_count": inventory.get("model_file_count"),
        "active_model_total_gib": inventory.get("model_total_gib"),
        "active_runtime_storage": inventory.get("active_runtime_storage"),
        "vault_used_for_active_runtime": inventory.get("vault_used_for_active_runtime"),
        "phones": {
            worker_id: {
                "remote_address": (row.get("identity") or {}).get("remote_address") if isinstance(row, dict) else "",
                "last_seen_utc": row.get("last_seen_utc") if isinstance(row, dict) else "",
            }
            for worker_id, row in phone_workers.items()
        },
        "sub_nodes": [
            {
                "node_id": row.get("node_id") or row.get("id"),
                "hostname": row.get("hostname"),
                "paired": row.get("paired"),
                "live": row.get("live"),
                "last_seen_utc": row.get("last_seen_utc"),
            }
            for row in sub_nodes
            if isinstance(row, dict)
        ],
    }


def live_memory_prompt_collision_scan(prompts: list[str]) -> dict[str, Any]:
    if not CT_KEY.is_file():
        return {"ok": False, "error": "CT246 SSH key is unavailable", "collision_count": None}
    common = [
        "-i", str(CT_KEY), "-p", CT_PORT,
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    try:
        completed = subprocess.run(
            [
                "ssh", *common, f"root@{CT_HOST}",
                "cat /opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": str(exc), "collision_count": None}
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": (completed.stderr or completed.stdout or "CT246 memory scan failed").strip()[:800],
            "collision_count": None,
        }
    seen: set[str] = set()
    for line in (completed.stdout or "").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and isinstance(row.get("prompt"), str):
            seen.add(row["prompt"])
    collisions = sorted(set(prompts).intersection(seen))
    return {
        "ok": not collisions,
        "campaign_prompt_count": len(prompts),
        "campaign_unique_prompt_count": len(set(prompts)),
        "live_memory_unique_prompt_count": len(seen),
        "collision_count": len(collisions),
        "collisions": collisions[:20],
    }


def preflight(material_prompts: list[str] | None = None) -> dict[str, Any]:
    chat = http_json(CHAT_HEALTH_URL)
    room = http_json(ROOM_HEALTH_URL)
    policy = chat.get("automatic_provider_policy") if isinstance(chat.get("automatic_provider_policy"), dict) else {}
    model = chat.get("model_runtime") if isinstance(chat.get("model_runtime"), dict) else {}
    checks = {
        "python_present": PYTHON.is_file(),
        "app_present": APP_EXE.is_file(),
        "visible_runner_present": VISIBLE_RUNNER.is_file(),
        "discord_runner_present": DISCORD_RUNNER.is_file(),
        "ct_chat_healthy": chat.get("ok") is True,
        "meeting_room_healthy": room.get("ok") is True,
        "ct_local_gguf_present": model.get("local_gguf_model_present") is True,
        "trained_lora_ready": model.get("lora_runtime_ready") is True,
        "automatic_local_first": policy.get("local_model_first") is True,
        "fallback_only_after_local_failure": policy.get("fallback_after_local_failure") is True,
        "automatic_bridge_candidates_enabled": policy.get("auto_bridge_routing_enabled") is True,
        "build_local_all_stages": policy.get("build_local_all_stages") is True,
    }
    material_scan: dict[str, Any] = {}
    if material_prompts is not None:
        retired_prompts = {
            text
            for prompt_set in DESKTOP_PROMPT_SETS + DISCORD_PROMPT_SETS
            for text in prompt_set
        }
        retired_prompts.update(
            text
            for card in NEW_MATERIAL_CARDS
            for lane in new_material_prompts(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V5
            for lane in fresh_material_prompts_v5(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V6
            for lane in fresh_material_prompts_v6(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V7[:1]
            for lane in fresh_material_prompts_v7(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V8[:1]
            for lane in fresh_material_prompts_v8(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V9[:1]
            for lane in fresh_material_prompts_v9(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V10[:1]
            for lane in fresh_material_prompts_v10(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V11[:1]
            for lane in fresh_material_prompts_v11(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V12[:1]
            for lane in fresh_material_prompts_v12(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V13[:1]
            for lane in fresh_material_prompts_v13(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V14[:1]
            for lane in fresh_material_prompts_v14(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V15[:1]
            for lane in fresh_material_prompts_v15(card)
            for text in lane
        )
        retired_prompts.update(
            text
            for card in FRESH_MATERIAL_CARDS_V16[:1]
            for lane in fresh_material_prompts_v16(card)
            for text in lane
        )
        static_collisions = sorted(set(material_prompts).intersection(retired_prompts))
        material_scan = live_memory_prompt_collision_scan(material_prompts)
        material_scan["retired_prompt_count"] = len(retired_prompts)
        material_scan["retired_collision_count"] = len(static_collisions)
        material_scan["retired_collisions"] = static_collisions[:20]
        checks["fresh_material_prompts_unique"] = len(material_prompts) == len(set(material_prompts))
        checks["fresh_material_absent_from_retired_curricula"] = not static_collisions
        checks["fresh_material_absent_from_live_ct_memory"] = material_scan.get("ok") is True
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "fresh_material_scan": material_scan,
        "devices": compact_device_snapshot(),
    }


def write_epoch_templates(run_dir: Path, epoch: int) -> tuple[Path, Path, int, int]:
    curriculum_size = len(FRESH_MATERIAL_CARDS_V17)
    set_index = (epoch - 1) % curriculum_size
    round_index = (epoch - 1) // curriculum_size
    desktop, discord = fresh_material_prompts_v17(FRESH_MATERIAL_CARDS_V17[set_index])
    if round_index:
        desktop[0] = [
            "Picking this conversation back up, how are you doing?",
            "Checking in again, what should we work through together?",
            "I am back. Start with a normal check-in.",
        ][(round_index - 1) % 3]
        discord[0] = [
            "Picking this back up, give me a normal quick check-in.",
            "Checking in again, what should we talk through?",
            "I am back. Start with a short natural reply.",
        ][(round_index - 1) % 3]
    template_dir = run_dir / "templates"
    visible_path = template_dir / f"epoch_{epoch:02d}_desktop.json"
    discord_path = template_dir / f"epoch_{epoch:02d}_discord.json"
    write_json(
        visible_path,
        {
            "schema": "engel_visible_chat_training_template_v1",
            "purpose": "One-day local-first real-person desktop chat epoch",
            "material_version": CAMPAIGN_MATERIAL_VERSION,
            "fresh_material": True,
            "smoke_prompts": desktop[:3],
            "active_prompts": desktop,
        },
    )
    write_json(
        discord_path,
        {
            "schema": "engel_discord_owner_ui_training_template_v1",
            "purpose": "One-day local-first real-person Discord chat epoch",
            "material_version": CAMPAIGN_MATERIAL_VERSION,
            "fresh_material": True,
            "prompts": discord,
        },
    )
    return visible_path, discord_path, len(desktop), len(discord)


def newest_report(pattern: str, since_epoch: float) -> Path | None:
    candidates = [
        path for path in REPORT_DIR.glob(pattern)
        if path.is_file() and path.stat().st_mtime >= since_epoch - 2
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def summarize_epoch(visible: dict[str, Any], discord: dict[str, Any]) -> dict[str, Any]:
    visible_hits = (visible.get("ct_persistent_memory") or {}).get("hits") or {}
    discord_results = discord.get("results") if isinstance(discord.get("results"), list) else []
    route_rows = [row for row in visible_hits.values() if isinstance(row, dict)]
    route_rows.extend(
        row.get("local_model_proof", {})
        for row in discord_results
        if isinstance(row, dict) and isinstance(row.get("local_model_proof"), dict)
    )
    local_count = sum(1 for row in route_rows if row.get("local_model_verified") is True or row.get("verified") is True)
    escalation_count = sum(1 for row in route_rows if row.get("verified_local_first_escalation") is True)
    pipeline_count = sum(1 for row in route_rows if row.get("provider_pipeline_used") is True)
    unauthorized_count = sum(
        1 for row in route_rows
        if row.get("provider_pipeline_used") is True and row.get("verified_local_first_escalation") is not True
    )
    visible_route_ok = visible.get("local_first_or_verified_escalation_ok") is True
    discord_route_ok = bool(discord_results) and all(
        (row.get("local_model_proof") or {}).get("routing_policy_verified") is True
        for row in discord_results
        if isinstance(row, dict)
    )
    return {
        "visible_report_status": visible.get("status", "MISSING"),
        "discord_report_status": discord.get("status", "MISSING"),
        "visible_chat_route_ok": visible_route_ok,
        "discord_chat_route_ok": discord_route_ok,
        "persistent_memory_ok": visible.get("ct_persistent_memory_ok") is True
        and visible.get("ct_single_write_ok") is True
        and visible.get("ct_training_eligible_ok") is True
        and int(discord.get("persistent_lines_after") or 0) > int(discord.get("persistent_lines_before") or 0)
        and bool(discord_results)
        and all(row.get("training_sample_eligible") is True for row in discord_results if isinstance(row, dict)),
        "local_model_turn_count": local_count,
        "provider_pipeline_turn_count": pipeline_count,
        "verified_escalation_count": escalation_count,
        "unauthorized_provider_turn_count": unauthorized_count,
        "visible_phone_count": (visible.get("phone_link_after") or {}).get("live_phone_worker_count"),
        "route_policy_ok": visible_route_ok and discord_route_ok and unauthorized_count == 0,
    }


def persist_report_to_ct(path: Path) -> None:
    if not CT_KEY.is_file() or not path.is_file():
        return
    destination = "/opt/engel/reports/training/"
    common = ["-i", str(CT_KEY), "-p", CT_PORT, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    subprocess.run(
        ["ssh", *common, f"root@{CT_HOST}", f"mkdir -p {destination}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    scp_common = [
        "-i", str(CT_KEY), "-P", CT_PORT,
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    subprocess.run(
        ["scp", *scp_common, str(path), f"root@{CT_HOST}:{destination}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    return "\n".join(
        [
            f"# Engel One-Day Local-First Chat Training {report.get('status', 'UNKNOWN')}",
            "",
            f"- Run: `{report.get('run_id', '')}`",
            f"- Started UTC: `{report.get('started_at_utc', '')}`",
            f"- Finished UTC: `{report.get('finished_at_utc', '')}`",
            f"- Requested chat minutes per UI lane: `{report.get('requested_chat_minutes_per_lane', 0)}`",
            f"- Epochs completed: `{summary.get('epochs_completed', 0)}/{report.get('epoch_count', 0)}`",
            f"- Local-model turns: `{summary.get('local_model_turn_count', 0)}`",
            f"- Verified provider escalations: `{summary.get('verified_escalation_count', 0)}`",
            f"- Unauthorized provider turns: `{summary.get('unauthorized_provider_turn_count', 0)}`",
            f"- Persistent-memory epochs passed: `{summary.get('persistent_memory_epoch_count', 0)}`",
            f"- Device faults observed: `{summary.get('device_fault_epoch_count', 0)}`",
            "",
            "Provider use is valid only when the same CT246 receipt proves the local model failed first.",
            "This is conversational training and regression evidence; it does not claim a new model-weight update.",
            "",
        ]
    )


def process_running(pid: int) -> bool:
    # Kernel-handle probe instead of shelling out to tasklist: the tasklist version
    # spawned a console process per poll (visible terminal flashes under Windows
    # Terminal) and cost ~100x more. Shared implementation, do not re-inline.
    from engel_process_liveness import pid_is_running

    return pid_is_running(pid)


def status() -> int:
    active = load_json(ACTIVE_PATH)
    if not active:
        print(json.dumps({"ok": False, "status": "no active one-day campaign"}, indent=2))
        return 1
    pid = int(active.get("pid") or 0)
    running = process_running(pid)
    active["process_running"] = running
    run_dir = Path(str(active.get("run_dir") or ""))
    active["state"] = load_json(run_dir / "state.json")
    print(json.dumps(active, indent=2, sort_keys=True))
    return 0 if running else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--epoch-minutes", type=float, default=60.0)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        return status()
    if args.hours <= 0 or args.epoch_minutes <= 0:
        raise SystemExit("hours and epoch-minutes must be positive")

    prior = load_json(ACTIVE_PATH)
    prior_pid = int(prior.get("pid") or 0)
    if process_running(prior_pid):
        raise SystemExit(f"one-day campaign already running as PID {prior_pid}")

    run_id = "engel_one_day_local_first_" + stamp()
    run_dir = RUNTIME_ROOT / run_id
    event_log = run_dir / "events.jsonl"
    state_path = run_dir / "state.json"
    final_json = REPORT_DIR / f"ENGEL_ONE_DAY_LOCAL_FIRST_CHAT_TRAINING_{run_id}.json"
    final_md = final_json.with_suffix(".md")
    epoch_count = int(math.ceil(args.hours * 60.0 / args.epoch_minutes))
    if epoch_count > len(FRESH_MATERIAL_CARDS_V17):
        raise SystemExit(
            f"fresh curriculum has {len(FRESH_MATERIAL_CARDS_V17)} unique epochs; requested {epoch_count}"
        )
    requested_total_minutes = args.hours * 60.0
    started_at = utc_now()
    write_json(
        ACTIVE_PATH,
        {
            "schema": "engel_one_day_training_active_v1",
            "run_id": run_id,
            "pid": os.getpid(),
            "run_dir": str(run_dir),
            "started_at_utc": started_at,
            "material_version": CAMPAIGN_MATERIAL_VERSION,
            "fresh_material_only": True,
        },
    )
    append_event(
        event_log,
        "campaign_started",
        run_id=run_id,
        epoch_count=epoch_count,
        material_version=CAMPAIGN_MATERIAL_VERSION,
        fresh_material_only=True,
    )
    campaign_prompts = [
        text
        for card in FRESH_MATERIAL_CARDS_V17[:epoch_count]
        for lane in fresh_material_prompts_v17(card)
        for text in lane
    ]
    initial_preflight = preflight(campaign_prompts)
    start_reps = post_json(
        "http://127.0.0.1:24680/reps/evaluate",
        {
            "kind": "training_campaign_start",
            "lane": "chat_training",
            "source": "engel-one-day-local-first-supervisor",
            "prompt": "Run one day of new chat material through Engel desktop and Discord with the local LLM first.",
            "assistant_reply": "The campaign is starting with 24 unique epochs and verified local-first routing.",
            "lesson": "A provider response is valid only after the same CT246 receipt records a failed local attempt.",
            "receipt_path": str(run_dir / "preflight.json"),
        },
    )
    initial_preflight["reps_start"] = start_reps
    write_json(run_dir / "preflight.json", initial_preflight)
    if not initial_preflight.get("ok"):
        append_event(event_log, "campaign_preflight_failed", preflight=initial_preflight)
        write_json(state_path, {"status": "PRECHECK_FAILED", "preflight": initial_preflight})
        return 2

    epoch_reports: list[dict[str, Any]] = []
    remaining_minutes = requested_total_minutes
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for epoch in range(1, epoch_count + 1):
        epoch_minutes = min(args.epoch_minutes, remaining_minutes)
        remaining_minutes -= epoch_minutes
        visible_template, discord_template, visible_count, discord_count = write_epoch_templates(run_dir, epoch)
        epoch_dir = run_dir / f"epoch_{epoch:02d}"
        epoch_dir.mkdir(parents=True, exist_ok=True)
        epoch_started = time.time()
        epoch_started_utc = utc_now()
        visible_cmd = [
            str(PYTHON), str(VISIBLE_RUNNER), "--mode", "one-hour", "--minutes", str(epoch_minutes),
            "--template", str(visible_template), "--terminate-existing", "--allow-verified-provider-escalation",
        ]
        discord_cmd = [
            str(PYTHON), str(DISCORD_RUNNER), "--minutes", str(epoch_minutes), "--template", str(discord_template),
            "--reply-timeout", "240", "--allow-verified-provider-escalation",
        ]
        append_event(event_log, "epoch_started", epoch=epoch, minutes=epoch_minutes, visible_prompts=visible_count, discord_prompts=discord_count)
        with (epoch_dir / "visible.log").open("w", encoding="utf-8") as visible_log, (epoch_dir / "discord.log").open("w", encoding="utf-8") as discord_log:
            visible_proc = subprocess.Popen(
                visible_cmd, cwd=str(ROOT), stdout=visible_log, stderr=subprocess.STDOUT,
                text=True, creationflags=creation_flags,
            )
            # Keep the two visible surfaces real while avoiding an artificial
            # first-turn collision on the shared local model service.
            time.sleep(min(90.0, max(15.0, epoch_minutes * 60.0 * 0.04)))
            discord_proc = subprocess.Popen(
                discord_cmd, cwd=str(ROOT), stdout=discord_log, stderr=subprocess.STDOUT,
                text=True, creationflags=creation_flags,
            )
            next_heartbeat = time.monotonic()
            while visible_proc.poll() is None or discord_proc.poll() is None:
                if time.monotonic() >= next_heartbeat:
                    device_snapshot = compact_device_snapshot()
                    state = {
                        "schema": "engel_one_day_training_state_v1",
                        "status": "RUNNING",
                        "run_id": run_id,
                        "material_version": CAMPAIGN_MATERIAL_VERSION,
                        "fresh_material_only": True,
                        "pid": os.getpid(),
                        "epoch": epoch,
                        "epoch_count": epoch_count,
                        "epoch_started_at_utc": epoch_started_utc,
                        "visible_pid": visible_proc.pid,
                        "visible_running": visible_proc.poll() is None,
                        "discord_pid": discord_proc.pid,
                        "discord_running": discord_proc.poll() is None,
                        "devices": device_snapshot,
                        "updated_at_utc": utc_now(),
                    }
                    write_json(state_path, state)
                    append_event(event_log, "heartbeat", epoch=epoch, devices=device_snapshot)
                    next_heartbeat = time.monotonic() + 300.0
                time.sleep(2.0)
            visible_exit = int(visible_proc.returncode or 0)
            discord_exit = int(discord_proc.returncode or 0)

        visible_path = newest_report("ENGEL_VISIBLE_CHAT_UI_SOAK_*.json", epoch_started)
        discord_path = newest_report("ENGEL_DISCORD_OWNER_UI_TRAINING_*.json", epoch_started)
        visible_report = load_json(visible_path)
        discord_report = load_json(discord_path)
        epoch_summary = summarize_epoch(visible_report, discord_report)
        epoch_device_snapshot = compact_device_snapshot()
        epoch_report = {
            "epoch": epoch,
            "material_version": CAMPAIGN_MATERIAL_VERSION,
            "started_at_utc": epoch_started_utc,
            "finished_at_utc": utc_now(),
            "requested_minutes": epoch_minutes,
            "visible_exit_code": visible_exit,
            "discord_exit_code": discord_exit,
            "visible_report": str(visible_path or ""),
            "discord_report": str(discord_path or ""),
            "device_snapshot": epoch_device_snapshot,
            **epoch_summary,
        }
        epoch_report["ok"] = bool(
            visible_exit == 0
            and discord_exit == 0
            and epoch_summary.get("route_policy_ok") is True
            and epoch_summary.get("persistent_memory_ok") is True
            and int(epoch_summary.get("visible_phone_count") or 0) >= 3
            and len(epoch_device_snapshot.get("phones") or {}) == 3
        )
        epoch_reports.append(epoch_report)
        write_json(epoch_dir / "epoch_report.json", epoch_report)
        append_event(event_log, "epoch_finished", **epoch_report)
        if epoch_report["ok"] is not True:
            partial_summary = {
                "epochs_completed": len(epoch_reports),
                "route_policy_epoch_count": sum(
                    1 for row in epoch_reports if row.get("route_policy_ok") is True
                ),
                "persistent_memory_epoch_count": sum(
                    1 for row in epoch_reports if row.get("persistent_memory_ok") is True
                ),
                "local_model_turn_count": sum(
                    int(row.get("local_model_turn_count") or 0) for row in epoch_reports
                ),
                "provider_pipeline_turn_count": sum(
                    int(row.get("provider_pipeline_turn_count") or 0) for row in epoch_reports
                ),
                "verified_escalation_count": sum(
                    int(row.get("verified_escalation_count") or 0) for row in epoch_reports
                ),
                "unauthorized_provider_turn_count": sum(
                    int(row.get("unauthorized_provider_turn_count") or 0) for row in epoch_reports
                ),
                "device_fault_epoch_count": sum(
                    1 for row in epoch_reports if int(row.get("visible_phone_count") or 0) < 3
                ),
            }
            failed_report = {
                "schema": "engel_one_day_local_first_chat_training_report_v1",
                "ok": False,
                "status": "FAIL",
                "failure_reason": f"epoch {epoch} failed a required UI, route, memory, or device gate",
                "run_id": run_id,
                "material_version": CAMPAIGN_MATERIAL_VERSION,
                "fresh_material_only": True,
                "unique_prompt_count": len(set(campaign_prompts)),
                "started_at_utc": started_at,
                "finished_at_utc": utc_now(),
                "requested_chat_minutes_per_lane": requested_total_minutes,
                "epoch_count": epoch_count,
                "initial_preflight": initial_preflight,
                "summary": partial_summary,
                "epochs": epoch_reports,
                "persistent_memory_authority": "/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl",
                "training_kind": "conversational regression and memory training; no model-weight update claimed",
            }
            write_json(final_json, failed_report)
            final_md.write_text(render_markdown(failed_report), encoding="utf-8")
            persist_report_to_ct(final_json)
            persist_report_to_ct(final_md)
            failed_state = {
                "schema": "engel_one_day_training_state_v1",
                "status": "FAILED_EPOCH_GATE",
                "run_id": run_id,
                "material_version": CAMPAIGN_MATERIAL_VERSION,
                "pid": os.getpid(),
                "epoch": epoch,
                "epoch_count": epoch_count,
                "failure_reason": failed_report["failure_reason"],
                "updated_at_utc": utc_now(),
            }
            write_json(state_path, failed_state)
            append_event(
                event_log,
                "campaign_halted_on_failed_epoch",
                epoch=epoch,
                failure_reason=failed_report["failure_reason"],
            )
            return 3

    summary = {
        "epochs_completed": len(epoch_reports),
        "route_policy_epoch_count": sum(1 for row in epoch_reports if row.get("route_policy_ok") is True),
        "persistent_memory_epoch_count": sum(1 for row in epoch_reports if row.get("persistent_memory_ok") is True),
        "local_model_turn_count": sum(int(row.get("local_model_turn_count") or 0) for row in epoch_reports),
        "provider_pipeline_turn_count": sum(int(row.get("provider_pipeline_turn_count") or 0) for row in epoch_reports),
        "verified_escalation_count": sum(int(row.get("verified_escalation_count") or 0) for row in epoch_reports),
        "unauthorized_provider_turn_count": sum(int(row.get("unauthorized_provider_turn_count") or 0) for row in epoch_reports),
        "device_fault_epoch_count": sum(1 for row in epoch_reports if int(row.get("visible_phone_count") or 0) < 3),
    }
    ok = bool(
        len(epoch_reports) == epoch_count
        and summary["route_policy_epoch_count"] == epoch_count
        and summary["persistent_memory_epoch_count"] == epoch_count
        and summary["local_model_turn_count"] > 0
        and summary["unauthorized_provider_turn_count"] == 0
    )
    report = {
        "schema": "engel_one_day_local_first_chat_training_report_v1",
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "run_id": run_id,
        "material_version": CAMPAIGN_MATERIAL_VERSION,
        "fresh_material_only": True,
        "unique_prompt_count": len(set(campaign_prompts)),
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "requested_chat_minutes_per_lane": requested_total_minutes,
        "epoch_count": epoch_count,
        "initial_preflight": initial_preflight,
        "summary": summary,
        "epochs": epoch_reports,
        "persistent_memory_authority": "/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl",
        "training_kind": "conversational regression and memory training; no model-weight update claimed",
    }
    report["reps_finish"] = post_json(
        "http://127.0.0.1:24680/reps/evaluate",
        {
            "kind": "training_campaign_finish",
            "lane": "chat_training",
            "source": "engel-one-day-local-first-supervisor",
            "prompt": "Evaluate the completed one-day local-first chat campaign.",
            "assistant_reply": json.dumps(summary, sort_keys=True),
            "lesson": "Keep only evidence-backed local turns and verified post-local-failure escalations.",
            "receipt_path": str(final_json),
        },
    )
    write_json(final_json, report)
    final_md.write_text(render_markdown(report), encoding="utf-8")
    write_json(state_path, {"status": report["status"], "report": str(final_json), "summary": summary, "updated_at_utc": utc_now()})
    append_event(event_log, "campaign_finished", status=report["status"], report=str(final_json), summary=summary)
    persist_report_to_ct(final_json)
    persist_report_to_ct(final_md)
    try:
        ACTIVE_PATH.unlink()
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
