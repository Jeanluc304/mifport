"""What a paragraph tag or character tag means in Markdown/AsciiDoc terms.

FrameMaker paragraph tags are free names. The role of a tag comes, in this order, from:
1. the user's mapping file (--map), 2. the tag name, 3. its autonumber format (bullets and
list numbers), 4. its font (a monospaced font means code), 5. otherwise 'paragraph'.
"""
import json
import re

from .model import BOLD, ITALIC, CODE, SUPER, SUB, UNDERLINE, STRIKE

PARA_ROLES = {'title', 'heading', 'paragraph', 'bullet', 'numbered', 'code', 'quote', 'skip'}
PARA_ROLES |= {f'heading{n}' for n in range(1, 7)}
CHAR_ROLES = {'plain': None, 'bold': BOLD, 'italic': ITALIC, 'code': CODE, 'superscript': SUPER,
              'subscript': SUB, 'underline': UNDERLINE, 'strike': STRIKE}

TITLE = re.compile(r'(document|doc|dokument)?[ ._-]?(title|titel)', re.I)
HEADING = re.compile(r'heading|überschrift|ueberschrift|headline|kapitel|chapter|section|'
                     r'abschnitt|^h[1-9]$|^(title|titel)[ ._-]?[0-9]', re.I)
# "Hed"/"Head" as the last word part of the name: at the start or after a non-letter (H-Hed,
# 2Hed, head-2, sub-head) or at a CamelCase boundary (SubHed, ChapHead), and followed only by
# the end, white space, a digit, '.', '_' or '-'. Not inside a word (Shed, Ahead, Overhead,
# Hedge) and not followed by another word (HeadNote, HeadRule). Case-sensitive on purpose, so
# that CamelCase boundaries can be seen.
_END = r'(?=$|[\s\d._-])'
HED = re.compile(r'(?:(?<![A-Za-z])|(?<=[a-z]))(?:(?:Sub)?(?:Hed|Head)|Sub(?:hed|head))' + _END
                 + r'|(?<![A-Za-z])(?:SUB)?(?:HED|HEAD)' + _END
                 + r'|(?<![A-Za-z])(?:sub)?(?:hed|head)' + _END)
# fig(?-i:...): case-sensitive look-ahead, so that FigHead is excluded but Fig stays one word.
# after/nach/following: a body paragraph after a heading (BodyAfterHead), but not Afterword,
# Nachwort or Nachtrag.
NOT_HEADING = re.compile(r'table|tabelle|tbl|column|spalte|figure|fig(?-i:(?![a-z]))|abbildung|'
                         r'bild|toc|lof|lot|index|cell|zelle|run-?in|running|runhead|'
                         r'after(?!word)|nach(?!wort|trag)|following|header|footer|kopfzeile|'
                         r'fußzeile|fusszeile|mapping|ix$', re.I)
CODE_TAG = re.compile(r'^(code|codeblock|listing|programlisting|quellcode|sourcecode|pre)\b', re.I)
QUOTE_TAG = re.compile(r'^(quote|blockquote|zitat|extract)\b', re.I)


def tag_role(tag):
    """The role suggested by a paragraph tag's name alone, or None."""
    if TITLE.fullmatch(tag.strip()):
        return 'title'
    if (HEADING.search(tag) or HED.search(tag)) and not NOT_HEADING.search(tag):
        return 'heading'
    if CODE_TAG.search(tag):
        return 'code'
    if QUOTE_TAG.search(tag):
        return 'quote'
    return None


def tag_number(tag):
    """The level number in a tag name ('Heading2' -> 2, 'title.0' -> 0, '2Hed' -> 2), or None.

    A trailing number wins; otherwise a leading one is used."""
    m = re.search(r'([0-9]+)\s*$', tag) or re.match(r'\s*([0-9]+)', tag)
    return int(m.group(1)) if m else None


SUB_TAG = re.compile(r'(?:(?<![A-Za-z])|(?<=[a-z]))(?:Sub|SUB)|(?<![A-Za-z])sub')


def is_sub(tag):
    """Whether a tag name says it is a lower level ('SubHeading', 'H2-SubHed', 'sub-head')."""
    return bool(SUB_TAG.search(tag))


class Mapping:
    """The user's mapping file: paragraph tag -> role, character tag -> styles.

    {
      "paragraphs": {"Überschrift1": "heading1", "Kopf": "skip"},
      "characters": {"Hervorhebung": "italic", "Befehl": "code", "Wichtig": "bold italic"}
    }
    """

    def __init__(self, path=None):
        self.paragraphs, self.characters = {}, {}
        if not path:
            return
        with open(path, encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f'{path}: not valid JSON: {e}') from None
        if not isinstance(data, dict) or not all(
                isinstance(data.get(k, {}), dict) for k in ('paragraphs', 'characters')):
            raise ValueError(f'{path}: expected an object with "paragraphs" and "characters" objects')
        for tag, role in data.get('paragraphs', {}).items():
            if not isinstance(role, str):
                raise ValueError(f'{path}: the role of {tag!r} must be a string')
            role = role.strip().lower()
            if role not in PARA_ROLES:
                raise ValueError(f'{path}: unknown paragraph role {role!r} for {tag!r} '
                                 f'(known: {", ".join(sorted(PARA_ROLES))})')
            self.paragraphs[tag] = role
        for tag, roles in data.get('characters', {}).items():
            if not isinstance(roles, str):
                raise ValueError(f'{path}: the roles of {tag!r} must be a string')
            styles = set()
            for r in roles.replace(',', ' ').lower().split():
                if r not in CHAR_ROLES:
                    raise ValueError(f'{path}: unknown character role {r!r} for {tag!r} '
                                     f'(known: {", ".join(CHAR_ROLES)})')
                if CHAR_ROLES[r]:
                    styles.add(CHAR_ROLES[r])
            self.characters[tag] = frozenset(styles)
