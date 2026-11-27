from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0026_ruta_ubicacion_gps'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='embedding_facial_version',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='perfilapoderado',
            name='embedding_facial_version',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='perfildelegado',
            name='embedding_facial_version',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
