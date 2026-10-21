from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from scraper.affiliate import affiliate_url
from scraper.fetch import FetchError, check_url
from scraper.parse import parse_price, parse_product
from scraper.tasks import scrape_product
from wishlists.models import Product, Wishlist

JSON_LD_PAGE = """
<html><head><title>Shop</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "BreadcrumbList"},
  {"@type": "Product", "name": "Kaffeemühle", "description": "Mahlt Kaffee.",
   "image": ["/img/muehle.jpg"], "offers": {"@type": "Offer", "price": "49.90", "priceCurrency": "EUR"}}
]}
</script></head><body></body></html>
"""

OG_PAGE = """
<html><head>
<meta property="og:title" content="Lego Set">
<meta property="og:image" content="https://cdn.example/lego.png">
<meta property="product:price:amount" content="1.299,99">
<meta property="product:price:currency" content="eur">
</head></html>
"""


class ParseTests(SimpleTestCase):
    def test_prices(self):
        self.assertEqual(parse_price("1.299,99 €"), Decimal("1299.99"))
        self.assertEqual(parse_price("1,299.99"), Decimal("1299.99"))
        self.assertEqual(parse_price("19,9"), Decimal("19.90"))
        self.assertEqual(parse_price("1.000"), Decimal("1000.00"))
        self.assertEqual(parse_price(12.5), Decimal("12.50"))
        self.assertIsNone(parse_price("Preis auf Anfrage"))

    def test_json_ld(self):
        data = parse_product(JSON_LD_PAGE, "https://shop.example/p/1")
        self.assertEqual(data["title"], "Kaffeemühle")
        self.assertEqual(data["image_url"], "https://shop.example/img/muehle.jpg")
        self.assertEqual(data["price"], Decimal("49.90"))
        self.assertEqual(data["currency"], "EUR")

    def test_opengraph(self):
        data = parse_product(OG_PAGE, "https://shop.example/")
        self.assertEqual(data["title"], "Lego Set")
        self.assertEqual(data["price"], Decimal("1299.99"))
        self.assertEqual(data["currency"], "EUR")


class FetchTests(SimpleTestCase):
    def test_rejects_internal_and_odd_urls(self):
        for url in ("http://127.0.0.1/", "http://localhost:8000/", "http://10.0.0.1/", "file:///etc/passwd",
                    "http://[::1]/", "http://169.254.169.254/latest/meta-data/"):
            with self.subTest(url=url), self.assertRaises(FetchError):
                check_url(url)


class AffiliateTests(SimpleTestCase):
    @override_settings(AMAZON_AFFILIATE_TAG="wishly-21")
    def test_amazon_tag_added_and_replaced(self):
        self.assertEqual(affiliate_url("https://www.amazon.de/dp/B0001"), "https://www.amazon.de/dp/B0001?tag=wishly-21")
        self.assertEqual(affiliate_url("https://amazon.de/dp/B0001?tag=other-21&th=1"),
                         "https://amazon.de/dp/B0001?th=1&tag=wishly-21")
        self.assertEqual(affiliate_url("https://notamazon.de/x"), "https://notamazon.de/x")

    @override_settings(AMAZON_AFFILIATE_TAG="")
    def test_untouched_without_tag(self):
        self.assertEqual(affiliate_url("https://www.amazon.de/dp/B0001"), "https://www.amazon.de/dp/B0001")


class TaskTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("anna", password="pw")
        wishlist = Wishlist.objects.create(profile=user.profile, title="Liste")
        self.product = Product.objects.create(wishlist=wishlist, shop_url="https://shop.example/p/1",
                                              title="Mein Titel", scrape_status="pending")

    @mock.patch("scraper.tasks.fetch_html", return_value=("https://shop.example/p/1", JSON_LD_PAGE))
    def test_fills_only_empty_fields(self, _fetch):
        scrape_product(self.product.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, "Mein Titel")
        self.assertEqual(self.product.price, Decimal("49.90"))
        self.assertEqual(self.product.scrape_status, Product.ScrapeStatus.DONE)

    @mock.patch("scraper.tasks.fetch_html", side_effect=FetchError("kaputt"))
    def test_failure_is_recorded(self, _fetch):
        scrape_product(self.product.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.scrape_status, Product.ScrapeStatus.FAILED)
        self.assertEqual(self.product.scrape_error, "kaputt")


class SelectorTests(SimpleTestCase):
    def test_amazon_like_page(self):
        html = """<html><head><title>Amazon.de: Buch : Autor</title></head><body>
        <span id="productTitle"> Ein Buch </span>
        <img id="landingImage" src="small.jpg" data-old-hires="https://m.media-amazon.com/big.jpg">
        <span class="a-price"><span class="a-offscreen"></span></span><span class="a-color-price">9,99 €</span>
        </body></html>"""
        data = parse_product(html, "https://www.amazon.de/dp/1")
        self.assertEqual(data["title"], "Ein Buch")
        self.assertEqual(data["image_url"], "https://m.media-amazon.com/big.jpg")
        self.assertEqual(data["price"], Decimal("9.99"))
