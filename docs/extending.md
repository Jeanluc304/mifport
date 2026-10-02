# Extending the converter

Read [architecture.md](architecture.md) first; the recipes below assume you know the
pipeline and the document model.

General rules:

- **Standard library only.** The converters must run with nothing but Python 3.
  External programs (pandoc, Asciidoctor) may be used in tests, which skip when the
  program is missing.
- **Degrade, don't fail.** Something the converter cannot handle is left out with one
  `self.warn(...)` message, and the conversion goes on.
- **No real documents in the repository**, only rebuilt examples (see
  [troubleshooting.md](troubleshooting.md#step-4-make-a-small-test-case)).

## Support a new MIF feature

Example: MIF has something that is currently ignored, for instance hypertext markers
(`MType 8`) that should become links.

1. **Find it in MIF.** Look it up in the MIF Reference and in MIF files with `grep`, and
   note which statements are involved and where they are (paragraph text, a catalog, a
   frame). Add what you
   learned to [mif-primer.md](mif-primer.md).
2. **Model.** Can the existing model express the result? A hypertext link to a URL is a
   `Link` with `internal=False`, so nothing to do. If not, add a dataclass to `model.py`,
   and handle it in `model.plain()` and `model.walk_images()` if they need to see it.
3. **Builder.** Read the statement where it occurs. Inline things go into
   `Builder.inlines()` (see `marker()` for markers); block things into `_entry()` or
   `para_entries()`; document-wide lookups into `__init__`.
4. **Writers.** Handle the new type in **every** writer: `MarkdownWriter.inlines()` (and
   `HtmlInline.inlines()` for GFM tables), `AsciiDocWriter.inlines()`, and `dump.inlines()`.
   A writer that cannot express it should write the text and warn.
5. **Sample and tests.** Add an example to `samples/sample/make_sample.py`, regenerate
   the expected files with `UPDATE_EXPECTED=1 python3 -m unittest discover tests`, review
   the differences line by line, and add a model-level assertion to `SampleTest`.
6. **Documentation.** Update the feature table in `README.md`.

## Add an output format

Example: HTML, DocBook or reStructuredText.

1. Create `mifdoc/<format>.py` with a writer class `XWriter(warn)` whose `write(doc)`
   returns the whole text. Use `markdown.py` and `asciidoc.py` as models: `blocks()`,
   `block()`, `inlines()`, `styled()`, `escape()`, and separate methods for lists, tables
   and footnotes.
2. Handle every model type listed in [architecture.md](architecture.md#the-document-model).
   If the format cannot express one (merged cells, footnotes, index entries), choose a
   fallback, write it in the docstring, and warn once.
3. **Escaping is the important part.** Write `escape()` for plain text and decide what
   needs protecting at the start of a line. Then add a round-trip test like
   `AsciidoctorTest.test_escaping_roundtrip`: every string in `TRICKY` must come back
   unchanged through the format's real processor.
4. Add a command line entry point, `mif2x.py`, modelled on `mif2adoc.py`:

   ```python
   from mifdoc.convert import arguments, run, warn
   from mifdoc.x import XWriter

   if __name__ == '__main__':
       args = arguments('mif2x', 'Convert a FrameMaker MIF file to X.', '.x')
       run(args, '.x', lambda: XWriter(warn))
   ```
5. Add the expected output to `OUTPUTS` in `tests/test_mifdoc.py` and generate it.
6. Document the format in `README.md`, and its choices in [decisions.md](decisions.md).

## Change a heuristic

The guesses that decide what a paragraph is:

| Guess | Code | Protected by |
|---|---|---|
| Role from the tag name | `roles.tag_role`, `TITLE`, `HEADING`, `NOT_HEADING`, `CODE_TAG`, `QUOTE_TAG` | `SampleTest.test_title_language_headings` |
| Bullet or numbered list from the numbering format | `formats.numbering` | `RulesTest.test_numbering` |
| Code from a monospaced font | `formats.MONO`, `Builder.role` | `SampleTest.test_code_merged` |
| Heading levels | `Builder._heading_levels` | `SampleTest.test_title_language_headings` |
| List nesting and continuation | `Builder._group` | `SampleTest.test_lists` |
| Character styles | `Builder.char_style` | `SampleTest.test_inline_styles` |

A heuristic serves all documents. Before you change one for your document, check whether
a mapping file (`--map`) solves it. If you change it, add a test for the new case and
make sure the existing ones still pass.

## Add a special character

`Char` statements map to text in `builder.CHARS`; an unknown one is left out with a
warning naming it. Add the name with its character, written as a `\N{...}` escape so the
source stays readable. If LaTeX's pdflatex cannot print the character, map it to a plain
equivalent as the typographic spaces are (`builder.PLAIN`).

## Run the tests

```
python3 -m unittest discover tests
```

All tests must pass before and after your change. If the expected output changes on
purpose, regenerate it with `UPDATE_EXPECTED=1` and review every changed line. An
unexpected change in the expected files is a bug until you can explain it.
