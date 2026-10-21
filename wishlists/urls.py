from django.urls import path

from . import child_views, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("listen/neu/", views.wishlist_create, name="wishlist_create"),
    path("listen/<int:pk>/", views.wishlist_detail, name="wishlist_detail"),
    path("listen/<int:pk>/bearbeiten/", views.wishlist_edit, name="wishlist_edit"),
    path("listen/<int:pk>/loeschen/", views.wishlist_delete, name="wishlist_delete"),
    path("listen/<int:pk>/link-erneuern/", views.wishlist_new_link, name="wishlist_new_link"),
    path("listen/<int:pk>/wunsch/neu/", views.product_create, name="product_create"),
    path("wuensche/<int:pk>/bearbeiten/", views.product_edit, name="product_edit"),
    path("wuensche/<int:pk>/loeschen/", views.product_delete, name="product_delete"),
    path("wuensche/<int:pk>/neu-einlesen/", views.product_rescrape, name="product_rescrape"),
    path("wuensche/<int:pk>/status/", views.product_status, name="product_status"),
    path("wuensche/<int:pk>/vorschlag/<str:decision>/", views.suggestion_decide, name="suggestion_decide"),
    path("wuensche/<int:pk>/reservieren/", views.reserve, name="reserve"),
    path("reservierungen/", views.my_reservations, name="my_reservations"),
    path("reservierungen/<int:pk>/aufheben/", views.reservation_delete, name="reservation_delete"),
    path("l/<uuid:public_id>/", views.public_wishlist, name="public_wishlist"),
    path("l/<uuid:public_id>/wunsch/<int:pk>/reservieren/", views.public_reserve, name="public_reserve"),
    path("l/<uuid:public_id>/reservierung/<int:pk>/aufheben/", views.public_unreserve, name="public_unreserve"),
    path("kind/<str:token>/", child_views.child_home, name="child_home"),
    path("kind/<str:token>/listen/<int:pk>/", child_views.child_wishlist, name="child_wishlist"),
    path("kind/<str:token>/wuensche/<int:pk>/bearbeiten/", child_views.child_product_edit, name="child_product_edit"),
    path("kind/<str:token>/wuensche/<int:pk>/loeschen/", child_views.child_product_delete,
         name="child_product_delete"),
    path("kind/<str:token>/wuensche/<int:pk>/status/", child_views.child_product_status,
         name="child_product_status"),
]
