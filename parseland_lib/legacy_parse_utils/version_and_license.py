import json
import re
import unicodedata
from urllib.parse import unquote

from lxml import etree

from parseland_lib.legacy_parse_utils.pdf import get_pdf_in_meta, \
    trust_publisher_license, find_normalized_license, site_license_covers_articles, _host_in, _CC_SHORTHAND_RE
from parseland_lib.legacy_parse_utils.strings import normalized_strings_equal, \
    get_tree


# Site chrome, never the article's own licence statement: a site-wide "content of this site is licensed CC BY" footer
# turned paywalled pages into cc-by (scientific.net, crossref.org defunct-DOI page, 2026-09). Kept on SITE_LICENSE_HOSTS,
# whose footer licenses every article (pdf.py).
SITE_CHROME_FINDERS = [
    "//footer",
    "//nav",
    "//*[@role='contentinfo']",
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' footer ')"
    " or contains(@class, 'footer-') or contains(@class, '-footer') or contains(@class, '_footer')"
    " or @id='footer' or starts-with(@id, 'footer') or contains(@id, '-footer') or contains(@id, '_footer')]",
]

# Where the page's own content is (#2239): HTML allows one <main> (or role="main") per page and never inside a
# <footer> or <nav>, so an element that holds it is not site chrome, whatever its tag or name says.
_MAIN_CONTENT = etree.XPath("//main | //*[@role='main'][not(self::nav or self::footer)]")


# A statement in site chrome that speaks of the page's article, not of the site (#2239, round 2): "This is an open
# access article distributed under ...", "This article is licensed under ...". Journals print it once, in the footer
# of every article page (4 dev pages, all labelled with that licence). The sentence is kept; the rest of the footer
# still goes. What stays chrome, on purpose:
# - "This work is licensed under ..." (the Creative Commons chooser's badge text, pasted into site footers, where "this
#   work" is the site): 26 dev pages whose label is no licence against 1 with one;
# - "All published work is licensed under ...", "<Journal> is licensed under ...", "content of this site ...": the
#   labels go both ways on the same wording (clausiuspress.com with a licence, an iMedPub journal without), so that
#   is a decision, not a rule. Decided for Open Journal Systems pages on 16 Nov 2026: _OJS_SUBJECT below.
# The licence must be named in the same sentence, so "Share this article" beside a site badge keeps nothing, and a
# condition ("if this article is published under ...") is not a statement.
_ARTICLE_STATEMENT = re.compile(
    r"\bthis\s+(?:is\s+an?\s+)?(?:open[\s\-]?access\s+)?article\s+"
    r"(?:(?:is\s+)?(?:licen[sc]ed|distributed|published|(?:made\s+)?available)\s+)?under"
    r"\b(?:[^.]|\.(?=\S)){0,300}", re.IGNORECASE)
_CONDITION_BEFORE = re.compile(r"\b(?:if|when|where|whether|unless)\s+$", re.IGNORECASE)
# One exact mention of a Creative Commons licence: its link, its full name (with its conditions or its version number)
# or its short name. The bare family name does not count: pages write "Creative Commons Attribution License (CC-By-NC)"
# over a by-nc link, and that names one licence, not two. Nor does a public-domain dedication: beside an article's
# licence it is about something else (the metadata).
_EXACT_LICENSE_MENTION = re.compile(
    r"creativecommons\.org/licenses/[a-z\-]+"
    r"|creative\s+commons\s+attribution"
    r"(?:(?:[\s\-]+(?:non[\s\-]*commercial|share[\s\-]*alike|non?[\s\-]*deriv\w*))+|\s+\d\.\d)"
    r"|" + _CC_SHORTHAND_RE.pattern, re.IGNORECASE)
_INLINE_TAGS = frozenset(('a', 'span', 'b', 'strong', 'i', 'em', 'u', 'small', 'font', 'sup', 'sub'))


# a Creative Commons badge names its licence in the picture's address: .../l/by-nc-sa/4.0/88x31.png
_LICENSE_BADGE = re.compile(r"(?:i\.creativecommons\.org|licensebuttons\.net)/l/(by(?:-[a-z]{2})*)/", re.IGNORECASE)


def _licenses_named(element):
    """The licences the element names exactly, in its text, its links and its licence badges together
    (find_normalized_license alone gives only the first by rank)."""
    named = " ".join([" ".join(element.itertext())] + [link.get('href') or '' for link in element.iter('a')])
    licenses = {find_normalized_license(mention.group(0)) for mention in _EXACT_LICENSE_MENTION.finditer(named)}
    for image in element.iter('img'):
        if badge := _LICENSE_BADGE.search(image.get('src') or ''):
            licenses.add(find_normalized_license("cc-" + badge.group(1)))
    return licenses - {None}


def _article_statements(section):
    """The sentences in a site-chrome element that license the page's article itself (_ARTICLE_STATEMENT). Whether
    they stand is decided for the page's chrome as a whole (_clear_site_chrome): not when it names several licences.
    """
    text = " ".join(section.itertext())
    if 'rticle' not in text and 'RTICLE' not in text:
        return []  # nearly every nav and footer: skip the whitespace pass
    text = re.sub(r"\s+", " ", text)
    return [m.group(0) for m in _ARTICLE_STATEMENT.finditer(text)
            if find_normalized_license(m.group(0))
            and not _CONDITION_BEFORE.search(text, max(0, m.start() - 12), m.start())]


# An Open Journal Systems journal states its licence once, in the footer of every page (#2239, round 5; charter § 6,
# 16 Nov 2026 09:30: on OJS pages a footer statement that licenses the journal or its articles is the article's
# licence; it replaces the line of 13 Nov). #2267 read all 17,118 OJS pages whose licence a re-parse dropped: 94%
# carry a journal-wide Creative Commons statement in the footer, the journals' own copyright pages say the same, and
# most article PDFs state no licence, so the footer is the only statement there is.
# On an OJS page a statement in site chrome counts for the article when the statement itself names
# - the work ("This work is licensed under ...", the Creative Commons chooser's sentence and its translations:
#   "Ciptaan disebarluaskan di bawah Lisensi ...", "Esta obra está bajo una Licencia ..."),
# - the journal ("This journal is licensed ...", "Jurnal ini ...", or the journal's own title, short title or address
#   as the page's meta tags give them: "KONSTAN (Jurnal Fisika ...) is licensed under ..."), or
# - its articles ("All articles published in this journal are licensed ...", "Dergimizde yayımlanan makaleler ...").
# The licence must be named in the same sentence, after the subject. What does not count:
# - a bare "Licensed under ..." or a badge alone: it names nothing;
# - a statement about the site, its pages or its metadata, or a credit for an image, a theme or an icon set
#   (_NOT_THE_JOURNAL between the subject and the licence, or "the website of" before the subject): "The Jurnal
#   Tabarru' site and its metadata are licensed under CC BY-SA", "The content of this site is licensed ...", "Sabine's
#   Gull by A. Reago is licensed under CC BY";
# - a licence that covers only some of the journal's articles (_ONLY_SOME_ARTICLES): "after June 2018", an embargo;
# - chrome that names several different licences, in whichever blocks (_clear_site_chrome): a journal statement and
#   another licence's badge beside it ("<Journal> is licensed under ... ShareAlike" under a by-nc badge) do not say
#   which is the journal's.
# The article's own statement wins: the footer's is read only when the rest of the page names no licence and its
# text does not speak of Creative Commons at all, or says the footer's own licence in words (_says_in_words;
# page_potential_license_text).
# Round 6 (same charter line; the loop's dev pages whose stored licence round 5 still dropped): the content of the
# journals of a site of several journals ("El contenido de las Revistas de este sitio ..."); the journal's name
# without its accents, and from the journal's feed links where the page has no tags (an OJS 2 issue page);
# "NonDerivative" for "NoDerivatives". Still out, waiting for a decision: statements with no subject at all
# ("Utgiven av <publisher> | Open Access enligt CC-BY 4.0", "Excepto donde se indique ... se publica bajo ...").
_OJS_SUBJECT = re.compile(
    r"\b(?:this|the)\s+(?:work|journal|publication)\b|\bwork\s+is\s+(?:licen[sc]ed|distributed)\b"
    r"|\b(?:all|the|these|our|published)\s+(?:of\s+)?(?:the\s+)?(?:published\s+)?"
    r"(?:articles|papers|manuscripts|works?)\b"
    r"|\barticles\s+(?:published|in)\b|\bjournal\s+(?:content|papers|articles)\b|\bopen[\s\-]?access\s+journal\b"
    r"|\bcontents?\s+of\s+(?:this|the)\s+journal\b"
    # Indonesian and Malay
    r"|\b(?:jurnal|karya|ciptaan|artikel|tulisan|naskah)\s+ini\b"
    r"|\b(?:ciptaan|jurnal|karya)\s+(?:ini\s+)?di(?:sebarluaskan|lisensikan)\b"
    r"|\b(?:semua|seluruh)\s+artikel\b|\bartikel\s+(?:dalam|pada|di)\s+jurnal\b"
    # Spanish and Portuguese
    r"|\best[ae]\s+(?:obra|trabajo|trabalho|revista|publicaci[oó]n|peri[oó]dico)\b"
    # "el contenido de la revista", and of every journal of the site: "el contenido de las revistas de este sitio"
    # (round 6: a site of several journals licenses the content of its journals, which is not the site's own content;
    # "el contenido de este sitio" names no journal). Before "los contenidos", which would end the subject too early.
    r"|\b(?:(?:el|los|o|os)\s+)?conte(?:ni|[uú])dos?\s+d(?:[eoa]s?|el|est[ea]s?|ess[ea]s?)\s+(?:(?:la|esta)s?\s+)?"
    r"(?:revistas?|peri[oó]dicos?)\b(?:\s+de\s+este\s+(?:sitio|portal)\b|\s+deste\s+(?:site|s[ií]tio|portal)\b)?"
    r"|\b(?:los|os)\s+(?:art[ií]culos|artigos|trabajos|trabalhos|contenidos|conte[uú]dos)\b"
    # French, Italian, German, Turkish
    r"|\bce(?:tte|\(tte\))?\s+(?:œuvre|oeuvre|revue|travail)\b|\bles\s+articles\b|\bquest['’]\s?opera\b"
    r"|\bquesta\s+(?:opera|rivista)\b|\bdieses\s+werk\b|\bdiese\s+zeitschrift\b"
    r"|\bbu\s+(?:eser|çalışma|dergi)\b|\byay[ıi][mn]lanan\s+makaleler\b"
    # Arabic, Russian, Ukrainian: "this work", "this journal" (round 8: Ukrainian "цей твір", "ця робота"; the class
    # [яей] took one letter, so "цей" never matched)
    r"|هذا\s+(?:العمل|المصنف)|هذه\s+المجلة|\bэто\s+произведение\b|\bц(?:ей|я|е)\s+(?:робота|твір|журнал)\b"
    # Persian: "this journal", "this work" (Sinaweb and OJS journals in Iran; round 8)
    r"|این\s+(?:نشریه|مجله|اثر)"
    # "Articles are published under ..." (round 8)
    r"|\barticles\s+(?:are|is)\s+(?:published|licen[sc]ed|distributed)\b"
    # Russian and Polish: the journal's materials, the journal, its articles (round 7)
    r"|\bматериалы\s+журнала\b|\bстатьи\s+журнала\b|\bвсе\s+статьи\b|\bczasopism[oa]\b|\bartyku[łl]y\b",
    re.IGNORECASE)
