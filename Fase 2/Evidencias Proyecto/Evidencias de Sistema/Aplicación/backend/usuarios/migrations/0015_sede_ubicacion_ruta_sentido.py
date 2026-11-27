from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0014_ruta_gestion_operativa'),
    ]

    operations = [
        migrations.AddField(
            model_name='sede',
            name='latitud',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='sede',
            name='longitud',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='ruta',
            name='sentido',
            field=models.CharField(
                choices=[
                    ('hacia_colegio', 'Hacia el colegio'),
                    ('desde_colegio', 'Desde el colegio'),
                ],
                default='hacia_colegio',
                max_length=20,
            ),
        ),
    ]
