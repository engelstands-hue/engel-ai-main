# PDF Reference — Advanced Topics

Material that goes beyond the day-to-day recipes in SKILL.md: high-performance rendering, JavaScript tooling, less-common CLI flags, precision extraction, and troubleshooting.

## Fast Rendering with pypdfium2

pypdfium2 wraps PDFium (the Chromium PDF engine) and is the strongest choice for turning pages into images quickly. It also serves as a permissively licensed stand-in for PyMuPDF.

```python
import pypdfium2 as pdfium

doc = pdfium.PdfDocument("paper.pdf")

# Single page at 2x resolution
first = doc[0].render(scale=2.0, rotation=0)
first.to_pil().save("page_1.png", "PNG")

# Whole document as JPEGs
for idx, pg in enumerate(doc, start=1):
    pg.render(scale=1.5).to_pil().save(f"page_{idx}.jpg", "JPEG", quality=90)
```

It can also extract text:

```python
doc = pdfium.PdfDocument("paper.pdf")
for idx, pg in enumerate(doc, start=1):
    print(f"page {idx}: {len(pg.get_text())} chars")
```

## JavaScript: pdf-lib

pdf-lib (MIT) creates and edits PDFs in any JS runtime, and is notably good at preserving form structure during edits.

Open and extend an existing document:

```javascript
import { PDFDocument } from 'pdf-lib';
import fs from 'fs';

const doc = await PDFDocument.load(fs.readFileSync('input.pdf'));
console.log(`${doc.getPageCount()} pages`);

const extra = doc.addPage([600, 400]);
extra.drawText('Appended page', { x: 100, y: 300, size: 16 });

fs.writeFileSync('extended.pdf', await doc.save());
```

Build a document from nothing, with fonts, shapes, and tabular text:

```javascript
import { PDFDocument, rgb, StandardFonts } from 'pdf-lib';
import fs from 'fs';

const doc = await PDFDocument.create();
const regular = await doc.embedFont(StandardFonts.Helvetica);
const bold = await doc.embedFont(StandardFonts.HelveticaBold);

const page = doc.addPage([595, 842]); // A4 in points
const { width, height } = page.getSize();

page.drawText('Invoice #12345', {
  x: 50, y: height - 50, size: 18, font: bold, color: rgb(0.2, 0.2, 0.8),
});
page.drawRectangle({
  x: 40, y: height - 100, width: width - 80, height: 30, color: rgb(0.9, 0.9, 0.9),
});

const rows = [
  ['Item', 'Qty', 'Price', 'Total'],
  ['Widget', '2', '$50', '$100'],
  ['Gadget', '1', '$75', '$75'],
];
let y = height - 150;
for (const row of rows) {
  row.forEach((cell, col) => {
    page.drawText(cell, { x: 50 + col * 120, y, size: 12, font: regular });
  });
  y -= 25;
}

fs.writeFileSync('invoice.pdf', await doc.save());
```

Selective merging — copy chosen pages between documents:

```javascript
import { PDFDocument } from 'pdf-lib';
import fs from 'fs';

const target = await PDFDocument.create();
const a = await PDFDocument.load(fs.readFileSync('a.pdf'));
const b = await PDFDocument.load(fs.readFileSync('b.pdf'));

(await target.copyPages(a, a.getPageIndices())).forEach((p) => target.addPage(p));
(await target.copyPages(b, [0, 2, 4])).forEach((p) => target.addPage(p));

fs.writeFileSync('merged.pdf', await target.save());
```

## JavaScript: pdfjs-dist

PDF.js (Apache) is Mozilla's renderer, aimed at displaying PDFs in the browser.

```javascript
import * as pdfjsLib from 'pdfjs-dist';

pdfjsLib.GlobalWorkerOptions.workerSrc = './pdf.worker.js'; // required for performance

const doc = await pdfjsLib.getDocument('paper.pdf').promise;
const page = await doc.getPage(1);
const viewport = page.getViewport({ scale: 1.5 });

const canvas = document.createElement('canvas');
canvas.width = viewport.width;
canvas.height = viewport.height;
await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
document.body.appendChild(canvas);
```

