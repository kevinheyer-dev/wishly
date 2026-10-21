"""Readable URL names for families, profiles and lists (/mueller/anna/weihnachten/)."""

from django.core.exceptions import ValidationError
from django.utils.text import slugify

# First path segments the app uses itself – a family must not shadow them
RESERVED = {
    "admin", "api", "familien", "kind", "konto", "l", "link-vorschau", "listen", "media", "profile",
    "reservierungen", "static", "verwaltung", "wuensche",
}

UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def german_slugify(value, fallback):
    return slugify(str(value).translate(UMLAUTS))[:50].strip("-") or fallback


def unique_slug(queryset, value, fallback, reserved=()):
    """First free slug among `queryset`: anna, anna-2, anna-3 …"""
    base = german_slugify(value, fallback)
    slug, n = base, 1
    while slug in reserved or queryset.filter(slug=slug).exists():
        n += 1
        slug = f"{base[:46]}-{n}"
    return slug


def validate_not_reserved(value):
    if value in RESERVED:
        raise ValidationError("Dieser Name ist für die Seite selbst reserviert.")
