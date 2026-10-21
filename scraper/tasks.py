import logging

from celery import shared_task

from wishlists.models import Product

from .fetch import FetchError, fetch_html
from .parse import parse_product

logger = logging.getLogger(__name__)


@shared_task
def scrape_product(product_id, overwrite=False):
    """Fill in product data from its shop page. Fields the user typed stay unless overwrite is set."""
    product = Product.objects.filter(pk=product_id).first()
    if product is None or not product.shop_url:
        return
    try:
        _final_url, html = fetch_html(product.shop_url)
        data = parse_product(html, product.shop_url)
    except FetchError as exc:
        Product.objects.filter(pk=product_id).update(
            scrape_status=Product.ScrapeStatus.FAILED, scrape_error=str(exc)[:300]
        )
        return
    except Exception:
        logger.exception("Scraping product %s failed", product_id)
        Product.objects.filter(pk=product_id).update(
            scrape_status=Product.ScrapeStatus.FAILED, scrape_error="Die Seite konnte nicht ausgewertet werden."
        )
        return

    # Re-read so edits made while the page was loading are not overwritten
    product.refresh_from_db()
    fields = ["scrape_status", "scrape_error"]
    for field in ("title", "description", "image_url", "price"):
        if data[field] not in ("", None) and (overwrite or getattr(product, field) in ("", None)):
            setattr(product, field, data[field])
            fields.append(field)
    if data["currency"] and "price" in fields:
        product.currency = data["currency"]
        fields.append("currency")
    found = any(data[f] for f in ("title", "image_url", "price"))
    product.scrape_status = Product.ScrapeStatus.DONE if found else Product.ScrapeStatus.FAILED
    product.scrape_error = "" if found else "Auf der Seite wurden keine Produktdaten gefunden."
    product.save(update_fields=fields)
