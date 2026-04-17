import pytest

from parseland_eval.score.normalize import (
    canonicalize_url,
    normalize_alpha,
    normalize_doi,
    normalize_text,
    strip_diacritics,
)


class TestNormalizeText:
    def test_empty(self) -> None:
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_diacritics_folded(self) -> None:
        # unidecode maps ö→o, ß→ss (not oe/ss), é→e
        assert normalize_text("Cédric") == normalize_text("Cedric") == "cedric"
        assert normalize_text("Mößbauer") == "mossbauer"
        assert normalize_text("Straße") == normalize_text("strasse") == "strasse"

    def test_case_folded(self) -> None:
        assert normalize_text("ABC") == normalize_text("abc") == "abc"

    def test_whitespace_collapsed(self) -> None:
        assert normalize_text("  hello   world  ") == "hello world"


class TestNormalizeAlpha:
    def test_strips_punctuation(self) -> None:
        assert normalize_alpha("Smith, John-Paul!") == "smith john paul"


class TestCanonicalizeUrl:
    def test_empty(self) -> None:
        assert canonicalize_url("") == ""
        assert canonicalize_url(None) == ""

    def test_lowercases_host(self) -> None:
        assert canonicalize_url("HTTPS://Example.COM/path") == "https://example.com/path"

    def test_strips_www(self) -> None:
        assert canonicalize_url("https://www.example.com/") == "https://example.com/"

    def test_strips_tracking_params(self) -> None:
        u = canonicalize_url("https://x.com/a?utm_source=foo&keep=1")
        assert u == "https://x.com/a?keep=1"


class TestNormalizeDoi:
    def test_strips_scheme(self) -> None:
        assert normalize_doi("https://doi.org/10.1/Abc") == "10.1/abc"

    def test_strips_doi_prefix(self) -> None:
        assert normalize_doi("DOI:10.5/XYZ") == "10.5/xyz"

    def test_lowercases(self) -> None:
        assert normalize_doi("10.1/ABC") == "10.1/abc"
