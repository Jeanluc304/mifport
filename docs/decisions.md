# Design decisions

Why some things are done the way they are. Several of these replaced an obvious
solution that turned out to be wrong; please read the reason before changing one back.

## General

**A document model between reading and writing.** MIF describes layout, Markdown and
AsciiDoc describe structure, and there is more than one output format. The model keeps
FrameMaker knowledge in one place (the builder) and output syntax in another (the
writers), so a new format does not need to know MIF.

**Standard library only.** The converters must run on any machine with Python 3. pandoc
and Asciidoctor are only used by tests, which skip when they are missing.

**Graphics are copied, not converted.** Converting would need Pillow, LibreOffice or
similar. The tools warn about formats the next step cannot use instead.

**Warnings instead of errors.** A document can always contain something the converter
does not handle. The conversion always finishes; every loss is reported once.

## Reading MIF

**Formats are resolved for the whole file in file order.** A paragraph without
`PgfTag`/`Pgf` inherits from the previous paragraph *in the file*, across flows and
table cells. Resolving per flow or per cell gives wrong formats.

**FrameRoman comes from Adobe's character set tables, not from Python's `mac_roman`.**
The tables pair every code with its Windows character, which settles the codes where
FrameRoman differs (×, ½, ³, þ … in Mac Roman's math-symbol slots; ¤ at `\xdb`, where
Apple later put €). One entry is not followed: the Windows tables swap `\x92`/`\x93`
(í/ì), unlike the UNIX table and unlike every other accented letter, so that is taken as
a typo.

**Partial statements follow the MIF Reference, even where FrameMaker's files never need
it.** A `Font` in the text builds on the current font, a `Pgf` with a tag loads the catalog
format first, catalog formats inherit from the one above. MIF that lists all
properties in every statement converts the same either way; MIF that lists only some
relies on these rules. An earlier version restarted every `Font` from the paragraph font,
which turned italic followed by bold into bold only.

**Roles are guessed in a fixed order: mapping file, tag name, numbering, font.** Tag names
are the strongest hint FrameMaker gives; the mapping file lets users correct the guess
without code changes.

**Heading levels are ranked by font size first, then by the number in the tag name.**
Documents can mix tag families (`Heading2`, `H2`, `Section`) whose numbers do not line
up; the font size does. The number separates headings of the same size.
`PgfAcrobatLevel` (PDF bookmark level) was considered and rejected: it says which
paragraphs become PDF bookmarks, which can include captions and list items, not only
headings.

**Heading levels never jump by more than one.** AsciiDoc warns about out-of-sequence
section levels, and the output reads better.

**List levels come from the first-line indent, continuation from the left indent.**
FrameMaker has no list structure; the indents are what the reader sees.

**Heading numbers are dropped; other autonumbers are kept as text.** pandoc
(`--number-sections`) and Asciidoctor (`:sectnums:`) number headings themselves. "Figure
3: " and "Note: " labels are part of the text.

**Table titles keep their number separately (`Table.label`).** pandoc and Asciidoctor
add "Table 1:" themselves; GFM has no captions, so its writer prints the label.

**Typographic spaces become normal spaces, the non-breaking hyphen a hyphen.** LaTeX's
pdflatex, pandoc's default PDF engine, stops at U+2002 and similar characters. The hard
space stays a non-breaking space; pdflatex handles that one.

**Cross-reference page numbers become a `PageRef`.** FrameMaker's resolved text contains
its page number ("on page 2"), which is wrong anywhere else. In the pandoc flavour it
becomes `\pageref{id}`, so the PDF shows the real page. GFM and AsciiDoc have no page
numbers and keep FrameMaker's text. The number is found by matching
the target marker's `MCurrPage` in the reference's text, only if the format contains
`<$pagenum>`.

**Tracked changes are shown as accepted.** FrameMaker marks inserted and deleted text with
the conditions `FM8_TRACK_CHANGES_ADDED` and `FM8_TRACK_CHANGES_DELETED`. Deleted text
is always left out and inserted text always kept, whatever the document showed, because
a converted document should read as the final text.

