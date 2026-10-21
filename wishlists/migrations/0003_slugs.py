from django.db import migrations, models


def fill_slugs(apps, schema_editor):
    from accounts.slugs import unique_slug

    Wishlist = apps.get_model("wishlists", "Wishlist")
    for wishlist in Wishlist.objects.order_by("pk"):
        others = Wishlist.objects.filter(profile_id=wishlist.profile_id).exclude(pk=wishlist.pk)
        wishlist.slug = unique_slug(others, wishlist.title, "liste")
        wishlist.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_slugs"),
        ("wishlists", "0002_child_link"),
    ]

    operations = [
        migrations.RemoveField(model_name="wishlist", name="public_id"),
        migrations.AddField(
            model_name="wishlist",
            name="slug",
            field=models.SlugField(
                blank=True, max_length=50, verbose_name="Name in Links",
                help_text="Letzter Teil des öffentlichen Links, z. B. „weihnachten-2026“. Leer lassen = aus dem Titel.",
            ),
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="wishlist",
            name="public_enabled",
            field=models.BooleanField(
                default=False, verbose_name="Öffentlicher Link aktiv",
                help_text="Jeder, der den Link kennt oder errät, kann die Liste sehen und Wünsche reservieren.",
            ),
        ),
        migrations.AddConstraint(
            model_name="wishlist",
            constraint=models.UniqueConstraint(
                fields=("profile", "slug"), name="unique_wishlist_slug",
                violation_error_message="Diesen Namen hat schon eine andere Liste.",
            ),
        ),
    ]
