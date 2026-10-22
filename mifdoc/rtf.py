"""Document model -> RTF for Word and LibreOffice Writer.

Unlike Markdown and AsciiDoc, RTF can keep FrameMaker's formats: every paragraph tag
becomes a paragraph style of the same name and every character tag a character style,
both defined from FrameMaker's catalog (Document.formats, Document.char_formats). The
structure comes from the model as for the other writers: headings get an outline level
(navigation pane, table of contents), lists become Word lists, tables Word tables,
footnotes Word footnotes, cross-references fields that Word can update.

RTF is written as 7-bit ASCII; every other character is a \\uN escape.
"""
import os
import re
import struct

from . import model as m

# BCP 47 language tag -> Windows language id (\lang)
LCID = {'en': 1033, 'en-US': 1033, 'en-GB': 2057, 'de': 1031, 'de-DE': 1031, 'de-CH': 2055,
        'de-AT': 3079, 'fr': 1036, 'fr-FR': 1036, 'it': 1040, 'es': 1034, 'nl': 1043, 'da': 1030,
        'sv': 1053, 'nb': 1044, 'no': 1044, 'fi': 1035, 'pt': 2070, 'pt-BR': 1046, 'pl': 1045,
        'cs': 1029, 'ja': 1041, 'zh': 2052, 'ko': 1042, 'ru': 1049}
ALIGN = {'left': r'\ql', 'center': r'\qc', 'right': r'\qr', 'justify': r'\qj'}
TAB_KIND = {'Left': '', 'Center': r'\tqc', 'Right': r'\tqr', 'Decimal': r'\tqdec'}
TAB_LEADER = {'.': r'\tldot', '-': r'\tlhyph', '_': r'\tlul', '=': r'\tleq', '·': r'\tlmdot'}
BULLETS = ['\N{BULLET}', '\N{WHITE BULLET}', '\N{BLACK SMALL SQUARE}']
MONO_FONT = 'Courier New'
DEFAULT_FONT = 'Times New Roman'
CELL_PAD = 80          # twips between cell border and text (4 pt)
BORDER = r'\brdrs\brdrw10'   # cell borders: single lines, 0.5 pt


def tw(points):
    """Points -> twips."""
    return int(round(points * 20))


def esc(text):
    r"""Plain text -> RTF: escape \ { }, tabs and no-break spaces as control words, every
    non-ASCII character as \uN (a signed 16-bit number; outside the BMP a surrogate pair).

    The fallback for readers without Unicode follows \uN as a hex escape, as Word writes it:
    the Windows-1252 byte, or \'3f ('?'). A literal '?' would be ambiguous: some readers
    (pandoc) then also drop the character after it."""
    out = []
    for ch in text:
        o = ord(ch)
        if ch in '\\{}':
            out.append('\\' + ch)
        elif ch == '\t':
            out.append(r'\tab ')
        elif ch == '\n':
            out.append(r'\line ')
        elif ch == '\N{NO-BREAK SPACE}':
            out.append(r'\~')
        elif ch == '\N{SOFT HYPHEN}':
            out.append(r'\-')
        elif 32 <= o < 128:
            out.append(ch)
        elif o < 32 or o == 127:
            continue
        elif o < 0x10000:
            out.append('\\u%d%s' % (o if o < 32768 else o - 65536, _fallback(ch)))
        else:  # outside the BMP: UTF-16 surrogate pair
            o -= 0x10000
            for u in (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)):
                out.append("\\u%d\\'3f" % (u - 65536))
    return ''.join(out)


def _fallback(ch):
    try:
        return "\\'%02x" % ch.encode('cp1252')[0]
    except UnicodeEncodeError:
        return "\\'3f"


def style_name(tag):
    """A FrameMaker tag as an RTF style name: ';' ends the name in the style sheet and ','
    separates aliases in Word, and 'Normal' is the default style already."""
    name = tag.replace(';', '.').replace(',', '.')
    return esc(name + ' (FrameMaker)' if name.lower() == 'normal' else name)


def image_size(data):
    """(width, height) in pixels of PNG or JPEG data, from the file header; None otherwise."""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    if data[:2] != b'\xff\xd8':
        return None
    i = 2  # JPEG: walk the segments up to the frame header (a SOFn marker), which holds the size
    while i + 9 < len(data):
        if data[i] != 0xFF or data[i + 1] == 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack('>HH', data[i + 5:i + 9])
            return width, height
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            i += 2
            continue
        i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
    return None