**Markers by name first.** Since MIF 5.5 FrameMaker identifies markers by name and the
reference calls the numbers of custom types arbitrary. The standard names (`Index`,
`Cross-Ref`) decide; the number is only a fallback, for example for localised names.

**Copied-in graphics are dropped with a warning.** Their facet data (`=EPSI`,
`=FrameImage` …) is in FrameMaker's own formats; decoding them would need more than the
standard library. The parser removes the facet lines first, because their data can
contain `<`, `>` and `` ` `` and would otherwise break the statement tree.

**Anchor ids are made from the target's text** (`slug`: ASCII letters, digits, hyphens,
starting with a letter). Readable links, and valid in HTML, LaTeX and AsciiDoc.

**Index terms in headings move to the next paragraph (AsciiDoc).** Asciidoctor discourages
index terms in section titles; they also end up in the generated section id.

## Markdown

**Two flavours.** pandoc's Markdown is the target for PDF; GitHub Flavored Markdown is
what most viewers show. They differ in tables, anchors, super/subscript and HTML.

**No raw HTML in the pandoc flavour.** pandoc drops raw HTML when it writes LaTeX: an HTML
table becomes loose text, `<a id>` disappears. Anchors use `{#id}` and `[]{#id}`; complex
tables use grid tables.

**Grid tables for complex tables, pipe tables otherwise.** Pipe tables cannot merge cells
or hold more than one paragraph per cell. pandoc (3.x) reads row and column spans in grid
tables. Both table kinds get column widths proportional to FrameMaker's: pandoc derives
relative widths from the dashes and cell widths.

**Grid tables are drawn on a character canvas.** With merged cells, borders of different
rows meet at different places; drawing each cell's rectangle and then the corners is the
simplest correct way. Columns are widened until no line is longer than its cell.

**Escaping uses backslashes, only where needed.** Every ASCII punctuation character can be
backslash-escaped in CommonMark and pandoc. The writer always escapes backslash,
backtick, `*`, `[`, `]`, `<`, `|`, `~`, `^` and `$`; `@` for pandoc (citations); `_` only
at word boundaries (intra-word underscores are safe and common); `&` only before
something that looks like an entity; and `--` for pandoc
(its `smart` extension makes a dash). Characters that only matter at the start of a line
(`#`, `>`, `-`, `+`, `1.`, `a.`, `(1)`, `:`, `%`) are escaped there.

**`$` is escaped in GFM too.** GitHub renders `$...$` as math.

**Two lists in a row are separated by `<!-- -->`.** Otherwise Markdown merges them into
one list. pandoc drops the comment in PDF output, which is fine.

**Footnotes in GFM HTML tables are written in brackets.** GFM footnote syntax does not
work inside HTML.

## AsciiDoc

**Risky words go into `pass:c[...]`.** The first approach used character references
(`{asterisk}`, `{startsb}` …). It fails: Asciidoctor resolves attribute references
*before* replacements and macros, so `-{empty}-` still became an em dash and `<<a>>`,
written as `{lt}<a>>`, was read as a cross-reference that swallowed the following text.
An inline passthrough is set aside before every other substitution and still escapes
`< > &` for HTML. Only words that contain a risky character or sequence are wrapped, so
normal text stays readable. A backslash at the end of such a word goes outside as
`{backslash}`, because `\]` would escape the closing bracket.

**HTML character references are protected too.** Asciidoctor keeps `&amp;` and `&#169;`
as references; text that contains them literally must be wrapped.

**Line starts are protected with `{empty}`.** Lists (`* `, `. `, `1. `, `a. `), titles,
admonitions (`NOTE:`), attribute entries, comments and directives (`include::`) are
recognised at the start of a line, before any inline substitution.

**Formatting uses the unconstrained marks** (`**`, `__`, ` `` `). They work in the middle
of words, which FrameMaker's character formats often require.

**Complex table cells are `a|` cells.** They can hold lists and several paragraphs;
simple cells stay `|` cells. Only one heading row is supported by Asciidoctor; further
heading rows become body rows with a warning.
