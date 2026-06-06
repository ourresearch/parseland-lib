from __future__ import annotations

from bs4 import BeautifulSoup

from parseland_lib.publisher.parsers.springer import Springer


def _parser(body: str) -> Springer:
    html = f"""
    <html>
      <head>
        <link rel="canonical" href="https://link.springer.com/article/10.1007/example" />
      </head>
      <body>{body}</body>
    </html>
    """
    return Springer(BeautifulSoup(html, "html.parser"))


def test_structured_sections_recover_bmc_conference_abstract():
    parser = _parser(
        """
        <section><h2>Background</h2><p>Background sentence.</p></section>
        <section><h2>Methods</h2><p>Methods sentence.</p></section>
        <section><h2>Results</h2><p>Results sentence.</p></section>
        <section><h2>Conclusion</h2><p>Conclusion sentence.</p></section>
        <section><h2>Author information</h2><p>Not part of abstract.</p></section>
        """
    )

    abstract = parser.parse()["abstract"]

    assert "Background sentence." in abstract
    assert "Methods sentence." in abstract
    assert "Results sentence." in abstract
    assert "Conclusion sentence." in abstract
    assert "Not part of abstract." not in abstract


def test_language_heading_recovers_missing_abstract_only():
    parser = _parser(
        """
        <section>
          <h2>Zusammenfassung</h2>
          <p>Dies ist ein deutschsprachiger Abstract mit genug Inhalt,
          damit der Missing-Fallback greift und nicht als kurzer Teaser
          verworfen wird.</p>
        </section>
        """
    )

    abstract = parser.parse()["abstract"]

    assert abstract.startswith("Dies ist ein deutschsprachiger Abstract")
