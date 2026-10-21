from urllib.parse import quote_plus

from django import template
from django.utils.html import format_html

from scraper.affiliate import affiliate_url

register = template.Library()


@register.filter
def affiliate(url):
    return affiliate_url(url)


@register.filter
def stars(priority):
    return format_html('<span class="stars" title="Priorität {} von 5">{}<span class="stars-off">{}</span></span>',
                       priority, "★" * priority, "★" * (5 - priority))


@register.filter
def price_search_url(title):
    """Price comparison is a search link for now – no scraping of comparison sites."""
    return "https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=" + quote_plus(title)


@register.filter
def money(value, currency="EUR"):
    if value is None:
        return ""
    text = f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{text} €" if currency == "EUR" else f"{text} {currency}"
