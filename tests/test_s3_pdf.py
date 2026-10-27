"""A stored landing page that is really a PDF yields no landing page, gzipped or not (oxjob #1794).

The range read in is_pdf_in_r2 sees only the first 5 stored bytes, which for a gzipped object is the gzip header, so
gzipped PDFs used to be parsed as HTML until the worker timeout.
"""
import gzip
import io

from parseland_lib.s3 import get_landing_page_from_r2


class FakeS3:
    def __init__(self, stored: bytes):
        self.stored = stored

    def get_object(self, Bucket, Key, Range=None):
        body = self.stored
        if Range:
            start, end = Range.split("=")[1].split("-")
            body = body[int(start):int(end) + 1]
        return {"Body": io.BytesIO(body)}


def test_gzipped_pdf_is_no_landing_page():
    assert get_landing_page_from_r2("x", FakeS3(gzip.compress(b"%PDF-1.7\n%stuff"))) is None


def test_plain_pdf_is_no_landing_page():
    assert get_landing_page_from_r2("x", FakeS3(b"%PDF-1.4\n%stuff")) is None


def test_gzipped_html_is_returned_decompressed():
    html = b"<html><head><title>t</title></head><body>PDF-1 is a word here</body></html>"
    assert get_landing_page_from_r2("x", FakeS3(gzip.compress(html))) == html


def test_plain_html_is_returned_as_is():
    html = b"<html><body>x</body></html>"
    assert get_landing_page_from_r2("x", FakeS3(html)) == html