# Off Open Journal Systems (#2239, round 7; charter § 6, 17 Nov 2026 08:20, rule 2): a footer sentence counts when it
# names the journal, its articles or its materials, on any host ("This is an open access journal, is following CC-BY
# license"; "Материалы журнала доступны по лицензии ..."; "Czasopismo jest udostępnione ... (CC-BY-NC-ND)"; "<Journal>
# is licensed under ..."). Not "this work" or "this publication", in any language (rule 3: off OJS the Creative
# Commons chooser's "This work is licensed under ..." is the site's, f77943e): _OJS_SUBJECT without those.
_JOURNAL_SUBJECT = re.compile(
    r"\b(?:this|the)\s+journal\b"
    r"|\b(?:all|the|these|our|published)\s+(?:of\s+)?(?:the\s+)?(?:published\s+)?(?:articles|papers|manuscripts)\b"
    r"|\barticles\s+(?:published|in)\b|\bjournal\s+(?:content|papers|articles|materials)\b|\bopen[\s\-]?access\s+journal\b"
    r"|\b(?:contents?|materials?)\s+of\s+(?:this|the)\s+journal\b|\bmaterials\s+published\s+in\b"
    r"|\bjurnal\s+ini\b|\b(?:semua|seluruh)\s+artikel\b|\bartikel\s+(?:dalam|pada|di)\s+jurnal\b"
    r"|\best[ae]\s+(?:revista|peri[oó]dico)\b"
    r"|\b(?:(?:el|los|o|os)\s+)?conte(?:ni|[uú])dos?\s+d(?:[eoa]s?|el|est[ea]s?|ess[ea]s?)\s+(?:(?:la|esta)s?\s+)?"
    r"(?:revistas?|peri[oó]dicos?)\b(?:\s+de\s+este\s+(?:sitio|portal)\b|\s+deste\s+(?:site|s[ií]tio|portal)\b)?"
    r"|\b(?:los|os)\s+(?:art[ií]culos|artigos)\b"
    r"|\bcette\s+revue\b|\bles\s+articles\b|\bquesta\s+rivista\b|\bdiese\s+zeitschrift\b"
    r"|\bbu\s+dergi\b|\byay[ıi][mn]lanan\s+makaleler\b|هذه\s+المجلة|\bц(?:ей|я)\s+журнал\b"
    r"|\bматериалы\s+журнала\b|\bстатьи\s+журнала\b|\bвсе\s+статьи\b|\bczasopism[oa]\b|\bartyku[łl]y\b"
    # round 8: Persian "this journal" (Sinaweb: "این نشریه تحت مجوز ... می باشد"); "Articles are published under ...";
    # a conference's own materials, "All LREC proceedings (...) are licenced under ..."
    r"|این\s+(?:نشریه|مجله)|\barticles\s+(?:are|is)\s+(?:published|licen[sc]ed|distributed)\b"
    r"|\ball\s+(?:[\w\-]+\s+){0,2}?proceedings\b",
    re.IGNORECASE)
_NOT_THE_JOURNAL_WORDS = (
    r"\b(?:web|websites?|webpages?|sites?|sitios?|sítios?|situs|laman|portal|platform|plataforma|pages?|p[aá]ginas?"
    r"|metadat\w*|metadad\w*|themes?|templates?|plugins?|software|logos?|images?|imagen|imagem|photos?|fotos?"
    r"|pictures?|gambar|icons?|fonts?|cover|banner|design|map)\b")
_NOT_THE_JOURNAL = re.compile(_NOT_THE_JOURNAL_WORDS, re.IGNORECASE)
# ... or just before the subject: "The website of this journal is licensed under ..."
_OF_THE_SUBJECT = re.compile(
    _NOT_THE_JOURNAL_WORDS + r"\s+(?:of|for|on|de|del|da|do|dari)\s+(?:the\s+)?$", re.IGNORECASE)
_ONLY_SOME_ARTICLES = re.compile(
    r"\bembargo|\b(?:after|since|from|until|before|prior\s+to|starting|beginning|as\s+of|between|desde|a\s+partir\s+de"
    r"|hasta|antes\s+de|ap[oó]s|at[eé]|sejak|mulai|sebelum|setelah)\b[^.]{0,30}?\b(?:19|20)\d\d\b", re.IGNORECASE)
# where a statement's licence starts: the family name, a licence link or a short name
_LICENSE_START = re.compile(r"creative\s*commons|" + _CC_SHORTHAND_RE.pattern, re.IGNORECASE)
_LICENSE_HINT = re.compile(r"ommons|(?<![A-Za-z0-9])CC[\s\-]*BY", re.IGNORECASE)
_LICENSING_WORD = re.compile(
    r"licen[sc]|lisensi|lisans|licença|lizenz|distribu|disebarluaskan|publi|under|bajo|\bsob\b|bawah|below|operates"
    r"|adopt|adot|terms|رخص|enligt|unter|лиценз|доступн|udost", re.IGNORECASE)
# On OJS a licence line with no subject counts too (#2239, round 7; charter § 6, 17 Nov 2026 08:20, rule 1): the footer
# is the journal's or its portal's own statement ("Utgiven av <publisher> | Open Access enligt Creative Commons CC-BY
# 4.0", publicera.kb.se; "Excepto donde se indique explícitamente se publica bajo la siguiente licencia ...", a portal
# of journals; "Published by <publisher> under the terms of ..."; "Licensed under ..."). _licence_lines reads them:
# - the line licenses: a licensing word before the licence (_LINE_VERB);
# - with no subject of its own: no subject in words (_OJS_SUBJECT) in its sentence, and nothing "is/are licensed"
#   before the licence ("Sabine's Gull by A. Reago is licensed under ...", "<another journal> is licensed under ..."
#   name something else; _HAS_OWN_SUBJECT);
# - not about something else: no word for the site, its pages or metadata, a theme, the software, a picture or an icon
#   anywhere in its sentence (_NOT_THE_JOURNAL), no condition, no date range;
# - not a badge: the licence is named in the text, not only in a link's or a picture's address.
# Two licences in the chrome still license nothing (_clear_site_chrome).
# (verbs and prepositions only: the licence's own name, "Licença Creative Commons ..." beside a badge, says nothing;
# round 8: Italian "È edita da <press> ed è distribuita con Licenza ...", ojs.unica.it)
_LINE_VERB = re.compile(
    r"\b(?:licen[sc]ed|licen[sc]iad[oa]s?|licenziat[oaie]|lizenziert|\w*lisensikan|lisansl\w*|distributed"
    r"|distribu[ií]d[oa]s?|distribu[ée]e?s?|distribuit[oaie]|published|publica|publican|publicad[oa]s?|pubblicat[oaie]"
    r"|under|bajo|sob|unter|sous|enligt|bawah|terms|t[ée]rminos|termos|available|disponibles?|dispon[ií]ve(?:l|is))\b",
    re.IGNORECASE)
_HAS_OWN_SUBJECT = re.compile(
    r"[^\W_]\S*\s+(?:is|are|was|were|has\s+been|have\s+been|est[aá]n?|es|son|é|são|ist|sind|est|sont|jest|s[aą])\s",
    re.IGNORECASE)
_CONDITION_WORD = re.compile(r"\b(?:if|when|whether|unless|wenn|falls)\b", re.IGNORECASE)
# a line that starts with its verb after a full stop in the same block: the full stop ended an abbreviation, and the
# subject is before it ("... Hybrid Access Journals by Journal Press Inc. is licensed under ...")
_STARTS_WITH_VERB = re.compile(
    r"\s*(?:is|are|was|were|has\s+been|have\s+been|est[aá]n?|es|son|é|são|ist|sind|est|sont|jest|s[aą])\s",
    re.IGNORECASE)
