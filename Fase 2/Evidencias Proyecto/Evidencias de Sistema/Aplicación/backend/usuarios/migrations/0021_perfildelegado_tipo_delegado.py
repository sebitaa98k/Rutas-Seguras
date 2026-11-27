from django.db import migrations, models


def clasificar_inspectores_existentes(apps, schema_editor):
    PerfilDelegado = apps.get_model('usuarios', 'PerfilDelegado')
    Estudiante = apps.get_model('usuarios', 'Estudiante')

    ruts_autorizados = {
        str(rut).replace('.', '').replace('-', '').upper().strip()
        for rut in Estudiante.objects.exclude(rut_persona_autorizada__isnull=True)
        .exclude(rut_persona_autorizada='')
        .values_list('rut_persona_autorizada', flat=True)
    }

    for perfil in PerfilDelegado.objects.all():
        rut = (perfil.rut or '').replace('.', '').replace('-', '').upper().strip()
        tiene_sede = perfil.sedes_responsable.filter(activo=True).exists()
        if tiene_sede or (perfil.colegio_id and rut not in ruts_autorizados):
            perfil.tipo_delegado = 'inspector'
            perfil.save(update_fields=['tipo_delegado'])


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0020_delegadosede'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfildelegado',
            name='tipo_delegado',
            field=models.CharField(
                choices=[
                    ('autorizado', 'Persona autorizada por apoderado'),
                    ('inspector', 'Inspector del establecimiento'),
                ],
                default='autorizado',
                max_length=20,
            ),
        ),
        migrations.RunPython(clasificar_inspectores_existentes, migrations.RunPython.noop),
    ]
