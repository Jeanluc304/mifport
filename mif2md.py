#!/usr/bin/env python3
"""mif2md: convert a FrameMaker MIF file to Markdown."""
from mifdoc.convert import arguments, run, warn
from mifdoc.markdown import MarkdownWriter
from mifdoc.style import pandoc_defaults


def extra(p):
    p.add_argument('--flavor', choices=('pandoc', 'gfm'), default='pandoc',
                   help='pandoc: Pandoc Markdown, for conversion to PDF (default); '
                        'gfm: GitHub Flavored Markdown')


if __name__ == '__main__':
    args = arguments('mif2md', 'Convert a FrameMaker MIF file to Markdown.', '.md', extra)
    style = ('.pandoc.yaml', pandoc_defaults) if args.flavor == 'pandoc' else None
    run(args, '.md', lambda: MarkdownWriter(args.flavor, warn), style)
