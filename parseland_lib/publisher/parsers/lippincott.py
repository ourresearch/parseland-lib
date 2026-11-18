import re
from typing import List

from nameparser import HumanName

from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.elements import Author, Affiliation, AuthorAffiliations
from parseland_lib.publisher.parsers.utils import name_in_text, split_name, strip_prefix, same_person

import unicodedata

from bs4 import Comment, NavigableString

# The label of an LWW author-info note that names the corresponding author: "Reprints:", "Reprint requests to:",
# "Address for reprints:", "Address correspondence and reprint requests to", "Address requests for reprints to:",
# "Corresponding Author:", "* Corresponding author:", "Correspondence:", "Correspondance to", "Correspondence to:",
# "Address for correspondence:", "Email for corresponding author:" (oxjob #2128). It must open the note or follow a
# sentence end, so prose that mentions correspondence never counts.
_LWW_CORR_LABEL = re.compile(
    r"(?:^|(?<=[.;]\s))\*?\s*(?:"
    r"(?:e-?mail\s+(?:address\s+)?for\s+)?correspond(?:ing|ence)\s+authors?"
    r"|(?:send\s+|address\s+(?:all\s+)?)?(?:correspond[ae]nce|reprint\s+requests?|requests?\s+for\s+reprints)"
    r"(?:\s+and\s+(?:reprint\s+)?requests?(?:\s+for\s+reprints)?|\s+and\s+reprints?(?:\s+requests?)?"
    r"|\s+and\s+correspond[ae]nce)?(?:\s+address)?"
    r"|address\s+for\s+(?:correspond[ae]nce|reprints?)(?:\s+and\s+reprints?)?"
    r"|reprints?(?:\s+requests?)?"
    # "to" as a word: "Reprints: Toshitaka Yoshii" lost its "To" (oxjob #2288)
    r")\s*(?:to\b)?\s*[:\-\u2013]?\s*(?:to\b\s*:?\s*)?",
    re.I)
_TITLES = re.compile(r"^(?:(?:Dr|Drs|Prof|Professor|Mr|Mrs|Ms|Miss|Sir)\.?\s+)+", re.I)
# A star in the author-info notes that opens a corresponding note ("*Corresponding author", "* Authors to whom
# correspondence should be addressed"), and one that keys anything else ("From the *Department of Surgery") (#2288).
_STAR = r"(?<![*∗])[*∗]+(?![*∗])"
_STAR_ON_CORR_NOTE = r"\s*(?:[^\W\d_]+\s+){0,4}?(?:correspond|reprint)"
_STAR_CORR = re.compile(_STAR + r"(?=" + _STAR_ON_CORR_NOTE + ")", re.I)
_STAR_KEY = re.compile(_STAR + r"(?!" + _STAR_ON_CORR_NOTE + ")", re.I)


def _fold(text):
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _byline_entries(authors_section):
    """(name, marks) per author in an LWW byline paragraph ("Lee, Nathan J. MD<sup>1,a</sup>; ..."), byline order."""
    para = authors_section.find("p")
    if para is None:
        return []
    entries, buf, marks = [], "", []
    for node in para.descendants:
        if getattr(node, "name", None) == "sup":
            marks.extend(m for m in re.split(r"[\s,]+", node.get_text(" ", strip=True)) if m)
            continue
        if not isinstance(node, NavigableString) or isinstance(node, Comment) or node.find_parent("sup") is not None:
            continue
        for i, part in enumerate(node.split(";")):
            if i > 0:
                entries.append((buf, marks))
                buf, marks = "", []
            buf += part
    entries.append((buf, marks))
    return [(re.sub(r"\s+", " ", n).strip(" ,;*\u2217"), m) for n, m in entries if n.strip(" ,;*\u2217")]


def _statement_name(rest):
    """The person a corresponding note names: the words before the first comma, "(", " is ", ";" or " at "."""
    chunk = re.split(r",|\(|;|\s+is\s+|\s+at\s+|\s+-\s+", _TITLES.sub("", rest.strip()), maxsplit=1)[0]
    chunk = chunk.strip(" .:")
    if not chunk or "@" in chunk or len(chunk.split()) > 5 or not re.match(r"[^\W\d_]", chunk):
        return None
    return chunk


