import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0013_migrar_datos_colegios'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ruta',
            name='estado',
            field=models.CharField(
                choices=[
                    ('activa', 'Activa'),
                    ('en_ruta', 'En ruta'),
                    ('finalizada', 'Finalizada'),
                    ('inactiva', 'Inactiva'),
                ],
                default='activa',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='ruta',
            name='conductor_perfil',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rutas', to='usuarios.perfilconductor'),
        ),
        migrations.AddField(
            model_name='ruta',
            name='furgon',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rutas', to='usuarios.furgon'),
        ),
        migrations.AddField(
            model_name='ruta',
            name='estudiantes',
            field=models.ManyToManyField(blank=True, related_name='rutas', to='usuarios.estudiante'),
        ),
        migrations.AddField(model_name='ruta', name='origen_direccion', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='ruta', name='destino_direccion', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='ruta', name='origen_latitud', field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name='ruta', name='origen_longitud', field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name='ruta', name='destino_latitud', field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name='ruta', name='destino_longitud', field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name='ruta', name='iniciada_en', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='ruta', name='finalizada_en', field=models.DateTimeField(blank=True, null=True)),
    ]
