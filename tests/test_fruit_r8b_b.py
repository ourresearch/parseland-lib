"""Round 8b fruit fixes (oxjob #2239, phase 2): existing misses on big hosts found on the practice draws' random pages.

Markup is cut down from stored pages of the dev and check1 draws.
"""
from parseland_lib.parse import parse_page

LWW_OG = '<meta property="og:url" content="https://journals.lww.com/wajr/fulltext/2022/02000/x.2.aspx">'


def _lww(byline, notes):
    paras = "".join(notes)
    return (f'<html><head>{LWW_OG}</head><body><section id="ejp-article-authors"><p id="P7">{byline}</p>'
            f'<section><a href="#" id="ejp-article-authors-link"> Author Information </a></section></section>'
            f'<div class="ejp-article-authors-info-holder">{paras}</div></body></html>')


def _affs(html, url="https://journals.lww.com/x"):
    out = parse_page(html.encode(), "doi", url)
    return [(a["name"], [x["name"] if isinstance(x, dict) else x for x in a.get("affiliations") or []])
            for a in out["authors"]]


EMAIL = ('<span><a href="/cdn-cgi/l/email-protection#2d40" onclick="javascript:window.open(\'mailto:x@y.org\');'
         'return false"><span class="__cf_email__" data-cfemail="a1cc">[email&#160;protected]</span></a></span>')


# --- LWW: lines that are not affiliations -------------------------------------------------------------------------

def test_lww_labelled_correspondence_note_is_not_an_affiliation():
    # b076d792: "Address for correspondence: Dr. <name>, <address>. E-mail: ..." was added to the author (twice).
    html = _lww("Aybar, Mustafa Devran; Turna, Onder<sup>1</sup>",
                ['<p id="">Department of Radiology, Private Medigold Sultan Hospital, Istanbul, Turkey</p>',
                 '<p id=""><sup>1</sup>Department of Radiology, Mehmet Akif Ersoy Training and Research Hospital, '
                 'Istanbul, Turkey</p>',
                 f'<p id="cor1"><strong>Address for correspondence:</strong> Dr. Mustafa Devran Aybar, Department of '
                 f'Radiology, Private Medigold Sultan Hospital, Istanbul, Turkey. E-mail: {EMAIL}</p>',
                 '<p id="">This is an open-access article distributed under the terms of the Creative Commons.</p>'])
    assert _affs(html) == [
        ("Aybar, Mustafa Devran", ["Department of Radiology, Private Medigold Sultan Hospital, Istanbul, Turkey"]),
        ("Turna, Onder", ["Department of Radiology, Mehmet Akif Ersoy Training and Research Hospital, Istanbul, "
                          "Turkey"])]


def test_lww_unmarked_author_before_a_marked_one_keeps_byline_order_and_marks():
    # d8bd87ec: an unmarked author mid-byline stopped the reading of marks, so every later author lost theirs; the
    # correspondence note ("Correspondence to <name>, ...") was the only unmarked line left and went to them.
    html = _lww("Alalawi, Luay H.<sup>a</sup>; Dookhan, Christina M.<sup>b</sup>; Alchokhachi, Zahra; "
                "Ghanem, Ahmed<sup>a</sup>; Roy, Sion<sup>a</sup>",
                ['<p id=""><sup>a</sup>The Lundquist Institute, Harbor-UCLA Medical Center, Torrance, California</p>',
                 '<p id=""><sup>b</sup>Cardiology Division, Massachusetts General Hospital, Boston, Massachusetts</p>',
                 '<p id="">Received 13 December 2021 Accepted 9 April 2022</p>',
                 f'<p id="c1">Correspondence to Luay H. Alalawi, MD, Department of Cardiology, The Lundquist '
                 f'Institute, 1209 W 220th St, Torrance, CA 90502, USA, Tel: +4805248911; e-mail: {EMAIL}</p>'])
    lund = "The Lundquist Institute, Harbor-UCLA Medical Center, Torrance, California"
    assert _affs(html) == [
        ("Alalawi, Luay H.", [lund]),
        ("Dookhan, Christina M.", ["Cardiology Division, Massachusetts General Hospital, Boston, Massachusetts"]),
        ("Alchokhachi, Zahra", []),
        ("Ghanem, Ahmed", [lund]),
        ("Roy, Sion", [lund])]


