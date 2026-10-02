#!/usr/bin/env python3
"""Write sample.mif (MIF 2015, UTF-8) and sample-mif7.mif (MIF 7.00, FrameRoman) plus
the graphic they use. The files are written by this script, not by FrameMaker; they
contain one example of every feature the converters handle, written as Adobe's MIF
Reference and FrameMaker User Guide describe it (see docs/sources.md).

    python3 samples/sample/make_sample.py [folder]

The files go next to this script unless another folder is given (the tests use that to
check that the committed files are up to date).
"""
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def s(text):
    """A MIF string literal, escaped as the MIF Reference describes: \\\\ \\q \\Q \\> \\t."""
    for a, b in (('\\', '\\\\'), ("'", '\\q'), ('`', '\\Q'), ('>', '\\>'), ('\t', '\\t')):
        text = text.replace(a, b)
    return '`' + text + "'"


def font(family='Times', size='11.0 pt', weight='Regular', angle='Regular', **extra):
    items = [f'<FFamily {s(family)}>', f'<FSize {size}>', f'<FWeight {s(weight)}>',
             f'<FAngle {s(angle)}>', '<FLanguage USEnglish>']
    items += [f'<{k} {v}>' for k, v in extra.items()]
    return ' '.join(items)


def pgf(tag, fnt, numformat=None, findent='0.0 mm', lindent='0.0 mm', before='0.0 pt',
        after='0.0 pt', leading='2.0 pt'):
    num = f"<PgfAutoNum Yes> <PgfNumFormat {s(numformat)}>" if numformat else '<PgfAutoNum No>'
    return (f'<Pgf <PgfTag {s(tag)}> <PgfFIndent {findent}> <PgfLIndent {lindent}> '
            f'<PgfSpBefore {before}> <PgfSpAfter {after}> <PgfLeading {leading}> {num} '
            f'<PgfFont <FTag `\'> {fnt}>>')


CATALOG = [
    pgf('Title', font('Helvetica', '24.0 pt', 'Bold'), after='12.0 pt'),
    pgf('Heading1', font('Helvetica', '18.0 pt', 'Bold'), before='18.0 pt', after='6.0 pt'),
    pgf('Heading2', font('Helvetica', '14.0 pt', 'Bold'), before='12.0 pt', after='4.0 pt'),
    pgf('Heading3', font('Helvetica', '12.0 pt', 'Bold'), before='9.0 pt', after='3.0 pt'),
    pgf('Subsection', font('Helvetica', '12.0 pt', 'Bold', 'Italic'), before='9.0 pt', after='3.0 pt'),
    pgf('Quote', font('Times', '11.0 pt', 'Regular', 'Italic'), None, '10.0 mm', '10.0 mm'),
    pgf('Body', font(), after='6.0 pt'),
    pgf('Bulleted', font(), '•\\t', '5.0 mm', '10.0 mm'),
    pgf('Bulleted2', font(), '–\\t', '10.0 mm', '15.0 mm'),
    pgf('Numbered1', font(), 'S:<n=1>.\\t', '5.0 mm', '10.0 mm'),
    pgf('Numbered', font(), 'S:<n+>.\\t', '5.0 mm', '10.0 mm'),
    pgf('Indented', font(), None, '10.0 mm', '10.0 mm'),
    pgf('Code', font('Courier New', '10.0 pt')),
    pgf('TableTitle', font('Helvetica', '10.0 pt', 'Bold'), 'T:Table <n+>: '),
    pgf('CellHeading', font('Helvetica', '10.0 pt', 'Bold')),
    pgf('CellBody', font('Times', '10.0 pt')),
    pgf('CellNumbered1', font('Times', '10.0 pt'), 'S:<n=1>.\\t', '0.0 mm', '5.0 mm'),
    pgf('CellNumbered', font('Times', '10.0 pt'), 'S:<n+>.\\t', '0.0 mm', '5.0 mm'),
    pgf('CellBullet', font('Times', '10.0 pt'), '•\\t', '0.0 mm', '5.0 mm'),
    pgf('Footnote', font('Times', '9.0 pt')),
    pgf('Figure', font('Times', '10.0 pt', 'Regular', 'Italic'), 'F:Figure <n+>: '),
]

CHAR_FORMATS = [
    "<Font <FTag `Emphasis'> <FAngle `Italic'>>",
    "<Font <FTag `Strong'> <FWeight `Bold'>>",
    "<Font <FTag `Command'> <FFamily `Courier New'>>",
]


def line(*items):
    return '<ParaLine ' + ' '.join(items) + '>'


