# mifport – export FrameMaker MIF to Markdown, AsciiDoc and RTF

mifport consists of three command line tools that read FrameMaker documents in **MIF**
(Maker Interchange Format, version 7.0 up to 2026) and write the content as **Markdown**
(`mif2md`), **AsciiDoc** (`mif2adoc`) or **RTF** (`mif2rtf`): headings, paragraphs,
lists, character formatting, tables (including merged cells), footnotes,
cross-references, graphics, variables and conditional text.

The RTF output opens in Word and LibreOffice Writer and keeps FrameMaker's formatting:
every paragraph and character format becomes a style of the same name, with its fonts,
sizes, colours, indents, spacing and tab stops (see
[RTF for Word and LibreOffice Writer](#rtf-for-word-and-libreoffice-writer)).

Markdown and AsciiDoc describe structure, not layout. Page layout, fonts, colours, master
pages, headers and footers are not converted into the text; `--style` writes the page
size, margins and formats into a style file for pandoc or asciidoctor-pdf instead (see
[docs/styling.md](docs/styling.md)).

## MIF versions

The converters read MIF 7.0 and all later versions up to MIF 2026, the current one, as
Adobe describes them in the *MIF Reference* (FrameMaker 7.0 and March 2026 editions) and
in its FrameMaker character set tables:

- **MIF 7.0 and older** store non-ASCII characters as `\xNN` codes in FrameRoman, which
  the converters decode with Adobe's table.
- **MIF 8 and newer** (up to 2026) are UTF-8. The statements the converters read have
  not changed in ways that matter here (see the MIF Reference's chapter "MIF
  Compatibility"), and the converters read all these versions the same way.

The converters read MIF files only, not binary FrameMaker documents (`.fm`, `.book`).
Asian MIF encodings (the `MIFEncoding` statement) are not supported.

The tests use a generated sample document in two forms, MIF 7.00 (FrameRoman) and MIF
2015 (UTF-8), and require the same output from both; other versions are not tested. Rules
of the MIF Reference that the sample does not contain are tested with small MIF snippets
in `tests/test_mifdoc.py`.

## Installation

Download or clone the repository; there is nothing to install with pip. Run the tools
with Python from the repository folder:

```
git clone https://github.com/Jeanluc304/mifport.git
cd mifport
python3 mif2md.py --help
```

## Requirements

Python 3.9 or newer, standard library only. Nothing else is needed for the conversion.

To go further you may want:

| For | Program |
|---|---|
| Opening the RTF | Word, LibreOffice Writer or another word processor that reads RTF |
| Markdown → PDF | [pandoc](https://pandoc.org) and a LaTeX installation |
| SVG graphics in pandoc's PDF | `rsvg-convert` (Debian/Ubuntu package `librsvg2-bin`) |
| AsciiDoc → HTML or PDF | [Asciidoctor](https://asciidoctor.org), `asciidoctor-pdf` |

## Usage

```
python3 mif2md.py   input.mif [output.md]   [--flavor pandoc|gfm]
python3 mif2adoc.py input.mif [output.adoc]
python3 mif2rtf.py  input.mif [output.rtf]
```

The output name defaults to the input name with `.md`, `.adoc` or `.rtf`. The tools print
one `WARNING:` line for every feature they had to leave out or approximate, then `wrote
output.md`.

| Option | Meaning |
|---|---|
| `--flavor pandoc` | (mif2md, default) Pandoc's Markdown, made for `pandoc → PDF` |
| `--flavor gfm` | (mif2md) GitHub Flavored Markdown |
| `--map FILE` | Tag mapping file, see [Paragraph roles](#paragraph-roles) |
| `--list-tags` | List the paragraph tags in the document with the role each one gets, then stop |
| `--dump` | Print the document model – what the converter understood – then stop (see [docs/troubleshooting.md](docs/troubleshooting.md)) |
| `--style` | Also write a style file with the page size, margins and formats of the MIF file: a pandoc defaults file (`mif2md`, pandoc flavour) or an asciidoctor-pdf theme (`mif2adoc`); see [docs/styling.md](docs/styling.md) |
| `--image-dir DIR` | Folder for copied graphics, relative to the output file (default `images`); not for RTF, which embeds its graphics |
| `--no-copy-images` | Link graphics where they are instead of copying them (not for RTF) |
| `--version` | Print the version |

### Markdown to PDF with pandoc

```
python3 mif2md.py manual.mif manual.md
pandoc manual.md -o manual.pdf --pdf-engine=lualatex
```

`lualatex` (or `xelatex`) handles any Unicode text; pandoc's default `pdflatex` stops at
characters it has no font setup for. Useful additions are `-V geometry:margin=2.5cm`,
`--toc` and `--number-sections`. FrameMaker's heading numbers are not copied into the
Markdown, so `--number-sections` brings them back.

What the `pandoc` flavour does for PDF output:

- the title goes into a YAML block with the document language (`lang: en-US`), which sets
  the hyphenation;
- tables with merged cells or several paragraphs per cell become **grid tables**, others
  pipe tables; column widths follow FrameMaker's;
- cross-references link to their target, and their page number becomes `\pageref`, so
  the PDF shows the real page number;
- graphics get their width relative to the text column (`{width=50%}`);
- there is no raw HTML, because pandoc drops it on the way to PDF; the only exception is
  an empty comment `<!-- -->` between two lists, which keeps them apart and is meant to
  be dropped.

For other targets than PDF, pandoc leaves out the `\pageref`; the text then reads "on
page" without a number.

### GitHub Flavored Markdown

`--flavor gfm` writes Markdown for GitHub, GitLab and similar viewers. Tables that a pipe
table cannot hold are written as HTML tables, and footnotes inside such tables are put in
brackets after their reference.

### AsciiDoc

```
python3 mif2adoc.py manual.mif
asciidoctor manual.adoc                # HTML
asciidoctor-pdf manual.adoc            # PDF
```

AsciiDoc can hold almost everything: merged cells (`2+|`, `.2+|`), cells with lists or
several paragraphs (`a|`), footnotes, cross-references (`xref:`), index entries
(`indexterm:[]`) and image widths (`pdfwidth`). Words with characters that AsciiDoc would
read as markup are written as `pass:c[...]`, so the text comes out exactly as it was.

### RTF for Word and LibreOffice Writer

```
python3 mif2rtf.py manual.mif           # writes manual.rtf
```

Open the file in Word or LibreOffice Writer and save it in their own format (`.docx`,
`.odt`). Unlike Markdown and AsciiDoc, RTF keeps FrameMaker's formats, while the
structure is real Word structure:

- **Paragraph formats become paragraph styles** of the same name (`Body`, `Heading1`,
  `Bulleted` …), defined from FrameMaker's paragraph catalog: font, size, bold, italic,
  underline, capitals, colour, alignment, indents, space above and below, line spacing,
  keep with next, page break before, hyphenation and tab stops (with leaders). A
  paragraph that overrides its format in FrameMaker (a local override) keeps its own
  values as direct formatting; the style stays as in the catalog.
- **Character formats become character styles** (`Emphasis`, `Command` …), applied to
  the text that uses them.
- **Headings** get an outline level, so the navigation pane and an automatic table of
  contents work; FrameMaker's heading numbers ("2.1 ") are kept as text.
- **Lists** are Word lists, nested as in FrameMaker, at FrameMaker's indents, with
  FrameMaker's number format: the counter style (`1`, `a`, `A`, `i`, `I`), the text around
  it (`(a)`, `1.`, `[1]`), the bullet character (also bullets typed in Zapf Dingbats,
  Wingdings or Symbol, shown as the Unicode symbol), the number's character format, and
  whether a tab follows. Numbered lists start where FrameMaker's start.
- **Tables** with column widths, repeating heading rows, merged cells and simple lines
  around every cell; **footnotes** as Word footnotes; **cross-references** as links with
  the page number as a `PAGEREF` field, which Word and Writer update; **index markers**
  as `XE` fields, so that Word can build the index (Writer imports them, but reads the
  whole entry as the index key).
- **Graphics** in PNG or JPEG are embedded in the RTF at their FrameMaker width; other
  formats become a placeholder text with a warning (convert them to PNG first).
- **Page size and margins** come from the body pages.
- **Headers and footers** come from the master pages: the text frames above and below
  the body frame, with their paragraph formats and tab stops. Page numbers become `PAGE`
  fields, the number of pages `NUMPAGES`, running headers (`<$paratext[Tag]>`) `STYLEREF`
  fields that show the nearest heading. Two-sided documents get different left and right
  headers and footers; a first page with a master page of its own (a title page) gets
  that page's header and footer. The page numbering starts at FrameMaker's first page
  number, in its style (`1`, `i`, `I`, `a`, `A`); page numbers and the number of pages
  also work in the text.

Not in the RTF: other master pages than the left, right and first-page ones (their pages
get the left and right headers and footers), several text columns, FrameMaker's table
rulings and shading, drawing objects (also on master pages), and FrameMaker's exact line
and page breaks – Word and Writer lay out the text themselves. Multi-level numbers such
as `1.2` in a list keep only their last part. LibreOffice starts the page numbering of
the first section at 1 whatever the RTF says; Word follows it.

## Paragraph roles

FrameMaker paragraph tags are free names, so the tools have to guess what each tag is.
The role of a tag comes from, in this order:

1. the mapping file given with `--map`;
2. the tag name, for example: `Title`/`Titel` is the document title; names containing
   `Heading`, `Überschrift`, `Chapter`, `Kapitel`, `Section` or like `H1` and `Title2` are
   headings, and so are names ending in the old abbreviations *Head* and *Hed* such as
   `ChapHead`, `SubHead`, `H-Hed` and `2Hed` (but not `HeadNote`, nor `TableTitle`,
   `CellHeading`, `ColumnHead`, `BodyAfterHead`, `RunningHead`, `HeadingRunIn`, TOC and
   index formats …); `Code` and `Listing` are code;
   `Quote`, `Zitat` and `Extract` are quotes (the full rules are in `mifdoc/roles.py`);
3. the autonumber format: a symbol such as `•\t` makes a bulleted list (also a letter in
   a symbol font, such as `l` in Zapf Dingbats, which shows as ●), a counter such as
   `<n+>.\t` a numbered list (`<n=1>` starts a new list);
4. the font: a monospaced font makes a code block;
5. otherwise a normal paragraph.

Heading levels are ranked by font size, then by *Sub* in the tag name (`SubHead` comes
after `Head`), then by the number in the tag name, at the end or at the start (`Heading2`,
`2Hed`; a name without a number counts as 1). Run `--list-tags` to see the result:

```
$ python3 mif2md.py --list-tags samples/sample/sample.mif
TAG          COUNT  ROLE
Body            11  paragraph
Bulleted         2  bullet
Bulleted2        1  bullet
Code             2  code
Figure           1  paragraph
Footnote         1  paragraph
Heading1         1  heading1
Heading2         3  heading2
Heading3         1  heading3
Indented         1  paragraph
Numbered         4  numbered
Numbered1        3  numbered
Quote            2  quote
Subsection       1  heading4
Title            1  title
```

If a guess is wrong, write a mapping file (see `mapping.example.json`):

```json
{
  "paragraphs": {
    "Unterüberschrift": "heading3",
    "Seitenkopf": "skip",
    "Hinweis": "quote"
  },
  "characters": {
    "Hervorhebung": "italic",
    "Befehl": "code",
    "Wichtig": "bold italic"
  }
}
```

Paragraph roles: `title`, `heading`, `heading1` … `heading6`, `paragraph`, `bullet`,
`numbered`, `code`, `quote`, `skip`. Character roles (combine with spaces): `plain`,
`bold`, `italic`, `code`, `superscript`, `subscript`, `underline`, `strike`. Without a
mapping, character formatting is taken from the font properties (weight, angle, family,
position) relative to the paragraph's font.

## What is converted

The table shows the Markdown and AsciiDoc output; for RTF see
[RTF for Word and LibreOffice Writer](#rtf-for-word-and-libreoffice-writer).

| FrameMaker | Markdown (pandoc / gfm) | AsciiDoc |
|---|---|---|
| Text flows on body pages | Document body, in page order | same |
| Title paragraph | YAML `title` / `#` heading | `= Title` |
| Headings | `#` … `######` | `==` … `======` |
| Bulleted and numbered lists, nested by indent | `-` / `1.` | `*` / `.` |
| Indented paragraph after a list item | Continues the item | `+` continuation |
| Code paragraphs (merged when consecutive) | Fenced code block | `----` block |
| Bold, italic, monospaced, super/subscript, underline, strikethrough | `**` `*` `` ` `` `^ ^`/`<sup>` … | `**` `__` ` `` ` `^ ^` … |
| Tables with title, heading rows, merged cells | Pipe or grid table / HTML table | `\|===` table |
| Footnotes (also in tables) | `[^1]` | `footnote:[]` |
| Cross-references within the document | Link to an anchor; the page number becomes `\pageref` (pandoc flavour); gfm keeps FrameMaker's text ("on page 2") | `xref:`; keeps FrameMaker's text ("on page 2") |
| Cross-references to other files | Text | Text |
| Index markers | Left out | `indexterm:[]` |
| Imported graphics in anchored frames | Image, copied to `images/` | `image::` |
| Autonumber text of other paragraphs ("Figure 3: ") | Kept as text | Kept as text |
| User variables, dates, file name | Their text | Their text |
| Page number and running header variables | Left out (warning); RTF: Word fields | same |
| Hidden conditional text (also hidden by an active Boolean condition expression, and hidden table rows and columns) | Left out | Left out |
| Tracked changes | As if all changes were accepted | same |
| MIF 7 FrameRoman text | Decoded | Decoded |

Not converted, with a warning: drawing objects (lines, rectangles, text lines), text
frames and equations in frames, graphics copied into the document instead of linked to a
file. A frame holding several graphics on top of each other is written as separate
images, one below the other. Structured FrameMaker documents are converted from their
paragraph formats; the element structure is ignored, banner text (the instructions in
empty elements) is left out, and cross-references to elements stay plain text. Master and
reference pages (headers, footers) are not part of the output. A MIF book file only lists
its chapters: convert each chapter file.

Graphics are looked up as stored in the MIF (relative to the MIF file), then by file name
next to the MIF and in a `Graphics/`, `graphics/` or `images/` folder there. The graphics
are copied, not converted: pandoc's PDF route accepts PDF, PNG and JPEG (SVG with
`rsvg-convert`); the tools warn about other formats.

## Fixing problems and extending

If a document converts wrongly, start with
[docs/troubleshooting.md](docs/troubleshooting.md): it explains `--dump`, the usual
causes, and how to turn a problem into a test without sharing the document. More in
[CONTRIBUTING.md](CONTRIBUTING.md) and in `docs/`:

| Document | Content |
|---|---|
| [architecture.md](docs/architecture.md) | The pipeline, the modules and the document model |
| [mif-primer.md](docs/mif-primer.md) | The parts of MIF the converter reads |
| [troubleshooting.md](docs/troubleshooting.md) | Finding and fixing conversion problems |
| [extending.md](docs/extending.md) | Adding MIF features and output formats |
| [decisions.md](docs/decisions.md) | Why things are done the way they are |
| [sources.md](docs/sources.md) | The Adobe documents and sections behind every feature |
| [styling.md](docs/styling.md) | Getting the PDF closer to the FrameMaker look |

## Tests

```
python3 -m unittest discover tests
```

The test document `samples/sample/sample.mif` (and its MIF 7 version) is written by
`samples/sample/make_sample.py`. The tests check the document model, compare the output
of all three tools with `samples/sample/expected/`, and check that the MIF 7 and the MIF 2015
file give the same output. If pandoc or Asciidoctor is installed, they also check that
escaped text comes back unchanged and that tables, footnotes and links are recognised.
`NoNetworkTest` checks that no converter uses the network or starts another program
(see [SECURITY.md](SECURITY.md#no-network-access-and-how-to-check-it)). After an intended change of the output, rewrite the expected files with
`UPDATE_EXPECTED=1 python3 -m unittest discover tests`.

GitHub Actions runs the tests for every pull request and push to `main`
(`.github/workflows/check.yml`): on Python 3.9, 3.12 and the newest 3.x with pandoc and
Asciidoctor installed, and once with Python only. It also checks that `make_sample.py`
reproduces the committed sample exactly.

## Files

```
mif2md.py, mif2adoc.py,
mif2rtf.py               command line entry points
mapping.example.json     example of a tag mapping file (--map)
mifdoc/
  mif.py        MIF file -> tree of statements; string escapes, FrameRoman
  formats.py    paragraph and character catalogs, format inheritance, autonumber rules
  roles.py      paragraph roles from tag names and the mapping file
  model.py      the document model between MIF and the writers
  builder.py    MIF tree -> document model
  markdown.py   document model -> Markdown (pandoc and gfm)
  asciidoc.py   document model -> AsciiDoc
  rtf.py        document model -> RTF, with FrameMaker's formats as styles
  convert.py    shared command line handling, graphics copying
  dump.py       the document model as a readable tree (--dump)
  style.py      style files for pandoc and asciidoctor-pdf (--style)
docs/           documentation for maintainers
samples/sample/ generated test document and expected outputs
tests/          unit tests
.github/        the CI workflow
CHANGELOG.md    changes per version
SECURITY.md     how to report security problems; converting untrusted files
```

## License

MIT, see [LICENSE](LICENSE).

Adobe and FrameMaker are either registered trademarks or trademarks of Adobe in the
United States and/or other countries. This project is not affiliated with, endorsed or
sponsored by Adobe. Other names mentioned are trademarks of their respective owners.
