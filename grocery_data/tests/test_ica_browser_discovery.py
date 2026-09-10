from grocery_data.scripts.discover_ica_browser import is_access_challenge


def test_access_challenge_is_detected_without_storing_body() -> None:
    assert is_access_challenge(405, "text/html", "AWS WAF CAPTCHA")
    assert is_access_challenge(403, "text/html", "request could not be satisfied")
    assert is_access_challenge(202, "text/html", "Human Verification")


def test_normal_public_responses_are_not_mislabeled_as_challenges() -> None:
    assert not is_access_challenge(200, "text/html", "ordinary ICA catalog")
    assert not is_access_challenge(405, "application/json", '{"error":"method"}')
