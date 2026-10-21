import logging
import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import FamilyGroup, Profile
from accounts.reminders import upcoming_birthdays
from scraper.fetch import FetchError
from scraper.tasks import scrape_product, scrape_url

from . import access
from .forms import GuestReservationForm, ProductForm, QuickAddForm, ReservationForm, SuggestionForm, WishlistForm
from .models import Product, Reservation, Wishlist

logger = logging.getLogger(__name__)

GUEST_SESSION_KEY = "wishly_guest_key"


def _product_rows(products, *, user=None, guest_key=None, show_reservations=True):
    """Products with their reservation figures, computed once for the template."""
    rows = []
    for product in products.prefetch_related("reservations__reserved_by"):
        reservations = list(product.reservations.all())
        reserved = sum(r.quantity for r in reservations)
        mine = next((
            r for r in reservations
            if (user is not None and user.is_authenticated and r.reserved_by_id == user.pk)
            or (guest_key and str(r.guest_key) == guest_key)
        ), None)
        rows.append({
            "product": product,
            "reservations": reservations if show_reservations else [],
            "reserved": reserved if show_reservations else None,
            "open": max(product.quantity_desired - reserved, 0) if show_reservations else None,
            "purchased": sum(r.quantity for r in reservations if r.status == Reservation.Status.PURCHASED),
            "mine": mine,
        })
    return rows


def _start_scraping(product, overwrite=False):
    """Fetch missing data from the shop link in the background – unless the form already brought it."""
    complete = product.title and product.image_url and product.price is not None
    if not product.shop_url or (complete and not overwrite):
        return
    product.scrape_status = Product.ScrapeStatus.PENDING
    product.scrape_error = ""
    product.save(update_fields=["scrape_status", "scrape_error"])

    def enqueue():
        try:
            scrape_product.delay(product.pk, overwrite)
        except Exception:
            logger.exception("Could not queue scraping of product %s", product.pk)
            Product.objects.filter(pk=product.pk).update(
                scrape_status=Product.ScrapeStatus.FAILED, scrape_error="Der Hintergrunddienst ist nicht erreichbar."
            )

    transaction.on_commit(enqueue)


def link_preview_response(url):
    """JSON with what a shop link yields, for filling in the product form before saving."""
    try:
        url = forms.URLField().clean(url)
        data = scrape_url(url)
    except forms.ValidationError:
        return JsonResponse({"error": "Das ist kein gültiger Link."}, status=400)
    except FetchError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except Exception:
        logger.exception("Link preview for %s failed", url)
        return JsonResponse({"error": "Die Seite konnte nicht ausgewertet werden."}, status=422)
    data["price"] = str(data["price"]) if data["price"] is not None else ""
    return JsonResponse(data)


@login_required
def link_preview(request):
    return link_preview_response(request.GET.get("url", ""))


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, "landing.html")
    user = request.user
    visible = Profile.objects.visible_to(user)
    managed = Profile.objects.managed_by(user)
    lists = Wishlist.objects.select_related("profile__user").annotate(n=Count("products"))
    pending = Product.objects.filter(
        visibility=Product.Visibility.PENDING, wishlist__profile__in=managed
    ).exclude(suggested_by=user).count()
    return render(request, "wishlists/dashboard.html", {
        "my_lists": lists.filter(profile__in=managed).order_by("profile__name", "event_date"),
        "family_lists": lists.filter(profile__in=visible).exclude(profile__in=managed),
        "birthdays": upcoming_birthdays(visible, 60),
        "pending_suggestions": pending,
        "open_reservations": user.reservations.filter(status=Reservation.Status.RESERVED).count(),
        "has_group": user.memberships.exists(),
    })


def _wishlist_for_viewer(request, pk):
    wishlist = get_object_or_404(Wishlist.objects.select_related("profile__user"), pk=pk)
    if not access.can_view(request.user, wishlist):
        raise Http404
    return wishlist


