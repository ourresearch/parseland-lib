import re

from bs4 import UnicodeDammit
from lxml import html, etree
from unidecode import unidecode


def clean_html(raw_html):
    cleanr = re.compile('<\w+.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

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

