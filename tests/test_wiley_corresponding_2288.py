"""
Wiley: an e-mail (or one shared note) under every author is not a corresponding mark; a note naming an author is
(oxjob #2288).

Older Wiley/Blackwell pages have no <p class="author-type">Corresponding Author</p> tags. The parser read a mailto,
an "E-mail:" line or a "correspondence" note in an author's block as a mark, but these pages give every author an
e-mail, or repeat one shared note in every author's block, so ~600 sampled works flagged every author. #1791 gold
label-v1: an e-mail shown for every author marks no one; a note naming one author marks that author even when the
template repeats it in every block; a page that names every author keeps every flag. Fragments are cut down from the
stored pages named in each test.
"""
from bs4 import BeautifulSoup

from parseland_lib.parse import parse_page
from parseland_lib.publisher.parsers.wiley import Wiley

URL = "https://onlinelibrary.wiley.com/doi/10.1111/example"


def author(name, *blocks, mailto=None, tag=False):
    email = (f'<ul class="rlist sm-account"><li class="sm-account__item"><a class="sm-account__link" '
             f'href="mailto:{mailto}"><span>{mailto}</span></a></li></ul>') if mailto else ""
    author_type = '<p class="author-type">Corresponding Author</p>' if tag else ""
    paras = "".join(f"<p>{b}</p>" for b in blocks)
    return (f'<span class="accordion-tabbed__tab-mobile accordion__closed"><a class="author-name" href="#">'
            f'<span>{name}</span></a><div class="author-info accordion-tabbed__content">{author_type}'
            f'<p class="author-name">{name}</p>{email}{paras}'
            f'<a class="moreInfoLink" href="#">Search for more papers by this author</a></div></span>')


def html(authors, header_block=""):
    block = f'<div class="article-header__correspondence-to">{header_block}</div>' if header_block else ""
    return (f'<html><head><meta property="og:url" content="{URL}"/>'
            f'<meta property="og:site_name" content="Wiley Online Library"/>'
            f'<meta name="citation_title" content="A study"/></head><body>'
            f'<div class="loa-authors">{"".join(authors)}</div>{block}</body></html>')


def wiley_corr(authors, header_block=""):
    out = Wiley(BeautifulSoup(html(authors, header_block), "lxml")).parse()
    return [a.name for a in out["authors"] if a.is_corresponding]


def page_corr(authors, header_block=""):
    out = parse_page(html(authors, header_block).encode(), "doi", URL)
    return [a["name"] for a in out["authors"] if a["is_corresponding"]]


CF = '<a class="__cf_email__" data-cfemail="00" href="/cdn-cgi/l/email-protection">[email&#160;protected]</a>'


def test_mailto_on_every_author_marks_no_one():
    # 10.1002/tax.513002: each author's own address behind the envelope
    authors = [author("Dan H. Nicolson", "Botany MRC-166, Smithsonian Institution, Washington, D.C.",
                      mailto="nicolson.dan@nmnh.si.edu"),
               author("John McNeill", "Royal Botanic Garden, Edinburgh, U.K.", mailto="j.mcneill@rbge.org.uk")]
    assert wiley_corr(authors) == []
    assert page_corr(authors) == []


def test_email_line_in_every_authors_affiliation_marks_no_one():
    # 10.1111/j.1467-971x.2010.01636.x: "E-mail:" closes each author's own affiliation
    authors = [author("STEFANIE PILLAI", "University of Malaya, 50603 Kuala Lumpur, Malaysia. E-mail: stefanie@um.edu.my"),
               author("GERALD KNOWLES", "Lingenium Sdn. Bhd, Kuala Lumpur, Malaysia. E-mail: g.knowles@lancaster.ac.uk")]
    assert wiley_corr(authors) == []


def test_one_shared_email_repeated_in_every_block_marks_no_one():
    # 10.1111/j.1365-2044.2005.04391.x: the same address and protected e-mail under both authors
    note = f"Poole Hospital NHS Trust Poole, UK E-mail: {CF}"
    authors = [author("S. A Townley", note), author("W. Ashton", note)]
    assert wiley_corr(authors) == []
    assert page_corr(authors) == []


