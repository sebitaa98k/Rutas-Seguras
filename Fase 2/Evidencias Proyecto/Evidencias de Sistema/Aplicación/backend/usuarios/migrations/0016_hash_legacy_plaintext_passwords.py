from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations


def hash_legacy_plaintext_passwords(apps, schema_editor):
    """Repara credenciales antiguas creadas sin ``set_password``.

    Las contraseñas ya codificadas y las contraseñas inutilizables se dejan
    intactas. El valor original nunca se registra ni se expone.
    """
    Usuario = apps.get_model('usuarios', 'Usuario')

    for usuario in Usuario.objects.all().only('id', 'password').iterator():
        if not usuario.password or usuario.password.startswith('!'):
            continue

        try:
            identify_hasher(usuario.password)
        except ValueError:
            usuario.password = make_password(usuario.password)
            usuario.save(update_fields=['password'])


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0015_sede_ubicacion_ruta_sentido'),
    ]

    operations = [
        migrations.RunPython(hash_legacy_plaintext_passwords, migrations.RunPython.noop),
    ]
