# Filling Out PDF Forms

Work through this document in order — every step exists because skipping it produces broken output. All helper scripts live in `scripts/` relative to this file.

First, determine which kind of form you have:

```bash
python scripts/check_fillable_fields.py <file.pdf>
```

- If it reports fillable fields, follow **Path 1: Forms with Fillable Fields** below.
- If it reports none, follow **Path 2: Flat Forms (Text Annotations)**.

---

# Path 1: Forms with Fillable Fields

## 1. Dump the field inventory

```bash
python scripts/extract_form_field_info.py <input.pdf> <field_info.json>
```

The output is a JSON array, one entry per form field:

- `field_id` — the exact identifier the fill step requires
- `label` — human-readable purpose (e.g. "Your first name and middle initial", "Line 11b - Adjusted gross income"); match values to fields using this
- `type` — one of "text", "checkbox", "radio_group", "choice"
- `page` — 1-based page number

Sample output:

```json
[
  {"field_id": "f1_14[0]", "label": "Your first name and middle initial", "type": "text", "page": 1},
  {"field_id": "f1_15[0]", "label": "Last name", "type": "text", "page": 1},
  {"field_id": "f1_16[0]", "label": "Your social security number", "type": "text", "page": 1},
  {"field_id": "f2_01[0]", "label": "11b. Amount from line 11a (adjusted gross income)", "type": "text", "page": 2},
  {"field_id": "f2_02[0]", "label": "12e. Standard deduction or itemized deductions", "type": "text", "page": 2},
  {"field_id": "c2_1[0]",  "label": "12a. You as a dependent", "type": "checkbox", "checked_value": "/1", "unchecked_value": "/Off", "page": 2}
]
```

## 2. Write the values file

Build `field_values.json` by copying `field_id` and `page` verbatim from step 1 and attaching a `"value"` to each field you intend to fill:

```json
[
  {"field_id": "f1_14[0]", "page": 1, "value": "Andrew J."},
  {"field_id": "f1_15[0]", "page": 1, "value": "Patterson"},
  {"field_id": "f1_16[0]", "page": 1, "value": "567-89-2241"},
  {"field_id": "f2_01[0]", "page": 2, "value": "118702"},
  {"field_id": "f2_02[0]", "page": 2, "value": "31500"},
  {"field_id": "c2_1[0]",  "page": 2, "value": "/Off"}
]
```

Checkboxes take their `checked_value` (to tick) or `unchecked_value` (to leave blank). Radio groups take one of their listed `radio_options`.

## 3. Fill

```bash
python scripts/fill_fillable_fields.py <input.pdf> <field_values.json> <output.pdf>
```

The script validates every ID and value before writing anything. On errors, correct `field_values.json` and rerun.

## 4. Inspect the result

```bash
python scripts/convert_pdf_to_images.py <output.pdf> <verify_dir/>
```

Look at each rendered page and confirm every value landed beside the correct label. Field IDs are routinely mislabeled in real-world forms — the visual pass is what catches it.

---

# Path 2: Flat Forms (Text Annotations)

Without fillable fields you must place text at explicit coordinates. Get those coordinates from the PDF's internal structure when possible (precise), and fall back to measuring rendered images when not (scanned forms).

## 1. Attempt structure extraction

```bash
python scripts/extract_form_structure.py <input.pdf> form_structure.json
```

The JSON contains:

- **labels** — every text run with exact coordinates (`x0`, `top`, `x1`, `bottom`, in PDF points)
- **lines** — horizontal rules that delimit rows
- **checkboxes** — small square rectangles, with centers
- **row_boundaries** — row top/bottom positions derived from the lines

Decide the route based on what came back: meaningful labels present → **Route A**. Scanned/image-only PDF with no usable labels (e.g. text appears as `(cid:X)` garbage) → **Route B**. Mostly usable with a few gaps → **Hybrid** (below).

## Route A: Coordinates from Structure (preferred)

### A.1 Map out the form

Working from `form_structure.json`, identify:

1. Label groups — adjacent runs forming one label ("Last" + "Name")
2. Rows — labels sharing roughly the same `top`
3. Entry areas — the space starting just past each label's right edge
4. Checkboxes — take their rectangles directly

Coordinate convention here: y = 0 at the **top** of the page, increasing downward.

### A.2 Note what extraction misses

Structure extraction commonly overlooks circular checkboxes (only squares are detected), decorative or non-standard controls, and faint elements. If the rendered page shows a field that `form_structure.json` lacks, handle that field via the Hybrid approach.

