from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from wishlists.access import visible_products

from .forms import AccountForm, ChildProfileForm, GroupForm, OwnProfileForm, SignupForm
from .models import FamilyGroup, Membership, Profile, new_invite_token


def signup(request):
    if not settings.ALLOW_SIGNUP:
        raise Http404
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(
            request, "Willkommen bei wishly! Lege eine Familie an oder tritt über einen Einladungslink bei."
        )
        target = request.GET.get("next", "")
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
            target = "dashboard"
        return redirect(target)
    return render(request, "registration/signup.html", {"form": form})


@login_required
def account(request):
    profile = request.user.profile
    account_form = AccountForm(request.POST or None, instance=request.user, prefix="account")
    profile_form = OwnProfileForm(request.POST or None, instance=profile, prefix="profile")
    if request.method == "POST" and account_form.is_valid() and profile_form.is_valid():
        account_form.save()
        profile_form.save()
        messages.success(request, "Gespeichert.")
        return redirect("account")
    return render(request, "accounts/account.html", {"account_form": account_form, "profile_form": profile_form})


def _group_for_member(request, pk):
    group = get_object_or_404(FamilyGroup, pk=pk)
    if not group.memberships.filter(user=request.user).exists():
        raise Http404
    return group


def _require_admin(request, group):
    if not group.is_admin(request.user):
        raise PermissionDenied


@login_required
def group_list(request):
    groups = request.user.family_groups.all()
    return render(request, "accounts/group_list.html", {"groups": groups})


@login_required
def group_create(request):
    form = GroupForm(request.POST or None)
    if form.is_valid():
        with transaction.atomic():
            group = form.save()
            Membership.objects.create(user=request.user, group=group, role=Membership.Role.ADMIN)
        messages.success(request, "Familie angelegt. Teile den Einladungslink mit deinen Liebsten.")
        return redirect(group)
    return render(request, "accounts/group_form.html", {"form": form})


@login_required
def group_detail(request, pk):
    group = _group_for_member(request, pk)
    memberships = group.memberships.select_related("user__profile")
    return render(request, "accounts/group_detail.html", {
        "group": group,
        "memberships": memberships,
        "children": group.child_profiles.prefetch_related("guardians"),
        "is_admin": group.is_admin(request.user),
        "invite_url": request.build_absolute_uri(reverse("group_join", args=[group.invite_token])),
    })


@login_required
def group_edit(request, pk):
    group = _group_for_member(request, pk)
    _require_admin(request, group)
    form = GroupForm(request.POST or None, instance=group)
    if form.is_valid():
        form.save()
        return redirect(group)
    return render(request, "accounts/group_form.html", {"form": form, "group": group})


@login_required
def group_delete(request, pk):
    group = _group_for_member(request, pk)
    _require_admin(request, group)
    if request.method == "POST":
        group.delete()
        messages.success(request, f"„{group.name}“ wurde gelöscht.")
        return redirect("group_list")
    return render(request, "confirm_delete.html", {
        "object": group,
        "warning": "Alle Kinderprofile dieser Familie und ihre Listen werden ebenfalls gelöscht.",
        "cancel_url": group.get_absolute_url(),
    })


@login_required
@require_POST
def group_new_invite(request, pk):
    group = _group_for_member(request, pk)
    _require_admin(request, group)
    group.invite_token = new_invite_token()
    group.save(update_fields=["invite_token"])
    messages.success(request, "Neuer Einladungslink erstellt – der alte gilt nicht mehr.")
    return redirect(group)


@login_required
def group_join(request, token):
    group = get_object_or_404(FamilyGroup, invite_token=token)
    if group.memberships.filter(user=request.user).exists():
        return redirect(group)
    if request.method == "POST":
        Membership.objects.get_or_create(user=request.user, group=group)
        messages.success(request, f"Du bist jetzt Mitglied von „{group.name}“.")
        return redirect(group)
    return render(request, "accounts/group_join.html", {"group": group})


def _admin_count(group):
    return group.memberships.filter(role=Membership.Role.ADMIN).count()


@login_required
@require_POST
def member_role(request, pk, membership_pk):
    group = _group_for_member(request, pk)
    _require_admin(request, group)
    membership = get_object_or_404(group.memberships, pk=membership_pk)
    role = request.POST.get("role")
    if role not in Membership.Role.values:
        raise Http404
    if membership.role == Membership.Role.ADMIN and role != membership.role and _admin_count(group) == 1:
        messages.error(request, "Eine Familie braucht mindestens einen Administrator.")
    else:
        membership.role = role
        membership.save(update_fields=["role"])
    return redirect(group)


@login_required
@require_POST
def member_remove(request, pk, membership_pk):
    """Admins remove anyone; every member may remove themselves (leave)."""
    group = _group_for_member(request, pk)
    membership = get_object_or_404(group.memberships, pk=membership_pk)
    if membership.user_id != request.user.pk:
        _require_admin(request, group)
    if membership.role == Membership.Role.ADMIN and _admin_count(group) == 1 and group.memberships.count() > 1:
        messages.error(request, "Ernenne zuerst einen anderen Administrator.")
        return redirect(group)
    with transaction.atomic():
        membership.delete()
        for child in group.child_profiles.filter(guardians=membership.user):
            child.guardians.remove(membership.user)
        if not group.memberships.exists():
            group.delete()
    if membership.user_id == request.user.pk:
        messages.success(request, f"Du hast „{group.name}“ verlassen.")
        return redirect("group_list")
    return redirect(group)


@login_required
def child_create(request, pk):
    group = _group_for_member(request, pk)
    form = ChildProfileForm(request.POST or None, group=group, initial={"guardians": [request.user]})
    if form.is_valid():
        child = form.save(commit=False)
        child.family_group = group
        child.save()
        form.save_m2m()
        messages.success(request, f"Profil für {child.name} angelegt.")
        return redirect(child)
    return render(request, "accounts/child_form.html", {"form": form, "group": group})


def _visible_profile(request, pk):
    profile = get_object_or_404(Profile.objects.select_related("user", "family_group"), pk=pk)
    if not Profile.objects.visible_to(request.user).filter(pk=pk).exists():
        raise Http404
    return profile


@login_required
def profile_detail(request, pk):
    profile = _visible_profile(request, pk)
    wishlists = []
    for wishlist in profile.wishlists.all():
        products = visible_products(request.user, wishlist)
        wishlists.append((wishlist, products.count()))
    return render(request, "accounts/profile_detail.html", {
        "profile": profile,
        "wishlists": wishlists,
        "can_manage": profile.can_manage(request.user),
    })


@login_required
def child_edit(request, pk):
    profile = _visible_profile(request, pk)
    if not profile.is_child:
        return redirect("account")
    if not profile.can_manage(request.user):
        raise PermissionDenied
    form = ChildProfileForm(request.POST or None, instance=profile, group=profile.family_group)
    if form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect(profile)
    return render(request, "accounts/child_form.html",
                  {"form": form, "group": profile.family_group, "profile": profile})


@login_required
def child_delete(request, pk):
    profile = _visible_profile(request, pk)
    if not profile.is_child or not profile.can_manage(request.user):
        raise PermissionDenied
    if request.method == "POST":
        group = profile.family_group
        profile.delete()
        messages.success(request, f"Profil von {profile.name} gelöscht.")
        return redirect(group)
    return render(request, "confirm_delete.html", {
        "object": profile,
        "warning": "Alle Wunschlisten dieses Profils werden ebenfalls gelöscht.",
        "cancel_url": profile.get_absolute_url(),
    })
