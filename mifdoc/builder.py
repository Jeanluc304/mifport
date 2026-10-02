"""MIF tree -> document model.

All FrameMaker knowledge lives here: which text flows are the document, what each
paragraph is (heading, list item, code ...), character formatting, tables, footnotes,
cross-references, anchored graphics, variables and conditional text.
"""
import datetime
import os
import re
import unicodedata
from collections import Counter

from . import model as m
from .formats import (Formats, is_bold, is_italic, is_mono, is_underlined, length, lengths,
                      numbering)
from .mif import Node
from .roles import Mapping, is_sub, tag_number, tag_role

# Char statements -> text. None means a line break; '' means nothing visible.
CHARS = {
    'Tab': '\t', 'HardSpace': '\N{NO-BREAK SPACE}', 'SoftHyphen': '', 'DiscHyphen': '',
    'NoHyphen': '', 'HardHyphen': '-', 'EmDash': '\N{EM DASH}', 'EnDash': '\N{EN DASH}',
    'Cent': '\N{CENT SIGN}', 'Pound': '\N{POUND SIGN}', 'Yen': '\N{YEN SIGN}',
    'Bullet': '\N{BULLET}', 'Dagger': '\N{DAGGER}', 'DoubleDagger': '\N{DOUBLE DAGGER}',
    'ThinSpace': ' ', 'EnSpace': ' ', 'EmSpace': ' ', 'NumberSpace': ' ', 'HardReturn': None,
}
# Typographic spaces and hyphens -> plain ones (LaTeX's pdflatex cannot print them). MIF 8
# and newer may write special characters as characters instead of Char statements; the
# soft hyphen is dropped like <Char SoftHyphen>/<Char DiscHyphen>.
PLAIN = str.maketrans({'\N{EN SPACE}': ' ', '\N{EM SPACE}': ' ', '\N{FIGURE SPACE}': ' ',
                       '\N{THIN SPACE}': ' ', '\N{NON-BREAKING HYPHEN}': '-',
                       '\N{SOFT HYPHEN}': ''})

# Condition tags FrameMaker uses for tracked changes
TRACK_ADDED, TRACK_DELETED = 'FM8_TRACK_CHANGES_ADDED', 'FM8_TRACK_CHANGES_DELETED'

# Standard marker names. Since MIF 5.5 markers are identified by name; the MType number
# is kept for compatibility (2 = Index, 9 = cross-reference). The reference's table names
# the cross-reference type "X-Ref", FrameMaker's marker dialog "Cross-Ref"; both are used.
MARKER_KINDS = {'Index': 'index', 'Cross-Ref': 'xref', 'X-Ref': 'xref'}
STANDARD_MARKERS = {'Header/Footer $1', 'Header/Footer $2', 'Comment', 'Subject', 'Author',
                    'Glossary', 'Equation', 'Hypertext', 'Conditional Text'} | set(MARKER_KINDS)

# ObjectAttribute tags that hold the alternative text of a graphic. The User Guide calls
# the field "Alt Text" (Object Attributes of an anchored frame); the MIF Reference does
# not name the tag, so close spellings are accepted too. "Actual Text" is a replacement
# for text such as a drop cap, not a description, and is not used.
ALT_TAGS = {'alt text', 'alt', 'alttext', 'alternate text'}

# FrameMaker language names -> BCP 47 tags (for pandoc's `lang`)
LANGUAGES = {
    'German': 'de', 'NewGerman': 'de', 'SwissGerman': 'de-CH', 'NewSwissGerman': 'de-CH',
    'UKEnglish': 'en-GB', 'USEnglish': 'en-US', 'English': 'en', 'French': 'fr',
    'CanadianFrench': 'fr-CA', 'Spanish': 'es', 'Catalan': 'ca', 'Italian': 'it',
    'Portuguese': 'pt', 'Brazilian': 'pt-BR', 'Dutch': 'nl', 'Danish': 'da', 'Swedish': 'sv',
    'Norwegian': 'nb', 'Nynorsk': 'nn', 'Finnish': 'fi', 'Polish': 'pl', 'Czech': 'cs',
    'Hungarian': 'hu', 'Russian': 'ru', 'Greek': 'el', 'Turkish': 'tr', 'Japanese': 'ja',
    'AustriaGerman': 'de-AT', 'German1996': 'de', 'SwissGerman1996': 'de-CH',
    'TraditionalChinese': 'zh-Hant', 'SimplifiedChinese': 'zh-Hans', 'Korean': 'ko',
    'Arabic': 'ar', 'Hebrew': 'he',
}

MONTHS = {
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
           'September', 'October', 'November', 'December'],
    'de': ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August',
           'September', 'Oktober', 'November', 'Dezember'],
}
DAYS = {
    'en': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    'de': ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'],
}


def slug(text):
    """An anchor id from text: ASCII letters, digits and hyphens, starting with a letter."""
    t = text.lower()
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        t = t.replace(a, b)
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode()
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:60].strip('-')
    if not t or not t[0].isalpha():
        t = 'ref-' + t if t else 'ref'
    return t


BOOL_TOKEN = re.compile(r'\s*(?:["\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}]'
                        r'([^"\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}]*)'
                        r'["\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}]'
                        r'|(\()|(\))|(AND|OR|NOT)(?![A-Za-z]))', re.I)


