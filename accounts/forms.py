from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import FamilyGroup, Profile, User


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="E-Mail", help_text="Für Passwort-Zurücksetzen und Geburtstags-Erinnerungen.")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")


class OwnProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("slug", "birth_day", "birth_month", "birthday_reminders")


class ChildProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("name", "slug", "birth_day", "birth_month", "guardians", "child_approval_required")
        widgets = {"guardians": forms.CheckboxSelectMultiple}

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        self.fields["guardians"].queryset = User.objects.filter(memberships__group=group).order_by("username")
        self.fields["guardians"].required = True
        self.fields["guardians"].help_text = "Dürfen die Listen des Kindes verwalten."


class GroupForm(forms.ModelForm):
    class Meta:
        model = FamilyGroup
        fields = ("name", "slug")
