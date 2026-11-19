"""The document model between MIF and the writers.

The builder fills it from MIF; the Markdown and AsciiDoc writers only read it. It knows
nothing about FrameMaker and nothing about output syntax.
"""
import re
from dataclasses import dataclass, field

# Inline styles (members of Text.style)
BOLD, ITALIC, CODE, SUPER, SUB, UNDERLINE, STRIKE = 'b', 'i', 'code', 'sup', 'sub', 'u', 's'


# ---- inlines ----

@dataclass
class Text:
    text: str
    style: frozenset = frozenset()
    ctag: str = ''         # FrameMaker character format; only the RTF writer uses it


@dataclass
class LineBreak:
    pass


@dataclass
class Link:
    """A link: to an anchor in this document (internal) or to a URL."""
    target: str
    children: list
    internal: bool = True


@dataclass
class PageRef:
    """The page number of an anchor, as FrameMaker last printed it (`text`)."""
    target: str
    text: str


@dataclass
class Anchor:
    """A link target inside the text."""
    id: str


@dataclass
class FootnoteRef:
    blocks: list


@dataclass
class IndexTerm:
    """One index entry; `levels` is ['primary', 'secondary', ...]."""
    levels: list


@dataclass
class Image:
    """An imported graphic, inline or (inside an ImageBlock) on its own line.

    `source` is the file found on disk (None if missing), `name` the file name stored in
    the MIF, `href` the path the writers use (set by the converter after copying). A
    graphic stored inside the MIF file has no file: `data` holds it as PNG, `other_formats`
    names its better versions, if any, and `eps` holds its EPSI version, if any.
    """
    source: str
    name: str
    width_pt: float = 0.0
    width_pct: int = 0     # width relative to the text column, 0 if unknown
    alt: str = ''
    href: str = ''
    data: bytes = None
    other_formats: str = ''
    eps: bytes = None


@dataclass
class FieldCode:
    """A value only a paginated document knows: 'page' (current page number), 'pages'
    (number of pages) or 'styleref' (the text of the nearest paragraph with tag `arg`,
    a running header), or 'seq' (a caption number; `arg` is the counter, such as
    'Figure'). `text` is shown until the word processor updates it."""
    kind: str
    arg: str = ''
    text: str = ''


@dataclass
class PageVariable:
    """A FrameMaker variable that needs pages (page numbers, running headers): `parts`
    are Text and FieldCode items. Only the RTF writer can show it; the Markdown and
    AsciiDoc writers leave it out with a warning."""
    name: str
    parts: list


# ---- blocks ----

# `tag` on blocks is the FrameMaker paragraph tag the block came from. The Markdown and
# AsciiDoc writers ignore it (it is there for --dump); the RTF writer makes it the style.
# `local` is set only when the paragraph overrides its tag's format (a local override in
# FrameMaker); the RTF writer writes it as direct formatting.

@dataclass
class Heading:
    level: int
    inlines: list
    anchors: list = field(default_factory=list)
    tag: str = ''
    id: str = ''           # unique id for headings that are no cross-reference target
    number: str = ''       # FrameMaker's autonumber ('2.1 '); only the RTF writer uses it
    local: 'ParaFormat' = None   # the paragraph's own format if it overrides its tag's


@dataclass
class Paragraph:
    inlines: list
    tag: str = ''
    local: 'ParaFormat' = None
    caption: bool = False  # a figure or table title; only the RTF writer uses it


@dataclass
class CodeBlock:
    text: str
    tag: str = ''
    local: 'ParaFormat' = None


@dataclass
class Quote:
    blocks: list


@dataclass
class ListMarker:
    """How FrameMaker numbers a list (from its PgfNumFormat): the counter style
    ('decimal', 'lower-alpha', 'upper-alpha', 'lower-roman', 'upper-roman') or 'bullet',
    the text around the number ('(' and ')' for '(a)'), the bullet character, whether a
    tab follows, and the number's character format. Only the RTF writer uses it."""
    style: str = 'decimal'
    prefix: str = ''
    suffix: str = '.'
    bullet: str = '\N{BULLET}'
    tab: bool = True
    font: 'CharFormat' = None


