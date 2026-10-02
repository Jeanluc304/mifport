"""Document model -> AsciiDoc (for Asciidoctor and asciidoctor-pdf)."""
import re
import string

from . import model as m

# A word containing one of these characters or sequences could be read as markup
# (formatting marks, attribute references, macros, replacements such as -- or ->,
# character references such as &amp;).
RISKY = re.compile(r'[*_`#^~+\[\]{}\\]|<<|>>|--|->|=>|<-|<=|::|;;|\(\(|\)\)|\((C|R|TM)\)'
                   r'|&#?\w+;')
# For values inside macro attribute lists (index terms, image alt text)
CHAR_REFS = {
    '\\': '{backslash}', '*': '{asterisk}', '`': '{backtick}', '^': '{caret}', '~': '{tilde}',
    '+': '{plus}', '[': '{startsb}', ']': '{endsb}', '|': '{vbar}', '"': '{quot}',
}
ADMONITION = re.compile(r'^(NOTE|TIP|IMPORTANT|WARNING|CAUTION):')
# Preprocessor directives work on every line, also inside listing blocks; a backslash in
# front turns them into text (and is removed by Asciidoctor)
DIRECTIVE = re.compile(r'^(\s*)(include|ifdef|ifndef|ifeval|endif)::')
LIST_START = re.compile(r'^([0-9]+|[A-Za-z]|[ivxIVX]+)[.)]\s')