def _match_byline(name, entries):
    """The one byline name that is this person: same_person, else same surname and (no given name, or the same
    first initial). None when nobody or more than one author matches."""
    hits = [n for n, _ in entries if same_person(n, name)]
    if len(hits) == 1:
        return hits[0]
    words = _fold(name).replace("-", " ").split()
    if not words:
        return None
    surname, initial = words[-1].strip("."), (words[0][0] if len(words) > 1 else None)
    hits = []
    for n, _ in entries:
        family, _, given = _fold(n).partition(",")
        if not given:  # "Given Family" byline form
            parts = family.split()
            family, given = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
        if family.replace("-", " ").split()[-1:] != [surname]:
            continue
        if initial and given.strip() and given.strip()[0] != initial:
            continue
        hits.append(n)
    return hits[0] if len(hits) == 1 else None


def lww_corresponding_names(soup):
    """Byline names an LWW article page (journals.lww.com, ``#ejp-article-authors``) names as corresponding ([] if none).

    The author-info block under the byline (``div.ejp-article-authors-info-holder``) carries one note per paragraph;
    the corresponding author's reads "Reprints: Nathan J. Lee, MD, ...", "Reprint requests: Dr. Steinmann, ...",
    "Corresponding Author: Arseniy P. Yashkin, PhD, ..." or, with only an e-mail, "<sup>CA</sup>Corresponding Author:
    [e-mail]" whose mark ("CA", "a", "*") sits on that author in the byline. Lippincott.get_authors looks only for a
    paragraph containing "correspondence", so these pages showed no corresponding author (oxjob #2128: ~11% of LWW
    pages whose work has none). A reprints note names the corresponding author, as the gold reads it. Names come back
    as the byline writes them, so the parsed author is found whichever parser won the page. Call it on the page's
    soup before any parser runs: Lippincott.get_authors removes the byline's <sup> marks.
    """
    authors_section = soup.find(id="ejp-article-authors")
    holder = soup.select_one("div.ejp-article-authors-info-holder")
    if authors_section is None or holder is None:
        return []
    entries = _byline_entries(authors_section)
    if not entries:
        return []
    paras = holder.find_all("p")
    for i, para in enumerate(paras):
        text = re.sub(r"\s+", " ", para.get_text(" ", strip=True))
        first_sup = para.find("sup")
        mark = first_sup.get_text(strip=True) if first_sup is not None and text.startswith(
            first_sup.get_text(" ", strip=True)) else None
        body = text[len(first_sup.get_text(" ", strip=True)):].strip() if mark else text
        found = _LWW_CORR_LABEL.search(body)
        if not found:
            continue
        # "*Corresponding author. Address: Komal F. Satti, ..." (Pediatric Quality & Safety) (oxjob #2288)
        rest = re.sub(r"^[.\s]*address\s*:\s*", "", body[found.end():].strip(), flags=re.I)
        if not rest and i + 1 < len(paras):  # "Address reprint requests to:" with the name in the next paragraph
            rest = re.sub(r"\s+", " ", paras[i + 1].get_text(" ", strip=True))
        name = _statement_name(rest)
        if name and (hit := _match_byline(name, entries)):
            return [hit]
        if mark and not mark.isdigit():
            marked = [n for n, marks in entries if mark in marks]
            if len(marked) == 1:
                return marked
    # PRS Global Open prints the corresponding author's address with no label ("Disclosure statements are at the end
    # of this article, following the correspondence information."): "Pedro C. Cavadas, MD, PhD, ..., E-mail: ...".
    # One such paragraph only: an e-mail for every author marks no one (oxjob #2288).
    blocks = [hit for para in paras if re.search(r"e-?mail", text := para.get_text(" ", strip=True), re.I)
              and (name := _statement_name(text)) and (hit := _match_byline(name, entries))]
    return blocks if len(blocks) == 1 else []


