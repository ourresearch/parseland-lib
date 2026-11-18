"""DIGIBIB record pages: Americanae (americanae.aecid.es), Hispana and the other portals built on DIGIBIB's OAI
harvester (#2239 round 8b).

Their meta tags describe the portal, not the record (DC.creator is the library behind it, DC.identifier the portal's
home page), so no tag reader finds the record's authors or full text. The record is printed in two panels: the
"Ficha" (`#panel_ficha_dc`, a <dl> of "Autor/Productor:", "Relación:", "Formato:" ... rows) and the harvested
metadata as displayed XML (`#panel_xoai` and others), where a DSpace source lists its files.
"""
import re

_NO_NAME = re.compile(r"^(?:sem|sin|no)\s+informa", re.I)  # "sem informação": the source had no name
_LIFE_DATES = re.compile(r",?\s*\d{4}\s*-\s*(?:\d{4})?\.?$")  # "Aldar, Henrique, 1986-"
_SOURCE_TAG = re.compile(r"\s*\[[^\]]*\]$")  # "Tufik, Sergio [UNIFESP]": the source repository's tag
_ROLE = re.compile(r"\s*[-–,]\s*autor(?:/a|a)?\.?$", re.I)  # "Zukerfeld, Mariano - Autor/a"
# Not a person: "Anonymous", "Autores varios"; a body or event ("Guggenheim Bilbao Museoa", "Congreso Cientifico 4º
# 1909 Santiago de Chile", "Església Catòlica. Papa (1352-1362 : Innocenci VI), autor"): no digits, brackets or colons
_NOT_A_PERSON = re.compile(r"^(?:anonymous|an[oó]nimo|autores\s+varios|varios\s+autores|various(?:\s+authors)?)$|"
                           r"[\d():]|\b(?:museoa|congreso|congress|iglesia|esgl[eé]sia|church)\b", re.I)
# An OJS galley ("/article/view/<article>/<galley>"): the record's file when the record's format is a PDF
# A source repository's own address for its file (some DSpace sources export "http://localhost:8080/...")
_PUBLIC_URL = re.compile(r"https?://(?!localhost\b|127\.|10\.|192\.168\.)[^/\s]+\.[^/\s]+/")
_OJS_GALLEY = re.compile(r"/index\.php/[^?#]+/article/view/[^/?#]+/\d+/?$")


def is_digibib_record(soup):
    return soup.select_one("#panel_ficha_dc dl") is not None


def _ficha(soup):
    """The record panel's rows: label ("Autor/Productor") -> its <dd> tags, in page order."""
    rows, label = {}, None
    dl = soup.select_one("#panel_ficha_dc dl")
    for tag in dl.find_all(["dt", "dd"]) if dl is not None else []:
        if tag.name == "dt":
            label = tag.get_text(" ", strip=True).rstrip(": ").strip()
            rows.setdefault(label, [])
        elif label is not None:
            rows[label].append(tag)
    return rows


def digibib_creator_values(soup):
    """The record's "Autor/Productor" values, cleaned ('Family, Given' each). [] when one value cannot be read as
    names (three or more parts that do not pair into 'Family, Given'): better none than a merged or cut name."""
    values = []
    for dd in _ficha(soup).get("Autor/Productor", []):
        text = re.sub(r"\s+", " ", dd.get_text(" ", strip=True)).strip()
        text = _ROLE.sub("", _LIFE_DATES.sub("", _SOURCE_TAG.sub("", text))).strip(" ,;")
        if not text or _NO_NAME.match(text) or _NOT_A_PERSON.search(text):
            continue
        for part in text.split(";"):
            parts = [p.strip() for p in part.split(",") if p.strip()]
            if len(parts) <= 2:
                values.append(", ".join(parts))
            elif len(parts) % 2 == 0:  # "Pezoa, R., Kuleshov, Serguey": two people in one field
                values.extend(f"{parts[i]}, {parts[i + 1]}" for i in range(0, len(parts), 2))
            else:
                return []
    return values


def digibib_pdf(soup):
    """The record's PDF: the source repository's ORIGINAL bitstream whose format is application/pdf (DSpace sources,
    in the harvested xoai metadata), else the record's OJS galley link when the record gives its format as
    application/pdf. None otherwise."""
    for element in soup.select("#panel_xoai li.xml_element"):
        if _element_name(element) != "bitstream" or _bundle_name(element) != "ORIGINAL":
            continue
        fields = _fields(element)
        if fields.get("format") == "application/pdf" and _PUBLIC_URL.match(fields.get("url", "")):
            return fields["url"]
    rows = _ficha(soup)
    if any(dd.get_text(strip=True).lower() == "application/pdf" for dd in rows.get("Formato", [])):
        galleys = {link["href"] for dd in rows.get("Relación", []) for link in dd.find_all("a", href=True)
                   if _OJS_GALLEY.search(link["href"])}
        if len(galleys) == 1:  # two galleys (a PDF and an HTML one) do not say which is the PDF
            return galleys.pop()
    return None


def _element_name(li):
    head = li.find("p", recursive=False)
    value = head.select_one(".attribute_value") if head is not None else None
    return value.get_text(strip=True) if value is not None else None


def _fields(li):
    """The <field name="..."> values directly inside a displayed XML element."""
    out = {}
    body = li.find("ol", recursive=False)
    for child in body.find_all("li", recursive=False) if body is not None else []:
        name, text = _element_name(child), child.select_one(".xml_text")
        if name and text is not None and child.find("ol", recursive=False) is None:
            out.setdefault(name, text.get_text(strip=True))
    return out


def _bundle_name(li):
    for parent in li.find_parents("li"):
        if _element_name(parent) == "bundle":
            return _fields(parent).get("name")
    return None
