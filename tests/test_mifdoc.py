"""Tests for mif2md and mif2adoc. Run from the repository root:

    python3 -m unittest discover tests

The expected outputs in samples/sample/expected/ are rewritten instead of compared when
the environment variable UPDATE_EXPECTED=1 is set. Tests that need pandoc or Asciidoctor
are skipped when the program is not installed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mifdoc import mif, model as m  # noqa: E402
from mifdoc.asciidoc import AsciiDocWriter, protect_line_start  # noqa: E402
from mifdoc.builder import Builder, split_index  # noqa: E402
from mifdoc.formats import numbering  # noqa: E402
from mifdoc.markdown import MarkdownWriter, escape, escape_line_start  # noqa: E402

SAMPLE = os.path.join(ROOT, 'samples', 'sample')
EXPECTED = os.path.join(SAMPLE, 'expected')
OUTPUTS = {'sample.md': ('mif2md.py', []), 'sample-gfm.md': ('mif2md.py', ['--flavor', 'gfm']),
           'sample.adoc': ('mif2adoc.py', [])}

# Text that is markup somewhere in Markdown or AsciiDoc; each must come out unchanged.
TRICKY = [
    'a * b *c* d', 'snake_case and _under_ __x__', '`tick` and ``x``', '# hash at start', 'x#y#z',
    '^sup^ ~sub~ ~~strike~~', 'C++ and a+b+c', '[x] [[id]] [a](b) link:foo[bar]',
    '{author} {#id}', 'a|b', 'C:\\path\\ and back\\slash', 'a -- b a--b --x', '<<ref>> <tag>',
    'x -> y => z <- w <= v', '100$ and $x$ & &amp; &#169;', '@cite', '1. not a list',
    '1) nor this', 'a. nor this', '- or this', '+ this', '> quote', '= title', '% title',
    ': def', '(1) list', 'a::b term:: c;; d', '((idx)) (((idx2)))', '(C) (R) (TM)',
    'footnote:[x] image:a.png[] pass:[x]', 'NOTE: not an admonition', 'include::x[]',
    'ends with backslash\\',
]


def tricky_table(code_cell):
    """A table with one row per TRICKY string; the second column holds inline code with a
    vertical bar, or (code_cell=True) a paragraph and a code block with one."""
    rows = []
    for t in TRICKY:
        if code_cell:
            second = m.Cell([m.Paragraph([m.Text('x')]), m.CodeBlock('a | b')])
        else:
            second = m.Cell([m.Paragraph([m.Text('a|b', frozenset({m.CODE}))])])
        rows.append(m.Row('body', [m.Cell([m.Paragraph([m.Text(t)])]), second]))
    return m.Document(blocks=[m.Table([72.0, 72.0], rows)])


def html_cells(html_text):
    """The text of every table cell in an HTML page, tags removed."""
    import html
    cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', html_text, re.S)
    return [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in cells]


def build(path, warnings=None):
    root, _ = mif.load(path)
    return Builder(root, path, warn=(warnings.append if warnings is not None else lambda s: None)).build()


def run_tool(script, args, mif_path, out_dir):
    out = os.path.join(out_dir, 'out' + ('.adoc' if 'adoc' in script else '.md'))
    p = subprocess.run([sys.executable, os.path.join(ROOT, script), mif_path, out] + args,
                       capture_output=True, text=True)
    if p.returncode:
        raise AssertionError(p.stderr)
    with open(out, encoding='utf-8') as f:
        return f.read(), p.stderr


class ParserTest(unittest.TestCase):
    def test_tree_and_strings(self):
        root = mif.parse("<A <B `x\\>y \\q\\Q'> <C 1.5 mm> # comment\n <D <E `'>>>")
        a = root.get('A')
        self.assertEqual(a.str('B'), "x>y '`")
        self.assertEqual(a.val('C'), '1.5 mm')
        self.assertEqual(a.get('D').str('E'), '')
        self.assertEqual([n.name for n in root.find('E')], ['E'])

    def test_frameroman_table(self):
        """Codes where FrameRoman differs from Mac Roman (Adobe's character set tables)."""
        got = mif.unescape('\\xba \\xb0 \\xb2 \\xca \\xdb \\xfb \\xb8 \\x92 \\x93 ')
        self.assertEqual(got, '\N{VULGAR FRACTION ONE HALF}\N{MULTIPLICATION SIGN}'
                              '\N{LATIN SMALL LETTER ETH}\N{LATIN SMALL LETTER THORN}'
                              '\N{CURRENCY SIGN}\N{DEGREE SIGN}\N{SUPERSCRIPT THREE}'
                              '\N{LATIN SMALL LETTER I WITH ACUTE}\N{LATIN SMALL LETTER I WITH GRAVE}')

    def test_frameroman_forced_return(self):
        root = mif.parse("<Para <ParaLine <String `one\\x09 two'>>>")
        doc = Builder(root, 'x.mif', warn=lambda s: None).build()
        inl = doc.blocks[0].inlines
        self.assertEqual([type(i).__name__ for i in inl], ['Text', 'LineBreak', 'Text'])

    def test_frameroman(self):
        self.assertEqual(mif.unescape('Gr\\x9f\\xa7e \\x11 x'), 'Grüße \N{NO-BREAK SPACE}x')

    def test_not_mif(self):
        with tempfile.NamedTemporaryFile('w', suffix='.mif', delete=False) as f:
            f.write('hello')
        try:
            with self.assertRaises(ValueError):
                mif.load(f.name)
        finally:
            os.unlink(f.name)


class RulesTest(unittest.TestCase):
    def test_numbering(self):
        self.assertEqual(numbering('S:<n+>.\t'), ('ordered', False))
        self.assertEqual(numbering('<n=1>.\\t'), ('ordered', True))
        self.assertEqual(numbering('B:\u2022\\t'), ('bullet', None))
        self.assertEqual(numbering('T:Table <n+>: '), (None, None))
        self.assertEqual(numbering('Caution: '), (None, None))
        self.assertEqual(numbering(None), (None, None))

    def test_index_entries(self):
        self.assertEqual(split_index('a;b:c<$nopage>;[sort]d'), [['a'], ['b', 'c'], ['d']])


class SampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.warnings = []
        cls.doc = build(os.path.join(SAMPLE, 'sample.mif'), cls.warnings)

    def blocks(self, kind):
        return [b for b in self.doc.blocks if isinstance(b, kind)]

    def test_title_language_headings(self):
        self.assertEqual(m.plain(self.doc.title), 'Sample Document')
        self.assertEqual(self.doc.lang, 'en-US')
        self.assertEqual([(h.level, m.plain(h.inlines)) for h in self.blocks(m.Heading)],
                         [(1, 'Introduction'), (2, 'Lists'), (2, 'Tables and graphics'),
                          (2, 'More structures'), (3, 'Lists with references'),
                          (4, 'Formatting and quotes')])  # 12 pt Heading3 before 12 pt Subsection
        self.assertEqual(self.blocks(m.Heading)[0].anchors, ['introduction'])

    def test_lists(self):
        bullets, first, second = self.blocks(m.ListBlock)[:3]
        self.assertFalse(bullets.ordered)
        self.assertEqual(len(bullets.items), 2)
        self.assertIsInstance(bullets.items[0][1], m.ListBlock)  # nested bullet
        self.assertEqual(m.plain(bullets.items[1][1].inlines),   # continuation paragraph
                         'A paragraph that continues the second bullet.')
        self.assertEqual((first.ordered, len(first.items)), (True, 2))
        self.assertEqual(len(second.items), 1)  # <n=1> started a new list

    def test_code_merged(self):
        self.assertEqual(self.blocks(m.CodeBlock)[0].text, 'for x in range(3):\n    print(x * 2)')

    def test_inline_styles(self):
        para = self.blocks(m.Paragraph)[1]
        styles = {i.text: i.style for i in para.inlines if isinstance(i, m.Text)}
        self.assertEqual(styles['italic'], {m.ITALIC})
        self.assertEqual(styles['bold'], {m.BOLD})
        self.assertEqual(styles['code_text()'], {m.CODE})
        self.assertEqual(styles['2'], {m.SUPER})
        self.assertTrue(any(isinstance(i, m.FootnoteRef) for i in para.inlines))
        terms = [i.levels for i in self.blocks(m.Heading)[0].inlines if isinstance(i, m.IndexTerm)]
        self.assertEqual(terms, [['Introduction'], ['Sample', 'first entry']])

    def test_hidden_condition_and_variables(self):
        texts = [m.plain(p.inlines) for p in self.blocks(m.Paragraph)]
        self.assertIn('Hidden text follows.', texts)
        self.assertIn('Version 1.2, pages:', texts)
        self.assertTrue(any('Page Count' in w for w in self.warnings))

    def test_cross_reference(self):
        link = next(i for p in self.blocks(m.Paragraph) for i in p.inlines if isinstance(i, m.Link))
        self.assertEqual(link.target, 'introduction')
        self.assertEqual(m.plain(link.children), '\u201cIntroduction\u201d on page 2')
        self.assertTrue(any(isinstance(i, m.PageRef) for i in link.children))

    def test_table(self):
        t = self.blocks(m.Table)[0]
        self.assertEqual(m.plain(t.title), 'Sample table')
        self.assertEqual(t.label, 'Table 1: ')
        self.assertEqual([r.kind for r in t.rows], ['head', 'body', 'body'])
        span2, covered, tall = t.rows[1].cells
        self.assertEqual((span2.colspan, covered, tall.rowspan), (2, None, 2))
        self.assertEqual(len(tall.blocks), 2)
        self.assertIsNone(t.rows[2].cells[2])

    def test_image(self):
        img = self.blocks(m.ImageBlock)[0].image
        self.assertTrue(img.source.endswith(os.path.join('Graphics', 'dot.png')))
        self.assertEqual(img.width_pct, 50)

    def test_list_with_reference_table_and_inline_image(self):
        steps, more = self.blocks(m.ListBlock)[3:5]
        self.assertEqual((steps.ordered, steps.start, len(steps.items)), (True, 1, 3))
        link = next(i for i in steps.items[0][0].inlines if isinstance(i, m.Link))
        self.assertEqual(link.target, 'tables-and-graphics')
        self.assertIsInstance(steps.items[1][1], m.Table)      # anchored in the list item
        self.assertTrue(any(isinstance(i, m.Image) for i in steps.items[2][0].inlines))
        self.assertEqual(more.start, 4)                         # the list goes on after a paragraph

    def test_second_table(self):
        t = self.blocks(m.ListBlock)[3].items[1][1]
        self.assertEqual(m.plain(t.title), 'Parts')
        self.assertTrue(t.title_below)
        self.assertEqual([r.kind for r in t.rows], ['head', 'head', 'body', 'body', 'foot'])
        self.assertEqual(t.rows[0].cells[0].colspan, 2)
        numbered = t.rows[2].cells[0].blocks[0]
        self.assertEqual((numbered.ordered, len(numbered.items)), (True, 2))
        self.assertTrue(any(isinstance(i, m.FootnoteRef) for i in t.rows[2].cells[1].blocks[0].inlines))
        self.assertIsInstance(t.rows[3].cells[0].blocks[0], m.ImageBlock)
        self.assertFalse(t.rows[3].cells[1].blocks[0].ordered)

    def test_more_styles_quote_and_overlapping_graphics(self):
        para = next(p for p in self.blocks(m.Paragraph) if m.plain(p.inlines).startswith('Underlined'))
        styles = [i.style for i in para.inlines if isinstance(i, m.Text) and i.style]
        self.assertEqual(styles, [{m.UNDERLINE}, {m.STRIKE}, {m.SUB}])
        quote = self.blocks(m.Quote)[0]
        self.assertEqual(len(quote.blocks), 2)
        self.assertEqual(len(self.blocks(m.ImageBlock)), 3)  # one frame with two graphics
        self.assertTrue(any('overlapping graphics' in w for w in self.warnings))

    def test_committed_sample_is_up_to_date(self):
        """make_sample.py must reproduce the committed files exactly (written into a
        temporary folder, so that running the tests changes nothing)."""
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, os.path.join(SAMPLE, 'make_sample.py'), tmp], check=True)
            for name in ('sample.mif', 'sample-mif7.mif', os.path.join('Graphics', 'dot.png')):
                with open(os.path.join(tmp, name), 'rb') as a, open(os.path.join(SAMPLE, name), 'rb') as b:
                    self.assertEqual(a.read(), b.read(), name)

    def test_mif7_same_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            for script, args in OUTPUTS.values():
                a, _ = run_tool(script, args, os.path.join(SAMPLE, 'sample.mif'), tmp)
                b, _ = run_tool(script, args, os.path.join(SAMPLE, 'sample-mif7.mif'), tmp)
                self.assertEqual(a, b, script + ' ' + ' '.join(args))

    def test_expected_output(self):
        update = os.environ.get('UPDATE_EXPECTED') == '1'
        with tempfile.TemporaryDirectory() as tmp:
            for name, (script, args) in OUTPUTS.items():
                text, _ = run_tool(script, args, os.path.join(SAMPLE, 'sample.mif'), tmp)
                self.assertTrue(os.path.isfile(os.path.join(tmp, 'images', 'dot.png')))
                path = os.path.join(EXPECTED, name)
                if update:
                    os.makedirs(EXPECTED, exist_ok=True)
                    with open(path, 'w', encoding='utf-8', newline='\n') as f:
                        f.write(text)
                    continue
                with open(path, encoding='utf-8') as f:
                    self.assertEqual(text, f.read(), name)


