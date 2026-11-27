from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0030_ruta_estudiantes_ausentes'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruta',
            name='estudiantes_entregados',
            field=models.ManyToManyField(
                blank=True,
                related_name='rutas_entregadas',
                to='usuarios.estudiante',
            ),
        ),
    ]
