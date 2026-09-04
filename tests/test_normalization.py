from app.services.normalization import (
    dedupe_key,
    normalize_company_name,
    normalize_location,
    normalize_url,
)


def test_normalize_url_strips_tracking_and_www():
    a = normalize_url("https://www.example.com/jobs/123/?utm_source=x&ref=abc&page=2#apply")
    b = normalize_url("https://example.com/jobs/123?page=2")
    assert a == b == "https://example.com/jobs/123?page=2"


def test_normalize_url_rejects_garbage():
    assert normalize_url("") is None
    assert normalize_url("not a url") is None


def test_company_suffixes_are_dropped():
    assert normalize_company_name("Acme Ltd.") == normalize_company_name("ACME Limited") == "acme"


def test_dedupe_key_tolerates_formatting():
    k1 = dedupe_key("Acme Ltd", "Senior Backend Engineer", "London, UK")
    k2 = dedupe_key("ACME Limited", "Senior  Backend Engineer!", "London, United Kingdom")
    assert k1 == k2
    assert k1 != dedupe_key("Acme Ltd", "Junior Backend Engineer", "London, UK")


# --- location normalisation -------------------------------------------------------------------
# Regression: an earlier version kept only the first comma-separated part, so every
# "Remote, <country>" posting collapsed to "remote" and unrelated roles were merged.


def test_country_synonyms_are_unified():
    assert normalize_location("London, UK") == normalize_location("London, United Kingdom")
    assert normalize_location("Austin, US") == normalize_location("Austin, USA")


def test_remote_postings_keep_their_country():
    poland = normalize_location("Remote, Poland")
    uk = normalize_location("Remote, United Kingdom")
    assert poland != uk
    assert "poland" in poland and "united kingdom" in uk


def test_bare_remote_survives_as_its_own_location():
    assert normalize_location("Remote") == "remote"
    assert normalize_location("Remote - EMEA") == "emea"


def test_multi_location_posting_is_order_independent():
    a = normalize_location("Remote, Canada; Remote, US")
    b = normalize_location("Remote, United States; Remote, Canada")
    assert a == b
    assert "canada" in a and "united states" in a


def test_dedupe_key_separates_same_role_in_different_countries():
    pl = dedupe_key("GitLab", "Staff Backend Engineer, EMEA", "Remote, Poland")
    uk = dedupe_key("GitLab", "Staff Backend Engineer, EMEA", "Remote, United Kingdom")
    assert pl != uk


def test_dedupe_key_still_merges_the_same_posting_written_differently():
    a = dedupe_key("GitLab", "Support Engineer, U.S. Government Support", "Remote, US")
    b = dedupe_key("GitLab Inc.", "Support Engineer, U.S. Government Support", "Remote, United States")
    assert a == b
