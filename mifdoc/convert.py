"""Shared command line handling for mif2md and mif2adoc."""
import argparse
import filecmp
import os
import re
import shutil
import sys
from collections import Counter

from . import __version__, mif
from .builder import Builder
from .dump import dump
from .model import walk_images
from .roles import Mapping

# Graphics formats LaTeX (pandoc's PDF route) cannot include, and what it needs for others
PANDOC_IMAGE_NOTES = {
    '.svg': 'SVG graphics: pandoc needs rsvg-convert (package librsvg2-bin) to make a PDF; '
            'without it the PDF conversion fails',
}
PANDOC_UNSUPPORTED = {'.eps', '.ps', '.ai', '.tif', '.tiff', '.bmp', '.wmf', '.emf', '.cgm',
                      '.pict', '.pct', '.gif', '.psd'}


_warned = set()


def warn(msg):
    """Print a warning once."""
    if msg not in _warned:
        _warned.add(msg)
        print(f'WARNING: {msg}', file=sys.stderr)


def arguments(prog, description, ext, extra=None):
    p = argparse.ArgumentParser(prog=prog, description=description)
    p.add_argument('input', help='MIF file (MIF 7.0 or newer)')
    p.add_argument('output', nargs='?', help=f'output file (default: input name with {ext})')
    p.add_argument('--map', metavar='FILE', help='JSON file mapping paragraph and character '
                   'tags to roles (see README)')
    p.add_argument('--image-dir', metavar='DIR', default='images',
                   help='folder for copied graphics, relative to the output file (default: images)')
    p.add_argument('--no-copy-images', action='store_true',
                   help='link graphics where they are instead of copying them')
    p.add_argument('--list-tags', action='store_true',
                   help='list the paragraph tags of the document with their roles, then stop')
    p.add_argument('--dump', action='store_true',
                   help='print the document model (what the converter understood), then stop')
    p.add_argument('--style', action='store_true',
                   help='also write a style file with the page size, margins and formats of '
                        'the MIF file, as a starting point for the PDF (see docs/styling.md)')
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    if extra:
        extra(p)
    return p.parse_args()


def run(args, ext, make_writer, style_file=None):
    """Read args.input, build the document, place graphics, write the output file.

    `style_file` is (file name suffix, function(style, name) -> text) for --style.
    """
    try:
        root, version = mif.load(args.input, warn)
        mapping = Mapping(args.map)
    except (OSError, ValueError) as e:
        sys.exit(f'error: {e}')
    builder = Builder(root, args.input, mapping, warn)
    if args.list_tags:
        list_tags(builder)
        return
    doc = builder.build()
    if args.dump:
        print('\n'.join(dump(doc)))
        return
    output = args.output or os.path.splitext(args.input)[0] + ext
    if os.path.abspath(output) == os.path.abspath(args.input):
        sys.exit('error: the output file would overwrite the MIF file')
    out_dir = os.path.dirname(os.path.abspath(output))
    if not os.path.isdir(out_dir):
        sys.exit(f'error: the folder for the output file does not exist: {out_dir}')
    place_images(doc, args, output, ext)
    text = make_writer().write(doc)
    with open(output, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print(f'wrote {output}')
    if args.style:
        if style_file is None:
            warn('--style: there is no style file for this output format')
            return
        suffix, make = style_file
        stem = os.path.splitext(output)[0]
        path = stem + suffix
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(make(doc.style, os.path.basename(stem)))
        print(f'wrote {path}')


def list_tags(builder):
    counts = Counter(builder.formats.of(p)['tag'] for p in builder.body_paras)
    width = max((len(t) for t in counts), default=3) + 2
    print(f'{"TAG".ljust(width)}{"COUNT":>6}  ROLE')
    for tag, n in sorted(counts.items(), key=lambda x: x[0].lower()):
        props = next(builder.formats.of(p) for p in builder.body_paras
                     if builder.formats.of(p)['tag'] == tag)
        role = builder.role(props)
        if role == 'heading':
            role += str(builder.heading_levels.get(tag, ''))
        print(f'{tag.ljust(width)}{n:>6}  {role}')


def place_images(doc, args, output, ext):
    """Copy graphics next to the output (or link them where they are) and set each
    Image.href to the path the output file should use."""
    out_dir = os.path.dirname(os.path.abspath(output))
    img_dir = os.path.join(out_dir, args.image_dir)
    copied = {}   # source path -> href
    names = set()
    for img in walk_images(doc.blocks):
        if not img.source:
            img.href = img.name
            continue
        if ext == '.md' and getattr(args, 'flavor', '') == 'pandoc':
            e = os.path.splitext(img.source)[1].lower()
            if e in PANDOC_IMAGE_NOTES:
                warn(PANDOC_IMAGE_NOTES[e])
            elif e in PANDOC_UNSUPPORTED:
                warn(f'{img.name}: pandoc cannot put {e} graphics into a PDF; convert it to '
                     'PNG, JPEG or PDF')
        if args.no_copy_images:
            img.href = os.path.relpath(img.source, out_dir).replace(os.sep, '/')
            continue
        source = os.path.realpath(img.source)  # one file referenced in two ways is one file
        if source in copied:
            img.href = copied[source]
            continue
        base, e = os.path.splitext(os.path.basename(source))
        base = re.sub(r'[^\w.-]+', '-', base).strip('-') or 'image'
        name, n = base + e, 1
        while True:
            # never overwrite a different file that is already there (from the user, or a
            # different graphic of the same name); reuse it if it is this very file or an
            # identical copy (from an earlier run)
            target = os.path.join(img_dir, name)
            if name.lower() not in names and (not os.path.exists(target) or same_file(source, target)):
                break
            n += 1
            name = f'{base}-{n}{e}'
        names.add(name.lower())
        if not os.path.exists(target):
            os.makedirs(img_dir, exist_ok=True)
            shutil.copy2(source, target)
        img.href = copied[source] = (args.image_dir.rstrip('/\\') + '/' + name).replace(os.sep, '/')


def same_file(a, b):
    """Are a and b the same file, or files with the same content?"""
    return os.path.samefile(a, b) or filecmp.cmp(a, b, shallow=False)