class AsciiDocWriter:
    def __init__(self, warn=print):
        self.warn = warn

    def write(self, doc):
        self.pending = ''  # index terms from a heading, for the next paragraph
        self.in_cell = 0   # > 0 while table cells are written
        body = self.blocks(doc.blocks)
        head = []
        if doc.title:
            head.append('= ' + self.inlines(doc.title).replace(' +\n', ' '))
        if doc.lang:
            head.append(f':lang: {doc.lang}')
        if head:
            head.append('')
        return '\n'.join(head + body).rstrip('\n') + '\n'

    # ---------- blocks ----------

    def blocks(self, blocks, continuation=False):
        """Lines for a sequence of blocks. Inside a list item (`continuation`), blocks after
        the first are attached with a '+' line instead of a blank line."""
        out = []
        prev = None
        for b in blocks:
            lines = self.block(b)
            if not lines:
                continue
            if out:
                if continuation and not isinstance(b, m.ListBlock):
                    out.append('+')
                elif not continuation:
                    out.append('')
                    if isinstance(prev, m.ListBlock) and isinstance(b, m.ListBlock):
                        out += ['//-', '']  # two lists in a row would merge
            out += lines
            prev = b
        return out

    def block(self, b, depth=1):
        if isinstance(b, m.Heading):
            terms = [i for i in b.inlines if isinstance(i, m.IndexTerm)]
            self.pending += self.inlines(terms)
            text = self.inlines([i for i in b.inlines if not isinstance(i, m.IndexTerm)])
            text = text.replace(' +\n', ' ')
            return [f'[[{a}]]' for a in b.anchors] + ['=' * min(6, b.level + 1) + ' ' + text]
        if isinstance(b, m.Paragraph):
            return self.para_lines(b.inlines)
        if isinstance(b, m.CodeBlock):
            fence = '----'
            while any(line.strip() == fence for line in b.text.split('\n')):
                fence += '-'
            lines = [DIRECTIVE.sub(r'\1\\\2::', line) for line in b.text.split('\n')]
            if self.in_cell:  # the cell is split at "|" before its content is read
                lines = [line.replace('|', '\\|') for line in lines]
            return [fence] + lines + [fence]
        if isinstance(b, m.Quote):
            return ['____'] + self.blocks(b.blocks) + ['____']
        if isinstance(b, m.ListBlock):
            return self.list_lines(b, depth)
        if isinstance(b, m.ImageBlock):
            return ['image::' + self.image_macro(b.image)]
        if isinstance(b, m.Table):
            return self.table(b)
        return []

    def para_lines(self, inlines):
        text = self.inlines(inlines)
        if self.pending and text:
            text, self.pending = self.pending + text, ''
        lines = [protect_line_start(line.strip()) for line in text.split(' +\n')]
        lines = [line for line in lines if line]
        return [line + ' +' for line in lines[:-1]] + lines[-1:]

    def list_lines(self, lst, depth=1):
        out = []
        if lst.ordered and lst.start != 1:
            out.append(f'[start={lst.start}]')
        marker = ('.' if lst.ordered else '*') * min(depth, 5)
        for item in lst.items:
            lines = []
            for n, b in enumerate(item):
                if isinstance(b, m.ListBlock):
                    lines += self.list_lines(b, depth + 1)
                    continue
                part = self.block(b)
                if n > 0 and part:
                    lines.append('+')
                lines += part
            if lines:
                out.append(marker + ' ' + lines[0])
                out += lines[1:]
        return out

    # ---------- inlines ----------

    def inlines(self, items):
        out = []
        for it in merge_text(items):
            if isinstance(it, m.Text):
                out.append(self.styled(it.text, it.style))
            elif isinstance(it, m.LineBreak):
                out.append(' +\n')
            elif isinstance(it, m.Link):
                text = self.inlines(it.children)
                out.append(f'xref:{it.target}[{text}]' if it.internal else f'{it.target}[{text}]')
            elif isinstance(it, m.Anchor):
                out.append(f'[[{it.id}]]')
            elif isinstance(it, m.PageRef):
                out.append(self.escape(it.text))
            elif isinstance(it, m.FootnoteRef):
                parts = []
                for b in it.blocks:
                    if isinstance(b, (m.Paragraph, m.Heading)):
                        parts.append(self.inlines(b.inlines).replace(' +\n', ' '))
                    else:
                        self.warn('a footnote with lists, tables or graphics was shortened to its text')
                out.append(f'footnote:[{" ".join(parts)}]')
            elif isinstance(it, m.IndexTerm):
                terms = ','.join('"' + self.attr_value(t) + '"' for t in it.levels[:3])
                out.append(f'indexterm:[{terms}]')
            elif isinstance(it, m.Image):
                out.append('image:' + self.image_macro(it))
        return join_parts(out)

    def styled(self, text, style):
        text = text.replace('\t', ' ')
        core = text.strip()  # also no-break and other Unicode spaces: marks must touch text
        if not style or not core:
            return self.escape(text)
        lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
        s = self.escape(core)
        if m.SUPER in style:
            s = '^' + s.replace(' ', '{sp}') + '^'
        elif m.SUB in style:
            s = '~' + s.replace(' ', '{sp}') + '~'
        if m.CODE in style:
            s = f'``{s}``'
        if m.UNDERLINE in style:
            s = f'[.underline]##{s}##'
        if m.STRIKE in style:
            s = f'[.line-through]##{s}##'
        if m.ITALIC in style:
            s = f'__{s}__'
        if m.BOLD in style:
            s = f'**{s}**'
        return lead + s + trail

    @staticmethod
    def escape(text):
        """Protect text from AsciiDoc markup: words with risky characters go into an
        inline passthrough, pass:c[...], which Asciidoctor sets aside before it applies
        any other substitution (it still escapes < > & for HTML).

        A vertical bar is written as {vbar} instead: tables are split into cells at every
        "|" before passthroughs are set aside, but after the attribute reference is not.
        """
        out = []
        for word in re.split(r'(\s+)', text):
            parts = []
            for part in word.split('|'):
                if part and not part.isspace() and RISKY.search(part):
                    core = part.rstrip('\\')  # a backslash before the closing ] would escape it
                    tail = '{backslash}' * (len(part) - len(core))
                    parts.append(('pass:c[' + core.replace(']', '\\]') + ']' if core else '') + tail)
                else:
                    parts.append(part)
            out.append('{vbar}'.join(parts))
        return ''.join(out)

    @staticmethod
    def attr_value(text):
        """Text for a double-quoted value in a macro's attribute list."""
        return ''.join(CHAR_REFS.get(ch, ch) for ch in text)

    def image_macro(self, img):
        target = (img.href or img.name).replace(' ', '%20')
        attrs = ['"' + self.attr_value(img.alt) + '"' if img.alt else '']
        if img.width_pct:
            attrs.append(f'pdfwidth={img.width_pct}%')
            attrs.append(f'scaledwidth={img.width_pct}%')
        return f'{target}[{",".join(attrs)}]'

    # ---------- tables ----------

    def table(self, t):
        out = [f'[[{a}]]' for a in t.anchors]
        if t.title:
            out.append('.' + self.inlines(t.title).replace(' +\n', ' '))
        total = sum(t.widths) or 1
        cols = ','.join(str(max(1, round(100 * w / total))) for w in t.widths)
        opts = []
        if t.rows and t.rows[0].kind == 'head':
            opts.append('header')
            if len(t.rows) > 1 and t.rows[1].kind == 'head':
                self.warn('a table with more than one heading row: only the first is a heading row')
        if t.rows and t.rows[-1].kind == 'foot':
            opts.append('footer')
        attrs = f'cols="{cols}"' + (f',options="{",".join(opts)}"' if opts else '')
        out += [f'[{attrs}]', '|===']
        for n, row in enumerate(t.rows):
            if n:
                out.append('')
            for cell in row.cells:
                if cell is None:
                    continue
                spec = ''
                if cell.colspan > 1:
                    spec += f'{cell.colspan}'
                if cell.rowspan > 1:
                    spec += f'.{cell.rowspan}'
                if spec:
                    spec += '+'
                if any(isinstance(b, m.Table) for b in cell.blocks):
                    self.warn('a table inside a table cell was converted to its text only')
                    cell = m.Cell(flatten(cell.blocks), cell.colspan, cell.rowspan)
                # a line break needs an a| cell: " +" is literal text in a simple cell
                simple = len(cell.blocks) <= 1 and all(
                    isinstance(b, m.Paragraph) and not any(isinstance(i, m.LineBreak) for i in b.inlines)
                    for b in cell.blocks)
                self.in_cell += 1
                if simple:
                    text = ' '.join(self.para_lines(cell.blocks[0].inlines)) if cell.blocks else ''
                    out.append(f'{spec}| {text}'.rstrip())
                else:
                    out.append(f'{spec}a|')
                    out += self.blocks(cell.blocks)
                self.in_cell -= 1
        out.append('|===')
        return out


