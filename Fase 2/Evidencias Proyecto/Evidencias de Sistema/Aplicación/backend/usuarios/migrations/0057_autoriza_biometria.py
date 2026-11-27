from django.db import migrations, models


def conservar_autorizaciones(apps, schema_editor):
    """Hasta ahora aceptar los términos incluía la biometría: esas cuentas quedan autorizadas."""
    Usuario = apps.get_model('usuarios', 'Usuario')
    AceptacionTerminos = apps.get_model('usuarios', 'AceptacionTerminos')
    for usuario in Usuario.objects.filter(rol='apoderado').exclude(terminos_version_aceptada=''):
        ultima = AceptacionTerminos.objects.filter(usuario=usuario).order_by('-aceptado_en').first()
        usuario.autoriza_biometria = True
        usuario.autoriza_biometria_en = ultima.aceptado_en if ultima else None
        usuario.save(update_fields=['autoriza_biometria', 'autoriza_biometria_en'])


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0056_estudiantes_habilitados'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='autoriza_biometria',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='usuario',
            name='autoriza_biometria_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(conservar_autorizaciones, migrations.RunPython.noop),
    ]
