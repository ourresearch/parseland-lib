"""Which language version of an abstract to give (oxjob #2239, phase 2).

The labelling rubric: "If several language versions are shown, give the English one, else the first." Pages show the
versions as separate meta tags (DSpace's two DCTERMS.abstract tags, often with the same xml:lang on both), under
separate headings ("Resumen" / "Abstract"), or run together in one block (DOAJ records, hanspub's description tag:
Chinese then English). Nothing here translates or guesses a language's name: the only question asked of a text is
"English, another language, or can't tell", by script and by a short list of function words, and a text is changed
only when one part is clearly English and the rest clearly is not.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[^\W\d_]{2,}")  # letters only, two or more: "x", "y", "e" are variables in any language
# Function words that are frequent in English prose and rare elsewhere ("in", "a", "on", "as", "an" are other
# languages' words too).
_EN = frozenset("the of and to is are was were with for that this by from which these".split())
# Function words of the Latin-script languages repository and journal pages pair with English: Spanish, Portuguese,
# Catalan, Italian, French, German, Dutch, Indonesian, Polish, Turkish. None is a common English word.
_OTHER = frozenset(
    "el los las del que en se por con para una es lo su como más das dos em um uma não da na ao com são foi "
    "le la les des et est dans pour une du sur au aux qui il di che non sono della "
    "der das und ist mit von für dem ein eine auf nach wurde wurden zu im bei durch "
    "het een van voor zijn op naar aan bij ook niet dat "
    "yang dan dari untuk dengan pada ini dalam adalah "
    "się nie że jest oraz "
    "ve bir bu ile için olarak els amb de".split())


def _foreign_script(ch: str) -> bool:
    """A letter of a script English is never written in. Greek is left out: α, β and μ are science's own."""
    o = ord(ch)
    return (0x0400 <= o <= 0x052F or 0x0590 <= o <= 0x0EFF or 0x1100 <= o <= 0x11FF or 0x3040 <= o <= 0x30FF
            or 0x3400 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF or 0xFB50 <= o <= 0xFDFF
            or 0xFE70 <= o <= 0xFEFF)


def _mark(word: str) -> int:
    """+1 for an English function word, -1 for another language's function word or a word with an accented letter
    (ą, ç, ğ, ñ, ö: Polish and Turkish have few function words but many of these), 0 for any other word."""
    return 1 if word in _EN else -1 if word in _OTHER or not word.isascii() else 0


def _shares(text: str):
    """(share of English function words, share of other languages' marks, word count)."""
    marks = [_mark(w) for w in _WORD.findall(text.lower())]
    if not marks:
        return 0.0, 0.0, 0
    return marks.count(1) / len(marks), marks.count(-1) / len(marks), len(marks)


def foreign_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(map(_foreign_script, letters)) / len(letters) if letters else 0.0


def is_english(text) -> bool:
    """Clearly English prose: Latin script, and at least 12% of its words are English function words (running
    English has ~20%) against few of any other language's."""
    if not text or foreign_share(text) > 0.05:
        return False
    en, other, n = _shares(text)
    return n >= 20 and en >= 0.12 and other <= en / 3


def is_other_language(text) -> bool:
    """Clearly not English: mostly another script, or Latin script with another language's function words and
    almost none of English's."""
    if not text:
        return False
    if foreign_share(text) >= 0.5:
        return True
    en, other, n = _shares(text)
    return n >= 20 and en <= 0.05 and other >= 0.08


# --- several versions run together in one block ----------------------------------------------------------------------
# Ukrainian DSpace repositories label each version in the one field: "UK: ... EN: ... RU: ..."
_CODE_LABEL = re.compile(r"(?:^|(?<=\s))(UK|UKR|UA|RU|RUS|EN|ENG)\s?:\s")
# SSRN: "Portuguese abstract: ... English abstract: ..."
_NAMED_LABEL = re.compile(r"(?:^|(?<=\s))([A-Z][a-z]{3,12}) abstract\s?:\s")
_LEAD_LABEL = re.compile(r"^(?:abstract|summary)\s*[:.]\s*", re.I)
_MIN_PART = 150  # characters: a version shorter than this is a title or a keyword line, not an abstract


