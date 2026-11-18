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


def is_english(text, min_words=20) -> bool:
    """Clearly English prose: Latin script, and at least 12% of its words are English function words (running
    English has ~20%) against few of any other language's."""
    if not text or foreign_share(text) > 0.05:
        return False
    en, other, n = _shares(text)
    return n >= min_words and en >= 0.12 and other <= en / 3


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
_MIN_LABELLED_PART = 40  # ... unless the page labels it as a version: then a sentence is enough


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


# where one sentence ends and the next begins with a capital, in either script
_SENTENCE_GAP = re.compile(r"[.!?。][\"”»’)]?\s+(?=[\"“«(]?[^\W\d_])")


def _short_script_split(text: str):
    """Two short versions in two scripts, each whole sentences of 60 characters or more ("Обґрунтування ...
    кафе-кондитерської "Coockie". Substantiation of ... the "Coockie" confectionery cafe."): the English one, else
    None. Cut only at a sentence end, so a Latin-script name inside the other version stays in it (#2239 round 8)."""
    if text.isascii():
        return None
    for gap in _SENTENCE_GAP.finditer(text):
        first, second = text[:gap.start() + 1].strip(), text[gap.end():].strip()
        for english, rest in ((first, second), (second, first)):
            if (min(len(english), len(rest)) >= 60 and english[:1].isupper() and foreign_share(rest) >= 0.9
                    and is_english(english, 8) and english.endswith((".", "!", "?", '."', ".”"))):
                return english
    return None


_TOKEN = re.compile(r"\S+")
_OPENING_QUOTES = "„“\"«‹"


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
    # English that opens inside the other language's sentence, in quotation marks, is a quotation, not a version
    # ("... als Fuzzy-Mengen betrachten kann: „… a pictorial object is a fuzzy set ...": a German Zusammenfassung
    # that ends on a quoted passage) (round 3)
    if not english_first and not ends and any(tokens[i].group(0)[0] in _OPENING_QUOTES for i in range(k, nxt)):
        return None
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


_GLUED_SENTENCE_END = re.compile(r"[.!?](?=[^\W\d_])")  # "... of the Constitution.RiassuntoIn questo lavoro"


def _middle_english(text: str):
    """[another language][English][another language ...]: three or more versions run together with the English
    one inside (a DOAJ record: Turkish, English, French, Arabic; an old journal's Zusammenfassung, Abstract and
    Résumé). The English version is found by the run of words where English function words most outnumber the
    other languages' marks; it reaches from the sentence after the last such mark before that run to the last
    sentence end before the next one. It counts only when it reads as English, the text before it and the text
    after it each clearly do not, and it is not far shorter than they are (an English quotation inside a German
    text is not a version of it) (round 3)."""
    tokens = list(_TOKEN.finditer(text))
    if len(tokens) < 90:
        return None
    tags = [_mark("".join(c for c in m.group(0).lower() if c.isalpha())) for m in tokens]
    if tags.count(1) < 8 or tags.count(-1) < 8:
        return None
    best, run, first = (0, 0, 0), 0, 0  # (score, first token, one past the last): the maximum-sum run
    for i, t in enumerate(tags):
        if run <= 0:
            run, first = 0, i
        run += t
        if run > best[0]:
            best = (run, first, i + 1)
    score, a, b = best
    p = max((i for i in range(a) if tags[i] < 0), default=None)
    q = next((i for i in range(b, len(tokens)) if tags[i] < 0), None)
    if score < 8 or p is None or q is None:
        return None  # no such run, or English at one end: _word_split's and _script_split's case
    start = tokens[p + 1].start()
    for i in range(p, a):  # the first sentence end from that mark on
        word = tokens[i].group(0)
        if word[-1] in ".!?":
            start = tokens[i + 1].start()
            break
        if glued := _GLUED_SENTENCE_END.search(word):
            start = tokens[i].start() + glued.end()
            break
    end = tokens[b - 1].end()
    for i in range(q - 1, b - 2, -1):  # the last sentence end before the next mark
        word = tokens[i].group(0)
        if word[-1] in ".!?":
            end = tokens[i].end()
            break
        if glued := _GLUED_SENTENCE_END.search(word):
            end = tokens[i].start() + glued.end()
            break
    english, before, after = text[start:end].strip(), text[:start], text[end:]
    if min(len(english), len(before), len(after)) < _MIN_PART or len(english) < 0.3 * max(len(before), len(after)):
        return None
    if english[0] in _OPENING_QUOTES:
        return None  # a quoted passage
    if not is_english(english) or not is_other_language(before) or not is_other_language(after):
        return None
    return english


def english_part(text):
    """`text` without the other-language versions run together with its English one; `text` itself when it is one
    version, or when the parts cannot be told apart for sure."""
    if not text or not isinstance(text, str):
        return text
    if len(text) < 2 * _MIN_PART:
        # Too short for the splits below to tell languages apart, but not for the page's own labels: one-sentence
        # versions under "UK: ... EN: ... RU: ..." (round 6). The labelled part must be in Latin script.
        part = _labelled_english(text) if text[:1].isupper() else None
        if part and len(part) >= _MIN_LABELLED_PART and foreign_share(part) <= 0.05:
            return part
        return _short_script_split(text) or text
    part = _labelled_english(text)
    # a labelled version is one whatever its length: "UK: ... EN: The methodical materials ... RU: ..." (round 8)
    if part is not None and _MIN_LABELLED_PART <= len(part) < _MIN_PART and foreign_share(part) <= 0.05:
        return part
    if part is None or len(part) < _MIN_PART:
        part = _script_split(text) or _word_split(text) or _middle_english(text)
    if not part:
        return text
    part = part.strip()
    if part.count("[") != part.count("]"):  # the translation stood in brackets: "... [Studi ini ...]"
        part = part.strip("[] ")
    part = _LEAD_LABEL.sub("", part).strip()
    return part if len(part) >= _MIN_PART else text