BODY_CATALOG = "<PgfCatalog <Pgf <PgfTag `Body'> <PgfFont <FFamily `Times'> <FSize 10 pt>>>>"


def doc_from(body, extra='', rect='<ShapeRect 0 0 400 600>', catalog=BODY_CATALOG):
    """Build a document from MIF snippets: `extra` goes before the pages (catalogs, tables,
    frames), `body` into the text flow. Returns (document, warnings)."""
    text = ("<MIFFile 2015>\n" + catalog + "\n"
            + extra + "\n<Page <PageType BodyPage> <TextRect <ID 1> " + rect + ">>\n"
            "<TextFlow <Para <PgfTag `Body'> <ParaLine <TextRectID 1> <String `start'>>>\n"
            + body + "\n>\n")
    warnings = []
    root = mif.parse(text)
    doc = Builder(root, os.path.join(SAMPLE, 'snippet.mif'), warn=warnings.append).build()
    return doc, warnings


def para(*items):
    return "<Para <ParaLine " + ' '.join(items) + ">>"


def table_mif(rows, ncols=2, title='', fmt='', tag='Format A'):
    return (f"<Tbls <Tbl <TblID 1> <TblTag `{tag}'> {fmt} <TblNumColumns {ncols}> {title} "
            f"<TblBody {rows}>>>")


