from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import FamilyGroup, Membership, Profile, User
from scraper.fetch import FetchError
from wishlists.models import Product, Wishlist

SCRAPED = {"title": "Kaffeemühle", "description": "", "image_url": "https://cdn.example/m.jpg",
           "price": Decimal("49.90"), "currency": "EUR"}


class LinkImportTests(TestCase):
    def setUp(self):
        self.group = FamilyGroup.objects.create(name="Familie")
        self.anna = User.objects.create_user("anna", password="pw")
        self.ben = User.objects.create_user("ben", password="pw")
        for user in (self.anna, self.ben):
            Membership.objects.create(user=user, group=self.group)
        self.wishlist = Wishlist.objects.create(profile=self.anna.profile, title="Liste")
        self.client.force_login(self.anna)

    @mock.patch("wishlists.views.scrape_url", return_value=SCRAPED)
    def test_preview_returns_scraped_data(self, scrape):
        response = self.client.get(reverse("link_preview"), {"url": "https://shop.example/p/1"})
        self.assertEqual(response.json()["title"], "Kaffeemühle")
        self.assertEqual(response.json()["price"], "49.90")
        scrape.assert_called_once_with("https://shop.example/p/1")

    @mock.patch("wishlists.views.scrape_url", side_effect=FetchError("Gesperrt."))
    def test_preview_reports_errors(self, _scrape):
        response = self.client.get(reverse("link_preview"), {"url": "https://shop.example/p/1"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "Gesperrt.")
        response = self.client.get(reverse("link_preview"), {"url": "kein link"})
        self.assertEqual(response.status_code, 400)

    def test_preview_needs_login_or_child_token(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("link_preview"), {"url": "https://x.de"}).status_code, 302)
        self.assertEqual(self.client.get(reverse("child_link_preview", args=["falsch"])).status_code, 404)
        Profile.objects.create(name="Mia", family_group=self.group, child_token="t")
        with mock.patch("wishlists.views.scrape_url", return_value=SCRAPED):
            response = self.client.get(reverse("child_link_preview", args=["t"]), {"url": "https://x.de/p"})
        self.assertEqual(response.json()["title"], "Kaffeemühle")

    @mock.patch("wishlists.views.scrape_product")
    def test_quick_add_with_link_only(self, scrape):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("product_quick_add", args=[self.wishlist.pk]),
                             {"shop_url": "https://shop.example/p/1"})
        product = Product.objects.get()
        self.assertEqual(product.title, "")
        self.assertEqual(product.scrape_status, Product.ScrapeStatus.PENDING)
        scrape.delay.assert_called_once_with(product.pk, False)

    def test_quick_add_only_for_editors(self):
        self.client.force_login(self.ben)
        response = self.client.post(reverse("product_quick_add", args=[self.wishlist.pk]),
                                    {"shop_url": "https://shop.example/p/1"})
        self.assertEqual(response.status_code, 403)

    @mock.patch("wishlists.views.scrape_product")
    def test_no_background_fetch_when_form_already_complete(self, scrape):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("product_create", args=[self.wishlist.pk]), {
                "shop_url": "https://shop.example/p/1", "title": "Mühle", "image_url": "https://cdn.example/m.jpg",
                "price": "49.90", "currency": "EUR", "priority": 3, "quantity_desired": 1,
            })
        scrape.delay.assert_not_called()
        self.assertEqual(Product.objects.get().scrape_status, "")

    @mock.patch("wishlists.views.scrape_product")
    def test_rescrape_overwrites(self, scrape):
        product = Product.objects.create(wishlist=self.wishlist, shop_url="https://shop.example/p/1", title="Alt",
                                         image_url="https://cdn.example/a.jpg", price=1)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("product_rescrape", args=[product.pk]))
        scrape.delay.assert_called_once_with(product.pk, True)