def string(text):
    return f'<String {s(text)}>'


def ftag(tag=''):
    return f"<Font <FTag {s(tag)}> <FLocked No>>"


def para(tag, *lines, numstring=None, rect=False):
    head = f'<Para <PgfTag {s(tag)}>'
    if numstring is not None:
        head += f' <PgfNumString {s(numstring)}>'
    if rect:
        lines = (line('<TextRectID 10>'),) + lines
    return head + ' ' + ' '.join(lines) + '>'


def marker(mtype, text, page=''):
    return f'<Marker <MType {mtype}> <MText {s(text)}> <MCurrPage {s(page)}>>'


def body():
    return [
        para('Title', line(string('Sample Document')), rect=True),
        para('Body', line(string('Version '), '<Variable <VariableName `Version\'>>',
                          string(', pages: '), '<Variable <VariableName `Page Count\'>>')),
        para('Heading1', line(marker(9, '11: Heading1: Introduction', '2'),
                              marker(2, 'Introduction;Sample:first entry'), string('Introduction'))),
        para('Body', line(string('Plain text with '), ftag('Emphasis'), string('italic'), ftag(),
                          string(', '), ftag('Strong'), string('bold'), ftag(), string(', '),
                          ftag('Command'), string('code_text()'), ftag(), string(' and E = mc'),
                          "<Font <FTag `'> <FPosition FSuperscript>>", string('2'), ftag(),
                          string('.')),
                     line(string(' A footnote'), '<FNote 1>', string(' follows.'))),
        para('Body', line(string('Characters that are markup elsewhere: * _ ` [x] | ~ ^ # {author} '
                                 '-- <<a>> a::b -> 50 % & 100$')),
             line('<Char EmDash>', string(' a dash, a forced'), '<Char HardReturn>',
                  string('line break and café über, \N{VULGAR FRACTION ONE HALF} '
                         '\N{MULTIPLICATION SIGN} 3\N{DEGREE SIGN} and x\N{SUPERSCRIPT THREE}.'))),
        para('Body', line(string('1. Not a list, because it is a body paragraph.'))),
        para('Body', line(string('Hidden text follows'),
                          "<Conditional <InCondition `Internal'>>", string(' SECRET'),
                          '<Unconditional>', string('.'))),
        para('Heading2', line(string('Lists'))),
        para('Bulleted', line(string('First bullet')), numstring='•\t'),
        para('Bulleted2', line(string('Nested bullet')), numstring='–\t'),
        para('Bulleted', line(string('Second bullet')), numstring='•\t'),
        para('Indented', line(string('A paragraph that continues the second bullet.'))),
        para('Numbered1', line(string('Step one')), numstring='1.\t'),
        para('Numbered', line(string('Step two')), numstring='2.\t'),
        para('Numbered1', line(string('A new list, step one again')), numstring='1.\t'),
        para('Code', line(string('for x in range(3):'))),
        para('Code', line(string('    print(x * 2)'))),
        para('Heading2', line(marker(9, '12: Heading2: Tables and graphics', '3'),
                              string('Tables and graphics'))),
        para('Body', line(string('See '), xref('11: Heading1: Introduction', '“Introduction” on page 2'),
                          string(' and the table below.'), '<ATbl 1>')),
        para('Body', line('<AFrame 5>')),
        para('Figure', line(string('A small picture.')), numstring='Figure 1: '),
        para('Body', line('<AFrame 6>'), line(string('A graphic stored in the file is left out.'))),
        para('Heading2', line(string('More structures'))),
        para('Heading3', line(marker(9, '13: Heading3: Lists with references', '3'),
                              string('Lists with references'))),
        para('Numbered1', line(string('Read '), xref('12: Heading2: Tables and graphics',
                                                     '“Tables and graphics” on page 3'),
                               string(' first.')), numstring='1.\t'),
        para('Numbered', line(string('Then check the parts in this table:'), '<ATbl 2>'),
             numstring='2.\t'),
        para('Numbered', line(string('Finish with an inline '), '<AFrame 7>', string(' picture.')),
             numstring='3.\t'),
        para('Body', line(string('A paragraph between two parts of a list.'))),
        para('Numbered', line(string('The list goes on with step four.')), numstring='4.\t'),
        para('Subsection', line(string('Formatting and quotes'))),
        para('Body', line(string('Underlined '), "<Font <FTag `'> <FUnderlining FSingle>>",
                          string('words'), ftag(), string(', struck out '),
                          "<Font <FTag `'> <FStrike Yes>>", string('words'), ftag(),
                          string(', H'), "<Font <FTag `'> <FPosition FSubscript>>", string('2'),
                          ftag(), string('O, a tab'), '<Char Tab>', string('and a hard'),
                          '<Char HardSpace>', string('space.'))),
        para('Quote', line(string('A quoted paragraph.'))),
        para('Quote', line(string('Its second paragraph, see '),
                           xref('13: Heading3: Lists with references',
                                '“Lists with references” on page 3'), string('.'))),
        para('Body', line(string('Two graphics in one frame:'), '<AFrame 9>')),
    ]


