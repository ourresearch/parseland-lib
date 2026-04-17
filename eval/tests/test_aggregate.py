from parseland_eval.gold import GoldAuthor, GoldRow
from parseland_eval.runner import ParserRun
from parseland_eval.score.aggregate import score_row, summarize


def _gold_row(**overrides) -> GoldRow:
    defaults = dict(
        no=1,
        doi="10.1/test",
        link="https://doi.org/10.1/test",
        authors=(GoldAuthor("Jane Doe", ("MIT",), True),),
        abstract="Quick brown fox jumps over the lazy dog.",
        pdf_url="https://example.com/paper.pdf",
        status=True,
        notes="",
        has_bot_check=False,
        resolves_to_pdf=False,
    )
    defaults.update(overrides)
    return GoldRow(**defaults)


def _parser_run(parsed: dict | None = None, **overrides) -> ParserRun:
    defaults = dict(
        doi="10.1/test",
        parsed=parsed,
        error=None,
        duration_ms=5.0,
        html_cached=True,
        publisher_domain="example.com",
    )
    defaults.update(overrides)
    return ParserRun(**defaults)


class TestScoreRow:
    def test_perfect_parse(self) -> None:
        gold = _gold_row()
        run = _parser_run(
            parsed={
                "authors": [{"name": "Jane Doe", "affiliations": [{"name": "MIT"}], "is_corresponding": True}],
                "abstract": "Quick brown fox jumps over the lazy dog.",
                "urls": [{"url": "https://example.com/paper.pdf", "content_type": "pdf"}],
                "license": None,
                "version": None,
            }
        )
        s = score_row(gold, run)
        assert s.authors is not None
        assert s.authors.f1 == 1.0
        assert s.abstract.strict_match is True
        assert s.pdf_url.strict_match is True

    def test_parser_error_still_scored(self) -> None:
        gold = _gold_row()
        run = _parser_run(parsed=None, error="crash")
        s = score_row(gold, run)
        assert s.error == "crash"
        assert s.abstract.present is False
        assert s.pdf_url.strict_match is False

    def test_gold_na_skips_author_scoring(self) -> None:
        gold = _gold_row(authors=(), gold_quality="ok", score_authors=True)
        run = _parser_run(parsed={"authors": [], "abstract": None, "urls": [], "license": None, "version": None})
        s = score_row(gold, run)
        # Zero gold + zero parsed = authors result with F1 == 0 (division by zero returns 0 in our code)
        assert s.authors is not None

    def test_broken_json_flag_disables_author_scoring(self) -> None:
        gold = _gold_row(authors=(), gold_quality="broken-json", score_authors=False)
        run = _parser_run(parsed={"authors": [{"name": "X"}], "abstract": None, "urls": [], "license": None, "version": None})
        s = score_row(gold, run)
        assert s.authors is None
        assert s.affiliations is None


class TestSummarize:
    def test_overall_shape(self) -> None:
        rows = [_gold_row()]
        runs = [_parser_run(parsed={"authors": [{"name": "Jane Doe", "affiliations": [{"name": "MIT"}], "is_corresponding": True}], "abstract": rows[0].abstract, "urls": [{"url": rows[0].pdf_url, "content_type": "pdf"}], "license": None, "version": None})]
        scores = [score_row(g, r) for g, r in zip(rows, runs)]
        out = summarize(scores)
        assert "overall" in out
        assert "per_publisher" in out
        assert "per_failure_mode" in out
        assert out["overall"]["rows"] == 1
        assert out["overall"]["pdf_url_accuracy"] == 1.0
