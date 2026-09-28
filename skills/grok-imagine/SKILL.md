---
name: imagine
description: >
  Using the Imagine tools in Grok Build (image_gen, image_edit,
  reference_to_video): code vs. generation, prompt-craft, reference-first real
  people, consistency across shots, video with pinned frames and voices.
when-to-use: >
  Load whenever generating or editing an image or video is on the table, i.e.
  when an image_gen, image_edit or reference_to_video call is
  being considered or about to be made. Tool-usage-driven, not triggered by a
  user merely mentioning images or videos.
metadata:
  short-description: "Prompting and workflow guidance for Imagine image and video tools"
---

# Imagine

Guidance for the Imagine tool calls in Grok Build:

- `image_gen` - generate a **new** image from a text prompt.
- `image_edit` - modify an **existing** image using a text prompt and source image(s).
- `reference_to_video` - the video tool: a clip from reference images, preset voices, and/or pinned frames.

Apply this whenever you're considering or about to call any of them.

## Build accurate visuals with code, not the image tools

1. **Image models are unreliable at exact text, numbers, and structure.** They can handle short text or a simple layout, but they often garble words, invent numbers, draw chart bars that match no data, or point diagram arrows nowhere, and the more that has to be exact, the worse they do. A detailed prompt doesn't make it dependable, and an `image_edit` pass usually won't fix it. So when a result needs specific text, data, or structure to be correct (charts from real numbers, labeled or technical diagrams, math explainers, tables, screens with real copy, and multi-panel layouts like contact sheets, storyboards, or comic grids where the frame, panel borders, and labels must be exact), construct the asset with code, where you control the exact content. Prefer HTML and CSS, which give much better layout, typography, and polish than Python plotting. When only the look matters (photos, illustrations, characters, scenes, decorative art), the image tools are the right choice. Which one fits depends on what the output needs to get right, not on how the request is worded.

## Verifying discrete accuracy (loop)

When the output must get specific text, numbers, data, or structure right, don't trust the first result - verify it in a loop:

1. Produce the result (generate, or per *Build accurate visuals with code*, construct it in code).
2. Inspect the actual output - use image understanding to read a generated image back (or check the rendered code) - and confirm every word, number, label, and structural detail matches the requirement, and that nothing overlaps, clips, or runs off-canvas.
3. If anything is wrong, fix and re-verify:
   - Garbled text, invented numbers, or broken layout from an image model? Don't just re-prompt - it will likely garble it again. Rebuild it with code.
   - Overlapping or clipped elements in code-built output? Re-lay-out with auto-layout (HTML/CSS) rather than nudging coordinates by hand.
   - Otherwise make one targeted edit.
4. Only finish when the discrete content is exactly correct. If it can't be made accurate, tell the user instead of shipping something wrong.

## Core Principles

1. **You own the prompt.** If the user gives a detailed prompt or asks you to use theirs, use it verbatim. Otherwise craft the final prompt: front-load the subject, give strong high-level direction for mood, composition, lighting, and style without over-specifying every detail, write natural prose rather than keyword tags, and describe positively instead of using negative prompts. For edits, describe only what changes. Target 2-5 sentences.
2. **Reference-first for real people.** Never use pure `image_gen` for a named real person or group, including face swaps, posters, cartoons, and cinematic or editorial depictions. Use `image_edit` with a real reference instead, and never produce non-consensual, sexualized, or minor-involving likenesses. See Real People and References for the procedure.
3. **Ground facts with search first.** If any part of the request depends on a real-world fact, identity, brand or product, place, event, or top/latest/current result, search the web before generating and put the actual verified details into the prompt. Don't rely on memory, and don't write vague placeholders like "the current president"; write the verified name.
4. **Anchor recurring subjects to a reference.** When a character, object, setting, or look recurs across images or shots, generate one canonical reference first and derive every reappearance from it with `image_edit`/`reference_to_video` - never a fresh `image_gen`. See *Consistency across shots and panels*.
5. **Handle failures gracefully.** On a moderation or safety block, stop; don't retry and don't paraphrase the prompt to evade the filter. Tell the user it was blocked and offer a different direction. If a reference is weak or a result looks off-target, say so and ask for an upload or redirect rather than silently iterating.
6. **Plan multi-step workflows.** Sequence the steps; only parallelize generations that belong to the same step.
7. **Review at the end.** Confirm the generations you intended actually executed and match what was asked.
8. **Don't assume tool behavior.** Don't invent tool parameters, return values, or environment capabilities that aren't actually provided; verify rather than guess.

## Choosing the Tool

| Situation | Tool |
|-----------|------|
| New image, no source image | `image_gen` |
| Edit, restyle, recolor, add, remove, or extend an existing image | `image_edit` |
| Iterate on a previous result while keeping composition | `image_edit` |
| Named real person or group | `image_edit` with a real reference after a web search |
| Generic, invented, or non-factual subject from scratch | `image_gen` |
| Any video clip | `reference_to_video` (references, pinned frames, voices in one call) |
| Game art: sprites, sheets, animation frames, tiles, UI, icons | the `game-assets` skill (engine-ready defaults), then the tools above |
| 3D model / mesh / GLB from an image | the `game-assets` skill (`3d.md`), not `image_gen` |