Text extraction, with per-item positions available when you need layout awareness:

```javascript
const doc = await pdfjsLib.getDocument('paper.pdf').promise;
for (let n = 1; n <= doc.numPages; n++) {
  const content = await (await doc.getPage(n)).getTextContent();
  const plain = content.items.map((it) => it.str).join(' ');
  const positioned = content.items.map((it) => ({
    text: it.str, x: it.transform[4], y: it.transform[5],
    width: it.width, height: it.height,
  }));
  console.log(`--- page ${n} ---\n${plain}`);
}
```

Reading annotations:

```javascript
const doc = await pdfjsLib.getDocument('annotated.pdf').promise;
for (let n = 1; n <= doc.numPages; n++) {
  for (const a of await (await doc.getPage(n)).getAnnotations()) {
    console.log(a.subtype, a.contents, a.rect);
  }
}
```

## poppler-utils Beyond the Basics

```bash
# Text with bounding boxes as XML — the basis for structured extraction
pdftotext -bbox-layout paper.pdf layout.xml

# Page renders: pick resolution, range, and format
pdftoppm -png -r 300 paper.pdf out/pg
pdftoppm -png -r 600 -f 1 -l 3 paper.pdf out/hires
pdftoppm -jpeg -jpegopt quality=85 -r 200 paper.pdf out/jpg

# Embedded images: list first, then pull what you need
pdfimages -list paper.pdf
pdfimages -all paper.pdf img/fig     # original formats
pdfimages -j -p paper.pdf img/pg     # JPEG, page numbers in names
```

## qpdf Beyond the Basics

Page surgery:

```bash
qpdf --split-pages=3 big.pdf chunk_%02d.pdf                       # 3 pages per output file
qpdf big.pdf --pages big.pdf 1,3-5,8,10-end -- cherry_picked.pdf  # arbitrary ranges
qpdf --empty --pages a.pdf 1-3 b.pdf 5-7 c.pdf 2,4 -- spliced.pdf # cross-document
```

Optimization and repair:

```bash
qpdf --linearize input.pdf web_ready.pdf        # fast first-page load over HTTP
qpdf --optimize-level=all input.pdf smaller.pdf
qpdf --check suspect.pdf                        # diagnose structure problems
qpdf --fix-qdf damaged.pdf repaired.pdf
```

Encryption with granular permissions:

```bash
qpdf --encrypt user_pw owner_pw 256 --print=none --modify=none -- input.pdf locked.pdf
qpdf --show-encryption locked.pdf
qpdf --password=user_pw --decrypt locked.pdf unlocked.pdf
```

## Precision Extraction with pdfplumber

Character-level coordinates and region-scoped extraction:

```python
import pdfplumber

with pdfplumber.open("paper.pdf") as doc:
    pg = doc.pages[0]

    for ch in pg.chars[:10]:
        print(f"{ch['text']!r} at ({ch['x0']:.1f}, {ch['y0']:.1f})")

    header = pg.within_bbox((100, 100, 400, 200)).extract_text()
```

Tables that resist default detection often yield to explicit strategies, and rendering the page with detected lines overlaid is the fastest way to debug:

```python
with pdfplumber.open("gnarly_table.pdf") as doc:
    pg = doc.pages[0]
    tables = pg.extract_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "intersection_tolerance": 15,
    })
    pg.to_image(resolution=150).save("debug_layout.png")
```

## reportlab Table Styling

`TableStyle` commands address cell ranges as `(col, row)` pairs, with `-1` meaning "last":

