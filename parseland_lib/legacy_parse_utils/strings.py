import re

import bs4
from bs4 import UnicodeDammit
from lxml import html, etree
from unidecode import unidecode



def clean_html(raw_html):
    cleanr = re.compile('<\w+.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def cleanup_soup(soup):
    from parseland_lib.publisher.parsers.wiley import Wiley
    try:
        [script.extract() for script in soup('script')]
        [div.extract() for div in
         soup.find_all("div", {'class': 'table-of-content'})]
        [div.extract() for div in
         soup.find_all("li", {'class': 'linked-article__item'})]

        if Wiley(soup).is_publisher_specific_parser():
            [div.extract() for div in
             soup.find_all('div', {'class': 'hubpage-menu'})]

        if soup.find('meta', {'property': 'og:site_name', 'content': lambda
                x: 'Oncology Nursing Society' in x}):
            [div.extract() for div in
             soup.find_all('div', {'class': 'view-issue-articles'})]
    except Exception as e:
        pass
    return soup

def remove_punctuation(input_string):
    # from http://stackoverflow.com/questions/265960/best-way-to-strip-punctuation-from-a-string-in-python
    no_punc = input_string
    if input_string:
        no_punc = "".join(
            e for e in input_string if (e.isalnum() or e.isspace()))
    return no_punc

def normalize(text):
    if isinstance(text, bytes):
        text = str(text, 'ascii')
    response = text.lower()
    response = unidecode(response)
    response = clean_html(response)  # has to be before remove_punctuation
    response = remove_punctuation(response)
    response = re.sub(r"\b(a|an|the)\b", "", response)
    response = re.sub(r"\b(and)\b", "", response)
    response = re.sub(r"\s+", "", response)
    return response

def normalized_strings_equal(str1, str2):
    if str1 and str2:
        return normalize(str1) == normalize(str2)
    return False


def strip_jsessionid_from_url(url):
    url = re.sub(r";jsessionid=\w+", "", url)
    return url

def decode_escaped_href(href):
    if re.search(r'\\u[0-9a-fA-F]{4}', href):
        try:
            return href.encode().decode('unicode-escape')
        except UnicodeDecodeError:
            pass

    return href

def get_tree(page):
    if page is None:
        return None

    if isinstance(page, bs4.BeautifulSoup):
        page = str(page)
    elif not isinstance(page, str):
        # handle any other non-string types
        try:
            page = str(page)
        except UnicodeDecodeError:
            # Handle the case where page cannot be converted to string
            return None

    page = page.replace("&nbsp;",
                        " ")  # otherwise starts-with for lxml doesn't work
    try:
        page = page.encode('utf-8')  # this is a waste, take page as bytes later
        encoding = UnicodeDammit(page, is_html=True).original_encoding
        parser = html.HTMLParser(encoding=encoding)
        tree = html.fromstring(page, parser=parser)
    except (etree.XMLSyntaxError, etree.ParserError) as e:
        tree = None
    return tree