@dataclass
class ListBlock:
    """A bulleted or numbered list. Each item is a list of blocks."""
    ordered: bool
    items: list
    start: int = 1
    marker: ListMarker = None


@dataclass
class ImageBlock:
    image: Image


@dataclass
class Cell:
    blocks: list
    colspan: int = 1
    rowspan: int = 1
    angle: int = 0   # FrameMaker's rotation: 90 reads top to bottom, 270 bottom to top


@dataclass
class Row:
    """A table row. `cells` has one entry per column: a Cell, or None where the column is
    covered by a cell spanning from the left or from above."""
    kind: str  # 'head', 'body' or 'foot'
    cells: list
    height: float = 0.0  # as FrameMaker last computed it, in points


@dataclass
class Table:
    widths: list           # column widths in points
    rows: list
    title: list = None     # inlines, or None
    label: str = ''        # FrameMaker's number for the title, e.g. 'Table 3: '
    anchors: list = field(default_factory=list)
    title_below: bool = False  # FrameMaker places the title below the table
    title_tag: str = ''    # the title's paragraph tag; only the RTF writer uses it


@dataclass
class ChapterBreak:
    """The start of the next MIF file when several are combined into one document (RTF
    only): a new page and section, with that file's headers, footers and page numbering
    (`pages`, None for none)."""
    name: str = ''         # the MIF file, for --dump
    pages: 'PageLayout' = None


@dataclass
class FontStyle:
    """The look of one kind of paragraph; sizes and spaces in points."""
    family: str = ''
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    leading: float = 0.0       # added to the size to give the distance between lines
    space_before: float = 0.0
    space_after: float = 0.0


@dataclass
class Style:
    """Page and format settings of the source document, for style files (--style).
    Writers of the text ignore it."""
    page_width: float = 0.0
    page_height: float = 0.0
    margins: tuple = ()        # top, right, bottom, left in points
    two_sided: bool = False
    body: FontStyle = None
    title: FontStyle = None
    headings: dict = field(default_factory=dict)   # level -> FontStyle
    code: FontStyle = None


@dataclass
class ParaFormat:
    """A FrameMaker paragraph format as the RTF writer needs it. Lengths in points;
    `first` is the first-line indent from the column edge (FrameMaker's PgfFIndent), not
    relative to `left`; colours are (r, g, b) tuples or None."""
    family: str = ''
    size: float = 12.0
    bold: bool = False
    italic: bool = False
    underline: str = ''        # '', 'single' or 'double'
    strike: bool = False
    caps: str = ''             # '', 'upper' or 'small'
    color: tuple = None
    align: str = 'left'        # left, center, right, justify
    left: float = 0.0
    first: float = 0.0
    right: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    leading: float = 2.0
    fixed_lines: bool = True   # line height exactly size + leading (else at least)
    keep_next: bool = False
    page_break: bool = False
    hyphenate: bool = True
    tabs: list = field(default_factory=list)   # (position, 'Left'|'Center'|'Right'|'Decimal', leader)


@dataclass
class CharFormat:
    """A FrameMaker character format: only the properties it sets (None = not set)."""
    family: str = None
    size: float = None
    bold: bool = None
    italic: bool = None
    underline: str = None
    strike: bool = None
    caps: str = None
    color: tuple = None
    position: str = None       # '', 'super' or 'sub'


