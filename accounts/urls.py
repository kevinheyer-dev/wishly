from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("konto/registrieren/", views.signup, name="signup"),
    path("konto/", views.account, name="account"),
    path("familien/", views.group_list, name="group_list"),
    path("familien/neu/", views.group_create, name="group_create"),
    path("familien/beitreten/<str:token>/", views.group_join, name="group_join"),
    path("familien/<int:pk>/", views.group_detail, name="group_detail"),
    path("familien/<int:pk>/bearbeiten/", views.group_edit, name="group_edit"),
    path("familien/<int:pk>/loeschen/", views.group_delete, name="group_delete"),
    path("familien/<int:pk>/einladung-erneuern/", views.group_new_invite, name="group_new_invite"),
    path("familien/<int:pk>/mitglieder/<int:membership_pk>/rolle/", views.member_role, name="member_role"),
    path("familien/<int:pk>/mitglieder/<int:membership_pk>/entfernen/", views.member_remove, name="member_remove"),
    path("familien/<int:pk>/kinder/neu/", views.child_create, name="child_create"),
    path("profile/<int:pk>/", views.profile_detail, name="profile_detail"),
    path("profile/<int:pk>/bearbeiten/", views.child_edit, name="child_edit"),
    path("profile/<int:pk>/loeschen/", views.child_delete, name="child_delete"),
    path("profile/<int:pk>/kinder-link/", views.child_link, name="child_link"),
    path("konto/anmelden/", auth_views.LoginView.as_view(), name="login"),
    path("konto/abmelden/", auth_views.LogoutView.as_view(), name="logout"),
    path("konto/passwort/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path("konto/passwort/fertig/", auth_views.PasswordChangeDoneView.as_view(), name="password_change_done"),
    path("konto/passwort/vergessen/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("konto/passwort/vergessen/gesendet/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("konto/passwort/neu/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("konto/passwort/neu/fertig/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