class RtfWriter:
    def __init__(self, warn=print):
        self.warn = warn

    # ---------- document ----------

    def write(self, doc):
        self.doc = doc
        self.fonts = [DEFAULT_FONT]
        self.colors = []
        self.styles = {}       # paragraph tag -> style number (0 is Normal)
        self.cstyles = {}      # character tag -> style number
        self.outline = {}      # paragraph tag -> outline level of its first heading
        self.bookmarks = {}    # anchor id -> bookmark name
        self.lists = []        # list definitions: (list id, ordered, start)
        st = doc.style or m.Style()
        self.text_width = (st.page_width - st.margins[1] - st.margins[3]
                           if st.page_width and len(st.margins) == 4 else 450.0)
        self._collect_outline(doc.blocks)
        lang = LCID.get(doc.lang) or LCID.get(doc.lang.split('-')[0], 1033) if doc.lang else 1033
        self.lang = lang

        body = []
        if doc.title:
            body.append(self.para(doc.title, doc.title_tag))
        body += self.blocks(doc.blocks)
        # Fonts, colours, styles and lists are registered while the body is written, and the
        # style sheet registers fonts and colours too; so the font and colour tables come last.
        styles, lists = self.stylesheet(), self.list_tables()
        return ''.join([
            r'{\rtf1\ansi\ansicpg1252\uc1\deff0\deflang%d' % lang, '\n',
            self.font_table(), self.color_table(), styles, lists,
            self.info(doc), self.page_setup(st), '\n',
            ''.join(body), '}\n'])

    def _collect_outline(self, blocks):
        for b in blocks:
            if isinstance(b, m.Heading):
                self.outline.setdefault(b.tag, b.level)

    def font(self, family):
        family = family or DEFAULT_FONT
        if family not in self.fonts:
            self.fonts.append(family)
        return self.fonts.index(family)

    def color(self, rgb):
        """Colour table number of (r, g, b); 0 is 'automatic'."""
        if rgb not in self.colors:
            self.colors.append(rgb)
        return self.colors.index(rgb) + 1

    def font_table(self):
        return '{\\fonttbl' + ''.join('{\\f%d\\fnil\\fcharset0 %s;}' % (i, esc(f.replace(';', ' ')))
                                      for i, f in enumerate(self.fonts)) + '}\n'

    def color_table(self):
        return '{\\colortbl;' + ''.join('\\red%d\\green%d\\blue%d;' % c for c in self.colors) + '}\n'

    def stylesheet(self):
        normal = self.doc.formats.get('Body') or m.ParaFormat(family=DEFAULT_FONT)
        out = ['{\\stylesheet{\\s0\\ql ', self.char_props(normal), ' Normal;}\n']
        for tag, n in sorted(self.styles.items(), key=lambda x: x[1]):
            fmt = self.doc.formats.get(tag, normal)
            level = self.outline.get(tag)
            props = self.para_props(fmt, level) + self.char_props(fmt)
            out.append('{\\s%d%s\\sbasedon0\\snext%d %s;}\n' % (n, props, n, style_name(tag)))
        for tag, n in sorted(self.cstyles.items(), key=lambda x: x[1]):
            out.append('{\\*\\cs%d\\additive%s %s;}\n' % (n, self.cf_props(self.doc.char_formats[tag]),
                                                       style_name(tag)))
        return ''.join(out) + '}\n'

    def info(self, doc):
        if not doc.title:
            return ''
        return '{\\info{\\title %s}}\n' % esc(m.plain(doc.title))

    def page_setup(self, st):
        s = r'\fet0\ftnbj\ftnnar\ftnrstcont\viewkind1'  # footnotes at the page bottom, 1, 2, 3 ...
        if st.page_width and st.page_height:
            s += r'\paperw%d\paperh%d' % (tw(st.page_width), tw(st.page_height))
        if len(st.margins) == 4:
            top, right, bottom, left = st.margins
            s += r'\margt%d\margr%d\margb%d\margl%d' % (tw(top), tw(right), tw(bottom), tw(left))
        if st.two_sided:
            s += r'\facingp\margmirror'
        return s + r'\sectd\sbknone'

    # ---------- formats ----------

    def style_no(self, tag):
        """The paragraph style number of a tag, registering it on first use (0 = Normal)."""
        if not tag or tag not in self.doc.formats:
            return 0
        if tag not in self.styles:
            self.styles[tag] = len(self.styles) + len(self.cstyles) + 1
        return self.styles[tag]

    def cstyle_no(self, tag):
        if tag not in self.cstyles:
            self.cstyles[tag] = len(self.styles) + len(self.cstyles) + 1
        return self.cstyles[tag]

    def para_props(self, f, level=None, grow=False):
        """Paragraph control words of a ParaFormat. `grow`: the paragraph holds a picture, so
        its line height may not be fixed."""
        s = ALIGN.get(f.align, r'\ql')
        s += r'\li%d\fi%d\ri%d\sb%d\sa%d' % (tw(f.left), tw(f.first - f.left), tw(f.right),
                                              tw(f.space_before), tw(f.space_after))
        line = tw(f.size + f.leading)
        if f.fixed_lines and not grow:
            s += r'\sl-%d\slmult0' % line   # FrameMaker: exactly font size + leading
        else:
            s += r'\sl%d\slmult0' % line
        if f.keep_next:
            s += r'\keepn'
        if f.page_break:
            s += r'\pagebb'
        if not f.hyphenate:
            s += r'\hyphpar0'
        if level:
            s += r'\outlinelevel%d' % (level - 1)
        for pos, kind, leader in f.tabs:
            s += TAB_LEADER.get(leader.strip()[:1], '') + TAB_KIND.get(kind, '') + r'\tx%d' % tw(pos)
        return s

    def char_props(self, f):
        """Character control words of a ParaFormat (the paragraph's own font)."""
        s = r'\f%d\fs%d' % (self.font(f.family), round(f.size * 2))
        s += r'\b' if f.bold else ''
        s += r'\i' if f.italic else ''
        s += {'single': r'\ul', 'double': r'\uldb'}.get(f.underline, '')
        s += r'\strike' if f.strike else ''
        s += {'upper': r'\caps', 'small': r'\scaps'}.get(f.caps, '')
        if f.color and f.color != (0, 0, 0):
            s += r'\cf%d' % self.color(f.color)
        return s + r'\lang%d' % self.lang

    def cf_props(self, c):
        """Character control words of a CharFormat: only what it sets."""
        s = ''
        if c.family:
            s += r'\f%d' % self.font(c.family)
        if c.size:
            s += r'\fs%d' % round(c.size * 2)
        if c.bold is not None:
            s += r'\b' if c.bold else r'\b0'
        if c.italic is not None:
            s += r'\i' if c.italic else r'\i0'
        if c.underline is not None:
            s += {'single': r'\ul', 'double': r'\uldb'}.get(c.underline, r'\ul0')
        if c.strike is not None:
            s += r'\strike' if c.strike else r'\strike0'
        if c.caps is not None:
            s += {'upper': r'\caps', 'small': r'\scaps'}.get(c.caps, r'\caps0\scaps0')
        if c.color is not None:
            s += r'\cf%d' % self.color(c.color)
        if c.position is not None:
            s += {'super': r'\super', 'sub': r'\sub'}.get(c.position, r'\nosupersub')
        return s

    def pard(self, tag, extra='', level=None, grow=False, style=True, local=None):
        r"""\pard ... for a paragraph of tag `tag`. The formatting is repeated as direct
        formatting, because RTF readers take a paragraph's look from the control words, not
        from the style it names: the style's, or the paragraph's own (`local`) if it
        overrides its tag in FrameMaker. `style=False` leaves out the style reference."""
        f = local or self.doc.formats.get(tag)
        n = self.style_no(tag) if style else 0
        s = r'\pard\plain' + (r'\s%d' % n if n else '') + extra
        if f is None:
            f = m.ParaFormat(family=DEFAULT_FONT)
        props = self.para_props(f, level, grow)
        if level is None and style and self.outline.get(tag):
            # a heading's tag used in a table cell or footnote: body text, not in the outline
            props += r'\outlinelevel9'
        return s + props + self.char_props(f) + ' '

    # ---------- blocks ----------

    def blocks(self, blocks, extra=''):
        out = []
        for b in blocks:
            out.append(self.block(b, extra))
        return out

    def block(self, b, extra=''):
        if isinstance(b, m.Heading):
            return self.heading(b, extra)
        if isinstance(b, m.Paragraph):
            return self.para(b.inlines, b.tag, extra, b.local)
        if isinstance(b, m.CodeBlock):
            text = esc(b.text)   # its lines become \line: one paragraph, as in FrameMaker
            if b.tag in self.doc.formats:
                return self.pard(b.tag, extra, local=b.local) + text + '\\par\n'
            return self.pard('', extra) + r'{\f%d ' % self.font(MONO_FONT) + text + '}\\par\n'
        if isinstance(b, m.Quote):
            return ''.join(self.blocks(b.blocks, extra))
        if isinstance(b, m.ListBlock):
            return self.list_block(b, 0, extra)
        if isinstance(b, m.Table):
            if extra:
                self.warn('tables inside table cells are written as text paragraphs')
                return ''.join(self.para(c.blocks[0].inlines, c.blocks[0].tag, extra)
                               for r in b.rows for c in r.cells
                               if c and c.blocks and isinstance(c.blocks[0], m.Paragraph))
            return self.table(b)
        if isinstance(b, m.ImageBlock):
            return self.pard('', extra, grow=True) + self.image(b.image) + '\\par\n'
        return ''

    def heading(self, h, extra=''):
        marks = [self.bookmark(a) for a in h.anchors] + ([self.bookmark(h.id)] if h.id else [])
        start = ''.join(r'{\*\bkmkstart %s}' % b for b in marks)
        end = ''.join(r'{\*\bkmkend %s}' % b for b in marks)
        number = esc(h.number) if h.number else ''
        grow = any(isinstance(i, m.Image) for i in h.inlines)
        return (self.pard(h.tag, extra, level=h.level, grow=grow, local=h.local) + number + start
                + self.inlines(h.inlines) + end + '\\par\n')

    def para(self, inlines, tag, extra='', local=None):
        grow = any(isinstance(i, m.Image) for i in inlines)
        return self.pard(tag, extra, grow=grow, local=local) + self.inlines(inlines) + '\\par\n'

    # ---------- lists ----------

    def list_block(self, lst, depth, extra=''):
        """A Word list. Every list gets its own list definition, so that numbering starts
        at the list's own start value; the paragraph's FrameMaker indents stay in charge."""
        n = len(self.lists) + 1
        level = min(depth, 8)
        self.lists.append((n, lst.ordered, lst.start, level))
        out = []
        for item in lst.items:
            first = True
            for b in item:
                if first and isinstance(b, m.Paragraph):
                    tag = b.tag
                    f = b.local or self.doc.formats.get(tag)
                    pard = self.pard(tag, extra + r'\ls%d\ilvl%d' % (n, level), local=b.local,
                                     grow=any(isinstance(i, m.Image) for i in b.inlines))
                    if f is None:  # no FrameMaker indents: a hanging indent per level
                        pard = pard.replace(r'\li0\fi0', r'\li%d\fi-360' % (360 * (level + 1)), 1)
                    out.append(pard + self.inlines(b.inlines) + '\\par\n')
                    first = False
                elif isinstance(b, m.ListBlock):
                    out.append(self.list_block(b, depth + 1, extra))
                else:
                    out.append(self.block(b, extra))
                    first = False
        return ''.join(out)

    def list_tables(self):
        if not self.lists:
            return ''
        defs, overrides = [], []
        for n, ordered, start, own in self.lists:
            levels = []
            for lvl in range(9):
                if ordered:
                    text = r"{\leveltext\'02\'0%d.;}{\levelnumbers\'01;}" % lvl
                    levels.append(r'{\listlevel\levelnfc0\leveljc0\levelfollow0\levelstartat%d'
                                  r'%s\li%d\fi-360}' % (start if lvl == own else 1, text, 360 * (lvl + 1)))
                else:
                    bullet = BULLETS[lvl % len(BULLETS)]
                    text = r"{\leveltext\'01%s;}{\levelnumbers;}" % esc(bullet)
                    levels.append(r'{\listlevel\levelnfc23\leveljc0\levelfollow0\levelstartat1'
                                  r'%s\li%d\fi-360}' % (text, 360 * (lvl + 1)))
            defs.append(r'{\list\listtemplateid%d\listhybrid%s\listid%d}' % (n, ''.join(levels), n))
            overrides.append(r'{\listoverride\listid%d\listoverridecount0\ls%d}' % (n, n))
        return ('{\\*\\listtable' + '\n'.join(defs) + '}\n'
                + '{\\*\\listoverridetable' + ''.join(overrides) + '}\n')

    # ---------- tables ----------

    def table(self, t):
        out = []
        caption = None
        if t.title is not None or t.label:
            title = ([m.Text(t.label)] if t.label else []) + (t.title or [])
            marks = [self.bookmark(a) for a in t.anchors]
            caption = (self.pard('', r'\keepn' if not t.title_below else '',
                                 grow=any(isinstance(i, m.Image) for i in title))
                       + ''.join(r'{\*\bkmkstart %s}{\*\bkmkend %s}' % (b, b) for b in marks)
                       + r'{\b ' + self.inlines(title) + '}\\par\n')
        elif t.anchors:
            out.append(self.pard('') + ''.join(r'{\*\bkmkstart %s}{\*\bkmkend %s}' % (b, b)
                                                for b in (self.bookmark(a) for a in t.anchors)) + '\\par\n')
        if caption and not t.title_below:
            out.append(caption)
        ncols = len(t.widths)
        edges = [0]
        for w in t.widths:
            edges.append(edges[-1] + tw(w))
        pending = [None] * ncols   # rowspan from above: [rows left, colspan]
        for row in t.rows:
            defs, cells = [], []
            c = 0
            while c < ncols:
                if pending[c]:
                    left, span = pending[c]
                    defs.append(self.cell_def(r'\clvmrg', edges[min(c + span, ncols)]))
                    cells.append(self.pard('', r'\intbl') + '\\cell\n')
                    pending[c] = [left - 1, span] if left > 1 else None
                    c += span
                    continue
                cell = row.cells[c] if c < len(row.cells) else None
                if cell is None:  # covered columns are skipped above, so this one is empty
                    defs.append(self.cell_def('', edges[c + 1]))
                    cells.append(self.pard('', r'\intbl') + '\\cell\n')
                    c += 1
                    continue
                span = max(1, min(cell.colspan, ncols - c))
                merge = ''
                if cell.rowspan > 1:
                    merge = r'\clvmgf'
                    pending[c] = [cell.rowspan - 1, span]
                defs.append(self.cell_def(merge, edges[c + span]))
                cells.append(self.cell(cell))
                c += span
            head = r'\trhdr' if row.kind == 'head' else ''
            trow = (r'\trowd\trgaph%d\trleft0%s\trpaddl%d\trpaddr%d\trpaddfl3\trpaddfr3'
                    % (CELL_PAD, head, CELL_PAD, CELL_PAD))
            out.append(trow + ''.join(defs) + '\n' + ''.join(cells) + '\\row\n')
        if caption and t.title_below:
            out.append(caption)
        return ''.join(out)

    @staticmethod
    def cell_def(merge, right):
        return (merge + r'\clvertalt\clbrdrt%s\clbrdrl%s\clbrdrb%s\clbrdrr%s\cellx%d'
                % (BORDER, BORDER, BORDER, BORDER, right))

    def cell(self, cell):
        """A table cell: its paragraphs with \\intbl, the last one ended by \\cell."""
        parts = ''.join(self.blocks(cell.blocks, r'\intbl'))
        if not parts:
            return self.pard('', r'\intbl') + '\\cell\n'
        i = parts.rfind('\\par\n')
        return parts[:i] + '\\cell\n' + parts[i + 5:]

    # ---------- inlines ----------

    def inlines(self, items):
        return ''.join(self.inline(i) for i in items)

    def inline(self, i):
        if isinstance(i, m.Text):
            return self.text(i)
        if isinstance(i, m.LineBreak):
            return r'\line '
        if isinstance(i, m.Anchor):
            b = self.bookmark(i.id)
            return r'{\*\bkmkstart %s}{\*\bkmkend %s}' % (b, b)
        if isinstance(i, m.Link):
            if i.internal:
                inst = 'HYPERLINK \\\\l "%s"' % self.bookmark(i.target)
            else:
                inst = 'HYPERLINK "%s"' % esc(i.target.replace('\\', '\\\\').replace('"', '%22'))
            return self.field(inst, self.inlines(i.children))
        if isinstance(i, m.PageRef):
            return self.field('PAGEREF %s \\\\h' % self.bookmark(i.target), esc(i.text))
        if isinstance(i, m.FootnoteRef):
            return self.footnote(i)
        if isinstance(i, m.IndexTerm):
            # inside the field instruction Word reads \\ as a backslash and ':' as a level
            # separator, so a ':' inside a level becomes ';' and '"' a typographic quote
            entry = ':'.join(lv.replace('\\', '\\\\').replace('"', '\N{RIGHT DOUBLE QUOTATION MARK}')
                             .replace(':', ';') for lv in i.levels)
            return r'{\v' + self.field('XE "%s"' % esc(entry), '') + '}'
        if isinstance(i, m.Image):
            return self.image(i)
        return ''

    def text(self, t):
        s = ''
        if t.ctag and t.ctag in self.doc.char_formats:
            s += r'\cs%d' % self.cstyle_no(t.ctag) + self.cf_props(self.doc.char_formats[t.ctag])
        st = t.style
        if m.BOLD in st:
            s += r'\b'
        if m.ITALIC in st:
            s += r'\i'
        if m.UNDERLINE in st:
            s += r'\ul'
        if m.STRIKE in st:
            s += r'\strike'
        if m.SUPER in st:
            s += r'\super'
        elif m.SUB in st:
            s += r'\sub'
        if m.CODE in st and not (t.ctag and self.doc.char_formats.get(t.ctag, m.CharFormat()).family):
            s += r'\f%d' % self.font(MONO_FONT)
        if not s:
            return esc(t.text)
        return '{' + s + ' ' + esc(t.text) + '}'

    @staticmethod
    def field(inst, result):
        r"""A Word field: instruction `inst` (already RTF), shown as `result` (RTF) until
        Word updates it."""
        return r'{\field{\*\fldinst{ %s }}{\fldrslt{%s}}}' % (inst, result)

    def footnote(self, fn):
        r"""\chftn is Word's automatic footnote number, once in the text and once in the note.
        The note's paragraphs carry no style reference: LibreOffice forces its own footnote
        style on them and then drops direct formatting that equals the named style."""
        paras = []
        for b in fn.blocks:
            if isinstance(b, m.Paragraph):
                mark = r'{\super\chftn} ' if not paras else ''
                grow = any(isinstance(i, m.Image) for i in b.inlines)
                paras.append(self.pard(b.tag, style=False, grow=grow, local=b.local) + mark
                             + self.inlines(b.inlines))
            else:
                if not paras:  # the number needs a paragraph of its own
                    paras.append(r'\pard\plain{\super\chftn}')
                part = self.block(b)
                paras.append(part[:-len('\\par\n')] if part.endswith('\\par\n') else part)
        if not paras:
            return ''
        return r'{\super\chftn}{\footnote ' + r'\par '.join(paras) + '}'

    def bookmark(self, ident):
        r"""Bookmark name for an anchor id: letters, digits and _, at most 40 characters,
        starting with a letter, unique."""
        if ident in self.bookmarks:
            return self.bookmarks[ident]
        name = re.sub(r'\W', '_', ident, flags=re.ASCII)
        if not name[:1].isalpha():
            name = 'b' + name
        name = name[:40]
        used = set(self.bookmarks.values())
        base, n = name, 1
        while name in used:
            n += 1
            suffix = '_%d' % n
            name = base[:40 - len(suffix)] + suffix
        self.bookmarks[ident] = name
        return name

    # ---------- images ----------

    def image(self, img):
        """An embedded picture (PNG or JPEG); other graphics become a placeholder text."""
        kind = None
        data = None
        if img.source and os.path.isfile(img.source):
            ext = os.path.splitext(img.source)[1].lower()
            kind = {'.png': r'\pngblip', '.jpg': r'\jpegblip', '.jpeg': r'\jpegblip'}.get(ext)
            if kind:
                with open(img.source, 'rb') as f:
                    data = f.read()
        size = image_size(data) if data else None
        if not size or not size[0] or not size[1]:
            if not img.source:
                self.warn(f'graphic not found: {img.name} (written as a placeholder)')
            else:
                self.warn(f'{os.path.basename(img.source)}: only PNG and JPEG graphics can be '
                          'embedded in RTF; convert it to PNG (written as a placeholder)')
            return r'{\i [%s]}' % esc(img.alt or os.path.basename(img.name or 'graphic'))
        pw, ph = size
        width = img.width_pt or pw * 0.75   # without a size in the MIF: 96 dpi
        width = min(width, self.text_width)
        height = width * ph / pw
        # \picw/\pich: size in pixels; \picwgoal/\pichgoal: size on the page; data as hex
        return (r'{\pict%s\picw%d\pich%d\picwgoal%d\pichgoal%d '
                % (kind, pw, ph, tw(width), tw(height)) + data.hex() + '}')
