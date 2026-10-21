import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import FamilyGroup, Membership, Profile, User
from wishlists.models import Product, Reservation, Wishlist


class FamilyTestCase(TestCase):
    def setUp(self):
        self.group = FamilyGroup.objects.create(name="Familie")
        self.anna = User.objects.create_user("anna", password="pw")
        self.ben = User.objects.create_user("ben", password="pw")
        self.stranger = User.objects.create_user("stranger", password="pw")
        for user in (self.anna, self.ben):
            Membership.objects.create(user=user, group=self.group)
        self.wishlist = Wishlist.objects.create(
            profile=self.anna.profile, title="Annas Geburtstag", public_enabled=True
        )
        self.product = Product.objects.create(wishlist=self.wishlist, title="Buch", quantity_desired=2)

    def detail(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("wishlist_detail", args=[self.wishlist.pk]))


class SurpriseProtectionTests(FamilyTestCase):
    def test_recipient_does_not_see_reservations(self):
        Reservation.objects.create(product=self.product, reserved_by=self.ben, quantity=1)
        response = self.detail(self.anna)
        self.assertNotContains(response, "ben:")
        self.assertNotContains(response, "frei")
        self.assertContains(response, "Überraschungsschutz")

    def test_family_sees_reservations(self):
        carla = User.objects.create_user("carla", password="pw")
        Membership.objects.create(user=carla, group=self.group)
        Reservation.objects.create(product=self.product, reserved_by=self.ben, quantity=1)
        response = self.detail(carla)
        self.assertContains(response, "ben: 1× Reserviert")
        self.assertContains(response, "1 von 2 frei")

    def test_recipient_does_not_see_secret_suggestion(self):
        Product.objects.create(wishlist=self.wishlist, title="Geheimtipp", suggested_by=self.ben,
                               visibility=Product.Visibility.SECRET)
        self.assertNotContains(self.detail(self.anna), "Geheimtipp")
        self.assertContains(self.detail(self.ben), "Geheimtipp")

    def test_recipient_cannot_reserve(self):
        self.client.force_login(self.anna)
        response = self.client.post(reverse("reserve", args=[self.product.pk]), {"quantity": 1, "status": "reserved"})
        self.assertEqual(response.status_code, 403)

    def test_recipient_on_public_link_sees_no_reservations(self):
        Reservation.objects.create(product=self.product, reserved_by=self.ben, quantity=2)
        self.client.force_login(self.anna)
        response = self.client.get(self.wishlist.get_public_url())
        self.assertNotContains(response, "Vergeben")

    def test_guardian_of_child_sees_reservations(self):
        child = Profile.objects.create(name="Mia", family_group=self.group)
        child.guardians.add(self.anna)
        wishlist = Wishlist.objects.create(profile=child, title="Mias Wünsche")
        product = Product.objects.create(wishlist=wishlist, title="Puppe")
        Reservation.objects.create(product=product, reserved_by=self.ben)
        self.client.force_login(self.anna)
        response = self.client.get(reverse("wishlist_detail", args=[wishlist.pk]))
        self.assertContains(response, "ben: 1× Reserviert")


class SuggestionTests(FamilyTestCase):
    def test_pending_suggestion_needs_confirmation(self):
        self.client.force_login(self.ben)
        self.client.post(reverse("product_create", args=[self.wishlist.pk]), {
            "title": "Fahrrad", "currency": "EUR", "priority": 3, "quantity_desired": 1, "visibility": "pending",
        })
        product = Product.objects.get(title="Fahrrad")
        self.assertEqual(product.visibility, Product.Visibility.PENDING)
        self.assertEqual(product.suggested_by, self.ben)
        carla = User.objects.create_user("carla", password="pw")
        Membership.objects.create(user=carla, group=self.group)
        self.assertNotContains(self.detail(carla), "Fahrrad")
        self.assertContains(self.detail(self.anna), "Fahrrad")
        self.client.post(reverse("suggestion_decide", args=[product.pk, "annehmen"]))
        product.refresh_from_db()
        self.assertEqual(product.visibility, Product.Visibility.VISIBLE)
        self.assertContains(self.detail(carla), "Fahrrad")

    def test_only_editor_decides(self):
        product = Product.objects.create(wishlist=self.wishlist, title="X", suggested_by=self.ben,
                                         visibility=Product.Visibility.PENDING)
        self.client.force_login(self.ben)
        response = self.client.post(reverse("suggestion_decide", args=[product.pk, "annehmen"]))
        self.assertEqual(response.status_code, 403)

    def test_member_cannot_edit_others_products(self):
        self.client.force_login(self.ben)
        self.assertEqual(self.client.get(reverse("product_edit", args=[self.product.pk])).status_code, 403)