_ADDRESS = re.compile(r"https?://\S*|\b[\w\-]+(?:\.[\w\-]+)+/\S*")
_OTHER_WORD = re.compile(r"[^\W\d_]{3,}")
_FLOW_TAGS = _INLINE_TAGS | {'br', 'img'}
_SENTENCE_FROM = re.compile(r"(?:[^.]|\.(?=\S)){0,300}")
_JOURNAL_NAME_TAGS = ('citation_journal_title', 'citation_journal_abbrev', 'dc.source', 'dc.source.uri')
# what an address ends with, or a title starts with, that names no journal
_NO_NAME = frozenset(('journal', 'journals', 'jurnal', 'revista', 'home', 'index', 'index.php', 'ojs', 'main',
                      'article', 'articles', 'issue', 'about'))
# PKP's software for books and preprints shares OJS's templates (is_ojs_page is true for both); a press's or a
# preprint server's footer is not a journal's
_OTHER_PKP_SOFTWARE = re.compile(r"open\s+(?:monograph\s+press|preprint\s+systems)", re.IGNORECASE)


# A journal named by its title in words where the page has no journal meta tags (round 8; rule 2: Drupal journal sites,
# "The Technology Innovation Management Review is published under a ...", "GSC Advanced Research and Reviews (GSCARR)
# is licensed under a ..."): a run of capitalised words, directly before "is published/licensed/distributed under",
# that holds a word only a periodical's title holds (_JOURNAL_WORD). Never after "by" (a credit: "<theme> by <name>"),
# and a lower-case word ends the run ("The Journal of X website is licensed ...": the website).
_TITLE_TOKEN = r"(?:[A-Z][\w’'\-]*|\([A-Z][\w\-]*\)|of|and|for|in|on|the|&|de|y|e)"
_JOURNAL_TITLE_LICENSED = re.compile(
    r"(?<![\w.’'])(?<!\bby\s)[A-Z][\w’'\-]*(?:\s+" + _TITLE_TOKEN + r"){1,12}"
    r"(?=\s+is\s+(?:published|licen[sc]ed|distributed)\s+under\b)")
_JOURNAL_WORD = re.compile(r"\b(?:Journal|Review|Reviews|Revista|Annals|Bulletin|Quarterly|Transactions|Letters"
                           r"|Proceedings|Magazine|Archives|Jurnal|Zeitschrift|Rivista|Revue)\b")
# A statement cut in two by markup (round 8: "<p>by INKLUSI: Journal of Disability Studies is licensed under a</p>
# <p><a ...>Creative Commons Attribution-NonCommercial 4.0 International License</a></p>"): a block that ends on its
# licensing preposition goes on in the next block.
_ENDS_UNDER = re.compile(
    r"\b(?:under|bajo|sob|unter|sous|enligt|bawah|terms\s+of)"
    r"(?:\s+(?:a|an|the|una?|uma?|la|el|einer?|der|une?))?\s*$", re.IGNORECASE)


def _fold(text):
    """The text without its Latin accents, character for character, so positions in it are positions in `text`: a
    footer in English names "Agronomía Mesoamericana" as "Agronomia Mesoamericana" (#2239, round 6)."""
    if text.isascii():
        return text
    return "".join(base if ord(c) > 127 and (base := unicodedata.normalize('NFD', c)[0]).isascii() else c
                   for c in text)


# the feeds OJS's web feed plugin lists in the head of every page of a journal:
#   <link rel="alternate" type="application/atom+xml" title="<journal> (atom+xml)"
#         href="<the journal's address>/gateway/plugin/WebFeedGatewayPlugin/atom">
_OJS_FEED = re.compile(r"^(https?://.+?)/gateway/plugin/WebFeedGatewayPlugin/", re.IGNORECASE)
_FEED_KIND = re.compile(r"\s*\((?:atom|rss|rdf)\+xml\)\s*$", re.IGNORECASE)


# A journal whose tags give its title only in another script names itself in English in its footer: Sinaweb's
# "Literary Text Research is licensed under ..." on the pages of "متن پژوهی ادبی", "Amirkabir Journal of Civil
# Engineering is licensed under ..." on "نشریه مهندسی عمران امیرکبیر" (#2239, round 7; the charter's rule 2 names
# these footers, labelled with the licence on 2 of 2 pages). Then a title in Latin capitals, two words or more, directly
# before "is licensed under", is the journal's: never "This ...", "The ...", a site's or an author's ("... by Name").
_LATIN_TITLE_LICENSED = (
    r"(?-i:(?<![\w.])(?<!\bby\s)(?!(?:This|The|All|Our|Content|Site|Website|Except|Unless|Copyright|Licensed)\b)"
    r"[A-Z][a-z]+(?:\s+(?:of|and|for|in|on|&|[A-Z][a-z]+)){1,9})(?=\s+is\s+licen[sc]ed\s+under\b)")


def _journal_names(tree, ojs=True):
    """A pattern for the journal's own names on an OJS page, from the meta tags OJS writes, the page's title and the
    journal's feed links: its title, its short title, the short name a title starts with ("KOVALEN: Jurnal Riset
    Kimia", "KONSTAN (Jurnal Fisika ...)"), its address and the address's last part (".../index.php/JKKI"). The names
    are without their accents, for a text read through _fold. None when the page gives none; False when the page is
    not a journal's at all.
    Off OJS (`ojs` false; round 7) only the journal's title and short title in the meta tags count: another site's
    title ("<post> | <blog>") and addresses name the site, not a journal; and when those tags give no title in Latin
    letters, a Latin title before "is licensed under" (_LATIN_TITLE_LICENSED)."""
    patterns, titles = set(), []

    def add(name):
        words = re.findall(r"\w+", _fold(name))
        if len("".join(words)) >= 3 and name.strip().lower() not in _NO_NAME:
            patterns.add(r"(?<!\w)" + r"[\W_]+".join(map(re.escape, words)) + r"(?!\w)")

    def add_title(title):
        add(title)
        add(re.split(r":|\s\(|\s[-–—]\s", title, maxsplit=1)[0])

    def add_address(url):
        address = re.sub(r"^https?://(?:www\.)?|/(?:index)?/?$", "", url, flags=re.IGNORECASE)
        if '/' in address:  # a journal's address on its site, never a bare host
            patterns.add(re.escape(address))
            add(address.rsplit('/', 1)[1])

    for meta in tree.iter('meta'):
        name, content = (meta.get('name') or '').lower(), (meta.get('content') or '').strip()
        if name == 'generator' and _OTHER_PKP_SOFTWARE.match(content):
            return False
        if name not in _JOURNAL_NAME_TAGS:
            continue
        if re.match(r"https?://", content, re.IGNORECASE):
            if ojs:
                add_address(content)
        else:
            add_title(content)
            titles.append(content)
    if not ojs:
        if patterns and not any(re.search(r"[A-Za-z]", title) for title in titles):
            patterns.add(_LATIN_TITLE_LICENSED)  # the tags name the journal only in another script
        return re.compile("|".join(sorted(patterns)), re.IGNORECASE) if patterns else None
    title = tree.findtext('.//title') or ''
    if '|' in title:  # OJS titles its pages "<article or issue> | <journal>"; an issue page has no other name
        add(title.rsplit('|', 1)[1])
    # An OJS 2 issue page has neither the tags nor the journal in its title ("Vol 5, No 1 (2017)"): its head still
    # lists the journal's own feeds (round 6). A site of several journals lists its own at .../index.php/index, which
    # names no journal.
    for link in tree.iter('link'):
        feed = _OJS_FEED.match((link.get('href') or '').strip())
        if feed and feed.group(1).rsplit('/', 1)[1].lower() not in _NO_NAME:
            add_address(feed.group(1))
            add_title(_FEED_KIND.sub('', link.get('title') or ''))
    return re.compile("|".join(sorted(patterns)), re.IGNORECASE) if patterns else None


def _flow_text(element):
    """An element's own running text: its text and that of its inline markup, with the address of each Creative Commons
    licence link on both sides of the link's text (the text may end the sentence, or start the statement). A
    block-level child ends the sentence; its text is its own."""
    parts = []

    def walk(node):
        parts.append(node.text or '')
        for child in node:
            if isinstance(child.tag, str) and child.tag in _FLOW_TAGS:
                href = child.get('href') if child.tag == 'a' else None
                href = f" {href.strip()} " if href and 'creativecommons.org/licenses/' in href else ''
                parts.append(href or (' ' if child.tag == 'br' else ''))  # a line break parts two words
                walk(child)
                parts.append(href)
            elif isinstance(child.tag, str):
                parts.append(' . ')
            parts.append(child.tail or '')

    walk(element)
    return "".join(parts)


