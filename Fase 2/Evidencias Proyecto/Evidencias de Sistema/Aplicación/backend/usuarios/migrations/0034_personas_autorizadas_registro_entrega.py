from django.db import migrations, models
import django.db.models.deletion


def migrar_autorizados_legacy(apps, schema_editor):
    Estudiante = apps.get_model('usuarios', 'Estudiante')
    PerfilDelegado = apps.get_model('usuarios', 'PerfilDelegado')
    PersonaAutorizada = apps.get_model('usuarios', 'PersonaAutorizada')

    def normalizar(rut):
        return (rut or '').replace('.', '').replace('-', '').upper().strip()

    perfiles = {normalizar(p.rut): p for p in PerfilDelegado.objects.exclude(rut__isnull=True)}
    for estudiante in Estudiante.objects.exclude(rut_persona_autorizada__isnull=True).exclude(rut_persona_autorizada=''):
        if not estudiante.colegio_id:
            continue
        rut = estudiante.rut_persona_autorizada.strip()
        PersonaAutorizada.objects.get_or_create(
            estudiante_id=estudiante.id,
            rut=rut,
            defaults={
                'apoderado_id': estudiante.apoderado_id,
                'colegio_id': estudiante.colegio_id,
                'perfil_delegado_id': getattr(perfiles.get(normalizar(rut)), 'id', None),
                'nombre': estudiante.persona_autorizada or 'Persona autorizada',
                'activa': True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0033_emergencia_contexto_operacional')]

    operations = [
        migrations.CreateModel(
            name='PersonaAutorizada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200)), ('rut', models.CharField(max_length=12)),
                ('telefono', models.CharField(blank=True, default='', max_length=20)),
                ('activa', models.BooleanField(default=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('apoderado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personas_autorizadas', to='usuarios.perfilapoderado')),
                ('colegio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personas_autorizadas', to='usuarios.colegio')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personas_autorizadas', to='usuarios.estudiante')),
                ('perfil_delegado', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='autorizaciones_estudiantes', to='usuarios.perfildelegado')),
            ],
        ),
        migrations.AddConstraint(model_name='personaautorizada', constraint=models.UniqueConstraint(fields=('estudiante', 'rut'), name='autorizado_unico_por_estudiante')),
        migrations.CreateModel(
            name='RegistroEntrega',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_receptor', models.CharField(choices=[('apoderado', 'Apoderado titular'), ('persona_autorizada', 'Persona autorizada'), ('delegado_institucional', 'Delegado institucional')], max_length=30)),
                ('receptor_nombre', models.CharField(max_length=200)), ('receptor_rut', models.CharField(blank=True, default='', max_length=12)),
                ('metodo_validacion', models.CharField(choices=[('facial', 'Reconocimiento facial'), ('qr', 'Código QR')], max_length=20)),
                ('destino', models.CharField(max_length=255)), ('entregado_en', models.DateTimeField(auto_now_add=True)),
                ('conductor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='registros_entrega', to='usuarios.perfilconductor')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='registros_entrega', to='usuarios.estudiante')),
                ('persona_autorizada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros_entrega', to='usuarios.personaautorizada')),
                ('perfil_delegado', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros_entrega', to='usuarios.perfildelegado')),
                ('ruta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='registros_entrega', to='usuarios.ruta')),
            ],
            options={'ordering': ['-entregado_en']},
        ),
        migrations.AddConstraint(model_name='registroentrega', constraint=models.UniqueConstraint(fields=('ruta', 'estudiante'), name='entrega_unica_por_ruta_estudiante')),
        migrations.RunPython(migrar_autorizados_legacy, migrations.RunPython.noop),
    ]
