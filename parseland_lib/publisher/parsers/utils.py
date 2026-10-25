import json
import re
import unicodedata
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
