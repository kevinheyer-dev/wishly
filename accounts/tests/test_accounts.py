import datetime

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import BirthdayReminder, FamilyGroup, Membership, Profile, User
from accounts.reminders import send_birthday_reminders, upcoming_birthdays


def make_family():
    group = FamilyGroup.objects.create(name="Familie")
    anna = User.objects.create_user("anna", "anna@example.org", "pw")
    ben = User.objects.create_user("ben", "ben@example.org", "pw")
    Membership.objects.create(user=anna, group=group, role=Membership.Role.ADMIN)
    Membership.objects.create(user=ben, group=group)
    return group, anna, ben


class ProfileTests(TestCase):
    def test_profile_created_with_user(self):
        user = User.objects.create_user("x", password="pw")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_visibility_follows_groups(self):
        group, anna, ben = make_family()
        stranger = User.objects.create_user("stranger", password="pw")
        child = Profile.objects.create(name="Kind", family_group=group)
        child.guardians.add(anna)
        visible = Profile.objects.visible_to(ben)
        self.assertIn(anna.profile, visible)
        self.assertIn(child, visible)
        self.assertNotIn(stranger.profile, visible)
        self.assertEqual(list(Profile.objects.visible_to(stranger)), [stranger.profile])
        self.assertIn(child, Profile.objects.managed_by(anna))
        self.assertNotIn(child, Profile.objects.managed_by(ben))

    def test_next_birthday_handles_leap_day(self):
        profile = Profile(birth_day=29, birth_month=2)
        self.assertEqual(profile.next_birthday(datetime.date(2027, 1, 1)), datetime.date(2027, 2, 28))
        self.assertEqual(profile.next_birthday(datetime.date(2027, 3, 1)), datetime.date(2028, 2, 29))


@override_settings(BIRTHDAY_REMINDER_DAYS=14)
class ReminderTests(TestCase):
    def test_reminder_goes_to_family_once(self):
        _group, anna, ben = make_family()
        Profile.objects.filter(user=anna).update(birth_day=10, birth_month=5)
        today = datetime.date(2027, 5, 1)
        self.assertEqual(send_birthday_reminders(today), 1)
        self.assertEqual(mail.outbox[0].to, ["ben@example.org"])
        self.assertIn("anna", mail.outbox[0].subject)
        self.assertEqual(send_birthday_reminders(today + datetime.timedelta(days=1)), 0)
        self.assertEqual(BirthdayReminder.objects.count(), 1)

    def test_no_reminder_outside_window_or_when_disabled(self):
        _group, anna, ben = make_family()
        Profile.objects.filter(user=anna).update(birth_day=10, birth_month=6)
        self.assertEqual(send_birthday_reminders(datetime.date(2027, 5, 1)), 0)
        Profile.objects.filter(user=ben).update(birthday_reminders=False)
        self.assertEqual(send_birthday_reminders(datetime.date(2027, 6, 1)), 0)

    def test_upcoming_birthdays_sorted(self):
        _group, anna, ben = make_family()
        Profile.objects.filter(user=anna).update(birth_day=20, birth_month=1)
        Profile.objects.filter(user=ben).update(birth_day=5, birth_month=1)
        result = upcoming_birthdays(Profile.objects.all(), 30, datetime.date(2027, 1, 1))
        self.assertEqual([p.user for _, p in result], [ben, anna])


class GroupViewTests(TestCase):
    def test_signup_and_join_by_invite(self):
        group, _anna, _ben = make_family()
        response = self.client.post(reverse("signup"), {
            "username": "carla", "first_name": "Carla", "last_name": "", "email": "c@example.org",
            "password1": "ein-langes-passwort-42", "password2": "ein-langes-passwort-42",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.client.post(reverse("group_join", args=[group.invite_token]))
        self.assertTrue(group.memberships.filter(user__username="carla").exists())

    def test_signup_ignores_foreign_next(self):
        response = self.client.post(reverse("signup") + "?next=https://evil.example/", {
            "username": "dora", "email": "d@example.org",
            "password1": "ein-langes-passwort-42", "password2": "ein-langes-passwort-42",
        })
        self.assertRedirects(response, reverse("dashboard"))

    def test_last_admin_cannot_leave(self):
        group, anna, _ben = make_family()
        self.client.force_login(anna)
        membership = group.memberships.get(user=anna)
        self.client.post(reverse("member_remove", args=[group.pk, membership.pk]))
        self.assertTrue(group.memberships.filter(user=anna).exists())

    def test_member_cannot_remove_others(self):
        group, anna, ben = make_family()
        self.client.force_login(ben)
        response = self.client.post(reverse("member_remove", args=[group.pk, group.memberships.get(user=anna).pk]))
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_see_group(self):
        group, _anna, _ben = make_family()
        self.client.force_login(User.objects.create_user("stranger", password="pw"))
        self.assertEqual(self.client.get(reverse("group_detail", args=[group.pk])).status_code, 404)

    def test_child_profile_with_guardian(self):
        group, anna, ben = make_family()
        self.client.force_login(ben)
        response = self.client.post(reverse("child_create", args=[group.pk]), {
            "name": "Mia", "birth_day": "3", "birth_month": "4", "guardians": [ben.pk],
        })
        child = Profile.objects.get(name="Mia")
        self.assertRedirects(response, child.get_absolute_url())
        self.assertTrue(child.can_manage(ben))
        self.assertFalse(child.can_manage(anna))
