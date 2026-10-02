"""Document model -> Markdown, in two flavours.

pandoc  Pandoc's Markdown, for `pandoc out.md -o out.pdf`: grid tables for complex
        tables, {#id} attributes for anchors, ^super^/~sub~, YAML title block. No raw
        HTML, because pandoc drops it on the way to PDF.
gfm     GitHub Flavored Markdown: pipe tables, HTML tables where a pipe table cannot
        hold the content, <a id> anchors, <sup>/<sub>.
"""
import html
import re
import textwrap

from . import model as m

GRID_WIDTH = 100  # character width of grid tables; pandoc derives relative column widths


class MarkdownWriter:
    def __init__(self, flavor='pandoc', warn=print):
        if flavor not in ('pandoc', 'gfm'):
            raise ValueError(f'unknown Markdown flavour {flavor!r}')
        self.pandoc = flavor == 'pandoc'
        self.warn = warn

    def write(self, doc):
        self.notes = []
        self.shift = 0
        out = []
        if self.pandoc:
            meta = []
            if doc.title:
                meta.append('title: ' + yaml_str(self.inlines(doc.title).replace('\\\n', ' ')))
            if doc.lang:
                meta.append('lang: ' + doc.lang)
            if meta:
                out += ['---'] + meta + ['---', '']
        elif doc.title:
            out += ['# ' + self.inlines(doc.title), '']
            self.shift = 1
        out += self.blocks(doc.blocks)
        n = 0
        while n < len(self.notes):  # footnotes may contain footnotes: loop, don't iterate
            lines = self.blocks(self.notes[n])
            n += 1
            first = f'[^{n}]: '
            out += [''] + [(first if i == 0 else '    ' if line else '') + line
                           for i, line in enumerate(lines)]
        return '\n'.join(out).rstrip('\n') + '\n'

    # ---------- blocks ----------

    def blocks(self, blocks, width=None):
        """Lines for a sequence of blocks, separated by blank lines."""
        out = []
        prev = None
        for b in blocks:
            lines = self.block(b, width)
            if not lines:
                continue
            if out:
                out.append('')
                if isinstance(prev, m.ListBlock) and isinstance(b, m.ListBlock):
                    out += ['<!-- -->', '']  # two lists in a row would merge
            out += lines
            prev = b
        return out

    def block(self, b, width=None):
        if isinstance(b, m.Heading):
            level = min(6, b.level + self.shift)
            text = self.inlines(b.inlines).replace('\\\n', ' ')
            if self.pandoc:
                ids = ''.join(f' {{#{a}}}' for a in (b.anchors or [b.id])[:1] if a)
                extra = [f'[]{{#{a}}}' for a in b.anchors[1:]]
                return ['#' * level + ' ' + text + ids] + ([''] + extra if extra else [])
            return [f'<a id="{a}"></a>' for a in b.anchors] + ['#' * level + ' ' + text]
        if isinstance(b, m.Paragraph):
            return self.para_lines(b.inlines, width)
        if isinstance(b, m.CodeBlock):
            fence = '```'
            while fence in b.text:
                fence += '`'
            return [fence] + b.text.split('\n') + [fence]
        if isinstance(b, m.Quote):
            return ['> ' + line if line else '>' for line in self.blocks(b.blocks, width and width - 2)]
        if isinstance(b, m.ListBlock):
            return self.list_lines(b, width)
        if isinstance(b, m.ImageBlock):
            return [self.image(b.image)]
        if isinstance(b, m.Table):
            return self.table(b)
        return []

    def para_lines(self, inlines, width=None):
        text = self.inlines(inlines)
        lines = []
        segments = text.split('\\\n')
        for n, seg in enumerate(segments):
            wrapped = wrap(seg, width) if width else [seg]
            wrapped = [escape_line_start(line.strip(), self.pandoc) for line in wrapped]
            if n < len(segments) - 1:
                wrapped[-1] += '\\'
            lines += wrapped
        return [line for line in lines if line] or []

    def list_lines(self, lst, width=None):
        tight = all(len(item) == 1 and isinstance(item[0], m.Paragraph) for item in lst.items)
        out = []
        for n, item in enumerate(lst.items):
            marker = f'{lst.start + n}.' if lst.ordered else '-'
            pad = ' ' * (len(marker) + 1)
            lines = self.blocks(item, width and width - len(pad))
            if out and not tight:
                out.append('')
            for i, line in enumerate(lines):
                out.append((marker + ' ' if i == 0 else pad if line else '') + line)
        return out

    # ---------- inlines ----------

    def inlines(self, items):
        out = []
        for it in merge_text(items):
            if isinstance(it, m.Text):
                out.append(self.styled(it.text, it.style))
            elif isinstance(it, m.LineBreak):
                out.append('\\\n')
            elif isinstance(it, m.Link):
                href = '#' + it.target if it.internal else it.target
                text = self.inlines(it.children)
                core = text.strip()
                lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
                out.append(f'{lead}[{core}]({href}){trail}')
            elif isinstance(it, m.PageRef):
                out.append(f'\\pageref{{{it.target}}}' if self.pandoc else escape(it.text, False))
            elif isinstance(it, m.Anchor):
                out.append(f'[]{{#{it.id}}}' if self.pandoc else f'<a id="{it.id}"></a>')
            elif isinstance(it, m.FootnoteRef):
                self.notes.append(it.blocks)
                out.append(f'[^{len(self.notes)}]')
            elif isinstance(it, m.Image):
                out.append(self.image(it))
        return ''.join(out)

    def styled(self, text, style):
        text = text.replace('\t', ' ')
        core = text.strip()  # also no-break and other Unicode spaces: marks must touch text
        if not style or not core:
            return escape(text, self.pandoc)
        lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
        if m.CODE in style:
            ticks = '`'
            while ticks in core:
                ticks += '`'
            pad = ' ' if core.startswith('`') or core.endswith('`') else ''
            s = f'{ticks}{pad}{core}{pad}{ticks}'
        else:
            s = escape(core, self.pandoc)
        if m.SUPER in style:
            s = f'^{s.replace(" ", chr(92) + " ")}^' if self.pandoc else f'<sup>{s}</sup>'
        elif m.SUB in style:
            s = f'~{s.replace(" ", chr(92) + " ")}~' if self.pandoc else f'<sub>{s}</sub>'
        if m.UNDERLINE in style:
            s = f'[{s}]{{.underline}}' if self.pandoc else f'<ins>{s}</ins>'
        if m.ITALIC in style:
            s = f'*{s}*'
        if m.BOLD in style:
            s = f'**{s}**'
        if m.STRIKE in style:
            s = f'~~{s}~~'
        return lead + s + trail

    def image(self, img):
        alt = escape(img.alt, self.pandoc)
        href = (img.href or img.name).replace(' ', '%20')
        size = f'{{width={img.width_pct}%}}' if self.pandoc and img.width_pct else ''
        return f'![{alt}]({href}){size}'

    # ---------- tables ----------

    def table(self, t):
        if self.pandoc:
            caption = [': ' + self.inlines(t.title)] if t.title else []
        else:
            caption = ['**' + escape(t.label, False) + self.inlines(t.title) + '**', ''] if t.title else []
        anchors = ([f'[]{{#{a}}}' for a in t.anchors] if self.pandoc
                   else [f'<a id="{a}"></a>' for a in t.anchors])
        anchors = anchors + [''] if anchors else []
        if is_simple(t):
            body = self.pipe_table(t)
        elif self.pandoc:
            body = self.grid_table(t)
        else:
            body = self.html_table(t)
        if self.pandoc:
            return anchors + body + ([''] + caption if caption else [])
        if t.title_below:
            return anchors + body + ([''] + caption[:-1] if caption else [])
        return anchors + caption + body

    def pipe_table(self, t):
        head = [r for r in t.rows if r.kind == 'head']
        body = [r for r in t.rows if r.kind != 'head']
        ncols = len(t.widths)

        def row(r):
            cells = [self.inlines(c.blocks[0].inlines) if c and c.blocks else '' for c in r.cells]
            return '| ' + ' | '.join(cells) + ' |'

        total = sum(t.widths) or 1
        dashes = [max(3, round(GRID_WIDTH * w / total)) for w in t.widths]
        lines = [row(head[0]) if head else '|' + '   |' * ncols]
        lines.append('|' + '|'.join('-' * d for d in dashes) + '|')
        lines += [row(r) for r in body]
        return lines

    def grid_table(self, t):
        rows, ncols = t.rows, len(t.widths)
        # widths: proportional to FrameMaker's, but at least the longest word of a cell
        total = sum(t.widths) or 1
        cw = [max(3, round((GRID_WIDTH - 3 * ncols) * w / total)) for w in t.widths]
        notes = len(self.notes)
        while True:  # widen columns until no cell has a line longer than its width
            del self.notes[notes:]  # rendering a cell again must not repeat its footnotes
            content, grow = {}, False
            for r, row in enumerate(rows):
                for c, cell in enumerate(row.cells):
                    if cell:
                        w = sum(cw[c:c + cell.colspan]) + 3 * (cell.colspan - 1)
                        content[r, c] = self.blocks(cell.blocks, w)
                        over = max((len(line) for line in content[r, c]), default=0) - w
                        if over > 0:
                            cw[c + cell.colspan - 1] += over
                            grow = True
            if not grow:
                break
        # row heights: single-row cells first, then grow the last row a span covers
        heights = [1] * len(rows)
        for (r, c), lines in content.items():
            if rows[r].cells[c].rowspan == 1:
                heights[r] = max(heights[r], len(lines))
        for (r, c), lines in content.items():
            rs = rows[r].cells[c].rowspan
            if rs > 1:
                room = sum(heights[r:r + rs]) + rs - 1
                if len(lines) > room:
                    heights[r + rs - 1] += len(lines) - room
        xs = [0]
        for w in cw:
            xs.append(xs[-1] + w + 3)
        ys = [0]
        for h in heights:
            ys.append(ys[-1] + h + 1)
        grid = [[' '] * (xs[-1] + 1) for _ in range(ys[-1] + 1)]
        corners = []
        for (r, c), lines in content.items():
            cell = rows[r].cells[c]
            x1, x2 = xs[c], xs[c + cell.colspan]
            y1, y2 = ys[r], ys[r + cell.rowspan]
            for x in range(x1, x2 + 1):
                grid[y1][x] = grid[y2][x] = '-'
            for y in range(y1, y2 + 1):
                grid[y][x1] = grid[y][x2] = '|'
            corners += [(y1, x1), (y1, x2), (y2, x1), (y2, x2)]
            for i, line in enumerate(lines):
                for j, ch in enumerate(line):
                    grid[y1 + 1 + i][x1 + 2 + j] = ch
        for y, x in corners:
            grid[y][x] = '+'
        nhead = 0
        while nhead < len(rows) and rows[nhead].kind == 'head':
            nhead += 1
        if 0 < nhead < len(rows):
            y = ys[nhead]
            grid[y] = ['=' if ch == '-' else ch for ch in grid[y]]
        return [''.join(line).rstrip() for line in grid]

    def html_table(self, t):
        h = HtmlInline(self)
        out = ['<table>']
        for row in t.rows:
            tag = 'th' if row.kind == 'head' else 'td'
            cells = []
            for cell in row.cells:
                if cell is None:
                    continue
                attrs = (f' colspan="{cell.colspan}"' if cell.colspan > 1 else '') + \
                        (f' rowspan="{cell.rowspan}"' if cell.rowspan > 1 else '')
                cells.append(f'<{tag}{attrs}>{h.blocks(cell.blocks)}</{tag}>')
            out.append('<tr>' + ''.join(cells) + '</tr>')
        out.append('</table>')
        return out


