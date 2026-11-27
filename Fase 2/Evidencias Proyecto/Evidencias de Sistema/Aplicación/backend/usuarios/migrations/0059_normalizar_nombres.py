"""Deja con el formato nuevo ("Juan Carlos de la Fuente") los nombres que ya estaban guardados."""
from django.db import migrations

from usuarios.nombres import normalizar_nombre


def _normalizar(modelo, campos):
    for registro in modelo.objects.all().only('pk', *campos).iterator():
        cambios = {campo: normalizar_nombre(getattr(registro, campo)) for campo in campos}
        if any(cambios[campo] != getattr(registro, campo) for campo in campos):
            modelo.objects.filter(pk=registro.pk).update(**cambios)


def normalizar_existentes(apps, schema_editor):
    _normalizar(apps.get_model('usuarios', 'Usuario'), ('first_name', 'last_name'))
    _normalizar(apps.get_model('usuarios', 'Estudiante'), ('nombre', 'apellido', 'persona_autorizada'))
    _normalizar(apps.get_model('usuarios', 'PersonaAutorizada'), ('nombre',))


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0058_historial_biometria'),
    ]

    operations = [
        migrations.RunPython(normalizar_existentes, migrations.RunPython.noop),
    ]
