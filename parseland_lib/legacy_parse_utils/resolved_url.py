from urllib.parse import urlparse

def get_base_url_from_soup(soup):
    """Extract base URL from BeautifulSoup object."""
    base_tag = soup.find('base', href=True)
    if base_tag:
        return base_tag['href']

    canonical = soup.find('link', {'rel': 'canonical', 'href': True})
    if canonical:
        return canonical['href']

    og_url = soup.find('meta', {'property': 'og:url', 'content': True})
    if og_url:
        return og_url['content']

    meta_url_tags = [
        ('meta', {'name': 'citation_url', 'content': True}),
        ('meta', {'name': 'dc.identifier', 'content': True}),
        ('meta', {'property': 'al:web:url', 'content': True}),
    ]

    for tag, attrs in meta_url_tags:
        meta = soup.find(tag, attrs)
        if meta:
            return meta['content']

    for meta in soup.find_all('meta', content=True):
        content = meta['content']
        if content.startswith(('http://', 'https://')):
            parsed = urlparse(content)
            return f"{parsed.scheme}://{parsed.netloc}"

    # default
    return ""