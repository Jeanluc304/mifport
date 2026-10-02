# MIF primer

Just enough of FrameMaker's MIF (Maker Interchange Format) to read and change this
converter. The complete reference is Adobe's
[MIF Reference Guide](https://help.adobe.com/en_US/framemaker/pdfs/fm-mif-reference.pdf);
the converter follows its March 2026 edition (which differs from the 2020 edition mainly in colour-library details) and the
FrameMaker 7.0 edition. Some details (autonumber and variable building blocks, index
entries) are not in these documents but in the FrameMaker User
Guide; the FrameRoman character set is in Adobe's *FrameMaker Character Sets* (7.0 and 8).

## Syntax

A MIF file is a tree of statements. A statement is `<Name values... children...>`:

```
<Para
 <PgfTag `Body'>
 <ParaLine
  <String `Hello '>
  <Font <FTag `Emphasis'> <FLocked No>>
  <String `world'>
 > # end of ParaLine
> # end of Para
```

- Statement names are case-sensitive; white space between `<` and the name is allowed
  (`< Units Uin >`).
- Values are bare tokens (`12.0 pt`, `Yes`, `FSuperscript`) or **strings** between a
  backquote and a straight quote: `` `text' ``.
- `#` starts a comment that runs to the end of the line. A `<Comment ...>` statement is a
  comment too, including the statements inside it; the parser drops it.
- String escapes: `\>` is `>`, `\q` is `'`, `\Q` is `` ` ``, `\t` is a tab, `\\` is a
  backslash, `\xNN ` a FrameRoman character (see below) and `\uNNNN` a Unicode character. Numbering formats use a literal `\t` (written `\\t` in the file) to mean
  "tab".
- Lengths carry units: `pt`/`point`, `"`/`in`, `mm`/`millimeter`, `cm`/`centimeter`,
  `pc`/`pica`, `dd`/`didot` (0.01483 inch), `cc`/`cicero` (12 didots) and `px` (0.75 pt),
  for example `12.0 pt` or `1.0"`. `formats.length()` converts any of them to points.
  A number without a unit would use the unit of the `<Units>` statement; the converter
  does not read `<Units>` and takes such numbers as points.

**Macro statements** are written without angle brackets and are expanded before the
statements are read (`mif.expand_macros`):

- `define (Bold, <Font <FWeight `Bold'>>)` defines a macro; `<Bold>` later in the file is
  replaced by `<Font <FWeight `Bold'>>`.
- `include (template.mif)` inserts another file; a relative path is relative to the file
  that includes it. Programs use it to read a template with the catalogs.

`mif.parse()` builds `Node` objects. The helpers you will use most:

| Call | Returns |
|---|---|
| `node.get('X')` | the first child statement `X`, or `None` |
| `node.all('X')` | all direct children `X` |
| `node.find('X')` | all statements `X` anywhere below, in file order |
| `node.val('X')` | the raw value of child `X` (strings still escaped) |
| `node.str('X')` | the value of child `X` with string escapes undone |
| `node.value`, `node.text` | the node's own value, raw or unescaped |

## Versions and character sets

The first line names the version: `<MIFFile 7.00>`, `<MIFFile 2015>`, `<MIFFile 2026>`.

- **MIF 8 and newer** (FrameMaker 8 to 2026) are UTF-8. Special characters may be
  written as characters instead of `Char` statements (`<Char Tab>`, `<Char HardReturn>`
  …); both forms are valid, and the converter reads both.
- **MIF 7.0 and older** are 7-bit: every non-ASCII character is written `\xNN ` (note
  the space after it), a byte in **FrameRoman**. FrameRoman is Mac Roman except for the
  control codes below `\x20` (`\x09` is a forced return, `\x11` a non-breaking space …)
  and about 20 codes where Mac Roman has math symbols: FrameRoman puts Windows Latin-1
  characters there (`\xb0` ×, `\xba` ½, `\xb8` ³, `\xca` þ …), and `\xdb` is ¤, not €.
  All are listed in `mif.FRAMEROMAN`, with the source. Some characters are not written in
  strings at all in MIF 7 but as `Char` statements (`<Char EmDash>`, `<Char EnDash>`,
  `<Char Cent>`). Characters FrameRoman does not have (such as €) cannot be stored in
  MIF 7.

A MIF 7 file and a newer file of the same document must give the same output; the tests
check this with the sample document.

## Top-level structure

The statements the converter uses, in the order they appear:

| Statement | Content |
|---|---|
| `ConditionCatalog` | Condition tags (`CTag`) and whether they are hidden (`CState CHidden`); tracked changes use the tags `FM8_TRACK_CHANGES_ADDED` and `FM8_TRACK_CHANGES_DELETED` |
| `PgfCatalog` | Paragraph formats: `Pgf` blocks with `PgfTag` |
| `FontCatalog` | Character formats: `Font` blocks with `FTag` |
| `VariableFormats` | Variable definitions: `VariableName`, `VariableDef` |
| `XRefFormats` | Cross-reference formats: `XRefName`, `XRefDef` |
| `Document` | Document settings, among them `DLanguage` and `DShowAllConditions` |
| `AFrames` | All anchored frames: `Frame` with `ID` |
| `Tbls` | All tables: `Tbl` with `TblID` |
| `Page` (many) | Body, master and reference pages with their text frames (`TextRect`) |
| `TextFlow` (many) | The text: `Para` statements, and `Notes` with the footnotes |

Statements the converter does not know are ignored, so newer MIF versions with new
statements still convert.

## Pages, text frames and flows

Text is not stored on pages. Each `Page` has a `PageType` (`BodyPage`,
`LeftMasterPage`, `RightMasterPage`, `OtherMasterPage`, `ReferencePage`, `HiddenPage`)
and contains `TextRect` statements with an `ID`. A `TextFlow` holds the paragraphs and
records the frames it runs through with `<TextRectID n>`, usually inside a `ParaLine`
(it may also stand directly in a `Para` or `TextFlow`).

The converter takes **the flows that pass through text frames on body pages**, ordered
by their first page (`Builder._body_flows`). Flows on master pages (headers and footers)
and reference pages are left out. According to the MIF Reference, a MIF file with hidden
conditional text keeps that text in a flow tagged `HIDDEN` on a hidden page, with a
`<Marker <MType 10>>` where it belongs; that flow is not on a body page, so it is left
out too.

A MIF file written by another program may have **no pages at all**: FrameMaker then
creates a default layout for its text flows, or for `Para` statements at the top level.
The converter does the same: without body pages it takes the text flows that are not
linked to master or reference pages (except `HIDDEN`), or else the top-level paragraphs.

## Paragraph formats

```
<Para
 <PgfTag `Body'>                          switch to the catalog format "Body"
 <Pgf <PgfTag `Body'> <PgfLIndent 10 mm>> format block: changes some properties
 <PgfNumString `2.\t'>                    the autonumber as FrameMaker last computed it
 <ParaLine ...> <ParaLine ...>            the text, one ParaLine per line FrameMaker set
>
```

**Inheritance – the rule that matters most.** A paragraph without `PgfTag` and without
`Pgf` keeps the format of the **previous paragraph in the file** – not the previous
paragraph in its flow or its table cell. A `Pgf` block changes only the properties it
lists. Therefore `Formats` resolves every `Para` of the whole file once, in file order,
before anything is built.

- A `PgfTag` in the `Para`, or inside its `Pgf` block, loads that catalog format first;
  the rest of the block is applied on top.
- A tag that is not in the catalog keeps the inherited properties and only changes the
  name.
- Catalog formats inherit what they leave out from the format above them in the catalog,
  and the first paragraph of the file starts from the last catalog format.

These rules matter whenever a `Pgf` block lists only some properties, as hand-written or
generated MIF often does.

Properties the converter reads:

| Property | Used for |
|---|---|
| `PgfTag` | The role (heading, list …), see `roles.py` |
| `PgfFont` (`FFamily`, `FSize`, `FWeight`, `FAngle` …) | Paragraph font: code blocks, heading ranking, the base for character styles |
| `PgfAutoNum`, `PgfNumFormat` | Bullets and numbered lists (`formats.numbering`) |
| `PgfNumString` | The number of a list item; the label of other paragraphs ("Figure 3: ") |
| `PgfNumAtEnd` | `Yes`: the label goes at the end of the paragraph ("Equation (3)") |
| `PgfFIndent`, `PgfLIndent` | List nesting (first line = bullet position) and continuation paragraphs |
| `FLanguage` in the font | The document language |

Autonumber formats start with an optional series label (`S:`, `T:`), followed by text and
building blocks: `<n+>` counts up, `<n=1>` restarts, `<a+>` letters, `<r+>` Roman numbers,
`<$chapnum>` the chapter number. (The MIF Reference only shows `<n+>`; the others are
described in the FrameMaker User Guide.)

## Text inside a paragraph

| Statement in `ParaLine` | Meaning |
|---|---|
| `String` | Text |
| `Char` | A special character: `Tab`, `HardSpace`, `HardReturn`, `SoftHyphen`, `EmDash` … (`builder.CHARS`) |
| `Font` | Change character formatting from here on |
| `Conditional` / `Unconditional` | Start/end conditional text; `InCondition` names the condition tags |
| `Variable` | A variable, by `VariableName` |
| `XRef` … `XRefEnd` | A cross-reference; FrameMaker's resolved text is between the two |
| `Marker` | Index entry or cross-reference target (see below), others ignored |
| `FNote n` | Footnote reference; the text is the `FNote` with `<ID n>` in a `Notes` block |
| `ATbl n` | Table `n` from `Tbls`, placed below the paragraph |
| `AFrame n` | Anchored frame `n` from `AFrames` |
| `TextRectID n` | The flow continues in text frame `n` |

**Character formatting.** A `Font` statement changes the current font: properties it does
not list stay as they were, so `<Font <FAngle `Italic'>>` followed by
`<Font <FWeight `Bold'>>` gives bold italic. `<Font <FTag `'>>` (an empty character format
name) returns to the paragraph font; a non-empty `FTag` applies that character format from
the catalog. Every paragraph starts again with its paragraph font. The converter turns the difference between the current font and the paragraph font into
inline styles (`Formats.char_font`, `Builder.char_style`). The older yes/no properties
`FBold` and `FItalic`, used by filters, count as bold and italic.

**Markers** are identified by their name, `MTypeName` (`Index`; for cross-references the
reference's table says `X-Ref`, files may have `Cross-Ref`, and both count); since MIF
5.5 the number `MType` is only kept for compatibility. The converter uses the name of the
standard types and falls back to the number (2 = index, 9 = cross-reference) for other
names (`builder.marker_kind`).

**Cross-references.** The target paragraph holds a marker
`<Marker <MType 9> <MText `11: Heading1: Introduction'> <MCurrPage `2'>>`. The reference
names the same text: `<XRef <XRefName `Heading & Page'> <XRefSrcText `11: Heading1:
Introduction'>>`. The converter matches them by this text. `MCurrPage` is the page
number FrameMaker printed; it becomes a `PageRef` if the format contains `<$pagenum>`.
References with an `XRefSrcFile` point to another file and stay plain text. The text
between `XRef` and `XRefEnd` is optional in MIF written by other programs; when it is
missing, the converter builds it from the format (`XRefDef`), filling in `<$paratext>`,
`<$paranum>`, `<$paranumonly>`, `<$paratag>` and `<$pagenum>` (`Builder.xref_text`).

**Conditional text.** `Conditional` starts text with one or more condition tags,
`Unconditional` ends it. Text is hidden when all its tags are hidden (`CState CHidden` in
the `ConditionCatalog`), unless the document shows all conditions (`DShowAllConditions
Yes`). A Boolean condition expression in the `BoolCondCatalog` with `BoolCondState
`Active'` replaces this rule: conditional text is shown if the expression, such as
`"Print" AND NOT "Draft"`, is true for its tags (`builder.bool_condition`). Tracked
changes are always shown as accepted.

**Structured documents** add statements around the text (`ElementBegin`, `ElementEnd`,
`PrefixEnd`, `SuffixBegin`); their text is ordinary `String` text. Banner text, the
instructions FrameMaker shows in empty elements, sits between `BannerTextBegin` and
`BannerTextEnd` and is left out. A cross-reference to an element has `<XRefSrcIsElem
Yes>`; it stays plain text.

**Variables.** The definition is text with building blocks: `<$curpagenum>`,
`<$lastpagenum>`, `<$paratext[Tag]>` (running headers), date blocks (`<$year>`,
`<$monthname>` …), `<$filename>`, and character format switches like `<Emphasis>`.

## Tables

```
<Tbl
 <TblID 1>
 <TblNumColumns 3>
 <TblColumnWidth 40.0 mm> ...
 <TblTitle <TblTitleContent <Para ...>>>
 <TblH <Row <Cell <CellContent <Para ...>>> ...>>   heading rows
 <TblBody <Row ...> ...>                            body rows
 <TblF <Row ...>>                                   footing rows
>
```

Each `Row` has one `Cell` **per column, including cells covered by a merged cell**. The
merged cell carries `<CellColumns n>` and/or `<CellRows n>` (counting itself); the
covered cells still appear and must be skipped (`Builder.table` keeps a set of covered
positions). Extra `Cell`s beyond `TblNumColumns` are ignored, missing ones are empty. A
row can be conditional (`<Row <Conditional <InCondition ...>>>`); a hidden row still
counts for the straddles around it. Columns can be conditional too: in the table format,
`<TblColumn <TblColumnNum n> <TableColumn <Conditional <InCondition ...>>>>` (columns are
numbered from 0). Hidden columns are left out, and cells merged across them get narrower.

The table title's paragraphs are in `TblTitleContent`, after a `Notes` block with the
title's own footnotes. Whether and where the title is shown is the format property
`TblTitlePlacement` (`InHeader`, `InFooter`, `None`). Format properties come from the
catalog format named by `TblTag` (in `TblCatalog`), overridden by a `TblFormat` inside the
`Tbl` (`Builder.table_format`).

## Anchored frames and graphics

A `Frame` in `AFrames` has a `FrameType`: `Inline` (inside the text line, like a
character), `Below` (on its own below the anchor line), `Top`/`Bottom` (at the top or
bottom of the text column), `RunIntoParagraph` (text flows around it) or outside the
column. The converter puts every frame that is not `Inline` below its paragraph. Its `ShapeRect` is `x y width height`.

Graphics are `ImportObject` statements inside the frame (also inside nested frames and
groups). A graphic **linked to a file** has its name in `ImportObFileDI`, a
device-independent path made of components: `<c\>` folder or file, `<u\>` up one level,
`<r\>` root, `<v\>` volume, `<h\>` host (`builder.di_path`). `ImportObFile` with a plain
path is obsolete according to the MIF Reference and only written for older FrameMaker
versions; the converter uses it when there is no `ImportObFileDI`. A graphic imported
from a web server may have `<ImportURL `https://...'>`; when the graphic has no file
name, the converter links to that address (plain `http(s)` addresses only).

A graphic **copied into the document** has `<ImportObFile `2.0 internal inset'>` and its
data as *facets*: lines that start with `=` (the facet name, such as `=EPSI` or
`=FrameImage`, and `=EndInset` at the end) and `&` (data). Facet lines are not
statements and may contain any character, `<`, `>`, `` ` `` and `#` included, so
`mif.strip_facets` removes them before tokenising and leaves one `<Facet `name'>` per
facet. The converter does not extract these graphics; it warns with the facet names.

`ShapeRect` of a graphic is its size *before* rotation; `Angle` rotates it, so at 90 or
270 degrees the width on the page is the `ShapeRect` height. Alternative text, if any, is
an object attribute of the anchored frame (User Guide, "Add object attributes for tagged
PDF"): `<ObjectAttribute <Tag `Alt Text'> <Value `...'>>`. The MIF Reference does not
name the tag; the converter accepts the spellings in `builder.ALT_TAGS`.

Frames can also hold drawing objects (`PolyLine`, `Rectangle`, `TextLine` …), text
frames and equations (`Math`); they are not converted.

## Finding your way in a large MIF file

```
grep -o '<[A-Za-z]*' file.mif | sort | uniq -c | sort -rn | head -40   # which statements occur
grep -n "PgfTag \`Heading1'" file.mif                                   # where a format is used
grep -n '<TblID 3>' file.mif                                            # a table by ID
grep -n -A12 '<XRef $' file.mif                                         # all cross-references
grep -n "MType 9" file.mif                                              # all cross-reference targets
```

Remember that a paragraph without `PgfTag` gets its format from the paragraph before it
in the file, so look upwards when a paragraph's format surprises you.