class HtmlInline:
    """HTML for table cells in GFM, where Markdown syntax is not available."""

    TAGS = [(m.BOLD, 'strong'), (m.ITALIC, 'em'), (m.CODE, 'code'), (m.SUPER, 'sup'),
            (m.SUB, 'sub'), (m.UNDERLINE, 'ins'), (m.STRIKE, 'del')]

    def __init__(self, writer):
        self.writer = writer

    def blocks(self, blocks):
        parts = []
        for b in blocks:
            if isinstance(b, (m.Paragraph, m.Heading)):
                parts.append(self.inlines(b.inlines))
            elif isinstance(b, m.CodeBlock):
                parts.append(f'<pre><code>{html.escape(b.text)}</code></pre>')
            elif isinstance(b, m.ListBlock):
                tag = 'ol' if b.ordered else 'ul'
                start = f' start="{b.start}"' if b.ordered and b.start != 1 else ''
                items = ''.join(f'<li>{self.blocks(item)}</li>' for item in b.items)
                parts.append(f'<{tag}{start}>{items}</{tag}>')
            elif isinstance(b, m.ImageBlock):
                parts.append(self.img(b.image))
            elif isinstance(b, m.Quote):
                parts.append(f'<blockquote>{self.blocks(b.blocks)}</blockquote>')
            elif isinstance(b, m.Table):
                parts.append('\n'.join(self.writer.html_table(b)).replace('\n', ''))
        if len(parts) == 1 and blocks and isinstance(blocks[0], m.Paragraph):
            return parts[0]
        return ''.join(p if p.startswith('<') else f'<p>{p}</p>' for p in parts)

    def inlines(self, items):
        out = []
        for it in merge_text(items):
            if isinstance(it, m.Text):
                s = html.escape(it.text.replace('\t', ' '), quote=False)
                for st, tag in self.TAGS:
                    if st in it.style:
                        s = f'<{tag}>{s}</{tag}>'
                out.append(s)
            elif isinstance(it, m.LineBreak):
                out.append('<br>')
            elif isinstance(it, m.Link):
                href = '#' + it.target if it.internal else it.target
                out.append(f'<a href="{html.escape(href)}">{self.inlines(it.children)}</a>')
            elif isinstance(it, m.Anchor):
                out.append(f'<a id="{it.id}"></a>')
            elif isinstance(it, m.PageRef):
                out.append(html.escape(it.text))
            elif isinstance(it, m.FootnoteRef):  # GFM footnotes do not work inside HTML
                note = ' '.join(self.blocks([b]) for b in it.blocks)
                out.append(f' ({note})')
            elif isinstance(it, m.Image):
                out.append(self.img(it))
        return ''.join(out)

    @staticmethod
    def img(img):
        return f'<img src="{html.escape(img.href or img.name)}" alt="{html.escape(img.alt)}">'


