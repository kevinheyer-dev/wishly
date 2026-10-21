import datetime
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.urls import reverse

from accounts.models import Profile

from .context_processors import SEASONS


class Wishlist(models.Model):
    class EventType(models.TextChoices):
        BIRTHDAY = "birthday", "Geburtstag"
        WEDDING = "wedding", "Hochzeit"
        CHRISTMAS = "christmas", "Weihnachten"
        BABY = "baby", "Babyparty"
        OTHER = "other", "Sonstiges"

    class Theme(models.TextChoices):
        AUTO = "auto", "Automatisch (Anlass/Jahreszeit)"
        BIRTHDAY = "birthday", "Geburtstag"
        WEDDING = "wedding", "Hochzeit"
        CHRISTMAS = "christmas", "Weihnachten"
        BABY = "baby", "Baby"
        SPRING = "spring", "Frühling"
        SUMMER = "summer", "Sommer"
        AUTUMN = "autumn", "Herbst"
        WINTER = "winter", "Winter"
        PLAIN = "plain", "Schlicht"

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="wishlists", verbose_name="Für")
    title = models.CharField("Titel", max_length=150)
    event_type = models.CharField("Anlass", max_length=20, choices=EventType.choices, default=EventType.BIRTHDAY)
    event_date = models.DateField("Datum des Anlasses", null=True, blank=True)
    description = models.TextField("Beschreibung", blank=True)
    theme = models.CharField("Design", max_length=20, choices=Theme.choices, default=Theme.AUTO)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    public_enabled = models.BooleanField(
        "Öffentlicher Link aktiv", default=False,
        help_text="Jeder mit dem Link kann die Liste sehen und Wünsche reservieren.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_date", "title"]
        verbose_name = "Wunschliste"
        verbose_name_plural = "Wunschlisten"

    def __str__(self):
        return f"{self.title} ({self.profile})"

    def get_absolute_url(self):
        return reverse("wishlist_detail", args=[self.pk])

    def get_public_url(self):
        return reverse("public_wishlist", args=[self.public_id])

    def resolved_theme(self, today=None):
        if self.theme != self.Theme.AUTO:
            return self.theme
        if self.event_type != self.EventType.OTHER:
            return self.event_type
        return SEASONS[(self.event_date or today or datetime.date.today()).month]


class Product(models.Model):
    class Visibility(models.TextChoices):
        VISIBLE = "visible", "Sichtbar"
        # Suggested by someone else, waits for the recipient (or a guardian) to accept it
        PENDING = "pending", "Vorschlag, wartet auf Bestätigung"
        # Suggested by someone else, hidden from the recipient for good
        SECRET = "secret", "Geheimer Vorschlag"

    class ScrapeStatus(models.TextChoices):
        NONE = "", "—"
        PENDING = "pending", "Wird eingelesen"
        DONE = "done", "Eingelesen"
        FAILED = "failed", "Fehlgeschlagen"

    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="products")
    title = models.CharField("Titel", max_length=300, blank=True)
    description = models.TextField("Beschreibung", blank=True)
    image_url = models.URLField("Bild-URL", max_length=1000, blank=True)
    shop_url = models.URLField("Link zum Shop", max_length=2000, blank=True)
    price = models.DecimalField("Preis", max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField("Währung", max_length=3, default="EUR")
    priority = models.PositiveSmallIntegerField(
        "Priorität", default=3, validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 = nice to have, 5 = Herzenswunsch",
    )
    quantity_desired = models.PositiveSmallIntegerField(
        "Gewünschte Anzahl", default=1, validators=[MinValueValidator(1)]
    )
    notes = models.TextField("Notizen", blank=True, help_text="z. B. Größe, Farbe, Ausführung")
    suggested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="suggested_products", verbose_name="Vorgeschlagen von",
    )
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.VISIBLE)
    scrape_status = models.CharField(max_length=10, choices=ScrapeStatus.choices, blank=True, default="")
    scrape_error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "created_at"]
        verbose_name = "Wunsch"
        verbose_name_plural = "Wünsche"

    def __str__(self):
        return self.title or self.shop_url or f"Wunsch {self.pk}"

    @property
    def display_title(self):
        return str(self)

    def quantity_reserved(self):
        return self.reservations.aggregate(n=Sum("quantity"))["n"] or 0

    def quantity_purchased(self):
        return self.reservations.filter(status=Reservation.Status.PURCHASED).aggregate(n=Sum("quantity"))["n"] or 0

    def quantity_open(self):
        return max(self.quantity_desired - self.quantity_reserved(), 0)


class Reservation(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserviert"
        PURCHASED = "purchased", "Gekauft / erhalten"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reservations")
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="reservations"
    )
    # Guests reserve through the public link; the key in their session lets them undo it
    guest_name = models.CharField("Name", max_length=100, blank=True)
    guest_key = models.UUIDField(null=True, blank=True, editable=False)
    quantity = models.PositiveSmallIntegerField("Anzahl", default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RESERVED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Reservierung"
        verbose_name_plural = "Reservierungen"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(reserved_by__isnull=False) | models.Q(guest_key__isnull=False),
                name="reservation_has_owner",
            ),
        ]

    def __str__(self):
        return f"{self.quantity}× {self.product} – {self.reserver_name}"

    @property
    def reserver_name(self):
        return str(self.reserved_by) if self.reserved_by_id else f"{self.guest_name or 'Gast'} (Gast)"
