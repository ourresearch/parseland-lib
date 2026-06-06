import re

from bs4 import BeautifulSoup, Tag

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import is_h_tag


class ElsevierBV(PublisherParser):
    parser_name = "Elsevier BV"

    def is_publisher_specific_parser(self):
        # Original signal: the OneTrust cookie consent script that runs on
        # modern ScienceDirect pages. Legacy /abs/ pages (pre-2000s reprints,
        # older Cell Press supplements, conference abstracts) omit this
        # script but ARE Elsevier — the canonical link points to
        # sciencedirect.com. Accept either signal.
        if self.domain_in_canonical_link("papers.ssrn.com"):
            return False
        return bool(
            self.soup.find(
                "script", {"src": "https://cdn.cookielaw.org/scripttemplates/otSDKStub.js"}
            )
            or self.domain_in_canonical_link("sciencedirect.com")
        )

    def authors_found(self):
        # Legacy ScienceDirect template uses <li class="author">.
        # Modern React-based ScienceDirect (post-2019 redesign) uses
        # <div class="author-group">. Older / supplement / legacy pages
        # (pre-2000s reprints, conference abstracts, journal supplements)
        # have neither but DO carry the Highwire/Google Scholar
        # <meta name="citation_author"> tags — fall back to those so the
        # dispatcher routes the page through ElsevierBV instead of the
        # generic fallback (which loses Elsevier-specific abstract /
        # affiliation handling). Match any of the four signals.
        return bool(
            self.soup.findAll("li", class_="author")
            or self.soup.find("div", class_="author-group")
            or self.soup.find("meta", attrs={"name": "citation_author"})
            or self.soup.find("a", class_="author-name")
        )

    def _parse_modern_author_group(self):
        """Extract authors from the modern <div class="author-group"> layout.

        Markup shape (modern ScienceDirect, post-2019 React template):

            <div class="author-group" id="author-group">
              <button data-xocs-content-type="author">    (or <a class="anchor">)
                <span class="given-name">First</span>
                <span class="text surname">Last</span>
                <span class="author-ref"><sup>a</sup></span>
                <svg class="icon icon-person ..." title="Correspondence author icon">
                <svg class="icon icon-envelope ..." title="Author email ...">
              </button>
              ...
            </div>

        Affiliations live in <dl class="affiliation"> blocks elsewhere on the
        page; the <sup> letter in author-ref maps to the matching <sup> in
        <dl><dt><sup>a</sup></dt><dd>institution</dd></dl>.
        """
        results = []
        # Some ScienceDirect pages (older Phys Lett B reprints, book chapters
        # from the Reference Module series, etc.) wrap EACH author in a
        # separate <div class="author-group"> sibling rather than collecting
        # them all in a single container. find() returned only the first
        # author in those cases — collect them all.
        author_groups = self.soup.find_all("div", class_="author-group")
        if not author_groups:
            return results

        # Affiliations live in <dl class="affiliation"> blocks. Two layouts:
        #   (1) Labeled: <dt>a</dt><dd>institution</dd>. Authors point at the
        #       letter via <span class="author-ref"><sup>a</sup></span>.
        #   (2) Unlabeled: <dt></dt><dd>institution</dd>. There's typically one
        #       affiliation shared by every author (e.g. clpl.2024.100067).
        aff_map = {}             # letter -> text (labeled case)
        unlabeled_affs = []      # texts that apply to all authors (unlabeled)
        for dl in self.soup.find_all("dl", class_="affiliation"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if not dd:
                continue
            text = dd.get_text(" ", strip=True)
            label = dt.get_text(strip=True) if dt else ""
            if label:
                aff_map[label] = text
            else:
                unlabeled_affs.append(text)

        # Each author block contains a span.surname. The enclosing element is
        # either <a class="anchor"> (e.g. mee.2007.12.032) or <button> (e.g.
        # clpl.2024.100067). Walking up from each surname gives us the right
        # author container regardless of layout. Note: data-xocs-content-type
        # ="author" is unreliable — it sometimes appears only on the
        # "show all authors" toggle button.
        seen = set()
        author_tags = []
        for ag in author_groups:
            for s in ag.find_all("span", class_="surname"):
                t = s.find_parent(["button", "a"])
                if t is not None and id(t) not in seen:
                    seen.add(id(t))
                    author_tags.append(t)

        sibling_corresponding_tag_ids = self._modern_sibling_corresponding_tag_ids(
            author_groups
        )

        for tag in author_tags:
            surname_el = tag.find("span", class_="surname")
            if not surname_el:
                continue
            given_el = tag.find("span", class_="given-name")
            name_parts = []
            if given_el:
                name_parts.append(given_el.get_text(strip=True))
            name_parts.append(surname_el.get_text(strip=True))
            name = " ".join(p for p in name_parts if p).strip()
            if not name:
                continue

            # Corresponding-author detection: the "Correspondence author icon"
            # is an SVG with class containing "icon-person" (in this template,
            # the person icon means corresponding, not just "author"). The
            # envelope icon also appears for corresponding-only on most pages.
            is_corresponding = False
            if id(tag) in sibling_corresponding_tag_ids:
                is_corresponding = True
            elif self._has_corresponding_author_icon(tag):
                is_corresponding = True

            # Affiliation letter refs (e.g. <sup>a</sup>, <sup>b</sup>). When
            # the page has labeled <dl> blocks, each author cross-references
            # one or more letters. When labels are absent (single shared
            # affiliation case), the author has no author-ref spans — fall
            # back to all unlabeled affiliations.
            affiliations = []
            for ref in tag.find_all("span", class_="author-ref"):
                letter = ref.get_text(strip=True)
                if letter and letter in aff_map and aff_map[letter] not in affiliations:
                    affiliations.append(aff_map[letter])
            if not affiliations and unlabeled_affs:
                for u in unlabeled_affs:
                    if u not in affiliations:
                        affiliations.append(u)

            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )

        # JSON enrichment from window.__PRELOADED_STATE__. ScienceDirect
        # embeds the full structured author + affiliation + correspondence
        # data as JSON in a <script> tag. We use it as a fallback when the
        # DOM signal is missing — corresponding flags and affiliations both
        # frequently live only in the JSON on older or simpler page layouts.
        json_data = self._authors_data_from_preloaded_state()
        if json_data:
            by_surname = json_data.get("by_surname", {})
            for r in results:
                surname_tail = (r.name or "").rstrip().rsplit(" ", 1)[-1]
                info = by_surname.get(surname_tail)
                if not info:
                    continue
                if info.get("is_corresponding") and not r.is_corresponding:
                    r.is_corresponding = True
                if not r.affiliations and info.get("affiliations"):
                    r.affiliations = list(info["affiliations"])

        # citation_author_email meta enrichment. On many modern ScienceDirect
        # pages the icon-person SVG marker is shown next to only ONE
        # corresponding author even when gold flags multiple — but the page's
        # <meta name="citation_author_email"> tags always sit adjacent to
        # every CA's citation_author meta. Use those as an additive signal
        # (only ever turns CA on, never off) so we don't regress the icon
        # path.
        email_ca_map = self._citation_author_email_map()
        if email_ca_map:
            for r in results:
                if r.is_corresponding or not r.name:
                    continue
                surname = r.name.rsplit(" ", 1)[-1]
                if email_ca_map.get(r.name) or email_ca_map.get(surname):
                    r.is_corresponding = True

        return results

    def _modern_sibling_corresponding_tag_ids(self, author_groups):
        """Map modern Elsevier icon-only sibling buttons to the preceding author.

        ScienceDirect often renders the author name as one ``button``/``a`` and
        puts the explicit "Correspondence author icon" in a separate icon-only
        sibling immediately after that name. The existing in-tag SVG check
        misses those. Keep this conservative: only explicit correspondence
        person icons count, and the signal attaches only to the closest
        preceding author before the next surname-bearing author tag.
        """
        corresponding_ids = set()
        for ag in author_groups:
            previous_author_tag = None
            for child in ag.children:
                if not isinstance(child, Tag):
                    continue
                if child.find("span", class_="surname"):
                    previous_author_tag = child
                    continue
                if previous_author_tag is not None and self._has_corresponding_author_icon(child):
                    corresponding_ids.add(id(previous_author_tag))
        return corresponding_ids

    @staticmethod
    def _has_corresponding_author_icon(tag) -> bool:
        for svg in tag.find_all("svg"):
            cls = svg.get("class", []) or []
            title = (svg.get("title") or "") + " " + (svg.get("aria-label") or "")
            if any("icon-person" in c for c in cls):
                return True
            if "correspond" in title.lower():
                return True
        return False

    def _authors_data_from_preloaded_state(self):
        """Pull structured author data from window.__PRELOADED_STATE__.

        Returns ``{"by_surname": {surname: {"is_corresponding": bool,
        "affiliations": list[str]}}}`` or None if the JSON blob is missing
        or shaped unexpectedly. Defensive — never raises.

        ScienceDirect's application/json and __PRELOADED_STATE__ shapes both
        expose this relevant slice:

            authors:
              content: [{$$: [{#name: "author", $$: [
                {#name: "given-name", _: "..."},
                {#name: "surname", _: "..."},
                {#name: "cross-ref", $: {refid: "aff1"}},
                {#name: "cross-ref", $: {refid: "cor1"}},
              ]}]}]
              affiliations: {aff1: {$$: [{#name: "textfn", _: "..."}]}, ...}
              correspondences: {cor1: {...}, ...}
        """
        try:
            import json
            import re
            data = None

            # Keep the legacy ScienceDirect preloaded-state blob as the only
            # structured author-affiliation source for now. A broad
            # script[type=application/json] fallback improved one focused
            # slice, but regressed the full 10K current-Goldie gate because
            # those payloads can carry mismatched affiliation/correspondence
            # refs. Re-enable only behind DOI-grounded evidence.
            for script in self.soup.find_all("script"):
                text = script.string or script.text or ""
                if "__PRELOADED_STATE__" not in text:
                    continue
                m = re.search(r"__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?\s*$", text, re.DOTALL)
                if not m:
                    continue
                data = json.loads(m.group(1))
                break
            if not isinstance(data, dict):
                return None

            authors_node = data.get("authors") or {}
            content = authors_node.get("content")
            if not isinstance(content, list):
                return None

            # Build affiliation refid -> text map first
            aff_lookup = {}
            for refid, blob in (authors_node.get("affiliations") or {}).items():
                if not isinstance(blob, dict):
                    continue
                # textfn child has the human-readable text
                textfn = None
                for child in blob.get("$$") or []:
                    if isinstance(child, dict) and child.get("#name") == "textfn":
                        textfn = (child.get("_") or "").strip()
                        break
                if textfn:
                    aff_lookup[refid] = textfn

            by_surname = {}
            for author_group in content:
                if not isinstance(author_group, dict):
                    continue
                for entry in author_group.get("$$") or []:
                    if not isinstance(entry, dict) or entry.get("#name") != "author":
                        continue
                    surname = None
                    is_corresp = False
                    refids = []
                    for child in entry.get("$$") or []:
                        if not isinstance(child, dict):
                            continue
                        name = child.get("#name")
                        if name == "surname":
                            surname = (child.get("_") or "").strip()
                        elif name == "cross-ref":
                            refid = (child.get("$") or {}).get("refid", "")
                            # Some pages (e.g. 0021-9673(93)80418-8) emit
                            # refid="COR1" in uppercase. Match case-insensitively.
                            if refid.lower().startswith("cor"):
                                is_corresp = True
                            else:
                                refids.append(refid)
                    if not surname:
                        continue
                    affs = []
                    for rid in refids:
                        if rid in aff_lookup and aff_lookup[rid] not in affs:
                            affs.append(aff_lookup[rid])
                    # Single-shared-affiliation fallback: if the author has no
                    # explicit refs and there's exactly one affiliation in the
                    # JSON, attribute it to every author (mirrors how the page
                    # actually renders these single-aff layouts).
                    if not affs and len(aff_lookup) == 1:
                        affs = list(aff_lookup.values())
                    by_surname[surname] = {
                        "is_corresponding": is_corresp,
                        "affiliations": affs,
                    }
            return {"by_surname": by_surname}
        except Exception:
            return None

    def parse_abstract(self):

        if abs_header := self.soup.find(lambda tag: is_h_tag(tag) and tag.text.lower().strip() == 'abstract'):
            if abs_tag := abs_header.find_next_sibling('div', class_='section-paragraph'):
                return abs_tag.text
        if abs_tag := self.soup.select_one('h2[data-left-hand-nav="Summary"] + div.section-paragraph'):
            return abs_tag.text

        abs_text = ''
        for i, tag in enumerate(self.soup.select('div[class*=article__sections] div.section-paragraph')):
            if tag.figure:
                tag.figure.decompose()
            if i != 0:
                abs_text += '\n'
            prev_sibling = tag.find_previous_sibling()
            if prev_sibling and is_h_tag(prev_sibling) and 'introduction' in prev_sibling.text.lower():
                break
            abs_text += tag.text
            if prev_sibling and is_h_tag(prev_sibling) and any([word in prev_sibling.text.lower() for word in {'funding', 'conclusion'}]):
                break
            # if prev_sibling and is_h_tag(prev_sibling) and 'funding' in prev_sibling.text.lower():
            #     break
            # abs_text += tag.text
            # if prev_sibling and is_h_tag(prev_sibling) and 'conclusion' in prev_sibling.text.lower():
            #     break

        if abs_text:
            return abs_text

        # Modern ScienceDirect template fallback: the abstract lives in
        # <div class="abstract author">. Pages also often emit sibling
        # blocks the gold abstract is NOT — Highlights and Graphical
        # abstracts. The shape is:
        #
        #   <div class="abstracts">
        #     <div class="abstract author-highlights">
        #       <h2>Highlights</h2>
        #       <div class="abstract author"> bullets </div>  ← naive select_one wins here
        #     </div>
        #     <div class="abstract author"> <h2>Abstract</h2> body </div>  ← the one we want
        #     <div class="abstract graphical"> Graphical abstract... </div>
        #   </div>
        #
        # `select_one("div.abstract.author")` matches the FIRST occurrence
        # in document order, which is the nested div inside the highlights
        # wrapper — yielding the bullet list instead of the abstract body.
        # Filter to top-level `div.abstract.author` blocks (no
        # `author-highlights` or `graphical` ancestor) and prefer one whose
        # leading <h2> reads "Abstract" or "Summary".
        #
        # Older Elsevier pages (e.g. j.vetpar.2003) and modern ones
        # (e.g. j.buildenv.2024, j.yofte.2019) share this markup, so the
        # selector covers both. We strip a leading "Abstract" header word
        # that the publisher template prepends to the text node.
        candidates = []
        # Prefer walking the .abstracts container's direct-child layout
        # when present: that's where ScienceDirect lays out the disjoint
        # blocks (Highlights, Abstract, Graphical abstract). When the
        # container is absent (older pages), fall back to a global scan
        # with the same filters applied.
        abstracts_root = self.soup.select_one(".abstracts")
        if abstracts_root is not None:
            scope = abstracts_root.find_all(
                "div",
                class_=lambda c: c and "abstract" in c,
                recursive=True,
            )
        else:
            scope = self.soup.select("div.abstract.author")

        for div in scope:
            cls = set(div.get("class") or [])
            # The selector must require both "abstract" and "author" classes
            # (graphical / author-highlights are the rejects).
            if "abstract" not in cls or "author" not in cls:
                continue
            # Skip the highlights wrapper itself when scoping the whole
            # .abstracts container.
            if "author-highlights" in cls or "graphical" in cls:
                continue
            # Skip nested div inside the Highlights wrapper. The wrapper has
            # the `author-highlights` class; its nested abstract.author child
            # carries the bullets.
            bad_ancestor = div.find_parent(
                "div",
                class_=lambda c: c
                and any(token in c for token in ("author-highlights", "graphical")),
            )
            if bad_ancestor is not None:
                continue
            candidates.append(div)

        # Take the first surviving block. Don't preference English "Abstract"
        # h2 over other languages — bilingual pages (e.g.
        # 10.1016/s0294-1260(02)00149-8) emit the primary-language
        # block first (Résumé) and the translated block second; gold
        # captures the primary block. Skipping highlights/graphical and
        # taking the first match preserves that ordering.
        chosen = candidates[0] if candidates else None

        if chosen is not None:
            text = chosen.get_text(" ", strip=True)
            if text:
                # Strip the leading "Abstract" / "Summary" header word
                # that the template injects in front of the body text.
                for prefix in ("Abstract", "Summary"):
                    if text.startswith(prefix):
                        text = text[len(prefix):].lstrip()
                        break
                return text

        return abs_text

    def parse_short_citation_abstract_meta(self):
        """Elsevier-only fallback for short Highwire citation abstracts.

        The generic meta fallback intentionally requires >200 characters to
        avoid accepting page descriptions. Some legacy ScienceDirect pages
        carry the true abstract only in ``citation_abstract`` and the value can
        be much shorter, sometimes with a small HTML fragment embedded in the
        meta content.
        """
        for meta_property_name in ("name", "property"):
            meta_tag = self.soup.find(
                "meta",
                {meta_property_name: re.compile("^citation_abstract$", re.I)},
            )
            if meta_tag is None:
                continue
            text = meta_tag.get("content", "").strip()
            if not text:
                continue
            if "<" in text and ">" in text:
                text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            text = re.sub(r"^(abstract|summary)[:.]?\s*", "", text, flags=re.I).strip()
            if (
                len(text) >= 40
                and not text.endswith("...")
                and not text.endswith("…")
                and not text.startswith("http")
            ):
                return text
        return None

    def parse(self):
        author_results = []
        author_soup = self.soup.findAll("li", class_="author")
        for author in author_soup:
            name_soup = author.find("a", class_="loa__item__name")
            if name_soup:
                name = name_soup.text
            else:
                continue
            is_corresponding = False
            if correspondence := author.find(
                "span", class_="article-header__info__group__label"):
                if correspondence.text.lower().strip() == 'correspondence':
                    is_corresponding = True
            if author.select_one('.icon-gizmo-person'):
                is_corresponding = True
            elif author.select_one('.article-header__info__email'):
                is_corresponding = True

            affiliations = []
            # method 1
            info_groups = author.findAll("div", class_="article-header__info__group")
            for group in info_groups:
                header = group.find("span", class_="article-header__info__group__label")
                for sup in group.find_all("sup"):
                    sup.unwrap()  # remove sup tags
                    group.smooth()  # join navigable strings
                if header.text == "Affiliations":
                    affiliation_soup = group.find(
                        "div", class_="article-header__info__group__body"
                    )

                    if affiliation_soup:
                        for aff in affiliation_soup.stripped_strings:
                            affiliations.append(aff.strip())

            # method 2
            affiliation_soup = author.find(
                "div", class_="article-header__info__group__body"
            )
            if affiliation_soup and not info_groups:
                for aff in affiliation_soup.stripped_strings:
                    affiliations.append(aff.strip())
            if not affiliations:
                affiliation_soup = author.select('div.affiliation')
                affiliations = [aff.text.strip() for aff in affiliation_soup]
            author_results.append(
                AuthorAffiliations(
                    name=name.strip(),
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )

        # If the legacy <li class="author"> path found nothing, try the modern
        # <div class="author-group"> layout. This catches the React-based
        # ScienceDirect template that all 13 Elsevier gold rows use.
        if not author_results:
            author_results = self._parse_modern_author_group()

        # Final fallback for older / supplement / legacy pages where neither
        # <li class="author"> nor <div class="author-group"> exists but the
        # Highwire/Google Scholar <meta name="citation_author"> tags do.
        # Affiliations come from <meta name="citation_author_institution">
        # which immediately follow each author meta in document order.
        # is_corresponding is unknowable from meta tags alone (the spec
        # has no field for it); defaults to False.
        if not author_results:
            author_results = self._parse_citation_author_meta()
            # Cell Press / Elsevier journal portals (cell.com, ajconline.org,
            # ajo.com, americanjournalofsurgery.com, bjoms.com,
            # annalsthoracicsurgery.org, onlinejcf.com, ...) emit the author
            # names via <meta name="citation_author"> but omit
            # citation_author_institution. Per-author affiliations and the
            # corresponding-author flag live in the rendered DOM instead —
            # enrich the meta-based results from those nodes when shapes line
            # up. Skipped when the meta path already produced affiliations
            # (institution metas are authoritative when present).
            self._enrich_from_core_author_blocks(author_results)

        return {
            "authors": author_results,
            "abstract": self.parse_abstract()
            or self.parse_short_citation_abstract_meta()
            or self.parse_abstract_meta_tags(),
        }

    def _enrich_from_core_author_blocks(self, results):
        """Cell Press / Elsevier journal portal enrichment.

        Pages on hosts like cell.com, ajconline.org, ajo.com,
        americanjournalofsurgery.com, bjoms.com, annalsthoracicsurgery.org,
        and onlinejcf.com render under a shared portal template that emits:

            <div class="core-author-affiliations">
              Affiliations &lt;institution text&gt;
            </div>

        — one per author, in the same document order as the
        <meta name="citation_author"> tags. The same template wraps the
        corresponding author in <span class="corresponding-author">. None of
        this surfaces through <meta name="citation_author_institution">, so
        the meta-only fallback leaves affiliations empty on these pages.

        Mutates ``results`` in place. Skipped when the meta path already
        produced affiliations (institution metas remain authoritative). Skipped
        when the count of core-author-affiliations blocks does not match the
        author count (defensive — never misalign).

        Never raises. Used by ``parse()`` only on the meta-fallback path.
        """
        if not results:
            return
        # Don't overwrite affiliations the meta path already populated.
        if any(r.affiliations for r in results):
            return

        aff_blocks = self.soup.find_all(
            "div", class_=lambda c: c and "core-author-affiliations" in c
        )
        if aff_blocks and len(aff_blocks) == len(results):
            for r, block in zip(results, aff_blocks):
                text = block.get_text(" ", strip=True)
                # Template prepends a literal "Affiliations" header word in
                # front of the body text — strip it. Whitespace collapse via
                # get_text(" ", strip=True) means we don't need to handle
                # newlines or nested children explicitly.
                if text.lower().startswith("affiliations"):
                    text = text[len("affiliations"):].lstrip()
                if text:
                    r.affiliations = [text]

        # Corresponding-author signal. The portal wraps the CA author block in
        # <span class="corresponding-author">; surname/given-name inside it
        # match one of the parsed names. Augments the email-meta CA signal
        # without ever clearing it (additive only).
        for span in self.soup.find_all(
            "span", class_=lambda c: c and "corresponding-author" in c
        ):
            ca_text = span.get_text(" ", strip=True)
            if not ca_text:
                continue
            for r in results:
                if r.is_corresponding or not r.name:
                    continue
                surname = r.name.rsplit(" ", 1)[-1]
                if surname and surname in ca_text:
                    r.is_corresponding = True
                    break

    def _parse_citation_author_meta(self):
        """Read <meta name="citation_author"> and follow with any
        <meta name="citation_author_institution"> tags that appear before
        the next author meta. Also detect corresponding-author flags from
        adjacent <meta name="citation_author_email"> tags — Highwire's
        convention is that an author with an email meta is a corresponding
        author (the email meta sits immediately after that author's
        citation_author meta in document order).

        Most academic publishers (including Elsevier on legacy and
        supplement pages) include these Google Scholar / Highwire metadata
        tags for indexing-service compatibility. When the structured DOM
        author markup is missing, the meta-tag list is still complete.

        We honor document order so that institution and email metas attach
        to the preceding author. If an institution/email meta appears
        before any author meta, it's dropped.
        """
        results = []
        metas = self.soup.find_all(
            "meta",
            attrs={
                "name": [
                    "citation_author",
                    "citation_author_institution",
                    "citation_author_email",
                ],
            },
        )
        current_name = None
        current_affs: list = []
        current_corresponding = False
        for m in metas:
            name = m.get("name")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if name == "citation_author":
                if current_name:
                    results.append(
                        AuthorAffiliations(
                            name=current_name,
                            affiliations=current_affs,
                            is_corresponding=current_corresponding,
                        )
                    )
                current_name = content
                current_affs = []
                current_corresponding = False
            elif name == "citation_author_institution":
                if current_name and content not in current_affs:
                    current_affs.append(content)
            elif name == "citation_author_email":
                if current_name:
                    current_corresponding = True
        if current_name:
            results.append(
                AuthorAffiliations(
                    name=current_name,
                    affiliations=current_affs,
                    is_corresponding=current_corresponding,
                )
            )
        return results

    def _citation_author_email_map(self):
        """Build a name→is_corresponding map from <meta name='citation_author'>
        + adjacent <meta name='citation_author_email'> tags.

        Returned dict maps both the full author name and its surname-tail
        to True when an email meta follows that author's name meta in
        document order. Used by ``_parse_modern_author_group`` to augment
        corresponding-author detection on modern pages whose DOM doesn't
        carry the icon-person SVG for every CA but whose meta tags do.
        """
        mapping: dict = {}
        metas = self.soup.find_all(
            "meta",
            attrs={"name": ["citation_author", "citation_author_email"]},
        )
        current_name = None
        for m in metas:
            name = m.get("name")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if name == "citation_author":
                current_name = content
            elif name == "citation_author_email" and current_name:
                mapping[current_name] = True
                surname = current_name.rsplit(" ", 1)[-1]
                if surname:
                    mapping[surname] = True
        return mapping

    # Per-DOI test cases. The single `jvs.2021.03.049` entry is the existing
    # canonical Elsevier test. Iter 1 of oxjob #202 (parseland-elsevier-iter1,
    # 2026-05-20) attempted to extend this with 11 snapshots from the human-goldie
    # gold standard but discovered that ElsevierBV.parse() directly returns 0
    # authors on many real Elsevier pages (e.g. 0021-9673, mee.2007.12.032,
    # 0021-9673(93)80418-8) because `authors_found()` returns False on those
    # markup variants — the live POST /parseland path routes those pages through
    # a generic citation_author-meta fallback parser instead. Encoding the
    # generic-parser output as ElsevierBV test_cases would be wrong.
    #
    # Snapshot fragment for the 13 gold rows is preserved at
    # `tests/fixtures/elsevier-test-cases-snapshot.py.fragment` for iter 2's
    # work on either expanding ElsevierBV's markup coverage or routing per-DOI
    # tests through the dispatcher.
    test_cases = [
        {
            "doi": "10.1016/j.jvs.2021.03.049",
            "result": {
                "authors": [
                    {
                        "name": "Jessica Rouan, MD",
                        "affiliations": [
                            "Department of Surgery, University of North Carolina at Chapel Hill, Chapel Hill, NC"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Gabriela Velazquez, MD",
                        "affiliations": [
                            "Department of Vascular and Endovascular Surgery, Wake Forest School of Medicine, Wake Forest, NC"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Julie Freischlag, MD",
                        "affiliations": [
                            "Department of Vascular and Endovascular Surgery, Wake Forest School of Medicine, Wake Forest, NC"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Melina R. Kibbe, MD",
                        "affiliations": [
                            "Department of Surgery, University of North Carolina at Chapel Hill, Chapel Hill, NC",
                            "Department of Biomedical Engineering, University of North Carolina at Chapel Hill, Chapel Hill, NC",
                        ],
                        "is_corresponding": True,
                    },
                ],
                "abstract": "<h2>Abstract</h2><p>Publication bias has been shown to exist in research across medical and surgical specialties. Bias can occur at any stage of the publication process and can be related to race, ethnicity, age, religion, sex, gender, or sexual orientation. Although some improvements have been made toward addressing this issue, bias still spans the publication process from authors and peer reviewers, to editorial board members and editors, with poor inclusion of women and underrepresented minorities throughout. The result of bias remaining unchecked is the publication of research that leaves out certain groups, is not applicable to all people, and can result in harm to some populations. We have highlighted the current landscape of publication bias and strived to demonstrate the importance of addressing it. We have also provided solutions for reducing bias at multiple stages throughout the publication process. Increasing diversity, equity, and inclusion throughout all aspects of the publication process, requiring diversity, equity, and inclusion statements in reports, and providing specific education and guidelines will ensure the identification and eradication of publication bias. By following these measures, we hope that publication bias will be eliminated, which will reduce further harm to certain populations and promote better, more effective research pertinent to all people.</p>",
            },
        },
    ]
