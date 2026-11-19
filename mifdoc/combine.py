"""Several MIF files (the chapters of a book) as one document, for the RTF writer.

Each file is built on its own; here their blocks are put one after the other, each later
file starting with a ChapterBreak (a new page with its own headers and footers). Anchor
ids that two files share are renamed, and cross-references between the files become links.
"""
import os
import re

from . import model as m


def natural_key(path):
    """Sort key for file names that counts numbers as numbers: ch2 before ch10."""
    return [(0, int(p), '') if p.isdigit() else (1, 0, p.lower()) for p in re.split(r'(\d+)', path)]


# File names of appendices, which come after the chapters: app_a.mif, Appendix1.mif, AppB.mif,
# anhang_a.mif (not application.mif)
APPENDIX = re.compile(r'(?i:app|appendix|anhang)(?![a-z])')


def file_order(path):
    """Sort key of the files to combine: by name, numbers counted as numbers (ch2 before
    ch10), appendices after the other files."""
    return (bool(APPENDIX.match(os.path.basename(path))), natural_key(os.path.splitext(path)[0]))


def read_order(order_file, files, folder):
    """The files of `files` in the order of `order_file` (one name per line; empty lines
    and lines starting with # are ignored), and the files it does not list. A name is the
    path relative to the folder, or just the file name; the extension may be left out.
    Raises ValueError for a name that is no file of the folder."""
    by_name = {}
    for f in files:
        rel = os.path.relpath(f, folder)
        for name in {rel, os.path.basename(rel)}:
            for n in (name, os.path.splitext(name)[0]):
                by_name.setdefault(os.path.normcase(n.replace('\\', '/')).lower(), []).append(f)
    with open(order_file, encoding='utf-8-sig') as fh:
        names = [line.strip() for line in fh if line.strip() and not line.strip().startswith('#')]
    ordered = []
    for name in names:
        found = by_name.get(os.path.normcase(name.replace('\\', '/')).lower(), [])
        found = list(dict.fromkeys(found))
        if not found:
            raise ValueError(f'{order_file}: {name!r} is no .mif file of the folder')
        if len(found) > 1:
            raise ValueError(f'{order_file}: {name!r} names more than one file; give its folder too')
        if found[0] in ordered:
            raise ValueError(f'{order_file}: {name!r} is listed twice')
        ordered.append(found[0])
    return ordered, [f for f in files if f not in ordered]


def file_key(path):
    """How cross-references name a file: its name without folder and extension, lower case
    (see builder.file_target)."""
    return os.path.splitext(os.path.basename(path))[0].lower()


def inline_owners(blocks):
    """(object, attribute) for every list of inlines in `blocks`, also inside links,
    footnotes, lists and tables. Each attribute is read anew when the walk gets to it, so
    it may be replaced on the way."""
    for b in blocks:
        if isinstance(b, (m.Heading, m.Paragraph)):
            yield from _owners_in(b, 'inlines')
        elif isinstance(b, m.Quote):
            yield from inline_owners(b.blocks)
        elif isinstance(b, m.ListBlock):
            for item in b.items:
                yield from inline_owners(item)
        elif isinstance(b, m.Table):
            if b.title is not None:
                yield from _owners_in(b, 'title')
            for row in b.rows:
                for c in row.cells:
                    if c:
                        yield from inline_owners(c.blocks)


def _owners_in(obj, attr):
    yield obj, attr
    for i in getattr(obj, attr):
        if isinstance(i, m.Link):
            yield from _owners_in(i, 'children')
        elif isinstance(i, m.FootnoteRef):
            yield from inline_owners(i.blocks)


def anchor_blocks(blocks):
    """Every Heading and Table in `blocks`, the blocks that carry anchor ids of their own
    (not those in footnotes, where FrameMaker has neither)."""
    for b in blocks:
        if isinstance(b, (m.Heading, m.Table)):
            yield b
        if isinstance(b, m.Quote):
            yield from anchor_blocks(b.blocks)
        elif isinstance(b, m.ListBlock):
            for item in b.items:
                yield from anchor_blocks(item)
        elif isinstance(b, m.Table):
            for row in b.rows:
                for c in row.cells:
                    if c:
                        yield from anchor_blocks(c.blocks)


