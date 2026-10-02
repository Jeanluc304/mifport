"""MIF reader: turns a MIF file into a tree of Node objects.

A MIF file is a tree of statements, `<Name value ... <Child ...> >`. Values are bare
tokens (`12.0 pt`, `Yes`) or strings in `backquote ... quote' delimiters. Before the
statements are read, copied-in graphic data is removed and the macro statements
`define` and `include` are expanded.
"""
import os
import re

# One token per match: "<Name" opens a statement (white space after "<" is allowed),
# ">" closes one, `...' is a string (backslash escapes allowed inside), anything else
# non-blank is a bare value. Comments (# to end of line) and white space are skipped.
TOKEN = re.compile(r"<\s*(\w+)|>|`((?:[^'\\]|\\.)*)'|([^\s<>`#]+)|#[^\n]*|\s+")


class Node:
    """One MIF statement: its name, its leaf values and its child statements in order.

    `items` keeps leaf values and child nodes interleaved in file order; a leaf value is
    a str subclass, Str for `strings' (still escaped) and Tok for bare tokens.
    """
    __slots__ = ('name', 'items')

    def __init__(self, name):
        self.name = name
        self.items = []

    def __repr__(self):
        return f'<Node {self.name} {self.value!r}>'

    @property
    def children(self):
        """Child statements in file order."""
        return [i for i in self.items if isinstance(i, Node)]

    @property
    def value(self):
        """The raw leaf value: all tokens joined by spaces (strings still escaped)."""
        return ' '.join(i for i in self.items if not isinstance(i, Node))

    @property
    def text(self):
        """The leaf value as text, with string escapes undone."""
        return unescape(self.value)

    def all(self, name):
        """All direct children called `name`."""
        return [i for i in self.items if isinstance(i, Node) and i.name == name]

    def get(self, name):
        """The first direct child called `name`, or None."""
        for i in self.items:
            if isinstance(i, Node) and i.name == name:
                return i
        return None

    def val(self, name, default=None):
        """Raw value of the first child called `name`, or `default`."""
        c = self.get(name)
        return c.value if c is not None else default

    def str(self, name, default=None):
        """Unescaped string value of the first child called `name`, or `default`."""
        c = self.get(name)
        return c.text if c is not None else default

    def find(self, name):
        """All statements called `name` anywhere below this node, in file order."""
        out = []
        stack = [iter(self.items)]
        while stack:
            for i in stack[-1]:
                if isinstance(i, Node):
                    if i.name == name:
                        out.append(i)
                    stack.append(iter(i.items))
                    break
            else:
                stack.pop()
        return out


class Str(str):
    """A `string' value (still escaped)."""


class Tok(str):
    """A bare token value."""


# Graphics copied into a document are stored as facets: lines starting with "=" (a facet
# name, "=EndInset" at the end) and "&" (data, which may contain any character, < > ` #
# included). They are not statements and must not reach the tokeniser.
FACET_NAME = re.compile(r'^[ \t]*=(?!EndInset\b)(\S+)[^\n]*$', re.M)
FACET_DATA = re.compile(r'^[ \t]*(?:&|=EndInset\b)[^\n]*(?:\n|$)', re.M)


def strip_facets(text):
    """Replace facet data by one <Facet `name'> statement per facet."""
    if '\n=' not in text and '\n&' not in text and not re.search(r'\n[ \t]+[=&]', text):
        return text
    text = FACET_DATA.sub('', text)
    return FACET_NAME.sub(lambda m: "<Facet `" + m.group(1).replace("'", '') + "'>", text)


# Macro statements: `define (name, replacement)` and `include (pathname)`, written without
# angle brackets anywhere in a file. A defined macro is used as <name>. Strings and
# comments are matched first so that the words inside them are left alone.
MACRO = re.compile(r"`(?:[^'\\]|\\.)*'|#[^\n]*|\b(define|include)\s*\(|<\s*(\w+)\s*>")
MAX_INCLUDE_DEPTH = 10


