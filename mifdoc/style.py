"""Style files from the source document's page and format settings (--style).

mif2md writes a pandoc defaults file, mif2adoc an asciidoctor-pdf theme. Both are a
starting point: page size, margins, font sizes, bold/italic, line and paragraph spacing.
Fonts are only suggested in comments, because a font that is not installed stops the
PDF conversion.
"""
import json

from .formats import MONO

SANS = ('helvetica', 'arial', 'sans', 'frutiger', 'univers', 'verdana', 'segoe', 'calibri',
        'myriad', 'futura', 'gill', 'optima', 'tahoma', 'avenir', 'roboto', 'open sans')

# pandoc's LaTeX output: heading level -> KOMA-Script heading command
KOMA_LEVELS = {1: 'section', 2: 'subsection', 3: 'subsubsection', 4: 'paragraph',
               5: 'subparagraph'}


def yaml_str(s):
    """A YAML string (JSON strings are valid YAML)."""
    return json.dumps(s, ensure_ascii=False)


def mm(pt):
    return f'{pt * 25.4 / 72:.1f}mm'


def num(pt):
    return f'{pt:.1f}'.rstrip('0').rstrip('.')


def family_kind(family):
    f = family.lower()
    if any(k in f for k in MONO):
        return 'mono'
    if any(k in f for k in SANS):
        return 'sans'
    return 'serif'


def pandoc_defaults(style, name):
    """A pandoc defaults file (YAML) for the PDF conversion of `name`.md."""
    out = [f'# pandoc defaults written by mif2md from the formats of {name}.mif',
           f'# Use:  pandoc {name}.md --defaults {name}.pandoc.yaml -o {name}.pdf',
           '# Adjust freely; see docs/styling.md.',
           'pdf-engine: lualatex',
           'variables:',
           '  documentclass: scrartcl']
    if style.page_width and style.margins:
        top, right, bottom, left = style.margins
        out += ['  geometry:',
                f'    - paperwidth={mm(style.page_width)}',
                f'    - paperheight={mm(style.page_height)}',
                f'    - top={mm(top)}',
                f'    - bottom={mm(bottom)}',
                f'    - {"inner" if style.two_sided else "left"}={mm(left)}',
                f'    - {"outer" if style.two_sided else "right"}={mm(right)}']
        if style.two_sided:
            out.append('  classoption: twoside')
    body = style.body
    if body and body.size:
        out.append(f'  fontsize: {num(body.size)}pt')
        if body.leading:
            # LaTeX's normal line distance is 1.2 times the font size
            out.append(f'  linestretch: {(body.size + body.leading) / (1.2 * body.size):.2f}')
    fonts = []
    if body and body.family:
        fonts.append(f'mainfont: {yaml_str(body.family)}')
    heading_families = {h.family for h in style.headings.values() if h.family}
    sans = sorted(f for f in heading_families if family_kind(f) == 'sans')
    if sans:
        fonts.append(f'sansfont: {yaml_str(sans[0])}')
    if style.code and style.code.family:
        fonts.append(f'monofont: {yaml_str(style.code.family)}')
    if fonts:
        out.append('  # The fonts of the source document. Install them, then remove the "#":')
        out += [f'  # {f}' for f in fonts]
    tex = ['\\setkomafont{disposition}{\\normalfont}']
    if style.title and style.title.size:
        tex.append(f'\\setkomafont{{title}}{{{koma_font(style.title, body)}}}')
    for level, cmd in KOMA_LEVELS.items():
        h = style.headings.get(level)
        if h and h.size:
            tex.append(f'\\setkomafont{{{cmd}}}{{{koma_font(h, body)}}}')
            # afterskip must be positive, or LaTeX runs the heading into the paragraph
            tex.append(f'\\RedeclareSectionCommand[beforeskip={num(h.space_before or 6)}pt,'
                       f'afterskip={num(h.space_after or 3)}pt]{{{cmd}}}')
    if body and body.space_after:
        tex.append(f'\\setlength{{\\parskip}}{{{num(body.space_after)}pt}}')
    out.append('  header-includes:')
    out += [f"    - '{t}'" for t in tex]
    return '\n'.join(out) + '\n'


def koma_font(fs, body):
    """LaTeX font commands for a heading or title format."""
    cmds = [f'\\fontsize{{{num(fs.size)}pt}}{{{num(fs.size * 1.2)}pt}}\\selectfont']
    kind = family_kind(fs.family) if fs.family else 'serif'
    if fs.family and body and fs.family != body.family:
        cmds.append({'sans': '\\sffamily', 'mono': '\\ttfamily'}.get(kind, '\\rmfamily'))
    if fs.bold:
        cmds.append('\\bfseries')
    if fs.italic:
        cmds.append('\\itshape')
    return ''.join(cmds)


def asciidoctor_theme(style, name):
    """An asciidoctor-pdf theme (YAML) for `name`.adoc, extending the default theme."""
    out = [f'# asciidoctor-pdf theme written by mif2adoc from the formats of {name}.mif',
           f'# Use:  asciidoctor-pdf -a pdf-theme=./{name}-theme.yml {name}.adoc',
           '# Adjust freely; see docs/styling.md and the asciidoctor-pdf theming guide.',
           'extends: default']
    if style.page_width and style.margins:
        top, right, bottom, left = style.margins
        out += ['page:',
                f'  size: [{mm(style.page_width)}, {mm(style.page_height)}]',
                f'  margin: [{mm(top)}, {mm(right)}, {mm(bottom)}, {mm(left)}]']
    body = style.body
    families = [f for f in (body.family if body else '',
                            *(h.family for h in style.headings.values())) if f]
    if body and body.size:
        out += ['base:', f'  font-size: {num(body.size)}']
        if body.leading:
            out.append(f'  line-height: {(body.size + body.leading) / body.size:.2f}')
        if families:
            out.append(f'  # font-family: {yaml_str(families[0])}   (needs the font catalog below)')
        if body.space_after:
            out += ['prose:', f'  margin-bottom: {num(body.space_after)}']
    levels = {1: style.title} if style.title else {}
    # AsciiDoc section level n (== ...) is heading h(n+1); the document title is h1
    levels.update({n + 1: h for n, h in style.headings.items() if n + 1 <= 6})
    if levels:
        out.append('heading:')
        for h_level, fs in sorted(levels.items()):
            if not fs or not fs.size:
                continue
            out += [f'  h{h_level}:', f'    font-size: {num(fs.size)}',
                    f'    font-style: {font_style_name(fs)}']
            if fs.space_before:
                out.append(f'    margin-top: {num(fs.space_before)}')
            if fs.space_after:
                out.append(f'    margin-bottom: {num(fs.space_after)}')
    if style.code and style.code.size:
        out += ['code:', f'  font-size: {num(style.code.size)}']
    if families:
        out += ['# The fonts of the source document. asciidoctor-pdf needs them as TTF files;',
                '# add them here and use the name as font-family in base and heading:',
                '# font:',
                '#   catalog:',
                '#     merge: true',
                f'#     {yaml_str(families[0])}:',
                '#       normal: /path/to/regular.ttf',
                '#       bold: /path/to/bold.ttf',
                '#       italic: /path/to/italic.ttf',
                '#       bold_italic: /path/to/bold-italic.ttf']
    return '\n'.join(out) + '\n'


def font_style_name(fs):
    return {(True, True): 'bold_italic', (True, False): 'bold',
            (False, True): 'italic'}.get((fs.bold, fs.italic), 'normal')
