import re
from unicodedata import normalize

from bs4 import NavigableString

from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import is_h_tag, strip_prefix, strip_suffix


class Wiley(PublisherParser):
    parser_name = "wiley"

    def is_publisher_specific_parser(self):
        return self.domain_in_meta_og_url("onlinelibrary.wiley.com") or self.text_in_meta_og_site_name('Wiley Online Library')

    def authors_found(self):
        return self.soup.find("div", class_="loa-authors") or (
            self.is_publisher_specific_parser() and self._abstract_signal_found()
        )

    def _abstract_signal_found(self):
        if self.soup.select_one('section[class*="abstract"], div[class*="abstract"]'):
            return True
        if self.soup.select_one('meta[name="citation_abstract"]'):
            return True
        if self.soup.select_one('div.article__body p'):
            return True
        return bool(self.parse_abstract_meta_tags())

    def parse(self):
        return {"authors": self.get_authors(),
                "abstract": self.get_abstract()}

    def get_authors(self):
        results = []
        if author_soup := self.soup.find("div", class_="loa-authors"):
            authors = author_soup.findAll("span", class_="accordion__closed")
        else:
            authors = []
        # Wiley pages often list a per-author "Email this author" mailto as a
        # courtesy on every author, not as a corresponding-author marker. When
        # the page DOES surface structured CA metadata via a
        # <p class="author-type">Corresponding Author</p> tag on at least one
        # author, trust that exclusively — other authors' mailtos are courtesy
        # links and must be ignored. When NO author has the author-type tag
        # the page lacks structured CA metadata (older Wiley/Blackwell
        # templates) and mailto becomes the best per-author CA heuristic.
        def _has_author_type_ca(span):
            tag = span.find("p", class_="author-type")
            return bool(tag and "corresponding" in tag.text.lower())

        page_has_structured_ca = any(_has_author_type_ca(a) for a in authors)
        for author in authors:
            affiliations = []
            name = author.a.text
            aff_soup = author.findAll("p", class_=None)

            is_corresponding = False

            author_type = author.find("p", class_="author-type")
            if author_type and "corresponding" in author_type.text.lower():
                is_corresponding = True
            elif not page_has_structured_ca and author.select_one('a[href*=mailto]'):
                is_corresponding = True

            for aff in aff_soup:
                if "correspondence" in aff.text.lower() or "e-mail" in aff.text.lower():
                    is_corresponding = True

            for aff in aff_soup:
                if (
                    "correspond" in aff.text.lower()[:25]
                    or "address reprint" in aff.text.lower()[:40]
                    or "author deceased" in aff.text.lower()
                    or "e-mail:" in aff.text.lower()
                    or aff.text.lower().startswith("contribution")
                    or aff.text.lower().startswith("joint first authors")
                    or aff.text.lower().startswith("†joint")
                ) and len(aff_soup) > 1:
                    break
                aff_txt = aff.text.strip()
                aff_txt = strip_suffix('Direct inquiries.*', aff_txt)
                aff_txt = strip_prefix('Authors are with ', aff_txt)
                aff_txt = aff_txt.strip().split('Fax')[0].strip()
                affiliations.append(normalize("NFKD", aff_txt))

            # CAND3: bare-text fallback + author-jobTitle pickup.
            # Legacy Wiley/Blackwell pages (e.g. 10.1111/j.1540-6261.1970...)
            # place the affiliation as a bare text node inside
            # <div class="author-info">. Some such pages embed the job title
            # as <p class="author-jobTitle"> and the rest as a bare text node
            # that REPEATS the job title at its start ("Professor of
            # Economics, University of Missouri-St. Louis" alongside a
            # separate <p class="author-jobTitle">Professor of Economics</p>).
            # The bare text IS the canonical affiliation in gold annotation.
            # Strategy: when no <p class=None> affs, scan ALL direct
            # NavigableString children of author-info for any text >= 20
            # chars with a comma (institution+location signal), excluding
            # known UI strings.
            if not affiliations:
                info_div = author.find("div", class_="author-info")
                if info_div is not None:
                    for child in info_div.children:
                        if not isinstance(child, NavigableString):
                            continue
                        text = str(child).strip()
                        if len(text) < 20 or "," not in text:
                            continue
                        low = text.lower()
                        if low.startswith("search for more papers"):
                            continue
                        cleaned = text.rstrip(".").strip()
                        if cleaned:
                            affiliations.append(normalize("NFKD", cleaned))
                            break  # only take first matching text node

            results.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        self._mark_corresponding_from_header_block(results)
        return results

    def _mark_corresponding_from_header_block(self, results):
        """Older Wiley/Blackwell pages surface the corresponding-author name
        only inside ``<div class="article-header__correspondence-to">``, not
        inside the per-author span (no author-type heading, no mailto). Match
        an author whose first AND last name both appear in the block text and
        flag them. Additive only — never clears an existing CA flag.

        Tokens are punctuation-stripped before substring matching: parsed
        author names often carry initials like ``C.`` while the correspondence
        block strips the period (``C Elliott``). Failing to strip the trailing
        period on the parsed token means ``c.`` is searched inside ``c elliott``
        and the match fails. Example DOI: ``10.1111/j.1467-789x.2007.00418.x``.
        """
        block = self.soup.find("div", class_="article-header__correspondence-to")
        if not block:
            return
        block_text = block.get_text(separator=" ").lower()

        def _norm(tok: str) -> str:
            # Strip trailing punctuation that appears on initials/abbreviations.
            return tok.lower().strip(".,;:")

        for r in results:
            if r.is_corresponding:
                continue
            name = (r.name or "").strip()
            tokens = name.split()
            if len(tokens) < 2:
                continue
            first = _norm(tokens[0])
            last = _norm(tokens[-1])
            if first and last and first in block_text and last in block_text:
                r.is_corresponding = True

    def get_abstract(self):
        # Primary: h2/h3 "Abstract" or "Summary" heading -> next sibling text.
        if abs_headings := self.soup.find_all(
            lambda tag: is_h_tag(tag) and (tag.text.lower().strip() == 'abstract' or tag.text.lower() == 'summary')
        ):
            for abstract_heading in abs_headings:
                # if graphical abstract is the only abstract, then take it, otherwise try to find actual abstract
                if any(['graphical' in cls for cls in abstract_heading.get('class') or []]) and len(abs_headings) > 1:
                    continue
                if abstract_body := abstract_heading.find_next_sibling():
                    if (abstract := abstract_body.text.strip()) and len(abstract_body.text.strip()) > 100:
                        return abstract

        # Fallback 1: <section> or <div> whose class contains "abstract".
        # Modern Wiley pages use <section class="article-section__abstract">
        # containing one or more <p>; the section also wraps a header that
        # often emits trailing language codes (e.g. "Abstract" + "en"
        # adjacent in text). Grab only the <p> children to skip headers and
        # language tags. Excludes graphical and related-content variants.
        # Length gate is intentionally low (> 20 chars): the semantic
        # class name is the strong signal here, not the length. Book-chapter
        # pages on Wiley legitimately have very short "abstracts" — e.g.
        # `10.1002/chin.198608340` is just "Review: (74 refs.)" (17 chars),
        # `10.1002/9780470693551.ch43` is "This chapter contains section
        # titled: Introduction" (50 chars). A 100-char gate dropped them.
        for selector in ('section[class*="abstract"]', 'div[class*="abstract"]'):
            for el in self.soup.select(selector):
                cls = ' '.join(el.get('class') or []).lower()
                if 'graphical' in cls or 'related' in cls:
                    continue
                paragraphs = [p.text.strip() for p in el.find_all('p') if p.text.strip()]
                if not paragraphs:
                    continue
                text = '\n'.join(paragraphs).strip()
                # Length gate intentionally permissive: the semantic class
                # name IS the strong signal. 17 chars catches even
                # `10.1002/chin.198608340` ("Review: (74 refs.)"); empty
                # paragraphs were already filtered above.
                if len(text) >= 15:
                    return text

        # Fallback 2: standard meta-tag extraction (citation_abstract,
        # og:description, dc.description, description). Uses the base class
        # helper which already gates length > 200 and strips leading
        # "abstract:" prefixes.
        if meta_abs := self.parse_abstract_meta_tags():
            return meta_abs

        # Fallback 3: short `div.article__body` (editorial / journal-intro
        # template). Some older Wiley editorials and EPPO/journal-front-
        # matter pages have no Abstract heading, no
        # `section[class*=abstract]` markup, and no useful meta tag — the
        # entire intro IS the abstract and lives only in
        # `div.article__body p`. CANNOT be used unconditionally: on full
        # research articles it grabs intro + methods + results +
        # discussion + conclusions and produces multi-thousand-character
        # "abstracts" that fail the threshold match. Gate on paragraph
        # count: ≤ 5 paragraphs ≈ editorial-shape, > 5 ≈ full research
        # article — drop it. Examples that need this fallback:
        # 10.1002/jpln.202370065 (editorial, gold 792 chars),
        # 10.1002/uog.24515 (commentary, gold 1685 chars),
        # 10.1111/epp.12861 (panel decision note, gold 448 chars). Known
        # remaining miss: 10.1111/bjh.15726 (long editorial, 15 paragraphs,
        # gold 4832 chars) — the only regression vs iter-1 and accepted as
        # a trade-off for the FP-cleanup wins this fallback gate produces.
        if paragraphs := self.soup.select('div.article__body p'):
            if len(paragraphs) <= 5:
                text = '\n'.join(p.text for p in paragraphs).strip()
                if len(text) > 100:
                    return text

        return None

    test_cases = [
        {
            "doi": "10.1096/fba.2020-00145",
            "result": {
                "authors": [
                    {
                        "name": "Lia Tadesse Gebremedhin",
                        "affiliations": ["Minister of Health, Addis Ababa, Ethiopia"],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Tedla W. Giorgis",
                        "affiliations": [
                            "Advisor to the Minister, Ministry of Health, Addis Ababa, Ethiopia"
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Heran Gerba",
                        "affiliations": [
                            "Director-General, Ethiopian Food and Drug Administration, Addis Ababa, Ethiopia"
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": 'In Ethiopia, noncommunicable diseases (NCDs) represent 18.3% of premature mortality, consume 23% of the household expenditures, and cost 1.8% of the gross domestic product. Risk factors such as alcohol, khat, and cannabis use are on the rise and are correlated with a substantial portion of NCDs. Associated NCDs include depression, anxiety, hypertension, coronary heart disease, and myocardial infarction. The multi-faceted nature of mental health and substance abuse disorders require multi-dimensional interventions. The article draws upon participant observation and literature review to examine the policies, delivery models, and lessons learned from the Federal Ministry of Health (FMOH) experience in integrating Mental Health and Substance Abuse (MH/SA) services into primary care in Ethiopia. In 2019, FMOH developed national strategies for both NCDs and mental health to reach its population. Ethiopia integrated MH/SA services at all levels within the government sector, with an emphasis on primary health care. FMOH launched the Ethiopian Primary Health Care Clinical Guidelines, which includes the delivery of NCD services, to standardize the care given at the primary health care level. To date, the guidelines have been implemented by over 800 health centers and are expected to improve the quality of service and health outcomes. Existing primary care programs were expanded to include prevention, early detection, treatment, and rehabilitation for MH/SA. This included training and leveraging an array of health professionals, including traditional healers and those from faith-based institutions and community-based organizations. A total of 244 health centers completed training in the Mental Health Gap Action Programme (mhGAP). In 2020, 5,000 urban Health Extension Workers (HEWs) participated in refresher training, which includes mental health and NCDs. A similar curriculum for rural health workers is in development. Ethiopia\'s experience has many lessons learned about stakeholder buy-in, roles, training, logistics, and sustainability that are transferable to other countries. Lessons include that "buy-in" by leaders of public health care facilities requires consistent and persistent nurturing. Ensure the gradual and calibrated integration of MH/SA services so that the task-sharing will not be viewed as "task dumping." Supervision and mentorship of the newly trained is important for the delivery of quality care and acquisition of skills.',
            },
        },
        {
            "doi": "10.1002/ptr.6273",
            "result": {
                "authors": [
                    {
                        "name": "Chunyu Li",
                        "affiliations": [
                            "Department of Integrated Chinese Traditional and Western Medicine, International Medical School, Tianjin Medical University, Tianjin, China"
                        ],
                        "is_corresponding": True,
                    },
                    {
                        "name": "Qi Wang",
                        "affiliations": [
                            "Department of Oncology, Shanghai Pulmonary Hospital Affiliated Tongji University, Shanghai, China"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Shen Shen",
                        "affiliations": [
                            "Department of Integrated Chinese Traditional and Western Medicine, International Medical School, Tianjin Medical University, Tianjin, China"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Xiaolu Wei",
                        "affiliations": [
                            "Department of Integrated Chinese Traditional and Western Medicine, International Medical School, Tianjin Medical University, Tianjin, China"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Guoxia Li",
                        "affiliations": [
                            "Department of Integrated Chinese Traditional and Western Medicine, International Medical School, Tianjin Medical University, Tianjin, China"
                        ],
                        "is_corresponding": False,
                    },
                ],
                "abstract": "Tumor metastasis is still the leading cause of melanoma mortality. Luteolin, a natural flavonoid, is found in fruits, vegetables, and medicinal herbs. The pharmacological action and mechanism of luteolin on the metastasis of melanoma remain elusive. In this study, we investigated the effect of luteolin on A375 and B16-F10 cell viability, migration, invasion, adhesion, and tube formation of human umbilical vein endothelial cells. Epithelial–mesenchymal transition (EMT) markers and pivotal molecules in HIF-1α/VEGF signaling expression were analysed using western blot assays or quantitative real-time polymerase chain reaction. Results showed that luteolin inhibits cellular proliferation in A375 and B16-F10 melanoma cells in a time-dependent and concentration-dependent manner. Luteolin significantly inhibited the migratory, invasive, adhesive, and tube-forming potential of highly metastatic A375 and B16-F10 melanoma cells or human umbilical vein endothelial cells at sub-IC50 concentrations, where no significant cytotoxicity was observed. Luteolin effectively suppressed EMT by increased E-cadherin and decreased N-cadherin and vimentin expression both in mRNA and protein levels. Further, luteolin exerted its anti-metastasis activity through decreasing the p-Akt, HIF-1α, VEGF-A, p-VEGFR-2, MMP-2, and MMP-9 proteins expression. Overall, our findings first time suggests that HIF-1α/VEGF signaling-mediated EMT and angiogenesis is critically involved in anti-metastasis effect of luteolin as a potential therapeutic candidate for melanoma.",
            },
        },
    ]