def read_text(path, warn=None):
    """The text of a MIF file: UTF-8 (MIF 8 and newer), else 7-bit with \\xNN escapes."""
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError as e:
        version = re.match(rb'\s*(?:\xef\xbb\xbf)?<MIFFile\s+([0-9]+)', raw)
        if warn and version and int(version.group(1)) >= 8:
            warn(f'{path} is MIF {version.group(1).decode()} but not valid UTF-8 '
                 f'(byte {e.start}); characters may be wrong')
        return raw.decode('latin-1')


def macro_args(text, pos):
    """Read the argument list of a macro statement from `pos` (just after the opening
    parenthesis) up to the matching closing one. Returns (arguments, end position); the
    replacement of a define may contain statements, strings and parentheses."""
    depth, args, start, i = 0, [], pos, pos
    while i < len(text):
        ch = text[i]
        if ch == '`':
            m = re.compile(r"`(?:[^'\\]|\\.)*'").match(text, i)
            i = m.end() if m else i + 1
            continue
        if ch in '<(':
            depth += 1
        elif ch in '>)' and depth:
            depth -= 1
        elif ch == ')':
            args.append(text[start:i].strip())
            return args, i + 1
        elif ch == ',' and depth == 0 and not args:
            args.append(text[start:i].strip())
            start = i + 1
        i += 1
    raise ValueError('a define or include statement is not closed with ")"')


def expand_macros(text, base_dir='.', macros=None, warn=None, depth=0):
    """Expand define and include statements (see MACRO)."""
    if 'define' not in text and 'include' not in text and not macros:
        return text
    macros = {} if macros is None else macros
    out, pos = [], 0
    for m in MACRO.finditer(text):
        if m.start() < pos:  # inside the arguments of a macro statement already read
            continue
        out.append(text[pos:m.start()])
        pos = m.end()
        if m.group(1):
            args, pos = macro_args(text, m.end())
            if m.group(1) == 'define':
                if len(args) == 2:
                    macros[args[0]] = expand_macros(args[1], base_dir, dict(macros), warn, depth)
            else:
                out.append(include(args[0], base_dir, macros, warn, depth))
        elif m.group(2) in macros:
            out.append(macros[m.group(2)])
        else:
            out.append(m.group(0))
    out.append(text[pos:])
    return ''.join(out)


def include(name, base_dir, macros, warn, depth):
    """The expanded text of an included file (relative paths are relative to the file
    that includes it)."""
    path = name if os.path.isabs(name) or re.match(r'^[A-Za-z]:', name) else os.path.join(base_dir, name)
    if depth >= MAX_INCLUDE_DEPTH:
        raise ValueError(f'include statements nested more than {MAX_INCLUDE_DEPTH} deep: {name}')
    if not os.path.isfile(path):
        if warn:
            warn(f'included file not found: {name}')
        return ''
    text = strip_facets(read_text(path))
    return expand_macros(text, os.path.dirname(os.path.abspath(path)), macros, warn, depth + 1)


def parse(text, base_dir='.', warn=None):
    """Parse MIF text; returns a root Node named 'MIF' holding the top-level statements.

    `base_dir` is where files named in include statements are looked for. Comment
    statements are dropped: their content is not part of the document.
    """
    root = Node('MIF')
    stack = [root]
    text = expand_macros(strip_facets(text), base_dir, warn=warn)
    for m in TOKEN.finditer(text):
        name, string, token = m.group(1), m.group(2), m.group(3)
        if name:
            node = Node(name)
            stack[-1].items.append(node)
            stack.append(node)
        elif string is not None:
            stack[-1].items.append(Str(string))
        elif token:
            stack[-1].items.append(Tok(token))
        elif m.group(0) == '>' and len(stack) > 1:  # a stray '>' must not pop the root
            node = stack.pop()
            if node.name == 'Comment':
                stack[-1].items.pop()
    return root


def load(path, warn=None):
    """Read and parse a MIF file. Returns (root node, MIF version string)."""
    text = read_text(path, warn)
    if text.lstrip('\N{BYTE ORDER MARK}').startswith('<Book'):
        raise ValueError(f'{path} is a MIF book file, which only lists its chapter files; '
                         'convert each chapter file instead')
    if not text.lstrip('\N{BYTE ORDER MARK}').startswith('<MIFFile'):
        raise ValueError(f'{path} is not a MIF file (it does not start with <MIFFile)')
    root = parse(text, os.path.dirname(os.path.abspath(path)), warn)
    if warn and root.get('MIFEncoding') is not None:
        warn(f'MIFEncoding {root.val("MIFEncoding")}: Asian MIF encodings are not supported; '
             'characters may be wrong')
    return root, root.val('MIFFile', '')


