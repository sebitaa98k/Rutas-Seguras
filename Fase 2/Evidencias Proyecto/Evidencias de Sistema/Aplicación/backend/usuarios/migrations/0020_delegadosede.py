import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0019_codigoqrentrega')]
    operations = [
        migrations.CreateModel(
            name='DelegadoSede',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('delegado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sedes_responsable', to='usuarios.perfildelegado')),
                ('sede', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='delegado_responsable', to='usuarios.sede')),
            ],
        ),
    ]
