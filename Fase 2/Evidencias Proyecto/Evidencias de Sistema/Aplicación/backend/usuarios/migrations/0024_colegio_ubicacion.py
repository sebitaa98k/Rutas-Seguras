from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0023_estudiante_ubicacion_confirmada'),
    ]

    operations = [
        migrations.AddField(
            model_name='colegio',
            name='latitud',
            field=models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='colegio',
            name='longitud',
            field=models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True),
        ),
    ]

