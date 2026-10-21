"""Pages behind a child's secret link: no account, sees its lists like a recipient, adds wishes."""

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Profile

from . import access
from .forms import ChildProductForm
from .models import Product
from .views import _product_rows, _start_scraping, link_preview_response


def _child_profile(token):
    return get_object_or_404(Profile, child_token=token, user__isnull=True)


def _child_product(token, pk):
    """Children may change only what they entered themselves."""
    profile = _child_profile(token)
    product = get_object_or_404(Product.objects.select_related("wishlist"), pk=pk,
                                wishlist__profile=profile, added_by_child=True)
    return profile, product


def child_home(request, token):
    profile = _child_profile(token)
    wishlists = list(profile.wishlists.all())
    if len(wishlists) == 1:
        return redirect("child_wishlist", token, wishlists[0].pk)
    return render(request, "child/home.html", {"profile": profile, "wishlists": wishlists, "token": token})


def child_wishlist(request, token, pk):
    profile = _child_profile(token)
    wishlist = get_object_or_404(profile.wishlists, pk=pk)
    form = ChildProductForm(request.POST or None)
    if form.is_valid():
        with transaction.atomic():
            product = form.save(commit=False)
            product.wishlist = wishlist
            product.added_by_child = True
            if profile.child_approval_required:
                product.visibility = Product.Visibility.PENDING
            product.save()
            _start_scraping(product)
        if product.visibility == Product.Visibility.PENDING:
            messages.success(request, f"„{product}“ ist notiert – deine Eltern schauen es sich noch an.")
        else:
            messages.success(request, f"„{product}“ steht jetzt auf deiner Liste!")
        return redirect("child_wishlist", token, wishlist.pk)
    return render(request, "child/wishlist.html", {
        "profile": profile,
        "wishlist": wishlist,
        "rows": _product_rows(access.child_products(wishlist), show_reservations=False),
        "form": form,
        "token": token,
        "theme": wishlist.resolved_theme(),
        "has_more_lists": profile.wishlists.count() > 1,
    })


def child_product_edit(request, token, pk):
    profile, product = _child_product(token, pk)
    old_url = product.shop_url
    form = ChildProductForm(request.POST or None, instance=product)
    if form.is_valid():
        with transaction.atomic():
            product = form.save()
            if product.shop_url != old_url:
                _start_scraping(product)
        messages.success(request, "Gespeichert.")
        return redirect("child_wishlist", token, product.wishlist_id)
    return render(request, "child/product_form.html", {
        "form": form, "profile": profile, "product": product, "token": token,
        "theme": product.wishlist.resolved_theme(),
    })


def child_product_delete(request, token, pk):
    profile, product = _child_product(token, pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, f"„{product}“ ist von deiner Liste entfernt.")
        return redirect("child_wishlist", token, product.wishlist_id)
    return render(request, "child/confirm_delete.html", {
        "object": product, "profile": profile, "token": token, "theme": product.wishlist.resolved_theme(),
    })


def child_product_status(request, token, pk):
    _profile, product = _child_product(token, pk)
    return JsonResponse({"status": product.scrape_status})


def child_link_preview(request, token):
    _child_profile(token)
    return link_preview_response(request.GET.get("url", ""))