def xref(target, text):
    """A cross-reference with FrameMaker's resolved text."""
    return (f"<XRef <XRefName `Heading & Page'> <XRefSrcText {s(target)}> <XRefSrcFile `'>> "
            f"{string(text)} <XRefEnd>")


TABLE = """
<Tbls
 <Tbl
  <TblID 1>
  <TblTag `Format A'>
  <TblNumColumns 3>
  <TblColumnWidth 40.0 mm>
  <TblColumnWidth 40.0 mm>
  <TblColumnWidth 80.0 mm>
  <TblTitle <TblTitleContent
   <Para <PgfTag `TableTitle'> <PgfNumString `Table 1: '> <ParaLine <String `Sample table'>>>>>
  <TblH
   <Row
    <Cell <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `Name'>>>>>
    <Cell <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `Value'>>>>>
    <Cell <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `Notes'>>>>>
   >
  >
  <TblBody
   <Row
    <Cell <CellColumns 2> <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `Spans two columns'>>>>>
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `(covered)'>>>>>
    <Cell <CellRows 2> <CellContent
     <Para <PgfTag `CellBody'> <ParaLine <String `Spans two rows.'>>>
     <Para <PgfTag `CellBody'> <ParaLine <String `Second paragraph | with a bar.'>>>>>
   >
   <Row
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `alpha'>>>>>
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `42'>>>>>
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `(covered)'>>>>>
   >
  >
 >
 <Tbl
  <TblID 2>
  <TblTag `Format B'>
  <TblNumColumns 2>
  <TblColumnWidth 50.0 mm>
  <TblColumnWidth 90.0 mm>
  <TblTitle <TblTitleContent
   <Para <PgfTag `TableTitle'> <PgfNumString `Table 2: '> <ParaLine <String `Parts'>>>>>
  <TblH
   <Row
    <Cell <CellColumns 2> <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `Parts and notes'>>>>>
    <Cell <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `(covered)'>>>>>
   >
   <Row
    <Cell <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `Part'>>>>>
    <Cell <CellContent <Para <PgfTag `CellHeading'> <ParaLine <String `Notes'>>>>>
   >
  >
  <TblBody
   <Row
    <Cell <CellContent
     <Para <PgfTag `CellNumbered1'> <PgfNumString `1.\\t'> <ParaLine <String `Open the lid'>>>
     <Para <PgfTag `CellNumbered'> <PgfNumString `2.\\t'> <ParaLine <String `Close it again'>>>>>
    <Cell <CellContent
     <Notes <FNote <ID 2> <Para <PgfTag `Footnote'> <ParaLine <String `A note from a table cell.'>>>>>
     <Para <PgfTag `CellBody'> <ParaLine <String `Handle with care'> <FNote 2> <String `.'>>>>>
   >
   <Row
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <AFrame 8>>>>>
    <Cell <CellContent
     <Para <PgfTag `CellBullet'> <PgfNumString `•\\t'> <ParaLine <String `light'>>>
     <Para <PgfTag `CellBullet'> <PgfNumString `•\\t'> <ParaLine <String `small'>>>>>
   >
  >
  <TblF
   <Row
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `Total'>>>>>
    <Cell <CellContent <Para <PgfTag `CellBody'> <ParaLine <String `2 parts'>>>>>
   >
  >
 >
>
"""