Rule of thumb: **no source image -> `image_gen`; source image -> `image_edit`.**

## `image_gen`

Generates a new image from a text prompt.

Inputs:

- `prompt` (required) - full description of the desired image.
- `aspect_ratio` - `1:1`, `16:9`, `9:16`, `3:2`, `2:3`, or `auto` (default).

Use for generic or invented subjects, or to create a base image you'll edit later. Not for named real people; see Reference-first for real people.

To produce multiple variations, make multiple `image_gen` calls with distinct prompts. The tool does not expose `n` or `count` parameters.

## `image_edit`

Transforms an existing image according to a prompt.

Inputs:

- `prompt` (required) - describe the desired transformation, and note what should stay the same.
- `image` (required) - one or more references. Each entry is, in priority order: (1) an image the user attached to the conversation, referenced by its placeholder token exactly as shown, e.g. `[Image #1]` - attachments have no path you can see, so never invent one; (2) an absolute filesystem path the user gave you or a file you generated; (3) a `data:image/...;base64,...` URL. Prefer a single clean reference for reliable results.
- `aspect_ratio` - optional; used for multi-image edits. Single-image edits preserve the input image aspect ratio.

References are downscaled before they reach the model (to roughly 768px on the long side), so fine detail in a reference will not survive; pick references for composition, identity, and color, not for small text.

Use to restyle, recolor, add or remove elements, preserve likeness, transfer style, remix, or iterate on a generated result.

To produce multiple variations, make multiple `image_edit` calls. The tool does not expose `n` or `count` parameters.

## Writing Strong Prompts

Describe, roughly in this order: **subject -> action/pose -> setting -> style -> composition -> lighting/mood -> key details.**

- Be specific and concrete; lead with the most important elements.
- State what to include rather than what to exclude.
- Use one coherent scene per prompt.
- Match `aspect_ratio` to the use case when using `image_gen`: `9:16` for phone/story, `16:9` for banner/video frame, `1:1` for avatar/icon.

## Real People and References

1. Search the web first to confirm identity, role, relationship, or event, even when it seems obvious.
2. Use a single strong reference with `image_edit`. A user-uploaded photo is best (pass its `[Image #N]` token); otherwise use a high-quality found reference and cite the source. `image_edit` can take more than one reference, but one clean reference is more reliable.
3. If no suitable reference exists, ask the user to upload one rather than generating from a weak base.

## Consistency across shots and panels

Grok Build has no persistent character or style memory, so consistency is manufactured on every call - independent generations of "the same" subject always drift.

- **Anchor to a reference.** For any recurring character, asset, wardrobe, location, or effect/color-grade ("look"), generate one canonical reference first, then produce every reappearance with `image_edit` (or `reference_to_video`) seeded from it. Restate the subject's fixed traits and any hard rule in each prompt, and verify each result against the reference. For coverage - one scene from several angles - derive each angle from a single scene master, not from fresh generations.
- **Build a set of assets as one sheet.** When several characters, props, or variants must share a style, generate them together in a single image - a character sheet, lineup, or prop sheet - rather than one generation each. One image is rendered in one style; separate generations drift in palette, line weight, and proportion. Then isolate each item into its own file by segmentation - key the flat background, find connected components, crop each with the mask as alpha and uniform padding, verify the count - rather than slicing a grid, which clips limbs and keeps neighbours; or pass the sheet itself as a reference. For a single recurring character, a turnaround sheet (front/side/back in one image) gives later edits and `reference_to_video` more identity to hold onto than one pose.
- **Multi-panel sets are a pipeline, not one image.** A storyboard, contact sheet, comic page, or scene series can't be a single generation; it collapses into a few generic frames with drifting faces and dropped panels. Instead: (1) build the references above; (2) generate each panel separately, seeded from the references it needs, verifying each; (3) assemble the grid, borders, and labels in code (per *Build accurate visuals with code*).

## Video

Video starts from images - there is no text-to-video tool. **`reference_to_video` is the only video tool**: it takes reference images, preset voices, and pinned frames in one call. Animating one still is simply `first_frame` with nothing else.

**Availability.** The tool is present in Grok Build but gated: on the free and X Basic tiers it returns an upgrade notice instead of a video - relay it and stop, don't retry. Under zero-data-retention (ZDR) mode it fails with a storage error unless a user-hosted bucket is configured - relay that error verbatim and stop the workflow; don't generate more source images or retry.

### `reference_to_video`

- `images` - up to 14 reference images (people, objects, wardrobe, settings). They condition the clip and appear **re-rendered**, not as literal frames. Tag them in the prompt as `<IMAGE_i>`.
- `voices` - up to 3 preset voice ids (e.g. `ara`, `eve`, `leo`, `rex`); the subject speaks in that voice. Tag as `<AUDIO_0>`... and put the spoken line in the prompt.
- `first_frame` / `last_frame` - images pinned as the **exact** first and last frame. Both set = the clip interpolates between them; the same image in both = a seamless loop.
- `keyframes` - up to 4 `{image, timestamp_s}` anchors that appear literally at a time strictly inside the clip; timestamps snap to a 1/3-second grid, and anchors closer than 1/3s apart are rejected.
- `prompt` (required), `aspect_ratio` (required), `duration` 1-15s (default 6), `resolution_name` 480p/720p.