def defined_ids(blocks):
    ids = []
    for b in anchor_blocks(blocks):
        ids += b.anchors + ([b.id] if isinstance(b, m.Heading) and b.id else [])
    for obj, attr in inline_owners(blocks):
        ids += [i.id for i in getattr(obj, attr) if isinstance(i, m.Anchor)]
    return ids


def rename_ids(blocks, rename):
    """Give the anchors in `blocks`, and the links and page numbers pointing to them, the
    new ids of `rename` (old id -> new id)."""
    if not rename:
        return
    for b in anchor_blocks(blocks):
        b.anchors = [rename.get(a, a) for a in b.anchors]
        if isinstance(b, m.Heading) and b.id:
            b.id = rename.get(b.id, b.id)
    for obj, attr in inline_owners(blocks):
        for i in getattr(obj, attr):
            if isinstance(i, m.Anchor):
                i.id = rename.get(i.id, i.id)
            elif isinstance(i, (m.Link, m.PageRef)) and getattr(i, 'internal', True):
                i.target = rename.get(i.target, i.target)


def combine(parts, warn):
    """One Document of `parts`, a list of (MIF file name, Document, cross-reference
    targets of the file: marker text -> anchor id), in that order."""
    used, targets = set(), {}
    for name, doc, anchors in parts:
        defined = set(defined_ids(doc.blocks))
        rename = {}
        for ident in sorted(defined):
            new, n = ident, 1
            while new in used or new != ident and new in defined:
                n += 1
                new = f'{ident}-{n}'
            rename[ident] = new
            used.add(new)
        rename = {a: b for a, b in rename.items() if a != b}
        rename_ids(doc.blocks, rename)
        key = file_key(name)
        for text, ident in anchors.items():
            targets.setdefault((key, text), rename.get(ident, ident))
    keys = {file_key(name) for name, _, _ in parts}

    first = parts[0][1]
    out = m.Document(title=first.title, lang=first.lang, style=first.style,
                     title_tag=first.title_tag, pages=first.pages, blocks=list(first.blocks),
                     formats=dict(first.formats), char_formats=dict(first.char_formats))
    differ, sizes = set(), set()
    for name, doc, _ in parts[1:]:
        out.blocks.append(m.ChapterBreak(name, doc.pages))
        if doc.title:  # written in its own format, as the first file's title is
            out.blocks.append(m.Paragraph(doc.title, doc.title_tag))
        out.blocks += doc.blocks
        for table, other in ((out.formats, doc.formats), (out.char_formats, doc.char_formats)):
            for tag, f in other.items():
                if tag in table and table[tag] != f:
                    differ.add(tag)
                table.setdefault(tag, f)
        st = doc.style
        if st and first.style and (st.page_width, st.page_height) != (
                first.style.page_width, first.style.page_height):
            sizes.add(os.path.basename(name))
    if differ:
        warn('formats that differ between the files keep the definition of the first file '
             'that uses them: ' + ', '.join(sorted(differ)))
    if sizes:
        warn('page size differs from the first file in: %s; all pages get the size of the '
             'first file' % ', '.join(sorted(sizes)))
    _resolve(out.blocks, targets, keys, warn)
    return out


def _resolve(blocks, targets, keys, warn):
    """Cross-references between the files: links to file_target ids become links to the
    anchor in that file; those to files that are not combined are kept as text."""
    for obj, attr in inline_owners(blocks):
        items = getattr(obj, attr)
        if not any(isinstance(i, m.Link) and i.target.startswith('\0') for i in items):
            continue
        new = []
        for i in items:
            if isinstance(i, m.Link) and i.target.startswith('\0'):
                _, key, text = i.target.split('\0', 2)
                target = targets.get((key, text))
                if target:
                    i.target = target
                    new.append(i)
                    continue
                if key not in keys:
                    warn(f'cross-references to the file {key!r} are kept as text: it is not '
                         'among the combined files')
                else:
                    warn(f'cross-reference target not found in {key!r}: {text!r} (kept as text)')
                new += i.children
            else:
                new.append(i)
        setattr(obj, attr, new)
