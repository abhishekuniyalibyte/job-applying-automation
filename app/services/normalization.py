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
    # "London, UK" and "London, United Kingdom" -> keep the first significant part to be tolerant
    parts = [p.strip() for p in re.split(r",| - |/", location or "") if p.strip()]
    return normalize_text(parts[0]) if parts else ""


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
