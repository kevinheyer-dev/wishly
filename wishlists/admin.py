from django.contrib import admin

from .models import Product, Reservation, Wishlist


class ProductInline(admin.TabularInline):
    model = Product
    extra = 0
    fields = ("title", "price", "priority", "quantity_desired", "visibility")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("title", "profile", "event_type", "event_date", "public_enabled")
    list_filter = ("event_type", "public_enabled")
    search_fields = ("title",)
    inlines = [ProductInline]


class ReservationInline(admin.TabularInline):
    model = Reservation
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("__str__", "wishlist", "price", "priority", "visibility", "scrape_status")
    list_filter = ("visibility", "scrape_status")
    search_fields = ("title", "shop_url")
    inlines = [ReservationInline]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("product", "reserver_name", "quantity", "status", "created_at")
    list_filter = ("status",)