def test_lww_unlabelled_address_with_email_naming_an_author_is_not_an_affiliation():
    # 95c9161c: the corresponding author's postal address with an e-mail, no label.
    html = _lww("Valente, Denis Souto M.D.; Padoin, Alexandre Vontobel Ph.D.",
                ['<p id="">From the School of Medicine, Pontifical Catholic University of Rio Grande do Sul.</p>',
                 f'<p id="">Denis Souto Valente, M.D., Verissimo de Amaral 580-1704, Porto Alegre, Brazil 91360-470, '
                 f'{EMAIL}</p>'])
    aff = "the School of Medicine, Pontifical Catholic University of Rio Grande do Sul."
    assert _affs(html) == [("Valente, Denis Souto M.D.", [aff]), ("Padoin, Alexandre Vontobel Ph.D.", [aff])]


def test_lww_disclosure_sentence_is_not_an_affiliation():
    # 7d53ce35: "The author has disclosed no conflicts of interest." was the only line and became the affiliation.
    html = _lww("Mains, Cheryl MBA, BSN, RN, ONC, CNOR",
                ['<p id="">The author has disclosed no conflicts of interest.</p>'])
    assert _affs(html) == [("Mains, Cheryl MBA, BSN, RN, ONC, CNOR", [])]


def test_lww_inline_marked_departments_drop_the_joining_and():
    # c6cf0886: "Departments of <sup>1</sup>Nuclear Medicine, <sup>2</sup>Psychiatry and <sup>3</sup>Tracer ..."
    html = _lww("TAKANO, A.<sup>1</sup>; KOBAYASHI, J.<sup>2</sup>; KATOH, C.<sup>3</sup>",
                ['<p id="P_ID_1">Departments of <sup>1</sup>Nuclear Medicine, <sup>2</sup>Psychiatry and '
                 '<sup>3</sup>Tracer Kinetics, Hokkaido University School of Medicine, Sapporo, Japan</p>',
                 f'<p id="P_ID_2">*Address all correspondence to Dr Nagara Tamaki, Department of Nuclear Medicine, '
                 f'Hokkaido University School of Medicine, Sapporo, Japan. e-mail: {EMAIL}</p>'])
    assert _affs(html) == [
        ("TAKANO, A.", ["Nuclear Medicine"]),
        ("KOBAYASHI, J.", ["Psychiatry"]),
        ("KATOH, C.", ["Tracer Kinetics, Hokkaido University School of Medicine, Sapporo, Japan"])]


def test_lww_affiliation_with_an_email_but_no_author_name_is_kept():
    # Look-alike: an affiliation line that carries an e-mail but names no byline author stays an affiliation.
    html = _lww("Smith, John MD<sup>1</sup>",
                [f'<p id=""><sup>1</sup>Department of Surgery, University of Iowa, Iowa City, IA. E-mail: {EMAIL}</p>'])
    assert _affs(html)[0][1] and _affs(html)[0][1][0].startswith("Department of Surgery, University of Iowa")


def test_lww_affiliation_that_mentions_and_mid_line_is_kept_whole():
    # Look-alike: "and" inside an affiliation (not left by a mark) stays.
    html = _lww("Smith, John MD<sup>1</sup>",
                ['<p id=""><sup>1</sup>Department of Obstetrics and Gynecology, University of Iowa</p>'])
    assert _affs(html) == [("Smith, John MD", ["Department of Obstetrics and Gynecology, University of Iowa"])]


