"""Corresponding authors on Egyptian Knowledge Bank (EKB, journals.ekb.eg) article pages (oxjob #2216).

Markup is cut down from stored EKB pages (#2149 EXPLORE § 1, 350 seeded pages). EKB runs the Sinaweb platform. The
author list (`li.padding-3`) gives the corresponding author an envelope `mailto` whose tooltip reads "Email to
Corresponding Author" (Arabic pages: "إرسال بريد إلكتروني إلى المؤلف المختص"), or a Font Awesome asterisk in the
author's `<sup>`; the older template puts `<sup>*</sup>` inside `a.citation_author`. Gold v1.3 dev marks all three.
An asterisk or star counts only when it singles out some authors of a multi-author page (stars on every author mark
no one), and an envelope on the page outranks the asterisks.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.egyptian_knowledge_bank import EgyptianKnowledgeBank

URL = "https://example.journals.ekb.eg/article_12345.html"


def _page(names, body, abstract_url=URL):
    metas = "".join(f'<meta name="citation_author" content="{n}"/>' for n in names)
    return (f'<html><head><meta name="citation_title" content="A title"/>{metas}'
            f'<meta name="citation_abstract_html_url" content="{abstract_url}"/>'
            f'<meta name="citation_doi" content="10.21608/x.2024.1"/></head><body>{body}</body></html>')


ENVELOPE = ('<sup><a href="mailto:a@example.com" data-toggle="tooltip" data-placement="bottom" '
            'title="Email to Corresponding Author"><i class="fa fa-envelope-o" ></i></a></sup>')
ASTERISK = '<sup><i class="fa fa-asterisk" ></i></sup>'


def _byline(names, marks):
    items = "".join(f'<li class="padding-3"><a href="./?_action=article&amp;au={i}&amp;_au={n.replace(" ", "+")}">{n}</a>'
                    f'{m}<sup><a href="#aff{i}">{i}</a></sup></li>' for i, (n, m) in enumerate(zip(names, marks), 1))
    return f'<ul class="list-inline list-inline-seprator margin-bottom-6">{items}</ul>'


def _corr(html):
    return [a["name"] for a in parse_page(html.encode(), "doi", URL)["authors"] if a["is_corresponding"]]


META = ["Setta, Hany Saad", "Al Mahmoudy, Niveen Fathy", "Abdel Halim, Mohamed Mamdouh"]
BYLINE = ["Hany Saad Setta", "Niveen Fathy Al Mahmoudy", "mohamed mamdouh abdel halim"]


def test_envelope_marks_its_author():
    html = _page(META, _byline(BYLINE, ["", ENVELOPE, ""]))
    assert _corr(html) == ["Al Mahmoudy, Niveen Fathy"]


def test_arabic_envelope_marks_its_author():
    env = ENVELOPE.replace("Email to Corresponding Author", "إرسال بريد إلكتروني إلى المؤلف المختص")
    html = _page(["النجار, نور", "رشوان, هدير هلال"], _byline(["نور  النجار", "هدير هلال  رشوان"], [env, ""]))
    assert _corr(html) == ["النجار, نور"]


def test_lone_asterisk_marks_its_author():
    html = _page(META, _byline(BYLINE, ["", "", ASTERISK]))
    assert _corr(html) == ["Abdel Halim, Mohamed Mamdouh"]


def test_sole_author_asterisk_marks_them():
    html = _page(["عفيفي, هلال عبدالفتاح"], _byline(["هلال عبدالفتاح  عفيفي"], [ASTERISK]))
    assert _corr(html) == ["عفيفي, هلال عبدالفتاح"]


def test_asterisk_on_every_author_marks_no_one():
    html = _page(META, _byline(BYLINE, [ASTERISK, ASTERISK, ASTERISK]))
    assert _corr(html) == []


def test_envelope_outranks_asterisks():
    html = _page(META, _byline(BYLINE, [ASTERISK, ENVELOPE, ASTERISK]))
    assert _corr(html) == ["Al Mahmoudy, Niveen Fathy"]


def test_no_mark_marks_no_one():
    assert _corr(_page(META, _byline(BYLINE, ["", "", ""]))) == []


def test_byline_matched_by_name_when_counts_differ():
    # a fourth meta author with no byline entry: the mark is matched by name, not position
    html = _page(META + ["Extra, Someone"], _byline(BYLINE, ["", "", ENVELOPE]))
    assert _corr(html) == ["Abdel Halim, Mohamed Mamdouh"]


OLD_ENVELOPE = ('<sup><a href="mailto:a@example.com" title="Email to Corresponding Author">'
                '<img alt="email" src="images/email.png"/></a></sup>')


def _old_byline(names, marks):
    # older template: <a class="citation_author">Name<sup>*</sup> </a>; the envelope sits inside the link too
    return "".join(f'<a class="citation_author" href="./?_action=article&amp;au={i}">{n} {m}</a>; '
                   for i, (n, m) in enumerate(zip(names, marks), 1))


OLD_META = ["Atshan, Ali F.", "Mahmoud, Kamal S.", "Abed, Ahmed H."]
OLD_BYLINE = ["Ali F. Atshan", "Kamal S. Mahmoud", "Ahmed H. Abed"]


def test_old_template_star():
    assert _corr(_page(OLD_META, _old_byline(OLD_BYLINE, ["<sup>*</sup>", "", ""]))) == ["Atshan, Ali F."]


def test_old_template_star_on_every_author_marks_no_one():
    assert _corr(_page(OLD_META, _old_byline(OLD_BYLINE, ["<sup>*</sup>"] * 3))) == []


def test_old_template_envelope():
    assert _corr(_page(OLD_META, _old_byline(OLD_BYLINE, ["", "", OLD_ENVELOPE]))) == ["Abed, Ahmed H."]


def test_other_sinaweb_site_is_not_claimed():
    # the same Sinaweb byline on a non-EKB journal: not this parser's page, so no EKB mark is read
    html = _page(META, _byline(BYLINE, ["", ENVELOPE, ""]),
                 abstract_url="https://journal.example.ac.ir/article_12345.html")
    assert not EgyptianKnowledgeBank(BeautifulSoup(html, "lxml")).is_publisher_specific_parser()
