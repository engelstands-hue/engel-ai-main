---
name: pdf
description: Read, create, and transform PDF files. Covers pulling text and tables out of PDFs, generating new PDFs, merging and splitting documents, rotating pages, watermarking, encrypting or removing passwords, extracting embedded images, running OCR on scanned documents, and filling out PDF forms including official tax forms. Apply this skill whenever a task involves a .pdf file as input or deliverable.
user-invocable: false
---

# Working with PDFs

Task-oriented recipes for PDF work, built around three Python libraries (`pypdf`, `pdfplumber`, `reportlab`) and the poppler-utils / qpdf command-line suites.

Companion documents in this directory — open them when the task calls for it:

- `forms.md` — required reading before filling out any PDF form
- `tax.md` — required reading before preparing the official tax forms bundled under `forms/`
- `reference.md` — deeper material: pypdfium2 rendering, JavaScript libraries (pdf-lib, pdfjs-dist), advanced qpdf/poppler flags, performance tuning, and troubleshooting

## Choosing a Tool

| Goal | Reach for |
|------|-----------|
| Pull out plain text | `pdfplumber` or `pdftotext` |
| Pull out tables | `pdfplumber` (`extract_tables`) |
| Combine documents | `pypdf` or `qpdf` |
| Break a document apart | `pypdf` (one writer per output) |
| Produce a new PDF | `reportlab` (Canvas for absolute layout, Platypus for flowing documents) |
| Grab embedded images | `pdfimages` |
| Render pages as pictures | `pdftoppm` / `pdf2image` |
| OCR a scanned document | `pytesseract` + `pdf2image` |
| Fill out a form | see `forms.md` |

## Getting Content Out of a PDF

### Text

```python
import pdfplumber

with pdfplumber.open("report.pdf") as doc:
    full_text = "\n".join(pg.extract_text() or "" for pg in doc.pages)
```

From the shell, `pdftotext` is quickest; `-layout` keeps the visual column structure and `-f`/`-l` bound the page range:

```bash
pdftotext -layout report.pdf report.txt
pdftotext -f 2 -l 4 report.pdf middle_pages.txt
```

### Tables

`pdfplumber` returns each table as a list of rows; feed them straight into pandas when you need to reshape or export:

```python
import pandas as pd
import pdfplumber

frames = []
with pdfplumber.open("report.pdf") as doc:
    for pg in doc.pages:
        for tbl in pg.extract_tables():
            if tbl:
                frames.append(pd.DataFrame(tbl[1:], columns=tbl[0]))

if frames:
    pd.concat(frames, ignore_index=True).to_excel("tables.xlsx", index=False)
```

### Document Metadata

```python
from pypdf import PdfReader

info = PdfReader("report.pdf").metadata
for key in ("title", "author", "subject", "creator"):
    print(key, "=", getattr(info, key))
```

### Embedded Images vs. Page Renders

These are different operations — pick the right one:

- `pdfimages -all report.pdf img/fig` copies the *original bitmap objects* embedded in the file, untouched by page layout.
- `pdftoppm -png -r 300 report.pdf pages/pg` *rasterizes* whole pages — text, vectors, and annotations included — producing what is effectively a screenshot of each page.

A rendered page is never a substitute for an extracted image, and vice versa.

### Scanned Documents (OCR)

Scanned PDFs contain pictures of text, so extraction tools return nothing useful. Rasterize first, then OCR each page:

```python
# pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

pages = convert_from_path("scan.pdf")
recognized = [pytesseract.image_to_string(img) for img in pages]
print("\n\n".join(recognized))
```

## Reorganizing Pages

### Combine Documents

```python
from pypdf import PdfWriter

writer = PdfWriter()
for path in ["intro.pdf", "body.pdf", "appendix.pdf"]:
    writer.append(path)

with open("combined.pdf", "wb") as out:
    writer.write(out)
```

Or from the shell:

```bash
qpdf --empty --pages intro.pdf body.pdf appendix.pdf -- combined.pdf
```

### Split into Pieces

```python
from pypdf import PdfReader, PdfWriter

src = PdfReader("combined.pdf")
for idx, pg in enumerate(src.pages, start=1):
    part = PdfWriter()
    part.add_page(pg)
    with open(f"part_{idx}.pdf", "wb") as out:
        part.write(out)
```

`qpdf` handles page ranges without any code:

```bash
qpdf combined.pdf --pages . 1-5 -- first_five.pdf
```

### Rotate

```python
from pypdf import PdfReader, PdfWriter

src = PdfReader("sideways.pdf")
writer = PdfWriter()
for pg in src.pages:
    writer.add_page(pg)
writer.pages[0].rotate(90)  # clockwise degrees; must be a multiple of 90

with open("upright.pdf", "wb") as out:
    writer.write(out)
```

### Stamp a Watermark

Overlay one PDF page (the watermark) onto every page of another:

```python
from pypdf import PdfReader, PdfWriter

stamp = PdfReader("stamp.pdf").pages[0]
src = PdfReader("contract.pdf")
writer = PdfWriter()

for pg in src.pages:
    pg.merge_page(stamp)
    writer.add_page(pg)

with open("stamped.pdf", "wb") as out:
    writer.write(out)
```

### Passwords

