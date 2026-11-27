from django.db import migrations

ESTADOS_RUTA_VIGENTE = ('activa', 'en_ruta', 'finalizada')


def sincronizar_conductor_desde_rutas(apps, schema_editor):
    """La ruta pasa a ser la fuente de verdad de la asignación conductor-estudiante."""
    Estudiante = apps.get_model('usuarios', 'Estudiante')
    for estudiante in Estudiante.objects.all():
        ruta = (
            estudiante.rutas.exclude(conductor_perfil__isnull=True)
            .filter(estado__in=ESTADOS_RUTA_VIGENTE)
            .order_by('id')
            .first()
        )
        conductor_id = ruta.conductor_perfil_id if ruta else None
        if estudiante.conductor_id != conductor_id:
            estudiante.conductor_id = conductor_id
            estudiante.save(update_fields=['conductor'])


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0027_version_embedding_facial'),
    ]

    operations = [
        migrations.RunPython(sincronizar_conductor_desde_rutas, migrations.RunPython.noop),
    ]
