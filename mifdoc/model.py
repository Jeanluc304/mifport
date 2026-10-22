"""The document model between MIF and the writers.

The builder fills it from MIF; the Markdown and AsciiDoc writers only read it. It knows
nothing about FrameMaker and nothing about output syntax.
"""
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
    the MIF, `href` the path the writers use (set by the converter after copying).
    """
    source: str
    name: str
    width_pt: float = 0.0
    width_pct: int = 0     # width relative to the text column, 0 if unknown
    alt: str = ''
    href: str = ''


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


@dataclass
class CodeBlock:
    text: str
    tag: str = ''
    local: 'ParaFormat' = None


@dataclass
class Quote:
    blocks: list


@dataclass
class ListBlock:
    """A bulleted or numbered list. Each item is a list of blocks."""
    ordered: bool
    items: list
    start: int = 1


@dataclass
class ImageBlock:
    image: Image


@dataclass
class Cell:
    blocks: list
    colspan: int = 1
    rowspan: int = 1


@dataclass
class Row:
    """A table row. `cells` has one entry per column: a Cell, or None where the column is
    covered by a cell spanning from the left or from above."""
    kind: str  # 'head', 'body' or 'foot'
    cells: list


@dataclass
class Table:
    widths: list           # column widths in points
    rows: list
    title: list = None     # inlines, or None
    label: str = ''        # FrameMaker's number for the title, e.g. 'Table 3: '
    anchors: list = field(default_factory=list)
    title_below: bool = False  # FrameMaker places the title below the table


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
class Document:
    title: list = None     # inlines, or None
    lang: str = ''         # BCP 47 language tag, e.g. 'de'
    blocks: list = field(default_factory=list)
    style: Style = None
    # For the RTF writer, which keeps FrameMaker's formats; the other writers ignore them.
    title_tag: str = ''
    formats: dict = field(default_factory=dict)        # paragraph tag -> ParaFormat
    char_formats: dict = field(default_factory=dict)   # character tag -> CharFormat


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