def _journal_statements(section, names, ojs=True):
    """The sentences in a site-chrome element of an OJS page that license the work, the journal or its articles
    (_OJS_SUBJECT, or one of the journal's own `names`), each with its licence link's address; and its licence lines
    with no subject (_licence_lines).
    Off OJS (`ojs` false; round 7, rule 2): only sentences that name the journal, its articles or its materials
    (_JOURNAL_SUBJECT, or the journal's title from the meta tags), in words: the licence named in the text, and after a
    journal's title a licensing word ("<Journal>: <badge>" is a badge). `names`: _journal_names, or a function that
    returns it (read only for a section that names a licence)."""
    if not _LICENSE_HINT.search(" ".join(section.itertext())) and not any(
            'creativecommons.org/licenses/' in (link.get('href') or '') for link in section.iter('a')):
        return []  # nearly every nav and footer
    if callable(names):
        names = names()
    if names is False:
        return []  # a press's or a preprint server's page
    statements = []
    for element in section.iter(tag=etree.Element):
        if (element.tag in _FLOW_TAGS and element is not section) or element.tag in ('script', 'style'):
            continue  # inline markup is read with its block
        text = _flow_text(element)
        following = element.getnext()
        if following is not None and isinstance(following.tag, str) and following.tag not in _FLOW_TAGS \
                and _ENDS_UNDER.search(text):
            text = f"{text} {_flow_text(following)}"  # the statement goes on in the next block (round 8)
        if not _LICENSE_HINT.search(text):
            continue
        text = re.sub(r"\s+", " ", text)
        found = len(statements)
        subjects = [(subject, False) for subject in (_OJS_SUBJECT if ojs else _JOURNAL_SUBJECT).finditer(text)] + [
            (subject, True) for subject in (names.finditer(_fold(text)) if names else ())]
        if not ojs and not names and 'under' in text:  # off OJS, the journal's title in words where no tag names it
            subjects += [(subject, True) for subject in _JOURNAL_TITLE_LICENSED.finditer(text)
                         if _JOURNAL_WORD.search(subject.group(0))]
        block = []  # the licences the block itself names, read once and only when needed
        for subject, is_name in subjects:
            # the subject, and the rest of its sentence (a name may hold a full stop: "Rilce. Revista de ...")
            # (cut from `text`: a name is found in the text without its accents, at the same place)
            statement = text[subject.start():subject.end()] + _SENTENCE_FROM.match(text, subject.end()).group(0)
            statement = _with_block_licence(statement, element, block)
            subject_end = subject.end() - subject.start()
            license_start = _LICENSE_START.search(statement, subject_end)
            if not license_start or not (find_normalized_license(statement) or '').startswith('cc-by'):
                continue
            # The journal's name is followed by the statement at once ("<Journal> (e-ISSN ...) by <publisher> is
            # licensed under", "<Journal>: <badge>"), never by an address and some other statement, nor by other
            # words and a badge ("View <Journal> Stats <badge>").
            between = re.sub(r"https?://\S*", " ", statement[subject_end:license_start.start()])
            if license_start.start() - subject_end > (120 if is_name else 200) or (
                    is_name and not _LICENSING_WORD.search(between) and (_OTHER_WORD.search(between) or not ojs)):
                continue
            # off OJS the licence is named in words, never by a badge or a link's address alone
            if not ojs and not _LICENSE_START.search(_ADDRESS.sub(" ", statement), subject_end):
                continue
            # (a subject in words is searched after its end: "las revistas de este sitio" are journals, not a site)
            if _NOT_THE_JOURNAL.search(statement, 0 if is_name else subject_end, license_start.start()) \
                    or _ONLY_SOME_ARTICLES.search(statement) \
                    or _CONDITION_BEFORE.search(text, max(0, subject.start() - 12), subject.start()) \
                    or _OF_THE_SUBJECT.search(text, max(0, subject.start() - 30), subject.start()):
                continue
            statements.append(statement)
        if ojs and len(statements) == found:
            statements.extend(_licence_lines(text))
    return statements


def _with_block_licence(statement, element, block):
    """A statement that names Creative Commons in words this reader cannot read ("Este trabalho está licenciado sob uma
    Licença Creative Commons Atribuição 4.0 Internacional", its badge link before it, the address after "visite:")
    with the address of the one licence its block names, when the words spell that licence's terms (_TERMS_IN_WORDS:
    English, Spanish, Portuguese); otherwise the statement as it is (round 8). `block`: a list that keeps the block's
    licences once read."""
    if find_normalized_license(statement) or not _CREATIVE_COMMONS.search(statement):
        return statement
    if not block:
        block.append(_licenses_named(element))
    if len(block[0]) != 1:
        return statement  # none, or several: the words do not say which
    license = next(iter(block[0]))
    if 'cc-' + "".join(term for term, words in _TERMS_IN_WORDS if words.search(statement)) != license:
        return statement
    return f"{statement} https://creativecommons.org/licenses/{license[3:]}/"


def _licence_lines(text):
    """An OJS footer block's licence lines with no subject of their own (round 7, rule 1: see _LINE_VERB), each its
    sentence from its start to its end."""
    lines, read = [], set()
    for license_start in _LICENSE_START.finditer(text):
        start = text.rfind('. ', 0, license_start.start()) + 1
        if start in read:
            continue  # the same sentence
        read.add(start)
        sentence = text[start:license_start.start()] + _SENTENCE_FROM.match(text, license_start.start()).group(0)
        words = _ADDRESS.sub(" ", sentence)  # the licence named in words: never only by an address (a badge)
        named = _LICENSE_START.search(words)
        if not named or not (find_normalized_license(sentence) or '').startswith('cc-by'):
            continue
        before = words[:named.start()]  # what the line says before it names the licence
        if not _LINE_VERB.search(before) \
                or _HAS_OWN_SUBJECT.search(before) \
                or (start and _STARTS_WITH_VERB.match(before)) \
                or _OJS_SUBJECT.search(sentence) \
                or _NOT_THE_JOURNAL.search(words) \
                or _ONLY_SOME_ARTICLES.search(sentence) \
                or _CONDITION_WORD.search(before):
            continue
        lines.append(sentence.strip())
    return lines


_CREATIVE_COMMONS = re.compile(r"creative\s*commons", re.IGNORECASE)


def _speaks_of_creative_commons(tree):
    """True when the page's visible text names Creative Commons (an address, an alt text or a script does not)."""
    visible = []
    for element in tree.iter():
        if isinstance(element.tag, str) and element.tag not in ('script', 'style') and element.text:
            visible.append(element.text)
        if element.tail:
            visible.append(element.tail)
    return _CREATIVE_COMMONS.search(" ".join(visible)) is not None


# A licence's terms in words, as an article's copyright block spells them where it names no licence this reader can
# read (#2239, round 6): PKP's default notice in translation, "with the work registered under the attribution,
# non-commercial and no-derivative license from Creative Commons" (revistas.ucr.ac.cr), "con el trabajo registrado
# con la licencia de atribución de Creative Commons". English, Spanish and Portuguese.
_TERMS_IN_WORDS = (
    ('by', re.compile(r"attribution|atribuci[oó]n|reconocimiento|atribui[cç][aã]o", re.IGNORECASE)),
    ('-nc', re.compile(r"non?[\s\-]*com+ercial|n[aã]o[\s\-]*comercial", re.IGNORECASE)),
    ('-nd', re.compile(r"non?[\s\-]*deriv|sin[\s\-]*(?:obras?[\s\-]*)?deriva|sem[\s\-]*deriva", re.IGNORECASE)),
    ('-sa', re.compile(r"share[\s\-]*alike|compartir[\s\-]*igual|compartilha[\s\-]*igual", re.IGNORECASE)),
)


def _says_in_words(tree, license):
    """True when every sentence of the page that speaks of Creative Commons spells the terms of `license`, and no
    others, in words. Such a sentence is never read as a licence on its own: it only lets the journal's footer
    statement of the same licence stand (page_potential_license_text)."""
    for element in tree.iter(tag=etree.Element):
        if element.tag in _FLOW_TAGS or element.tag in ('script', 'style'):
            continue  # inline markup is read with its block
        text = _flow_text(element)
        if not _CREATIVE_COMMONS.search(text):
            continue
        text = re.sub(r"\s+", " ", text)
        for mention in _CREATIVE_COMMONS.finditer(text):
            end = text.find('. ', mention.end())
            sentence = text[text.rfind('. ', 0, mention.start()) + 1:len(text) if end < 0 else end]
            terms = [term for term, words in _TERMS_IN_WORDS if words.search(sentence)]
            if 'cc-' + "".join(terms) != license:  # also when it spells none, or both -nd and -sa
                return False
    return True


def _clear_all_but_main(element, mains, holders):
    """Clear what a <nav> or <footer> holds beside the page's main content; True when anything went."""
    cleared = False
    for child in element.iterchildren(tag=etree.Element):
        if child in mains:
            continue
        if child in holders:
            cleared |= _clear_all_but_main(child, mains, holders)
        else:
            child.clear()
            cleared = True
    return cleared


# class="article-footer", "article__footer", "articleFooter": the article's footer by the page's own naming
_ARTICLE_OWN_FOOTER = re.compile(r"(?:^|\s)article[\w\-]*footer", re.IGNORECASE)
# <div id="not-footer">: a sticky-footer layout's wrapper of everything that is NOT the footer (Atmire's Open Repository
# theme wraps the whole item page in it; round 8). The finders' "-footer" matched it and cleared the item's own licence.
_NOT_FOOTER = re.compile(r"(?:^|\s)no[nt]?[\-_]footer(?:\s|$)", re.IGNORECASE)