FRAME = """
<AFrames
 <Frame
  <ID 5>
  <FrameType Below>
  <ShapeRect 0.0 mm 0.0 mm 80.0 mm 40.0 mm>
  <ImportObject
   <ImportObFileDI `<c\\>Graphics<c\\>dot.png'>
   <ShapeRect 0.0 mm 0.0 mm 80.0 mm 40.0 mm>
  >
 >
 <Frame
  <ID 6>
  <FrameType Below>
  <ShapeRect 0.0 mm 0.0 mm 20.0 mm 20.0 mm>
  <ImportObject
   <ImportObEditor `FrameImage'>
   <ImportObFile `2.0 internal inset'>
=EPSI
&%v
&%!PS-Adobe-3.0 EPSF-3.0 <not a statement> `not a string # not a comment
=EndInset
   <ShapeRect 0.0 mm 0.0 mm 20.0 mm 20.0 mm>
  >
 >
 <Frame
  <ID 7>
  <FrameType Inline>
  <ShapeRect 0.0 mm 0.0 mm 6.0 mm 3.0 mm>
  <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>dot.png'> <ShapeRect 0.0 mm 0.0 mm 6.0 mm 3.0 mm>>
 >
 <Frame
  <ID 8>
  <FrameType Below>
  <ShapeRect 0.0 mm 0.0 mm 30.0 mm 15.0 mm>
  <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>dot.png'> <ShapeRect 0.0 mm 0.0 mm 30.0 mm 15.0 mm>>
 >
 <Frame
  <ID 9>
  <FrameType Below>
  <ShapeRect 0.0 mm 0.0 mm 80.0 mm 40.0 mm>
  <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>dot.png'> <ShapeRect 0.0 mm 0.0 mm 80.0 mm 40.0 mm>>
  <ImportObject <ImportObFileDI `<c\\>Graphics<c\\>dot.png'> <ShapeRect 10.0 mm 10.0 mm 16.0 mm 8.0 mm>>
 >
>
"""

NOTES = """
 <Notes
  <FNote <ID 1> <Para <PgfTag `Footnote'> <ParaLine <String `The footnote text.'>>>>
 >
"""


def document():
    parts = [
        '<Units Upt>',
        "<ColorCatalog <Color <ColorTag `Black'> <ColorBlack 100.0>>>",
        "<TblCatalog <TblFormat <TblTag `Format B'> <TblTitlePlacement InFooter>>>",
        "<ConditionCatalog <Condition <CTag `Internal'> <CState CHidden>>"
        " <Condition <CTag `Comment'> <CState CShown>>>",
        '<PgfCatalog\n ' + '\n '.join(CATALOG) + '\n>',
        '<FontCatalog\n ' + '\n '.join(CHAR_FORMATS) + '\n>',
        "<VariableFormats <VariableFormat <VariableName `Version'> <VariableDef `1.2'>>"
        " <VariableFormat <VariableName `Page Count'> <VariableDef `<$lastpagenum\\>'>>>",
        "<XRefFormats <XRefFormat <XRefName `Heading & Page'>"
        " <XRefDef `“<$paratext\\>” on page<$pagenum\\>'>>>",
        '<Document <DPageSize 210.0 mm 297.0 mm> <DLanguage USEnglish>>',
        FRAME, TABLE,
        '<Page <PageType BodyPage> <TextRect <ID 10> <ShapeRect 20.0 mm 20.0 mm 160.0 mm 250.0 mm>>>',
        '<TextFlow <TFTag `A\'>' + NOTES + '\n ' + '\n '.join(body()) + '\n>',
    ]
    return '\n'.join(parts) + '\n'


# FrameRoman codes that differ from Mac Roman, for the characters this sample uses
# (from Adobe's FrameMaker 7.0 character set tables)
NOT_MAC_ROMAN = {'\N{VULGAR FRACTION ONE HALF}': 0xba, '\N{MULTIPLICATION SIGN}': 0xb0,
                 '\N{DEGREE SIGN}': 0xfb, '\N{SUPERSCRIPT THREE}': 0xb8}


def frameroman(text):
    """MIF 7 encoding: non-ASCII characters as \\xNN FrameRoman escapes."""
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        else:
            code = NOT_MAC_ROMAN.get(ch) or ch.encode('mac_roman')[0]
            out.append(f'\\x{code:02x} ')
    return ''.join(out)


def png(w, h):
    """A small PNG (a grey square on white) made with the standard library only."""
    rows = b''
    for y in range(h):
        rows += b'\0' + bytes(0x80 if w // 4 <= x < 3 * w // 4 and h // 4 <= y < 3 * h // 4
                              else 0xff for x in range(w))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def main(folder=HERE):
    doc = document()
    with open(os.path.join(folder, 'sample.mif'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('<MIFFile 2015> # written by make_sample.py\n' + doc)
    with open(os.path.join(folder, 'sample-mif7.mif'), 'w', encoding='ascii', newline='\n') as f:
        f.write('<MIFFile 7.00> # written by make_sample.py\n' + frameroman(doc))
    os.makedirs(os.path.join(folder, 'Graphics'), exist_ok=True)
    with open(os.path.join(folder, 'Graphics', 'dot.png'), 'wb') as f:
        f.write(png(40, 20))


if __name__ == '__main__':
    main(*sys.argv[1:2])
