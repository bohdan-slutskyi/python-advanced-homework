from django.db import migrations


def seed_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ("Tenant", "Landlord"):
        Group.objects.using(schema_editor.connection.alias).get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_groups, migrations.RunPython.noop)]
