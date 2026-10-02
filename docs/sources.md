# Sources

Everything the converters read, and everything the generated sample
(`samples/sample/make_sample.py`) and the test snippets (`tests/test_mifdoc.py`) contain,
follows these Adobe documents. This project is not affiliated with, endorsed or sponsored
by Adobe.

| Short name | Document |
|---|---|
| MIF Ref | [MIF Reference Guide, March 2026](https://help.adobe.com/en_US/framemaker/pdfs/fm-mif-reference.pdf) (differs from the 2020 edition mainly in colour-library details) |
| MIF Ref 7 | [MIF Reference, FrameMaker 7.0](https://www.daube.ch/docu/fm-documentation/FM/fm07-MIF-reference.pdf) (third-party copy of Adobe's manual) |
| User Guide | [Using Adobe FrameMaker, March 2026](https://help.adobe.com/en_US/framemaker/pdfs/framemaker_help.pdf) |
| Char Sets | FrameMaker Character Sets, [7.0 (Windows)](https://www.daube.ch/docu/fm-documentation/FM/fm07-Character_Sets.pdf) and [8 (Windows and UNIX)](https://www.frameusers.com/uploads/2016/02/FM8_framemaker_character_sets.pdf) (third-party copies of Adobe's manuals) |

## Feature by feature

| Feature | Source (section) |
|---|---|
| Statements, strings, escapes `\t \> \q \Q \\ \xNN`, `\uNNNN`, comments, white space after `<` | MIF Ref: MIF statement syntax; Character set in strings |
| `Comment` statement, `define` and `include` | MIF Ref: Comment statement; Macro statements |
| Units (`pt`, `mm`, `millimeter`, `didot`, `cicero`, `px` …) | MIF Ref: MIF statement syntax (units table) |
| `MIFFile` line, `Book` files | MIF Ref: MIFFile statement; MIF book file identification line |
| FrameRoman (`\xNN` in MIF 7) | MIF Ref 7: Character set in strings; Char Sets: The Windows character sets (each code with its ANSI character) |
| Special characters (`Char Tab`, `HardReturn`, `EmDash` …), and their UTF-8 form since MIF 8 | MIF Ref: Char statement |
| Paragraph catalog, `Para`, `Pgf`, inheritance in file order | MIF Ref: Creating a simple MIF file (How paragraphs inherit properties); Paragraph formats |
| `PgfNumFormat`, `PgfNumString`, `PgfNumAtEnd` | MIF Ref: Paragraph formats (Pgf statement, Para statement) |
| Autonumber building blocks `S:`, `<n+>`, `<n=1>`, `<$chapnum>` | User Guide: Autonumbering (Series label; Counters in autonumber formats) |
| Character catalog, `Font` in text (current font state, empty `FTag`) | MIF Ref: Creating and applying character formats; PgfFont and Font statements |
| `FWeight`, `FAngle`, `FPosition`, `FUnderlining`, `FStrike`, `FBold`/`FItalic`, `FLanguage` | MIF Ref: PgfFont and Font statements |
| Pages, `TextRect`, `TextFlow`, `TextRectID`, files without pages | MIF Ref: Specifying page layout (Using the default layout); Pages; Text flows |
| Hidden pages and the `HIDDEN` flow | MIF Ref: Conditional text (How FrameMaker writes a conditional document) |
| Conditions, `Conditional`/`Unconditional`, conditional rows and columns | MIF Ref: Creating conditional text; Conditional text; Tables (`TblColumn` statement) |
| Boolean condition expressions | MIF Ref: Boolean expressions |
| Tracked changes (`FM8_TRACK_CHANGES_ADDED/DELETED`) | MIF Ref: Track edited text |
| Markers, `MType`, `MTypeName` | MIF Ref: Creating markers; Marker statement |
| Index entries (`;`, `:`, `[...]`, `<$nopage>`, backslash) | User Guide: Insert an index marker in a FrameMaker document |
| Cross-references, marker text `34126: Heading: My Heading`, `XRefDef` with `<$paratext>` and `<$pagenum>`, text between `XRef` and `XRefEnd` optional | MIF Ref: Creating cross-references; Cross-references |
| Variables, `Page Count` = `<$lastpagenum>`, `Table Continuation`, `Table Sheet` | MIF Ref: Creating variables; Variables |
| Date building blocks (`<$monthnum>`, `<$daynum>`, `<$shortyear>` …) | User Guide: Editing user and system variables |
| Footnotes, `Notes` in text flows, table cells and table titles | MIF Ref: Text flows (Notes statement); Tables |
| Tables, `TblCatalog`, `TblFormat`, `TblTitlePlacement`, one `Cell` per column, straddles | MIF Ref: Creating and formatting tables; Tables |
| Page size, margins and formats for `--style`: `DPageSize`, `DMargins`, `DTwoSides`, `PgfLeading`, `PgfSpBefore`, `PgfSpAfter` | MIF Ref: Specifying page layout (Creating a simple page layout); Document statement; Pgf statement |
| Anchored frames, `FrameType`, `ShapeRect`, `Angle` | MIF Ref: Graphic objects and graphic frames |
| `ImportObject`, `ImportObFileDI` paths, `ImportURL` | MIF Ref: Graphic objects and graphic frames; MIF statement syntax (Device-independent pathnames) |
| Graphics copied into the document (facets, `2.0 internal inset`) | MIF Ref: Facets for imported graphics |
| Alternative text as an object attribute of the anchored frame | User Guide: Add object attributes for tagged PDF; MIF Ref: Graphic objects and graphic frames (`ObjectAttribute` statement) |
| Banner text, cross-references to elements | MIF Ref: Banner text; Cross-references (`XRefSrcIsElem` statement) |

## Not documented by Adobe

Two details the converter needs are not spelled out in these documents. They are
handled as follows and marked in the code:

- **The tag of the alternative text in MIF.** The User Guide names the field "Alt Text";
  the MIF Reference only says that object attributes are `Tag`/`Value` pairs. The
  converter accepts "Alt Text" and close spellings (`builder.ALT_TAGS`).
- **`<$curpagenum>`** (the current page number) is not listed in the March 2026
  documents. The converter leaves out page number variables in any case, so it only
  needs to recognise the name.

One entry of Adobe's Windows character set tables is not followed: they swap `\x92` and
`\x93` (í/ì), unlike the UNIX table and unlike all other accented letters
(see [decisions.md](decisions.md)).
