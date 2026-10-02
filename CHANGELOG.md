# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Paragraph tags using the abbreviations *Hed*/*Head* (`H-Hed`, `2Hed`, `ChapHead`,
  `SubHead`) are recognised as headings.

### Changed

- Heading levels: a number at the start of a tag name counts (`2Hed`, `2Heading`), *Sub*
  in the name ranks a tag one level lower (`H2-SubHed`), and a tag without a number ranks
  like number 1 instead of last. Formerly `1Heading`, `2Heading` and `3Heading` of the
  same size were all level 1.
- `ColumnHead`/`ColumnHeading` and other names with *Column* or *Spalte* are no longer
  headings.

## [0.1.0] - 2026-10-02

First release.

### Added

- `mif2md`: FrameMaker MIF (7.0 to 2026) to Markdown, in two flavours: pandoc's Markdown
  for conversion to PDF (grid tables, `\pageref` page numbers, YAML title and language)
  and GitHub Flavored Markdown.
- `mif2adoc`: MIF to AsciiDoc for Asciidoctor and asciidoctor-pdf.
- Headings, paragraphs, bulleted and numbered lists (nested, with continuation
  paragraphs), code blocks, quotes, bold, italic, monospaced, superscript, subscript,
  underline and strikethrough.
- Tables with titles, heading and footing rows, merged cells, and lists, graphics and
  footnotes in cells.
- Footnotes, cross-references with anchors, index entries (AsciiDoc), variables,
  conditional text including Boolean condition expressions, tracked changes shown as
  accepted, and imported graphics copied next to the output.
- MIF 7.0 FrameRoman text decoded with Adobe's character set tables; `define` and
  `include` macro statements; MIF files without pages.
- Paragraph roles guessed from tag names, numbering and fonts, with a JSON mapping file
  (`--map`) to correct them; `--list-tags` and `--dump` to see what the converter
  understood.
- `--style`: a pandoc defaults file or an asciidoctor-pdf theme with the page size,
  margins, font sizes and spacing of the MIF file, as a starting point for the PDF.
- Documentation for maintainers (`docs/`), a generated sample document with expected
  outputs, and tests.

[Unreleased]: https://github.com/Jeanluc304/mifport/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Jeanluc304/mifport/releases/tag/v0.1.0
