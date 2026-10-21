"""Extract product data from a shop page: JSON-LD first, then OpenGraph and microdata."""

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def parse_price(value):
    """Turn '1.299,99 €', '1,299.99' or 19.9 into a Decimal."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = re.sub(r"[^\d,.]", "", str(value))
    if not text:
        return None
    if "," in text and "." in text:
        # The last separator is the decimal one
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        whole, _, fraction = text.rpartition(",")
        text = f"{whole.replace(',', '')}.{fraction}" if len(fraction) <= 2 else text.replace(",", "")
    elif text.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", text):
        text = text.replace(".", "")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


# Shops without structured data (Amazon); (selector, attribute) – None means the element text
SELECTORS = {
    "title": [("#productTitle", None)],
    "image_url": [("#landingImage", "data-old-hires"), ("#landingImage", "src"), ("#imgBlkFront", "src")],
    "price": [(".priceToPay .a-offscreen", None), ("#corePrice_feature_div .a-offscreen", None),
              (".a-price .a-offscreen", None), ("span.a-color-price", None)],
}


def _from_selectors(soup):
    result = {}
    for field, candidates in SELECTORS.items():
        for selector, attribute in candidates:
            tag = soup.select_one(selector)
            value = tag and (tag.get(attribute) if attribute else tag.get_text(" ", strip=True))
            if value:
                result[field] = value
                break
    return result


def _iter_json_ld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                yield item
                stack.extend(v for k, v in item.items() if k in ("@graph", "mainEntity", "itemListElement"))


def _is_product(item):
    types = item.get("@type", [])
    types = types if isinstance(types, list) else [types]
    return any(t in ("Product", "ProductGroup") for t in types)


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _from_json_ld(soup):
    for item in _iter_json_ld(soup):
        if not _is_product(item):
            continue
        image = _first(item.get("image"))
        if isinstance(image, dict):
            image = image.get("url") or image.get("contentUrl")
        offer = _first(item.get("offers")) or {}
        if isinstance(offer, dict) and offer.get("@type") == "AggregateOffer":
            price = offer.get("lowPrice") or offer.get("price")
        elif isinstance(offer, dict):
            price = offer.get("price") or _first(offer.get("priceSpecification") or [{}]).get("price")
        else:
            price = None
        return {
            "title": item.get("name"),
            "description": item.get("description"),
            "image_url": image,
            "price": price,
            "currency": isinstance(offer, dict) and offer.get("priceCurrency") or None,
        }
    return {}


def _meta(soup, *names):
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _itemprop(soup, name):
    tag = soup.find(attrs={"itemprop": name})
    if not tag:
        return None
    return tag.get("content") or tag.get_text(" ", strip=True) or None


def parse_product(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    data = _from_selectors(soup) | {k: v for k, v in _from_json_ld(soup).items() if v}
    fallbacks = {
        "title": _meta(soup, "og:title", "twitter:title") or _itemprop(soup, "name")
        or (soup.title.get_text(strip=True) if soup.title else None),
        "description": _meta(soup, "og:description", "description", "twitter:description"),
        "image_url": _meta(soup, "og:image", "og:image:url", "twitter:image") or _itemprop(soup, "image"),
        "price": _meta(soup, "product:price:amount", "og:price:amount") or _itemprop(soup, "price"),
        "currency": _meta(soup, "product:price:currency", "og:price:currency") or _itemprop(soup, "priceCurrency"),
    }
    result = {key: data.get(key) or fallbacks[key] for key in fallbacks}
    result["title"] = (result["title"] or "").strip()[:300]
    result["description"] = (result["description"] or "").strip()[:2000]
    image = result["image_url"]
    result["image_url"] = urljoin(base_url, image)[:1000] if image and not image.startswith("data:") else ""
    result["price"] = parse_price(result["price"])
    currency = (result["currency"] or "").strip().upper()
    result["currency"] = currency if re.fullmatch(r"[A-Z]{3}", currency) else ""
    return result
