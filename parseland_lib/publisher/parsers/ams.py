import re

from parseland_lib.publisher.parsers.parser import PublisherParser

# The "Additional Notes" entry of an AMS article's Additional Information (oxjob #2330): a support note, and on some
# articles which author is the corresponding one ("The fifth author is the corresponding author").
_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
_CORRESPONDING = re.compile(r"\bthe (\w+) author is (?:the )?corresponding author\b\.?", re.I)
_FUNDING = re.compile(r"\bsupport|\bgrant|\bfund(?:s|ed|ing)?\b|\bfellow|\baward|\bfoundation|\bsponsor|\bfinanc",
                      re.I)
_NOTES_LABEL = "Additional Notes:"


def _squash(text):
    return re.sub(r"\s+", " ", text).strip()


class AmericanMathematicalSociety(PublisherParser):
    parser_name = "american_mathematical_society"

    def is_publisher_specific_parser(self):
        # remembered: parse() asks too (below), and production asks again right after parse() on the same instance
        if not hasattr(self, "_claimed"):
            if og_title := self.soup.select_one('meta[property="og:title"]'):
                self._claimed = 'American Mathematical Society' in og_title['content']
            else:
                self._claimed = False
        return self._claimed

    def authors_found(self):
        return bool(self.parse_author_meta_tags())

    def parse_abstract(self):
        if abs_tag := self.soup.select_one('a[name=Abstract]'):
            return abs_tag.next_sibling.text.strip()
        elif abs_tag := self.soup.select_one('section#Abstract'):
            if heading := abs_tag.find('h2'):
                heading.decompose()
            return abs_tag.text.strip()
        return None

    def additional_notes(self):
        """The Additional Notes entry's lines: an <li> in the current template, the text after its label link up to
        the next label link in the older one (lines split at <br />)."""
        entry = None
        for item in self.soup.select('section#additionalinformation li'):
            if item.get_text().lstrip().startswith(_NOTES_LABEL):
                entry = list(item.children)
                break
        else:
            for label in self.soup.select('a[href$="abstracthelp.html#addinfo"]'):
                if label.get_text(strip=True) == _NOTES_LABEL:
                    entry = []
                    for node in label.next_siblings:
                        if node.name == 'a' and 'abstracthelp.html' in (node.get('href') or ''):
                            break
                        entry.append(node)
                    break
        if entry is None:
            return []
        lines, line = [], []
        for node in entry:
            if node.name == 'br':
                lines.append(_squash(''.join(line)))
                line = []
            else:
                line.append(node.get_text() if node.name else str(node))
        lines.append(_squash(''.join(line)))
        if lines and lines[0].startswith(_NOTES_LABEL):
            lines[0] = lines[0][len(_NOTES_LABEL):].strip()
        return [text for text in lines if text]

    def parse(self):
        result = {'authors': self.parse_author_meta_tags(),
                  'abstract': self.parse_abstract()}
        # This parse() runs on every page with citation_author tags and can win other sites' pages (see
        # get_authors_and_abstract): read the notes only on the pages this parser claims.
        if not self.is_publisher_specific_parser():
            return result
        funding, authors = [], result['authors']
        for line in self.additional_notes():
            if corresponding := _CORRESPONDING.search(line):
                ordinal = corresponding.group(1).lower()
                place = len(authors) - 1 if ordinal == "last" else (
                    _ORDINALS.index(ordinal) if ordinal in _ORDINALS else None)
                if place is not None and place < len(authors) and not any(a['is_corresponding'] for a in authors):
                    for i, author in enumerate(authors):
                        author['is_corresponding'] = i == place
                line = _squash(_CORRESPONDING.sub('', line))
            if line and _FUNDING.search(line):
                funding.append(line)
        if funding:
            result['funding_statement'] = '\n'.join(funding)
        return result