@dataclass
class PageLayout:
    """Headers and footers from FrameMaker's master pages and the page numbering, for
    the RTF writer. Headers and footers are lists of blocks, or None for none. `header`
    and `footer` are for right pages (all pages in one-sided documents), `*_left` for
    left pages of two-sided documents, `*_first` for the first page when it uses a master
    page of its own (`first_page_own`). Distances in points: `header_top` from the top
    edge to the header, `footer_bottom` from the footer to the bottom edge."""
    header: list = None
    footer: list = None
    header_left: list = None
    footer_left: list = None
    header_first: list = None
    footer_first: list = None
    first_page_own: bool = False
    header_top: float = 0.0
    footer_bottom: float = 0.0
    start: int = 1                 # number of the first page
    number_style: str = 'decimal'  # decimal, lower-roman, upper-roman, lower-alpha, upper-alpha


@dataclass
class Document:
    title: list = None     # inlines, or None
    lang: str = ''         # BCP 47 language tag, e.g. 'de'
    blocks: list = field(default_factory=list)
    style: Style = None
    # For the RTF writer, which keeps FrameMaker's formats; the other writers ignore them.
    title_tag: str = ''
    formats: dict = field(default_factory=dict)        # paragraph tag -> ParaFormat
    char_formats: dict = field(default_factory=dict)   # character tag -> CharFormat
    pages: PageLayout = None


def plain(inlines):
    """The plain text of a list of inlines (footnotes and index terms left out)."""
    out = []
    for i in inlines:
        if isinstance(i, Text):
            out.append(i.text)
        elif isinstance(i, Link):
            out.append(plain(i.children))
        elif isinstance(i, LineBreak):
            out.append(' ')
        elif isinstance(i, PageRef):
            out.append(i.text)
    return ''.join(out)


def walk_images(blocks):
    """Every Image in a list of blocks, including those in tables, lists and footnotes."""
    def inl(items):
        for i in items or []:
            if isinstance(i, Image):
                yield i
            elif isinstance(i, Link):
                yield from inl(i.children)
            elif isinstance(i, FootnoteRef):
                yield from walk_images(i.blocks)

    for b in blocks:
        if isinstance(b, ImageBlock):
            yield b.image
        elif isinstance(b, (Heading, Paragraph)):
            yield from inl(b.inlines)
        elif isinstance(b, Quote):
            yield from walk_images(b.blocks)
        elif isinstance(b, ListBlock):
            for item in b.items:
                yield from walk_images(item)
        elif isinstance(b, Table):
            yield from inl(b.title)
            for row in b.rows:
                for c in row.cells:
                    if c:
                        yield from walk_images(c.blocks)


def drop_page_variables(doc, warn):
    """A copy of the document without PageVariables, for outputs without pages
    (Markdown, AsciiDoc); each dropped variable is reported once."""
    import copy
    doc = copy.deepcopy(doc)

    def inl(items):
        if not any(isinstance(i, PageVariable) for i in items):
            return [_inner(i) for i in items]
        out = []
        for i in items:
            if isinstance(i, PageVariable):
                warn(f'variable {i.name!r} (page numbers, running headers) has no meaning '
                     'outside FrameMaker pages; left out')
            else:
                out.append(_inner(i))
        # white space next to a dropped variable at the start or end goes too
        if out and isinstance(out[0], Text):
            out[0] = Text(out[0].text.lstrip(), out[0].style, out[0].ctag)
        if out and isinstance(out[-1], Text):
            out[-1] = Text(out[-1].text.rstrip(), out[-1].style, out[-1].ctag)
        return [i for i in out if not isinstance(i, Text) or i.text]

    def _inner(i):
        if isinstance(i, Link):
            i.children = inl(i.children)
        elif isinstance(i, FootnoteRef):
            i.blocks = blk(i.blocks)
        return i

    def blk(blocks):
        for b in blocks:
            if isinstance(b, (Heading, Paragraph)):
                b.inlines = inl(b.inlines)
            elif isinstance(b, Quote):
                b.blocks = blk(b.blocks)
            elif isinstance(b, ListBlock):
                b.items = [blk(item) for item in b.items]
            elif isinstance(b, Table):
                if b.title is not None:
                    b.title = inl(b.title)
                for row in b.rows:
                    for c in row.cells:
                        if c:
                            c.blocks = blk(c.blocks)
        return blocks

    if doc.title is not None:
        doc.title = inl(doc.title)
    doc.blocks = blk(doc.blocks)
    return doc