def is_simple(t):
    """Can this table be a pipe table? One header row at most, no spans, every cell one
    paragraph at most, no line breaks."""
    heads = [r for r in t.rows if r.kind == 'head']
    if len(heads) > 1 or (heads and t.rows[0].kind != 'head'):
        return False
    for row in t.rows:
        for cell in row.cells:
            if cell is None:
                return False
            if cell.colspan > 1 or cell.rowspan > 1 or len(cell.blocks) > 1:
                return False
            if cell.blocks and not isinstance(cell.blocks[0], m.Paragraph):
                return False
            if cell.blocks and any(isinstance(i, (m.LineBreak, m.FootnoteRef))
                                   for i in cell.blocks[0].inlines):
                return False
            # a pipe table is split at "|" before code spans are read
            if cell.blocks and any(isinstance(i, m.Text) and m.CODE in i.style and '|' in i.text
                                   for i in cell.blocks[0].inlines):
                return False
    return True


def merge_text(items):
    """Join neighbouring Text items with the same style."""
    out = []
    for it in items:
        if isinstance(it, m.Text) and out and isinstance(out[-1], m.Text) and out[-1].style == it.style:
            out[-1] = m.Text(out[-1].text + it.text, it.style)
        elif not isinstance(it, m.IndexTerm):  # Markdown has no index
            out.append(it)
    return out


