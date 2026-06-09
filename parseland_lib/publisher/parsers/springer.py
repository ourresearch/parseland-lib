import json
import re
from collections import defaultdict
from unicodedata import normalize

from parseland_lib.elements import Author, Affiliation, AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser


class Springer(PublisherParser):
    parser_name = "springer"

    def is_publisher_specific_parser(self):
        return bool(
            self.domain_in_canonical_link("link.springer.com")
            or self.domain_in_canonical_link("springeropen.com")
            or self.domain_in_canonical_link("springermedizin.de")
            or self.domain_in_canonical_link("springerpflege.de")
            or self.domain_in_canonical_link("mijn.bsl.nl")
            or self.domain_in_meta_og_url("nature.com")
            or self.domain_in_meta_og_url("biomedcentral.com")
            or self.domain_in_meta_og_url("springermedizin.de")
            or self.domain_in_meta_og_url("springerpflege.de")
            or self.domain_in_meta_og_url("mijn.bsl.nl")
            or self._has_springer_materials_marker()
        )

    def authors_found(self):
        return True

    def _has_springer_materials_marker(self):
        title = self.soup.find("title")
        if title and "springermaterials" in title.get_text(" ", strip=True).lower():
            return True
        return bool(self.substr_in_citation_publisher("SpringerMaterials"))

    @staticmethod
    def _try_find_abstract_in_metadatas(metadatas):
        for md in metadatas:
            if 'description' in md:
                desc = md['description']
                # Springer book-chapter templates sometimes emit a
                # whitespace-only ``description`` (the chapter has no
                # formal Abstract section so the JSON-LD slot was
                # rendered empty). Treat strip-empty as missing so the
                # ``parse_abstract`` DOM fallback can fire instead of
                # locking in 400+ chars of pure whitespace.
                if isinstance(desc, str) and desc.strip():
                    return desc
        return None

    def parse_authors_method_3(self):
        author_tags = self.soup.select('li.c-article-authors-listing__item')
        authors = []
        for tag in author_tags:
            name_tag = tag.select_one('span[class*=search-name]')
            name = name_tag.text.strip()
            is_corr = bool(name_tag.select_one('a[id*=corresp]'))
            affs = [aff_tag.text.strip() for aff_tag in
                    tag.select('ol[class*=affiliation__list] li p')]
            authors.append({
                'name': name,
                'affiliations': affs,
                'is_corresponding': is_corr,
            })
        return authors

    @classmethod
    def _split(cls, input_string, split_char=',', min_length=5):
        substrings = []
        current_substr = ''
        for char in input_string:
            current_substr += char
            if char == split_char:
                if len(current_substr.strip()) >= min_length or not substrings:
                    substrings.append(current_substr)
                elif substrings:
                    substrings[-1] += current_substr
                current_substr = ''
        if current_substr:
            if len(current_substr.strip()) >= min_length:
                substrings.append(current_substr)
            elif substrings:
                substrings[-1] += current_substr

        return substrings

    @staticmethod
    def _is_author_suffix_token(value):
        compact = re.sub(r'[^A-Za-z]', '', value or '').upper()
        return compact in {
            'BA',
            'BS',
            'BSC',
            'DDS',
            'DMD',
            'DPHIL',
            'FBA',
            'FACP',
            'FRS',
            'FRCPC',
            'FRCP',
            'FRCPCH',
            'FRCS',
            'MA',
            'MBA',
            'MBBS',
            'MD',
            'MPH',
            'MSC',
            'PHD',
            'RN',
        }

    @classmethod
    def _merge_author_suffix_tokens(cls, names):
        merged = []
        for name in names:
            name = name.strip(' ,')
            if not name:
                continue
            if merged and cls._is_author_suffix_token(name):
                merged[-1] = f"{merged[-1]}, {name}"
                continue
            merged.append(name)
        return merged

    @classmethod
    def _author_match_key(cls, name):
        if not name:
            return None

        name = name.replace('\xa0', ' ').strip()
        honorifics = {
            'dr',
            'dipl',
            'ing',
            'prof',
            'professor',
            'sir',
            'wirt',
        }

        def _tokens(value):
            return re.findall(r'[^\W\d_]+', value, flags=re.UNICODE)

        if ',' in name:
            last_part, rest = name.split(',', 1)
            last_tokens = _tokens(last_part)
            first_tokens = _tokens(rest)
            while first_tokens and first_tokens[0].lower() in honorifics:
                first_tokens.pop(0)
            if last_tokens and first_tokens:
                return (normalize('NFKD', last_tokens[-1]).casefold(),
                        normalize('NFKD', first_tokens[0][:1]).casefold())

        tokens = _tokens(name)
        while tokens and tokens[0].lower() in honorifics:
            tokens.pop(0)
        while len(tokens) > 1 and (
            cls._is_author_suffix_token(tokens[-1])
            or (len(tokens[-1]) == 1 and tokens[-1].isupper())
        ):
            tokens.pop()
        if not tokens:
            return None
        return (normalize('NFKD', tokens[-1]).casefold(),
                normalize('NFKD', tokens[0][:1]).casefold())

    @staticmethod
    def _author_name(author):
        if isinstance(author, dict):
            return (author.get('name') or '').replace('\xa0', ' ').strip()
        return (getattr(author, 'name', '') or '').replace('\xa0', ' ').strip()

    @staticmethod
    def _author_affiliations(author):
        if isinstance(author, dict):
            return list(author.get('affiliations') or [])
        return list(getattr(author, 'affiliations', None) or [])

    @staticmethod
    def _author_is_corresponding(author):
        if isinstance(author, dict):
            return author.get('is_corresponding')
        return getattr(author, 'is_corresponding', None)

    def _parse_short_author_list(self):
        names = []
        seen = set()
        for tag in self.soup.select(
            'ul.c-article-author-list [data-test="author-name"]'
        ):
            name = tag.get_text(' ', strip=True).replace('\xa0', ' ').strip(' ,')
            if not name:
                continue
            key = re.sub(r'\s+', ' ', name).casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
        return [
            {
                'name': name,
                'affiliations': [],
                'is_corresponding': None,
            }
            for name in names
        ]

    def _editor_text_norm(self):
        try:
            section = (
                self.soup.find(id="editor-information-section")
                or self.soup.find(id="editor-information-content")
            )
            if section is None:
                return ''
            return section.get_text(' ', strip=True).replace('\xa0', ' ').lower()
        except Exception:
            return ''

    def _repair_authors_from_short_list(self, authors):
        short_authors = self._parse_short_author_list()
        if not short_authors:
            return authors

        if not authors:
            return short_authors

        current_by_key = {}
        current_keys = []
        for author in authors:
            key = self._author_match_key(self._author_name(author))
            if not key:
                continue
            current_keys.append(key)
            current_by_key.setdefault(key, author)

        short_keys = [
            self._author_match_key(short_author['name'])
            for short_author in short_authors
        ]
        short_keys = [key for key in short_keys if key]
        if not short_keys:
            return authors
        if not current_keys:
            return short_authors

        current_set = set(current_keys)
        short_set = set(short_keys)
        editor_text = self._editor_text_norm()
        current_names = [self._author_name(author) for author in authors]
        current_all_in_editor_section = bool(editor_text) and all(
            name and name.lower() in editor_text
            for name in current_names
        )

        should_replace = (
            current_set < short_set
            or short_set < current_set
            or (current_all_in_editor_section and short_set != current_set)
        )
        if not should_replace:
            return authors

        unique_current_affiliations = []
        seen_affiliations = set()
        for author in authors:
            affs = tuple(self._author_affiliations(author))
            if not affs or affs in seen_affiliations:
                continue
            seen_affiliations.add(affs)
            unique_current_affiliations.append(affs)
        shared_affiliations = (
            list(unique_current_affiliations[0])
            if current_set < short_set and len(unique_current_affiliations) == 1
            else []
        )

        repaired = []
        for short_author in short_authors:
            key = self._author_match_key(short_author['name'])
            current = current_by_key.get(key)
            repaired.append({
                'name': short_author['name'],
                'affiliations': (
                    self._author_affiliations(current)
                    if current else shared_affiliations
                ),
                'is_corresponding': (
                    self._author_is_corresponding(current)
                    if current else None
                ),
            })
        return repaired

    def parse_authors_method_2(self):
        author_tags = self.soup.select(
            'ol.c-article-author-affiliation__list li[id*=A]')
        authors_by_key = {}
        author_order = []
        for author_tag in author_tags:
            aff_tag = author_tag.select_one('p[class*=affiliation__address]')
            authors_tag = author_tag.select_one('p[class*=authors-list]')
            if not aff_tag or not authors_tag:
                continue

            aff_text = aff_tag.text.strip().split('E-mail')[0].strip()
            author_names = [
                name.strip(' ,')
                for name in self._split(authors_tag.text.replace('&', ',').strip())
                if '(' not in name and name.strip(' ,')
            ]
            author_names = self._merge_author_suffix_tokens(author_names)
            for name in author_names:
                key = name.replace('\xa0', ' ').strip().lower()
                if key not in authors_by_key:
                    authors_by_key[key] = {
                        'name': name,
                        'affiliations': [],
                        'is_corresponding': None
                    }
                    author_order.append(key)
                if aff_text and aff_text not in authors_by_key[key]['affiliations']:
                    authors_by_key[key]['affiliations'].append(aff_text)
        return [authors_by_key[key] for key in author_order]

    def _parse_springer_materials_authors(self):
        authors_section = self.soup.select_one("dd#authors")
        if not authors_section:
            return []

        affiliations_by_id = {}
        for tag in self.soup.select("dd.author-affiliation li"):
            text = tag.get_text(" ", strip=True).replace("\xa0", " ")
            text = re.sub(r"\s+", " ", text).strip()
            match = re.match(r"^([A-Za-z0-9_]+)\s+(.+)$", text)
            if not match:
                continue
            aff_id, affiliation = match.groups()
            if affiliation:
                affiliations_by_id[aff_id] = [affiliation]

        authors = []
        for tag in authors_section.select("li"):
            sup = tag.find("sup")
            aff_id = ""
            if sup:
                aff_id = sup.get_text(" ", strip=True).strip("() ")

            name_parts = []
            for child in tag.children:
                child_name = getattr(child, "name", None)
                if child_name in {"a", "sup"}:
                    continue
                text = (
                    child.get_text(" ", strip=True)
                    if child_name
                    else str(child)
                )
                if text.strip():
                    name_parts.append(text)
            name = re.sub(r"\s+", " ", " ".join(name_parts)).strip(" ,")
            if not name:
                continue

            fallback_aff = []
            if sup and sup.get("title"):
                fallback_aff = [sup.get("title").strip()]
            authors.append({
                "name": name,
                "affiliations": affiliations_by_id.get(aff_id, fallback_aff),
                "is_corresponding": None,
            })

        return authors

    def parse(self):
        article_metadatas = self.parse_article_metadatas()
        abstract = self._try_find_abstract_in_metadatas(article_metadatas)
        authors_affiliations = None
        if self.soup.select('li.c-article-authors-listing__item'):
            authors_affiliations = self.parse_authors_method_3()

        if not authors_affiliations:
            authors = self.get_authors()
            if authors:
                affiliations = self.get_affiliations()
                authors_affiliations = self.merge_authors_affiliations(
                    authors, affiliations
                )

        if not authors_affiliations:
            authors_affiliations = self.parse_authors_method_2()

        if not authors_affiliations and self._has_springer_materials_marker():
            authors_affiliations = self._parse_springer_materials_authors()

        if not authors_affiliations:
            authors_affiliations = self.parse_author_meta_tags()
            for author in authors_affiliations:
                author['affiliations'] = [aff.split('Fax')[0] for aff in author['affiliations']]

        if not authors_affiliations:
            authors = self.get_authors(try_editors=True)
            if authors:
                affiliations = self.get_affiliations(try_editors=True)
                authors_affiliations = self.merge_authors_affiliations(
                    authors, affiliations
                )

        if not authors_affiliations:
            authors_affiliations = self.parse_ld_json(article_metadatas)

        # Try to detect corresponding author from "Correspondence to" text
        authors_affiliations = self._mark_corresponding_author(authors_affiliations)

        # Additive CA detection from email signals. The earlier parser paths
        # (methods 2/3, get_authors, meta tags, editors) typically leave
        # is_corresponding=None even when the page carries clear email-based
        # CA signals. The ld+json path sets it from author.email, but only
        # fires when every earlier path returned empty — so the email signal
        # is silently dropped for the majority of pages. Use it here as a
        # supplement that only ever turns CA on, never off.
        authors_affiliations = self._mark_corresponding_from_emails(
            authors_affiliations
        )

        # Strip NBSP from author names + affiliations and dedupe authors by
        # normalized name. Two distinct issues both close here:
        #
        #   (a) NBSP padding: parse_ld_json and parse_authors_method_2 emit
        #       names with leading/trailing `\xa0` characters that survive
        #       BeautifulSoup's `.text.strip()`. Downstream the bipartite
        #       author scorer doesn't normalize NBSP, so the gold "Anders
        #       Wahlin" never matches the parsed "Anders Wahlin\xa0".
        #
        #   (b) Within-page duplicates: some Springer templates emit each
        #       author twice (once in the author list, once in an "author
        #       information" expander block). Without dedupe, the parser
        #       inflates parsed_total well past gold_total — every duplicate
        #       costs precision on every metric that uses parsed count.
        #
        # Implementation is intentionally conservative: dedupe key is the
        # normalized name lowercased; merge affiliations into the first
        # occurrence; OR the is_corresponding flag (never clears it). Order
        # of first occurrence is preserved.
        authors_affiliations = self._normalize_and_dedupe(authors_affiliations)

        # Book-chapter pages on SpringerLink include a separate
        # `<div id="editor-information-section">` block listing the book's
        # editors (with their affiliations and academic titles). The legacy
        # parser paths sometimes pull names from this block into the author
        # list — e.g. on `10.1007/978-1-4939-7274-6_16` the parser returns
        # the 2 chapter authors plus "Robert C. Elston" (book editor). The
        # filter below drops any parsed author whose normalized name appears
        # in that block's text, leaving journal articles (no editor section)
        # untouched.
        authors_affiliations = self._drop_book_editors_from_authors(
            authors_affiliations
        )
        authors_affiliations = self._repair_authors_from_short_list(
            authors_affiliations
        )

        # Prefer the DOM Abstract section when present: on multi-paragraph
        # book-chapter abstracts the JSON-LD ``description`` carried only
        # the opening paragraph (truncated at ~600-700 chars), while the
        # DOM section had every paragraph. When both exist, the longer of
        # the two wins (DOM nearly always is).
        dom_abstract = self.parse_abstract()
        if dom_abstract and (not abstract or len(dom_abstract) > len(abstract)):
            abstract = dom_abstract
        if not abstract:
            abstract = self._parse_missing_abstract_fallback()

        return {"authors": authors_affiliations,
                "abstract": abstract or dom_abstract, }

    def _get_correspondence_name(self):
        """Extract corresponding author name from 'Correspondence to' section."""
        # Look for "Correspondence to" paragraph
        corr_p = self.soup.find(lambda tag: (
            tag.name == 'p' and
            'correspondence to' in tag.text.lower()[:30]
        ))
        if corr_p:
            text = corr_p.get_text(" ", strip=True)
            # Extract name after "Correspondence to".
            # Original pattern was `(.+?)(?:\.|$)` — non-greedy `.+?` paired
            # with `(?:\.|$)` truncates at the FIRST period in the candidate
            # name, which on a name like "Robert J. Wright" stops after the
            # middle initial's period and returns just "Robert J". That
            # caused the 2-part name-match in `_mark_corresponding_author`
            # to fail on every Springer page where the CA has an initial.
            # Capture greedily to the end of the text node, then strip a
            # single trailing period — initials in the middle survive.
            import re
            match = re.search(r'[Cc]orrespondence\s+to\s*[:\.]?\s*(.+?)\s*$', text)
            if match:
                name = match.group(1).strip()
                # Strip a trailing standalone period (the sentence-ending
                # "." after the name, common in this template). Internal
                # initials like "J." stay because they're not at the end.
                if name.endswith("."):
                    name = name[:-1].rstrip()
                return name

        # Also check for "Corresponding author" section
        corr_section = self.soup.find(lambda tag: (
            tag.name in ('p', 'div', 'section') and
            'corresponding author' in tag.text.lower()[:30]
        ))
        if corr_section:
            # Try to find email link to identify corresponding author
            email_link = corr_section.find('a', href=lambda x: x and 'mailto:' in x)
            if email_link:
                # Return the text before the email as potential name
                text = corr_section.text.split('@')[0]
                import re
                match = re.search(r'[Cc]orresponding\s+author[:\s]*(.+?)(?:\s*[,\(]|$)', text)
                if match:
                    return match.group(1).strip()

        return None

    def _drop_book_editors_from_authors(self, authors):
        """Drop parsed authors that are actually the book's editors.

        On SpringerLink book-chapter pages, the legacy `get_authors` /
        `parse_authors_method_2` / `parse_ld_json` paths sometimes scoop
        names out of the book's editor section into the chapter author
        list. The page exposes editor names in a dedicated DOM block:

            <div id="editor-information-section">
              Editor information
              Editors and Affiliations
              <affiliation lines>
              <editor name (often prefixed with "Prof.", "Dr.", "Professor")>
              ...
            </div>

        Names that show up there are NOT chapter authors. Drop any
        parsed author whose normalized name (NBSP-stripped, lowercased)
        appears in the editor section's plain text.

        Defensive:
          - If no editor section exists (every journal article, plus
            many newer book chapters), this is a no-op.
          - Substring match is on the lowercased + NBSP-normalized form
            so academic titles in the page text don't block the match.
          - Skipped for authors with empty / very-short names.

        Returns the filtered list. Never raises.
        """
        if not authors:
            return authors
        try:
            section = (
                self.soup.find(id="editor-information-section")
                or self.soup.find(id="editor-information-content")
            )
            if section is None:
                return authors
            editor_text = section.get_text(" ", strip=True)
            if not editor_text:
                return authors
            editor_text_norm = editor_text.replace("\xa0", " ").lower()
        except Exception:
            return authors

        def _name_of(a):
            if isinstance(a, dict):
                return (a.get("name") or "").strip()
            return (getattr(a, "name", "") or "").strip()

        # Pre-compute the set of "editor names found in parser output" so we
        # can decide whether the filter would drop everyone. Some chapter
        # types — particularly single-author book chapters where the chapter
        # author also edited the book (Jan W. Gooch's encyclopedia
        # contributions are the canonical case) — list one name in BOTH the
        # author area and the editor section. A naive drop would zero out
        # the author list. If the filter would drop every parsed author,
        # bail out and keep everything: the editor-section is then telling
        # us "this is the same person", not "these are extra editors".
        flagged_indices = []
        for i, a in enumerate(authors):
            name = _name_of(a)
            if not name or len(name) < 3:
                continue
            name_norm = name.replace("\xa0", " ").lower()
            if name_norm in editor_text_norm:
                flagged_indices.append(i)

        if len(flagged_indices) >= len(authors):
            # Every parsed author appears in the editor section → preserve
            # all (single-author-also-editor case). Without this guard
            # iter-3 regressed F1 to 0 on 7 such rows.
            return authors

        out = []
        for i, a in enumerate(authors):
            if i in flagged_indices:
                # Drop — this person is in the editor section, not a
                # chapter author. (False positives are theoretically
                # possible if a chapter author is ALSO the book editor;
                # in practice on SpringerLink that overlap is rare and
                # the precision win from dropping editor-name false
                # positives outweighs it.)
                continue
            out.append(a)
        return out

    def _normalize_and_dedupe(self, authors):
        """Strip NBSP from names + affiliations and dedupe authors by
        normalized name.

        Operates on the final author list emitted by ``parse()`` regardless
        of which primary path produced it. Two failure modes both clear here:

          (a) Author names with leading/trailing `\\xa0` (non-breaking
              space) — emitted by ``parse_ld_json`` and the legacy
              ``parse_authors_method_2`` split logic. The downstream
              bipartite author scorer in parseland-eval doesn't normalize
              NBSP, so 'Anders Wahlin\\xa0' fails to match the gold
              'Anders Wahlin' and shows up as a precision miss + a CA
              recall miss simultaneously.

          (b) Within-page author duplication. Some Springer templates emit
              each author twice — e.g. once in the headline author list,
              once again in an "Author information" expander block. The
              parser concatenates both into a single output list, inflating
              ``parsed_total`` and dragging precision on every metric.

        Dedupe key is the lowercased normalized name. The first occurrence
        wins position; duplicate occurrences merge their affiliation lists
        in document order (no reordering, no de-dup of the affiliations
        themselves beyond exact-match). ``is_corresponding`` is OR-ed across
        duplicates so a CA-flagged second occurrence promotes the first.

        Mutates the input objects (sets ``name``/``affiliations`` to the
        normalized form) and returns the filtered list. Handles both dict
        and dataclass ``AuthorAffiliations`` author shapes.
        """
        if not authors:
            return authors

        def _norm_aff(a):
            return a.replace("\xa0", " ").strip() if isinstance(a, str) else a

        seen: dict[str, int] = {}
        out: list = []
        for a in authors:
            if isinstance(a, dict):
                name = (a.get("name") or "").replace("\xa0", " ").strip()
                affs = [_norm_aff(x) for x in (a.get("affiliations") or [])]
                affs = [x for x in affs if x]
                ca = bool(a.get("is_corresponding"))
                a["name"] = name
                a["affiliations"] = affs
            else:
                raw_name = getattr(a, "name", "") or ""
                name = raw_name.replace("\xa0", " ").strip()
                raw_affs = getattr(a, "affiliations", None) or []
                affs = [_norm_aff(x) for x in raw_affs]
                affs = [x for x in affs if x]
                ca = bool(getattr(a, "is_corresponding", False))
                try:
                    a.name = name
                    a.affiliations = affs
                except Exception:
                    pass

            if not name:
                continue

            key = name.lower()
            if key in seen:
                idx = seen[key]
                existing = out[idx]
                # Conservative aff handling: only adopt affiliations from the
                # duplicate occurrence when the first occurrence carried
                # none. Merging across duplicates inflates the per-author aff
                # set past what gold typically lists (gold tends to attribute
                # one primary affiliation per author per paper) — which
                # drags the per-pair affiliation F1 even when the parser is
                # semantically right that the author appears at both places
                # on the page. This rule preserves iter-1's affiliation
                # quality on rows where the first occurrence already had
                # affs, while still rescuing dup cases where the FIRST entry
                # was aff-less and a later occurrence carries the real list.
                if isinstance(existing, dict):
                    if not (existing.get("affiliations") or []) and affs:
                        existing["affiliations"] = list(affs)
                    if ca and not existing.get("is_corresponding"):
                        existing["is_corresponding"] = True
                else:
                    if not (getattr(existing, "affiliations", None) or []) and affs:
                        try:
                            existing.affiliations = list(affs)
                        except Exception:
                            pass
                    if ca and not getattr(existing, "is_corresponding", False):
                        try:
                            existing.is_corresponding = True
                        except Exception:
                            pass
                continue

            seen[key] = len(out)
            out.append(a)

        return out

    def _mark_corresponding_from_emails(self, authors):
        """Additive CA detection from email signals on the page.

        Used as a supplement after the primary parser paths and the
        ``_mark_corresponding_author`` text-based path have run. Only ever
        sets ``is_corresponding = True``; never clears it. Robust to NBSP
        and trailing whitespace in author names that came out of the
        primary paths (Springer's JSON-LD path is the worst offender).

        Signals used, in order:
          1. ``<meta name="citation_author_email">`` — 97% of Springer pages
             with a corresponding author carry these. Order on the page
             tracks the order of the matching ``<meta name="citation_author">``
             tags, so we pair them index-by-index.
          2. ``<script type="application/ld+json">`` authors with an
             ``email`` field — same per-author signal, redundant with (1)
             on most pages, but cheap to include and catches the legacy
             Springer subset where only one signal exists.

        Never raises.
        """
        if not authors:
            return authors

        ca_names: set[str] = set()
        ca_surnames: set[str] = set()

        def _surname_of(meta_name: str) -> str:
            """Derive surname from a citation_author / ld+json author name.

            Springer's ``citation_author`` meta tag almost always uses the
            "Surname, Given Names" convention (e.g. ``Ibrahim, Adel Ehab``,
            ``O'Donnell, Patricia M.``). A naive ``rsplit(' ', 1)[-1]``
            then picks the LAST given-name token as the surname:

                - ``Ibrahim, Adel Ehab``  → ``Ehab``  (wrong; should be Ibrahim)
                - ``O'Donnell, Patricia M.`` → ``M.``  (wrong; should be O'Donnell)

            That mis-derived surname then floods ``ca_surnames`` with
            common given names ("Ahmed", "M.") that collide with other
            authors' real surnames (creating CA false positives) AND fails
            to match the parser's "Given Surname" DOM-order names (creating
            CA false negatives).

            Comma-aware split: if the meta content has exactly one comma,
            treat the part BEFORE the comma as the surname. Otherwise fall
            back to the original ``rsplit`` behavior so ld+json names in
            "Given Surname" form (no comma) still work.
            """
            if not meta_name:
                return meta_name
            if meta_name.count(",") == 1:
                surname = meta_name.split(",", 1)[0].strip()
                if surname:
                    return surname
            return meta_name.rsplit(" ", 1)[-1]

        def _norm_name(s: str) -> str:
            return " ".join((s or "").replace("\xa0", " ").lower().split())

        def _person_key(name: str) -> tuple[str, str]:
            """Return a conservative (surname, first-initial) key.

            Springer meta names are commonly "Surname, Given" while DOM
            names are "Given Surname". Matching only on surname created false
            positives whenever coauthors shared a surname. This key keeps the
            useful comma-order bridge without marking every same-surname
            coauthor as corresponding.
            """
            name = _norm_name(name)
            if not name:
                return ("", "")
            if name.count(",") == 1:
                surname, given = [p.strip() for p in name.split(",", 1)]
                first = given.split()[0] if given.split() else ""
                return (surname, first[:1])
            parts = name.split()
            if len(parts) == 1:
                return (parts[0], "")
            return (parts[-1], parts[0][:1])

        try:
            # Walk both citation_author and citation_author_email metas in
            # document order. Track the most recent citation_author content;
            # each citation_author_email pairs with whatever
            # citation_author preceded it. This matches Highwire's "email
            # meta sits immediately after its author meta" convention used
            # by Springer / ScienceDirect / most academic publisher
            # templates. Falls back gracefully when an email meta has no
            # preceding author meta (skipped silently).
            #
            # Discriminator: book-chapter pages on Springer's modern template
            # routinely emit citation_author_email for EVERY chapter author —
            # not just the one(s) annotators mark as corresponding. Treating
            # "has email" as a CA signal then floods false positives on
            # those rows (canonical: 978-981-10-4508-0_44 where all 5
            # authors have emails but gold lists 1 CA). When the count of
            # email-bearing authors equals the count of authors with metas,
            # the per-author email signal is non-discriminative for this
            # page — skip it and let the text-based "Correspondence to"
            # path handle the row instead.
            authors_in_meta: list[str] = []
            emailed_authors: list[str] = []
            current_author = None
            for meta in self.soup.find_all(
                "meta",
                attrs={"name": ["citation_author", "citation_author_email"]},
            ):
                name = meta.get("name")
                content = (meta.get("content") or "").strip()
                if not content:
                    continue
                if name == "citation_author":
                    current_author = content
                    authors_in_meta.append(content)
                elif name == "citation_author_email" and current_author:
                    emailed_authors.append(current_author)

            n_authors = len(authors_in_meta)
            n_emails = len(emailed_authors)
            # Only treat emails as CA signal when fewer than ALL the
            # citation_author metas have a paired email. ≥2 metas required
            # so single-author pages (where the only author is by
            # definition the CA) still benefit from the email signal.
            email_signal_discriminative = (
                n_authors >= 2 and 0 < n_emails < n_authors
            )
            if email_signal_discriminative:
                for current_author in emailed_authors:
                    ca_names.add(current_author)
                    ca_surnames.add(_surname_of(current_author))
            elif n_authors < 2 and emailed_authors:
                # Single-author page — preserve the iter-2 behavior.
                for current_author in emailed_authors:
                    ca_names.add(current_author)
                    ca_surnames.add(_surname_of(current_author))
        except Exception:
            pass

        try:
            # ld+json email signal — same per-author "every author has an
            # email" discriminator as above. Springer's ld+json block tends
            # to be a subset of the meta block (often just 1 author with
            # email even when the meta has more) so the discriminator runs
            # against the meta-based ``authors_in_meta`` count when
            # available, otherwise against the ld+json author count.
            ld_authors = 0
            ld_emailed: list[str] = []
            for s in self.soup.find_all("script", {"type": "application/ld+json"}):
                if not s.text:
                    continue
                try:
                    blob = json.loads(s.text)
                except Exception:
                    continue
                if isinstance(blob, dict) and "mainEntity" in blob:
                    blob = blob["mainEntity"]
                if not isinstance(blob, dict):
                    continue
                for a in blob.get("author") or []:
                    if not isinstance(a, dict):
                        continue
                    if a.get("name"):
                        ld_authors += 1
                    if a.get("email") and a.get("name"):
                        ld_emailed.append(a["name"].strip())

            ld_total = len(authors_in_meta) if authors_in_meta else ld_authors
            ld_discriminative = (
                ld_total >= 2 and 0 < len(ld_emailed) < ld_total
            ) or (ld_total < 2 and ld_emailed)
            if ld_discriminative:
                for name in ld_emailed:
                    ca_names.add(name)
                    ca_surnames.add(_surname_of(name))
        except Exception:
            pass

        if not ca_names:
            return authors

        def _norm(s: str) -> str:
            # NBSP-aware whitespace stripping. Python's default str.strip()
            # removes \xa0, but parser paths (esp. parse_ld_json) sometimes
            # surface names without normalization — collapse them here.
            return (s or "").replace("\xa0", " ").strip()

        ca_norms = {_norm_name(n) for n in ca_names if _norm_name(n)}
        ca_keys = {_person_key(n) for n in ca_names if _person_key(n)[0]}

        parsed_surname_counts: dict[str, int] = {}
        for author in authors:
            if hasattr(author, "name"):
                candidate = _norm(author.name)
            else:
                candidate = _norm(author.get("name", ""))
            surname, _initial = _person_key(candidate)
            if surname:
                parsed_surname_counts[surname] = parsed_surname_counts.get(surname, 0) + 1

        for author in authors:
            if hasattr(author, "name"):
                name = _norm(author.name)
                already = getattr(author, "is_corresponding", None)
            else:
                name = _norm(author.get("name", ""))
                already = author.get("is_corresponding")
            if already:
                continue
            if not name:
                continue
            surname, _initial = _person_key(name)
            # Match if (a) exact-string match, (b) NBSP-normalized exact
            # match, (c) comma-order aware person-key match, or (d) a
            # surname-only fallback only when that surname is unique among
            # parsed authors. The previous unconditional surname match
            # overmarked same-surname coauthors (e.g. "Anders Wahlin" and
            # "Björn E. Wahlin") when only one was the visible CA.
            hit = (
                name in ca_names
                or _norm_name(name) in ca_norms
                or _person_key(name) in ca_keys
                or (
                    surname in ca_surnames
                    and parsed_surname_counts.get(surname, 0) == 1
                )
            )
            if hit:
                if hasattr(author, "is_corresponding"):
                    author.is_corresponding = True
                else:
                    author["is_corresponding"] = True

        return authors

    def _mark_corresponding_author(self, authors):
        """Mark corresponding author based on 'Correspondence to' section."""
        if not authors:
            return authors

        corr_name = self._get_correspondence_name()
        if not corr_name:
            return authors

        # Normalize for comparison
        corr_name_lower = corr_name.lower().strip()
        corr_name_parts = set(corr_name_lower.replace(',', ' ').split())

        for author in authors:
            # Handle both dict and dataclass
            if hasattr(author, 'name'):
                author_name = author.name
            else:
                author_name = author.get('name', '')

            author_name_lower = author_name.lower().strip()
            author_name_parts = set(author_name_lower.replace(',', ' ').split())

            # Check if names match (at least 2 parts in common, or exact match)
            common_parts = corr_name_parts & author_name_parts
            if len(common_parts) >= 2 or corr_name_lower == author_name_lower:
                if hasattr(author, 'is_corresponding'):
                    author.is_corresponding = True
                else:
                    author['is_corresponding'] = True
                break

        return authors

    def parse_abstract(self):
        if abstract_soup := self.soup.find("section", class_="Abstract"):
            if abstract_heading := abstract_soup.find(
                    class_="Heading", string="Abstract"
            ):
                abstract_heading.decompose()

            for citation in abstract_soup.find_all("span",
                                                   class_="CitationRef"):
                citation.decompose()

            return abstract_soup.text.strip()

        # Modern SpringerLink template. The legacy lookup picked the FIRST
        # <p> only (``select_one``), which silently truncated multi-paragraph
        # abstracts to their opening paragraph — a common book-chapter
        # shape where the abstract is split into 4-6 enumerated paragraphs
        # under the same section. Iterate every <p> instead and join with
        # blank lines preserved between paragraphs.
        if abs_section := self.soup.select_one('section[data-title=Abstract]'):
            ps = abs_section.select('div[class*=c-article-section] p')
            if not ps:
                ps = abs_section.find_all('p')
            if ps:
                chunks = [p.get_text(" ", strip=True) for p in ps]
                chunks = [c for c in chunks if c]
                if chunks:
                    return "\n".join(chunks)

        # Book-chapter fallback (modern SpringerLink template).
        # Many SpringerLink book chapters have NO formal Abstract section
        # — only an "Introduction" section whose opening paragraph IS the
        # chapter abstract (and is what gold annotators captured). The
        # canonical example is ``978-1-4614-7612-2_16-1``: no
        # ``section.Abstract``, no ``section[data-title=Abstract]``, but
        # ``section[data-title=Introduction]`` carries the 978-char gold
        # text. Use Introduction's first <p> only when no Abstract section
        # was found; journal articles always carry a real Abstract so this
        # branch never fires for them.
        if intro_section := self.soup.select_one('section[data-title=Introduction]'):
            first_p = intro_section.find('p')
            if first_p:
                text = first_p.get_text(" ", strip=True)
                if text:
                    return text

        # Legacy SpringerLink template (pre-2018 reference works / older
        # book chapters). DOM shape is ``<section class="Section1">`` with
        # ``<h2 class="Heading">Introduction</h2>`` followed by the
        # chapter intro paragraph. Canonical example:
        # ``978-3-030-30018-0_1052`` (Encyclopedia of Global Archaeology).
        # Scan the first few ``Section1`` sections, take the first whose
        # ``<h2>`` text is Introduction (or Abstract / Summary, which the
        # legacy template also uses), and return its first <p>.
        for sec in self.soup.select('section.Section1, section[class*=Section1]')[:5]:
            h2 = sec.find('h2')
            if not h2:
                continue
            head = (h2.get_text(" ", strip=True) or "").lower()
            if head in ('introduction', 'abstract', 'summary'):
                first_p = sec.find('p')
                if first_p:
                    text = first_p.get_text(" ", strip=True)
                    if text:
                        return text

        if text := self._parse_springer_materials_abstract():
            return text

        if text := self._parse_reference_entry_definition():
            return text

        # Legacy/older SpringerLink book-chapter pages (and many encyclopedia
        # entries) emit no JSON-LD ``description``, no ``section.Abstract``,
        # no ``section[data-title=Abstract|Introduction]``, and no
        # ``section.Section1`` with an Introduction/Abstract/Summary heading.
        # The chapter abstract on those pages lives only in the
        # ``og:description`` / ``<meta name="description">`` tags (Springer
        # renders them server-side from the same source the gold annotators
        # used). Use the longer of the two as a last-resort fallback when
        # every DOM section probe came up empty. Require >=80 chars so we
        # don't lock in a one-line catalog blurb.
        meta_texts = []
        og = self.soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            meta_texts.append(og["content"].strip())
        desc = self.soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            meta_texts.append(desc["content"].strip())
        meta_texts = [t for t in meta_texts if len(t) >= 80]
        if meta_texts:
            return max(meta_texts, key=len)

        return None

    def _parse_springer_materials_abstract(self):
        if not self._has_springer_materials_marker():
            return None
        root = self.soup.select_one("div.main-content")
        if root is None:
            return None
        text = re.sub(r"\s+", " ", root.get_text(" ", strip=True)).strip()
        match = re.search(
            r"\bAbstract\b\s+(.*?)(?:\s+Get Access\s+PDF"
            r"|\s+Impact of COVID-19 pandemic|\s+View PDF"
            r"|\s+Cite this page|\s+References?\s*\(|$)",
            text,
            flags=re.I,
        )
        if not match:
            return None
        abstract = match.group(1).strip()
        return abstract if len(abstract) >= 80 else None

    def _parse_reference_entry_definition(self):
        if not (
            self.domain_in_canonical_link("link.springer.com/referencework")
            or self.domain_in_meta_og_url("link.springer.com/referencework")
        ):
            return None
        for node in self.soup.select("div.c-article-section__content"):
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            text = re.sub(r"^n\s+", "", text)
            lower = text.lower()
            if len(text) < 30:
                continue
            if (
                "reprints and permissions" in lower
                or lower.startswith("authors and affiliations")
                or lower.startswith("editors and affiliations")
                or lower.startswith("cite this entry")
                or lower.startswith("© ")
            ):
                continue
            return text
        return None

    def _parse_nature_intro_summary(self):
        if not (
            self.domain_in_canonical_link("nature.com")
            or self.domain_in_meta_og_url("nature.com")
        ):
            return None
        for node in self.soup.select("div.c-article-section__content"):
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            lower = text.lower()
            if len(text) < 120:
                continue
            if (
                "reprints and permissions" in lower
                or lower.startswith("cite this article")
                or lower.startswith("credit:")
                or "download citation" in lower
            ):
                continue
            return text
        return None

    def _parse_missing_abstract_fallback(self):
        """Last-resort abstract recovery for pages with no existing abstract.

        This intentionally runs only when the normal JSON-LD / DOM / meta
        ladder found nothing. It covers older Springer/BMC pages whose
        abstract-like content is split under language-specific or structured
        headings, without overriding already-good abstract strings.
        """
        if text := self._parse_language_abstract_section():
            return text
        if text := self._parse_structured_abstract_sections():
            return text
        return self._parse_nature_intro_summary()

    @staticmethod
    def _section_heading(section):
        heading = section.find(["h1", "h2", "h3"])
        return (
            section.get("data-title")
            or (heading.get_text(" ", strip=True) if heading else "")
            or ""
        ).strip().lower()

    @staticmethod
    def _section_text(section):
        for bad in section.select("span.CitationRef, sup, .CitationRef"):
            bad.decompose()
        chunks = []
        nodes = section.find_all(["p", "li"])
        if not nodes:
            text = section.get_text(" ", strip=True)
            return text.strip() if text else None
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if text:
                chunks.append(text)
        return "\n".join(chunks).strip() or None

    def _parse_language_abstract_section(self):
        abstract_headings = {
            "zusammenfassung",
            "samenvatting",
            "résumé",
            "resume",
            "resumen",
            "riassunto",
        }
        for section in self.soup.select("section")[:12]:
            if self._section_heading(section) not in abstract_headings:
                continue
            text = self._section_text(section)
            if text and len(text) >= 80:
                return text
        return None

    def _parse_structured_abstract_sections(self):
        structured_headings = {
            "background",
            "objective",
            "objectives",
            "case presentation",
            "methods",
            "method",
            "results",
            "conclusion",
            "conclusions",
        }
        chunks = []
        for section in self.soup.select("section")[:12]:
            if self._section_heading(section) in structured_headings:
                text = self._section_text(section)
                if text:
                    chunks.append(text)
                continue
            if chunks:
                break
        if len(chunks) >= 2:
            return "\n".join(chunks)
        return None

    def parse_article_metadatas(self):
        metadatas = []
        for ld_json in self.soup.find_all("script",
                                          {"type": "application/ld+json"}):
            article_metadata = json.loads(ld_json.text)
            if 'mainEntity' in article_metadata:
                article_metadata = article_metadata['mainEntity']
            metadatas.append(article_metadata)
        return metadatas

    @staticmethod
    def parse_ld_json(metadatas):
        authors = []

        for article_metadata in metadatas:
            for author in article_metadata.get("author", []):
                if author.get("@type") == "Person":
                    name = author.get("name")
                    affiliations = []

                    json_affiliations = author.get("affiliation")
                    is_corresponding = True if author.get("email") else False
                    if isinstance(json_affiliations, str):
                        affiliations = [json_affiliations]
                    elif (
                            isinstance(json_affiliations, dict)
                            and "name" in json_affiliations
                    ):
                        affiliations = [
                            json_affiliations.get('address', {}).get('name') or
                            json_affiliations['name']]
                    elif isinstance(json_affiliations, list):
                        for json_affiliation in json_affiliations:
                            if (
                                    isinstance(json_affiliation, str)
                                    and json_affiliation not in affiliations
                            ):
                                affiliations.append(json_affiliation)
                            elif (
                                    isinstance(json_affiliation, dict)
                                    and "name" in json_affiliation
                            ):
                                if json_affiliation["name"] not in affiliations:
                                    affiliations.append(
                                        json_affiliation.get('address', {}).get(
                                            'name') or json_affiliation['name'])

                    authors.append(
                        AuthorAffiliations(
                            name=name,
                            affiliations=affiliations,
                            is_corresponding=is_corresponding,
                        )
                    )

        return authors

    def get_authors(self, try_editors=False):
        authors = []

        section_id = (
            "editorsandaffiliations" if try_editors else "authorsandaffiliations"
        )
        section = self.soup.find(id=section_id)

        if not section:
            return None

        author_itemprop = "editor" if try_editors else "author"
        author_soup = section.findAll("li", {"itemprop": author_itemprop})

        for author in author_soup:
            ref_ids = []
            references = author.find("ul", {"data-role": "AuthorsIndexes"})
            if references:
                for reference in references:
                    ref_ids.append(int(reference.text))
            name = normalize("NFKD", author.span.text)
            authors.append(Author(name=name, aff_ids=ref_ids))

        return authors

    def get_affiliations(self, try_editors=False):
        affiliations = []

        section_id = (
            "editorsandaffiliations" if try_editors else "authorsandaffiliations"
        )
        section = self.soup.find(id=section_id)

        aff_soup = section.findAll("li", class_="affiliation")
        for aff in aff_soup:
            aff_id = int(aff["data-affiliation-highlight"][-1])

            # get affiliations
            spans = aff.findAll("span")
            affiliation_data = []
            for span in spans:
                if span.has_attr("itemprop") and span["itemprop"] != "address":
                    affiliation_data.append(span.text)

            affiliation = ", ".join(affiliation_data)

            affiliations.append(
                Affiliation(aff_id=aff_id, organization=affiliation))

        return affiliations

    test_cases = [
        {
            "doi": "10.1007/978-0-387-39343-8_21",
            "result": {
                "authors": [
                    {
                        "name": "Pascal Boileau MD",
                        "affiliations": [
                            "Professor,        Orthopaedic Surgery and Sports Traumatology, University of Nice-Sophia Antipolis, L’Archet 2 Hospital, Nice, 06200, France"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Christopher R. Chuinard MD, MPH",
                        "affiliations": [],
                        "is_corresponding": None,
                    },
                ],
                "abstract": "The tendon of the long head of the biceps (LHB) is a frequent source of pain in the shoulder and is subject to numerous pathologies.1\u20133 Treatment of pathology of the LHB involves resection of the intra-articular portion with a simple tenotomy or a tenodesis. Tenodesis of the LHB, with or without a rotator cuff repair, is an intervention known to reliably and effectively reduce the pain.4,5 We were not satisfied with the results obtained with other techniques. Because of our experience with the use of interference screw for surgery of the anterior cruciate ligament (ACL), we developed a technique for tenodesis of the biceps utilizing a bioresorbable interference screw.6,7\nKeywordsAnterior Cruciate LigamentRotator CuffBone TunnelInterference ScrewRotator Cuff RepairThese keywords were added by machine and not by the authors. This process is experimental and the keywords may be updated as the learning algorithm improves.",
            },
        },
        {
            "doi": "10.1007/0-306-48581-8_22",
            "result": {
                "authors": [
                    {
                        "name": "L. Michael Ascher",
                        "affiliations": [
                            "Department of Psychology, Philadelphia College of Osteopathic Medicine, Philadelphia"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Christina Esposito",
                        "affiliations": [
                            "Department of Psychology, Philadelphia College of Osteopathic Medicine, Philadelphia"
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": None,
            },
        },
        {
            "doi": "10.1007/0-306-48688-1_15",
            "result": {
                "authors": [
                    {
                        "name": "Ping Zhang",
                        "affiliations": [
                            "Department of Medicine, Section of Pulmonary and Critical Care Medicine, and Alcohol Research Center, Louisiana State University Health Sciences Center, New Orleans, LA, 70112"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Gregory J. Bagby",
                        "affiliations": [
                            "Department of Medicine, Section of Pulmonary and Critical Care Medicine, Department of Physiology, and Alcohol Research Center, Louisiana State University Health Sciences Center, New Orleans, LA, 70112"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Jay K. Kolls",
                        "affiliations": [
                            "Department of Medicine, Section of Pulmonary and Critical Care Medicine, Alcohol Research Center and Gene Therapy Programs, Louisiana State University Health Sciences Center, New Orleans, LA, 70112"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Lee J. Quinton",
                        "affiliations": [
                            "Department of Physiology and Alcohol Research Center, Louisiana State University Health Sciences Center, New Orleans, LA, 70112"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Steve Nelson",
                        "affiliations": [
                            "Department of Medicine, Section of Pulmonary and Critical Care Medicine, Department of Physiology, and Alcohol Research Center, Louisiana State University Health Sciences Center, New Orleans, LA, 70112"
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": None,
            },
        },
        {
            "doi": "10.1007/0-306-48581-8_7",
            "result": {
                "authors": [
                    {
                        "name": "Christine Bowman Edmondson",
                        "affiliations": [],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Daniel Joseph Cahill",
                        "affiliations": [
                            "Department of Psychology, California State University, Fresno, Fresno, California"
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": None,
            },
        },
        {
            "doi": "10.3758/s13414-014-0792-2",
            "result": {
                "authors": [
                    {
                        "name": "Scharenborg, Odette",
                        "affiliations": ["Radboud University Nijmegen"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Weber, Andrea",
                        "affiliations": [
                            "Max Planck Institute for Psycholinguistics",
                            "Radboud University Nijmegen",
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Janse, Esther",
                        "affiliations": [
                            "Radboud University Nijmegen",
                            "Max Planck Institute for Psycholinguistics",
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": "This study investigates two variables that may modify lexically guided perceptual learning: individual hearing sensitivity and attentional abilities. Older Dutch listeners (aged 60+ years, varying from good hearing to mild-to-moderate high-frequency hearing loss) were tested on a lexically guided perceptual learning task using the contrast [f]-[s]. This contrast mainly differentiates between the two consonants in the higher frequencies, and thus is supposedly challenging for listeners with hearing loss. The analyses showed that older listeners generally engage in lexically guided perceptual learning. Hearing loss and selective attention did not modify perceptual learning in our participant sample, while attention-switching control did: listeners with poorer attention-switching control showed a stronger perceptual learning effect. We postulate that listeners with better attention-switching control may, in general, rely more strongly on bottom-up acoustic information compared to listeners with poorer attention-switching control, making them in turn less susceptible to lexically guided perceptual learning. Our results, moreover, clearly show that lexically guided perceptual learning is not lost when acoustic processing is less accurate.",
            },
        },
        {
            "doi": "10.1038/s41417-021-00297-6",
            "result": {
                "authors": [
                    {
                        "name": "Hong, Yanni",
                        "affiliations": [
                            "Quanzhou First Hospital Affiliated Fujian Medical University"
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Li, Xiaofeng",
                        "affiliations": [
                            "Quanzhou First Hospital Affiliated Fujian Medical University"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Zhu, Jinfeng",
                        "affiliations": [
                            "Quanzhou First Hospital Affiliated Fujian Medical University"
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "Non-small cell lung cancer (NSCLC) is a prevalent cancer with unfavorable prognosis. Over the past decade accumulating studies have reported an involvement of lysine-specific histone demethylase 1 (LSD1) in NSCLC development. Here, we aimed to explore whether LSD1 affects the metastasis of NSCLC by mediating Septin 6 (SEPT6) through the TGF-β1 pathway. RT-qPCR was used to determine LSD1 and SEPT6 expression in NSCLC tissues and cells. Interactions between LSD1, SEPT6, and TGF-β1 were detected using lentivirus-mediated silencing of LSD1 and overexpression of SEPT6. The role of LSD1 and SEPT6 in mediating the biological behavior of NSCLC cells was determined using the EdU proliferation assay, Transwell assay, and flow cytometry. Thereafter, transplanted cell tumors into nude mice were used to explore the in vivo effects of LSD1 and SEPT6 on metastasis of NSCLC. LSD1 and SEPT6 were overexpressed in NSCLC tissue and cell samples. LSD1 could demethylate the promoter of the SEPT6 to positively regulate SEPT6 expression. LSD1 promoted proliferation, migration, and invasion, while suppressing the apoptosis of NSCLC cells by increasing SEPT6 expression. LSD1-mediated SEPT6 accelerated in vivo NSCLC metastasis through the TGF-β1/Smad pathway. Collectively, LSD1 demethylates SEPT6 promoter to upregulate SEPT6, which activates TGF-β1 pathway, thereby promoting metastasis of NSCLC.",
            },
        },
        {
            "doi": "10.1038/s41416-020-01139-2",
            "result": {
                "authors": [
                    {
                        "name": "Miligy, Islam M.",
                        "affiliations": ["The University of Nottingham"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Toss, Michael S.",
                        "affiliations": ["The University of Nottingham"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Shiino, Sho",
                        "affiliations": ["The University of Nottingham"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Oni, Georgette",
                        "affiliations": [
                            "Nottingham University Hospitals NHS Trust"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Syed, Binafsha M.",
                        "affiliations": [
                            "Liaquat University of Medical & Health Sciences"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Khout, Hazem",
                        "affiliations": [
                            "Nottingham University Hospitals NHS Trust"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Tan, Qing Ting",
                        "affiliations": [
                            "Nottingham University Hospitals NHS Trust"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Green, Andrew R.",
                        "affiliations": ["The University of Nottingham"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Macmillan, R. Douglas",
                        "affiliations": [
                            "Nottingham University Hospitals NHS Trust"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Robertson, John F. R.",
                        "affiliations": [
                            "University of Nottingham Royal Derby Hospital"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Rakha, Emad A.",
                        "affiliations": ["The University of Nottingham"],
                        "is_corresponding": None,
                    },
                ],
                "abstract": None,
            },
        },
        {
            "doi": "10.1007/978-3-030-50899-9",
            "result": {
                "authors": [
                    {
                        "name": "Cemal Cingi",
                        "affiliations": [
                            "Department of Otolaryngology, Eskisehir Osmangazi University, Eskisehir, Turkey"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Nuray Bayar Muluk",
                        "affiliations": [
                            "Otolaryngology Department, Kırıkkale University, Faculty Medicine, Kirikkale, Turkey"
                        ],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Glenis K Scadding",
                        "affiliations": [
                            "Royal National ENT Hospital, London, UK"],
                        "is_corresponding": None,
                    },
                    {
                        "name": "Ranko Mladina",
                        "affiliations": [
                            "Croatian Academy of Medical Sciences, Zagreb, Croatia"
                        ],
                        "is_corresponding": None,
                    },
                ],
                "abstract": None,
            },
        },
    ]