# A statement that is not an affiliation: disclosures and conflict-of-interest lines (#2239).
_DISCLOSURE = re.compile(r"\bdisclos(?:ed|es|ure)\b|\bconflicts? of interests?\b|\bcompeting interests?\b", re.I)
_EMAIL_TEXT = re.compile(r"\be-?mail\b|@|\[email", re.I)


def _mark_list(text):
    """The marks of a byline <sup> when it is a plain list ("a,b,c,*", "12", "**"), else None (#2239). Letter lists
    longer than five characters lost their letters ("a,b,c,*" read as "*" alone), "12" read as 1 and 2, and "**"
    (a mark of its own) as "*" twice."""
    tokens = [t for t in re.split(r"[\s,]+", text.strip()) if t]
    if tokens and all(re.fullmatch(r"\d+|[a-zA-Z]|([^\w\s])\1*", t) for t in tokens):
        return tokens
    return None


def _is_correspondence_note(para, entries):
    """True when an author-info paragraph is a correspondence note (#2239): it opens with a correspondence or
    reprints label ("Address for correspondence:", "Correspondence to", "*Address all correspondence to Dr ..."), or,
    unlabelled, it carries an e-mail and opens with a byline author's name ("Denis Souto Valente, M.D., <street>,
    [e-mail]"). An affiliation line with an e-mail that names no author stays."""
    pid = para.get("id") or ""
    if re.match(r"(?:cor\d*|c\d+)$", pid, re.I):
        return True
    text = re.sub(r"\s+", " ", para.get_text(" ", strip=True))
    body = re.sub(r"^[\s*\u2217\u2020\u2021\u00a7\u00b6#]+", "", text)
    if _LWW_CORR_LABEL.match(body):
        return True
    has_email = para.select_one('a[href*="mailto"], a[href*="email-protection"], .__cf_email__') is not None \
        or _EMAIL_TEXT.search(text)
    return bool(has_email and entries and (name := _statement_name(body)) and _match_byline(name, entries))