def cell(text, extra=''):
    return f"<Cell {extra} <CellContent <Para <ParaLine <String `{text}'>>>>>"


class ReferenceTest(unittest.TestCase):
    """Rules of Adobe's MIF Reference that the sample document does not exercise."""

    def blocks(self, doc, kind):
        return [b for b in doc.blocks if isinstance(b, kind)]

    def test_embedded_graphic_facets(self):
        frame = ("<AFrames <Frame <ID 1> <FrameType Below> <ShapeRect 0 0 100 100>\n"
                 " <ImportObject <ImportObEditor `x'> <ImportObFile `2.0 internal inset'>\n"
                 "=EPSI\n&%v\n&<< /a (b) >> def # not a comment `x\n&\\x\n&3E3C\n&\\x\n=EndInset\n"
                 " <ShapeRect 0 0 100 100>>>>")
        doc, warnings = doc_from(para('<AFrame 1>') + para("<String `after'>"), frame)
        self.assertEqual([m.plain(p.inlines) for p in self.blocks(doc, m.Paragraph)],
                         ['start', 'after'])
        self.assertFalse(self.blocks(doc, m.ImageBlock))
        self.assertTrue(any('EPSI' in w for w in warnings))
        ob = mif.parse(frame).find('ImportObject')[0]
        self.assertIsNotNone(ob.get('ShapeRect'))  # the data did not swallow the statement

    def test_table_title_footnote(self):
        title = ("<TblTitle <TblTitleContent <Notes <FNote <ID 7> "
                 "<Para <ParaLine <String `the note'>>>>> "
                 "<Para <ParaLine <String `Title'> <FNote 7>>>>>")
        doc, _ = doc_from(para('<ATbl 1>'), table_mif('<Row ' + cell('a') + cell('b') + '>',
                                                      title=title))
        t = self.blocks(doc, m.Table)[0]
        self.assertEqual(m.plain(t.title), 'Title')
        self.assertTrue(any(isinstance(i, m.FootnoteRef) for i in t.title))

    def test_title_placement_from_catalog(self):
        catalog = ("<TblCatalog <TblFormat <TblTag `Hidden'> <TblTitlePlacement None>> "
                   "<TblFormat <TblTag `Below'> <TblTitlePlacement InFooter>>>")
        title = "<TblTitle <TblTitleContent <Para <ParaLine <String `Title'>>>>>"
        row = '<Row ' + cell('a') + cell('b') + '>'
        doc, _ = doc_from(para('<ATbl 1>'), catalog + table_mif(row, title=title, tag='Hidden'))
        self.assertIsNone(self.blocks(doc, m.Table)[0].title)
        doc, _ = doc_from(para('<ATbl 1>'), catalog + table_mif(row, title=title, tag='Below'))
        self.assertTrue(self.blocks(doc, m.Table)[0].title_below)

    def test_extra_and_missing_cells(self):
        rows = '<Row ' + cell('a') + cell('b') + cell('extra') + '> <Row ' + cell('c') + '>'
        doc, _ = doc_from(para('<ATbl 1>'), table_mif(rows))
        t = self.blocks(doc, m.Table)[0]
        self.assertEqual(len(t.widths), 2)
        self.assertEqual([len(r.cells) for r in t.rows], [2, 2])
        self.assertEqual(t.rows[1].cells[1].blocks, [])  # missing cell: empty

    def test_hidden_row_inside_straddle(self):
        catalog = "<ConditionCatalog <Condition <CTag `Secret'> <CState CHidden>>>"
        rows = ('<Row ' + cell('A', '<CellRows 2>') + cell('b') + '>'
                "<Row <Conditional <InCondition `Secret'>> " + cell('') + cell('hidden') + '>'
                '<Row ' + cell('C') + cell('d') + '>')
        doc, _ = doc_from(para('<ATbl 1>'), catalog + table_mif(rows))
        t = self.blocks(doc, m.Table)[0]
        self.assertEqual(len(t.rows), 2)
        self.assertEqual(t.rows[0].cells[0].rowspan, 1)
        self.assertEqual(m.plain(t.rows[1].cells[0].blocks[0].inlines), 'C')

    def test_markers_by_name(self):
        body = para("<Marker <MType 25> <MTypeName `Index'> <MText `term'>>",
                    "<Marker <MType 2> <MTypeName `Comment'> <MText `not an index entry'>>",
                    "<String `x'>")
        doc, _ = doc_from(body)
        terms = [i.levels for i in self.blocks(doc, m.Paragraph)[1].inlines
                 if isinstance(i, m.IndexTerm)]
        self.assertEqual(terms, [['term']])

    def test_tracked_changes_accepted(self):
        catalog = ("<ConditionCatalog <Condition <CTag `FM8_TRACK_CHANGES_ADDED'> <CState CHidden>>"
                   " <Condition <CTag `FM8_TRACK_CHANGES_DELETED'> <CState CShown>>>")
        body = para("<String `a '>",
                    "<Conditional <InCondition `FM8_TRACK_CHANGES_DELETED'>> <String `old'>",
                    "<Conditional <InCondition `FM8_TRACK_CHANGES_ADDED'>> <String `new'>",
                    "<Unconditional> <String ` b'>")
        doc, warnings = doc_from(body, catalog)
        self.assertEqual(m.plain(self.blocks(doc, m.Paragraph)[1].inlines), 'a new b')
        self.assertTrue(any('tracked changes' in w for w in warnings))

    def test_language_names(self):
        extra = "<Document <DLanguage German1996>>"
        doc, _ = doc_from(para("<String `x'>"), extra)
        self.assertEqual(doc.lang, 'de')

    def test_special_characters_in_strings(self):
        doc, _ = doc_from(para("<String `Sil\N{SOFT HYPHEN}be one\N{LINE SEPARATOR}two'>"))
        inl = self.blocks(doc, m.Paragraph)[1].inlines
        self.assertEqual(m.plain(inl), 'Silbe one two')
        self.assertTrue(any(isinstance(i, m.LineBreak) for i in inl))

    def test_units(self):
        from mifdoc.formats import lengths
        got = lengths('1 millimeter 1 centimeter 1 cicero 1 didot 1 px 1 pica 1.0"')
        want = [72 / 25.4, 72 / 2.54, 12 * 0.01483 * 72, 0.01483 * 72, 0.75, 12.0, 72.0]
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w)

    def test_image_rotation_alt_text_and_columns(self):
        frame = ("<AFrames <Frame <ID 1> <FrameType Below> <ShapeRect 0 0 300 300>"
                 " <ObjectAttribute <Tag `Alt Text'> <Value `A grey square'>>"
                 " <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>dot.png'> <Angle 90.0>"
                 " <ShapeRect 0 0 100 50>>>>")
        rect = '<ShapeRect 0 0 420 600> <TRNumColumns 2> <TRColumnGap 20>'
        doc, _ = doc_from(para('<AFrame 1>'), frame, rect)
        img = self.blocks(doc, m.ImageBlock)[0].image
        self.assertEqual(img.width_pt, 50)       # turned by 90 degrees: the height
        self.assertEqual(img.width_pct, 25)      # of a 200 pt column
        self.assertEqual(img.alt, 'A grey square')


