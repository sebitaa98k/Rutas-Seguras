import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0018_usuario_admin_colegio_constraints')]
    operations = [
        migrations.CreateModel(
            name='CodigoQREntrega',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('expira_en', models.DateTimeField()),
                ('usado_en', models.DateTimeField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('estudiante', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='codigos_qr_entrega', to='usuarios.estudiante')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='codigos_qr_entrega', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-creado_en']},
        ),
    ]
