from django.test import TestCase
from django.urls import reverse

from accounts.models import FamilyGroup, Membership, Profile, User
from wishlists.models import Product, Reservation, Wishlist


class ChildLinkTests(TestCase):
    def setUp(self):
        self.group = FamilyGroup.objects.create(name="Familie")
        self.mama = User.objects.create_user("mama", password="pw")
        self.oma = User.objects.create_user("oma", password="pw")
        for user in (self.mama, self.oma):
            Membership.objects.create(user=user, group=self.group)
        self.child = Profile.objects.create(name="Mia", family_group=self.group, child_token="geheim123")
        self.child.guardians.add(self.mama)
        self.wishlist = Wishlist.objects.create(profile=self.child, title="Mias Geburtstag")
        self.list_url = reverse("child_wishlist", args=["geheim123", self.wishlist.pk])

    def add_wish(self, title):
        return self.client.post(self.list_url, {"title": title, "priority": 4, "quantity_desired": 1})

    def test_single_list_opens_directly(self):
        self.assertRedirects(self.client.get(reverse("child_home", args=["geheim123"])), self.list_url)

    def test_unknown_or_adult_token_is_404(self):
        self.assertEqual(self.client.get(reverse("child_home", args=["falsch"])).status_code, 404)
        Profile.objects.filter(user=self.mama).update(child_token="erwachsen")
        self.assertEqual(self.client.get(reverse("child_home", args=["erwachsen"])).status_code, 404)

    def test_wish_visible_without_approval(self):
        self.add_wish("Einhorn")
        product = Product.objects.get(title="Einhorn")
        self.assertTrue(product.added_by_child)
        self.assertEqual(product.visibility, Product.Visibility.VISIBLE)
        self.client.force_login(self.oma)
        self.assertContains(self.client.get(self.wishlist.get_absolute_url()), "Einhorn")

    def test_wish_needs_approval_when_enabled(self):
        Profile.objects.filter(pk=self.child.pk).update(child_approval_required=True)
        self.add_wish("Trampolin")
        product = Product.objects.get(title="Trampolin")
        self.assertEqual(product.visibility, Product.Visibility.PENDING)
        self.assertContains(self.client.get(self.list_url), "Wartet auf Freigabe")
        self.client.force_login(self.oma)
        self.assertNotContains(self.client.get(self.wishlist.get_absolute_url()), "Trampolin")
        self.client.force_login(self.mama)
        self.assertContains(self.client.get(self.wishlist.get_absolute_url()), "Mia selbst eingetragen")
        self.client.post(reverse("suggestion_decide", args=[product.pk, "annehmen"]))
        self.client.force_login(self.oma)
        self.assertContains(self.client.get(self.wishlist.get_absolute_url()), "Trampolin")

    def test_child_sees_no_reservations_or_secrets(self):
        product = Product.objects.create(wishlist=self.wishlist, title="Buch")
        Reservation.objects.create(product=product, reserved_by=self.oma)
        Product.objects.create(wishlist=self.wishlist, title="Geheimtipp", visibility=Product.Visibility.SECRET)
        Product.objects.create(wishlist=self.wishlist, title="Omas Idee", suggested_by=self.oma,
                               visibility=Product.Visibility.PENDING)
        response = self.client.get(self.list_url)
        self.assertContains(response, "Buch")
        for hidden in ("Geheimtipp", "Omas Idee", "Vergeben", "frei", "oma"):
            self.assertNotContains(response, hidden)

    def test_child_changes_only_own_wishes(self):
        self.add_wish("Roller")
        own = Product.objects.get(title="Roller")
        parents = Product.objects.create(wishlist=self.wishlist, title="Von Mama")
        edit = reverse("child_product_edit", args=["geheim123", parents.pk])
        self.assertEqual(self.client.get(edit).status_code, 404)
        self.client.post(reverse("child_product_edit", args=["geheim123", own.pk]),
                         {"title": "Roter Roller", "priority": 5, "quantity_desired": 1})
        own.refresh_from_db()
        self.assertEqual(own.title, "Roter Roller")
        self.client.post(reverse("child_product_delete", args=["geheim123", own.pk]))
        self.assertFalse(Product.objects.filter(pk=own.pk).exists())

    def test_other_child_token_cannot_touch_wish(self):
        self.add_wish("Roller")
        Profile.objects.create(name="Tom", family_group=self.group, child_token="tom")
        own = Product.objects.get(title="Roller")
        response = self.client.post(reverse("child_product_delete", args=["tom", own.pk]))
        self.assertEqual(response.status_code, 404)

    def test_guardian_manages_link(self):
        self.client.force_login(self.oma)
        url = reverse("child_link", args=[self.child.pk])
        self.assertEqual(self.client.post(url, {"action": "renew"}).status_code, 403)
        self.client.force_login(self.mama)
        self.client.post(url, {"action": "renew"})
        self.child.refresh_from_db()
        self.assertNotIn(self.child.child_token, (None, "geheim123"))
        self.assertEqual(self.client.get(self.list_url).status_code, 404)
        self.client.post(url, {"action": "disable"})
        self.child.refresh_from_db()
        self.assertIsNone(self.child.child_token)

    def test_profile_page_shows_link_to_guardian_only(self):
        self.client.force_login(self.mama)
        self.assertContains(self.client.get(self.child.get_absolute_url()), "/kind/geheim123/")
        self.client.force_login(self.oma)
        self.assertNotContains(self.client.get(self.child.get_absolute_url()), "geheim123")
