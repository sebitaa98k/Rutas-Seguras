"""Consentimiento biométrico por hijo (Ley 21.719, términos 1.2).

1. Cada estudiante tiene su propio consentimiento (`autoriza_biometria`), que parte apagado.
2. Nace la tabla inmutable ConsentimientoBiometrico.
3. Todos los estudiantes pasan a QR: se borran sus fotos y vectores faciales, porque la autorización
   general anterior (del apoderado para todos sus hijos) ya no vale. Su apoderado debe autorizar
   a cada hijo de nuevo. Por cada hijo cuyo apoderado tenía la autorización general queda una
   constancia "revocado" de origen "migracion".
4. Se quita la autorización general del usuario. El historial antiguo (CambioBiometria) se conserva.
"""

import django.db.models.deletion
import usuarios.campos
from django.conf import settings
from django.db import migrations, models


def pasar_todos_a_qr(apps, schema_editor):
    Estudiante = apps.get_model('usuarios', 'Estudiante')
    Consentimiento = apps.get_model('usuarios', 'ConsentimientoBiometrico')
    estudiantes = Estudiante.objects.select_related('apoderado__usuario', 'colegio').all()
    for estudiante in estudiantes.iterator():
        tenia_datos = bool(estudiante.foto) or estudiante.embedding_facial is not None
        perfil = estudiante.apoderado
        usuario = perfil.usuario if perfil else None
        autorizaba = bool(usuario and usuario.autoriza_biometria)
        if tenia_datos:
            foto = estudiante.foto.name if estudiante.foto else None
            storage = estudiante.foto.storage if estudiante.foto else None
            Estudiante.objects.filter(pk=estudiante.pk).update(
                foto=None, embedding_facial=None, embedding_facial_version=None,
            )
            if foto and storage is not None:
                try:
                    storage.delete(foto)
                except Exception:  # noqa: BLE001 - si el archivo ya no estaba, igual se sigue
                    pass
        if autorizaba:
            Consentimiento.objects.create(
                apoderado=usuario,
                estudiante=estudiante,
                colegio=estudiante.colegio,
                apoderado_nombre=f'{usuario.first_name} {usuario.last_name}'.strip(),
                apoderado_rut=perfil.rut or '',
                apoderado_email=usuario.email,
                estudiante_nombre=f'{estudiante.nombre} {estudiante.apellido}'.strip(),
                estudiante_rut=estudiante.rut or '',
                colegio_nombre=estudiante.colegio.nombre if estudiante.colegio_id else '',
                evento='revocado',
                origen='migracion',
                version_terminos='1.2',
                datos_eliminados=tenia_datos,
                dispositivo='Migración a consentimiento por hijo',
            )


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0060_eliminar_contratos'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='autoriza_biometria',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='autoriza_biometria_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ConsentimientoBiometrico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('apoderado_nombre', models.CharField(blank=True, default='', max_length=300)),
                ('apoderado_rut', usuarios.campos.RutField(blank=True, default='', max_length=12)),
                ('apoderado_email', models.EmailField(blank=True, default='', max_length=254)),
                ('estudiante_nombre', models.CharField(blank=True, default='', max_length=300)),
                ('estudiante_rut', usuarios.campos.RutField(blank=True, default='', max_length=12)),
                ('colegio_nombre', models.CharField(blank=True, default='', max_length=200)),
                ('evento', models.CharField(choices=[('otorgado', 'Otorgado'), ('revocado', 'Revocado')], max_length=10)),
                ('origen', models.CharField(choices=[('agregar_hijo', 'Al inscribir al hijo'), ('detalle_hijo', 'Desde el detalle del hijo'), ('desactivacion', 'Al desactivar al estudiante'), ('migracion', 'Cambio a consentimiento por hijo (términos 1.2)')], max_length=20)),
                ('version_terminos', models.CharField(blank=True, default='', max_length=20)),
                ('datos_eliminados', models.BooleanField(default=False)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('dispositivo', models.CharField(blank=True, default='', max_length=255)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('apoderado', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consentimientos_biometricos', to=settings.AUTH_USER_MODEL)),
                ('colegio', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consentimientos_biometricos', to='usuarios.colegio')),
                ('estudiante', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consentimientos_biometricos', to='usuarios.estudiante')),
            ],
            options={
                'ordering': ['-creado_en', '-id'],
            },
        ),
        migrations.RunPython(pasar_todos_a_qr, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='usuario',
            name='autoriza_biometria',
        ),
        migrations.RemoveField(
            model_name='usuario',
            name='autoriza_biometria_en',
        ),
    ]
