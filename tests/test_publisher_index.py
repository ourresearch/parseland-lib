import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lib.publisher_index import classify_row, prefix_to_publisher


def test_supported_tail_prefixes_are_classified_without_network():
    cases = {
        "10.1038/s41598-020-70739-y": "springer",
        "10.1088/1742-6596/2853/1/012065": "iop",
        "10.1039/b922668k": "rsc",
        "10.1055/s-2008-1041524": "thieme",
        "10.1159/000277292": "karger",
        "10.1001/jama.2022.7461": "ama",
        "10.1142/9789814307031_0001": "world_scientific",
        "10.1504/ijista.2008.021305": "inderscience",
        "10.1128/genomea.00400-14": "asm",
    }

    for doi, publisher in cases.items():
        assert prefix_to_publisher(doi) == publisher
        assert classify_row({"DOI": doi, "Link": f"https://doi.org/{doi}"}, allow_network=False) == publisher


def test_ssrn_prefix_prefers_ssrn_parser_over_crossref_registrant_owner():
    doi = "10.2139/ssrn.4398349"

    assert prefix_to_publisher(doi) == "ssrn"
    assert classify_row({"DOI": doi, "Link": f"https://doi.org/{doi}"}, allow_network=False) == "ssrn"


def test_taylor_book_prefixes_are_classified_without_network():
    for doi in ("10.4324/9780203370469-11", "10.1201/9781003761877_ch34"):
        assert prefix_to_publisher(doi) == "taylor"
        assert classify_row({"DOI": doi, "Link": f"https://doi.org/{doi}"}, allow_network=False) == "taylor"
