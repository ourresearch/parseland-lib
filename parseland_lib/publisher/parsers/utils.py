import json
import re
import unicodedata

import unidecode
from nameparser import HumanName

EMAIL_RE = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
                      flags=re.IGNORECASE)


def strip_prefix(prefix, string, flags=0):
    return re.sub(f'^{prefix}', '', string, flags=flags)


def strip_suffix(suffix, string, flags=0):
    return re.sub(f'{suffix}$', '', string, flags=flags)


def strip_seq(seq, string, flags=0):
    return strip_prefix(seq, strip_suffix(seq, string, flags=flags),
                        flags=flags)


def _strip_seqs(seqs, string, flags=0):
    for seq in seqs:
        string = strip_seq(seq, string, flags)
    return string


def strip_seqs(seqs, string, flags=0, recursive=False):
    if not recursive:
        return _strip_seqs(seqs, string, flags)
    new_string = string
    prev_string = string
    while True:
        new_string = _strip_seqs(seqs, new_string, flags)
        if new_string == prev_string:
            break
        prev_string = new_string
    return new_string


def cleanup_raw_name(raw_name):
    return strip_prefix('and', raw_name.strip(' .,')).strip(' .,')


def is_h_tag(tag):
    return re.match('^h[1-6]$', tag.name)


def remove_parents(tags):
    final_tags = []
    for tag1 in tags:
        is_parent = False
        for tag2 in tags:
            if tag1 == tag2:
                continue
            tag1_children = list(tag1.children)
            if tag2 in tag1_children:
                is_parent = True
        if not is_parent:
            final_tags.append(tag1)
    return final_tags


def split_name(name):
    return [part for part in re.split('[ ,]', name.strip()) if
            len(part) > 1]


def name_in_text(name, text):
    name_split = split_name(name)
    if len(name_split) == 3:
        # only care about middle initial
        name_split[1] = name_split[1][0]
    return all([part in text for part in name_split])


def email_matches_name(email, name):
    _email = strip_prefix('mailto:', email)

    normalized_name = unicodedata.normalize('NFD', name.lower()).encode('ascii',
                                                                        'ignore').decode()
    split = split_name(normalized_name)
    return any([part in _email.split('@')[0] for part in split])


def names_match(name1: HumanName, name2: HumanName):
    if not isinstance(name1, HumanName):
        name1 = HumanName(name1)
    if not isinstance(name2, HumanName):
        name2 = HumanName(name2)
    return name1.last.lower() == name2.last.lower() and name1.first.lower() == name2.first.lower()


class NuxtPayload:
    """A Nuxt 3 page's ``<script id="__NUXT_DATA__">`` payload (devalue's flat format), read lazily.

    The payload is one JSON array; containers hold indices into it, and wrappers such as ["ShallowReactive", i]
    or ["Ref", i] point at their value. MDPI's article pages keep their full author and affiliation lists there
    (the HTML shows only the first four affiliations; oxjob #1805). ``node(i)`` resolves one level: a dict or list
    of indices, or a plain value.
    """
    WRAPPERS = {"ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}

    def __init__(self, arr):
        self.arr = arr

    @classmethod
    def from_soup(cls, soup):
        tag = soup.find("script", id="__NUXT_DATA__")
        if tag is None or not tag.string:
            return None
        try:
            arr = json.loads(tag.string)
        except ValueError:
            return None
        return cls(arr) if isinstance(arr, list) and arr else None

    def node(self, i):
        for _ in range(8):  # wrapper chains are short; a loop guard, not a real limit
            if not isinstance(i, int) or not 0 <= i < len(self.arr):
                return None  # devalue's negative sentinels: undefined, NaN, Infinity, -0
            v = self.arr[i]
            if isinstance(v, list) and len(v) == 2 and v[0] in self.WRAPPERS:
                i = v[1]
                continue
            return v
        return None

    def dicts(self, i):
        """The dicts in the list at index i (e.g. an article's authors), one level resolved."""
        return [d for d in map(self.node, self.node(i) or []) if isinstance(d, dict)]


def _name_tokens(name):
    """Accent-free lower-case name tokens; 'Family, Given' reads as 'Given Family'; any dash splits; curly
    apostrophes read straight. Kept close to gate/fields.py name_tokens (minus its title list), which scores us."""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c)).casefold()
    n = re.sub(r"[‘’ʼ`´]", "'", n)
    if "," in n:
        family, _, given = n.partition(",")
        n = f"{given} {family}"
    return sorted(t for t in re.split(r"[^\w']+", n.replace("-", " ")) if t)