def _clear_site_chrome(tree, journal_statements=None, ojs=True):
    """Clear the page's site chrome (SITE_CHROME_FINDERS), except chrome that holds the page; True when anything went.
    `journal_statements`: a list that takes the journal's own licence statements found in the cleared chrome
    (_journal_statements: on an Open Journal Systems page when `ojs`, by the narrower rule for other sites when not);
    they are not left in the tree.

    Site chrome that holds the page is not chrome (#2239, phase 2). The finders also match elements that wrap the
    WHOLE page, and the article's own licence went with them: arXiv's abstract pages sit in
    <div class="flex-wrap-footer"> (a sticky-footer layout), WordPress themes put footer options in the <body> class,
    and DSpace JSPUI leaves a <div> open in its header <nav>, so the parser ignores </nav> and the nav swallows <main>
    and all that follows (36 of 875 sampled pages whose stored licence the re-parse dropped; arXiv 32). So <html>,
    <body> and any element that holds the page's <main> are never cleared whole:
    - a wrapper that only has a footer-like name stays, and the real <footer>, <nav> and footer-named elements inside
      it still go, because the same finders match them on their own;
    - a real <nav>, <footer> or role=contentinfo that swallowed <main> loses everything but <main>: its own menu
      items are still chrome.
    Only structure counts. The share of the page's text an element holds, an <h1> or an <article> in it are not
    evidence of content: on short and paywalled pages the site footer is most of the text (sampled pages: an OJS
    footer with 70% of the page's visible text, another repository's with 85%, DOAJ's with 40%, OpenGrey's with
    40-60% once its inline scripts count), and site navs and footers carry <h1> logos and <article> teasers (PLOS,
    APS, Frontiers, Erudit). Sparing those would bring back the site-footer licences this rule exists to keep out.

    Round 2 (#2239), the same structure read the other way, and one wording rule:
    - a footer-named element the page itself names as the ARTICLE's, inside an <article>, is that article's own
      (<article class="article-body">...<footer class="article-footer"> with its licence line): it stays. Both are
      needed. Where it sits is not enough: doi.org's pages and some OJS themes put the SITE footer inside <main>,
      doi.org's "not found" page even inside <main><article> (5 gold pages took the site's licence when position
      alone counted);
    - a cleared element keeps the sentences that license the page's article itself (_ARTICLE_STATEMENT), as plain text.
    """
    mains = set(_MAIN_CONTENT(tree))
    holders = {ancestor for main in mains for ancestor in main.iterancestors()}
    cleared = False
    known = []

    def names():  # read once, and only for chrome that names a licence: most pages have none
        if not known:
            known.append(_journal_names(tree, ojs))
        return known[0]
    named, kept = set(), []  # the licences the cleared chrome names; the article statements left in it
    for section_finder in SITE_CHROME_FINDERS:
        for section in tree.xpath(section_finder):
            if section in mains or section.tag in ('html', 'body') \
                    or _NOT_FOOTER.search(f"{section.get('id') or ''} {section.get('class') or ''}"):
                continue  # <main class="has-footer">, <body class="ast-footer-overlay">: the content itself
            if _ARTICLE_OWN_FOOTER.search(section.get('class') or '') \
                    and next(section.iterancestors('article'), None) is not None:
                continue  # <article> ... <footer class="article-footer">: the article's own footer
            if section not in holders:
                if section.getroottree().getroot() is not tree:
                    continue  # already gone with an enclosing element cleared earlier in this pass
                statements = _article_statements(section)
                if journal_statements is not None:
                    journal_statements.extend(_journal_statements(section, names, ojs))
                named |= _licenses_named(section)
                section.clear()
                for statement in statements:
                    kept.append(etree.SubElement(section, 'p'))
                    kept[-1].text = statement
                cleared = True
            elif section.tag in ('nav', 'footer') or section.get('role') == 'contentinfo':
                cleared |= _clear_all_but_main(section, mains, holders)
    # Chrome that names different licences does not say which one is the article's: nothing in it counts, whether or
    # not each mention has a subject and whichever block each sits in (charter § 6, 16 Nov 2026). An OJS theme prints
    # "This is an open-access article distributed under ... Attribution-NonCommercial-ShareAlike ... Licensed under
    # <CC BY badge> a Creative Commons Attribution 4.0 International License" on every page of every journal that
    # uses it, whatever the journal's licence; learning-gate.com prints the two in two blocks (gold v1.4: none).
    if len(named) > 1:
        for statement in kept:
            if statement.getparent() is not None:
                statement.getparent().remove(statement)
    # ... and the journal's statements must agree with it and with each other (a statement may name its licence
    # loosely: "Creative Commons Attribution License" beside a by-nc badge)
    if journal_statements and len(named | set(map(find_normalized_license, journal_statements))) != 1:
        del journal_statements[:]
    return cleared


# A RightsLink permissions link names the licence of ONE article, the one in its contentID (#2239, round 2):
#   /servlet/linkout?type=rightslinkReprints&url=...%26contentID%3D10.1080%252F13530194.2021.1916154...%26oa%3DCC-BY-NC-ND...
# On older Taylor & Francis pages it is the only place the article's licence is named (beside an "Open access" badge),
# and its doubly URL-encoded "oa%3DCC-BY-NC-ND" stopped reading as a licence when the CC shorthands began to need
# token boundaries. On a Wiley issue page each listed article has its own link, and one open article licensed the
# issue. So the link is replaced by what it states: its decoded oa= value when its contentID is the page's own DOI,
# nothing otherwise (never the whole decoded link: its title= parameter is the article's title, which may name a
# licence). A page that names no DOI trusts none.
_RIGHTSLINK_OA = re.compile(r"(?<![A-Za-z])oa=[A-Za-z0-9\-+ ]+")
_RIGHTSLINK_CONTENT_ID = re.compile(r"contentID=(10\.\d{4,9}/[^&\s]+)", re.IGNORECASE)
_DOI_META_NAMES = {"citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi", "doi"}
_DOI_VALUE = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)


def _page_dois(tree):
    dois = set()
    for meta in tree.iter('meta'):
        if (meta.get('name') or meta.get('property') or '').lower() in _DOI_META_NAMES:
            doi = _DOI_VALUE.match((meta.get('content') or '').strip())
            if doi:
                dois.add(doi.group(1).lower())
    return dois


def _keep_own_rightslink_licence(tree):
    """Rewrite RightsLink links so only the page's own article can state a licence; True when any link changed."""
    changed, dois = False, None
    for link in tree.xpath("//a[contains(@href, 'rightslink')]"):
        href = unquote(unquote(link.get('href')))
        oa = _RIGHTSLINK_OA.search(href)
        if not oa:
            continue
        if dois is None:  # read once, and only on a page whose links name a licence
            dois = _page_dois(tree)
        content_id = _RIGHTSLINK_CONTENT_ID.search(href)
        own = content_id and content_id.group(1).lower() in dois
        link.set('href', 'rightslink ' + oa.group(0).replace('+', ' ') if own else 'rightslink')
        changed = True
    return changed


# Text that names a licence without stating the work's (#2239, round 2), dropped from the search text:
# - a JSON schema's "enum": the list of values a field MAY take. AgEcon Search (TIND) record pages define their file
#   table's licence column with every licence on offer, and each record read as cc-by-nc-nd;
# - a map's attribution ("Map data (c) OpenStreetMap contributors CC-BY-SA", in UNT Digital Library record pages);
# - an image credit: "Image by CSTAR via Wikipedia licensed under CC-BY-SA 3.0" (a schema.org image caption),
#   "Featured image by <a ...>Katherine Lynn</a> under a CC-BY-NC-ND license" (a blog post and its description),
#   "Image by Rob Palmer via iNaturalist (CC BY-NC-SA 4.0)" (an alt text). The credit ends at the next sentence,
#   and is not one when it reaches a word for the work itself before its licence.
# A map attribution or image credit runs over text and its own <a> links only (raw or escaped, as in a script once the
# tree is serialised), so on a one-line page it cannot swallow a statement in the next element.
# - a promise to license ANOTHER version (#2239, round 3): "The author will make the Author Accepted Manuscript (AAM)
#   version available under a CC BY public copyright license." Science prints this rights-retention line on articles it
#   distributes under its own "Science Journals Default License", most of them paywalled, and each read as cc-by (12 of
#   12 stored pages). Only the promise goes ("will make ... available under"): "this accepted manuscript version is
#   made available under ..." on a repository record is a statement about the item on the page and stays.
_LICENSE_OPTIONS = re.compile(r'"enum"\s*:\s*\[[^\[\]]*\]')
_ACCEPTED_MANUSCRIPT_PROMISE = re.compile(
    r"\bwill\s+make\s+the\s+(?:author\s+)?accepted\s+manuscript(?:\s*\(AAM\))?(?:\s+version)?\s+available\s+under"
    r"(?:[^.<>\"]|</?a\b[^>]*>){0,120}", re.IGNORECASE)
# its gate: case-sensitive with a literal start, so the scan is fast ("accepted" alone is on a third of all pages)
_ACCEPTED_MANUSCRIPT_HINT = re.compile(r"ccepted\s+[Mm]anuscript")
_MAP_ATTRIBUTION = re.compile(
    r"OpenStreetMap(?:\s*(?:</a>|&lt;/a&gt;))?\s*contributors"
    r"(?:</?a\b[^>]*>|&lt;/?a\b(?:(?!&gt;)[^\n])*&gt;|[^\"<>\n]){0,200}")
# cheap gate for _IMAGE_CREDIT, which would otherwise scan every page: the usual casings only
_IMAGE_CREDIT_HINTS = ("mage by", "hoto by", "icture by", "mage credit", "hoto credit")
# (round 8: or a dash before the licence, "Photo by <name> via Flickr - CC BY-SA", a blog post's description)
_IMAGE_CREDIT = re.compile(
    r"\b(?:image|photo|picture)\s+(?:by|credit)\b"
    r"(?:(?!\b(?:article|paper|work|post|text|content)\b)(?:[^\"<>]|</?a\b[^>]*>)){0,80}?"
    r"(?:\bunder\b|\(\s*CC\b|\s[\-–—]\s*CC\b)"
    r"(?:[^\"<>.]|\.(?!\s+[A-Z])){0,120}", re.IGNORECASE)