def bool_condition(expr):
    """Compile a Boolean condition expression ('"Comment" OR NOT "Draft"') into a function
    that takes the condition tags of a piece of text and says whether it is shown. NOT
    binds tighter than AND, AND tighter than OR. Returns None if the expression is invalid."""
    tokens, pos = [], 0
    while expr[pos:].strip():
        m_ = BOOL_TOKEN.match(expr, pos)
        if not m_:
            return None
        tag, op_open, op_close, op = m_.groups()
        tokens.append(('tag', tag) if tag is not None else ('(',) if op_open else
                      (')',) if op_close else (op.upper(),))
        pos = m_.end()

    def parse_or(i):
        left, i = parse_and(i)
        while i < len(tokens) and tokens[i][0] == 'OR':
            right, i = parse_and(i + 1)
            left = (lambda a, b: lambda t: a(t) or b(t))(left, right)
        return left, i

    def parse_and(i):
        left, i = parse_not(i)
        while i < len(tokens) and tokens[i][0] == 'AND':
            right, i = parse_not(i + 1)
            left = (lambda a, b: lambda t: a(t) and b(t))(left, right)
        return left, i

    def parse_not(i):
        if i < len(tokens) and tokens[i][0] == 'NOT':
            inner, i = parse_not(i + 1)
            return (lambda a: lambda t: not a(t))(inner), i
        if i < len(tokens) and tokens[i][0] == 'tag':
            name = tokens[i][1]
            return (lambda t: name in t), i + 1
        if i < len(tokens) and tokens[i][0] == '(':
            inner, i = parse_or(i + 1)
            if i < len(tokens) and tokens[i][0] == ')':
                return inner, i + 1
        raise ValueError('invalid Boolean condition expression')

    try:
        func, end = parse_or(0)
    except ValueError:
        return None
    return func if end == len(tokens) else None


def marker_kind(mk):
    """'index', 'xref' or None for a Marker statement: by its name, else by its number."""
    name = mk.str('MTypeName', '')
    if name in STANDARD_MARKERS:
        return MARKER_KINDS.get(name)
    return {'2': 'index', '9': 'xref'}.get(mk.val('MType'))


def di_path(di):
    """A device-independent MIF path ('<u\\><c\\>Graphics<c\\>a.png') as a relative path."""
    parts = []
    for kind, name in re.findall(r'<([a-z])\\?>([^<]*)', di):
        if kind == 'r':
            parts = ['/']
        elif kind == 'v':
            parts.append(name + (':' if len(name) == 1 else ''))
        elif kind == 'u':
            parts.append('..')
        elif kind in 'ch':
            parts.append(name)
    return os.path.join(*parts) if parts else ''


