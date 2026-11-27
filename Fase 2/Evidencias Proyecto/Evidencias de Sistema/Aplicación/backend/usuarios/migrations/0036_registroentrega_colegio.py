from django.db import migrations, models
import django.db.models.deletion


def completar_colegio(apps, schema_editor):
    RegistroEntrega = apps.get_model('usuarios', 'RegistroEntrega')
    for registro in RegistroEntrega.objects.select_related('ruta').all():
        registro.colegio_id = registro.ruta.colegio_id
        registro.save(update_fields=['colegio'])


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0035_notificacion_destinatario')]
    operations = [
        migrations.AddField(
            model_name='registroentrega', name='colegio',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='registros_entrega', to='usuarios.colegio'),
        ),
        migrations.RunPython(completar_colegio, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='registroentrega', name='colegio',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='registros_entrega', to='usuarios.colegio'),
        ),
    ]
