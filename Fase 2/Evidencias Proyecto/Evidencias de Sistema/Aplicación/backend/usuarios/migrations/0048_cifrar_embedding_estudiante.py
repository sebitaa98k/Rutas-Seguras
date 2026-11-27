from django.db import migrations, models

import usuarios.campos


def cifrar_existentes(apps, schema_editor):
    Estudiante = apps.get_model('usuarios', 'Estudiante')
    for estudiante in Estudiante.objects.filter(embedding_facial__isnull=False):
        estudiante.embedding_facial_cifrado = estudiante.embedding_facial
        estudiante.save(update_fields=['embedding_facial_cifrado'])


def descifrar_existentes(apps, schema_editor):
    Estudiante = apps.get_model('usuarios', 'Estudiante')
    for estudiante in Estudiante.objects.filter(embedding_facial_cifrado__isnull=False):
        estudiante.embedding_facial = estudiante.embedding_facial_cifrado
        estudiante.save(update_fields=['embedding_facial'])


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0047_apoderados_actuales_rut_habilitado'),
    ]

    operations = [
        migrations.RemoveField(model_name='perfilapoderado', name='embedding_facial'),
        migrations.RemoveField(model_name='perfilapoderado', name='embedding_facial_version'),
        migrations.RemoveField(model_name='perfildelegado', name='embedding_facial'),
        migrations.RemoveField(model_name='perfildelegado', name='embedding_facial_version'),
        migrations.AddField(
            model_name='estudiante',
            name='embedding_facial_cifrado',
            field=usuarios.campos.EmbeddingCifradoField(
                blank=True, null=True, help_text='Vector facial SFace (128 floats), cifrado en la base de datos',
            ),
        ),
        migrations.RunPython(cifrar_existentes, descifrar_existentes),
        migrations.RemoveField(model_name='estudiante', name='embedding_facial'),
        migrations.RenameField(
            model_name='estudiante', old_name='embedding_facial_cifrado', new_name='embedding_facial',
        ),
    ]
