#!/usr/bin/env python3
"""mif2rtf: convert a FrameMaker MIF file to RTF for Word and LibreOffice Writer."""
from mifdoc.convert import arguments, run, warn
from mifdoc.rtf import RtfWriter

if __name__ == '__main__':
    args = arguments('mif2rtf', 'Convert a FrameMaker MIF file to RTF (Word, LibreOffice '
                     'Writer), keeping its paragraph and character formats as styles.', '.rtf')
    run(args, '.rtf', lambda: RtfWriter(warn))
