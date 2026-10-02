# mifport – export FrameMaker MIF to Markdown and AsciiDoc

mifport consists of two command line tools that read FrameMaker documents in **MIF**
(Maker Interchange Format, version 7.0 up to 2026) and write the content as **Markdown**
(`mif2md`) or **AsciiDoc** (`mif2adoc`): headings, paragraphs, lists, character
formatting, tables (including merged cells), footnotes, cross-references, graphics,
variables and conditional text.

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
| Markdown → PDF | [pandoc](https://pandoc.org) and a LaTeX installation |
| SVG graphics in pandoc's PDF | `rsvg-convert` (Debian/Ubuntu package `librsvg2-bin`) |
| AsciiDoc → HTML or PDF | [Asciidoctor](https://asciidoctor.org), `asciidoctor-pdf` |

## Usage

```
python3 mif2md.py   input.mif [output.md]   [--flavor pandoc|gfm]
python3 mif2adoc.py input.mif [output.adoc]
```

The output name defaults to the input name with `.md` or `.adoc`. Both tools print one
`WARNING:` line for every feature they had to leave out or approximate, then `wrote
output.md`.

| Option | Meaning |
|---|---|
| `--flavor pandoc` | (mif2md, default) Pandoc's Markdown, made for `pandoc → PDF` |
| `--flavor gfm` | (mif2md) GitHub Flavored Markdown |
| `--map FILE` | Tag mapping file, see [Paragraph roles](#paragraph-roles) |
| `--list-tags` | List the paragraph tags in the document with the role each one gets, then stop |
| `--dump` | Print the document model – what the converter understood – then stop (see [docs/troubleshooting.md](docs/troubleshooting.md)) |
| `--style` | Also write a style file with the page size, margins and formats of the MIF file: a pandoc defaults file (`mif2md`, pandoc flavour) or an asciidoctor-pdf theme (`mif2adoc`); see [docs/styling.md](docs/styling.md) |
| `--image-dir DIR` | Folder for copied graphics, relative to the output file (default `images`) |
| `--no-copy-images` | Link graphics where they are instead of copying them |
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
3. the autonumber format: a symbol such as `•\t` makes a bulleted list, a counter such as
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
| Page number and running header variables | Left out (warning) | same |
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
of both tools with `samples/sample/expected/`, and check that the MIF 7 and the MIF 2015
file give the same output. If pandoc or Asciidoctor is installed, they also check that
escaped text comes back unchanged and that tables, footnotes and links are recognised.
After an intended change of the output, rewrite the expected files with
`UPDATE_EXPECTED=1 python3 -m unittest discover tests`.

GitHub Actions runs the tests for every pull request and push to `main`
(`.github/workflows/check.yml`): on Python 3.9, 3.12 and the newest 3.x with pandoc and
Asciidoctor installed, and once with Python only. It also checks that `make_sample.py`
reproduces the committed sample exactly.

## Files

```
mif2md.py, mif2adoc.py   command line entry points
mapping.example.json     example of a tag mapping file (--map)
mifdoc/
  mif.py        MIF file -> tree of statements; string escapes, FrameRoman
  formats.py    paragraph and character catalogs, format inheritance, autonumber rules
  roles.py      paragraph roles from tag names and the mapping file
  model.py      the document model between MIF and the writers
  builder.py    MIF tree -> document model
  markdown.py   document model -> Markdown (pandoc and gfm)
  asciidoc.py   document model -> AsciiDoc
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
