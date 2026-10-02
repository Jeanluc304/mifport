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

# `tag` on blocks is the FrameMaker paragraph tag the block came from. Writers ignore it;
# it is there for --dump.

@dataclass
class Heading:
    level: int
    inlines: list
    anchors: list = field(default_factory=list)
    tag: str = ''
    id: str = ''           # unique id for headings that are no cross-reference target


@dataclass
class Paragraph:
    inlines: list
    tag: str = ''


@dataclass
class CodeBlock:
    text: str
    tag: str = ''


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
class Document:
    title: list = None     # inlines, or None
    lang: str = ''         # BCP 47 language tag, e.g. 'de'
    blocks: list = field(default_factory=list)
    style: Style = None


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
