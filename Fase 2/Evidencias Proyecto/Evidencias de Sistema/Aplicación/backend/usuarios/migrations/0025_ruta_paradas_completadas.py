from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0024_colegio_ubicacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruta',
            name='paradas_completadas',
            field=models.ManyToManyField(
                blank=True,
                related_name='rutas_con_parada_completada',
                to='usuarios.estudiante',
            ),
        ),
    ]
