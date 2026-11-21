"""A WEKO3 search form's licence filter is not the record's licence (oxjob #1165; #891 found it on IRDB).

Every WEKO3 record page (JAIRO Cloud *.repo.nii.ac.jp, repo.qst.go.jp, repository.exst.jaxa.jp, ...) carries the
search form's settings in one attribute, `<div ng-init="initData({&#34;condition_setting&#34;: [...]})">`, whose
licence filter lists every licence the form offers (CC0 ... CC BY-NC-ND 4.0). Read as the record's licence, every
record came out cc-by-nc-nd, metadata-only records included. The record's own licence is its file's
"Creative Commons Licenses" link, outside the attribute. Fragments mirror live pages read 21 Nov 2026
(repo.qst.go.jp/records/65073, teikyo-u.repo.nii.ac.jp/records/2025656: no file, no licence of their own;
iwatemed.repo.nii.ac.jp/records/9600: a file with its own CC BY-NC-ND 3.0 link).
"""
import pytest

from parseland_lib.legacy_parse_utils.version_and_license import drop_weko3_search_form
from parseland_lib.parse import parse_page

RECORD_URL = "https://iwatemed.repo.nii.ac.jp/records/{}"

Q = "&#34;"
LICENCE_OPTIONS = ", ".join(
    f"{{{Q}contents{Q}: {Q}{label}{Q}, {Q}id{Q}: {Q}{key}{Q}}}" for label, key in [
        ("CC BY 4.0", "license_0"), ("CC BY-SA 4.0", "license_1"), ("CC BY-ND 4.0", "license_2"),
        ("CC BY-NC 4.0", "license_3"), ("CC BY-NC-SA 4.0", "license_4"), ("CC BY-NC-ND 4.0", "license_5"),
        ("CC BY-NC-ND 3.0", "license_11"), ("CC0", "license_12"), ("その他", "license_free")])
SEARCH_FORM = (
    f'<div ng-init="initData({{{Q}condition_setting{Q}: [{{{Q}contents{Q}: {Q}Title{Q}, {Q}id{Q}: {Q}title{Q}, '
    f'{Q}inputType{Q}: {Q}text{Q}, {Q}inputVal{Q}: {Q}{Q}}}, {{{Q}check_val{Q}: [{LICENCE_OPTIONS}], '
    f'{Q}contents{Q}: {Q}License{Q}, {Q}contents_value{Q}: {{{Q}en{Q}: {Q}License{Q}, {Q}ja{Q}: '
    f'{Q}ライセンス{Q}}}, {Q}id{Q}: {Q}license{Q}, {Q}inputType{Q}: {Q}checkbox_list{Q}}}]}})"></div>')


def own_licence_cell(deed):
    return (f'<td><!-- Creative Commons Licenses --><div><a class="creative-commons" target="_blank" '
            f'href="https://creativecommons.org/licenses/{deed}/deed.ja" alt="Creative Commons Licenses">'
            f'<img src="/static/images/default/88x31(6).png" alt="license.icon" /></a></div></td>')


def weko3_page(record_cells=""):
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><title>放射線影響の研究</title>
<meta name="citation_title" content="放射線影響の研究"><meta name="citation_author" content="山田, 太郎">
</head><body><div class="container">{SEARCH_FORM}
<table class="table"><tr><th>タイトル</th><td>放射線影響の研究</td></tr><tr>{record_cells}</tr></table>
</div></body></html>"""


def test_record_without_a_licence_of_its_own_has_none():
    assert parse_page(weko3_page(), "pmh", RECORD_URL.format(65073))["license"] is None


@pytest.mark.parametrize("deed, licence", [
    ("by-nc-nd/3.0", "cc-by-nc-nd"),
    ("by/4.0", "cc-by"),
    ("by-sa/4.0", "cc-by-sa"),
])
def test_record_keeps_its_own_licence(deed, licence):
    page = weko3_page(own_licence_cell(deed))
    assert parse_page(page, "pmh", RECORD_URL.format(9600))["license"] == licence


def test_search_form_alone_read_as_a_licence_before_the_fix():
    from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
    assert find_normalized_license(SEARCH_FORM) == "cc-by-nc-nd"


def test_drop_removes_only_the_search_form_attribute():
    page = weko3_page(own_licence_cell("by/4.0"))
    dropped = drop_weko3_search_form(page)
    assert "condition_setting" not in dropped and "CC BY-NC-ND 4.0" not in dropped
    assert "creativecommons.org/licenses/by/4.0" in dropped and "放射線影響の研究" in dropped


@pytest.mark.parametrize("page", [
    None, "",
    '<div ng-init="initData({&#34;item_id&#34;: 1})">CC BY-NC-ND 4.0</div>',
    "<p>condition_setting is mentioned, but no WEKO3 form here: CC BY 4.0</p>",
])
def test_pages_without_the_form_are_unchanged(page):
    assert drop_weko3_search_form(page) == page