# anchored on the newline before the comment (the caller prepends one): a fixed first character keeps the scan fast
_LICENSE_IN_CODE_COMMENT = re.compile(
    r"\n[ \t]*//[^\r\n]*(?:public\s*domain|creative\s*commons)[^\r\n]*", re.IGNORECASE)


# - a subject term named "Public Domain" (round 8): SAGE Knowledge pages list the encyclopedia's whole taxonomy in a
#   script ({'type': 'NV', 'name': ' Public Domain', 'position': '614'}), and every entry read as public-domain. Only
#   a value that is the phrase alone, under a name, label, term, keyword, subject or tag key.
_TERM_NAMED_PUBLIC_DOMAIN = re.compile(
    r"""['"](?:name|label|term|keyword|subject|tag)['"]\s*:\s*['"]\s*public\s+domain\s*['"]""", re.IGNORECASE)


def _drop_code_comments_naming_a_license(tree):
    """Drop the comment lines of code scripts that name a licence ("// Appends the Public Domain image", on every
    ROSAP and CDC Stacks record page); True when any went."""
    changed = False
    for script in tree.iter('script'):
        if 'json' in (script.get('type') or '').lower():
            continue  # data, not code
        text = script.text
        if text and ('ommons' in text or 'omain' in text):
            without, dropped = _LICENSE_IN_CODE_COMMENT.subn('\n', '\n' + text)
            if dropped:
                script.text = without[1:]
                changed = True
    return changed


def _drop_non_statements(text):
    """The search text without option lists, map attributions, image credits and promises about another version; the
    same object when it has none."""
    text = _LICENSE_OPTIONS.sub('', text)
    text = _MAP_ATTRIBUTION.sub('', text)
    if any(hint in text for hint in _IMAGE_CREDIT_HINTS):
        text = _IMAGE_CREDIT.sub('', text)
    if _ACCEPTED_MANUSCRIPT_HINT.search(text):
        text = _ACCEPTED_MANUSCRIPT_PROMISE.sub('', text)
    if 'omain' in text:
        text = _TERM_NAMED_PUBLIC_DOMAIN.sub('', text)
    return text


def page_potential_license_text(page, keep_site_chrome=False, ojs_page=False, journal_footer=False):
    """`ojs_page`: an Open Journal Systems page, whose footer speaks for the journal (#2239, round 5; round 7 rule 1).
    `journal_footer`: on any other page, read a footer sentence that names the journal, its articles or its materials
    (round 7, rule 2)."""
    tree = get_tree(page)

    if tree is None:
        return _drop_non_statements(page)

    # the journal's own footer statements (#2239, rounds 5 and 7)
    journal_statements = [] if ojs_page or journal_footer else None
    section_removed = False if keep_site_chrome else _clear_site_chrome(tree, journal_statements, ojs=ojs_page)
    if 'rightslink' in page:
        section_removed |= _keep_own_rightslink_licence(tree)
    section_removed |= _drop_code_comments_naming_a_license(tree)

    bad_section_finders = [
        "//div[contains(@class, 'view-pnas-featured')]",  # https://www.pnas.org/content/114/38/10035
        "//meta[contains(@name, 'citation_reference')]",  # https://www.thieme-connect.de/products/ebooks/lookinside/10.1055/sos-SD-226-00098
        # Page-template code that looks for a CC badge is not a licence statement: SAGE's older template ships
        # `if ($('.creative-commons-badge.cc-by').length){ console.debug('... CC-BY type of article.') ...}` on every
        # article page, paywalled or not, which read as cc-by (oxjob #1794: 755 closed works turned hybrid).
        "//script[contains(., 'creative-commons-badge')]",
        # IOP's Accepted Manuscript notice for a subscription article states a future licence for the manuscript,
        # not the article's licence: "During the embargo period ... the Accepted Manuscript is fully protected by
        # copyright ... As the Version of Record of this article is going to be / has been published on a
        # subscription basis, this Accepted Manuscript will be available for reuse under a CC BY-NC-ND 4.0 licence
        # after the 12 month embargo period", with a cc-by-nc-nd.png badge in the same block. Read as the article's
        # licence it turned paywalled IOP articles into hybrid OA (oxjob #1860: 249 of 250 sampled cc-by-nc-nd IOP
        # pages). Only the subscription notice goes; the gold-OA notice ("published on a gold open access basis
        # under a CC BY 4.0 licence") and the published article's own licence block stay.
        "//div[contains(@class, 'media') or contains(@class, 'license')]"
        "[contains(normalize-space(.), 'subscription basis')]"
        "[contains(., 'Accepted Manuscript')][contains(., 'embargo')]",
    ]
    if 'component-table-of-contents' in page:
        # PubFactory book pages (Brill) print the book's table of contents on every chapter page, each chapter with
        # its own access badge and licence link, so the open chapters' CC BY links licensed every chapter of the book
        # (#2239, round 3: Intersections 97, 4 chapters open and 12 sold, all 16 read as cc-by). The item's own
        # licence link is in its header, outside this component.
        bad_section_finders.append("//div[contains(@class, 'component-table-of-contents')]")

    for section_finder in bad_section_finders:
        for bad_section in tree.xpath(section_finder):
            bad_section.clear()
            section_removed = True

    if section_removed:
        try:
            page = etree.tostring(tree, encoding=str)
        except Exception:
            pass
    text = _drop_non_statements(page)
    # The journal's footer statement is read only when the rest of the page names no licence: the article's own
    # statement wins, whatever its rank. Also when it is one this reader cannot read: an article's copyright block
    # that says "Licencia Creative Commons Atribución-NoComercial-CompartirIgual" over a dead link, above a footer
    # that says Attribution-ShareAlike (revistascientificas.filo.uba.ar, labelled by-nc-sa), gets no licence. Unless
    # what the rest of the page says of Creative Commons is the footer's own licence, term for term, in words
    # (round 6: revistas.ucr.ac.cr, labelled by-nc-nd from the article's block; the footer says the same).
    if journal_statements and find_normalized_license(text) is None and (
            not _speaks_of_creative_commons(tree)
            or _says_in_words(tree, find_normalized_license(journal_statements[0]))):
        text = f"{text}\n{journal_statements[0]}"
    return text


# ScienceDirect states the article's own licence in its page state, once per page:
#   "access":{"openAccess":<bool>,"openArchive":<bool>[,"license":"<url>"]}
# The same state also holds licences that are not the article's: the journal's self-archiving policy
# ("sa-user-license": the licence an author's accepted manuscript may carry after an embargo, CC BY-NC-ND on most
# journals) and open-research agreements ("or-agreement-license"). Read anywhere on the page, those turned
# paywalled articles into cc-by-nc-nd (oxjob #1794: 12 of 12 such dev pages).
_SD_ACCESS = re.compile(r'"access":\{([^{}]*"openAccess":\s*(?:true|false)[^{}]*)\}')
_SD_ACCESS_LICENSE = re.compile(r'"license":\s*"([^"]*)"')


def sciencedirect_article_license_text(page):
    """The ScienceDirect article's own licence statement: its licence URL, or '' when it states none.

    None when the page carries no ScienceDirect article state, so other pages keep the whole-page search.
    """
    if not page:
        return None
    access = _SD_ACCESS.search(page) if '"openAccess"' in page else None
    if access is None and '\\"openAccess\\"' in page:
        # some pages (peer-review reports, year-book articles) hold the state as an escaped JSON string:
        # \"access\":{\"openAccess\":false,...}; read it the same way, or the self-archiving licence leaks again
        access = _SD_ACCESS.search(page.replace('\\"', '"'))
    if access is None:
        return None
    license_url = _SD_ACCESS_LICENSE.search(access.group(1))
    return license_url.group(1) if license_url else ''


# IEEE Xplore document pages state the article's own access in the page's metadata object, on every template:
#   xplGlobal.document.metadata={..."isOpenAccess":false,...,"openAccessFlag":"F",...};
# An open-access article also names its licence in a "ccby-indicator" line ("Under a Creative Commons License", linked).
# The page template's stylesheet styles that banner on every page, open or not
# (".document-header-metrics-banner.ccby-document{padding-bottom:0}"), and the class name read as "cc by". IEEE pages
# fetched whole carry that stylesheet inline: 147,579 of the 148,479 parsed in the week of 2 Nov 2026 read cc-by,
# ~160K paywalled works served as hybrid open access (oxjob #2417). A stylesheet never states a licence.
_IEEE_METADATA = 'xplGlobal.document.metadata='
_IEEE_IS_OPEN_ACCESS = re.compile(r'"isOpenAccess":\s*(true|false)')
_STYLE_BLOCK = re.compile(r'<style\b[^>]*>.*?</style\s*>', re.IGNORECASE | re.DOTALL)


def ieee_article_page(page):
    """True / False: the IEEE Xplore article's metadata says it is / is not open access. None when the page carries
    no IEEE Xplore document metadata, so other pages keep the whole-page search."""
    if not page:
        return None
    start = page.find(_IEEE_METADATA)
    if start == -1:
        return None
    end = page.find('</script>', start)
    flag = _IEEE_IS_OPEN_ACCESS.search(page, start, end if end != -1 else len(page))
    return None if flag is None else flag.group(1) == 'true'


