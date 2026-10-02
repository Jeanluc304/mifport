"""Paragraph and character formats: catalogs, inheritance and the questions the
builder asks about them (is this bold, is this monospaced, is this a list).
"""
import re

# The units of the MIF Reference: a didot is 0.01483 inch, a cicero 12 didots, a pixel
# 0.0625 pica.
DIDOT = 0.01483 * 72
UNITS = {'pt': 1.0, 'point': 1.0, 'in': 72.0, '"': 72.0, 'mm': 72 / 25.4, 'millimeter': 72 / 25.4,
         'cm': 72 / 2.54, 'centimeter': 72 / 2.54, 'pc': 12.0, 'pica': 12.0, 'dd': DIDOT,
         'didot': DIDOT, 'cc': 12 * DIDOT, 'cicero': 12 * DIDOT, 'px': 0.75}
LENGTH = re.compile(r'(-?[0-9.]+)\s*(millimeter|centimeter|point|pica|didot|cicero|'
                    r'pt|in|mm|cm|pc|dd|cc|px|")?(?![a-z])', re.I)


def lengths(value, default_unit='pt'):
    """All lengths in a MIF value, in points: '1.0" 2.0 cm' -> [72.0, 56.69]."""
    out = []
    for m in LENGTH.finditer(value or ''):
        unit = (m.group(2) or default_unit).lower()
        out.append(float(m.group(1)) * UNITS.get(unit, 1.0))
    return out


def length(value, default=0.0):
    """The first length in a MIF value, in points."""
    v = lengths(value)
    return v[0] if v else default


def font_props(node):
    """The character properties set in a Font or PgfFont statement, as a dict.

    FTag is left out: a character format name is not a property of the text.
    """
    return {c.name: c.text for c in node.children if c.name.startswith('F') and c.name != 'FTag'}


# FBold and FItalic are the older yes/no form, still read by FrameMaker and used by filters
def is_bold(font):
    w = font.get('FWeight', '').lower()
    return any(k in w for k in ('bold', 'black', 'heavy')) or font.get('FBold') == 'Yes'


def is_italic(font):
    a = font.get('FAngle', '').lower()
    return 'italic' in a or 'oblique' in a or font.get('FItalic') == 'Yes'


def is_underlined(font):
    """FNoUnderlining is the documented value; the reference's own example writes
    NoUnderlining."""
    return font.get('FUnderlining', '') not in ('', 'FNoUnderlining', 'NoUnderlining')


MONO = ('courier', 'consolas', 'mono', 'menlo', 'monaco', 'lucida console', 'letter gothic',
        'andale', 'source code', 'fira code', 'inconsolata', 'fixedsys', 'lucida sans typewriter')


def is_mono(font):
    f = font.get('FFamily', '').lower()
    return any(k in f for k in MONO)


class Formats:
    """Paragraph catalog, character catalog and the resolved format of every paragraph."""

    def __init__(self, root):
        # Catalog formats inherit what they leave out from the format above them
        self.pgf_catalog = {}
        self.last_catalog_format = {'tag': '', 'font': {}}
        cat = root.get('PgfCatalog')
        for p in cat.all('Pgf') if cat else []:
            self.last_catalog_format = self._pgf_props(p, self.last_catalog_format)
            self.pgf_catalog[p.str('PgfTag', '')] = self.last_catalog_format
        self.char_catalog = {}
        cat = root.get('FontCatalog')
        for f in cat.all('Font') if cat else []:
            self.char_catalog[f.str('FTag', '')] = font_props(f)
        self.resolved = {}
        self._resolve_all(root)

    @staticmethod
    def _pgf_props(pgf, base):
        """Apply the statements of a Pgf block to a copy of the property dict `base`.

        Properties are stored as raw values by statement name; the paragraph font is
        stored under 'font' as a dict, merged property by property.
        """
        d = dict(base)
        d['font'] = dict(base.get('font', {}))
        for c in pgf.children:
            if c.name == 'PgfFont':
                d['font'].update(font_props(c))
            elif c.name == 'PgfTag':
                d['tag'] = c.text
            elif c.name == 'PgfNumFormat':
                d['numformat'] = c.text
            elif c.name != 'TabStop':
                d[c.name] = c.value
        return d

    def _resolve_all(self, root):
        """Compute the format of every Para in the file.

        A paragraph without PgfTag and Pgf keeps the format of the previous paragraph in
        the file (the first one that of the last catalog format); a Pgf block changes only
        the properties it lists, after loading the catalog format its PgfTag names. So this
        must run over all paragraphs of the file in file order, whatever flow or cell they
        are in.
        """
        state = self.last_catalog_format
        for para in root.find('Para'):
            for c in para.children:
                if c.name == 'PgfTag':
                    tag = c.text
                    if tag in self.pgf_catalog:
                        state = dict(self.pgf_catalog[tag])
                    else:
                        state = dict(state, tag=tag)
                elif c.name == 'Pgf':
                    tag = c.str('PgfTag')
                    base = self.pgf_catalog[tag] if tag in self.pgf_catalog else state
                    state = self._pgf_props(c, base)
            self.resolved[id(para)] = state

    def of(self, para):
        """The resolved format of a Para node."""
        return self.resolved.get(id(para), {'tag': '', 'font': {}})

    def char_font(self, para_font, current, current_tag, font_node):
        """The character properties after a Font statement inside a paragraph.

        A Font statement keeps the current font for every property it does not list. An
        empty FTag returns to the paragraph font first; a character format name (FTag)
        applies that format. Returns (font, character format name).
        """
        tag_node = font_node.get('FTag')
        tag = current_tag if tag_node is None else tag_node.text
        f = dict(para_font) if tag_node is not None and not tag else dict(current)
        if tag_node is not None and tag:
            f.update(self.char_catalog.get(tag, {}))
        f.update(font_props(font_node))
        return f, tag


# Autonumber formats. A series label ("S:", "T:") comes first; the rest is text with
# building blocks such as <n+>, <n=1>, <a+>, <$chapnum>.
SERIES = re.compile(r'^[A-Za-z]:')
COUNTER = re.compile(r'<[naArR][^>]*>')


def numbering(numformat):
    """Classify an autonumber format: ('bullet', None), ('ordered', restart?) or (None, None).

    A bullet is a format of only one or two symbols and white space ("•\\t"); a list number
    is one counter with at most a period or parenthesis around it ("<n+>.\\t"). Formats
    with words ("Figure <n+>: ", "Step <n+>: ") are labels, not lists.
    """
    if not numformat:
        return None, None
    f = SERIES.sub('', numformat).replace('\\t', '\t').strip()
    if not f:
        return None, None
    counters = COUNTER.findall(f)
    if len(counters) == 1 and re.fullmatch(r'[(\[]?<[^>]*>[.):\]]?', f):
        return 'ordered', '=' in counters[0]
    if not counters and '<' not in f and len(f) <= 2 and not any(ch.isalnum() for ch in f):
        return 'bullet', None
    return None, None
