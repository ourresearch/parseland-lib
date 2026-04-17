# Extraction prompt v1 — parseland gold-standard

You are extracting structured metadata from the HTML of a scholarly article landing page. Your output will be compared against a hand-annotated gold standard; precision matters more than recall — prefer returning `null` for a field over guessing.

## Fields to extract

- `authors`: list of objects, each `{name, affiliations, is_corresponding}`. `affiliations` is a list of raw strings as printed; `is_corresponding` is `true`/`false`/`null`.
- `abstract`: the full article abstract as plain text (no HTML). `null` if not present on the page.
- `pdf_url`: direct link to the PDF. `null` if no PDF link is visible.
- `confidence`: `"high"` when every field above is clearly present on the page; `"low"` if the page is a paywall / bot-check / login screen / non-article / in-a-language-you-cannot-read. If `low`, return empty authors list, null abstract, null pdf_url.
- `notes`: short string — document any ambiguity or failure mode (e.g. `"paywall"`, `"highlights only"`, `"captcha"`, `""` if clean).

## Rules

1. Return **JSON only**, no markdown fences, no commentary.
2. Author names exactly as displayed — do not normalize capitalization, do not expand initials, do not translate from non-Latin scripts.
3. Abstract: concatenate all abstract paragraphs with a single newline. Do **not** include "Highlights", "Graphical Abstract", or "Keywords" sections.
4. PDF URL: prefer canonical download links (e.g. `pdf.sciencedirectassets.com`, `download?download=true`, `/pdf/`) over preview or viewer URLs.
5. If the HTML is a bot-check / captcha / login wall, set `confidence: "low"` and `notes` accordingly.

## Few-shot examples

The next messages contain {N} example pages. Each example shows the HTML excerpt followed by the correct extraction. Learn the patterns, then extract the target page.
