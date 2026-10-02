# Troubleshooting a document

Your document converts, but something in the output is wrong. This page helps you find
out where the problem is, fix it, and keep it fixed with a test.

## Step 1: read the warnings

Every feature that was left out or approximated prints one `WARNING:` line (each message
only once). Many surprises are explained there: a graphic that was not found, a hidden
condition, a variable with page numbers, a frame with drawing objects.

## Step 2: which side is wrong?

```
python3 mif2md.py --dump input.mif
```

prints the document model: what the converter understood, before any Markdown or
AsciiDoc is written. Each block shows the paragraph tag it came from:

```
H2 [Heading2] Tables and graphics  #tables-and-graphics
P  [Body] See <link #introduction: “Introduction” on page <page of #introduction: 2>> …
LIST bulleted
  - P  [Bulleted] First bullet
    LIST bulleted
      - P  [Bulleted2] Nested bullet
TABLE 3 columns (113, 113, 227 pt) "Table 1: Sample table"
  row 2 (body)
    [1] spans 2 column(s) x 1 row(s) P  [CellBody] Spans two columns
    [2] (covered by a merged cell)
```

Inline markers: `<b:…>`, `<i:…>`, `<code:…>`, `<sup:…>` for formatted text, `<link #id: …>`,
`<anchor #id>`, `<footnote n>` (the footnotes are listed at the end), `<index …>`,
`<image …>`, `<br>` for a forced line break.

- **The dump is wrong** (a heading is a paragraph, a list is not nested, text is
  missing): the problem is in reading MIF – `roles.py`, `formats.py` or `builder.py`.
  Often a mapping file solves it without changing code (step 3).
- **The dump is right, the output is wrong** (text changed, a table is broken, pandoc or
  Asciidoctor complains): the problem is in the writer, `markdown.py` or `asciidoc.py`.

`--list-tags` shows each paragraph tag with its role, which is often the quickest check:

```
python3 mif2md.py --list-tags input.mif
```

## Step 3: fix it with a mapping file

Paragraph roles are guessed from tag names, numbering and fonts. If a guess is wrong for
your document, tell the converter instead of changing code:

```json
{
  "paragraphs": { "Unterüberschrift": "heading3", "Seitenkopf": "skip" },
  "characters": { "Hervorhebung": "italic" }
}
```

```
python3 mif2md.py --map mytags.json input.mif
```

Change the code only if the guess is wrong for documents in general, not just for yours.

## Common symptoms

| Symptom | Likely cause | Where to look |
|---|---|---|
| A heading is a normal paragraph | The tag name is not recognised | `--list-tags`; `--map`; `roles.HEADING` / `NOT_HEADING` |
| A caption or table title became a heading | Its name contains "heading"/"title" | `roles.NOT_HEADING` |
| Heading levels are off by one | Levels are ranked by font size, then by the number in the tag | `Builder._heading_levels`; `--map` with `heading1` … `heading6` |
| Most headings end up at the deepest level | The document has more heading formats (sizes and numbers) than Markdown and AsciiDoc have levels; each one gets its own rank | `--map` with `heading1` … `heading6` to put several formats on one level |
| The first heading is missing | It was taken as the document title (tag `Title`/`Titel`) | `roles.TITLE`, `Builder.build` |
| A list is not a list | The numbering format is a word ("Step <n+>:"), not a bullet or counter | `formats.numbering`; `--map` with `bullet`/`numbered` |
| A list is nested wrongly | List levels follow the first-line indent (`PgfFIndent`) | `Builder._group`; `--dump`; check the indents in the MIF |
| A paragraph after a list item should belong to the item (or should not) | It continues the item if its left indent (`PgfLIndent`) is at least the item's | `Builder._group` |
| A numbered list does not restart | Only `<n=1>` in the numbering format starts a new list | `formats.numbering`, `Builder._group` |
| Text is missing | Hidden conditional text; a flow that is not on body pages; the `skip` role | `Builder._hidden_conditions`, `_body_flows`; `--map` |
| Bold or italic is missing, or too much is bold | Styles are relative to the paragraph font | `Builder.char_style`; character roles in `--map` |
| A whole paragraph is a code block | Its font is monospaced | `formats.MONO`; `--map` with `paragraph` |
| Wrong characters (only in MIF 7) | A FrameRoman code that is not Mac Roman | `mif.FRAMEROMAN` and its source, Adobe's character set tables |
| A cross-reference is plain text | Target marker not found, or the target is in another file | Warning text; `Builder._xref_targets` |
| "on page" without a number | Pandoc only fills `\pageref` in LaTeX/PDF output | Expected for other pandoc targets |
| A graphic is missing | File not found, embedded in the MIF, or a frame with only drawings | Warnings; `Builder.image` lookup order |
| Text changed in the output (`*`, `_`, `--`, `<<` …) | Escaping | `markdown.escape`, `asciidoc.AsciiDocWriter.escape`; add a test (below) |
| Pandoc PDF fails: `Unicode character … not set up` | pdflatex | Use `--pdf-engine=lualatex` |
| Pandoc PDF fails on an image | SVG without `rsvg-convert`, or a format LaTeX cannot use | Warnings; convert the graphic to PNG/PDF |
| A grid table looks broken | A line longer than its cell | `MarkdownWriter.grid_table` |

## Step 4: make a small test case

Never put a real document into the repository. Rebuild only the part that fails:

1. Find the statements involved in your MIF (see the grep patterns in
   [mif-primer.md](mif-primer.md#finding-your-way-in-a-large-mif-file)). Remember that a
   paragraph's format may come from the paragraph before it in the file.
2. Reproduce them with neutral text, either
   - in `samples/sample/make_sample.py`, if the feature belongs in the sample document
     (then run `UPDATE_EXPECTED=1 python3 -m unittest discover tests` and check the
     changes in `samples/sample/expected/` line by line), or
   - as a few lines of MIF in a unit test, for a narrow case:

     ```python
     from mifdoc import mif
     from mifdoc.builder import Builder

     root = mif.parse("""
     <PgfCatalog <Pgf <PgfTag `Body'> <PgfFont <FFamily `Times'>>>>
     <Page <PageType BodyPage> <TextRect <ID 1> <ShapeRect 0 0 400 600>>>
     <TextFlow <Para <PgfTag `Body'> <ParaLine <TextRectID 1> <String `x'>>>>
     """)
     doc = Builder(root, 'test.mif').build()
     ```
3. For a text that is escaped wrongly, add it to the `TRICKY` list in
   `tests/test_mifdoc.py`. The round-trip tests then check it through pandoc and
   Asciidoctor (if installed).
4. Fix the code, run `python3 -m unittest discover tests`, and convert your real
   document again.

If you report a problem instead of fixing it, the small MIF snippet and the `--dump`
output of it are the most useful things to include.
