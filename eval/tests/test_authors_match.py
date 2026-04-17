from parseland_eval.score.authors import score_authors


def _mk(name: str) -> dict:
    return {"name": name}


class TestAuthorMatching:
    def test_empty_inputs(self) -> None:
        r = score_authors([], [])
        assert r.f1 == 0.0
        assert r.f1_soft == 0.0

    def test_perfect_match_exact(self) -> None:
        gold = [_mk("Jane Doe"), _mk("John Smith")]
        parsed = [_mk("Jane Doe"), _mk("John Smith")]
        r = score_authors(gold, parsed)
        assert r.f1 == 1.0
        assert r.f1_soft == 1.0

    def test_order_insensitive(self) -> None:
        gold = [_mk("Jane Doe"), _mk("John Smith")]
        parsed = [_mk("John Smith"), _mk("Jane Doe")]
        r = score_authors(gold, parsed)
        assert r.f1 == 1.0

    def test_diacritic_fold(self) -> None:
        gold = [_mk("Cédric Moreau")]
        parsed = [_mk("Cedric Moreau")]
        r = score_authors(gold, parsed)
        assert r.f1 == 1.0

    def test_last_first_vs_first_last(self) -> None:
        gold = [_mk("Doe, Jane")]
        parsed = [_mk("Jane Doe")]
        r = score_authors(gold, parsed)
        assert r.f1 == 1.0

    def test_initial_vs_full_first(self) -> None:
        gold = [_mk("J. Doe")]
        parsed = [_mk("Jane Doe")]
        r = score_authors(gold, parsed)
        # Strict (last + first-initial) → match
        assert r.f1 == 1.0

    def test_missing_author_reduces_recall(self) -> None:
        gold = [_mk("Jane Doe"), _mk("John Smith"), _mk("Ada Lovelace")]
        parsed = [_mk("Jane Doe")]
        r = score_authors(gold, parsed)
        assert r.recall < 1.0
        assert r.precision == 1.0

    def test_spurious_author_reduces_precision(self) -> None:
        gold = [_mk("Jane Doe")]
        parsed = [_mk("Jane Doe"), _mk("Fake Person"), _mk("Noise Name")]
        r = score_authors(gold, parsed)
        assert r.precision < 1.0
        assert r.recall == 1.0
