Example Usage

```
from parseland_lib.parse import parse_page
from parseland_lib.s3 import get_landing_page_from_r2

url = 'https://doi.org/10.1002/andp.19033150414'
lp = get_landing_page_from_r2(url)
response = parse_page(lp)
print(response)
```