def _wishlist_for_editor(request, pk):
    wishlist = _wishlist_for_viewer(request, pk)
    if not access.can_edit(request.user, wishlist):
        raise PermissionDenied
    return wishlist


@login_required
def wishlist_create(request):
    initial = {"profile": request.GET.get("profil")} if request.GET.get("profil") else None
    form = WishlistForm(request.POST or None, user=request.user, initial=initial)
    if form.is_valid():
        wishlist = form.save()
        messages.success(request, "Liste angelegt – jetzt fehlen nur noch die Wünsche.")
        return redirect(wishlist)
    return render(request, "wishlists/wishlist_form.html", {"form": form})


@login_required
def wishlist_detail(request, pk):
    wishlist = _wishlist_for_viewer(request, pk)
    user = request.user
    show_reservations = access.can_see_reservations(user, wishlist)
    products = access.visible_products(user, wishlist)
    public_url = wishlist.get_public_url()
    rows = _product_rows(products.exclude(visibility=Product.Visibility.PENDING), user=user,
                         show_reservations=show_reservations)
    return render(request, "wishlists/wishlist_detail.html", {
        "wishlist": wishlist,
        "rows": rows,
        "suggestions": products.filter(visibility=Product.Visibility.PENDING),
        "can_edit": access.can_edit(user, wishlist),
        "is_recipient": access.is_recipient(user, wishlist),
        "show_reservations": show_reservations,
        "theme": wishlist.resolved_theme(),
        "public_url": public_url and request.build_absolute_uri(public_url),
        "profile_public_url": public_url and request.build_absolute_uri(wishlist.profile.get_public_url()),
    })


