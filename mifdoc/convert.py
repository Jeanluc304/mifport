"""Shared command line handling for mif2md, mif2adoc and mif2rtf."""
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
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
PANDOC_UNSUPPORTED = {'.eps', '.ps', '.ai', '.tif', '.tiff', '.bmp', '.wmf', '.emf', '.cgm',
                      '.pict', '.pct', '.gif', '.psd'}


_warned = set()
_prefix = ''


def warn(msg):
    """Print a warning once (once per file when a folder is converted)."""
    msg = _prefix + msg
    if msg not in _warned:
        _warned.add(msg)
        print(f'WARNING: {msg}', file=sys.stderr)


def _start_file(name):
    """Begin a new file of a folder: warnings get its name in front and are shown again."""
    global _prefix
    _prefix = f'{name}: ' if name else ''
    _warned.clear()


class ConvertError(Exception):
    """A problem with one input file, reported as `error: ...`."""


def arguments(prog, description, ext, extra=None):
    p = argparse.ArgumentParser(prog=prog, description=description)
    p.add_argument('input', help='MIF file (MIF 7.0 or newer), or a folder: then every .mif '
                   'file in it is converted')
    p.add_argument('output', nargs='?', help=f'output file (default: input name with {ext}); '
                   'with a folder as input, an existing output folder (default: next to each '
                   'MIF file)')
    p.add_argument('-r', '--recursive', action='store_true',
                   help='with a folder as input, also convert the MIF files in its subfolders '
                        '(and repeat the subfolders in the output folder)')
    p.add_argument('--map', metavar='FILE', help='JSON file mapping paragraph and character '
                   'tags to roles (see README)')
    p.add_argument('--image-dir', metavar='DIR', default='images',
                   help='folder for copied graphics, relative to the output file (default: images)')
    p.add_argument('--no-copy-images', action='store_true',
                   help='link graphics where they are instead of copying them')
    p.add_argument('--extract-eps', action='store_true',
                   help='also write the EPS version of graphics stored in the MIF file to the '
                        'image folder; a PNG of the same name there replaces the graphic')
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
    """Convert args.input, a MIF file or a folder of MIF files.

    `style_file` is (file name suffix, function(style, name) -> text) for --style.
    """
    try:
        mapping = Mapping(args.map)
    except (OSError, ValueError) as e:
        sys.exit(f'error: {e}')
    if os.path.isdir(args.input):
        sys.exit(run_folder(args, ext, make_writer, style_file, mapping))
    if args.recursive:
        warn('--recursive only applies when the input is a folder')
    try:
        convert(args.input, args.output, args, ext, make_writer, style_file, mapping)
    except (ConvertError, mif.BookFileError) as e:
        sys.exit(f'error: {e}')


def find_mif_files(folder, recursive):
    """The .mif files in folder (and its subfolders), sorted; links to folders are not followed."""
    found = []
    for path, folders, files in os.walk(folder):
        folders.sort()
        found += [os.path.join(path, f) for f in sorted(files) if f.lower().endswith('.mif')]
        if not recursive:
            break
    return found


def run_folder(args, ext, make_writer, style_file, mapping):
    """Convert every MIF file of the folder args.input. A file that fails is reported and
    the others are still converted. Returns the exit status."""
    folder = args.input
    if args.output and not os.path.isdir(args.output):
        return (f'error: with a folder as input, the output must be an existing folder: '
                f'{args.output}')
    files = find_mif_files(folder, args.recursive)
    if not files:
        return f'error: no .mif files in {folder}' + ('' if args.recursive else
                                                     ' (use --recursive for its subfolders)')
    report = args.list_tags or args.dump
    done, failed, skipped, outputs = 0, [], [], {}
    for path in files:
        rel = os.path.relpath(path, folder)
        _start_file(rel)
        if args.output:
            output = os.path.join(args.output, os.path.splitext(rel)[0] + ext)
        else:
            output = os.path.splitext(path)[0] + ext
        if report:
            print(f'{chr(10) if done or failed or skipped else ""}== {rel} ==')
        else:
            key = os.path.normcase(os.path.abspath(output))
            if key in outputs:
                print(f'error: {rel}: its output {output} is already written for {outputs[key]}',
                      file=sys.stderr)
                failed.append(rel)
                continue
            outputs[key] = rel
        try:
            if args.output and not report:
                os.makedirs(os.path.dirname(output), exist_ok=True)
            convert(path, output, args, ext, make_writer, style_file, mapping)
            done += 1
        except mif.BookFileError:
            skipped.append(rel)
            print(f'skipped {rel}: a MIF book file (its chapter files are converted on their own)',
                  file=sys.stderr)
        except (ConvertError, OSError) as e:
            print(f'error: {rel}: {e}', file=sys.stderr)
            failed.append(rel)
        except Exception as e:  # a bug in the converter: report it, go on with the next file
            print(f'error: {rel}: internal error ({type(e).__name__}: {e}); please report it',
                  file=sys.stderr)
            failed.append(rel)
    _start_file('')
    if not report:
        total = len(files) - len(skipped)
        summary = f'converted {done} of {total} file{"s" if total != 1 else ""}'
        if skipped:
            summary += f', skipped {len(skipped)} book file{"s" if len(skipped) != 1 else ""}'
        print(summary + (f'; failed: {", ".join(failed)}' if failed else ''))
    return 1 if failed else 0


