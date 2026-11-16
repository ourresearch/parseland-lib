import re

from bs4 import NavigableString, Tag

from parseland_lib.publisher.parsers.parser import PublisherParser

# The KCI landing service's own stylesheet path (kci.go.kr/kciportal/landing, "Korea Open Access Journals"): Korean
# DOIs of hundreds of small society journals resolve to this one template (oxjob #2268). A journal's own site that
# links to KCI's portal (JKSR's KCI logo) loads no landing stylesheet.
_LANDING_ASSETS = 'link[href*="/kciportal/resources/landing/"]'
_REF_HEADING = re.compile(r"^\s*(?:참고문헌|references)\s*\(\s*(\d+)\s*\)\s*$", re.I)
_DOI = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)$", re.I)


def _is_landing_asset(href):
    return href is not None and "/kciportal/resources/landing/" in href


def _text(node):
    return " ".join(node.get_text(" ", strip=True).split())


class KCIPortal(PublisherParser):
    parser_name = "kci_portal"
    # the page has no citation_author tags: its printed byline is the only one
    prefer_publisher_authors_over_generic = True

    def is_publisher_specific_parser(self):
        # Every parser's claim runs on every DOI page (oxjob #2239's per-page CPU rule), so look only in the small
        # <head>, where the landing stylesheets sit, and keep the answer. A page with no <head> is searched whole,
        # as before.
        claim = self.__dict__.get("_kci_claim")
        if claim is None:
            head = self.soup.head
            if head is None:
                claim = bool(self.soup.select_one(_LANDING_ASSETS))
            else:
                claim = head.find("link", href=_is_landing_asset) is not None
            self._kci_claim = claim
        return claim

    def authors_found(self):
        return self.is_publisher_specific_parser() and bool(self._byline())

    def _byline(self):
        tag = self.soup.select_one("div.articleInfo div.author")
        return tag if tag and tag.get_text(strip=True) else None

    def _affiliations(self):
        """{"1": "서울대학교", ...}: each div.attach line is "<sup>n</sup>institution"."""
        affs = {}
        for p in self.soup.select("div.articleInfo div.attach p"):
            sup = p.find("sup")
            if not sup:
                continue
            key = sup.get_text(strip=True)
            text = " ".join("".join(str(s) for s in p.find_all(string=True) if s.parent is not sup).split())
            if key and text:
                affs[key] = text
        return affs

    def _authors(self):
        """Names in byline order, each closed by its <sup>n</sup>. The Full Text XML variant prints "**" in a
        span.num after names and no affiliations: unexplained marks, neither names nor corresponding marks."""
        affs = self._affiliations()
        byline = self._byline()
        # each name is closed by its mark, so a comma inside one ("Kim, Pil-dong<sup>1</sup>") stays; a byline with
        # no marks at all is a plain comma list
        marked = bool(byline.find("sup") or byline.select_one("span.num"))
        authors, name = [], []

        def close(keys=()):
            text = " ".join("".join(name).split()).strip(" ,")
            name.clear()
            for part in [text] if marked else re.split(r"\s*,\s*", text):
                if part:
                    authors.append({"name": part, "affiliations": [], "is_corresponding": False})
            if authors and text:
                for key in keys:
                    if key in affs and affs[key] not in authors[-1]["affiliations"]:
                        authors[-1]["affiliations"].append(affs[key])

        for child in byline.children:
            if isinstance(child, NavigableString):
                name.append(str(child))
            elif isinstance(child, Tag) and child.name == "sup":
                close([k.strip() for k in child.get_text().split(",")])
            elif isinstance(child, Tag) and "num" in (child.get("class") or []):
                close()
            elif isinstance(child, Tag):
                name.append(child.get_text())
        close()
        return authors

    def _references(self):
        """The list under "참고문헌(N)": whole when it has N entries. Items of the Full Text XML variant (li.ref, with
        JATS markup leaking into the text) are left alone."""
        for heading in self.soup.select("div.articleBody div.box > h1"):
            m = _REF_HEADING.match(heading.get_text(" ", strip=True))
            if not m:
                continue
            items = heading.parent.select("ol.innerBox > li")
            if not items or any("ref" in (li.get("class") or []) for li in items):
                return None, False
            refs = []
            for li in items:
                link = li.select_one('a[href*="doi.org/10."]')
                doi = _DOI.search(link["href"].strip()) if link else None
                refs.append({"position": len(refs) + 1, "raw": _text(li), "doi": doi.group(1) if doi else None})
            whole = int(m.group(1)) == len(refs) and all(r["raw"] for r in refs)
            return refs, whole
        return None, False

    def parse(self):
        refs, whole = self._references()
        result = {"authors": self._authors(), "abstract": self.parse_headed_abstract_section(main_article=True)}
        if refs:
            result["references"] = refs
            result["references_complete"] = whole
        return result
