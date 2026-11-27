import re
from collections import Counter

from django.db import migrations
from django.utils import timezone

_FORMATO_RUT = re.compile(r'^\d{7,8}-[\dK]$')


def _formatear(valor):
    limpio = re.sub(r'[\s.\-]', '', valor or '').upper()
    return f'{limpio[:-1]}-{limpio[-1]}' if len(limpio) >= 2 else limpio


def vincular_apoderados_actuales(apps, schema_editor):
    """Deja los RUT como 12345678-9, asocia cada apoderado a su colegio y marca su RUT como usado."""
    PerfilApoderado = apps.get_model('usuarios', 'PerfilApoderado')
    RutHabilitado = apps.get_model('usuarios', 'RutHabilitado')
    ahora = timezone.now()

    for perfil in PerfilApoderado.objects.select_related('usuario').order_by('id'):
        cambios = []

        rut = _formatear(perfil.rut)
        if perfil.rut and rut != perfil.rut and _FORMATO_RUT.match(rut):
            if not PerfilApoderado.objects.filter(rut=rut).exclude(pk=perfil.pk).exists():
                perfil.rut = rut
                cambios.append('rut')

        conteo_colegios = Counter(
            colegio_id
            for colegio_id in perfil.estudiantes.values_list('colegio_id', flat=True)
            if colegio_id
        )
        if not perfil.colegio_id and conteo_colegios:
            perfil.colegio_id = conteo_colegios.most_common(1)[0][0]
            cambios.append('colegio')
        if cambios:
            perfil.save(update_fields=cambios)

        usuario = perfil.usuario
        if perfil.colegio_id and not usuario.colegio_id:
            usuario.colegio_id = perfil.colegio_id
            usuario.save(update_fields=['colegio'])

        if perfil.rut:
            for colegio_id in {perfil.colegio_id, *conteo_colegios} - {None}:
                RutHabilitado.objects.get_or_create(
                    colegio_id=colegio_id,
                    rut=perfil.rut,
                    defaults={'apoderado': perfil, 'usado_en': ahora},
                )


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0046_ruts_habilitados_y_terminos'),
    ]

    operations = [
        migrations.RunPython(vincular_apoderados_actuales, migrations.RunPython.noop),
    ]