def test_lww_letter_mark_lists_and_repeated_symbols_are_read_whole():
    # 0f153af2: "Chen, Chun-Yu<sup>a,b,c,*</sup>" lost a, b and c; 89175919: "**" read as "*" twice.
    html = _lww("Kuo, Li-Kai<sup>a</sup>; Chen, Chun-Yu<sup>a,b,c,*</sup>; Saraf, K.K.<sup>**</sup>",
                ['<p id=""><sup>a</sup>Department of Orthopaedics, Kaohsiung Veterans General Hospital</p>',
                 '<p id=""><sup>b</sup>College of Nursing, Meiho University</p>',
                 '<p id=""><sup>c</sup>Department of Occupational Therapy, Shu-Zen Junior College</p>',
                 '<p id=""><sup>**</sup>Associate Professor, Orthopaedics, Peoples Medical College, Bhopal MP</p>',
                 f'<p id="c1"><sup>*</sup><strong>Address correspondence.</strong> Dr. Chun-Yu Chen, Department of '
                 f'Orthopaedics, Kaohsiung. E-mail: {EMAIL}</p>'])
    assert _affs(html) == [
        ("Kuo, Li-Kai", ["Department of Orthopaedics, Kaohsiung Veterans General Hospital"]),
        ("Chen, Chun-Yu", ["Department of Orthopaedics, Kaohsiung Veterans General Hospital",
                           "College of Nursing, Meiho University",
                           "Department of Occupational Therapy, Shu-Zen Junior College"]),
        ("Saraf, K.K.", ["Associate Professor, Orthopaedics, Peoples Medical College, Bhopal MP"])]


# --- DIGIBIB record pages (Americanae, Hispana): authors and PDF from the record panels -----------------------------

_DIGIBIB_HEAD = ('<meta content="Americanae. Sistema de Difusión" name="DC.title"/>'
                 '<meta content=" Biblioteca de la Agencia Española de Cooperación Internacional para el Desarrollo '
                 '(AECID)" name="DC.creator"/>'
                 '<meta content="http://americanae.aecid.es/americanae/" name="DC.identifier" scheme="DCTERMS.URI"/>'
                 '<meta content="http://americanae.aecid.es/americanae/" property="og:url"/>')


def _xml_field(name, text):
    return (f'<li class="xml_element"><p><span class="xml_element_mark"><span class="xml_element_name">field</span> '
            f'<span class="attribute_name">name</span><span class="attribute_value">{name}</span></span>'
            f'<span class="xml_text">{text}</span></p></li>')


def _xml_element(name, children):
    return (f'<li class="xml_element expandible"><p class="xml_element_mark expandible_header">'
            f'<span class="xml_element_name">element</span> <span class="attribute_name">name</span>'
            f'<span class="attribute_value">{name}</span></p><ol class="expandible">{children}</ol></li>')


def _bundle(bundle, fmt, url):
    return _xml_element("bundle", _xml_field("name", bundle) + _xml_element(
        "bitstreams", _xml_element("bitstream", _xml_field("name", "a.pdf") + _xml_field("format", fmt)
                                   + _xml_field("url", url))))


def _digibib(rows, xoai=""):
    dl = "".join(f"<dt>{label}: </dt>" + "".join(f"<dd>{v}</dd>" for v in values) for label, values in rows)
    return (f'<html><head>{_DIGIBIB_HEAD}</head><body><div class="formato_ficha"><div id="paneles_ficha">'
            f'<div class="tab_panel" id="panel_ficha_dc"><h2>Ficha</h2><div class="tab_content"><dl>{dl}</dl></div>'
            f'</div><div class="tab_panel" id="panel_xoai"><ol class="xml_data">{xoai}</ol></div></div></div>'
            f'</body></html>')


def _pmh(html):
    return parse_page(html.encode(), "pmh", None)


def test_digibib_authors_from_the_record_rows():
    # f064379e, 1f0c44f7, f0120cdb, 6cbfd60a, 108bc14c, 76175756: the record's "Autor/Productor" rows, cleaned
    html = _digibib([("Título", ["Natural Language Explanation Model for Decision Trees"]),
                     ("Autor/Productor", ["Silva, Jesús", "Berrocal,Alexánder", "Tufik, Sergio [UNIFESP]",
                                          "Aldar, Henrique, 1986-", "Pezoa, R., Kuleshov, Serguey Vasilievievich",
                                          "Oxhorn, Philip; Catedrático-investigador de la Universidad McGill, Canadá",
                                          "sem informação", "0000-0002-2991-7678"]),
                     ("Editor", ["Institute of Physics Publishing"])])
    assert [a["name"] for a in _pmh(html)["authors"]] == [
        "Silva, Jesús", "Berrocal, Alexánder", "Tufik, Sergio", "Aldar, Henrique", "Pezoa, R.",
        "Kuleshov, Serguey Vasilievievich", "Oxhorn, Philip"]


