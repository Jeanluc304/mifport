"""--dump: the document model as an indented tree, for finding out why a document
converts the way it does.

If the tree is wrong, the problem is in the builder (MIF -> model); if the tree is right
but the output is wrong, it is in a writer.
"""
from . import model as m

STYLE_NAMES = {m.BOLD: 'b', m.ITALIC: 'i', m.CODE: 'code', m.SUPER: 'sup', m.SUB: 'sub',
               m.UNDERLINE: 'u', m.STRIKE: 's'}
WIDTH = 100  # longest text shown per block


def dump(doc):
    """Lines describing the whole document."""
    out = [f'TITLE  {inlines(doc.title) if doc.title else "(none)"}',
           f'LANG   {doc.lang or "(unknown)"}', '']
    notes = []
    out += blocks(doc.blocks, '', notes)
    n = 0
    while n < len(notes):  # footnotes may contain footnotes
        out += ['', f'FOOTNOTE {n + 1}']
        out += blocks(notes[n], '  ', notes)
        n += 1
    return out


def blocks(items, ind, notes):
    out = []
    for b in items:
        if isinstance(b, m.Heading):
            anchors = ''.join(f'  #{a}' for a in b.anchors)
            out.append(f'{ind}H{b.level} {tag(b)} {inlines(b.inlines, notes)}{anchors}')
        elif isinstance(b, m.Paragraph):
            out.append(f'{ind}P  {tag(b)} {inlines(b.inlines, notes)}')
        elif isinstance(b, m.CodeBlock):
            lines = b.text.split('\n')
            out.append(f'{ind}CODE {tag(b)} {len(lines)} line(s): {short(lines[0])}')
        elif isinstance(b, m.Quote):
            out.append(f'{ind}QUOTE')
            out += blocks(b.blocks, ind + '  ', notes)
        elif isinstance(b, m.ListBlock):
            kind = f'numbered, starts at {b.start}' if b.ordered else 'bulleted'
            out.append(f'{ind}LIST {kind}')
            for item in b.items:
                sub = blocks(item, ind + '    ', notes)
                if sub:
                    out.append(ind + '  - ' + sub[0].lstrip())
                    out += sub[1:]
        elif isinstance(b, m.ImageBlock):
            out.append(f'{ind}IMAGE {image(b.image)}')
        elif isinstance(b, m.Table):
            out += table(b, ind, notes)
        else:
            out.append(f'{ind}{type(b).__name__}')
    return out


def table(t, ind, notes):
    title = f' "{t.label}{inlines(t.title, notes)}"' if t.title else ''
    if t.title and t.title_below:
        title += ' (title below the table)'
    anchors = ''.join(f'  #{a}' for a in t.anchors)
    widths = ', '.join(f'{w:.0f}' for w in t.widths)
    out = [f'{ind}TABLE {len(t.widths)} columns ({widths} pt){title}{anchors}']
    for r, row in enumerate(t.rows):
        out.append(f'{ind}  row {r + 1} ({row.kind})')
        for c, cell in enumerate(row.cells):
            if cell is None:
                out.append(f'{ind}    [{c + 1}] (covered by a merged cell)')
                continue
            span = ''
            if cell.colspan > 1 or cell.rowspan > 1:
                span = f' spans {cell.colspan} column(s) x {cell.rowspan} row(s)'
            sub = blocks(cell.blocks, ind + '        ', notes)
            out.append(f'{ind}    [{c + 1}]{span}' + (' ' + sub[0].lstrip() if sub else ' (empty)'))
            out += sub[1:]
    return out


def tag(b):
    return f'[{b.tag}]' if b.tag else '[]'


def inlines(items, notes=None):
    """One line for a list of inlines; formatted text, links, anchors etc. are marked."""
    parts = []
    for i in items or []:
        if isinstance(i, m.Text):
            text = i.text.replace('\t', '\\t').replace('\n', '\\n')
            if i.style:
                names = ','.join(sorted(STYLE_NAMES[s] for s in i.style))
                text = f'<{names}:{text}>'
            parts.append(text)
        elif isinstance(i, m.LineBreak):
            parts.append('<br>')
        elif isinstance(i, m.Link):
            parts.append(f'<link #{i.target}: {inlines(i.children, notes)}>')
        elif isinstance(i, m.PageRef):
            parts.append(f'<page of #{i.target}: {i.text}>')
        elif isinstance(i, m.Anchor):
            parts.append(f'<anchor #{i.id}>')
        elif isinstance(i, m.FootnoteRef):
            if notes is not None:
                notes.append(i.blocks)
                parts.append(f'<footnote {len(notes)}>')
            else:
                parts.append('<footnote>')
        elif isinstance(i, m.IndexTerm):
            parts.append(f'<index {" > ".join(i.levels)}>')
        elif isinstance(i, m.Image):
            parts.append(f'<image {image(i)}>')
    return short(''.join(parts))


def image(img):
    size = f', {img.width_pct}% of the column' if img.width_pct else ''
    found = img.source or 'NOT FOUND'
    return f'{img.name}{size} ({found})'


def short(text):
    return text if len(text) <= WIDTH else text[:WIDTH - 1] + '…'
