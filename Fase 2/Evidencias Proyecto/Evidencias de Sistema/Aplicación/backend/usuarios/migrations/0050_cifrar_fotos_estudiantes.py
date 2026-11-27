from pathlib import Path

from django.conf import settings
from django.db import migrations, models

import usuarios.almacenamiento
import usuarios.models


def _archivos_de_fotos(apps):
    """Las fotos de los estudiantes y también los restos que quedaron en su carpeta (fotos reemplazadas o de
    estudiantes eliminados): ninguna foto de un menor debe quedar legible en el disco."""
    Estudiante = apps.get_model('usuarios', 'Estudiante')
    raiz = Path(settings.MEDIA_ROOT)
    rutas = {
        raiz / nombre
        for nombre in Estudiante.objects.exclude(foto='').exclude(foto__isnull=True).values_list('foto', flat=True)
    }
    carpeta = raiz / 'fotos_estudiantes'
    if carpeta.is_dir():
        rutas.update(carpeta.iterdir())
    return sorted(ruta for ruta in rutas if ruta.is_file())


def cifrar_fotos_existentes(apps, schema_editor):
    """Cifra en el disco las fotos guardadas antes de este cambio. Las ya cifradas no se tocan."""
    from usuarios.almacenamiento import cifrar_bytes, es_imagen_sin_cifrar

    for ruta in _archivos_de_fotos(apps):
        datos = ruta.read_bytes()
        if es_imagen_sin_cifrar(datos):
            ruta.write_bytes(cifrar_bytes(datos))


def descifrar_fotos(apps, schema_editor):
    from usuarios.almacenamiento import descifrar_bytes, es_imagen_sin_cifrar

    for ruta in _archivos_de_fotos(apps):
        datos = ruta.read_bytes()
        if not es_imagen_sin_cifrar(datos):
            ruta.write_bytes(descifrar_bytes(datos))


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0049_simulador_de_ruta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estudiante',
            name='foto',
            field=models.ImageField(
                blank=True,
                help_text='Foto privada del estudiante, cifrada; nunca se publica como archivo estático.',
                null=True,
                storage=usuarios.almacenamiento.almacenamiento_fotos_estudiantes,
                upload_to=usuarios.models.foto_estudiante_upload_to,
            ),
        ),
        migrations.RunPython(cifrar_fotos_existentes, descifrar_fotos),
    ]