class HandWrittenMifTest(unittest.TestCase):
    """MIF as other programs or people write it: partial statements, macros, no pages."""

    def paras(self, doc):
        return [b for b in doc.blocks if isinstance(b, m.Paragraph)]

    def test_font_statements_build_on_the_current_font(self):
        doc, _ = doc_from(para("<Font <FAngle `Italic'>> <String `a'>",
                               "<Font <FWeight `Bold'>> <String `b'>",
                               "<Font <FTag `'>> <String `c'>"))
        styles = {i.text: i.style for i in self.paras(doc)[1].inlines}
        self.assertEqual(styles, {'a': {m.ITALIC}, 'b': {m.BOLD, m.ITALIC}, 'c': frozenset()})

    def test_filter_font_properties(self):
        doc, _ = doc_from(para("<Font <FBold Yes>> <String `bold'>",
                               "<Font <FTag `'> <FUnderlining NoUnderlining>> <String ` plain'>"))
        styles = {i.text: i.style for i in self.paras(doc)[1].inlines}
        self.assertEqual(styles, {'bold': {m.BOLD}, ' plain': frozenset()})

    def test_pgf_with_tag_loads_the_catalog_format(self):
        catalog = ("<PgfCatalog <Pgf <PgfTag `Body'> <PgfFont <FFamily `Times'>>>"
                   " <Pgf <PgfTag `Sample'> <PgfFont <FFamily `Courier'>>>>")
        body = "<Para <Pgf <PgfTag `Sample'> <PgfFont <FSize 9 pt>>> <ParaLine <String `x = 1'>>>"
        doc, _ = doc_from(body, catalog=catalog)
        self.assertEqual([b.text for b in doc.blocks if isinstance(b, m.CodeBlock)], ['x = 1'])

    def test_catalog_formats_inherit_from_the_one_above(self):
        catalog = ("<PgfCatalog <Pgf <PgfTag `Body'> <PgfFont <FFamily `Times'>>>"
                   " <Pgf <PgfTag `Sample'> <PgfFont <FFamily `Courier'>>> <Pgf <PgfTag `More'>>>")
        doc, _ = doc_from("<Para <PgfTag `More'> <ParaLine <String `y'>>>", catalog=catalog)
        self.assertEqual([b.text for b in doc.blocks if isinstance(b, m.CodeBlock)], ['y'])

    def test_syntax_details(self):
        doc, _ = doc_from("< Para < ParaLine < String `pilcrow \\u00B6'>>>"
                          "<Comment <Para <ParaLine <String `commented out'>>>>")
        self.assertEqual([m.plain(p.inlines) for p in self.paras(doc)],
                         ['start', 'pilcrow \N{PILCROW SIGN}'])

    def test_no_pages(self):
        for text in ("<MIFFile 2015>\n<Para <ParaLine <String `hello'>>>",
                     "<MIFFile 2015>\n<TextFlow <Para <ParaLine <String `hello'>>>>"):
            root = mif.parse(text)
            doc = Builder(root, 'x.mif', warn=lambda s: None).build()
            self.assertEqual([m.plain(p.inlines) for p in self.paras(doc)], ['hello'])

    def test_cross_reference_without_text(self):
        extra = "<XRefFormats <XRefFormat <XRefName `Page'> <XRefDef `See <$paratext\\> on page<$pagenum\\>'>>>"
        body = (para("<Marker <MType 9> <MText `1: Body: Target'> <MCurrPage `4'>>", "<String `Target'>")
                + para("<XRef <XRefName `Page'> <XRefSrcText `1: Body: Target'>> <XRefEnd>"))
        doc, _ = doc_from(body, extra)
        link = self.paras(doc)[2].inlines[0]
        self.assertEqual((link.target, m.plain(link.children)), ('target', 'See Target on page4'))
        self.assertTrue(any(isinstance(i, m.PageRef) for i in link.children))

    def test_macros(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'defs.mif'), 'w') as f:
                f.write("define (Em, <Font <FAngle `Italic'>>)\n"
                        "define (Plain, <Font <FTag `'>>)\n")
            with open(os.path.join(tmp, 'doc.mif'), 'w') as f:
                f.write("<MIFFile 2015>\ninclude (defs.mif)\n"
                        "<Para <ParaLine <String `a '> <Em> <String `b'> <Plain>"
                        " <String ` include (not a file)'>>>\n")
            warnings = []
            root, _ = mif.load(os.path.join(tmp, 'doc.mif'), warnings.append)
            doc = Builder(root, os.path.join(tmp, 'doc.mif'), warn=warnings.append).build()
        styles = [(i.text, i.style) for i in self.paras(doc)[0].inlines]
        self.assertEqual(styles, [('a ', frozenset()), ('b', {m.ITALIC}),
                                  (' include (not a file)', frozenset())])
        self.assertFalse(warnings)


