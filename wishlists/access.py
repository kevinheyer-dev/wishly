"""Who may see and change what – the surprise protection lives here."""

from accounts.models import Profile

from .models import Product, Wishlist


def visible_wishlists(user):
    return Wishlist.objects.filter(profile__in=Profile.objects.visible_to(user))


def can_view(user, wishlist):
    return user.is_authenticated and Profile.objects.visible_to(user).filter(pk=wishlist.profile_id).exists()


def can_edit(user, wishlist):
    return wishlist.profile.can_manage(user)


def is_recipient(user, wishlist):
    """The person the gifts are for. Guardians of a child are gift givers, not recipients."""
    return user.is_authenticated and wishlist.profile.user_id == user.pk


def visible_products(user, wishlist):
    """Products the user may see on the list.

    The recipient never sees secret suggestions; pending suggestions are only visible to the
    people who decide about them and to whoever suggested them.
    """
    products = wishlist.products.select_related("suggested_by")
    if is_recipient(user, wishlist):
        return products.exclude(visibility=Product.Visibility.SECRET)
    if can_edit(user, wishlist):
        return products
    pending_by_others = products.filter(visibility=Product.Visibility.PENDING).exclude(suggested_by=user)
    return products.exclude(pk__in=pending_by_others)


def public_products(wishlist):
    return wishlist.products.filter(visibility=Product.Visibility.VISIBLE)


def can_see_reservations(user, wishlist):
    return not is_recipient(user, wishlist)


def can_see_product(user, product):
    return can_view(user, product.wishlist) and visible_products(user, product.wishlist).filter(pk=product.pk).exists()