def test_shared_note_naming_one_author_marks_that_author():
    # 10.1111/j.1750-3841.2006.00108.x: Food Science's "Direct inquiries to author X" repeated in every block
    note = ("Author Stoltenberg is with PrimusLabs.com, Santa Maria, CA 93455; Authors Getty and Phebus are with Kansas "
            "State Univ., Manhattan, KS 66506. Direct inquiries to author Getty (E-mail: kgetty@ksu.edu).")
    authors = [author("Stacey K. Stoltenberg", note), author("Kelly J. K. Getty", note), author("Randall K. Phebus", note)]
    assert wiley_corr(authors) == ["Kelly J. K. Getty"]
    assert page_corr(authors) == ["Kelly J. K. Getty"]


def test_name_before_a_parenthesised_corresponding_author_marks_it():
    # 10.1111/j.1439-037x.2006.00182.x
    note = (f"Authors' addresses: Dr M. Hirata (corresponding author; e-mail: {CF} ), Dr Y. Sugimoto and Dr K. Fukuyama, "
            "Faculty of Agriculture, University of Miyazaki, Japan; Dr Y. Ogawa, National Institute, Tsukuba, Japan")
    authors = [author("M. Hirata", note), author("Y. Ogawa", note), author("Y. Sugimoto", note)]
    assert wiley_corr(authors) == ["M. Hirata"]


def test_shared_bio_tying_its_one_email_to_a_name_marks_that_author():
    # 10.1111/j.1747-1567.2010.00618.x
    note = ('<i>J. Hay (</i> <a href="mailto:jenny.hay@agilent.com">jenny.hay@agilent.com</a> <i>) and P. Agee are '
            "application engineers with Agilent Technologies. E. Herbert is a postdoctoral researcher.</i>")
    authors = [author("J. Hay", note), author("P. Agee", note), author("E. Herbert", note)]
    assert wiley_corr(authors) == ["J. Hay"]


def test_shared_note_listing_every_authors_email_marks_no_one():
    # 10.1111/j.1571-9979.2001.tb00239.x: one bio note, an e-mail for each author
    note = ("Maria R. Volpe is Professor of Sociology at John Jay College, New York; email: mvolpe@jjay.cuny.edu. "
            "David Chandler is Professor of Sociology at the University of Hawaii; email: dchandle@hawaii.edu.")
    authors = [author("Maria R. Volpe", note), author("David Chandler", note)]
    assert wiley_corr(authors) == []


def test_corresponding_line_in_one_block_marks_only_that_author():
    # 10.1111/j.1467-9663.2008.00475.x: every author has an e-mail, one block says "Corresponding author:"
    authors = [author("CAROLINE A. RODENBURG", "Ernst and Young, Amsterdam. E-mail: caroline.rodenburg@nl.ey.com"),
               author("PETER NIJKAMP", "Corresponding author: Department of Spatial Economics, VU University, "
                                       "Amsterdam. E-mail: pnijkamp@feweb.vu.nl"),
               author("HENRI L.F. DE GROOT", "VU University, Amsterdam. E-mail: hgroot@feweb.vu.nl")]
    assert wiley_corr(authors) == ["PETER NIJKAMP"]


def test_note_naming_every_author_keeps_every_flag():
    # 10.1002/jmv.25740 shape, without author-type tags: "Correspondence A and B" in both blocks
    note = (f"Correspondence Qi Lu, MD, PhD and Yuan Shi MD, PhD, Department of Neonatology, Children's Hospital, "
            f"Chongqing 400014, China. Email: {CF} (Q. L.) and {CF} (Y. S.)")
    authors = [author("Qi Lu MD, PhD", "Children's Hospital, Chongqing, China", note),
               author("Yuan Shi MD, PhD", "Children's Hospital, Chongqing, China", note)]
    assert wiley_corr(authors) == ["Qi Lu MD, PhD", "Yuan Shi MD, PhD"]


def test_header_block_offering_either_author_keeps_every_flag():
    # 10.1111/j.1523-5378.2007.00529.x: "Reprint request to: A ... or B ..."
    authors = [author("Shin Maeda", "Asahi Life Foundation, Tokyo, Japan"),
               author("Andreas F. Mentis", "Institut Pasteur Hellenique, Athens, Greece")]
    block = (f"Reprint request to : Shin Maeda, Division of Gastroenterology, 1-6-1 Marunouchi, Tokyo, Japan. E-mail: "
             f"{CF} or Andreas F Mentis, Laboratory of Medical Microbiology, Athens, Greece. E-mail: {CF}")
    assert wiley_corr(authors, block) == ["Shin Maeda", "Andreas F. Mentis"]