@login_required
def wishlist_edit(request, pk):
    wishlist = _wishlist_for_editor(request, pk)
    form = WishlistForm(request.POST or None, instance=wishlist, user=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect(wishlist)
    return render(request, "wishlists/wishlist_form.html", {"form": form, "wishlist": wishlist})


@login_required
def wishlist_delete(request, pk):
    wishlist = _wishlist_for_editor(request, pk)
    if request.method == "POST":
        wishlist.delete()
        messages.success(request, f"„{wishlist.title}“ wurde gelöscht.")
        return redirect("dashboard")
    return render(request, "confirm_delete.html", {
        "object": wishlist,
        "warning": "Alle Wünsche und Reservierungen dieser Liste gehen verloren.",
        "cancel_url": wishlist.get_absolute_url(),
    })


@login_required
def product_create(request, pk):
    """Editors add wishes; everyone else who can see the list makes a suggestion."""
    wishlist = _wishlist_for_viewer(request, pk)
    is_editor = access.can_edit(request.user, wishlist)
    form_class = ProductForm if is_editor else SuggestionForm
    form = form_class(request.POST or None)
    if form.is_valid():
        with transaction.atomic():
            product = form.save(commit=False)
            product.wishlist = wishlist
            if not is_editor:
                product.suggested_by = request.user
            product.save()
            _start_scraping(product)
        if is_editor:
            messages.success(request, "Wunsch hinzugefügt.")
        else:
            messages.success(request, "Danke für deinen Vorschlag!")
        return redirect(wishlist)
    return render(request, "wishlists/product_form.html", {
        "form": form, "wishlist": wishlist, "is_suggestion": not is_editor,
        "theme": wishlist.resolved_theme(),
    })


@login_required
@require_POST
def product_quick_add(request, pk):
    """Only a link – everything else comes from the shop page."""
    wishlist = _wishlist_for_editor(request, pk)
    form = QuickAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Bitte einen gültigen Link einfügen.")
        return redirect(wishlist)
    with transaction.atomic():
        product = Product.objects.create(wishlist=wishlist, shop_url=form.cleaned_data["shop_url"])
        _start_scraping(product)
    messages.success(request, "Wunsch hinzugefügt – die Angaben werden aus dem Link geholt.")
    return redirect(wishlist)


def _product_for_editor(request, pk):
    """List editors may change every product; suggesters keep control over their own suggestions."""
    product = get_object_or_404(Product.objects.select_related("wishlist__profile__user"), pk=pk)
    wishlist = product.wishlist
    if not access.can_see_product(request.user, product):
        raise Http404
    is_own_suggestion = product.suggested_by_id == request.user.pk and product.visibility != Product.Visibility.VISIBLE
    if not (access.can_edit(request.user, wishlist) or is_own_suggestion):
        raise PermissionDenied
    return product


@login_required
def product_edit(request, pk):
    product = _product_for_editor(request, pk)
    old_url = product.shop_url
    form = ProductForm(request.POST or None, instance=product)
    if form.is_valid():
        with transaction.atomic():
            product = form.save()
            if product.shop_url != old_url:
                _start_scraping(product)
        messages.success(request, "Gespeichert.")
        return redirect(product.wishlist)
    return render(request, "wishlists/product_form.html", {
        "form": form, "wishlist": product.wishlist, "product": product,
        "theme": product.wishlist.resolved_theme(),
    })


@login_required
def product_delete(request, pk):
    product = _product_for_editor(request, pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, f"„{product}“ wurde entfernt.")
        return redirect(product.wishlist)
    return render(request, "confirm_delete.html", {
        "object": product,
        "warning": "Reservierungen für diesen Wunsch werden ebenfalls gelöscht.",
        "cancel_url": product.wishlist.get_absolute_url(),
    })


@login_required
@require_POST
def product_rescrape(request, pk):
    product = _product_for_editor(request, pk)
    if product.shop_url:
        with transaction.atomic():
            _start_scraping(product, overwrite=True)
    return redirect(product.wishlist)


@login_required
def product_status(request, pk):
    """Polled by the list page while product data is being fetched."""
    product = get_object_or_404(Product, pk=pk)
    if not access.can_see_product(request.user, product):
        raise Http404
    return JsonResponse({"status": product.scrape_status})


@login_required
@require_POST
def suggestion_decide(request, pk, decision):
    product = get_object_or_404(Product, pk=pk, visibility=Product.Visibility.PENDING)
    if not access.can_edit(request.user, product.wishlist):
        raise PermissionDenied
    if decision == "annehmen":
        product.visibility = Product.Visibility.VISIBLE
        product.save(update_fields=["visibility"])
        messages.success(request, f"„{product}“ steht jetzt auf der Liste.")
    else:
        product.delete()
        messages.success(request, "Vorschlag abgelehnt.")
    return redirect(product.wishlist)


def _save_reservation(request, product, form_class, mine_filter, **owner):
    """Create or change the caller's reservation; None (with a message) when it does not fit."""
    with transaction.atomic():
        # Lock the product so two people cannot reserve the last piece at the same time
        product = Product.objects.select_for_update().get(pk=product.pk)
        mine = product.reservations.filter(**mine_filter).first()
        others = product.quantity_reserved() - (mine.quantity if mine else 0)
        form = form_class(request.POST, instance=mine, max_quantity=product.quantity_desired - others)
        if not form.is_valid():
            messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
            return None
        reservation = form.save(commit=False)
        reservation.product = product
        for field, value in owner.items():
            setattr(reservation, field, value)
        reservation.save()
        return reservation


@login_required
@require_POST
def reserve(request, pk):
    product = get_object_or_404(Product.objects.select_related("wishlist__profile"), pk=pk)
    wishlist = product.wishlist
    if not access.can_see_product(request.user, product):
        raise Http404
    if access.is_recipient(request.user, wishlist) or product.visibility == Product.Visibility.PENDING:
        raise PermissionDenied
    reservation = _save_reservation(request, product, ReservationForm, {"reserved_by": request.user},
                                    reserved_by=request.user)
    if reservation:
        messages.success(request, f"„{product}“: {reservation.get_status_display()}, {reservation.quantity}×.")
    return redirect(_safe_next(request) or wishlist)


@login_required
@require_POST
def reservation_delete(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("product__wishlist"), pk=pk,
                                    reserved_by=request.user)
    reservation.delete()
    messages.success(request, f"Reservierung für „{reservation.product}“ aufgehoben.")
    return redirect(_safe_next(request) or reservation.product.wishlist.get_absolute_url())


@login_required
def my_reservations(request):
    reservations = (
        request.user.reservations
        .select_related("product__wishlist__profile__user")
        .order_by("status", "product__wishlist__event_date", "product__title")
    )
    return render(request, "wishlists/my_reservations.html", {"reservations": reservations})


def _safe_next(request):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return None


def _public_profile(family_slug, profile_slug):
    """The profile behind /<family>/<profile>/ – only if it really belongs to that family."""
    family = get_object_or_404(FamilyGroup, slug=family_slug)
    profile = get_object_or_404(
        Profile.objects.select_related("user").filter(
            Q(family_group=family) | Q(user__memberships__group=family)
        ).distinct(),
        slug=profile_slug,
    )
    return family, profile


def _public_wishlist(family_slug, profile_slug, list_slug):
    family, profile = _public_profile(family_slug, profile_slug)
    wishlist = get_object_or_404(profile.wishlists.select_related("profile__user"), slug=list_slug,
                                 public_enabled=True)
    return family, wishlist


def _public_list_url(family, wishlist):
    return reverse("public_wishlist", args=[family.slug, wishlist.profile.slug, wishlist.slug])


def public_profile(request, family, profile):
    family, profile = _public_profile(family, profile)
    wishlists = list(profile.wishlists.filter(public_enabled=True))
    if not wishlists:
        raise Http404
    if len(wishlists) == 1:
        return redirect(_public_list_url(family, wishlists[0]))
    return render(request, "wishlists/public_profile.html", {
        "family": family, "profile": profile, "wishlists": wishlists,
    })


def public_wishlist(request, family, profile, wishlist):
    family, wishlist = _public_wishlist(family, profile, wishlist)
    show_reservations = access.can_see_reservations(request.user, wishlist)
    guest_key = request.session.get(GUEST_SESSION_KEY)
    rows = _product_rows(access.public_products(wishlist), user=request.user, guest_key=guest_key,
                         show_reservations=show_reservations)
    return render(request, "wishlists/public_wishlist.html", {
        "family": family,
        "wishlist": wishlist,
        "rows": rows,
        "show_reservations": show_reservations,
        "theme": wishlist.resolved_theme(),
        "is_member": access.can_view(request.user, wishlist),
    })


@require_POST
def public_reserve(request, family, profile, wishlist, pk):
    family, wishlist = _public_wishlist(family, profile, wishlist)
    product = get_object_or_404(access.public_products(wishlist), pk=pk)
    if access.is_recipient(request.user, wishlist):
        raise PermissionDenied
    if request.user.is_authenticated:
        reservation = _save_reservation(request, product, ReservationForm, {"reserved_by": request.user},
                                        reserved_by=request.user)
    else:
        guest_key = request.session.get(GUEST_SESSION_KEY) or str(uuid.uuid4())
        reservation = _save_reservation(request, product, GuestReservationForm, {"guest_key": guest_key},
                                        guest_key=guest_key)
        if reservation:
            request.session[GUEST_SESSION_KEY] = guest_key
    if reservation:
        messages.success(request, f"Danke! „{product}“ ist für dich reserviert.")
    return redirect(_public_list_url(family, wishlist))


@require_POST
def public_unreserve(request, family, profile, wishlist, pk):
    family, wishlist = _public_wishlist(family, profile, wishlist)
    guest_key = request.session.get(GUEST_SESSION_KEY)
    if not guest_key:
        raise Http404
    reservation = get_object_or_404(Reservation, pk=pk, guest_key=guest_key, product__wishlist=wishlist)
    reservation.delete()
    messages.success(request, "Reservierung aufgehoben.")
    return redirect(_public_list_url(family, wishlist))