# A caption's number: the word in front (Figure, Abbildung, Table) and the number, which can
# count within the chapter ('2-3', '2.3').
CAPTION_NUMBER = re.compile(r'^(\s*)([^\W\d_]+\.?)(\s*)(\d+(?:[-.\N{EN DASH}]\d+)*)(?![\w])')


def simple_caption_numbers(doc):
    """A copy of the document with its figures and tables counted through the whole
    document (Figure 7) instead of per chapter (Figure 2-3). Each word in front of the
    number has its own counter. The number becomes a 'seq' FieldCode, and cross-references
    to a caption get the new number in their text."""
    import copy
    doc = copy.deepcopy(doc)
    counters, renumbered = {}, {}   # anchor id -> (old number, new number)

    def count(items, anchors):
        """Renumber the caption number at the start of `items` (inlines); returns new inlines."""
        lead = 0
        while lead < len(items) and not isinstance(items[lead], Text):
            lead += 1
        if lead == len(items):
            return items
        t = items[lead]
        found = CAPTION_NUMBER.match(t.text)
        if not found:
            return items
        key = found.group(2).rstrip('.')
        counters[key] = counters.get(key, 0) + 1
        new = str(counters[key])
        for a in anchors:
            renumbered[a] = (found.group(4), new)
        parts = [Text(t.text[:found.start(4)], t.style, t.ctag), FieldCode('seq', key, new),
                 Text(t.text[found.end(4):], t.style, t.ctag)]
        return items[:lead] + [p for p in parts if not isinstance(p, Text) or p.text] + items[lead + 1:]

    def captions(blocks):
        for b in blocks:
            if isinstance(b, Paragraph) and b.caption:
                b.inlines = count(b.inlines, [i.id for i in b.inlines if isinstance(i, Anchor)])
            elif isinstance(b, Quote):
                captions(b.blocks)
            elif isinstance(b, ListBlock):
                for item in b.items:
                    captions(item)
            elif isinstance(b, Table):
                if not b.title_below:
                    table_title(b)
                for row in b.rows:
                    for c in row.cells:
                        if c:
                            captions(c.blocks)
                if b.title_below:
                    table_title(b)

    def table_title(t):
        if t.title is None and not t.label:
            return
        title = ([Text(t.label)] if t.label else []) + (t.title or [])
        new = count(title, t.anchors)
        if new is not title:
            t.label, t.title = '', new

    def fix(o, target):
        """Replace the old number by the new one in the text of a cross-reference."""
        old, new = renumbered[target]
        pattern = re.compile(r'(?<![\d.\-\N{EN DASH}])' + re.escape(old) + r'(?![\d]|[-.\N{EN DASH}]\d)')
        for i, c in enumerate(o.children):
            if isinstance(c, Text) and pattern.search(c.text):
                o.children[i] = Text(pattern.sub(new, c.text, count=1), c.style, c.ctag)
                return

    def links(items):
        for i in items or []:
            if isinstance(i, Link):
                if i.internal and i.target in renumbered:
                    fix(i, i.target)
                links(i.children)
            elif isinstance(i, FootnoteRef):
                refs(i.blocks)

    def refs(blocks):
        for b in blocks:
            if isinstance(b, (Heading, Paragraph)):
                links(b.inlines)
            elif isinstance(b, Quote):
                refs(b.blocks)
            elif isinstance(b, ListBlock):
                for item in b.items:
                    refs(item)
            elif isinstance(b, Table):
                links(b.title)
                for row in b.rows:
                    for c in row.cells:
                        if c:
                            refs(c.blocks)

    captions(doc.blocks)
    refs(doc.blocks)
    return doc
