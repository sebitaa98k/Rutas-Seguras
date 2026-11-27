from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def completar_destinatarios(apps, schema_editor):
    Notificacion = apps.get_model('usuarios', 'Notificacion')
    for notificacion in Notificacion.objects.select_related('apoderado').all():
        if notificacion.apoderado_id:
            notificacion.destinatario_id = notificacion.apoderado.usuario_id
            notificacion.save(update_fields=['destinatario'])


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0034_personas_autorizadas_registro_entrega')]
    operations = [
        migrations.AlterField(
            model_name='notificacion', name='apoderado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones', to='usuarios.perfilapoderado'),
        ),
        migrations.AddField(
            model_name='notificacion', name='destinatario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones_recibidas', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(completar_destinatarios, migrations.RunPython.noop),
    ]