class RareFeaturesTest(unittest.TestCase):
    """Features of structured documents, condition expressions and other rare cases."""

    def paras(self, doc):
        return [m.plain(b.inlines) for b in doc.blocks if isinstance(b, m.Paragraph)]

    def test_boolean_expression_parser(self):
        from mifdoc.builder import bool_condition
        f = bool_condition('"comment"OR"summary"OR"detail\N{RIGHT DOUBLE QUOTATION MARK}')
        self.assertTrue(f({'summary'}))
        self.assertFalse(f({'other'}))
        g = bool_condition('NOT "a" AND ("b" OR "c")')
        self.assertEqual([g(t) for t in ({'b'}, {'a', 'b'}, {'c'}, set())], [True, False, True, False])
        for bad in ('"a" AND', '("a"', 'a OR "b"', '"a" "b"'):
            self.assertIsNone(bool_condition(bad), bad)

    def test_active_boolean_expression(self):
        catalog = ("<ConditionCatalog <Condition <CTag `a'> <CState CShown>>"
                   " <Condition <CTag `b'> <CState CShown>>>"
                   "<BoolCondCatalog <BoolCond <BoolCondTag `X'> <BoolCondExpr `\"a\" AND NOT \"b\"'>"
                   " <BoolCondState `Active'>>>")
        body = para("<String `0'>",
                    "<Conditional <InCondition `a'>> <String `1'>",
                    "<Conditional <InCondition `b'>> <String `2'>",
                    "<Conditional <InCondition `a'> <InCondition `b'>> <String `3'>",
                    "<Unconditional> <String `4'>")
        doc, _ = doc_from(body, catalog)
        self.assertEqual(self.paras(doc)[1], '014')

    def test_banner_text_and_element_cross_references(self):
        body = para("<String `a'> <BannerTextBegin> <String `Type the title here'>"
                    " <BannerTextEnd> <String `b '>",
                    "<XRef <XRefName `X'> <XRefSrcText `e1'> <XRefSrcIsElem Yes>> <String `see'>"
                    " <XRefEnd>")
        doc, warnings = doc_from(body)
        self.assertEqual(self.paras(doc)[1], 'ab see')
        self.assertTrue(any('elements of a structured document' in w for w in warnings))

    def test_hidden_table_column(self):
        catalog = "<ConditionCatalog <Condition <CTag `Secret'> <CState CHidden>>>"
        fmt = ("<TblFormat <TblColumn <TblColumnNum 1> <TableColumn <Conditional"
               " <InCondition `Secret'>>>>>")
        rows = ('<Row ' + cell('wide', '<CellColumns 2>') + cell('') + cell('c') + '>'
                '<Row ' + cell('a') + cell('secret') + cell('c2') + '>')
        doc, _ = doc_from(para('<ATbl 1>'), catalog + table_mif(rows, ncols=3, fmt=fmt))
        t = [b for b in doc.blocks if isinstance(b, m.Table)][0]
        self.assertEqual(len(t.widths), 2)
        self.assertEqual([[m.plain(c.blocks[0].inlines) for c in r.cells] for r in t.rows],
                         [['wide', 'c'], ['a', 'c2']])
        self.assertEqual(t.rows[0].cells[0].colspan, 1)

    def test_number_at_end(self):
        body = ("<Para <Pgf <PgfNumAtEnd Yes>> <PgfNumString ` (1)'>"
                " <ParaLine <String `Equation'>>>")
        doc, _ = doc_from(body)
        self.assertEqual(self.paras(doc)[1], 'Equation (1)')

    def test_graphic_by_url(self):
        frame = ("<AFrames <Frame <ID 1> <FrameType Below> <ShapeRect 0 0 100 100>"
                 " <ImportObject <ImportURL `https://example.com/a.png'> <ShapeRect 0 0 100 100>>>>")
        doc, warnings = doc_from(para('<AFrame 1>'), frame)
        img = [b for b in doc.blocks if isinstance(b, m.ImageBlock)][0].image
        self.assertEqual(img.href, 'https://example.com/a.png')
        self.assertFalse(warnings)

    def test_text_flow_inside_text_frame(self):
        text = ("<MIFFile 2015>\n<Page <PageType BodyPage> <TextRect <ID 3> <ShapeRect 0 0 400 600>"
                " <TextFlow <Para <ParaLine <TextRectID 3> <String `nested'>>>>>>")
        doc = Builder(mif.parse(text), 'x.mif', warn=lambda s: None).build()
        self.assertEqual(self.paras(doc), ['nested'])

    def test_graphic_url_must_be_plain(self):
        frame = ("<AFrames <Frame <ID 1> <FrameType Below> <ShapeRect 0 0 100 100>"
                 " <ImportObject <ImportURL `https://example.com/a.png[]pass:[x]'>>>>")
        doc, warnings = doc_from(para('<AFrame 1>'), frame)
        self.assertFalse([b for b in doc.blocks if isinstance(b, m.ImageBlock)])
        self.assertTrue(any('not a plain' in w for w in warnings))

    def test_book_file(self):
        with tempfile.NamedTemporaryFile('w', suffix='.mif', delete=False) as f:
            f.write('<Book 2015>\n<BookComponent <FileName `<c\\>ch1.fm\'>>\n')
        try:
            with self.assertRaisesRegex(ValueError, 'book file'):
                mif.load(f.name)
        finally:
            os.unlink(f.name)