class ReservationTests(FamilyTestCase):
    def test_quantity_is_capped(self):
        self.client.force_login(self.ben)
        self.client.post(reverse("reserve", args=[self.product.pk]), {"quantity": 3, "status": "reserved"})
        self.assertFalse(Reservation.objects.exists())
        self.client.post(reverse("reserve", args=[self.product.pk]), {"quantity": 2, "status": "reserved"})
        self.assertEqual(self.product.quantity_open(), 0)

    def test_update_own_reservation(self):
        self.client.force_login(self.ben)
        url = reverse("reserve", args=[self.product.pk])
        self.client.post(url, {"quantity": 2, "status": "reserved"})
        self.client.post(url, {"quantity": 2, "status": "purchased"})
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.status, Reservation.Status.PURCHASED)
        self.assertEqual(self.product.quantity_purchased(), 2)

    def test_outsider_cannot_reserve_internally(self):
        self.client.force_login(self.stranger)
        response = self.client.post(reverse("reserve", args=[self.product.pk]), {"quantity": 1, "status": "reserved"})
        self.assertEqual(response.status_code, 404)

    def test_guest_reserves_and_cancels_via_public_link(self):
        url = reverse("public_reserve", args=[self.wishlist.public_id, self.product.pk])
        self.client.post(url, {"guest_name": "Tante Erna", "quantity": 1})
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.guest_name, "Tante Erna")
        self.assertContains(self.client.get(self.wishlist.get_public_url()), "Reservierung aufheben")
        self.client.post(reverse("public_unreserve", args=[self.wishlist.public_id, reservation.pk]))
        self.assertFalse(Reservation.objects.exists())

    def test_logged_in_outsider_reserves_via_public_link(self):
        self.client.force_login(self.stranger)
        url = reverse("public_reserve", args=[self.wishlist.public_id, self.product.pk])
        self.client.post(url, {"quantity": 1, "status": "reserved"})
        self.assertEqual(Reservation.objects.get().reserved_by, self.stranger)

    def test_public_link_can_be_disabled_and_hides_secrets(self):
        Product.objects.create(wishlist=self.wishlist, title="Geheimtipp", visibility=Product.Visibility.SECRET)
        self.assertNotContains(self.client.get(self.wishlist.get_public_url()), "Geheimtipp")
        Wishlist.objects.filter(pk=self.wishlist.pk).update(public_enabled=False)
        self.assertEqual(self.client.get(self.wishlist.get_public_url()).status_code, 404)


class WishlistViewTests(FamilyTestCase):
    def test_outsider_gets_404(self):
        self.assertEqual(self.detail(self.stranger).status_code, 404)

    def test_dashboard_lists(self):
        self.client.force_login(self.ben)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Annas Geburtstag")

    def test_landing_for_anonymous(self):
        self.assertContains(self.client.get(reverse("dashboard")), "registrieren")

    def test_cannot_create_list_for_someone_else(self):
        self.client.force_login(self.ben)
        response = self.client.post(reverse("wishlist_create"), {
            "profile": self.anna.profile.pk, "title": "Fake", "event_type": "birthday", "theme": "auto",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Wishlist.objects.filter(title="Fake").exists())

    @mock.patch("wishlists.views.scrape_product")
    def test_product_with_link_starts_scraping(self, scrape):
        self.client.force_login(self.anna)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("product_create", args=[self.wishlist.pk]), {
                "shop_url": "https://shop.example/p/1", "currency": "EUR", "priority": 3, "quantity_desired": 1,
            })
        product = Product.objects.get(shop_url="https://shop.example/p/1")
        self.assertEqual(product.scrape_status, Product.ScrapeStatus.PENDING)
        scrape.delay.assert_called_once_with(product.pk)

    def test_theme_resolution(self):
        wishlist = Wishlist(event_type=Wishlist.EventType.OTHER, event_date=datetime.date(2027, 7, 1))
        self.assertEqual(wishlist.resolved_theme(), "summer")
        wishlist.event_type = Wishlist.EventType.CHRISTMAS
        self.assertEqual(wishlist.resolved_theme(), "christmas")
        wishlist.theme = Wishlist.Theme.PLAIN
        self.assertEqual(wishlist.resolved_theme(), "plain")