def license_search_text(page, resolved_url=None, ojs_page=False, journal_footer=False):
    """The text the licence regexes run over, on both the publisher and the repository path.

    A ScienceDirect page counts only its article's own licence statement (repository records such as Zenodo
    deposits often resolve to the ScienceDirect page, so the repository path needs the same rule), an IEEE Xplore
    page none when its metadata says the article is not open access (else the page without its stylesheets), a Taylor & Francis
    book page its product's, an ACL Anthology page the footer sentence for the paper's year, a Common Ground
    (cgscholar.com) article page its article's licenseType; any other page is
    searched whole, minus site chrome (kept on hosts whose footer licenses every article). `ojs_page`: the page is an
    Open Journal Systems page (is_ojs_page), whose footer may state the journal's own licence. `journal_footer`: any
    other page's footer may too, in a sentence that names the journal, its articles or its materials (round 7).
    """
    sd_license_text = sciencedirect_article_license_text(page)
    if sd_license_text is not None:
        return sd_license_text
    ieee_open = ieee_article_page(page)
    if ieee_open is False:
        return ''
    if ieee_open:
        page = _STYLE_BLOCK.sub('', page)
    tf_license_text = taylorfrancis_product_license_text(page)
    if tf_license_text is not None:
        return tf_license_text
    acl_license_text = acl_anthology_license_text(page, resolved_url)
    if acl_license_text is not None:
        return acl_license_text
    escholarship_text = escholarship_item_license_text(page, resolved_url)
    if escholarship_text is not None:
        return escholarship_text
    cgscholar_text = cgscholar_article_license_text(page, resolved_url)
    if cgscholar_text is not None:
        return cgscholar_text
    return page_potential_license_text(page, keep_site_chrome=site_license_covers_articles(resolved_url),
                                       ojs_page=ojs_page, journal_footer=journal_footer)


# eScholarship (escholarship.org) item pages hold the item in the page's JSON with its own licence, alphabetical keys:
#   "genre":"article","id":"53f3s8gg","index_digest":"...",...,"published":"2017","rights":null
# and, in the same JSON, the journal's navigation: every issue with ITS licence ("attrs":{...,"rights":"https://
# creativecommons.org/licenses/by-nc-nd/4.0/"}). Read anywhere, an issue's licence licensed an item that has none
# (#2239, round 8: check1 dfd279ce, "rights":null, read as cc-by-nc-nd). The item's own field is its licence; the
# page prints it as its "c-pubinfo__license" link.
_ESCHOLARSHIP_ITEM_RIGHTS = re.compile(
    r'"genre":"[^"]*","id":"[0-9a-z]{8}","index_digest":"[^"]*",(?:"[a-z_]+":(?:null|"[^"]*"|-?\d+),){0,10}?'
    r'"rights":(null|"[^"]*")')


def escholarship_item_license_text(page, resolved_url=None):
    """The eScholarship item's own licence (its "rights" address), or '' when it states none.

    None when the page is not an eScholarship item page, so other pages keep the whole-page search.
    """
    if not page or '"index_digest":' not in page or not (
            'escholarship.org' in page or (resolved_url and _host_in(resolved_url, ('escholarship.org',)))):
        return None
    rights = _ESCHOLARSHIP_ITEM_RIGHTS.search(page)
    if rights is None:
        return None
    return '' if rights.group(1) == 'null' else rights.group(1).strip('"')


# The ACL Anthology (aclanthology.org) states its licence once, in the site footer, by year of publication:
#   "Materials prior to 2016 here are licensed under the <a ...>Creative Commons Attribution-NonCommercial-ShareAlike
#   3.0 International License</a>. Permission is granted to make copies for the purposes of teaching and research.
#   Materials published in or after 2016 are licensed on a <a ...>Creative Commons Attribution 4.0 International
#   License</a>."
# It is a whole-site statement like those of SITE_LICENSE_HOSTS (pdf.py), but keeping the footer whole cannot work: it
# names both licences on every page. So the paper's own year (citation_publication_date) picks the sentence, and only
# that sentence is read (#2239, round 3: every labelled page is cc-by, all from 2016 on). Nothing else on the page
# licenses the paper: an abstract that says "we release the corpus under CC BY-SA" is about the corpus.
_ACL_YEAR_SENTENCE = re.compile(
    r"\bmaterials\s+(?:prior\s+to|published\s+(in\s+or\s+after))\s+((?:19|20)\d\d)\b(?:[^.]|\.(?=\S)){0,300}",
    re.IGNORECASE)
_LEADING_YEAR = re.compile(r"\s*((?:19|20)\d\d)(?!\d)")


def acl_anthology_license_text(page, resolved_url):
    """The ACL Anthology footer sentence that licenses the paper's year of publication; '' when the page gives no
    year or its footer has no sentence for that year.

    None when the page is not on aclanthology.org, so other pages keep the whole-page search.
    """
    if not resolved_url or not _host_in(resolved_url, ('aclanthology.org',)):
        return None
    tree = get_tree(page)
    if tree is None:
        return None
    year = None
    for meta in tree.iter('meta'):
        if (meta.get('name') or '').lower() == 'citation_publication_date':
            leading_year = _LEADING_YEAR.match(meta.get('content') or '')
            if leading_year:
                year = int(leading_year.group(1))
                break
    if year is None:
        return ''
    for footer in tree.iter('footer'):
        for sentence in _ACL_YEAR_SENTENCE.finditer(re.sub(r"\s+", " ", " ".join(footer.itertext()))):
            if (year >= int(sentence.group(2))) == bool(sentence.group(1)):  # group 1: "in or after"
                return sentence.group(0)
    return ''


# Taylor & Francis book pages (taylorfrancis.com) keep the product in Angular TransferState JSON, `"` escaped as `&q;`,
# and state the product's own licence once there:
#   &q;license&q;:{&q;type&q;:&q;open-access&q;,&q;description&q;:...,&q;location&q;:&q;http://creativecommons.org/licenses/by-nc-nd/4.0&q;}
# or &q;license&q;:null. The same JSON holds the chapter's subject keywords and text, so the whole-page search read a
# keyword ("Creative Commons Attribution ShareAlike") or a sentence ("... into the public domain") as the licence
# (oxjob #1809 pilot: 3 of 3,016 pages; the 37 right licences there all came from the object). Pages that hold several
# objects repeat the same one (8 of 372 sampled).
_TF_LICENSE = re.compile(r'&q;license&q;:(null|\{[^{}]*\})')


def taylorfrancis_product_license_text(page):
    """The T&F product's own licence statement (its licence object, quotes decoded), or '' when it is null.

    None when the page is not a T&F page carrying that object, so other pages keep the whole-page search.
    """
    if not page or '&q;license&q;:' not in page or 'taylorfrancis.com' not in page:
        return None
    m = _TF_LICENSE.search(page)
    if m is None:
        return None
    return '' if m.group(1) == 'null' else m.group(1).replace('&q;', '"')


def detect_bronze(soup, resolved_url):
    from parseland_lib.publisher.parsers.nejm import NewEnglandJournalOfMedicine
    from parseland_lib.publisher.parsers.elsevier_bv import ElsevierBV
    page = str(soup)
    open_version_string = None
    bronze_url_snippet_patterns = [
        ('sciencedirect.com/',
         '<div class="OpenAccessLabel">open archive</div>'),
        ('sciencedirect.com/',
         r'<span[^>]*class="[^"]*pdf-download-label[^"]*"[^>]*>Download PDF</span>'),
        ('sciencedirect.com/',
         r'<span class="primary-cta-button-text|link-button-text">View\s*<strong>PDF</strong></span>'),
        ('onlinelibrary.wiley.com',
         '<div[^>]*class="doi-access"[^>]*>Free Access</div>'),
        ('openedition.org', r'<span[^>]*id="img-freemium"[^>]*></span>'),
        ('openedition.org', r'<span[^>]*id="img-openaccess"[^>]*></span>'),
        # landing page html is invalid: <span class="accesstext"></span>Free</span>
        ('microbiologyresearch.org',
         r'<span class="accesstext">(?:</span>)?Free'),
        ('journals.lww.com',
         r'<li[^>]*id="[^"]*-article-indicators-free"[^>]*>'),
        ('ashpublications.org', r'<i[^>]*class="[^"]*icon-availability_free'),
        ('academic.oup.com', r'<i[^>]*class="[^"]*icon-availability_free'),
        ('publications.aap.org', r'<i[^>]*class="[^"]*icon-availability_free'),
        ('degruyter.com/', '<span>Free Access</span>'),
        ('degruyter.com/', 'data-accessrestricted="false"'),
        (
        'practicalactionpublishing.com', r'<img [^>]*class="open-access-icon"'),
        ("iucnredlist.org", r'<title>'),
    ]

    for (url_snippet, pattern) in bronze_url_snippet_patterns:
        if url_snippet in resolved_url.lower() and re.findall(pattern,
                                                                   page,
                                                                   re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via free article)"

    bronze_publisher_patterns = [
        (NewEnglandJournalOfMedicine(soup).is_publisher_specific_parser,
         '<meta content="yes" name="evt-free"'),
        (lambda: soup.find('meta', {'name': 'dc.Publisher', 'content': lambda x: 'university of chicago press' in x.lower()}),
         r'<img[^>]*class="[^"]*accessIconLocation'),
        (ElsevierBV(soup).is_publisher_specific_parser,
         r'<span[^>]*class="[^"]*article-header__access[^"]*"[^>]*>Open Archive</span>'),
    ]

    for (publisher_func, pattern) in bronze_publisher_patterns:
        if publisher_func() and re.findall(pattern, page, re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via free article)"

    # bronze_journal_patterns = [
    #     ('1352-2310', r'<span[^>]*>Download PDF</span>'),
    # ]

    # for (issn_l, pattern) in bronze_journal_patterns:
    #     if self.issn_l == issn_l and re.findall(pattern, page,
    #                                             re.IGNORECASE | re.DOTALL):
    #         self.scraped_open_metadata_url = metadata_url
    #         self.open_version_source_string = "open (via free article)"

    bronze_citation_pdf_patterns = [
        r'^https?://www\.sciencedirect\.com/science/article/pii/S[0-9X]+/pdf(?:ft)?\?md5=[0-9a-f]+.*[0-9x]+-main.pdf$'
    ]

    citation_pdf_link = get_pdf_in_meta(page)

    if citation_pdf_link and citation_pdf_link.href:
        for pattern in bronze_citation_pdf_patterns:
            if re.findall(pattern, citation_pdf_link.href,
                          re.IGNORECASE | re.DOTALL):
                open_version_string = "open (via free article)"

    return open_version_string