class StyleTest(unittest.TestCase):
    """--style: page size, margins and formats taken from the MIF file."""

    @classmethod
    def setUpClass(cls):
        cls.style = build(os.path.join(SAMPLE, 'sample.mif')).style

    def test_style_values(self):
        st = self.style
        mm = 72 / 25.4
        self.assertAlmostEqual(st.page_width, 210 * mm, places=1)
        self.assertEqual([round(v / mm) for v in st.margins], [20, 30, 27, 20])
        self.assertEqual((st.body.family, st.body.size, st.body.leading, st.body.space_after),
                         ('Times', 11.0, 2.0, 6.0))
        self.assertEqual({n: (h.size, h.bold, h.italic) for n, h in st.headings.items()},
                         {1: (18.0, True, False), 2: (14.0, True, False),
                          3: (12.0, True, False), 4: (12.0, True, True)})
        self.assertEqual((st.title.size, st.code.family), (24.0, 'Courier New'))

    def test_margins_from_dmargins_without_pages(self):
        root = mif.parse('<MIFFile 2015>\n<Document <DPageSize 7.5" 9.0"> <DMargins 2" 1" .5" .5">>\n'
                         "<TextFlow <Para <ParaLine <String `x'>>>>")
        st = Builder(root, 'x.mif', warn=lambda s: None).build().style
        self.assertEqual([round(v) for v in st.margins], [72, 36, 36, 144])  # top right bottom left

    def test_style_files(self):
        from mifdoc.style import asciidoctor_theme, pandoc_defaults
        p = pandoc_defaults(self.style, 'sample')
        for needle in ('paperwidth=210.0mm', 'left=20.0mm', 'right=30.0mm', 'fontsize: 11pt',
                       '# mainfont: "Times"', '\\setlength{\\parskip}{6pt}',
                       '\\setkomafont{section}{\\fontsize{18pt}{21.6pt}\\selectfont\\sffamily\\bfseries}'):
            self.assertIn(needle, p)
        a = asciidoctor_theme(self.style, 'sample')
        for needle in ('size: [210.0mm, 297.0mm]', 'margin: [20.0mm, 30.0mm, 27.0mm, 20.0mm]',
                       'line-height: 1.18', '  h2:\n    font-size: 18\n    font-style: bold',
                       '  h5:\n    font-size: 12\n    font-style: bold_italic'):
            self.assertIn(needle, a)

    @unittest.skipUnless(shutil.which('pandoc'), 'pandoc not installed')
    def test_pandoc_reads_the_defaults_file(self):
        from mifdoc.style import pandoc_defaults
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'sample.pandoc.yaml')
            with open(path, 'w') as f:
                f.write(pandoc_defaults(self.style, 'sample'))
            p = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'latex', '-s', '--defaults', path],
                               input='# Heading\n\nText\n', capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        for needle in ('{scrartcl}', 'paperwidth=210.0mm', '\\setkomafont{section}', '\\setlength{\\parskip}{6pt}'):
            self.assertIn(needle, p.stdout)

    @unittest.skipUnless(shutil.which('asciidoctor-pdf'), 'asciidoctor-pdf not installed')
    def test_asciidoctor_pdf_uses_the_theme(self):
        from mifdoc.style import asciidoctor_theme
        with tempfile.TemporaryDirectory() as tmp:
            theme = os.path.join(tmp, 'sample-theme.yml')
            with open(theme, 'w') as f:
                f.write(asciidoctor_theme(self.style, 'sample'))
            with open(os.path.join(tmp, 'x.adoc'), 'w') as f:
                f.write('= Title\n\n== Heading\n\nText.\n')
            p = subprocess.run(['asciidoctor-pdf', '-v', '--failure-level', 'WARN', '-a',
                                f'pdf-theme={theme}', os.path.join(tmp, 'x.adoc')],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            with open(os.path.join(tmp, 'x.pdf'), 'rb') as f:
                pdf = f.read()
        box = re.search(rb'/MediaBox \[0 0 ([0-9.]+) ([0-9.]+)\]', pdf)
        self.assertEqual((round(float(box.group(1))), round(float(box.group(2)))), (595, 842))


def write_mif(folder, body, extra=''):
    """A small MIF file in `folder` with `body` in its text flow; returns its path."""
    path = os.path.join(folder, 'x.mif')
    with open(path, 'w', encoding='utf-8') as f:
        f.write("<MIFFile 2015>\n" + BODY_CATALOG + "\n" + extra +
                "\n<Page <PageType BodyPage> <TextRect <ID 1> <ShapeRect 0 0 400 600>>>\n"
                "<TextFlow <Para <PgfTag `Body'> <ParaLine <TextRectID 1> <String `start'>>>\n"
                + body + "\n>\n")
    return path


def run_cli(script, *args):
    return subprocess.run([sys.executable, os.path.join(ROOT, script), *args],
                          capture_output=True, text=True)


class RegressionTest(unittest.TestCase):
    """Problems found in a review, each reproduced with generated MIF."""

    def test_image_copies_never_overwrite(self):
        frames = ("<AFrames"
                  " <Frame <ID 1> <FrameType Below> <ShapeRect 0 0 100 50>"
                  "  <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>a.png'> <ShapeRect 0 0 100 50>>>"
                  " <Frame <ID 2> <FrameType Below> <ShapeRect 0 0 100 50>"
                  "  <ImportObject <ImportObFileDI `<c\\>images<c\\>a.png'> <ShapeRect 0 0 100 50>>>"
                  " <Frame <ID 3> <FrameType Below> <ShapeRect 0 0 100 50>"
                  "  <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>..<c\\>Graphics<c\\>a.png'>"
                  "   <ShapeRect 0 0 100 50>>>>")
        with tempfile.TemporaryDirectory() as tmp:
            for folder, content in (('Graphics', b'graphic one'), ('images', b'the user\'s file')):
                os.makedirs(os.path.join(tmp, folder))
                with open(os.path.join(tmp, folder, 'a.png'), 'wb') as f:
                    f.write(content)
            mif_path = write_mif(tmp, para('<AFrame 1>') + para('<AFrame 2>') + para('<AFrame 3>'), frames)
            out = os.path.join(tmp, 'out.md')
            for _ in range(2):  # a second run must reuse the copies, not add new ones
                p = run_cli('mif2md.py', mif_path, out)
                self.assertEqual(p.returncode, 0, p.stderr)
            with open(os.path.join(tmp, 'images', 'a.png'), 'rb') as f:
                self.assertEqual(f.read(), b"the user's file")
            self.assertEqual(sorted(os.listdir(os.path.join(tmp, 'images'))), ['a-2.png', 'a.png'])
            with open(out, encoding='utf-8') as f:
                links = re.findall(r'\]\(([^)]+)\)', f.read())
        self.assertEqual(links, ['images/a-2.png', 'images/a.png', 'images/a-2.png'])

    def test_line_breaks_at_start_and_end_are_dropped(self):
        doc, _ = doc_from(para("<Char HardReturn> <String `text'> <Char HardReturn>"))
        inl = [b for b in doc.blocks if isinstance(b, m.Paragraph)][1].inlines
        self.assertEqual([type(i).__name__ for i in inl], ['Text'])

    def test_emphasis_ends_before_a_no_break_space(self):
        doc, _ = doc_from(para("<String `See '> <Font <FWeight `Bold'>> <String `page'>",
                               "<Char HardSpace> <Font <FTag `'>> <String `2.'>"))
        for flavor in ('gfm', 'pandoc'):
            text = MarkdownWriter(flavor, lambda s: None).write(doc)
            self.assertIn('**page**\N{NO-BREAK SPACE}2.', text, flavor)
        self.assertIn('**page**\N{NO-BREAK SPACE}2.', AsciiDocWriter(lambda s: None).write(doc))

    def test_markdown_rules_and_attributes_stay_text(self):
        doc = m.Document(blocks=[
            m.Paragraph([m.Text('Name'), m.LineBreak(), m.Text('====')]),
            m.Paragraph([m.Text('----------')]),
            m.Paragraph([m.Link('x', [m.Text('Target')]), m.Text('{.big}')])])
        for flavor in ('pandoc', 'gfm'):
            text = MarkdownWriter(flavor, lambda s: None).write(doc)
            # no line of only = or - (a heading underline or a horizontal rule)
            self.assertFalse([line for line in text.splitlines() if line and set(line) <= set('-= ')])
        self.assertIn('\\{.big}', MarkdownWriter('pandoc', lambda s: None).write(doc))

    def test_variables(self):
        extra = ("<VariableFormats"
                 " <VariableFormat <VariableName `Seconds'> <VariableDef `<$second00\\>'>>"
                 " <VariableFormat <VariableName `Day'> <VariableDef `<$shortdayname\\>'>>"
                 " <VariableFormat <VariableName `Path'> <VariableDef `C:\\\\dir'>>>")
        body = para("<Variable <VariableName `Seconds'>> <String ` '>"
                    "<Variable <VariableName `Day'>> <String ` '> <Variable <VariableName `Path'>>")
        doc, warnings = doc_from(body, extra)
        text = m.plain([b for b in doc.blocks if isinstance(b, m.Paragraph)][1].inlines)
        self.assertRegex(text, r'^[0-9]{2} [A-Z][a-z]{2} C:\\dir$')
        self.assertFalse([w for w in warnings if 'not supported' in w])

    def test_unique_heading_ids(self):
        body = (para("<String `Results'>").replace("<Para", "<Para <PgfTag `Heading1'>", 1)
                + para("<Marker <MType 9> <MText `7: Body: Results'>> <String `Results'>")
                + para("<String `Results'>").replace("<Para", "<Para <PgfTag `Heading1'>", 1))
        catalog = BODY_CATALOG.replace(">>>>", ">>> <Pgf <PgfTag `Heading1'> <PgfFont <FSize 18 pt>>>>")
        doc, _ = doc_from(body, catalog=catalog)
        ids = [b.id or b.anchors[0] for b in doc.blocks if isinstance(b, m.Heading)]
        anchors = [i.id for b in doc.blocks if isinstance(b, m.Paragraph) for i in b.inlines
                   if isinstance(i, m.Anchor)]
        self.assertEqual(len(set(ids + anchors)), 3)

    def test_cli_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            mif_path = write_mif(tmp, para("<String `x'>"))
            p = run_cli('mif2md.py', mif_path, mif_path)
            self.assertIn('would overwrite the MIF file', p.stderr)
            p = run_cli('mif2md.py', mif_path, os.path.join(tmp, 'missing', 'out.md'))
            self.assertIn('does not exist', p.stderr)
            for content, message in (('{"paragraphs": ', 'not valid JSON'), ('[1, 2]', 'expected an object')):
                with open(os.path.join(tmp, 'map.json'), 'w') as f:
                    f.write(content)
                p = run_cli('mif2md.py', '--map', os.path.join(tmp, 'map.json'), mif_path)
                self.assertIn(message, p.stderr)
                self.assertIn('map.json', p.stderr)
                self.assertNotIn('Traceback', p.stderr)

    def test_encoding_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'x.mif')
            with open(path, 'wb') as f:
                f.write(b"<MIFFile 2015>\n<Para <ParaLine <String `caf\xe9'>>>\n")
            warnings = []
            mif.load(path, warnings.append)
            self.assertTrue(any('not valid UTF-8' in w for w in warnings))
            with open(path, 'w') as f:
                f.write("<MIFFile 2015>\n<MIFEncoding `x'>\n")
            warnings = []
            mif.load(path, warnings.append)
            self.assertTrue(any('MIFEncoding' in w for w in warnings))