def flatten(blocks):
    """Replace tables by one paragraph per cell (for tables inside table cells)."""
    out = []
    for b in blocks:
        if isinstance(b, m.Table):
            for row in b.rows:
                for c in row.cells:
                    if c:
                        out += flatten(c.blocks)
        else:
            out.append(b)
    return out


FORMAT_START = re.compile(r'^(\*\*|__|``|##|\[\.|\^|~)')


def join_parts(parts):
    """Join rendered inline parts. A macro ending in "]" (footnote:[], indexterm:[],
    xref:id[] ...) directly followed by formatting marks would be read as the formatting's
    attribute list; {empty} keeps them apart."""
    out = []
    for p in parts:
        if out and out[-1].endswith(']') and FORMAT_START.match(p):
            out.append('{empty}')
        out.append(p)
    return ''.join(out)


def merge_text(items):
    out = []
    for it in items:
        if isinstance(it, m.Text) and out and isinstance(out[-1], m.Text) and out[-1].style == it.style:
            out[-1] = m.Text(out[-1].text + it.text, it.style)
        else:
            out.append(it)
    return out


def protect_line_start(line):
    """Put {empty} in front of a line that AsciiDoc would read as a block, list,
    admonition, attribute entry, comment or directive."""
    if not line:
        return line
    if ((line[0] in string.punctuation and line[0] not in '{"\'(') or line[0].isspace()
            or ADMONITION.match(line)
            or LIST_START.match(line) or re.match(r'^\w+::', line)):
        return '{empty}' + line
    return line
