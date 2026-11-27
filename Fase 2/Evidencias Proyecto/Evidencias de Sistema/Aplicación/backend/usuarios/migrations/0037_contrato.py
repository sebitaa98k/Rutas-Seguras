import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0036_registroentrega_colegio'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contrato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_contrato', models.CharField(max_length=50, unique=True)),
                ('fecha_firma', models.DateField()),
                ('estado', models.CharField(choices=[('vigente', 'Vigente'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], default='vigente', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('apoderado', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contratos', to='usuarios.perfilapoderado')),
                ('colegio', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contratos', to='usuarios.colegio')),
                ('estudiantes', models.ManyToManyField(related_name='contratos', to='usuarios.estudiante')),
            ],
            options={
                'ordering': ['-fecha_firma', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='contrato',
            constraint=models.UniqueConstraint(condition=models.Q(('estado', 'vigente')), fields=('apoderado', 'colegio'), name='contrato_vigente_unico_apoderado_colegio'),
        ),
    ]