class Lippincott(PublisherParser):
    parser_name = "lippincott"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url(
            "journals.lww.com") or bool(self.soup.find(
            id="ejp-article-authors")) or self.substr_in_citation_publisher(
            'American Society of Anesthesiologists')

    def authors_found(self):
        return self.soup.find(id="ejp-article-authors") or self.soup.select(
            '.al-author-name')

    @staticmethod
    def assign_affs_from_name(author_affiliations: List[AuthorAffiliations], affiliations):
        for aff in affiliations:
            matched_name = None
            for author in author_affiliations:
                name_parsed = HumanName(author.name)
                if name_parsed.first in aff.organization and name_parsed.last in aff.organization:
                    author.affiliations.append(aff.organization)
                    matched_name = name_parsed
            if matched_name:
                for author in author_affiliations:
                    name_parsed = HumanName(author.name)
                    if name_parsed.first in aff.organization and name_parsed.last in aff.organization:
                        continue
                    for i, _aff in enumerate(author.affiliations):
                        if aff.organization == _aff:
                            author.affiliations.pop(i)
                            break
        return author_affiliations

    def parse(self):
        if bool(self.soup.select('.al-author-name')):
            authors_affiliations = self.get_authors_2()
        else:
            authors = self.get_authors()
            affiliations = self.get_affiliations()
            authors_affiliations = self.merge_authors_affiliations(authors,
                                                                   affiliations)
            authors_affiliations = self.assign_affs_from_name(authors_affiliations, affiliations)

        abstract = None
        if abs_wrap := self.soup.select_one(
                'section#abstractWrap'):
            # The tabbed template holds two panels, "Abstract" and a machine-written "Plain Language Summary" ("Text
            # is machine generated and may contain inaccuracies."): only the first is the abstract (#2239 phase 2).
            abs_wrap = abs_wrap.select_one('.ejp-article-text-abstract') or abs_wrap
            if len(abs_wrap.text) > 100:
                abstract = abs_wrap.text.strip()
        elif (abstract_tag := self.soup.select_one('section#ArticleBody')) and not self._is_full_text(abstract_tag):
            abstract = abstract_tag.text.strip()
        abstract = re.sub('^abstract', '', abstract,
                          flags=re.IGNORECASE).strip() if abstract else None
        return {"authors": authors_affiliations, "abstract": abstract}

    # What only a work's full text holds: its closing statements, its reference list, a letter's salutation. A
    # meeting abstract's body (the one case where the body is the abstract) has none of them.
    _BACK_MATTER_HEADING = re.compile(
        r"^\s*(?:conflicts? of interest|financial support|declaration of|references?$|acknowledge?ments?|"
        r"authors?['’]? contributions?|data availability|ethic)", re.I)
    _LETTER_OPENING = re.compile(r"^\s*(?:dear (?:editor|sir)|to the editor|sir)\b", re.I)

    def _is_full_text(self, body):
        """True when section#ArticleBody is the work's full text (a letter, an editorial, a case report with no
        abstract section), not an abstract standing where the body would be (#2239 phase 2, round 3: letters came
        out with their whole text, statements and all, as the abstract)."""
        if self._LETTER_OPENING.match(body.get_text()):
            return True
        return any(self._BACK_MATTER_HEADING.match(h.get_text(" ", strip=True))
                   for h in body.find_all(re.compile("^h[1-6]$")))

    @classmethod
    def affs_last_name_map(cls, aff_tags):
        d = {}
        fallback_affs = []
        for aff_tag in aff_tags:
            if email_tag := aff_tag.find('a'):
                email_tag.decompose()
            aff_txt = aff_tag.text.strip()
            fallback_affs.append(aff_txt)
            if last_name := re.findall(r'^(\(.*?\))', aff_txt):
                only_aff = aff_txt.replace(last_name[0], '')
                last_name = last_name[0]
                for name in last_name.split(','):
                    name = name.strip('()')
                    if name not in d:
                        d[name] = []
                    d[name].append(only_aff)
        return d, fallback_affs

    def get_authors_2(self):
        author_names = [tag.text for tag in
                        self.soup.select('.al-author-name a.linked-name')]
        affiliation_tags = self.soup.select('.article-footnote')
        affs_map, affs = self.affs_last_name_map(affiliation_tags)
        authors = []
        corr_author_email = ''
        if corr_author_email_tag := self.soup.select_one(
            '.article-footnote a[href*=mailto]') or self.soup.select_one(
            '.info-author-correspondence a[href*=mailto]'):
            corr_author_email = corr_author_email_tag.get('href')
        for name in author_names:
            name_parsed = HumanName(name)
            name_split = [item for item in split_name(name) if '.' not in item]
            authors.append(
                {'name': name, 'affiliations': affs_map.get(name_parsed.last, []) if affs_map else affs,
                 'is_corresponding': name_in_text(name_split[-1].lower(),
                                                  corr_author_email.lower())})
        return authors

    def get_authors(self):
        authors = []
        author_section = self.soup.find(id="ejp-article-authors")
        if not author_section:
            return authors
        author_soup = author_section.findAll("sup")

        # authors with ids
        broke_at = None
        for author in author_soup:
            is_corresponding = None
            # set name
            name = self.clean_name(author.previous_element)
            if ";" in name:
                # An unmarked author sits before this one ("Alchokhachi, Zahra; Ghanem, Ahmed<sup>a</sup>"): the mark
                # is the last name's. Reading stopped here, so every later author lost their marks and took the
                # page's unmarked lines instead; the list is put back in byline order below (#2239).
                last = name.rsplit(";", 1)[-1].strip()
                if not re.search(r",\s*[^\W\d_]", last):  # not a "Family, Given" name ("FACG,"): stop, as before
                    break
                broke_at = len(authors) if broke_at is None else broke_at
                name = last

            if '∗' in author.text or '*' in author.text:
                is_corresponding = True

            # set aff_ids
            aff_ids = _mark_list(author.text) or (
                self.parse_aff_ids(author.text, first=False) if len(author.text) > 5 else list(author.text))

            if not aff_ids and name.lower().startswith("editor"):
                continue
            authors.append(Author(name=name, aff_ids=aff_ids,
                                  is_corresponding=is_corresponding))

        def author_already_exists(name):
            for author in authors:
                if author.name.lower() == name.lower():
                    return True
            return False

        # authors without ids
        if author_section.p:
            author_names = author_section.find("p")
            for sup in author_names.find_all('sup'):
                sup.decompose()

            parsed_author_names = author_names.text.split(";")
            if broke_at is not None:
                order = [name.replace("∗", "").strip() for name in parsed_author_names]
                if not all(author.name in order for author in authors):
                    authors = authors[:broke_at]  # cannot place them in the byline: read as before (#2239)
            for name in parsed_author_names:
                name = name.replace("∗", "").strip()
                if author_already_exists(name):
                    continue
                authors.append(Author(name=name, aff_ids=[]))
            if broke_at is not None and all(author.name in order for author in authors):
                authors.sort(key=lambda author: order.index(author.name))

        starred = [author for author in authors if author.is_corresponding]
        if starred and self._star_is_not_a_mark(on_everyone=len(starred) == len(authors), starred=starred):
            for author in starred:
                author.is_corresponding = None
        elif starred and (named := getattr(self, "_address_author", None)):
            for author in starred:  # the star leads to one author's own address: his mark alone (#2239)
                author.is_corresponding = True if author.name == named else None

        if not [author for author in authors if author.is_corresponding]:
            for author in self._named_in_correspondence_note(authors):
                author.is_corresponding = True
        return authors

    def _star_is_not_a_mark(self, on_everyone, starred=()):
        """True when the byline's stars are footnote keys, not corresponding marks (oxjob #2288).

        LWW keys affiliations with *, †, ‡ ("From the *Department of Surgery ...", "<sup>*</sup>Department of ..."), so
        a star often sits on every author: ~160 stored LWW pages flagged every author from it. The star is a mark
        only when the author-info notes use it for a corresponding note ("*Corresponding author: ..."), or, with no
        star in the notes at all, when it sits on some authors only (#2128 kept that case).
        """
        holder = self.soup.select_one("div.ejp-article-authors-info-holder")
        text = holder.get_text(" ", strip=True) if holder is not None else ""
        address_star, self._address_author = self._star_keys_an_address(holder, starred)
        if address_star:
            text = text.replace(address_star, " ", 1)
        if _STAR_KEY.search(text):
            return True
        return not address_star and not _STAR_CORR.search(text) and on_everyone

    @staticmethod
    def _star_keys_an_address(holder, starred):
        """(note text, byline name) when a star keys a starred author's own address with an e-mail, else (None, None)
        (#2239).

        "<sup>*</sup>Michael L. Volk, MD, MSc, Division of ..., Ann Arbor, MI 48109. E-mail: ..." (10.1002/cld.420)
        is a correspondence footnote with no label: the star is the corresponding mark, not an affiliation key
        ("<sup>*</sup>Department of Surgery, ..."), which names no author.
        """
        if holder is None or not starred:
            return None, None
        for para in holder.find_all("p"):
            note = para.get_text(" ", strip=True)
            star = re.match(r"\s*" + _STAR + r"\s*", note)
            if star and re.search(r"e-?mail", note, re.I) and (name := _statement_name(note[star.end():])) and (
                    hit := _match_byline(name, [(author.name, []) for author in starred])):
                return note, hit
        return None, None

    def _named_in_correspondence_note(self, authors):
        """The authors the page's first correspondence note names (oxjob #2288).

        The note is read from "correspond..." on, never the affiliation text before it in the same paragraph; a
        surname counts as a whole word ("Li" is not in "Little Rock") held by one author only; two authors sharing it
        are told apart by the note's first-named person ("Correspondence to Carol L. Shields"). A note naming several
        authors ("... to Ashlea A. Lem ..., or Misty Schwartz") marks each.
        """
        tag = self.soup.find(lambda t: t.name == 'p' and 'correspondence' in t.text.lower())
        if tag is None:
            return []
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
        if (start := text.lower().find("correspond")) < 0:  # the word split across tags
            return []
        note = text[start:]
        surnames = [author.name.split(",")[0].strip() for author in authors]
        named = [author for author, surname in zip(authors, surnames) if surname and surnames.count(surname) == 1
                 and re.search(r"(?<![\w-])" + re.escape(surname) + r"(?![\w-])", note)]
        if (found := _LWW_CORR_LABEL.search(note)) and (name := _statement_name(note[found.end():])):
            hit = _match_byline(name, [(author.name, []) for author in authors])
            named += [author for author in authors if author.name == hit and author not in named]
        return named

    @staticmethod
    def parse_aff_ids(aff_text, first=True):
        if matches := re.findall(r'([^a-zA-Z\d \':,/])|(\d+)', aff_text[:15]):
            matches = [item for sublist in matches for item in sublist if item]
            return matches[0] if first else matches
        return None if first else []

    def get_affiliations(self):
        aff_blacklist_prefixes = ['accepted',
                                  'received',
                                  'presented',
                                  'this',
                                  'revision',
                                  'disclosure',
                                  'reprint',
                                  'supported',
                                  'the authors',
                                  'patients have',
                                  'abbreviations',
                                  'funding']
        aff_blacklist_substr = ['contributed equally']

        def exclude_aff(aff_text):
            for prefix in aff_blacklist_prefixes:
                if aff_text.lower().startswith(prefix):
                    return True
            for substr in aff_blacklist_substr:
                if substr in aff_text.lower():
                    return True
            # "The author has disclosed no conflicts of interest." stood as the affiliation (#2239)
            return bool(_DISCLOSURE.search(aff_text))

        def cleanup_aff(aff_text):
            # aff.next_element.next_element is usually the NavigableString after
            # the <sup>, but on some LWW pages it's a Tag (e.g. <em>). Calling
            # .split on a Tag triggers bs4's child-tag lookup, which returns
            # None and then crashes the whole parse ("NoneType not callable").
            # Coerce to text first. NavigableString is already a str subclass.
            if aff_text is None:
                return ''
            if not isinstance(aff_text, str):
                aff_text = aff_text.get_text() if hasattr(
                    aff_text, 'get_text') else str(aff_text)
            aff_text = aff_text.split(' to:')[-1]
            aff_text = re.split(r'correspondence', aff_text, flags=re.IGNORECASE)[-1]
            aff_text = aff_text.split('From')[-1]
            aff_text = strip_prefix(r'[0-9]+', aff_text)
            return aff_text.strip(' ,:')

        aff_soup = self.soup.find("div",
                                  class_="ejp-article-authors-info-holder")
        if not aff_soup:
            return []

        results = []
        # The correspondence note is the corresponding author's postal address, not an affiliation: it was added to
        # that author, often twice (once more by assign_affs_from_name), or to every unmarked author (#2239).
        authors_section = self.soup.find(id="ejp-article-authors")
        entries = _byline_entries(authors_section) if authors_section is not None else []
        notes = [p for p in aff_soup.findAll("p") if _is_correspondence_note(p, entries)]

        # affiliations with ids
        affiliations = aff_soup.findAll("sup")
        for aff in affiliations:
            if aff.parent.get("id", "").startswith("cor") or aff.find_parent("p") in notes:
                continue

            aff_id = aff.text
            organization = cleanup_aff(aff.next_element.next_element)
            # "Departments of <sup>1</sup>Nuclear Medicine, <sup>2</sup>Psychiatry and <sup>3</sup>Tracer ...": the
            # text up to the next mark ends with the joining "and" (#2239)
            organization = re.sub(r"[\s,;]+(?:and|&)$", "", organization)
            results.append(
                Affiliation(aff_id=aff_id, organization=organization))

        # affiliation with no ids
        affiliations = [p for p in aff_soup.findAll("p") if p not in notes]
        if affiliations and ';' in affiliations[0].text:
            aff_texts = [txt.strip() for txt in affiliations[0].text.split(';')]
            for aff_text in aff_texts:
                aff_id = self.parse_aff_ids(aff_text)
                # parse_aff_ids returns None when no id matches; ''.split(None)
                # is [] and [-1] would IndexError. Fall back to the raw segment.
                org = aff_text.split(aff_id)[-1] if aff_id else aff_text
                results.append(Affiliation(aff_id=aff_id, organization=org))
            return results

        for aff in affiliations:
            if aff.sup:
                continue
            organization = cleanup_aff(aff.text)
            aff_id = None
            if aff_id := self.parse_aff_ids(aff.text.strip()):
                organization = aff.text.strip().split(aff_id)[-1].strip()
            if 'financial disclosure' in organization.lower():
                continue
            results.append(
                Affiliation(aff_id=aff_id, organization=organization))

        return [result for result in results if not exclude_aff(result.organization)]

    @staticmethod
    def clean_name(name):
        if name.startswith(";"):
            name = name[1:]
        name = name.strip()
        return name

    @staticmethod
    def format_ids(ids):
        ids_split = ids.split(",")
        aff_ids = []
        for aff_id in ids_split:
            if aff_id:
                aff_ids.append(aff_id)
        return aff_ids

    test_cases = [
        {
            "doi": "10.1097/LBR.0000000000000778",
            "result": [
                {
                    "name": "Avasarala, Sameer K. MBBS",
                    "affiliations": [
                        "Division of Allergy, Pulmonary, and Critical Care Medicine"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Lentz, Robert J. MD",
                    "affiliations": [
                        "Division of Allergy, Pulmonary, and Critical Care Medicine",
                        "Department of Thoracic Surgery, Vanderbilt University Medical Center",
                        "Department of Veterans Affairs Medical Center, Nashville, TN",
                    ],
                    "is_corresponding": None,
                },
            ],
        },
        {
            "doi": "10.1097/MJT.0000000000001293",
            "result": [
                {
                    "name": "Zhang, Wei-Yun MS",
                    "affiliations": [
                        "Department of Pulmonary and Critical Care Medicine, First Affiliated Hospital of Soochow University Suzhou, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Wang, Jia-Jia MM",
                    "affiliations": [
                        "Department of Pulmonary and Critical Care Medicine, First Affiliated Hospital of Soochow University Suzhou, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Liu, Ying-Ying MS",
                    "affiliations": [
                        "Department of Pulmonary and Critical Care Medicine, First Affiliated Hospital of Soochow University Suzhou, China"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Zeng, Da-Xiong MD",
                    "affiliations": [
                        "Department of Pulmonary and Critical Care Medicine, First Affiliated Hospital of Soochow University Suzhou, China"
                    ],
                    "is_corresponding": None,
                },
            ],
        },
        {
            "doi": "10.2106/jbjs.19.01395",
            "result": [
                {
                    "name": "Castile, Ryan M. BS",
                    "affiliations": [
                        "Departments of Mechanical Engineering & Materials Science (R.M.C., M.J.J., and S.P.L.) and Orthopaedic Surgery (S.P.L. and R.H.B.), Washington University in St. Louis, St. Louis, Missouri"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Jenkins, Matthew J. BS",
                    "affiliations": [
                        "Departments of Mechanical Engineering & Materials Science (R.M.C., M.J.J., and S.P.L.) and Orthopaedic Surgery (S.P.L. and R.H.B.), Washington University in St. Louis, St. Louis, Missouri"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Lake, Spencer P. PhD",
                    "affiliations": [
                        "Departments of Mechanical Engineering & Materials Science (R.M.C., M.J.J., and S.P.L.) and Orthopaedic Surgery (S.P.L. and R.H.B.), Washington University in St. Louis, St. Louis, Missouri"
                    ],
                    "is_corresponding": None,
                },
                {
                    "name": "Brophy, Robert H. MD",
                    "affiliations": [
                        "Departments of Mechanical Engineering & Materials Science (R.M.C., M.J.J., and S.P.L.) and Orthopaedic Surgery (S.P.L. and R.H.B.), Washington University in St. Louis, St. Louis, Missouri"
                    ],
                    "is_corresponding": None,
                },
            ],
        },
    ]