def detect_hybrid(soup, license_search_substr, resolved_url):
    from parseland_lib.publisher.parsers.cup import CUP
    from parseland_lib.publisher.parsers.ieee import IEEE
    from parseland_lib.publisher.parsers.oxford import Oxford
    from parseland_lib.publisher.parsers.rsc import RSC
    from parseland_lib.publisher.parsers.wiley import Wiley

    page = str(soup)
    open_version_string, license = None, None
    hybrid_url_snippet_patterns = [
        ('projecteuclid.org/', '<strong>Full-text: Open access</strong>'),
        (
        'sciencedirect.com/', '<div class="OpenAccessLabel">open access</div>'),
        ('journals.ametsoc.org/',
         r'src="/templates/jsp/_style2/_ams/images/access_free\.gif"'),
        ('apsjournals.apsnet.org',
         r'src="/products/aps/releasedAssets/images/open-access-icon\.png"'),
        ('psychiatriapolska.pl', 'is an Open Access journal:'),
        ('journals.lww.com', '<span class="[^>]*ejp-indicator--free'),
        ('journals.lww.com',
         r'<img[^>]*src="[^"]*/icon-access-open\.gif"[^>]*>'),
        ('iospress.com',
         r'<img[^>]*src="[^"]*/img/openaccess_icon.png[^"]*"[^>]*>'),
        ('rti.org/', r'</svg>[^<]*Open Access[^<]*</span>'),
        ('cambridge.org/',
         r'<span[^>]*class="open-access"[^>]*>Open access</span>'),
    ]

    for (url_snippet, pattern) in hybrid_url_snippet_patterns:
        if url_snippet in resolved_url.lower() and re.findall(pattern,
                                                                   page,
                                                                   re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via page says Open Access)"
            license = "unspecified-oa"

    backup_hybrid_url_snippet_patterns = [
        ('degruyter.com/', '<span>Open Access</span>'),
    ]

    # should probably defer to scraped license for all publishers, but don't want to rock the boat yet
    if not license:
        for (url_snippet, pattern) in backup_hybrid_url_snippet_patterns:
            if url_snippet in resolved_url.lower() and re.findall(pattern,
                                                                       page,
                                                                       re.IGNORECASE | re.DOTALL):
                open_version_string = "open (via page says Open Access)"
                license = "unspecified-oa"

    # # try the license tab on T&F pages
    # # https://www.tandfonline.com/doi/full/10.1080/03057240.2018.1471391
    # # https://www.tandfonline.com/action/showCopyRight?doi=10.1080%2F03057240.2018.1471391
    # if not self.scraped_license:
    #     if url_match := re.match(
    #             r'^https?://(?:www\.)?tandfonline\.com/doi/full/(10\..+)',
    #             self.resolved_url, re.IGNORECASE):
    #         license_tab_url = 'https://www.tandfonline.com/action/showCopyRight?doi={doi}'.format(
    #             doi=url_match.group(1))
    #         logger.info(
    #             f'looking for license tab {license_tab_url} on T&F landing page {self.resolved_url}')
    #         license_tab_response = http_get(
    #             license_tab_url, stream=True, publisher=self.publisher,
    #             session_id=self.session_id, ask_slowly=self.ask_slowly,
    #             cookies=self.r.cookies
    #         )
    #
    #         if license_tab_response.status_code == 200:
    #             license_tab_text = license_tab_response.text_small()
    #             if license_tab_license := find_normalized_license(
    #                     page_potential_license_text(license_tab_text)):
    #                 self.scraped_license = license_tab_license
    #                 logger.info(
    #                     f'found license {self.scraped_license} on license tab')

    hybrid_publisher_patterns = [
        # Informa UK Limited? Always returning true for now
        (lambda: True, "/accessOA.png"),
        (Oxford(soup).is_publisher_specific_parser, "<i class='icon-availability_open'"),
        (IEEE(soup).is_publisher_specific_parser,
         r'"isOpenAccess":true'),
        (IEEE(soup).is_publisher_specific_parser,
         r'"openAccessFlag":"yes"'),
        (RSC(soup).is_publisher_specific_parser, "/open_access_blue.png"),
        (CUP(soup).is_publisher_specific_parser,
         '<span class="icon access open-access cursorDefault">'),
        (Wiley(soup).is_publisher_specific_parser, r'<div[^>]*class="doi-access"[^>]*>Open Access</div>'),
    ]

    for (publisher_func, pattern) in hybrid_publisher_patterns:
        if publisher_func() and re.findall(pattern, page,
                                                            re.IGNORECASE | re.DOTALL):
            open_version_string = "open (via page says Open Access)"
            license = "unspecified-oa"

    # Look for more license-like patterns that make this a hybrid location.
    # Extract the specific license if present.

    license_patterns = [
        r"(creativecommons.org/licenses/[a-z\-]+)",
        "distributed under the terms (.*) which permits",
        "This is an open access article under the terms (.*) which permits",
        "This is an open-access article distributed under the terms (.*), where it is permissible",
        "This is an open access article published under (.*) which permits",
        '<div class="openAccess-articleHeaderContainer(.*?)</div>',
        r'this article is published under the creative commons (.*) licence',
        r'This work is licensed under a Creative Commons (.*), which permits ',
    ]


    if trust_publisher_license(resolved_url):
        for pattern in license_patterns:
            matches = re.findall(pattern, license_search_substr, re.IGNORECASE)
            if matches:
                normalized_license = find_normalized_license(matches[0])
                license = normalized_license or 'unspecified-oa'
                if normalized_license:
                    open_version_string = 'open (via page says license)'
                else:
                    open_version_string = 'open (via page says Open Access)'

    return open_version_string, license

def detect_sd_author_manuscript(soup):
    if bool(soup.find(lambda tag: tag.text == 'View Open Manuscript')):
        return 'open (author manuscript)'

    return None


# Common Ground Research Networks article pages (cgscholar.com, DOIs 10.18848/...) are Nuxt pages: the article, with its
# own licence, is one object in the page's __NUXT_DATA__ array, every value an index into that array:
#   {"id":..,"title":..,"doi":..,"copyrightStatement":19,"licenseType":20,..,"journalAccessModel":28,..}
#   ... "© 2026 Common Ground Research Networks. All rights reserved.","all_rights_reserved", ...
# licenseType is "all_rights_reserved" on a subscription article (its PDF is for sale), "cc_by_nc_nd" or "cc_by_4" on an
# open one. The same array holds the site's label list for every licence on offer ("Gold Open Access (CC-BY)", "Open
# Access (CC-BY-NC-ND)"), on every page, so the whole-page search read cc-by-nc-nd on paywalled articles in hybrid
# journals: 5 of 8 sampled cc-by-nc-nd works were all_rights_reserved with a priced PDF (oxjob #1168, 21 Nov 2026;
# tickets 27748, 28098). The article's licenseType is its licence.
_NUXT_DATA = r'<script\b[^>]*\bid="__NUXT_DATA__"[^>]*>(.*?)</script\s*>'
_CGSCHOLAR_LICENSE_VERSION = r'(?:_\d+(?:_\d+)?)+$'


def cgscholar_article_license_text(page, resolved_url=None):
    """The Common Ground article's own licence, in words ("CC BY-NC-ND"), or '' when its licenseType is
    all_rights_reserved or empty.

    None when the page is not a cgscholar.com article page carrying that object, so other pages keep the whole-page
    search.
    """
    if not page or '"licenseType"' not in page or '__NUXT_DATA__' not in page or not (
            'cgscholar.com' in page or (resolved_url and _host_in(resolved_url, ('cgscholar.com',)))):
        return None
    m = re.search(_NUXT_DATA, page, re.DOTALL)
    if m is None:
        return None
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    for item in data:
        if not (isinstance(item, dict) and 'licenseType' in item and 'doi' in item and 'journalAccessModel' in item):
            continue
        ref = item['licenseType']
        value = data[ref] if isinstance(ref, int) and 0 <= ref < len(data) else ref
        if value is None or value == '':
            return ''
        if not isinstance(value, str):
            continue
        value = value.strip().lower()
        if value in ('all_rights_reserved', 'none', 'copyright'):
            return ''
        words = re.sub(_CGSCHOLAR_LICENSE_VERSION, '', value).split('_')
        if words[0] == 'cc' and len(words) > 1:
            return 'CC ' + '-'.join(words[1:]).upper()
        return value.replace('_', ' ')
    return None