class Builder:
    def __init__(self, root, mif_path, mapping=None, warn=print):
        self.root = root
        self.mif_path = mif_path
        self.mif_dir = os.path.dirname(os.path.abspath(mif_path))
        self.map = mapping or Mapping()
        self._warn = warn
        self._warned = set()
        self.formats = Formats(root)

        cat = root.get('TblCatalog')
        self.table_catalog = {t.str('TblTag', ''): t for t in (cat.all('TblFormat') if cat else [])}
        tbls = root.get('Tbls')
        self.tables = {t.val('TblID'): t for t in (tbls.all('Tbl') if tbls else [])}
        frames = root.get('AFrames')
        self.frames = {f.val('ID'): f for f in (frames.all('Frame') if frames else [])}
        self.notes = {n.val('ID'): n for n in root.find('FNote') if n.get('ID') is not None}
        self.xref_formats = {}
        xf = root.get('XRefFormats')
        for x in xf.all('XRefFormat') if xf else []:
            self.xref_formats[x.str('XRefName', '')] = x.str('XRefDef', '')
        self.variables = {}
        vf = root.get('VariableFormats')
        for v in vf.all('VariableFormat') if vf else []:
            self.variables[v.str('VariableName', '')] = v.str('VariableDef', '')
        self.hidden = self._hidden_conditions()

        self.flows = self._body_flows()
        self.column_width = self._column_width()
        self.body_paras = [p for f in self.flows for p in f.find('Para')]
        self.lang = self._language()
        self.heading_levels = self._heading_levels()
        self.used_ids = Counter()  # anchor ids handed out, to keep them unique
        self.anchors = self._xref_targets()

    def warn(self, msg):
        if msg not in self._warned:
            self._warned.add(msg)
            self._warn(msg)

    # ---------- analysis ----------

    def _hidden_conditions(self):
        """Condition tags whose text is hidden (none if the document shows all).

        Tracked changes are shown as if all changes were accepted: deleted text is always
        hidden, inserted text always shown.
        """
        hidden = set()
        self.shown_by = None  # an active Boolean condition expression, compiled
        doc = self.root.get('Document')
        if doc is None or doc.val('DShowAllConditions') != 'Yes':
            cat = self.root.get('ConditionCatalog')
            hidden = {c.str('CTag', '') for c in (cat.all('Condition') if cat else [])
                      if c.val('CState') == 'CHidden'}
            bools = self.root.get('BoolCondCatalog')
            for b in bools.all('BoolCond') if bools else []:
                if b.str('BoolCondState', '').strip("'") == 'Active':
                    self.shown_by = bool_condition(b.str('BoolCondExpr', ''))
                    if self.shown_by is None:
                        self.warn(f'Boolean condition expression not understood: '
                                  f'{b.str("BoolCondExpr", "")!r}; using the show/hide state '
                                  'of each condition instead')
                    break
        return (hidden - {TRACK_ADDED}) | {TRACK_DELETED}

    def is_hidden(self, cond):
        """Is text (or a row) with this Conditional statement hidden? Text with several
        conditions is shown if any of them is shown."""
        tags = [c.text for c in cond.all('InCondition')]
        if TRACK_ADDED in tags or TRACK_DELETED in tags:
            self.warn('tracked changes: the output shows the text with all changes accepted')
        if TRACK_DELETED in tags:
            return True
        tags = [t for t in tags if t != TRACK_ADDED]
        if tags and self.shown_by:  # an active Boolean expression decides
            return not self.shown_by(set(tags))
        return bool(tags) and all(t in self.hidden for t in tags)

    def _body_flows(self):
        """The text flows that run through text frames on body pages, in page order."""
        rect_page = {}
        for n, page in enumerate(self.root.all('Page')):
            if page.val('PageType') == 'BodyPage':
                for r in page.all('TextRect'):
                    rect_page[r.val('ID')] = n
        flows = []
        for flow in self.root.find('TextFlow'):  # also flows written inside a TextRect
            pages = [rect_page[r.value] for r in flow.find('TextRectID') if r.value in rect_page]
            if pages:
                flows.append((min(pages), flow))
        if flows:
            return [f for _, f in sorted(flows, key=lambda x: x[0])]
        # A simple MIF file may have no pages at all: FrameMaker then makes a default
        # layout for its text flows, or for paragraphs written at the top level.
        layout = {r.val('ID') for p in self.root.all('Page') for r in p.find('TextRect')}
        flows = [f for f in self.root.find('TextFlow') if f.str('TFTag') != 'HIDDEN'
                 and not any(r.value in layout for r in f.find('TextRectID'))]
        if not flows and self.root.all('Para'):
            flow = Node('TextFlow')
            flow.items = self.root.all('Para')
            flows = [flow]
        if not flows:
            self.warn('no text flow on body pages found; nothing to convert')
        return flows

    def _column_width(self):
        """The most common width of a text column on body pages, in points: the text
        frame's width without the side head area (if the flow uses side heads), divided
        between its columns."""
        sideheads = any(f.val('TFSideheads') == 'Yes' for f in self.flows)
        widths = Counter()
        for page in self.root.all('Page'):
            if page.val('PageType') == 'BodyPage':
                for r in page.all('TextRect'):
                    w = (lengths(r.val('ShapeRect')) + [0, 0, 0])[2]
                    if sideheads:
                        w -= length(r.val('TRSideheadWidth')) + length(r.val('TRSideheadGap'))
                    n = max(1, int(r.val('TRNumColumns', '1') or 1))
                    w = (w - (n - 1) * length(r.val('TRColumnGap'))) / n
                    if w > 0:
                        widths[round(w)] += 1
        return widths.most_common(1)[0][0] if widths else 0

    def _language(self):
        langs = Counter(self.formats.of(p)['font'].get('FLanguage') for p in self.body_paras)
        langs.pop(None, None)
        name = langs.most_common(1)[0][0] if langs else None
        if not name or name == 'NoLanguage':
            doc = self.root.get('Document')
            name = doc.val('DLanguage') if doc is not None else None
        return LANGUAGES.get(name or '', '')

    def style(self):
        """Page size, margins and the formats used most for each role."""
        st = m.Style()
        doc = self.root.get('Document')
        if doc is not None:
            size = lengths(doc.val('DPageSize'))
            if len(size) >= 2:
                st.page_width, st.page_height = size[:2]
            st.two_sided = doc.val('DTwoSides') == 'Yes'
        rects = Counter()
        for page in self.root.all('Page'):
            if page.val('PageType') == 'BodyPage':
                for r in page.all('TextRect'):
                    rect = lengths(r.val('ShapeRect'))
                    if len(rect) == 4:
                        rects[tuple(round(v, 2) for v in rect)] += 1
        if rects and st.page_width:
            x, y, w, h = rects.most_common(1)[0][0]
            st.margins = (y, st.page_width - x - w, st.page_height - y - h, x)
        elif doc is not None and len(lengths(doc.val('DMargins'))) == 4:
            left, top, right, bottom = lengths(doc.val('DMargins'))  # used by filters
            st.margins = (top, right, bottom, left)

        by_role = {}
        for p in self.body_paras:
            props = self.formats.of(p)
            role = self.role(props)
            if role == 'heading':
                role = f'heading{self.heading_levels.get(props["tag"], 1)}'
            by_role.setdefault(role, Counter())[props['tag']] += 1
        first = {}
        for p in self.body_paras:
            first.setdefault(self.formats.of(p)['tag'], self.formats.of(p))

        def most_used(role):
            tags = by_role.get(role)
            return font_style(first[tags.most_common(1)[0][0]]) if tags else None

        st.body = most_used('paragraph')
        st.title = most_used('title')
        st.code = most_used('code')
        for n in range(1, 7):
            fs = most_used(f'heading{n}')
            if fs:
                st.headings[n] = fs
        return st

    def role(self, props):
        """The role of a paragraph with resolved format `props`."""
        tag = props.get('tag', '')
        if tag in self.map.paragraphs:
            return self.map.paragraphs[tag]
        r = tag_role(tag)
        if r:
            return r
        kind, _ = numbering(props.get('numformat') if props.get('PgfAutoNum') == 'Yes' else None)
        if kind:
            return 'bullet' if kind == 'bullet' else 'numbered'
        if is_mono(props['font']):
            return 'code'
        return 'paragraph'

    def _heading_levels(self):
        """Heading level for every tag with the role 'heading'.

        Tags are ranked by font size (larger first), then by 'Sub' in the name (Heading
        before SubHeading), then by the number in the tag name (Heading1 before Heading2;
        no number counts as 1); the rank is the level.
        """
        keys = {}
        for p in self.body_paras:
            props = self.formats.of(p)
            if self.role(props) == 'heading':
                size = length(props['font'].get('FSize', '12'))
                num = tag_number(props['tag'])
                keys[props['tag']] = (-round(size, 1), is_sub(props['tag']),
                                      num if num is not None else 1)
        ranked = sorted(set(keys.values()))
        return {tag: ranked.index(k) + 1 for tag, k in keys.items()}

    def _xref_targets(self):
        """Cross-reference marker text -> anchor id, for every target in the file."""
        anchors, used = {}, self.used_ids
        self.target_pages, self.target_info = {}, {}
        for para in self.root.find('Para'):
            for mk in para.find('Marker'):
                if marker_kind(mk) != 'xref':
                    continue
                text = ''.join(s.text for s in para.find('String'))
                base = slug(text.strip())
                used[base] += 1
                key = mk.str('MText', '')
                anchors[key] = base if used[base] == 1 else f'{base}-{used[base]}'
                self.target_pages[key] = mk.str('MCurrPage', '')
                self.target_info[key] = {'paratext': text.strip(),
                                         'paranum': (para.str('PgfNumString') or '').strip(),
                                         'paratag': self.formats.of(para)['tag']}
        return anchors

    def xref_text(self, src, fmt_name, target):
        """The text of a cross-reference that has none in the file (allowed in MIF
        written by other programs): its format with the target's text filled in."""
        info = self.target_info.get(src, {})
        number = re.search(r'[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*', info.get('paranum', ''))
        values = dict(info, paranumonly=number.group() if number else '')
        definition = self.xref_formats.get(fmt_name, '<$paratext>')
        out = []
        for part in re.split(r'(<[^<>]*>)', definition):
            block = re.fullmatch(r'<\$(\w+)(?:\[[^\]]*\])?>', part)
            if block and block.group(1) == 'pagenum':
                out.append(m.PageRef(target, self.target_pages.get(src, '')))
            elif block:
                if block.group(1) not in values:
                    self.warn(f'cross-reference format {fmt_name!r}: <${block.group(1)}> not supported')
                out.append(m.Text(values.get(block.group(1), '')))
            elif not part.startswith('<'):  # <Emphasis> and the like switch formats
                out.append(m.Text(part.translate(PLAIN)))
        return [i for i in out if not isinstance(i, m.Text) or i.text]

    # ---------- document ----------

    def build(self):
        doc = m.Document(lang=self.lang, style=self.style())
        blocks = []
        for flow in self.flows:
            blocks += self.blocks(flow.all('Para'), top=True)
        out, prev = [], 0
        for b in blocks:
            if isinstance(b, m.Heading) and b.level == 0:  # a 'title' paragraph
                if doc.title is None:
                    doc.title = b.inlines
                    continue
                b.level = 1
            if isinstance(b, m.Heading):  # no jumps of more than one level
                b.level = min(b.level, prev + 1)
                prev = b.level
                if not b.anchors:  # a unique id, so that no tool invents a duplicate one
                    base = slug(m.plain(b.inlines).strip())
                    self.used_ids[base] += 1
                    b.id = base if self.used_ids[base] == 1 else f'{base}-{self.used_ids[base]}'
            out.append(b)
        doc.blocks = out
        return doc

    def blocks(self, paras, top=False):
        """Blocks for a sequence of Para statements (a flow, a table cell, a footnote).

        Paragraphs become entries first; then runs of code or quote paragraphs are merged
        and list items are nested into lists by their indents.
        """
        entries = []
        for para in paras:
            entries += self.para_entries(para, top)
        return self._group(self._merge(entries))

    def para_entries(self, para, top):
        """Entries for one paragraph: (kind, block-or-data, props) tuples.

        The paragraph itself comes first (unless it is empty), followed by tables and
        graphics anchored in it.
        """
        props = self.formats.of(para)
        role = self.role(props)
        if role == 'skip':
            return []
        after = []
        inlines = self.inlines(para, props, after)
        anchors = [i.id for i in inlines if isinstance(i, m.Anchor)]
        inlines = [i for i in inlines if not isinstance(i, m.Anchor)]
        empty = not m.plain(inlines).strip() and not any(
            isinstance(i, (m.Image, m.FootnoteRef)) for i in inlines)
        out = []
        if empty:
            for b in after:  # anchors of an empty paragraph go to the table below it
                if isinstance(b, m.Table):
                    b.anchors += anchors
                    break
        else:
            out.append(self._entry(para, props, role, inlines, anchors, top))
        out += [('block', b, None) for b in after]
        return out

    def _entry(self, para, props, role, inlines, anchors, top):
        numstr = para.str('PgfNumString') or ''
        if role in ('title', 'heading') or role.startswith('heading'):
            if not top:  # headings in table cells and footnotes stay paragraphs
                return ('para', self._label(numstr, inlines, anchors, props), props)
            if role == 'title':
                level = 0
            elif role == 'heading':
                level = self.heading_levels.get(props['tag'], 1)
            else:
                level = int(role[-1])
            return ('block', m.Heading(level, _strip(inlines), anchors, props['tag']), None)
        if role in ('bullet', 'numbered'):
            number = re.search(r'[0-9]+', numstr)
            _, restart = numbering(props.get('numformat'))
            item = dict(ordered=role == 'numbered', start=int(number.group()) if number else 1,
                        restart=bool(restart), inlines=[m.Anchor(a) for a in anchors] + _strip(inlines),
                        tag=props['tag'])
            return ('item', item, props)
        if role == 'code':
            return ('code', m.plain(inlines), props)
        if role == 'quote':
            return ('quote', self._label(numstr, inlines, anchors, props), props)
        return ('para', self._label(numstr, inlines, anchors, props), props)

    @staticmethod
    def _label(numstr, inlines, anchors, props):
        """A paragraph with its autonumber text ('Figure 3: ') in front, or at the end if
        the format says so (PgfNumAtEnd)."""
        pre = [m.Anchor(a) for a in anchors]
        body = _strip(inlines)
        number = numstr.replace('\t', ' ').translate(PLAIN)
        if numstr.strip() and props.get('PgfNumAtEnd') == 'Yes':
            body = _strip(body + [m.Text(number)])
        elif numstr.strip():
            pre.append(m.Text(number))
        return m.Paragraph(pre + body, props['tag'])

    @staticmethod
    def _merge(entries):
        """Merge consecutive code paragraphs into one code block, quotes into one quote."""
        out = []
        for kind, data, props in entries:
            prev = out[-1] if out else None
            if kind == 'code':
                if prev and prev[0] == 'code' and prev[2]['tag'] == props['tag']:
                    out[-1] = ('code', prev[1] + '\n' + data, prev[2])
                else:
                    out.append((kind, data, props))
            elif kind == 'quote':
                if prev and prev[0] == 'quote' and prev[2]['tag'] == props['tag']:
                    prev[1].append(data)
                else:
                    out.append(('quote', [data], props))
            else:
                out.append((kind, data, props))
        return out

    def _group(self, entries):
        """Turn entries into blocks, nesting list items by indent.

        A list item's level comes from its first-line indent (where the bullet sits); a
        plain paragraph indented at least as far as an item's text continues that item.
        """
        out = []
        stack = []  # [ListBlock, bullet indent, text indent]
        tol = 1.0

        def target():
            return stack[-1][0].items[-1] if stack else out

        for kind, data, props in entries:
            if kind == 'item':
                bullet = length(props.get('PgfFIndent'))
                text = length(props.get('PgfLIndent'))
                while stack and stack[-1][1] > bullet + tol:
                    stack.pop()
                if stack and abs(stack[-1][1] - bullet) <= tol:
                    lst = stack[-1][0]
                    if lst.ordered != data['ordered'] or (data['ordered'] and data['restart']):
                        stack.pop()
                        stack.append([self._new_list(data, target()), bullet, text])
                    else:
                        lst.items.append([m.Paragraph(data['inlines'], data['tag'])])
                else:
                    stack.append([self._new_list(data, target()), bullet, text])
                continue
            if kind == 'block':
                block = data
            elif kind == 'code':
                block = m.CodeBlock(data, props['tag'])
            elif kind == 'quote':
                block = m.Quote(data)
            else:
                block = data
            if kind == 'block':
                # tables and graphics anchored in a list item belong to that item
                if not isinstance(block, (m.Table, m.ImageBlock)):
                    stack.clear()
            else:
                indent = length(props.get('PgfLIndent'))
                while stack and indent < stack[-1][2] - tol:
                    stack.pop()
            target().append(block)
        return out

    @staticmethod
    def _new_list(item, parent):
        lst = m.ListBlock(item['ordered'], [[m.Paragraph(item['inlines'], item['tag'])]], item['start'])
        parent.append(lst)
        return lst

    # ---------- text ----------

    def inlines(self, para, props, after):
        """The inline content of a paragraph. Tables and graphics placed below the
        paragraph are appended to `after`."""
        pfont = props['font']
        font, ctag = pfont, ''
        style = frozenset()
        banner = False
        hidden = False
        out = []
        xref = None  # (target id or None, inlines collected so far)

        def emit(item):
            (xref[1] if xref else out).append(item)

        for line in para.all('ParaLine'):
            for st in line.children:
                n = st.name
                if n == 'Conditional':
                    hidden = self.is_hidden(st)
                    continue
                if n == 'Unconditional':
                    hidden = False
                    continue
                if n in ('BannerTextBegin', 'BannerTextEnd'):
                    # instructions shown in empty elements of structured documents; not content
                    banner = n == 'BannerTextBegin'
                    continue
                if n == 'Font':
                    font, ctag = self.formats.char_font(pfont, font, ctag, st)
                    style = self.char_style(font, pfont, ctag)
                    continue
                if hidden or banner:
                    continue
                if n == 'String':
                    for i, part in enumerate(st.text.translate(PLAIN).split('\N{LINE SEPARATOR}')):
                        if i:
                            emit(m.LineBreak())
                        if part:
                            emit(m.Text(part, style))
                elif n == 'Char':
                    ch = CHARS.get(st.value, '')
                    if st.value not in CHARS:
                        self.warn(f'special character {st.value} left out')
                    emit(m.LineBreak() if ch is None else m.Text(ch, style))
                elif n == 'Variable':
                    text = self.variable(st.str('VariableName', ''))
                    if text:
                        emit(m.Text(text, style))
                elif n == 'XRef':
                    if st.str('XRefSrcFile'):
                        xref = (None, [], '', '', '')
                    elif st.val('XRefSrcIsElem') == 'Yes':
                        self.warn('cross-references to elements of a structured document are '
                                  'kept as text')
                        xref = (None, [], '', '', '')
                    else:
                        src = st.str('XRefSrcText', '')
                        target = self.anchors.get(src)
                        if target is None:
                            self.warn(f'cross-reference target not found: {src!r} (kept as text)')
                        page = ''
                        if '<$pagenum>' in self.xref_formats.get(st.str('XRefName', ''), ''):
                            page = self.target_pages.get(src, '')
                        xref = (target, [], page, src, st.str('XRefName', ''))
                elif n == 'XRefEnd':
                    if xref:
                        target, children, page, src, fmt_name = xref
                        xref = None
                        if target and not m.plain(children).strip():
                            children = self.xref_text(src, fmt_name, target)
                        elif target and page:
                            children = page_ref(children, target, page)
                        out.extend([m.Link(target, children)] if target else children)
                elif n == 'Marker':
                    self.marker(st, emit)
                elif n == 'FNote':
                    note = self.notes.get(st.value)
                    if note is not None:
                        emit(m.FootnoteRef(self.blocks(note.all('Para'))))
                elif n == 'ATbl':
                    tbl = self.tables.get(st.value)
                    if tbl is not None:
                        after.append(self.table(tbl))
                elif n == 'AFrame':
                    self.frame(st.value, emit, after)
        if xref:  # an XRef without XRefEnd: keep its text
            out.extend(xref[1])
        return out

    def char_style(self, font, pfont, ctag):
        """Inline styles of text in `font`, relative to the paragraph font `pfont`."""
        if ctag and ctag in self.map.characters:
            return self.map.characters[ctag]
        s = set()
        if is_bold(font) and not is_bold(pfont):
            s.add(m.BOLD)
        if is_italic(font) and not is_italic(pfont):
            s.add(m.ITALIC)
        if is_mono(font) and not is_mono(pfont):
            s.add(m.CODE)
        pos = font.get('FPosition', '')
        if 'Super' in pos:
            s.add(m.SUPER)
        elif 'Sub' in pos:
            s.add(m.SUB)
        if is_underlined(font) and not is_underlined(pfont):
            s.add(m.UNDERLINE)
        if font.get('FStrike') == 'Yes' and pfont.get('FStrike') != 'Yes':
            s.add(m.STRIKE)
        return frozenset(s)

    def marker(self, mk, emit):
        kind = marker_kind(mk)
        if kind == 'xref':
            target = self.anchors.get(mk.str('MText', ''))
            if target:
                emit(m.Anchor(target))
        elif kind == 'index':
            for entry in split_index(mk.str('MText', '')):
                emit(m.IndexTerm(entry))

    def variable(self, name):
        """The text of a variable, or '' for page-related variables."""
        if name in ('Table Continuation', 'Table Sheet'):
            return ''  # shown only on continued parts of a table
        d = self.variables.get(name)
        if d is None:
            self.warn(f'variable {name!r} has no definition; left out')
            return ''
        if re.search(r'<\$(cur|last)pagenum|<\$pagenum|<\$para(text|num|tag)|<\$marker|'
                     r'<\$(tbl|table)', d):
            self.warn(f'variable {name!r} (page numbers, running headers) has no meaning '
                      'outside FrameMaker pages; left out')
            return ''
        if re.search(r'<\$(short)?(year|month|day)|<\$(hour|minute|second|ampm|AMPM)', d):
            d = self.date_text(name, d)
        d = d.replace('<$filename>', os.path.splitext(os.path.basename(self.mif_path))[0])
        d = d.replace('<$fullfilename>', os.path.abspath(self.mif_path))
        if '<$' in d:
            self.warn(f'variable {name!r}: building blocks in {d!r} not supported; left out')
        d = re.sub(r'<\$[^>]*>', '', d)
        return re.sub(r'</?[^<>]*>', '', d)  # character format switches like <Emphasis>

    def date_text(self, name, d):
        """Fill date building blocks: current date for 'Current Date', the MIF file's
        modification time for creation and modification dates."""
        if re.search(r'creat|modif|änder|erstell', name, re.I):
            t = datetime.datetime.fromtimestamp(os.path.getmtime(self.mif_path))
            self.warn(f'variable {name!r}: using the date of the MIF file')
        else:
            t = datetime.datetime.now()
        lang = 'de' if self.lang.startswith('de') else 'en'
        blocks = {
            'second': str(t.second), 'second00': f'{t.second:02}',
            'minute': str(t.minute), 'minute00': f'{t.minute:02}',
            'hour': str(t.hour % 12 or 12), 'hour01': f'{t.hour % 12 or 12:02}',
            'hour24': str(t.hour), 'ampm': 'am' if t.hour < 12 else 'pm',
            'AMPM': 'AM' if t.hour < 12 else 'PM',
            'daynum': str(t.day), 'daynum01': f'{t.day:02}',
            'dayname': DAYS[lang][t.weekday()], 'shortdayname': DAYS[lang][t.weekday()][:3],
            'monthnum': str(t.month), 'monthnum01': f'{t.month:02}',
            'monthname': MONTHS[lang][t.month - 1], 'shortmonthname': MONTHS[lang][t.month - 1][:3],
            'year': str(t.year), 'shortyear': f'{t.year % 100:02}',
        }
        return re.sub(r'<\$(\w+)>', lambda mm: blocks.get(mm.group(1), mm.group(0)), d)

    # ---------- tables ----------

    def table_format(self, tbl):
        """The table's format: the catalog format named by TblTag, overridden by the
        properties of a TblFormat inside the table. Returns (properties, column widths,
        numbers of hidden conditional columns)."""
        inline = tbl.get('TblFormat')
        tag = tbl.str('TblTag') or (inline.str('TblTag') if inline is not None else '')
        props, widths, hidden = {}, [], {}
        for node in (self.table_catalog.get(tag), inline):
            if node is None:
                continue
            props.update({c.name: c.value for c in node.children if c.name != 'TblColumn'})
            cols = [length(c.val('TblColumnWidth')) for c in node.all('TblColumn')]
            if any(cols):
                widths = cols
            for n, col in enumerate(node.all('TblColumn')):
                cond = col.get('TableColumn') and col.get('TableColumn').get('Conditional')
                num = int(col.val('TblColumnNum', str(n)) or n)
                hidden[num] = cond is not None and self.is_hidden(cond)
        return props, widths, {n for n, h in hidden.items() if h}

    def table(self, tbl):
        fmt, format_widths, hidden_cols = self.table_format(tbl)
        ncols = int(tbl.val('TblNumColumns', '0') or 0)
        widths = [length(w.value) for w in tbl.all('TblColumnWidth')] or format_widths
        title, label = None, ''
        placement = fmt.get('TblTitlePlacement', 'InHeader')
        content = tbl.get('TblTitle') and tbl.get('TblTitle').get('TblTitleContent')
        if content is not None and placement != 'None':
            parts = []
            for para in content.all('Para'):  # not the title's footnotes, which are in Notes
                props = self.formats.of(para)
                label = label or (para.str('PgfNumString') or '').replace('\t', ' ').translate(PLAIN)
                inlines = _strip([i for i in self.inlines(para, props, []) if not isinstance(i, m.Anchor)])
                if inlines:
                    parts += ([m.Text(' ')] if parts else []) + inlines
            title = parts or None

        # Every Row has one Cell per column, also where a straddle covers it; extra Cells
        # are ignored, missing ones are empty. Hidden rows and columns still count for the
        # straddles; a position covered by a cell in a hidden column becomes an empty cell.
        source = []
        for group, kind in (('TblH', 'head'), ('TblBody', 'body'), ('TblF', 'foot')):
            g = tbl.get(group)
            for row in g.all('Row') if g is not None else []:
                cond = row.get('Conditional')
                source.append((kind, row, cond is not None and self.is_hidden(cond)))
        if not ncols:
            ncols = max((len(row.all('Cell')) for _, row, _ in source), default=0)
        rows, covered = [], {}  # covered position -> is its cell in a hidden column?
        for r, (kind, row, hidden) in enumerate(source):
            if hidden:
                continue
            given = row.all('Cell')[:ncols]
            cells = []
            for c in range(ncols):
                if (r, c) in covered:
                    if c not in hidden_cols:
                        cells.append(m.Cell([]) if covered[r, c] else None)
                    continue
                cell = given[c] if c < len(given) else None
                if cell is None:
                    if c not in hidden_cols:
                        cells.append(m.Cell([]))
                    continue
                cs = max(1, min(int(cell.val('CellColumns', '1') or 1), ncols - c))
                rs = max(1, min(int(cell.val('CellRows', '1') or 1), len(source) - r))
                for dr in range(rs):
                    for dc in range(cs):
                        if dr or dc:
                            covered[r + dr, c + dc] = c in hidden_cols
                if c in hidden_cols:
                    continue
                visible_rows = sum(1 for k in range(r, r + rs) if not source[k][2])
                visible_cols = sum(1 for k in range(c, c + cs) if k not in hidden_cols)
                content = cell.get('CellContent')
                blocks = self.blocks(content.all('Para')) if content is not None else []
                cells.append(m.Cell(blocks, visible_cols, visible_rows))
            rows.append(m.Row(kind, cells))
        if len(widths) < ncols:
            widths = widths + [72.0] * (ncols - len(widths))
        widths = [w for c, w in enumerate(widths[:ncols]) if c not in hidden_cols]
        return m.Table(widths, rows, title, label, title_below=placement == 'InFooter')

    # ---------- graphics ----------

    def frame(self, fid, emit, after):
        f = self.frames.get(fid)
        if f is None:
            return
        objs = f.find('ImportObject')
        others = [n for n in ('TextLine', 'PolyLine', 'Polygon', 'Rectangle', 'Ellipse', 'Arc',
                              'RoundRect', 'TextRect', 'Math', 'MathML') if f.find(n)]
        if others and not objs:
            self.warn('a frame with only drawing objects (lines, text lines, text frames, '
                      'equations ...) was left out')
            return
        if others:
            self.warn('drawing objects in frames (lines, text lines, text frames, equations ...) '
                      'left out; only the imported graphics are kept')
        if len(objs) > 1:
            self.warn('frames holding several overlapping graphics are written as separate '
                      'images, one below the other')
        frame_w = (lengths(f.val('ShapeRect')) + [0, 0, 0])[2]
        inline = f.val('FrameType') == 'Inline'
        for ob in objs:
            img = self.image(ob, f, frame_w)
            if img is None:
                continue
            if inline:
                emit(img)
            else:
                after.append(m.ImageBlock(img))

    def image(self, ob, frame, frame_w):
        """An Image for an ImportObject, or None for a graphic copied into the document."""
        facets = [c.text for c in ob.all('Facet')]
        if facets or 'internal inset' in (ob.str('ImportObFile') or ''):
            kinds = ', '.join(sorted(set(facets))) or 'unknown format'
            self.warn(f'a graphic stored inside the MIF file ({kinds}) was left out; only graphics '
                      'linked to a file are converted')
            return None
        name = ''
        di = ob.str('ImportObFileDI')
        if di:
            name = di_path(di)
        elif ob.str('ImportObFile'):
            name = ob.str('ImportObFile')
        url = ob.str('ImportURL') or ''
        if not name and re.fullmatch(r'https?://[^\s\[\]()<>"\'`{}|\\^]+', url):
            return m.Image(None, url, 0.0, 0, '', href=url)  # a graphic on a web server
        if not name and url:
            self.warn(f'graphic address not used, it is not a plain http(s) URL: {url!r}')
            return None
        if not name:
            self.warn('a graphic without a file name was left out')
            return None
        candidates = [os.path.join(self.mif_dir, name)]
        base = os.path.basename(name.replace('\\', '/'))
        candidates += [os.path.join(self.mif_dir, base)]
        candidates += [os.path.join(self.mif_dir, d, base) for d in ('Graphics', 'graphics', 'images')]
        source = next((c for c in candidates if os.path.isfile(c)), None)
        if source is None:
            self.warn(f'graphic not found: {name}')
        # ShapeRect is the size before rotation: a graphic turned by 90 or 270 degrees is
        # as wide as its ShapeRect is high
        rect = lengths(ob.val('ShapeRect')) + [0, 0, 0, 0]
        turned = round(float(ob.val('Angle', '0') or 0)) % 180 == 90
        w = rect[3] if turned else rect[2]
        if frame_w:
            w = min(w, frame_w) if w else frame_w
        alt = ''
        for node in (ob, frame):  # alternative text from the graphic, else from its frame
            for attr in node.all('ObjectAttribute'):
                if not alt and attr.str('Tag', '').strip().lower() in ALT_TAGS:
                    alt = attr.str('Value', '').strip()
        pct = min(100, round(100 * w / self.column_width)) if w and self.column_width else 0
        return m.Image(source, base, w, pct, alt)