def test_header_block_listing_every_authors_address_marks_no_one():
    # 10.1111/j.0021-9886.2004.00526.x
    authors = [author("Mike Artis", "European University Institute"), author("Andreas Beyer", "European Central Bank")]
    block = (f"Mike Artis Department of Economics European University Institute Florence, Italy email: {CF} "
             f"Andreas Beyer European Central Bank Frankfurt am Main, Germany email: {CF}")
    assert wiley_corr(authors, block) == []


def test_header_block_initial_must_start_the_given_name():
    # 10.1111/j.1600-0447.2005.00511.x: 'Jean Addington' is J. Addington, not D. Addington
    authors = [author("J. Addington", "Centre for Addiction and Mental Health, Toronto"),
               author("D. Addington", "Foothills Hospital, Calgary")]
    block = f"Jean Addington, Centre for Addiction and Mental Health, 250 College Street, Toronto, Canada. E-mail: {CF}"
    assert wiley_corr(authors, block) == ["J. Addington"]


def test_header_block_cue_names_the_corresponding_author_among_all_addresses():
    # 10.1046/j.1365-2362.2001.00874.x: every author in the address list, then "Correspondence to:"
    authors = [author("S. Fischer", "Klinikum Grosshadern, Munich"), author("G. Meyer", "Klinikum Grosshadern, Munich")]
    block = ("Department of Medicine II (S. Fischer), Department of Surgery (G. Meyer), Klinikum Grosshadern, Munich, "
             "Germany.Correspondence to: Sven Fischer, PhD, Department of Medicine II, Marchioninistrasse 15, Munich")
    assert wiley_corr(authors, block) == ["S. Fischer"]


def test_author_type_tag_on_some_authors_is_unchanged():
    authors = [author("Alice First", "Dept A, Univ X", mailto="alice@example.org"),
               author("Bob Second", "Dept B, Univ X", mailto="bob@example.org", tag=True)]
    assert wiley_corr(authors) == ["Bob Second"]


def test_author_type_tag_on_some_authors_beats_email_lines_on_the_others():
    # 10.1111/j.1654-1103.2009.01086.x: the tagged author has the envelope, the others an "E-mail" line
    authors = [author("Tara K. Rajaniemi", "University of Massachusetts Dartmouth, USA", mailto="t@umassd.edu", tag=True),
               author("Roy Turkington", "University of British Columbia, Vancouver", "E-mail royt@interchange.ubc.ca"),
               author("Deborah Goldberg", "University of Michigan, Ann Arbor", "E-mail degold@umich.edu")]
    assert wiley_corr(authors) == ["Tara K. Rajaniemi"]


def test_untagged_authors_own_corresponding_note_still_marks_it():
    # 10.1002/jssc.201400802 (gold): Hwang is tagged, Kim's block alone says "Additional corresponding author"
    kim = author("Ho Kyoung Kim", "Korea Institute of Oriental Medicine, Daejeon", mailto="hkkim@kiom.re.kr").replace(
        '<a class="moreInfoLink"', 'Additional corresponding author: Dr. Ho Kyoung Kim,E-mail: <a class="moreInfoLink"')
    authors = [author("In Jin Ha", "Korea Basic Science Institute, Seoul"), kim,
               author("Geum-Sook Hwang", "Korea Basic Science Institute, Seoul", "E-mail : gshwang@kbsi.re.kr",
                      mailto="gshwang@kbsi.re.kr", tag=True)]
    assert wiley_corr(authors) == ["Ho Kyoung Kim", "Geum-Sook Hwang"]


def test_author_type_tag_on_every_author_with_emails_keeps_every_flag():
    # 10.1111/fcre.12453: Wiley tags both authors "Corresponding Author"
    authors = [author("Gregory Firestone", mailto="gfiresto@usf.edu", tag=True),
               author("Sharon Press", mailto="sharon.press@mitchellhamline.edu", tag=True)]
    assert wiley_corr(authors) == ["Gregory Firestone", "Sharon Press"]