def test_digibib_no_authors_when_a_row_cannot_be_split_into_names():
    # Look-alike: "Smith, John, Jr." has three parts that do not pair: no author rather than a cut name
    html = _digibib([("Autor/Productor", ["Smith, John, Jr.", "Doe, Jane"])])
    assert _pmh(html)["authors"] == []


def test_digibib_portal_creator_is_not_an_author_without_the_record_panel():
    # Look-alike: the portal's own DC block alone (no record panel) still gives no author (round 8)
    html = f'<html><head>{_DIGIBIB_HEAD}</head><body><p>Americanae</p></body></html>'
    assert _pmh(html)["authors"] == []


def test_digibib_pdf_from_the_original_bitstream():
    # aef4dc82: the DSpace source's ORIGINAL bundle lists the PDF; the thumbnail and text bundles are not it
    html = _digibib([("Autor/Productor", ["Adriano, E A"])],
                    xoai=_bundle("THUMBNAIL", "image/jpeg", "http://repositorio.unicamp.br/jspui/bitstream/R/1/5/a.jpg")
                    + _bundle("ORIGINAL", "application/pdf",
                              "http://repositorio.unicamp.br/jspui/bitstream/REPOSIP/194975/1/pmed_11285493.pdf"))
    assert _pmh(html)["urls"][0] == {
        "url": "http://repositorio.unicamp.br/jspui/bitstream/REPOSIP/194975/1/pmed_11285493.pdf",
        "content_type": "pdf"}


def test_digibib_no_pdf_from_a_localhost_bitstream():
    # 9cd4c956: the source exports its own "http://localhost:8080/..." address
    html = _digibib([("Autor/Productor", ["Augustin, Juliana O."])],
                    xoai=_bundle("ORIGINAL", "application/pdf",
                                 "http://localhost:8080/xmlui/bitstream/123456789/22871/1/artigo.pdf"))
    assert _pmh(html)["urls"] == []


def test_digibib_pdf_from_one_ojs_galley_when_the_format_is_pdf():
    # 9844f994: "Relación" holds the OJS galley, "Formato" says application/pdf
    galley = "http://revistas.pucp.edu.pe/index.php/historica/article/view/154/151"
    html = _digibib([("Relación", [f'<a class="enlace_externo" href="{galley}">{galley}</a>']),
                     ("Autor/Productor", ["Rodríguez Garrido, José A."]), ("Formato", ["application/pdf"])])
    assert _pmh(html)["urls"][0] == {"url": galley, "content_type": "pdf"}


def test_digibib_no_pdf_from_two_galleys_or_without_a_pdf_format():
    # 1905406d: two galleys and nothing says which is the PDF; and a galley with no format row
    g1 = "https://revistas.unitru.edu.pe/index.php/SSMM/article/view/1626/2329"
    g2 = "https://revistas.unitru.edu.pe/index.php/SSMM/article/view/1626/2339"
    two = _digibib([("Relación", [f'<a href="{g1}">{g1}</a>', f'<a href="{g2}">{g2}</a>']),
                    ("Formato", ["application/pdf"])])
    no_format = _digibib([("Relación", [f'<a href="{g1}">{g1}</a>'])])
    assert _pmh(two)["urls"] == [] and _pmh(no_format)["urls"] == []


# --- Zenodo: record pages' JSON-LD creators -----------------------------------------------------------------------

def _zenodo(creators, og="https://zenodo.org/records/2089937", tags=""):
    import json
    ld = json.dumps({"@context": "http://schema.org", "@type": "https://schema.org/ScholarlyArticle",
                     "creator": creators, "name": "Primitive Secret Societies", "description": "n/a"})
    return (f'<html><head><meta property="og:url" content="{og}"/><meta name="citation_title" '
            f'content="Primitive Secret Societies"/>{tags}<script type="application/ld+json">{ld}</script></head>'
            f'<body><h1>Primitive Secret Societies</h1></body></html>')