def _labelled_english(text: str):
    for label_re, english in ((_CODE_LABEL, ("EN", "ENG")), (_NAMED_LABEL, ("English",))):
        labels = list(label_re.finditer(text))
        if len(labels) < 2 or labels[0].start() != 0:
            continue
        for i, m in enumerate(labels):
            if m.group(1) in english:
                end = labels[i + 1].start() if i + 1 < len(labels) else len(text)
                return text[m.end():end].strip()
    return None


def _best_split(tags):
    """Where a sequence of +1 / -1 / 0 marks changes side: (k, score, plus_first) for the split that best puts the
    +1s on one side and the -1s on the other. Among equal splits the earliest: right after the first side's last
    mark."""
    total = sum(tags)
    best = (0, 0, True)
    run = 0
    for k, t in enumerate(tags, 1):
        run += t
        for score, plus_first in ((2 * run - total, True), (total - 2 * run, False)):
            if score > best[1]:
                best = (k, score, plus_first)
    return best


def _script_split(text: str):
    """[other script][English] or [English][other script]: the English part, else None."""
    if text.isascii():
        return None
    tags = [(-1 if _foreign_script(c) else 1 if c.isascii() and c.isalpha() else 0) for c in text]
    if tags.count(-1) < 60:
        return None
    k, _, english_first = _best_split(tags)
    if english_first:
        # the split sits after the last Latin letter: the sentence's closing punctuation belongs to it
        while k < len(text) and text[k] in ".!?)]\"”’'":
            k += 1
        english, rest = text[:k], text[k:]
    else:
        # the split sits after the last letter of the other script: its closing punctuation stays behind
        while k < len(text) and (text[k].isspace() or text[k] in "。．.!！?？)）」』】:：;；"):
            k += 1
        english, rest = text[k:], text[:k]
    if len(english) < _MIN_PART or foreign_share(rest) < 0.5 or not is_english(english):
        return None
    return english.strip()


_TOKEN = re.compile(r"\S+")


def _word_split(text: str):
    """[another Latin-script language][English] or the reverse, told apart by function words: the English part."""
    tokens = list(_TOKEN.finditer(text))
    if len(tokens) < 60:
        return None
    tags = [_mark("".join(c for c in m.group(0).lower() if c.isalpha())) for m in tokens]
    if tags.count(1) < 8 or tags.count(-1) < 8:
        return None
    k, _, english_first = _best_split(tags)
    if not 0 < k < len(tokens):
        return None
    # between the last marked word of one language and the first of the next lie unmarked words: the versions part
    # at the last sentence end among them, else the unmarked words go with the English (the other languages' words
    # are mostly marked, by their accents if nothing else)
    nxt = next((i for i in range(k, len(tokens)) if tags[i]), len(tokens))
    ends = [i + 1 for i in range(k - 1, nxt) if tokens[i].group(0)[-1] in ".!?]"]
    k = ends[-1] if ends else nxt if english_first else k
    if not 0 < k < len(tokens):
        return None
    cut = tokens[k].start()
    first, second = text[:cut].strip(), text[cut:].strip()
    english, rest = (first, second) if english_first else (second, first)
    if min(len(english), len(rest)) < _MIN_PART or not 0.3 <= len(rest) / len(english) <= 3.5:
        return None
    if not is_english(english) or not is_other_language(rest):
        return None
    return english


def english_part(text):
    """`text` without the other-language versions run together with its English one; `text` itself when it is one
    version, or when the parts cannot be told apart for sure."""
    if not text or not isinstance(text, str) or len(text) < 2 * _MIN_PART:
        return text
    part = _labelled_english(text)
    if part is None or len(part) < _MIN_PART:
        part = _script_split(text) or _word_split(text)
    if not part:
        return text
    part = part.strip()
    if part.count("[") != part.count("]"):  # the translation stood in brackets: "... [Studi ini ...]"
        part = part.strip("[] ")
    part = _LEAD_LABEL.sub("", part).strip()
    return part if len(part) >= _MIN_PART else text
