"""Cada inspector queda con una sola sede y una sede puede tener varios inspectores."""
import django.db.models.deletion
from django.db import migrations, models


def dejar_una_sede_por_inspector(apps, schema_editor):
    # Si un inspector tenía varias sedes, conserva la primera que se le asignó.
    DelegadoSede = apps.get_model('usuarios', 'DelegadoSede')
    vistos = set()
    for relacion in DelegadoSede.objects.order_by('delegado_id', 'id'):
        if relacion.delegado_id in vistos:
            relacion.delete()
        else:
            vistos.add(relacion.delegado_id)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0050_cifrar_fotos_estudiantes'),
    ]

    operations = [
        migrations.RunPython(dejar_una_sede_por_inspector, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='delegadosede',
            name='sede',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='inspectores', to='usuarios.sede',
            ),
        ),
        migrations.AddConstraint(
            model_name='delegadosede',
            constraint=models.UniqueConstraint(fields=('delegado',), name='inspector_con_una_sola_sede'),
        ),
    ]
