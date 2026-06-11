import re
import unicodedata

from parseland_lib.exceptions import UnusualTrafficError
from parseland_lib.elements import AuthorAffiliations
from parseland_lib.publisher.parsers.parser import PublisherParser
from parseland_lib.publisher.parsers.utils import EMAIL_RE


class ACS(PublisherParser):
    parser_name = "acs"

    def is_publisher_specific_parser(self):
        if "Request forbidden by administrative rules" in str(self.soup):
            raise UnusualTrafficError(f"Page blocked within parser {self.parser_name}")
        return self.domain_in_meta_og_url(".acs.org")

    def authors_found(self):
        return self.soup.find("ul", class_="loa")

    @staticmethod
    def _clean_abstract(text):
        text = re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()
        return re.sub(r"\s+([,;:!?])", r"\1", text)

    @staticmethod
    def _decode_cfemail(value):
        try:
            key = int(value[:2], 16)
            return "".join(
                chr(int(value[i : i + 2], 16) ^ key)
                for i in range(2, len(value), 2)
            )
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _normalize_ascii(text):
        return (
            unicodedata.normalize("NFD", text or "")
            .encode("ascii", "ignore")
            .decode()
            .lower()
        )

    @classmethod
    def _email_matches_author(cls, email, name):
        local = cls._normalize_ascii((email or "").split("@", 1)[0])
        local_compact = re.sub(r"[^a-z0-9]+", "", local)
        parts = [
            p
            for p in re.split(r"[^a-z0-9]+", cls._normalize_ascii(name))
            if len(p) > 1
        ]
        if not local or not parts:
            return False
        first = parts[0]
        last = parts[-1]
        initials = "".join(p[0] for p in parts if p)

        if len(last) >= 3 and last in local_compact:
            if first in local_compact:
                return True
            if local_compact.startswith(first[:1] + last) or local_compact.startswith(
                last + first[:1]
            ):
                return True
            if local_compact.startswith(first[:1]) and local_compact.endswith(last):
                return True
            if len(last) >= 5 and local_compact.startswith(last):
                return True
        return len(initials) >= 2 and local_compact.startswith(initials)

    @staticmethod
    def _node_mentions_corresponding_email(node):
        current = node
        for _ in range(5):
            if not current or getattr(current, "name", None) in ("body", "html"):
                break
            text = current.get_text(" ", strip=True).lower()
            if "correspond" in text:
                return True
            current = current.parent
        return False

    def _corresponding_emails(self):
        emails = []
        seen = set()
        for tag in self.soup.select(
            'a[href^="mailto:"], a.__cf_email__[data-cfemail], '
            'a[href*="email-protection"][data-cfemail]'
        ):
            if not self._node_mentions_corresponding_email(tag):
                continue
            email = ""
            if tag.get("data-cfemail"):
                email = self._decode_cfemail(tag.get("data-cfemail"))
            else:
                email = re.sub(r"^mailto:", "", tag.get("href", ""), flags=re.I)
                email = email.split("?", 1)[0]
            email = email.strip()
            if not EMAIL_RE.search(email):
                continue
            key = email.lower()
            if key not in seen:
                emails.append(email)
                seen.add(key)
        return emails

    def _mark_corresponding_from_emails(self, authors):
        for email in self._corresponding_emails():
            matches = [
                author
                for author in authors
                if self._email_matches_author(email, author.name)
            ]
            if len(matches) == 1:
                matches[0].is_corresponding = True

    def get_abstract(self):
        for selector in (
            "div.article_abstract-content#abstractBox",
            "div.article_abstract-content.hlFld-Abstract",
        ):
            node = self.soup.select_one(selector)
            if not node:
                continue
            text = self._clean_abstract(node.get_text(" ", strip=True))
            if text:
                return text
        return self.parse_abstract_meta_tags()

    def parse(self):
        result_authors = []
        author_soup = self.soup.find("ul", class_="loa")
        authors = author_soup.findAll("li")
        # Alternate ACS template (older / some journals): affiliations are not
        # per-author loa-info-affiliations divs but a page-level list of
        # div.aff-info > span.aff-text (the main institutional affiliation,
        # usually shared by all authors; the dagger/double-dagger footnotes are
        # present-address / correspondence notes, captured separately). Use it as
        # a shared fallback for authors that have no per-author affiliations.
        shared_affs = []
        affs_by_symbol = {}
        for aff_info in self.soup.select("div.aff-info"):
            aff_text = aff_info.select_one("span.aff-text")
            if not aff_text:
                continue
            aff = aff_text.get_text(" ", strip=True)
            if not aff:
                continue
            shared_affs.append(aff)
            symbol = aff_info.select_one("span.aff-symbol")
            symbol_text = symbol.get_text(" ", strip=True) if symbol else ""
            if symbol_text:
                affs_by_symbol.setdefault(symbol_text, []).append(aff)
        for author in authors:
            # Prefer loa-info-name (modern template); fall back to
            # hlFld-ContribAuthor (alternate template — gives a clean name
            # without the trailing author-xref-symbol superscript); finally the
            # raw li text.
            name = author.find("div", class_="loa-info-name")
            if not name:
                name = author.find("span", class_="hlFld-ContribAuthor")
            if name:
                name = name.text.strip()
            else:
                name = author.text

            # ul.loa interleaves separator <li> elements (", " and " and ")
            # between author names; without a name div they fall through to
            # author.text and were being emitted as junk authors, tanking author
            # precision. Skip any <li> whose text is just a separator.
            name = (name or "").replace("\xa0", " ").strip()
            if not name or name.strip(" ,&").lower() in ("", "and"):
                continue

            strong = author.find("strong")
            is_corresponding = bool(strong and strong.text.strip() == "*")
            if not is_corresponding:
                # Alternate template marks the corresponding author with a '*'
                # in an author-xref-symbol superscript rather than a
                # <strong>*</strong>; the <strong> check alone missed these
                # (recall 0.63). The '*' xref is corresponding-only on ACS.
                is_corresponding = any(
                    "*" in x.get_text() for x in author.select(".author-xref-symbol")
                )

            affiliations = []
            affiliation_soup = author.find("div", class_="loa-info-affiliations")
            if affiliation_soup:
                for organization in affiliation_soup.findAll("div"):
                    affiliations.append(organization.text.strip())
            if not affiliations and affs_by_symbol:
                for symbol in author.select(".author-aff-symbol"):
                    symbol_text = symbol.get_text(" ", strip=True)
                    for aff in affs_by_symbol.get(symbol_text, []):
                        if aff not in affiliations:
                            affiliations.append(aff)
            if not affiliations:
                affiliations = list(shared_affs)

            result_authors.append(
                AuthorAffiliations(
                    name=name,
                    affiliations=affiliations,
                    is_corresponding=is_corresponding,
                )
            )
        self._mark_corresponding_from_emails(result_authors)
        return {"authors": result_authors, "abstract": self.get_abstract()}

    test_cases = [
        {
            "doi": "10.1021/acs.jpcb.1c05793",
            "result": {
                "authors": [
                    {
                        "name": "Piotr Wróbel",
                        "affiliations": [
                            "Faculty of Chemistry, Jagiellonian University, Gronostajowa 2, 30-387 Kraków, Poland",
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Piotr Kubisiak",
                        "affiliations": [
                            "Faculty of Chemistry, Jagiellonian University, Gronostajowa 2, 30-387 Kraków, Poland"
                        ],
                        "is_corresponding": False,
                    },
                    {
                        "name": "Andrzej Eilmes",
                        "affiliations": [
                            "Faculty of Chemistry, Jagiellonian University, Gronostajowa 2, 30-387 Kraków, Poland"
                        ],
                        "is_corresponding": True,
                    },
                ],
                "abstract": "Classical molecular dynamics simulations have been performed for a series of electrolytes based on sodium bis(fluorosulfonyl)imide or sodium bis(trifluoromethylsulfonyl)imide salts and monoglyme, tetraglyme, and poly(ethylene oxide) as solvents. Structural properties have been assessed through the analysis of coordination numbers and binding patterns. Residence times for Na–O interactions have been used to investigate the stability of solvation shells. Diffusion coefficients of ions and electrical conductivity of the electrolytes have been estimated from molecular dynamics trajectories. Contributions to the total conductivity have been analyzed in order to investigate the role of ion–ion correlations. It has been found that the anion–cation interactions are more probable in the systems with NaTFSI salts. Accordingly, the degree of correlations between ion motions is larger in NaTFSI-based electrolytes.",
            },
        }
    ]