def test_zenodo_record_page_keeps_its_creators_without_affiliations():
    # 5e5397e5 (oai:zenodo.org): the Zenodo parser read the creator, then was passed over for having no affiliation
    html = _zenodo([{"@type": "Person", "familyName": "Chamberlain", "givenName": "A. F.",
                     "name": "Chamberlain, A. F."}])
    assert [a["name"] for a in _pmh(html)["authors"]] == ["Chamberlain, A. F."]


def test_zenodo_placeholder_creator_is_no_author():
    # 4aa9dec1: the only creator is the placeholder "&Na;,"
    html = _zenodo([{"@type": "Person", "familyName": "&Na;", "givenName": "", "name": "&Na;,"}])
    assert _pmh(html)["authors"] == []


def test_zenodo_doi_page_takes_affiliations_from_its_json_ld_creators():
    # 1d7bcf91: reached by its DOI, the citation_author tags give the names and the JSON-LD the affiliations
    tags = ('<meta name="citation_author" content="EKPO, GODWIN MFON"/>'
            '<meta name="citation_author" content="UDOH, UNWANA NICHOLAS"/>')
    html = _zenodo([{"@type": "Person", "name": "EKPO, GODWIN MFON",
                     "affiliation": "Department of Economics, Ritman University, Nigeria"},
                    {"@type": "Person", "name": "UDOH, UNWANA NICHOLAS",
                     "affiliation": "Department of Management, Ritman University, Nigeria"}],
                   og="https://zenodo.org/record/7186853", tags=tags)
    out = parse_page(html.encode(), "doi", "https://doi.org/10.5281/zenodo.7186853")
    assert [(a["name"], [x["name"] for x in a["affiliations"]]) for a in out["authors"]] == [
        ("EKPO, GODWIN MFON", ["Department of Economics, Ritman University, Nigeria"]),
        ("UDOH, UNWANA NICHOLAS", ["Department of Management, Ritman University, Nigeria"])]


def test_zenodo_affiliation_fill_needs_the_same_person():
    # Look-alike: a JSON-LD creator who is not on the parsed byline gives no one an affiliation
    tags = '<meta name="citation_author" content="Smith, John"/>'
    html = _zenodo([{"@type": "Person", "name": "Doe, Jane", "affiliation": "University of Iowa"}],
                   og="https://zenodo.org/record/1", tags=tags)
    out = parse_page(html.encode(), "doi", "https://doi.org/10.5281/zenodo.1")
    assert [(a["name"], a["affiliations"]) for a in out["authors"]] == [("Smith, John", [])]


# --- SpringerLink reference-work entries: the opening of an entry is not its abstract -------------------------------

def _springer_entry(url, body, description="Most sediments undergo some degree of deformation after deposition. "
                                           "But the deformation is not always visible."):
    return (f'<html><head><meta property="og:url" content="{url}"/><link rel="canonical" href="{url}"/>'
            f'<meta property="og:type" content="Paper"/>'
            f'<meta name="description" content="{description}"/><meta property="og:description" '
            f'content="{description}"/><meta name="citation_title" content="Deformation of sediments"/>'
            f'<meta name="citation_publisher" content="Springer, Dordrecht"/></head><body>{body}</body></html>')


def test_springer_reference_entry_without_abstract_section_has_no_abstract():
    # f81fb8c6: an encyclopedia entry with an Introduction and no Abstract section; its description is its opening
    html = _springer_entry("https://link.springer.com/referenceworkentry/10.1007/3-540-31079-7_60",
                           '<section data-title="Introduction"><h2>Introduction</h2><p>Most sediments undergo some '
                           'degree of deformation after deposition. But the deformation is not always visible.</p>'
                           '</section>')
    out = parse_page(html.encode(), "doi", "https://link.springer.com/referenceworkentry/10.1007/3-540-31079-7_60")
    assert out["abstract"] is None


