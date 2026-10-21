from django.test import TestCase
from django.urls import reverse

from accounts.models import FamilyGroup, Membership, Profile, User
from accounts.slugs import german_slugify
from wishlists.models import Product, Wishlist


class SlugTests(TestCase):
    def test_german_slugs(self):
        self.assertEqual(german_slugify("Familie Müller-Weiß", "x"), "familie-mueller-weiss")
        self.assertEqual(german_slugify("!!!", "liste"), "liste")

    def test_generated_and_unique(self):
        group = FamilyGroup.objects.create(name="Müller")
        self.assertEqual(group.slug, "mueller")
        self.assertEqual(FamilyGroup.objects.create(name="Müller").slug, "mueller-2")
        self.assertEqual(FamilyGroup.objects.create(name="Konto").slug, "konto-2")
        anna = User.objects.create_user("anna1", first_name="Anna", password="pw")
        other = User.objects.create_user("anna2", first_name="Anna", password="pw")
        self.assertEqual(anna.profile.slug, "anna")
        self.assertEqual(other.profile.slug, "anna-2")
        first = Wishlist.objects.create(profile=anna.profile, title="Weihnachten 2026")
        second = Wishlist.objects.create(profile=anna.profile, title="Weihnachten 2026")
        self.assertEqual((first.slug, second.slug), ("weihnachten-2026", "weihnachten-2026-2"))
        self.assertEqual(Wishlist.objects.create(profile=other.profile, title="Weihnachten 2026").slug,
                         "weihnachten-2026")

    def test_reserved_family_slug_rejected_in_form(self):
        user = User.objects.create_user("anna", password="pw")
        self.client.force_login(user)
        response = self.client.post(reverse("group_create"), {"name": "Test", "slug": "konto"})
        self.assertContains(response, "reserviert")


class PublicLinkTests(TestCase):
    def setUp(self):
        self.family = FamilyGroup.objects.create(name="Müller")
        self.anna = User.objects.create_user("anna", first_name="Anna", password="pw")
        Membership.objects.create(user=self.anna, group=self.family)
        self.xmas = Wishlist.objects.create(profile=self.anna.profile, title="Weihnachten", public_enabled=True)
        Product.objects.create(wishlist=self.xmas, title="Buch")

    def test_readable_urls(self):
        self.assertEqual(self.xmas.get_public_url(), "/mueller/anna/weihnachten/")
        self.assertEqual(self.anna.profile.get_public_url(), "/mueller/anna/")
        self.assertContains(self.client.get("/mueller/anna/weihnachten/"), "Buch")

    def test_profile_url_redirects_to_only_list_or_lists_all(self):
        self.assertRedirects(self.client.get("/mueller/anna/"), "/mueller/anna/weihnachten/")
        Wishlist.objects.create(profile=self.anna.profile, title="Geburtstag", public_enabled=True)
        Wishlist.objects.create(profile=self.anna.profile, title="Privat")
        response = self.client.get("/mueller/anna/")
        self.assertContains(response, "Geburtstag")
        self.assertNotContains(response, "Privat")

    def test_private_lists_and_wrong_family_are_404(self):
        Wishlist.objects.filter(pk=self.xmas.pk).update(public_enabled=False)
        self.assertEqual(self.client.get("/mueller/anna/").status_code, 404)
        self.assertEqual(self.client.get("/mueller/anna/weihnachten/").status_code, 404)
        Wishlist.objects.filter(pk=self.xmas.pk).update(public_enabled=True)
        FamilyGroup.objects.create(name="Schmidt")
        self.assertEqual(self.client.get("/schmidt/anna/weihnachten/").status_code, 404)

    def test_child_profile_link(self):
        child = Profile.objects.create(name="Mia", family_group=self.family)
        Wishlist.objects.create(profile=child, title="Geburtstag", public_enabled=True)
        self.assertContains(self.client.get("/mueller/mia/geburtstag/"), "Mia")

    def test_app_routes_still_win(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get("/familien/neu/").status_code, 200)
        self.assertEqual(self.client.get("/konto/passwort/").status_code, 200)

    def test_guest_reservation_on_readable_url(self):
        product = self.xmas.products.get()
        self.client.post(f"/mueller/anna/weihnachten/reservieren/{product.pk}/", {"guest_name": "Erna", "quantity": 1})
        self.assertEqual(product.reservations.get().guest_name, "Erna")

    def test_no_family_no_public_link(self):
        loner = User.objects.create_user("solo", password="pw")
        wishlist = Wishlist.objects.create(profile=loner.profile, title="X", public_enabled=True)
        self.assertIsNone(wishlist.get_public_url())
        self.client.force_login(loner)
        self.assertContains(self.client.get(wishlist.get_absolute_url()), "erst einer")