```python
from pypdf import PdfWriter

writer = PdfWriter()
writer.append("private.pdf")
writer.encrypt(user_password="open-me", owner_password="admin-key")

with open("locked.pdf", "wb") as out:
    writer.write(out)
```

Removing a known password is a one-liner:

```bash
qpdf --password=open-me --decrypt locked.pdf unlocked.pdf
```

## Generating PDFs with reportlab

Two APIs, two mindsets:

- **Canvas** — you place every element at explicit coordinates. The origin is the *bottom-left* corner of the page and y grows upward, so "1 inch from the top" is `page_height - inch - element_height`.
- **Platypus** — you build a `story` list of flowables (`Paragraph`, `Table`, `Image`, `Spacer`, `PageBreak`) and the layout engine paginates for you. Prefer this for anything document-like.

### Minimal Examples

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("note.pdf", pagesize=letter)
_, page_h = letter
c.drawString(72, page_h - 72, "Placed one inch from the top-left corner.")
c.line(72, page_h - 90, 400, page_h - 90)
c.save()
```

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

styles = getSampleStyleSheet()
story = [
    Paragraph("Annual Summary", styles["Title"]),
    Spacer(1, 12),
    Paragraph("Body text flows and wraps automatically. " * 15, styles["Normal"]),
    PageBreak(),
    Paragraph("Second Section", styles["Heading1"]),
]
SimpleDocTemplate("summary.pdf", pagesize=letter).build(story)
```

### Placing Images

Keep the aspect ratio: derive the missing dimension from the source image, or let reportlab do it when fitting a box.

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

c = canvas.Canvas("figure.pdf", pagesize=letter)
_, page_h = letter

src = ImageReader("chart.png")
src_w, src_h = src.getSize()
w = 4.5 * inch
h = w * src_h / src_w

# bottom-left origin: subtract the image height to hang it below the top margin
c.drawImage(src, inch, page_h - inch - h, width=w, height=h)
c.save()
```

To fit an image inside a fixed region without distortion:

```python
c.drawImage("photo.jpg", box_x, box_y, width=box_w, height=box_h,
            preserveAspectRatio=True, anchor="c")
```

In Platypus, images are flowables — size them yourself and let the engine position them:

```python
from reportlab.platypus import Image

pic = Image("logo.png", width=w, height=h, hAlign="CENTER")
story.append(pic)
```

Prefer `drawImage` over `drawInlineImage`; it registers the image once as a shared object, so repeated use is smaller and faster.

### Subscripts and Superscripts

Do **not** type Unicode sub/superscript characters (₂, ⁹, …) — reportlab's built-in fonts lack those glyphs and they render as black rectangles. Use inline markup inside a `Paragraph` instead:

```python
Paragraph("H<sub>2</sub>O and E = mc<super>2</super>", styles["Normal"])
```

When drawing directly on a Canvas (no `Paragraph`), simulate the effect by shrinking the font and shifting the baseline manually.

### Tables

Two non-negotiable rules, both consequences of how `Table` lays out cells:

1. **Every cell — headers included — goes inside a `Paragraph`.** Bare strings never wrap; long values run over neighboring cells or off the page. `Paragraph` cells also accept inline markup (`<b>`, `<i>`, `<sub>`, `<super>`).
2. **Pass explicit `colWidths`, sized by content.** Equal-width columns squeeze prose and waste space on short IDs. Budget most of the printable width (letter with 1" margins ≈ 6.5", landscape ≈ 9") to the prose-heavy columns.

```python
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

body = getSampleStyleSheet()["BodyText"]

rows = [
    [Paragraph("<b>ID</b>", body), Paragraph("<b>Name</b>", body), Paragraph("<b>Notes</b>", body)],
    [Paragraph("1", body), Paragraph("Widget", body),
     Paragraph("Long prose wraps cleanly inside its column instead of spilling over.", body)],
]

grid = Table(rows, colWidths=[0.5 * inch, 1.5 * inch, 4.5 * inch], repeatRows=1)
grid.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
]))

SimpleDocTemplate("grid.pdf", pagesize=letter).build([grid])
```

Also: `repeatRows=1` reprints the header when a table crosses a page break; `VALIGN TOP` keeps wrapped rows tidy; and when content is genuinely too wide, switch to `landscape(letter)` rather than shrinking columns into illegibility.

## Always Verify Visually

After producing or modifying any PDF — especially after filling form fields, where name-to-label mappings are frequently wrong — render each page and look at it:

```bash
pdftoppm -png -r 300 -f 1 -l 1 result.pdf /tmp/check
pdftoppm -png -r 300 -f 2 -l 2 result.pdf /tmp/check_p2
```

pdftoppm appends the page number to the output prefix, so these commands write `/tmp/check-1.png` and `/tmp/check_p2-2.png`. View each PNG and confirm every value sits beside its intended label, nothing overlaps, and nothing is clipped. Inspecting the raw PDF objects cannot catch these problems; rendering does.

## Forms and Tax Forms

- Any form-filling task: read `forms.md` first and follow its steps in order. It covers both PDFs with real fillable fields and flat/scanned forms that need positioned text annotations, with helper scripts under `scripts/`.
- Tax returns: read `tax.md`. The deliverable is always the official IRS form from `forms/`, filled in — never a homemade summary document.
