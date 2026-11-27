from django.contrib.auth.hashers import make_password
from django.db import migrations


def mark_empty_passwords_unusable(apps, schema_editor):
    """Evita dejar cuentas antiguas con una credencial vacía inválida."""
    Usuario = apps.get_model('usuarios', 'Usuario')
    Usuario.objects.filter(password='').update(password=make_password(None))


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0016_hash_legacy_plaintext_passwords'),
    ]

    operations = [
        migrations.RunPython(mark_empty_passwords_unusable, migrations.RunPython.noop),
    ]