# FrameRoman, the character set of MIF 7.0 and older, is Mac Roman except for these codes.
# Source: Adobe's "FrameMaker Character Sets" for FrameMaker 7.0 (Windows) and 8 (Windows
# and UNIX), whose tables pair each code with its Windows (ANSI) character: Windows-only
# Latin-1 characters reuse Mac Roman's slots for math symbols. Not taken over:
# the Windows tables swap 0x92/0x93 (i grave/acute) against the UNIX table and against
# the order of all other accented letters, so that is a typo; Mac Roman applies.
FRAMEROMAN = {
    0x04: '\N{SOFT HYPHEN}',          # discretionary hyphen
    0x05: '',                         # suppress hyphenation (no visible output)
    0x08: '\t',
    0x09: '\N{LINE SEPARATOR}',       # forced return (the builder makes a line break)
    0x0a: '\N{LINE SEPARATOR}',       # end of paragraph (not expected inside a string)
    0x10: '\N{FIGURE SPACE}',         # numeric space
    0x11: '\N{NO-BREAK SPACE}',       # hard space
    0x12: '\N{THIN SPACE}',
    0x13: '\N{EN SPACE}',
    0x14: '\N{EM SPACE}',
    0x15: '\N{NON-BREAKING HYPHEN}',  # hard hyphen
    0xad: '\N{BROKEN BAR}',           # Mac Roman: not equal to
    0xb0: '\N{MULTIPLICATION SIGN}',  # infinity
    0xb2: '\N{LATIN SMALL LETTER ETH}',  # less-than or equal to
    0xb3: '\N{LATIN CAPITAL LETTER S WITH CARON}',  # greater-than or equal to
    0xb6: '\N{SUPERSCRIPT ONE}',      # partial differential
    0xb7: '\N{SUPERSCRIPT TWO}',      # n-ary summation
    0xb8: '\N{SUPERSCRIPT THREE}',    # n-ary product
    0xb9: '\N{VULGAR FRACTION ONE QUARTER}',  # pi
    0xba: '\N{VULGAR FRACTION ONE HALF}',     # integral
    0xbd: '\N{VULGAR FRACTION THREE QUARTERS}',  # omega
    0xc3: '\N{LATIN CAPITAL LETTER ETH}',  # square root
    0xc5: '\N{LATIN CAPITAL LETTER Y WITH ACUTE}',  # almost equal to
    0xc6: '\N{LATIN SMALL LETTER Y WITH ACUTE}',    # increment
    0xca: '\N{LATIN SMALL LETTER THORN}',           # no-break space
    0xd7: '\N{LATIN CAPITAL LETTER THORN}',         # lozenge
    0xdb: '\N{CURRENCY SIGN}',        # Python's mac_roman: euro sign (Apple's later change)
    0xf0: '\N{LATIN SMALL LETTER S WITH CARON}',    # Apple logo
    0xfb: '\N{DEGREE SIGN}',          # ring above
}


def frameroman(code):
    """The character for one FrameRoman byte."""
    if code in FRAMEROMAN:
        return FRAMEROMAN[code]
    return bytes([code]).decode('mac_roman')


ESCAPES = {'q': "'", 'Q': '`', '>': '>', 't': '\t', '\\': '\\'}
ESCAPE = re.compile(r'\\x([0-9a-fA-F]{2}) ?|\\u([0-9a-fA-F]{4})|\\(.)', re.S)


def unescape(s):
    """Undo MIF string escapes. `\\xNN ` is a FrameRoman byte (followed by one space),
    `\\uNNNN` a Unicode character."""
    if '\\' not in s:
        return s

    def sub(m):
        if m.group(1):
            return frameroman(int(m.group(1), 16))
        if m.group(2):
            return chr(int(m.group(2), 16))
        return ESCAPES.get(m.group(3), m.group(3))
    return ESCAPE.sub(sub, s)
