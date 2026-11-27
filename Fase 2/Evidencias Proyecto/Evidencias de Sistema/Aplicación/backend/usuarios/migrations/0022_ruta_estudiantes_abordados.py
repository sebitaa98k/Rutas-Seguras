from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0021_perfildelegado_tipo_delegado'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruta',
            name='estudiantes_abordados',
            field=models.ManyToManyField(
                blank=True,
                related_name='rutas_abordadas',
                to='usuarios.estudiante',
            ),
        ),
    ]
