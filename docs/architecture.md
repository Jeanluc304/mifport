# Architecture

## The pipeline

```
input.mif
   │  mif.load()                 mif.py       text -> tree of Node objects
   ▼
statement tree
   │  Formats(root)              formats.py   catalogs + the format of every paragraph
   │  Builder(root, ...).build() builder.py   all FrameMaker knowledge
   ▼
document model                   model.py     headings, lists, tables, links ... (no MIF, no syntax)
   │  place_images()             convert.py   copy graphics, set Image.href
   │  MarkdownWriter / AsciiDocWriter         all output syntax
   ▼
output.md / output.adoc
```

`mif2md.py` and `mif2adoc.py` only parse their options and call `convert.run()` with
the writer they need. Everything else is shared.

**The model is the contract.** The builder knows FrameMaker and nothing about Markdown or
AsciiDoc; the writers know their syntax and nothing about MIF. When you fix a problem,
first decide on which side of the model it is (see [troubleshooting.md](troubleshooting.md)):

- the model is wrong (`--dump` shows it) → fix the builder, `formats.py` or `roles.py`;
- the model is right but the output is wrong → fix the writer.

A fix should never need both sides, unless the model itself lacks a way to express
something. Then add a model type first (see [extending.md](extending.md)).

## Modules

| Module | Job | Main entry points |
|---|---|---|
| `mif.py` | Remove copied-in graphic data, expand `define`/`include`, tokenise and parse MIF; undo string escapes; decode MIF 7 FrameRoman | `load`, `parse`, `Node`, `unescape` |
| `formats.py` | Paragraph and character catalogs, format inheritance, lengths, font tests, autonumber classification | `Formats`, `numbering`, `length`, `is_bold` … |
| `roles.py` | What a paragraph tag means: name heuristics and the `--map` file | `tag_role`, `Mapping` |
| `model.py` | The document model (dataclasses) and two helpers | `Document`, `plain`, `walk_images` |
| `builder.py` | MIF tree → model | `Builder.build` |
| `markdown.py` | Model → Markdown, flavours `pandoc` and `gfm` | `MarkdownWriter.write` |
| `asciidoc.py` | Model → AsciiDoc | `AsciiDocWriter.write` |
| `dump.py` | Model → readable tree (`--dump`) | `dump` |
| `style.py` | `Document.style` → pandoc defaults file or asciidoctor-pdf theme (`--style`) | `pandoc_defaults`, `asciidoctor_theme` |
| `convert.py` | Command line options, graphics copying, warnings | `arguments`, `run` |

## The document model

Blocks:

| Type | Fields | Notes |
|---|---|---|
| `Document` | `title` (inlines), `lang`, `blocks`, `style` | `title` comes from the first `title` paragraph; `style` (page size, margins, `FontStyle` per role) is only used by `style.py` |
| `Heading` | `level` (1–6), `inlines`, `anchors`, `id` | `anchors` are ids of cross-reference targets in the heading; `id` is a unique id for the other headings |
| `Paragraph` | `inlines` | |
| `CodeBlock` | `text` | Consecutive code paragraphs with the same tag, joined with `\n` |
| `Quote` | `blocks` | |
| `ListBlock` | `ordered`, `start`, `items` | Each item is a list of blocks: its paragraph, then nested lists, continuation paragraphs, tables, images |
| `Table` | `widths` (pt), `rows`, `title`, `label`, `anchors`, `title_below` | `label` is FrameMaker's number ("Table 1: "), kept apart because pandoc and Asciidoctor number tables themselves |
| `Row` | `kind` (`head`/`body`/`foot`), `cells` | One entry per column; `None` where a merged cell covers the column |
| `Cell` | `blocks`, `colspan`, `rowspan` | |
| `ImageBlock` | `image` | A graphic on its own line |

`Heading`, `Paragraph` and `CodeBlock` also carry `tag`, the FrameMaker paragraph tag
they came from. Writers ignore it; `--dump` shows it.

Inlines:

| Type | Fields | Notes |
|---|---|---|
| `Text` | `text`, `style` | `style` is a frozenset of `BOLD`, `ITALIC`, `CODE`, `SUPER`, `SUB`, `UNDERLINE`, `STRIKE` |
| `LineBreak` | | FrameMaker's forced return |
| `Link` | `target`, `children`, `internal` | Internal targets are anchor ids |
| `PageRef` | `target`, `text` | The page number inside a cross-reference; `text` is FrameMaker's number |
| `Anchor` | `id` | A cross-reference target inside text |
| `FootnoteRef` | `blocks` | The footnote's content, inline where it is referenced |
| `IndexTerm` | `levels` | `['primary', 'secondary']` |
| `Image` | `source`, `name`, `width_pt`, `width_pct`, `alt`, `href` | `href` is set by `convert.place_images` |

## The builder in order

`Builder.__init__` analyses the whole file before anything is built, because several
decisions need the whole document:

1. `Formats(root)` resolves the format of **every** `Para` in the file in file order
   (see [mif-primer.md](mif-primer.md#paragraph-formats)).
2. Lookup tables: tables by `TblID`, anchored frames by `ID`, footnotes by `ID`, variable
   and cross-reference format definitions.
3. `_hidden_conditions` – condition tags whose text is hidden.
4. `_body_flows` – the text flows on body pages, in page order.
5. `_column_width` – the usual text frame width, for image widths in percent.
6. `_language` – the most common language of the body text.
7. `_heading_levels` – a level for every tag with the role `heading`.
8. `_xref_targets` – an anchor id for every cross-reference marker.

`build()` then turns each body flow into blocks:

- `blocks(paras)` → for each paragraph `para_entries()` → `_entry()` makes an entry
  (`para`, `item`, `code`, `quote` or `block`), followed by tables and frames anchored in
  the paragraph;
- `_merge()` joins consecutive code and quote paragraphs;
- `_group()` nests list items by indent and attaches continuation paragraphs;
- `build()` finally takes the title out and smooths heading levels (no jumps of more
  than one level).

`inlines()` walks the `ParaLine` statements of one paragraph and keeps three pieces of
state: the current character style (changed by `Font`), whether text is hidden (changed
by `Conditional`/`Unconditional`) and an open cross-reference (between `XRef` and
`XRefEnd`). Table cells and footnotes call `blocks()` recursively with `top=False`, so
headings inside them stay paragraphs.

## The writers

Both writers have the same shape: `write(doc)` → `blocks()` → `block()` per block type →
`inlines()` → `styled()` for formatted text → `escape()` for plain text. Lists, tables
and footnotes have their own methods.

The Markdown writer chooses the table syntax per table: `is_simple()` decides between a
pipe table and a grid table (pandoc) or an HTML table (gfm). `grid_table()` draws the
table on a character canvas, so that merged cells and multi-line cells line up.

The AsciiDoc writer writes complex cells as `a|` cells with full block content, and
moves index terms out of headings into the next paragraph.

Escaping is the most fragile part of both writers. Its rules and the reasons for them
are in [decisions.md](decisions.md); every change must keep the round-trip tests in
`tests/test_mifdoc.py` passing.
