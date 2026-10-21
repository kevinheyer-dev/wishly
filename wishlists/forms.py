from django import forms

from accounts.models import Profile

from .models import Product, Reservation, Wishlist


class WishlistForm(forms.ModelForm):
    class Meta:
        model = Wishlist
        fields = ("profile", "title", "event_type", "event_date", "description", "theme", "public_enabled")
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile"].queryset = Profile.objects.managed_by(user).select_related("user")
        self.fields["profile"].empty_label = None


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("shop_url", "title", "price", "currency", "priority", "quantity_desired", "notes",
                  "description", "image_url")
        widgets = {
            "shop_url": forms.URLInput(attrs={"placeholder": "https://…", "autofocus": True}),
            "priority": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "shop_url": "Titel, Bild, Preis und Beschreibung werden automatisch ergänzt, wenn du sie leer lässt.",
        }

    def clean_currency(self):
        return self.cleaned_data["currency"].upper()

    def clean(self):
        data = super().clean()
        if not data.get("title") and not data.get("shop_url"):
            raise forms.ValidationError("Gib einen Titel oder einen Link an.")
        return data


class QuickAddForm(forms.Form):
    shop_url = forms.URLField(max_length=2000)


class ChildProductForm(ProductForm):
    """Fewer fields and simpler words for children adding wishes through their link."""

    class Meta(ProductForm.Meta):
        fields = ("title", "shop_url", "priority", "quantity_desired", "notes")
        labels = {
            "title": "Was wünschst du dir?",
            "shop_url": "Link (wenn du einen hast)",
            "priority": "Wie sehr wünschst du es dir?",
            "quantity_desired": "Wie viele?",
            "notes": "Noch etwas wichtig? (Größe, Farbe …)",
        }
        widgets = {
            "title": forms.TextInput(attrs={"autofocus": True}),
            "shop_url": forms.URLInput(attrs={"placeholder": "https://…"}),
            "priority": forms.Select(choices=[(5, "★★★★★ Ganz doll"), (4, "★★★★ Sehr"), (3, "★★★ Mittel"),
                                              (2, "★★ Ein bisschen"), (1, "★ Wäre nett")]),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {"shop_url": "", "priority": ""}


class SuggestionForm(ProductForm):
    visibility = forms.ChoiceField(
        label="Sichtbarkeit",
        choices=[
            (Product.Visibility.PENDING, "Vorschlagen – erscheint auf der Liste, sobald er bestätigt wird"),
            (Product.Visibility.SECRET, "Geheim – nur für die anderen sichtbar, nie für den Beschenkten"),
        ],
        widget=forms.RadioSelect,
        initial=Product.Visibility.SECRET,
    )

    class Meta(ProductForm.Meta):
        fields = ProductForm.Meta.fields + ("visibility",)


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ("quantity", "status")

    def __init__(self, *args, max_quantity, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_quantity = max_quantity
        self.fields["quantity"].widget.attrs.update(min=1, max=max_quantity)

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.max_quantity:
            raise forms.ValidationError(f"Es sind nur noch {self.max_quantity} offen.")
        return quantity


class GuestReservationForm(ReservationForm):
    class Meta:
        model = Reservation
        fields = ("guest_name", "quantity")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["guest_name"].required = True
        self.fields["guest_name"].label = "Dein Name"