def test_springer_reference_entry_with_abstract_section_keeps_it():
    # Look-alike: aeff6f27, an entry that prints an Abstract section
    text = ("Spasticity is the most common motor disorder in cerebral palsy. It is managed with oral drugs, botulinum "
            "toxin injections and surgery, chosen by the child's goals and the pattern of tone.")
    html = _springer_entry("https://link.springer.com/referenceworkentry/10.1007/978-3-319-50592-3_41-1",
                           f'<section data-title="Abstract"><div class="c-article-section__content"><p>{text}</p>'
                           f'</div></section>', description=text)
    out = parse_page(html.encode(), "doi",
                     "https://link.springer.com/referenceworkentry/10.1007/978-3-319-50592-3_41-1")
    assert out["abstract"] and out["abstract"].startswith("Spasticity is the most common")


def test_springer_chapter_without_abstract_section_is_not_touched():
    # Look-alike: a book chapter (not a reference entry) keeps whatever its readers find
    html = _springer_entry("https://link.springer.com/chapter/10.1007/978-3-030-30018-0_1052",
                           '<section data-title="Introduction"><h2>Introduction</h2><p>Most sediments undergo some '
                           'degree of deformation after deposition. But the deformation is not always visible.</p>'
                           '</section>')
    out = parse_page(html.encode(), "doi", "https://link.springer.com/chapter/10.1007/978-3-030-30018-0_1052")
    assert out["abstract"]


def test_springer_reference_entry_with_a_german_abstract_section_keeps_it():
    # Look-alike: 651d0bb0, a Kindler entry whose abstract section is titled "Zusammenfassung"
    text = ("Von dem auf zwei Bände angelegten geschichtsphilosophischen Werk wurde 1922 lediglich der erste fertig "
            "gestellt. Das Buch ist eine Reihe selbständiger Abhandlungen aus den Jahren 1916 bis 1922.")
    html = _springer_entry("https://link.springer.com/referenceworkentry/10.1007/978-3-476-05728-0_20330-1",
                           f'<section data-title="Zusammenfassung"><h2>Zusammenfassung</h2>'
                           f'<div class="c-article-section__content"><p>{text}</p></div></section>', description=text)
    out = parse_page(html.encode(), "doi",
                     "https://link.springer.com/referenceworkentry/10.1007/978-3-476-05728-0_20330-1")
    assert out["abstract"] and out["abstract"].startswith("Von dem auf zwei")


def test_zenodo_record_creator_field_with_marks_and_several_people_is_no_author_list():
    # d86a88c2 (check1, unlabelled): one creator field "V.Viswanath1*, T.Niranjan Reddy1"
    html = _zenodo([{"@type": "Person", "name": "V.Viswanath1*, T.Niranjan Reddy1"}])
    assert _pmh(html)["authors"] == []


def test_lww_unmarked_byline_fragment_still_stops_the_mark_reading():
    # ca2f7d34 (check1, unlabelled): "...; FACG,<sup>" is no "Family, Given" name: read as before
    html = _lww("Carr-Locke, David L. MD<sup>1</sup>; FACG, <sup>2</sup>; Tomizawa, Yutaka MD<sup>3</sup>",
                ['<p id=""><sup>1</sup>Department of Medicine, Weill Cornell Medicine</p>',
                 '<p id=""><sup>2</sup>Division of Gastroenterology, Mount Sinai</p>',
                 '<p id=""><sup>3</sup>Department of Medicine, University of Washington</p>'])
    names = [n for n, _ in _affs(html)]
    assert names[0] == "Carr-Locke, David L. MD" and names.count("FACG,") <= 1


def test_digibib_bodies_events_and_placeholders_are_no_authors():
    # check1 / dev unlabelled pages: a museum, a congress, a church office, "Anonymous", "Autores varios"; a role
    # suffix is dropped
    html = _digibib([("Autor/Productor", ["Guggenheim Bilbao Museoa", "Congreso Cientifico 4º 1909 Santiago de Chile",
                                          "Església Catòlica. Papa (1352-1362 : Innocenci VI), autor", "Anonymous",
                                          "Autores varios", "Zukerfeld, Mariano - Autor/a"])])
    assert [a["name"] for a in _pmh(html)["authors"]] == ["Zukerfeld, Mariano"]
