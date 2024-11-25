Example Usage

```
from parseland_lib.parseland import parse_landing_page
from parseland_lib.s3 import get_landing_page

doi = '10.1016/j.ecoser.2021.101332'
lp = get_landing_page(doi)
resolved_url = 'https://www.sciencedirect.com/science/article/abs/pii/S2212041621000905?via%3Dihub'
parser, msg = parse_landing_page(lp) # msg is the typical Parseland API response (affiliations, abstract, etc). It's returned as part of a tuple because multiple parsers are ran to determine the best one, this saves you from having to call parser.parse() another time.
print(msg)
fulltext = parser.parse_fulltext_locations(resolved_url) # Unpaywall/legacy location parsing code
print(fulltext)
```

Alternatively
```
from parseland_lib.parseland import parse_landing_page
from parseland_lib.s3 import parse_doi

doi = '10.1016/j.ecoser.2021.101332'
resolved_url = 'https://www.sciencedirect.com/science/article/abs/pii/S2212041621000905?via%3Dihub'
parser, msg = parse_doi(doi) # msg is the typical Parseland API response (affiliations, abstract, etc). It's returned as part of a tuple because multiple parsers are ran to determine the best one, this saves you from having to call parser.parse() another time.
print(msg)
fulltext = parser.parse_fulltext_locations(resolved_url) # Unpaywall/legacy location parsing code
print(fulltext)
```
