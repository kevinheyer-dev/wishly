import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse

from .models import BirthdayReminder, Profile


def upcoming_birthdays(profiles, days, today=None):
    """[(date, profile)] for birthdays within the next `days` days, soonest first."""
    today = today or datetime.date.today()
    result = []
    for profile in profiles.filter(birth_day__isnull=False):
        birthday = profile.next_birthday(today)
        if (birthday - today).days <= days:
            result.append((birthday, profile))
    return sorted(result, key=lambda item: (item[0], item[1].display_name))


def send_birthday_reminders(today=None):
    """Mail each group member once per birthday, `BIRTHDAY_REMINDER_DAYS` ahead.

    Not tied to one exact day, so a missed run is caught up by the next one.
    """
    today = today or datetime.date.today()
    sent = 0
    for birthday, profile in upcoming_birthdays(Profile.objects.all(), settings.BIRTHDAY_REMINDER_DAYS, today):
        if birthday == today:
            continue
        recipients = list(profile.recipients_for_reminders())
        if not recipients:
            continue
        try:
            with transaction.atomic():
                BirthdayReminder.objects.create(profile=profile, birthday=birthday)
        except IntegrityError:
            continue
        context = {
            "profile": profile,
            "birthday": birthday,
            "days": (birthday - today).days,
            "url": settings.SITE_URL + reverse("profile_detail", args=[profile.pk]),
        }
        for user in recipients:
            context["user"] = user
            send_mail(
                f"Bald hat {profile.display_name} Geburtstag",
                render_to_string("accounts/email/birthday_reminder.txt", context),
                None,
                [user.email],
            )
            sent += 1
    return sent