### A.3 Build fields.json in PDF coordinates

Derive each entry box from the structure:

- Text entries: `x0 = label.x1 + 5`; `x1` = next label's `x0` or the row boundary; `top` = label top; `bottom` = the rule below, or label bottom + row height.
- Checkboxes: copy the detected rectangle as-is into `entry_bounding_box`.

Declare the pages with `pdf_width`/`pdf_height` — these key names tell the fill script the coordinates are PDF points:

```json
{
  "pages": [
    {"page_number": 1, "pdf_width": 612, "pdf_height": 792}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Last name entry field",
      "field_label": "Last Name",
      "label_bounding_box": [43, 63, 87, 73],
      "entry_bounding_box": [92, 63, 260, 79],
      "entry_text": {"text": "Smith", "font_size": 10}
    },
    {
      "page_number": 1,
      "description": "US Citizen Yes checkbox",
      "field_label": "Yes",
      "label_bounding_box": [260, 200, 280, 210],
      "entry_bounding_box": [285, 197, 292, 205],
      "entry_text": {"text": "X"}
    }
  ]
}
```

## Route B: Coordinates by Measuring Images (fallback)

### B.1 Render the pages

```bash
python scripts/convert_pdf_to_images.py <input.pdf> <images_dir/>
```

### B.2 Rough pass

Study each page image and note, approximately: field labels and where they sit, entry areas (lines, boxes, blanks), and checkbox positions. Rough pixel estimates are fine at this stage.

### B.3 Zoom in to pin down each field

Precision requires cropping around each estimate and re-examining. Crop with ImageMagick (`convert` works if `magick` is absent):

```bash
magick <page_image> -crop <width>x<height>+<x>+<y> +repage <crop.png>
```

`<x>,<y>` is the crop's top-left corner (your estimate minus some padding); make the crop the field area plus ~50 px on each side. Example for a "Name" field near (100, 150):

```bash
magick images_dir/page_1.png -crop 300x80+50+120 +repage crops/name_field.png
```

In the crop, find the exact pixels where the entry area starts (past the label), where it ends, and its top and bottom. Then translate back to full-page pixels by adding the crop offset:

- `full_x = x_in_crop + crop_offset_x`
- `full_y = y_in_crop + crop_offset_y`

So a crop taken at (50, 120) whose entry box starts at (52, 18) internally gives `entry_x0 = 102`, `entry_top = 138`. Batch nearby fields into shared crops where practical.

### B.4 Build fields.json in image coordinates

Same shape as Route A, but declare pages with `image_width`/`image_height` — that signals pixel coordinates:

```json
{
  "pages": [
    {"page_number": 1, "image_width": 1700, "image_height": 2200}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Last name entry field",
      "field_label": "Last Name",
      "label_bounding_box": [120, 175, 242, 198],
      "entry_bounding_box": [255, 175, 720, 218],
      "entry_text": {"text": "Smith", "font_size": 10}
    }
  ]
}
```

## Hybrid: Structure for Most, Visual for the Rest

When extraction covered most fields but missed a few:

1. Use Route A for everything the structure captured.
2. Render the pages and apply Route B's zoom technique to the missing fields only.
3. Convert those measured pixel positions into PDF points:
   - `pdf_x = image_x * (pdf_width / image_width)`
   - `pdf_y = image_y * (pdf_height / image_height)`
4. Keep **one** coordinate system in `fields.json` — after converting, declare pages with `pdf_width`/`pdf_height`.

## 2. Validate the boxes

Run this before every fill, regardless of route:

```bash
python scripts/check_bounding_boxes.py fields.json
```

It flags overlapping boxes (which produce collided text) and entry boxes too short for their font size. Resolve every reported problem first.

## 3. Fill

```bash
python scripts/fill_pdf_form_with_annotations.py <input.pdf> fields.json <output.pdf>
```

The script reads the page-size keys to detect which coordinate system you used and converts internally.

## 4. Inspect the result

```bash
python scripts/convert_pdf_to_images.py <output.pdf> <verify_images/>
```

If text landed in the wrong place:

- Route A — confirm the coordinates came from `form_structure.json` and pages declare `pdf_width`/`pdf_height`
- Route B — confirm the declared image dimensions match the rendered images and the pixel measurements are right
- Hybrid — recheck the pixel-to-point conversion on the visually measured fields
