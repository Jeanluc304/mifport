#!/usr/bin/env python3
"""mif2rtf: convert a FrameMaker MIF file to RTF for Word and LibreOffice Writer."""
from mifdoc.convert import arguments, run, warn
from mifdoc.rtf import RtfWriter


def extra(p):
    p.add_argument('--caption-numbers', choices=('chapter', 'simple'), default='chapter',
                   help='chapter: numbers of figures and tables as in FrameMaker (default); '
                        'simple: counted through the document (Figure 7), also in '
                        'cross-references')
    p.add_argument('--no-headers', action='store_true',
                   help='leave out the headers and footers of the master pages')
    p.add_argument('--combine', action='store_true',
                   help='with a folder as input: write all its MIF files into one RTF file '
                        '(the output, default: the folder name with .rtf), in the order of '
                        'their names (appendices, app_a.mif, last), each starting on a new '
                        'page')
    p.add_argument('--order', metavar='FILE',
                   help='with --combine: a text file listing the MIF files in the order to '
                        'combine them, one name per line; files it does not list are left out')


if __name__ == '__main__':
    args = arguments('mif2rtf', 'Convert a FrameMaker MIF file to RTF (Word, LibreOffice '
                     'Writer), keeping its paragraph and character formats as styles.', '.rtf',
                     extra)
    run(args, '.rtf', lambda: RtfWriter(warn, args.caption_numbers))
