from scripts.whole_goldie_eval import _html_block_reason


def test_loading_only_cache_is_js_render_blocked() -> None:
    html = """
    <html>
      <head><script src="/assets/app.js"></script></head>
      <body>Loading...</body>
    </html>
    """
    assert _html_block_reason(html) == "js_rendered_required"


def test_oup_robot_cache_is_bot_blocked() -> None:
    html = """
    <html><body>
      <div class="explanation-message">
        Help us confirm that you are not a robot and we will take you to your content.
      </div>
    </body></html>
    """
    assert _html_block_reason(html) == "cached_bot_check"


def test_cookie_reload_challenge_cache_is_bot_blocked() -> None:
    html = """
    <html><head><script>
      document.cookie="key="+n+"*"+p/n+":1"; document.location.reload(true);
    </script></head><body>Loading...</body></html>
    """
    assert _html_block_reason(html) == "cached_bot_check"


def test_just_a_moment_cache_is_bot_blocked() -> None:
    html = """
    <html><head><title>Just a moment...</title></head>
      <body>Please wait while we check your browser.</body>
    </html>
    """
    assert _html_block_reason(html) == "cached_bot_check"


def test_cookies_turned_off_cache_is_bot_blocked() -> None:
    html = """
    <html><head><title>Error - Cookies Turned Off</title></head>
      <body>Cookies turned off. Please enable cookies.</body>
    </html>
    """
    assert _html_block_reason(html) == "cached_bot_check"


def test_unrelated_error_page_is_retrieval_blocked() -> None:
    html = """
    <html><head><title>Cybercrime - FBI</title></head>
      <body>This cached page is not the publisher article landing page.</body>
    </html>
    """
    assert _html_block_reason(html) == "cached_error_page"
