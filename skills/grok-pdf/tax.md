# Preparing Tax Forms

The deliverable is always an official IRS form from `forms/`, filled in. Never substitute a homemade summary, a Word document, or a custom-built PDF.

**Whole dollars only.** Round every amount to the nearest dollar; no line gets cents.

Workflow:

1. Read `forms.md` and follow its fillable-fields path (Path 1).
2. Pick the correct blank form(s) out of `forms/`.
3. Use the helpers in `scripts/`:
   - `check_fillable_fields.py <form.pdf>` — confirm the form has fillable fields
   - `extract_form_field_info.py <form.pdf> <output.json>` — dump field IDs and labels
   - `fill_fillable_fields.py <form.pdf> <values.json> <output.pdf>` — write the values (details in `forms.md`)
   - `convert_pdf_to_images.py <form.pdf> <outdir>` — render pages for the visual check
4. Fill each form using the extracted field IDs and your computed values.
5. Render every filled form to images and visually confirm each value sits on the correct line.
