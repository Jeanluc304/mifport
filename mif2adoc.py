#!/usr/bin/env python3
"""mif2adoc: convert a FrameMaker MIF file to AsciiDoc."""
from mifdoc.asciidoc import AsciiDocWriter
from mifdoc.convert import arguments, run, warn
from mifdoc.style import asciidoctor_theme

if __name__ == '__main__':
    args = arguments('mif2adoc', 'Convert a FrameMaker MIF file to AsciiDoc.', '.adoc')
    run(args, '.adoc', lambda: AsciiDocWriter(warn), ('-theme.yml', asciidoctor_theme))
