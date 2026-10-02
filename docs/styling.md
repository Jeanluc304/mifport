# Getting closer to the FrameMaker look

Markdown and AsciiDoc carry structure, not layout: a PDF made from them uses the layout of
pandoc's LaTeX template or of the asciidoctor-pdf theme. This page shows how to bring the
PDF closer to the FrameMaker original, and what cannot be reproduced.

## Step 1: let the converter write a style file

```
python3 mif2md.py --style manual.mif      # writes manual.md and manual.pandoc.yaml
python3 mif2adoc.py --style manual.mif    # writes manual.adoc and manual-theme.yml
```

Then:

```
pandoc manual.md --defaults manual.pandoc.yaml -o manual.pdf
asciidoctor-pdf -a pdf-theme=./manual-theme.yml manual.adoc
```

The style file takes these settings from the MIF file:

| FrameMaker setting | Read from | pandoc defaults file | asciidoctor-pdf theme |
|---|---|---|---|
| Page size | `Document` → `DPageSize` | `geometry`: `paperwidth`, `paperheight` | `page.size` |
| Margins | the usual text frame (`TextRect`) of the body pages; without pages `DMargins` | `geometry`: `top`, `bottom`, `left`/`right` (`inner`/`outer` for two-sided documents) | `page.margin` (top, right, bottom, left) |
| Body text size | font of the most used body paragraph format | `fontsize` | `base.font-size` |
| Line spacing | `PgfLeading` of that format | `linestretch` | `base.line-height` |
| Space between paragraphs | `PgfSpAfter` of that format | `\parskip` | `prose.margin-bottom` |
| Title and heading formats (size, bold, italic, sans or serif) | the most used format of each heading level | `\setkomafont{section}` … (KOMA-Script class `scrartcl`) | `heading.h1` … `h6` |
| Space above and below headings | `PgfSpBefore`, `PgfSpAfter` | `\RedeclareSectionCommand[beforeskip, afterskip]` | `heading.hN.margin-top`, `margin-bottom` |
| Code size | the code paragraph format | – | `code.font-size` |
| Fonts | `FFamily` of these formats | `mainfont`, `sansfont`, `monofont` – as comments | `font.catalog` – as comments |

Heading levels: Markdown `#` is LaTeX's `\section`, `##` `\subsection` and so on;
AsciiDoc's document title is `h1` in the theme, `==` is `h2`.

## Step 2: fonts

The fonts are only suggested in comments, because a font that is not installed stops the
PDF conversion. To use them:

- **pandoc:** install the fonts, remove the `#` in front of `mainfont`, `sansfont` and
  `monofont`, and keep `pdf-engine: lualatex` (or use `xelatex`); pdflatex cannot use
  installed system fonts. The names are the font family names as the system knows them
  (`fc-list : family` on Linux).
- **asciidoctor-pdf:** it needs the TTF files. Fill in the `font.catalog` block at the end
  of the theme with the paths of the regular, bold, italic and bold-italic files, and set
  `font-family` in `base` and `heading` to the catalog name.

Fonts are licensed; the fonts of the FrameMaker document may not be available or allowed
on the machine that converts.

Without the fonts, the generated files still give the right page, sizes, spacing and
sans or serif headings, in the default fonts of LaTeX or asciidoctor-pdf.

## Step 3: going further by hand

These are not in the MIF-derived style file, but are easy to add.

**pandoc** – add lines to the `header-includes` list of the generated file (a second
`--defaults` file would replace the list instead of adding to it):

```yaml
    - '\usepackage[automark,headsepline]{scrlayer-scrpage}'   # running header with a rule
    - '\clearpairofpagestyles'
    - '\ohead{\headmark}'                                      # current section, outer side
    - '\ofoot*{\pagemark}'                                     # page number, also on page 1
    - '\usepackage{xcolor}'
    - '\addtokomafont{disposition}{\color[HTML]{1F4E79}}'     # heading colour
```

Numbered headings: `pandoc --number-sections`. A table of contents: `--toc`. Everything
else can go into your own LaTeX template (`pandoc -D latex > my.latex`, then
`--template my.latex`).

**asciidoctor-pdf** – a theme can extend the generated one:

```yaml
extends: ./manual-theme.yml
heading:
  font-color: 1F4E79
header:
  height: 12mm
  recto:
    right:
      content: '{section-title}'
footer:
  recto:
    right:
      content: '{page-number}'
```

Numbered headings: `-a sectnums`; a table of contents: `-a toc`. The asciidoctor-pdf
theming guide lists all keys (table borders and shading, captions, title page, lists).

## What cannot be reproduced

- **Line and page breaks.** LaTeX and asciidoctor-pdf set the text themselves; pages
  break at different places than in FrameMaker.
- **Master pages.** Headers and footers have to be rebuilt as above; graphics and
  decorations of master pages are not converted, and different master pages for
  different pages are not supported.
- **Side heads, run-in heads, multi-column text frames** and **anchored frames at fixed
  positions** (outside the column, text running around them): graphics are placed below
  their paragraph or in the line.
- **FrameMaker's numbering formats.** pandoc and Asciidoctor number headings, tables and
  figures in their own style.
- **Table rulings and shading** per table format, **paragraph rules and backgrounds**:
  only one style for all tables and paragraphs, set by hand in the template or theme.
- **Footnotes in asciidoctor-pdf** are collected at the end of the document, not at the
  bottom of the page.
- **Cells spanning several rows** are written correctly, but pandoc 3.1's LaTeX output
  cannot set them: the text of such a cell is put into its first row and may run past
  the table edge. The AsciiDoc route sets them correctly.
- **Two-sided documents**: the pandoc file mirrors the margins (`inner`/`outer`), the
  asciidoctor-pdf theme uses the same margins on every page; different left and right
  master page layouts are not reproduced.