At least one of `images`, `voices`, `first_frame`, `last_frame`, or `keyframes` is required. Prompt tags index in upload order `first_frame`, `images`, `keyframes`, `last_frame` - so with `first_frame` set, the first `images` entry is `<IMAGE_1>`, not `<IMAGE_0>`. Pinned frames need no tag; their timing is explicit.


### Staging a shot

| Shot | How to call `reference_to_video` |
|---|---|
| One subject or scene | its canonical reference in `images`; pin it as `first_frame` too when that exact composition should open the clip |
| **Several assets in one shot** (two characters, a character with a prop in a location) | **stage a first frame** - compose the assets with `image_gen`/`image_edit` (seeded from their references), pin it as `first_frame`, and pass each asset's reference in `images` so identities hold through the motion |
| A seamless loop | the same image as `first_frame` and `last_frame` |
| An exact start and end (a reveal, a transition, day to night) | `first_frame` + `last_frame` |
| A continuous take split across shots (the action keeps going, no cut) | `first_frame` = the **actual last frame of the previous shot's generated video** (extract it with `ffmpeg -sseof -0.05 -i shot1.mp4 -frames:v 1`), plus the recurring references in `images`; never a re-staged still; if the subject travels, stage shot 2's `last_frame` further along the path so the motion continues instead of stalling |
| A cut to a new setup (new location or angle, same characters) | stage a new first frame seeded from the references, and carry identity with the same references in `images`; do not pin the previous shot's frame |
| A subject that must **travel** across the shot (a boat drifting downstream, a character crossing) | pin `first_frame` at the start position **and** `last_frame` at the end position - stage the end frame with `image_edit` from the start frame ("same scene, the boat now at the right third") - and describe the path; never ask the camera to hold the subject "in the same position" unless a locked-off shot is the point |
| A subject that speaks | `voices` and the line in the prompt |
| A beat that must land at a specific moment | `keyframes` |

Staging a first frame is worth the extra generation when the shot composes multiple assets or the opening composition matters; a single-subject shot can go straight from its reference.

**Stage the subject *in* the scene, as one render.** A staged frame is a single coherent image - subject, setting, light and style rendered together (`image_gen` of the whole shot, or `image_edit` that places the subject into the scene and relights it in the scene's style). Never paste a cut-out onto a backdrop: a flat, cel-shaded or studio-lit reference dropped into a photoreal location reads as a sticker and animates like one. When a reference's style differs from the target look (a game sprite for a cinematic shot), restyle it into the target first and use *that* as the identity reference; when in doubt, generate the scene without the reference and carry identity through `images` only.

A named real person or group is never `image_gen`'d - not as the reference and not as a staged frame. Reference-first applies to video exactly as to images: a verified real photo, edited into the shot with `image_edit`, then passed in `images` / `first_frame`; with no suitable reference, ask for one and stop.

### Think in shots

Build video as a planned sequence of short shots, not one long take:

1. **Plan the story as shots** - break the idea into distinct shots, one beat each.
2. **Favor frequent, short shots** - prefer more 6s shots over fewer long ones; more cuts keep it dynamic and interesting.
3. **Build the references once** - a single sheet for the cast and key props (*Consistency across shots and panels*), then a canonical image per recurring location.
4. **Stage and animate each shot** per the table above.
5. **Assemble with FFmpeg** using stream copy so there's no quality loss: `ffmpeg -f concat ... -c copy` - never re-encode. Keep every shot at the same resolution and frame rate so the copy works.

Key behaviors:

- **Prompt-craft:** one short, vivid moment in present tense with a clear camera movement, in 1-2 sentences.
- **Motion must be visible:** state motion as a change of position in frame (from where to where, how far), not as a verb ("drifts", "moves") - video models turn bare verbs into bobbing in place. After generating, extract the first and last frame and check the subject actually moved; if it didn't when it should have, don't accept the clip - re-prompt with explicit start/end positions or pin a staged `last_frame`.
- **Minimal but interesting:** keep each shot to one clear subject and a single, simple motion or camera move. Avoid complex or multi-action animation (models handle it poorly); make the shot interesting through composition, lighting, and a strong moment, not busy motion.
- **Complex first frame?** An intricate frame (busy geometry, fine detail, heavy reflections) warps when animated. If you must use it, keep the subject fixed and move only the camera (slow push-in, orbit, or parallax), or break it into tighter, simpler shots. Stage a simpler, animation-friendly frame up front instead of animating a busy one.
- **Loops:** pin the same image as `first_frame` and `last_frame`; don't repeat a clip unless asked.
- **Aspect ratio:** set `aspect_ratio` explicitly and match it to the pinned frames and references; don't re-crop an existing video.
- **Duration:** 1-15s (default 6; prefer 6s shots).
- **Real people:** reference-first - drive the video from a verified reference image; never animate a named person without one.
