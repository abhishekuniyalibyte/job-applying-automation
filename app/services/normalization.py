"""Text/URL normalisation helpers used for deduplication."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_", "ref", "source", "src", "gclid", "fbclid", "mc_", "trk", "campaign")
_COMPANY_SUFFIXES = {
    "ltd", "limited", "inc", "incorporated", "llc", "plc", "corp", "corporation", "co", "gmbh",
    "pvt", "private", "pty", "sa", "ag", "bv", "group", "holdings", "company",
}
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")
# Country/region synonyms, so the same place written differently yields one key.
_LOCATION_SYNONYMS = {
    "uk": "united kingdom", "gb": "united kingdom", "great britain": "united kingdom",
    "us": "united states", "usa": "united states", "u s": "united states",
    "u s a": "united states", "america": "united states", "united states of america": "united states",
    "uae": "united arab emirates", "nl": "netherlands", "holland": "netherlands",
    "deutschland": "germany", "espana": "spain", "brasil": "brazil",
}


def normalize_text(s: str | None) -> str:
    if not s:
        return ""
    s = _PUNCT.sub(" ", s.lower())
    return _WS.sub(" ", s).strip()


def normalize_company_name(name: str | None) -> str:
    tokens = [t for t in normalize_text(name).split() if t not in _COMPANY_SUFFIXES]
    return " ".join(tokens)


def normalize_title(title: str | None) -> str:
    t = normalize_text(title)
    # Drop common noise that does not change the role identity
    t = re.sub(r"\b(m/f/d|m/w/d|f/m/x|urgent|hiring now|new)\b", " ", t)
    return _WS.sub(" ", t).strip()


def normalize_location(location: str | None) -> str:
    """Canonicalise a location for deduplication.

    Country/region synonyms are unified so "London, UK" == "London, United Kingdom", but the
    geography is preserved so "Remote, Poland" stays distinct from "Remote, United Kingdom".
    Multi-location postings ("Remote, Canada; Remote, US") keep every part, order-independently.
    """
    if not location:
        return ""
    # ";" and "|" separate whole locations; "," and "-" separate parts within one location.
    groups = [g for g in re.split(r"[;|]", location) if g.strip()]
    canonical: list[str] = []
    for group in groups:
        parts = [normalize_text(p) for p in re.split(r",|/| - ", group)]
        tokens = [_LOCATION_SYNONYMS.get(p, p) for p in parts if p]
        # Drop a bare "remote" qualifier only when it is not the entire location
        significant = [t for t in tokens if t != "remote"] or tokens
        seen: list[str] = []
        for t in significant:
            if t not in seen:
                seen.append(t)
        if seen:
            canonical.append(" ".join(seen))
    return " ".join(sorted(set(canonical)))


def dedupe_key(company: str | None, title: str | None, location: str | None) -> str:
    return "|".join([normalize_company_name(company), normalize_title(title), normalize_location(location)])


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if not parts.netloc:
        return None
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", host, path, urlencode(sorted(query)), ""))
