from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("verwaltung/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("wishlists.urls")),
]