def same_person(name1, name2):
    """True when two renderings of one byline name agree: 'Qu, Junle' / 'Junle Qu', 'Yan-Yan Song' /
    'Yan Yan Song', 'Jürgen' / 'Jurgen'. Exact first and last name (names_match) or the same token set."""
    if not name1 or not name2:
        return False
    if names_match(name1, name2):
        return True
    t1 = _name_tokens(name1)
    return bool(t1) and t1 == _name_tokens(name2)


def fill_affiliations_by_name(authors, pairs):
    """Give each (name, affiliations) pair's affiliations to the one parsed author with that name (same_person), if
    that author has none yet. For pages whose names and affiliations sit in different places (oxjob #1809)."""
    for name, affiliations in pairs:
        if not name or not affiliations:
            continue
        matches = [a for a in authors if same_person(a.name, name)]
        if len(matches) == 1 and not matches[0].affiliations:
            matches[0].affiliations.extend(affiliations)


# Finding an author's name inside free text, e.g. a correspondence note (oxjob #2149, first used for SciELO).
NAME_SUFFIXES = {"filho", "junior", "jr", "neto", "sobrinho", "segundo"}
NAME_PARTICLES = {"de", "da", "do", "dos", "das", "del", "della", "di", "du", "e", "y", "van", "von", "der", "den", "la", "le"}


def _fold_name(text):
    """Lower-case ASCII letters and single spaces only (accents and punctuation dropped), for name matching."""
    return re.sub(r"[^a-z]+", " ", unidecode.unidecode(text or "").lower()).strip()


def _initial_letters(words):
    """Initials a run of words spells: a word of up to 3 letters may itself be initials ("nrt", "mr"), longer words
    give their first letter."""
    return "".join(t if len(t) <= 3 else t[0] for t in words)


def _initials_span(tokens, givens, before):
    """How many of the words next to a surname (read back from it when before) spell the given names' initials, or 0.
    Single letters are always initials here, even 'e' and 'y'."""
    initials = _initial_letters(givens)
    words = [t for t in tokens if len(t) == 1 or t not in NAME_PARTICLES]
    need = min(2, len(initials))
    for cut in range(len(words)):
        part = words[cut:] if before else words[:len(words) - cut]
        letters = _initial_letters(part)
        if len(letters) >= need and initials.startswith(letters):
            return len(part)
    return 0


def name_position(name, text):
    """Where the author's name starts in text (folded), or None: the surname plus a given name, or the surname next to
    the given names' initials ('N.R.T. Damasceno', 'MCC NASCIMENTO'). Names come 'Last, First' or 'First Last'."""
    if "," in name:
        last, given = name.split(",", 1)
    else:
        tokens = name.split()
        while len(tokens) > 1 and _fold_name(tokens[-1]) in NAME_SUFFIXES:
            tokens = tokens[:-1]
        last, given = (tokens[-1], " ".join(tokens[:-1])) if len(tokens) > 1 else (name, "")
    surnames = [t for t in _fold_name(last).split() if len(t) >= 3 and t not in NAME_PARTICLES]
    givens = [t for t in _fold_name(given).split() if t not in NAME_PARTICLES]
    folded = _fold_name(text)
    positions = []
    for surname in surnames:
        for m in re.finditer(r"\b" + re.escape(surname) + r"\b", folded):
            window = folded[max(0, m.start() - 45):m.end() + 45]
            ok = any(len(g) >= 3 and re.search(r"\b" + re.escape(g) + r"\b", window) for g in givens)
            pos = m.start()
            if ok:  # start at the given name when it comes first
                first = folded.find(givens[0])
                if 0 <= first < pos:
                    pos = first
            elif givens:  # given names as initials, either side: "N R T damasceno", "levy carvalho gomes", "damasceno N"
                before = folded[:m.start()].split()[-6:]
                n = _initials_span(before, givens, before=True)
                if n:
                    ok, pos = True, max(0, m.start() - len(" ".join(before[-n:])) - 1)
                else:
                    ok = bool(_initials_span(folded[m.end():].split()[:4], givens, before=False))
            if ok:
                positions.append(pos)
    return min(positions, default=None)


