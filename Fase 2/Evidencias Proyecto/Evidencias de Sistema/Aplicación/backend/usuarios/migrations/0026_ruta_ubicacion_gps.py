from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0025_ruta_paradas_completadas'),
    ]

    operations = [
        migrations.AddField(
            model_name='ruta',
            name='ultima_latitud',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='ruta',
            name='ultima_longitud',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='ruta',
            name='precision_gps_metros',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='ruta',
            name='ubicacion_actualizada_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
