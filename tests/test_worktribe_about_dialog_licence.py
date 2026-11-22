"""
A Worktribe repository's "About" dialog credits the site's software licences, not the output's (oxjob #1165, ticket 23016).

Every Worktribe output page (durham-repository.worktribe.com, uwe-, soas-, nottingham-, napier-, hull-repository...)
carries an "About" modal listing the open-source libraries the application uses, among them Font Awesome's icon licence:
    <p>This application uses the following open-source libraries:</p> ... <h4 class="subtitle">Font Awesome</h4>
    <p>CC BY 3.0 (<a href=" http://creativecommons.org/licenses/by/3.0/"> http://creativecommons.org/licenses/by/3.0/</a>)</p>
Read as the output's licence it made every metadata-only record cc-by, which Walden counts as an open copy (51,244 Durham
pages with no file read cc-by; ~146K across Worktribe hosts). The output's own licence is in its file details
("Publisher Licence URL"). Fragments below mirror Wayback copies of durham-repository.worktribe.com/output/1174567
(metadata only), 1117904 (file, CC BY-NC-ND) and 1117658 (file, no licence stated); no network.
"""
import pytest

from parseland_lib.parse import parse_page

OUTPUT_URL = "https://durham-repository.worktribe.com/output/{}"

ABOUT_DIALOG = """<div class="modal" id="about" role="dialog" aria-labelledby="about-title" aria-modal="true"
 title="About Durham Research Online (DRO)" tabindex="0"><div class="modal-background"></div><div class="modal-card">
<div class="modal-card-head"><p id="about-title" class="modal-card-title">About Durham Research Online (DRO)</p></div>
<section class="modal-card-body" id="about-content">
<p>Administrator e-mail: <a href="mailto:dro.admin@example.org">dro.admin@example.org</a></p><br />
<p>This application uses the following open-source libraries:</p><br />
<h4 class="subtitle">SheetJS Community Edition</h4>
<p>Apache License Version 2.0 (<a href="http://www.apache.org/licenses/">http://www.apache.org/licenses/</a>)</p><br />
<h4 class="subtitle">PDF.js</h4>
<p>Apache License Version 2.0 (<a href="http://www.apache.org/licenses/">http://www.apache.org/licenses/</a>)</p><br />
<h4 class="subtitle">Font Awesome</h4>
<p>SIL OFL 1.1 (<a href="http://scripts.sil.org/OFL">http://scripts.sil.org/OFL</a>)</p>
<p>MIT License (<a href="http://opensource.org/licenses/mit-license.html">http://opensource.org/licenses/mit-license.html</a>)</p>
<p>CC BY 3.0 (<a href=" http://creativecommons.org/licenses/by/3.0/"> http://creativecommons.org/licenses/by/3.0/</a>)</p>
</section><div aria-label="Modal Footer" class="modal-card-foot"><p>Powered by <a href="http://worktribe.com"
 target="_blank"><strong>Worktribe</strong></a> &copy; 2024</p></div></div></div>"""


def file_block(output_id, licence_url=None, statement=None):
    licence = (f"""<strong>Publisher Licence URL</strong><br />
<small><a href="{licence_url}">{licence_url}</a></small>""") if licence_url else ""
    note = f"<strong>Copyright Statement</strong><br /><small>{statement}</small>" if statement else ""
    return f"""<div class="column"><p><strong>Files</strong></p>
<a href="https://durham-repository.worktribe.com/preview/2334198/{output_id}AAM.pdf">Accepted Journal Article</a>
<small>(1.2 Mb)</small><br /><strong>PDF</strong><br />{licence}{note}</div>"""


def worktribe_page(output_id, files=""):
    pdf_meta = (f'<meta name="citation_pdf_url" content="https://durham-repository.worktribe.com/preview/2334198/'
                f'{output_id}AAM.pdf">') if files else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="citation_title" content="An output"><meta name="citation_author" content="Smith, Jane">
<meta name="citation_publication_date" content="2020">{pdf_meta}<title>An output</title></head><body>
<main><h1 class="title">An output</h1><p>Abstract of the output.</p>{files}</main>
<footer class="footer"><div class="content has-text-centered"><p class="footer-links">
<strong>Durham Research Online (DRO)</strong> Powered by <a href="https://worktribe.com">Worktribe</a> |
<a href="https://durham-repository.worktribe.com/accessibility">Accessibility</a></p></div></footer>
{ABOUT_DIALOG}
</body></html>"""


def test_metadata_only_output_has_no_licence():
    assert parse_page(worktribe_page(1174567), "pmh", OUTPUT_URL.format(1174567))["license"] is None


def test_output_with_a_file_but_no_stated_licence_has_none():
    page = worktribe_page(1117658, files=file_block(1117658))
    parsed = parse_page(page, "pmh", OUTPUT_URL.format(1117658))
    assert parsed["license"] is None
    assert any(u["content_type"] == "pdf" for u in parsed["urls"])


@pytest.mark.parametrize("url, licence", [
    ("http://creativecommons.org/licenses/by-nc-nd/4.0/", "cc-by-nc-nd"),
    ("http://creativecommons.org/licenses/by-nc/4.0/", "cc-by-nc"),
    ("https://creativecommons.org/licenses/by/4.0/", "cc-by"),
])
def test_the_outputs_own_licence_stays(url, licence):
    page = worktribe_page(1117904, files=file_block(1117904, licence_url=url))
    assert parse_page(page, "pmh", OUTPUT_URL.format(1117904))["license"] == licence


def test_the_dialog_alone_read_as_cc_by_before_the_fix():
    from parseland_lib.legacy_parse_utils.pdf import find_normalized_license
    assert find_normalized_license(ABOUT_DIALOG) == "cc-by"