def font_style(props):
    """The FontStyle of a resolved paragraph format."""
    font = props['font']
    return m.FontStyle(font.get('FFamily', ''), length(font.get('FSize')), is_bold(font),
                       is_italic(font), length(props.get('PgfLeading')),
                       length(props.get('PgfSpBefore')), length(props.get('PgfSpAfter')))


def page_ref(children, target, page):
    """Replace the last occurrence of the page number in a cross-reference's text by a
    PageRef, so that writers that know page numbers (pandoc -> LaTeX) can use the real one."""
    for n in range(len(children) - 1, -1, -1):
        c = children[n]
        if isinstance(c, m.Text):
            hits = list(re.finditer(rf'(?<![0-9A-Za-z]){re.escape(page)}(?![0-9A-Za-z])', c.text))
            if hits:
                a, b = hits[-1].span()
                parts = [m.Text(c.text[:a], c.style), m.PageRef(target, page), m.Text(c.text[b:], c.style)]
                return children[:n] + [p for p in parts if not isinstance(p, m.Text) or p.text] + children[n + 1:]
    return children


def _strip(inlines):
    """Remove white space and line breaks at the start and end of a list of inlines."""
    inlines = list(inlines)

    def blank(i):
        return isinstance(i, m.LineBreak) or (isinstance(i, m.Text) and not i.text.strip())
    while inlines and blank(inlines[0]):
        inlines.pop(0)
    while inlines and blank(inlines[-1]):
        inlines.pop()
    if inlines and isinstance(inlines[0], m.Text):
        inlines[0] = m.Text(inlines[0].text.lstrip(), inlines[0].style)
    if inlines and isinstance(inlines[-1], m.Text):
        inlines[-1] = m.Text(inlines[-1].text.rstrip(), inlines[-1].style)
    return inlines


def split_index(text):
    """Index marker text -> entries, each a list of levels.

    'a;b:c' is two entries, the second with two levels. Building blocks (<$nopage>),
    character format switches (<Emphasis>) and sort keys ([...]) are removed.
    """
    out = []
    for entry in re.split(r'(?<!\\);', text):
        entry = re.sub(r'<[^>]*>', '', entry)
        entry = re.sub(r'\[[^\]]*\]', '', entry)
        levels = [lv.strip() for lv in re.split(r'(?<!\\):', entry) if lv.strip()]
        if levels:
            out.append([lv.replace('\\:', ':').replace('\\;', ';') for lv in levels])
    return out
