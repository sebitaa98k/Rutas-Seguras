from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0032_inasistencia_estudiante'),
    ]

    operations = [
        migrations.AddField(
            model_name='emergencia',
            name='ruta',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='emergencias', to='usuarios.ruta'),
        ),
        migrations.AddField(
            model_name='emergencia',
            name='colegio',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='emergencias', to='usuarios.colegio'),
        ),
        migrations.AddField(
            model_name='emergencia',
            name='furgon',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='emergencias', to='usuarios.furgon'),
        ),
    ]
