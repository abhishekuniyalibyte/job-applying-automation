from app.services.normalization import dedupe_key, normalize_company_name, normalize_url


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
