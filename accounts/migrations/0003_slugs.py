from django.db import migrations, models

import accounts.slugs


def fill_slugs(apps, schema_editor):
    # Historical models have no custom save(), so the slugs are computed here
    from accounts.slugs import RESERVED, unique_slug

    FamilyGroup = apps.get_model("accounts", "FamilyGroup")
    Profile = apps.get_model("accounts", "Profile")
    for group in FamilyGroup.objects.order_by("pk"):
        group.slug = unique_slug(FamilyGroup.objects.exclude(pk=group.pk), group.name, "familie", RESERVED)
        group.save(update_fields=["slug"])
    for profile in Profile.objects.select_related("user").order_by("pk"):
        source = (profile.user.first_name or profile.user.username) if profile.user_id else profile.name
        profile.slug = unique_slug(Profile.objects.exclude(pk=profile.pk), source, "profil")
        profile.save(update_fields=["slug"])


# Added without an index first: on PostgreSQL the later unique=True would otherwise create the
# "_like" index a second time.
class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_child_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="familygroup",
            name="slug",
            field=models.SlugField(blank=True, db_index=False, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="profile",
            name="slug",
            field=models.SlugField(blank=True, db_index=False, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="familygroup",
            name="slug",
            field=models.SlugField(
                blank=True, help_text="Erster Teil der öffentlichen Links, z. B. „mueller“. Leer lassen = aus dem Namen.",
                max_length=50, unique=True, validators=[accounts.slugs.validate_not_reserved], verbose_name="Name in Links",
            ),
        ),
        migrations.AlterField(
            model_name="profile",
            name="slug",
            field=models.SlugField(
                blank=True, help_text="Zweiter Teil der öffentlichen Links, z. B. „anna“. Leer lassen = aus dem Namen.",
                max_length=50, unique=True, verbose_name="Name in Links",
            ),
        ),
    ]