```python
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

data = [
    ["Product", "Q1", "Q2", "Q3", "Q4"],
    ["Widgets", "120", "135", "142", "158"],
    ["Gadgets", "85", "92", "98", "105"],
]

styled = Table(data)
styled.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 14),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
    ("GRID", (0, 0), (-1, -1), 1, colors.black),
]))

doc = SimpleDocTemplate("sales.pdf")
doc.build([Paragraph("Quarterly Sales", getSampleStyleSheet()["Title"]), styled])
```

## Batch Processing Pattern

When sweeping a directory, isolate failures per file so one bad PDF doesn't sink the run:

```python
import glob
import logging
import os

from pypdf import PdfReader, PdfWriter

log = logging.getLogger(__name__)

def merge_directory(input_dir: str, output_path: str) -> None:
    writer = PdfWriter()
    for path in sorted(glob.glob(os.path.join(input_dir, "*.pdf"))):
        try:
            writer.append(path)
        except Exception:
            log.exception("skipping %s", path)
    with open(output_path, "wb") as out:
        writer.write(out)

def dump_texts(input_dir: str) -> None:
    for path in sorted(glob.glob(os.path.join(input_dir, "*.pdf"))):
        try:
            text = "".join(pg.extract_text() or "" for pg in PdfReader(path).pages)
        except Exception:
            log.exception("skipping %s", path)
            continue
        with open(path.removesuffix(".pdf") + ".txt", "w", encoding="utf-8") as f:
            f.write(text)
```

## Cropping Pages

Shrink the visible page area by adjusting the media box (units are points, origin bottom-left):

```python
from pypdf import PdfReader, PdfWriter

src = PdfReader("input.pdf")
pg = src.pages[0]
pg.mediabox.left = 50
pg.mediabox.bottom = 50
pg.mediabox.right = 550
pg.mediabox.top = 750

writer = PdfWriter()
writer.add_page(pg)
with open("cropped.pdf", "wb") as out:
    writer.write(out)
```

## Performance Notes

- **Huge documents**: work page-by-page (pypdfium2 iterates lazily) or pre-split with `qpdf --split-pages` rather than loading everything at once.
- **Text**: `pdftotext` is the fastest path to plain text; use pdfplumber only when you need structure. Avoid `pypdf`'s `extract_text` on very large files.
- **Images**: `pdfimages` (copies embedded objects) is far cheaper than rendering; render at low DPI for previews and reserve high DPI for final output.
- **Forms**: pdf-lib preserves form structure better than most alternatives; validate field names before filling.
- **Memory**: split-then-process keeps the working set bounded:

```python
from pypdf import PdfReader, PdfWriter

def split_into_chunks(path: str, pages_per_chunk: int = 10) -> None:
    src = PdfReader(path)
    for start in range(0, len(src.pages), pages_per_chunk):
        chunk = PdfWriter()
        for pg in src.pages[start : start + pages_per_chunk]:
            chunk.add_page(pg)
        with open(f"chunk_{start // pages_per_chunk}.pdf", "wb") as out:
            chunk.write(out)
```

## Troubleshooting

**Password-protected input** — decrypt in place before reading pages:

```python
from pypdf import PdfReader

reader = PdfReader("locked.pdf")
if reader.is_encrypted:
    reader.decrypt("the-password")
```

**Corrupted files** — let qpdf diagnose and rewrite:

```bash
qpdf --check broken.pdf
qpdf --replace-input broken.pdf
```

**Extraction returns garbage or nothing** — the pages are probably scans; fall back to OCR:

```python
import pytesseract
from pdf2image import convert_from_path

def ocr_pdf(path: str) -> str:
    return "".join(pytesseract.image_to_string(img) for img in convert_from_path(path))
```

## Licenses

| Tool | License |
|------|---------|
| pypdf | BSD |
| pdfplumber | MIT |
| pypdfium2 | Apache/BSD |
| reportlab | BSD |
| poppler-utils | GPL-2 |
| qpdf | Apache |
| pdf-lib | MIT |
| pdfjs-dist | Apache |
