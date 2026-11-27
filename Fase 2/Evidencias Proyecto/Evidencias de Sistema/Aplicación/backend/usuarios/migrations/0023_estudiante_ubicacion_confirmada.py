from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0022_ruta_estudiantes_abordados'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='latitud',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='longitud',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='ubicacion_confirmada',
            field=models.BooleanField(default=False),
        ),
    ]

