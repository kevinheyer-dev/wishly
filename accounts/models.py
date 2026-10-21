import calendar
import datetime
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse

from .slugs import RESERVED, unique_slug, validate_not_reserved

MONTHS = [
    (1, "Januar"), (2, "Februar"), (3, "März"), (4, "April"), (5, "Mai"), (6, "Juni"),
    (7, "Juli"), (8, "August"), (9, "September"), (10, "Oktober"), (11, "November"), (12, "Dezember"),
]


def new_invite_token():
    return secrets.token_urlsafe(16)


class User(AbstractUser):
    def __str__(self):
        return self.get_full_name() or self.username


class FamilyGroup(models.Model):
    name = models.CharField("Name", max_length=100)
    slug = models.SlugField(
        "Name in Links", max_length=50, unique=True, blank=True, validators=[validate_not_reserved],
        help_text="Erster Teil der öffentlichen Links, z. B. „mueller“. Leer lassen = aus dem Namen.",
    )
    invite_token = models.CharField(max_length=40, unique=True, default=new_invite_token)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Membership", related_name="family_groups"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Familiengruppe"
        verbose_name_plural = "Familiengruppen"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("group_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.slug:
            others = FamilyGroup.objects.exclude(pk=self.pk)
            self.slug = unique_slug(others, self.name, "familie", reserved=RESERVED)
        super().save(*args, **kwargs)

    def is_admin(self, user):
        return self.memberships.filter(user=user, role=Membership.Role.ADMIN).exists()


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MEMBER = "member", "Familienmitglied"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    group = models.ForeignKey(FamilyGroup, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField("Rolle", max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "group"], name="unique_membership")]
        ordering = ["group", "user__username"]
        verbose_name = "Mitgliedschaft"
        verbose_name_plural = "Mitgliedschaften"

    def __str__(self):
        return f"{self.user} in {self.group} ({self.get_role_display()})"


class ProfileQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Own and managed profiles plus everyone who shares a group with the user."""
        group_ids = Membership.objects.filter(user=user).values("group_id")
        return self.filter(
            Q(user=user)
            | Q(guardians=user)
            | Q(user__memberships__group_id__in=group_ids)
            | Q(family_group_id__in=group_ids)
        ).distinct()

    def managed_by(self, user):
        return self.filter(Q(user=user) | Q(guardians=user)).distinct()


class Profile(models.Model):
    """A person who can receive gifts: a user or a child without a login."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="profile"
    )
    name = models.CharField(
        "Name", max_length=100, blank=True, help_text="Für Kinderprofile; bei Konten der Name des Kontos."
    )
    # Unique across all families: adults belong to several, so a per-family name could clash on joining
    slug = models.SlugField(
        "Name in Links", max_length=50, unique=True, blank=True,
        help_text="Zweiter Teil der öffentlichen Links, z. B. „anna“. Leer lassen = aus dem Namen.",
    )
    # Children belong to one group; adults reach their groups through Membership
    family_group = models.ForeignKey(
        FamilyGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="child_profiles"
    )
    guardians = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="managed_profiles", verbose_name="Erziehungsberechtigte"
    )
    birth_day = models.PositiveSmallIntegerField("Geburtstag (Tag)", null=True, blank=True)
    birth_month = models.PositiveSmallIntegerField(
        "Geburtstag (Monat)", null=True, blank=True, choices=MONTHS
    )
    # Secret link through which a child adds wishes without an account; empty = switched off
    child_token = models.CharField(max_length=40, unique=True, null=True, blank=True, editable=False)
    child_approval_required = models.BooleanField(
        "Wünsche des Kindes erst nach Freigabe zeigen", default=False,
        help_text="Was das Kind über seinen Link einträgt, sieht die Familie erst, wenn du es übernimmst.",
    )
    birthday_reminders = models.BooleanField(
        "Erinnerungen an Geburtstage per E-Mail", default=True,
        help_text="Gilt nur für Konten: Mails vor Geburtstagen deiner Familienmitglieder.",
    )

    objects = ProfileQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "Profil"
        verbose_name_plural = "Profile"
        constraints = [
            models.CheckConstraint(
                condition=Q(user__isnull=False) | Q(family_group__isnull=False),
                name="child_profile_needs_group",
            ),
        ]

    def __str__(self):
        return self.display_name

    def get_absolute_url(self):
        return reverse("profile_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.slug:
            source = (self.user.first_name or self.user.username) if self.user_id else self.name
            self.slug = unique_slug(Profile.objects.exclude(pk=self.pk), source, "profil")
        super().save(*args, **kwargs)

    def public_family(self):
        """The family that appears in this profile's public links."""
        if self.is_child:
            return self.family_group
        membership = self.user.memberships.select_related("group").order_by("joined_at").first()
        return membership.group if membership else None

    def get_public_url(self):
        family = self.public_family()
        return reverse("public_profile", args=[family.slug, self.slug]) if family else None

    @property
    def display_name(self):
        if self.user_id:
            return str(self.user)
        return self.name

    @property
    def is_child(self):
        return self.user_id is None

    def clean(self):
        if (self.birth_day is None) != (self.birth_month is None):
            raise ValidationError("Bitte Tag und Monat angeben oder beide leer lassen.")
        if self.birth_day is not None:
            # 2024 is a leap year, so 29 February is accepted
            try:
                datetime.date(2024, self.birth_month, self.birth_day)
            except ValueError:
                raise ValidationError("Dieses Datum gibt es nicht.") from None

    def can_manage(self, user):
        return user.is_authenticated and (
            self.user_id == user.pk or self.guardians.filter(pk=user.pk).exists()
        )

    def next_birthday(self, today=None):
        if self.birth_day is None:
            return None
        today = today or datetime.date.today()
        for year in (today.year, today.year + 1):
            day = self.birth_day
            if self.birth_month == 2 and day == 29 and not calendar.isleap(year):
                day = 28
            candidate = datetime.date(year, self.birth_month, day)
            if candidate >= today:
                return candidate

    def recipients_for_reminders(self):
        """Users who should hear about this profile's birthday: its group, minus the person."""
        if self.is_child:
            users = User.objects.filter(memberships__group=self.family_group)
        else:
            users = User.objects.filter(memberships__group__memberships__user=self.user).exclude(pk=self.user_id)
        return users.filter(profile__birthday_reminders=True).exclude(email="").distinct()


class BirthdayReminder(models.Model):
    """One row per profile and birthday, so a reminder is never sent twice."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="reminders")
    birthday = models.DateField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["profile", "birthday"], name="unique_reminder")]