def escape(text, pandoc):
    """Backslash-escape characters that Markdown could read as syntax."""
    special = r'\\`*\[\]<|~^$' + ('@' if pandoc else '')  # $: math in both flavours
    text = re.sub(f'([{special}])', r'\\\1', text)
    text = re.sub(r'(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])', r'\\_', text)  # intraword _ is safe
    text = re.sub(r'&(?=#?\w+;)', r'\\&', text)
    if pandoc:
        text = re.sub(r'-(?=-)', r'-\\', text)  # pandoc would make -- a dash
        text = text.replace('{', '\\{')  # after a link or code span, {...} are attributes
    return text


LINE_START = re.compile(r'^(#|>|[-+*=:%](?=\s|$)|[0-9]+(?=[.)](\s|$))|[A-Za-z](?=[.)]\s)|\((?=\w+\)))')


def escape_line_start(line, pandoc):
    """Escape what would start a heading, list, quote or (pandoc) definition at the start
    of a line."""
    if line.strip() and set(line) <= set('-= '):
        return '\\' + line  # a heading underline or a horizontal rule
    m_ = LINE_START.match(line)
    if not m_:
        return line
    if m_.group(1)[0].isalnum():
        end = m_.end()
        return line[:end] + '\\' + line[end:]
    return '\\' + line


def wrap(text, width):
    """Wrap Markdown text at spaces only (never inside a word, link target or code)."""
    if len(text) <= width:
        return [text]
    return textwrap.wrap(text, width, break_long_words=False, break_on_hyphens=False) or ['']


def yaml_str(s):
    return "'" + s.replace("'", "''") + "'"