def convert(path, output, args, ext, make_writer, style_file, mapping):
    """Read the MIF file `path`, build the document, place graphics, write `output`
    (None: the input name with ext). Raises ConvertError."""
    try:
        root, version = mif.load(path, warn)
    except mif.BookFileError:
        raise
    except (OSError, ValueError) as e:
        raise ConvertError(e) from None
    builder = Builder(root, path, mapping, warn, pages=ext == '.rtf')
    if args.list_tags:
        list_tags(builder)
        return
    doc = builder.build()
    if args.dump:
        print('\n'.join(dump(doc)))
        return
    output = output or os.path.splitext(path)[0] + ext
    if os.path.abspath(output) == os.path.abspath(path):
        raise ConvertError('the output file would overwrite the MIF file')
    out_dir = os.path.dirname(os.path.abspath(output))
    if not os.path.isdir(out_dir):
        raise ConvertError(f'the folder for the output file does not exist: {out_dir}')
    stored_graphics(doc, args, output)
    if ext != '.rtf':  # RTF embeds its pictures
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


def stored_graphics(doc, args, output):
    """Graphics stored in the MIF file: use a PNG of the same name from the image folder if
    there is one (made by the user from the EPS file), and write the EPS files if asked."""
    img_dir = os.path.join(os.path.dirname(os.path.abspath(output)), args.image_dir)
    written = set()
    for img in walk_images(doc.blocks):
        if not img.data:
            continue
        replaced = False
        path = os.path.join(img_dir, img.name)
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                data = f.read()
            if data[:8] == PNG_SIGNATURE:
                replaced = data != img.data
                img.data = data
            else:
                warn(f'{path} is not a PNG file; not used')
        if args.extract_eps and img.eps:
            eps = os.path.splitext(path)[0] + '.eps'
            os.makedirs(img_dir, exist_ok=True)
            with open(eps, 'wb') as f:
                f.write(img.eps)
            written.add(eps)
        if img.other_formats and not replaced:
            hint = '; --extract-eps gets the better version' if img.eps else ''
            warn(f'a graphic stored inside the MIF file was converted from its FrameImage version, '
                 f'not from {img.other_formats}; it can be a screen preview of lower quality{hint}')
    if args.extract_eps:
        print(f'wrote {len(written)} EPS file{"" if len(written) == 1 else "s"}'
              + (f' to {img_dir}' if written else ''))


def place_images(doc, args, output, ext):
    """Copy graphics next to the output (or link them where they are) and set each
    Image.href to the path the output file should use."""
    out_dir = os.path.dirname(os.path.abspath(output))
    img_dir = os.path.join(out_dir, args.image_dir)
    copied = {}   # source path -> href
    names = set()
    for img in walk_images(doc.blocks):
        if img.data:  # stored inside the MIF file; its name comes from its content
            os.makedirs(img_dir, exist_ok=True)
            path = os.path.join(img_dir, img.name)
            if not os.path.exists(path):  # it can be the user's better version
                with open(path, 'wb') as f:
                    f.write(img.data)
            img.href = args.image_dir.rstrip('/\\').replace(os.sep, '/') + '/' + img.name
            continue
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
