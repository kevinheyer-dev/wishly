"""Add our affiliate tag to shop links when they are shown – stored URLs stay clean."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings

AMAZON_DOMAINS = (
    "amazon.de", "amazon.com", "amazon.co.uk", "amazon.fr", "amazon.it", "amazon.es",
    "amazon.nl", "amazon.at", "amazon.pl", "amazon.se", "amazon.com.be", "amazon.ca",
)

# (domains, query parameter, setting with the tag) – further partner networks go here
PARTNERS = [
    (AMAZON_DOMAINS, "tag", "AMAZON_AFFILIATE_TAG"),
]


def _matches(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def affiliate_url(url):
    if not url:
        return url
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    for domains, param, setting in PARTNERS:
        tag = getattr(settings, setting, "")
        if tag and _matches(host, domains):
            query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != param]
            query.append((param, tag))
            return urlunsplit(parts._replace(query=urlencode(query)))
    return url


def is_affiliate(url):
    return affiliate_url(url) != url