def _letters_key(text):
    return re.sub(r"[\W_]+", "", text or "").casefold()


def same_opening_text(text, opening, prefix=80):
    """True when text starts like opening, or opening starts like text (letters and digits only, first `prefix`).

    For a page that marks the text it shows as the work's opening (oxjob #2162): its meta tags and JSON-LD repeat
    the same opening, with other spacing, quotes or a cut end.
    """
    a, b = _letters_key(text), _letters_key(opening)
    if len(a) < 20 or len(b) < 20:
        return False
    return a[:prefix] in b or b[:prefix] in a


# An opening that says what the work itself does reads as its abstract (gold v1.3 keeps "This chapter discusses the
# Chain Rule...", 10.1201/9781003449652-5), so a page's opening marker never removes it (oxjob #2162). Any other opening
# prose (background, narrative, a topic introduction, a quotation) is body text (gold convention, #1791 EXPLORE § 6).
# Read in the first ~600 characters: the self-description often comes after a sentence or two of setting.
# shortcut: English phrasing only; other languages' openings are removed when marked.
_WORK = (r"(?:chapter|paper|article|essay|study|contribution|note|review|preface|introduction|book|volume|report|"
         r"section|overview|survey|commentary|editorial|lecture)")
_DOES = (r"(?:examines|explores|addresses|argues|discusses|describes|presents|considers|outlines|introduces|reviews|"
         r"focuses|investigates|analy[sz]es|provides|traces|offers|looks|is\s+concerned|deals|sets\s+out|seeks|aims|"
         r"identifies|reports|proposes|shows|summari[sz]es|surveys|assesses|evaluates|develops|demonstrates|highlights|"
         r"maps|charts|draws|uses|takes|begins|turns|is\s+about|will|asks|compares|documents|situates|reflects|builds|"
         r"shifts|contends|includes|covers|gives|collects|brings)")
_STATES_WHAT_THE_WORK_DOES = re.compile(
    r"^\W*(?:abstract|summary)\b"
    r"|\bthis\s+" + _WORK + r"\s+(?:\S+\s+){0,6}?" + _DOES + r"\b"
    r"|\b(?:the\s+present|the|our)\s+" + _WORK + r"\s+(?:\w+\s+){0,2}?" + _DOES + r"\b"
    r"|\bthis\s+is\s+an?\s+(?:\S+\s+){0,3}?" + _WORK + r"\b"
    r"|\b(?:purpose|aim|goal|objective|focus|subject|concern)\s+of\s+(?:this|the\s+present)\s+" + _WORK +
    r"|\bin\s+(?:this|the\s+present|the\s+following)\s+" + _WORK + r"\b"
    r"|\b(?:the\s+aim\s+here|in\s+what\s+follows|in\s+the\s+following\s+pages)\b"
    r"|\bchapter\s+\d+\s+" + _DOES + r"\b"
    r"|\b(?:here|below|herein)\s+(?:we|i)\s+\w+"
    r"|\b(?:we|i)\s+(?:present|report|describe|propose|examine|investigate|study|show|review|discuss|consider|analy[sz]e|"
    r"argue|explore|explored|introduce|outline|suggest|focus|examined|investigated|studied|develop|developed|"
    r"compare|assess|evaluate|test|use|draw|trace|offer|collect)\b",
    re.IGNORECASE,
)


def states_what_the_work_does(text):
    # stored texts can carry literal "\n" escapes (T&F product data), which would hide a word boundary
    head = re.sub(r"\\[nrt]", " ", (text or "")[:600])
    return bool(_STATES_WHAT_THE_WORK_DOES.search(head))