class DumpTest(unittest.TestCase):
    def test_dump_shows_tags_and_structure(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, 'mif2md.py'), '--dump',
                            os.path.join(SAMPLE, 'sample.mif')], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        for needle in ('TITLE  Sample Document', 'H1 [Heading1]', '#introduction',
                       '  - P  [Bulleted] First bullet', '(covered by a merged cell)',
                       '<link #introduction:', 'FOOTNOTE 1'):
            self.assertIn(needle, p.stdout)


class SnippetTest(unittest.TestCase):
    def test_troubleshooting_example(self):
        """The minimal-document example in docs/troubleshooting.md must keep working."""
        with open(os.path.join(ROOT, 'docs', 'troubleshooting.md'), encoding='utf-8') as f:
            code = re.search(r'```python\n(.*?)```', f.read(), re.S).group(1)
        code = '\n'.join(line[5:] if line.startswith('     ') else line for line in code.split('\n'))
        scope = {}
        exec(code, scope)
        self.assertEqual(m.plain(scope['doc'].blocks[0].inlines), 'x')


@unittest.skipUnless(shutil.which('pandoc'), 'pandoc not installed')
class PandocTest(unittest.TestCase):
    def pandoc(self, text, fmt, to):
        p = subprocess.run(['pandoc', '-f', fmt, '-t', to, '--wrap=none'], input=text,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_escaping_roundtrip(self):
        for pandoc, fmt in ((True, 'markdown'), (False, 'gfm')):
            src = '\n\n'.join(escape_line_start(escape(t, pandoc), pandoc) for t in TRICKY)
            out = self.pandoc(src, fmt, 'plain').split('\n\n')
            for want, got in zip(TRICKY, out):
                self.assertEqual(got.strip(), want, fmt)

    def test_escaping_in_table_cells(self):
        for pandoc, fmt in ((True, 'markdown'), (False, 'gfm')):
            text = MarkdownWriter('pandoc' if pandoc else 'gfm', lambda s: None).write(tricky_table(False))
            cells = html_cells(self.pandoc(text, fmt, 'html'))
            self.assertEqual(cells[0::2], TRICKY, fmt)
            self.assertEqual(set(cells[1::2]), {'a|b'}, fmt)

    def test_sample_structure(self):
        doc = build(os.path.join(SAMPLE, 'sample.mif'))
        text = MarkdownWriter('pandoc', lambda s: None).write(doc)
        native = self.pandoc(text, 'markdown', 'native')
        for needle in ('RowSpan 2', 'ColSpan 2', 'Note', 'Superscript', 'RawInline (Format "tex") '
                       '"\\\\pageref{introduction}"', '"introduction"', 'OrderedList'):
            self.assertIn(needle, native)
        meta = json.loads(self.pandoc(text, 'markdown', 'json'))['meta']
        self.assertEqual(meta['lang']['c'][0]['c'], 'en-US')


@unittest.skipUnless(shutil.which('asciidoctor'), 'asciidoctor not installed')
class AsciidoctorTest(unittest.TestCase):
    def render(self, text):
        p = subprocess.run(['asciidoctor', '-v', '--failure-level', 'WARN', '-s', '-o', '-', '-'],
                           input=text, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_escaping_roundtrip(self):
        w = AsciiDocWriter()
        out = self.render('\n\n'.join(protect_line_start(w.escape(t)) for t in TRICKY))
        import html
        paras = [html.unescape(p) for p in re.findall(r'<p>(.*?)</p>', out, re.S)]
        self.assertEqual(len(paras), len(TRICKY))
        for want, got in zip(TRICKY, paras):
            self.assertEqual(got, want)

    def test_escaping_in_table_cells(self):
        for code_cell in (False, True):
            out = self.render(AsciiDocWriter(lambda s: None).write(tricky_table(code_cell)))
            cells = html_cells(out)
            self.assertEqual(cells[0::2], TRICKY)
            want = 'x\na | b' if code_cell else 'a|b'
            self.assertEqual({re.sub(r'\s*\n\s*', '\n', c) for c in cells[1::2]}, {want})

    def test_macros_followed_by_formatting(self):
        doc, _ = doc_from(para("<Marker <MType 2> <MText `datatype'>> <Font <FWeight `Bold'>>",
                               "<String `datatype'> <Font <FTag `'>> <String ` is bold.'> <FNote 1>",
                               "<Font <FWeight `Bold'>> <String `Bold'> <Font <FTag `'>> <String ` after.'>"),
                          "<Notes <FNote <ID 1> <Para <ParaLine <String `n'>>>>>")
        out = self.render(AsciiDocWriter(lambda s: None).write(doc))
        self.assertNotRegex(out, 'indexterm:|footnote:')
        self.assertIn('<strong>datatype</strong>', out)
        self.assertIn('<strong>Bold</strong>', out)

    def test_line_breaks_in_cells_and_titles(self):
        title = [m.Text('Title')]
        rows = [m.Row('body', [m.Cell([m.Paragraph([m.Text('one'), m.LineBreak(), m.Text('two')])]),
                               m.Cell([m.Paragraph([m.Text('p|q')])])]),
                m.Row('body', [m.Cell([m.Paragraph([m.Text('wide')])], colspan=2), None])]
        doc = m.Document(blocks=[m.Table([72.0, 72.0], rows, title)])
        out = self.render(AsciiDocWriter(lambda s: None).write(doc))
        self.assertEqual(out.count('<tr>'), 2)
        self.assertIn('one<br>', out.replace('\n', ''))
        self.assertNotIn(' + ', out)

    def test_directives_in_code_blocks_stay_text(self):
        doc = m.Document(blocks=[m.CodeBlock('include::secret.txt[]\n  ifdef::x[]\nendif::[]')])
        out = self.render(AsciiDocWriter(lambda s: None).write(doc))
        self.assertIn('include::secret.txt[]', out)
        self.assertIn('ifdef::x[]', out)
        self.assertNotIn('\\include', out)  # the escaping backslash is removed

    def test_sample_renders_without_warnings(self):
        doc = build(os.path.join(SAMPLE, 'sample.mif'))
        out = self.render(AsciiDocWriter(lambda s: None).write(doc))
        self.assertIn('rowspan="2"', out)
        self.assertIn('colspan="2"', out)
        self.assertIn('href="#introduction"', out)
        self.assertIn('class="footnote"', out)


if __name__ == '__main__':
    unittest.main()
