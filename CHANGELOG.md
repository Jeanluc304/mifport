# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-10-22

### Added

- `mif2rtf`: MIF to RTF for Word and LibreOffice Writer. FrameMaker's paragraph and
  character formats become styles of the same name, defined from the catalogs (fonts,
  sizes, colours, alignment, indents, spacing, line spacing, tab stops); local overrides
  are kept as direct formatting. Headings get outline levels and keep FrameMaker's
  numbers; lists are Word lists; tables keep merged cells and repeating heading rows;
  footnotes are Word footnotes; cross-references are links with `PAGEREF` fields; index
  markers are `XE` fields; PNG and JPEG graphics are embedded; page size and margins are
  set.
- The colour catalog is read (CMYK and tints), and tab stops are part of the paragraph
  formats.
- `mif2rtf`: headers and footers from the master pages (left and right pages, a first
  page with its own master page), with page numbers, the number of pages and running
  headers as Word fields; page numbering from FrameMaker's first page number and style.
  Page variables in the text become fields too.
- `mif2rtf`: lists keep FrameMaker's number format: counter style, the text around the
  number, the bullet character and the number's character format.
- A test (`NoNetworkTest`) that fails if a converter opens a network connection or starts
  another program, and a section in `SECURITY.md` on how to check this yourself.

### Fixed

- Bullets typed in a symbol font (`l` in Zapf Dingbats, `n` in Wingdings) are recognised
  as bulleted lists; before, the letter appeared in front of plain paragraphs.

## [0.2.0] - 2026-10-02

### Added

- Paragraph tags ending in the abbreviations *Hed*/*Head* (`H-Hed`, `2Hed`, `ChapHead`,
  `SubHead`) are recognised as headings; *Head* followed by another word (`HeadNote`,
  `HeadRule`) is not.

### Changed

- Heading levels: a number at the start of a tag name counts (`2Hed`, `2Heading`), *Sub*
  in the name ranks a tag one level lower (`H2-SubHed`), and a tag without a number ranks
  like number 1 instead of last. Formerly `1Heading`, `2Heading` and `3Heading` of the
  same size were all level 1.
- No longer headings: names with *Column* or *Spalte* (`ColumnHead`), with *After*,
  *Nach* or *Following* (`BodyAfterHead`, `BodyAfterHeading`; but `AfterwordHeading`,
  `NachwortHeading` and `NachtragHeading` stay headings), with *Running* or *RunHead*
  (running headers), and `FigHead` (figure captions).

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

[Unreleased]: https://github.com/Jeanluc304/mifport/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Jeanluc304/mifport/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Jeanluc304/mifport/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Jeanluc304/mifport/releases/tag/v0.1.0
