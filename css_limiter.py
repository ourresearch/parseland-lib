import logging
from functools import wraps
from bs4 import BeautifulSoup, Tag
import soupsieve
import soupsieve.css_match
from soupsieve.css_match import CSSMatch, SoupSieve

class CSSLimitExceeded(Exception):
    pass

class CSSLimiter:
    CALL_LIMIT = 2000
    WARN_THRESHOLD = 500
    _call_count = 0
    _call_locations = {}

    @classmethod
    def reset(cls):
        cls._call_count = 0
        cls._call_locations.clear()

    @classmethod
    def track_call(cls, caller):
        cls._call_count += 1
        if caller not in cls._call_locations:
            cls._call_locations[caller] = 0
        cls._call_locations[caller] += 1

        if cls._call_count > cls.CALL_LIMIT:
            logging.error(f"CSS call limit exceeded at {caller}")
            cls._log_call_distribution()
            raise CSSLimitExceeded(f"CSS selector call limit ({cls.CALL_LIMIT}) exceeded")

        if cls._call_count == cls.WARN_THRESHOLD:
            logging.warning(f"CSS calls approaching limit: {cls._call_count}/{cls.CALL_LIMIT}")
            cls._log_call_distribution()

    @classmethod
    def _log_call_distribution(cls):
        for location, count in sorted(cls._call_locations.items(), key=lambda x: x[1], reverse=True):
            logging.info(f"  {location}: {count} calls")

def get_caller():
    import inspect
    stack = inspect.stack()
    for frame_info in stack[2:]:
        filename = frame_info.filename.lower()
        if not any(x in filename for x in ['beautifulsoup', 'soupsieve', 'css_match']):
            return f"{frame_info.filename}:{frame_info.lineno}"
    return "unknown"

def install_css_limiter():
    """Install CSS selector limiting at multiple levels"""
    # Store original methods
    original_soup_select = soupsieve.select
    original_soup_match = soupsieve.match
    original_cssmatch_match = CSSMatch.match
    original_soupsieve_match = SoupSieve.match
    original_bs_select = BeautifulSoup.select
    original_bs_select_one = BeautifulSoup.select_one
    original_tag_select = Tag.select
    original_tag_select_one = Tag.select_one

    @wraps(original_soup_select)
    def limited_soup_select(*args, **kwargs):
        caller = get_caller()
        CSSLimiter.track_call(caller)
        return original_soup_select(*args, **kwargs)

    @wraps(original_soup_match)
    def limited_soup_match(*args, **kwargs):
        caller = get_caller()
        CSSLimiter.track_call(caller)
        return original_soup_match(*args, **kwargs)

    @wraps(original_cssmatch_match)
    def limited_cssmatch_match(self, *args, **kwargs):
        caller = get_caller()
        CSSLimiter.track_call(caller)
        return original_cssmatch_match(self, *args, **kwargs)

    @wraps(original_soupsieve_match)
    def limited_soupsieve_match(self, *args, **kwargs):
        caller = get_caller()
        CSSLimiter.track_call(caller)
        return original_soupsieve_match(self, *args, **kwargs)

    # Install all patches
    soupsieve.select = limited_soup_select
    soupsieve.match = limited_soup_match
    CSSMatch.match = limited_cssmatch_match
    SoupSieve.match = limited_soupsieve_match
    BeautifulSoup.select = original_bs_select
    BeautifulSoup.select_one = original_bs_select_one
    Tag.select = original_tag_select
    Tag.select_one = original_tag_select_one

    return CSSLimiter