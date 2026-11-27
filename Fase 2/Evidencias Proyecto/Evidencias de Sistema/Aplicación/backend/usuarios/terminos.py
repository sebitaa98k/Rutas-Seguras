"""Términos y condiciones: versión vigente y constancia de aceptación del apoderado."""
import hashlib
from pathlib import Path

from django.db import transaction

# Para publicar otra versión: agregar su archivo en terminos_textos y cambiar este valor.
VERSION_VIGENTE = '1.2'
TITULO = 'Términos y condiciones de uso'
_CARPETA_TEXTOS = Path(__file__).resolve().parent / 'terminos_textos'


def texto_terminos(version=VERSION_VIGENTE):
    return (_CARPETA_TEXTOS / f'v{version}.md').read_text(encoding='utf-8')


def huella_texto(texto):
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def debe_aceptar_terminos(usuario):
    return (
        usuario.rol == 'apoderado'
        and not usuario.is_superuser
        and not usuario.is_staff
        and usuario.terminos_version_aceptada != VERSION_VIGENTE
    )


def biometria_autorizada(estudiante):
    """Su apoderado autorizó usar el rostro de ESTE hijo (consentimiento por hijo, términos 1.2)."""
    return bool(estudiante.autoriza_biometria)


def eliminar_biometria(estudiantes):
    """Borra la foto (también del disco) y el vector facial. El estudiante queda en modo QR."""
    borrados = 0
    for estudiante in estudiantes:
        if not estudiante.foto and estudiante.embedding_facial is None:
            continue
        foto = estudiante.foto.name if estudiante.foto else None
        storage = estudiante.foto.storage
        estudiante.foto = None
        estudiante.embedding_facial = None
        estudiante.embedding_facial_version = None
        estudiante.save(update_fields=['foto', 'embedding_facial', 'embedding_facial_version', 'updated_at'])
        if foto:
            # Después de guardar: si fallara el guardado, la foto sigue en su lugar.
            transaction.on_commit(lambda nombre=foto, almacen=storage: almacen.delete(nombre))
        borrados += 1
    return borrados


def _datos_conexion(request):
    meta = request.META if request is not None else {}
    return {
        'ip': meta.get('REMOTE_ADDR') or None,
        'dispositivo': (meta.get('HTTP_USER_AGENT') or '')[:255],
    }


@transaction.atomic
def cambiar_biometria_estudiante(estudiante, autoriza, origen, request=None):
    """Otorga o revoca el consentimiento biométrico de UN hijo y deja la constancia inmutable.

    Al revocar se borran al tiro la foto y el vector de ese hijo (supresión, art. 7), que pasa a QR.
    Devuelve True si se borraron datos faciales. Si el estado no cambia, no hace nada.
    """
    from django.utils import timezone

    from .models import ConsentimientoBiometrico

    if bool(estudiante.autoriza_biometria) == bool(autoriza):
        return False
    borrados = False
    if not autoriza:
        borrados = bool(eliminar_biometria([estudiante]))
    estudiante.autoriza_biometria = bool(autoriza)
    estudiante.autoriza_biometria_en = timezone.now()
    estudiante.save(update_fields=['autoriza_biometria', 'autoriza_biometria_en', 'updated_at'])

    perfil = estudiante.apoderado
    usuario = perfil.usuario if perfil else None
    colegio = estudiante.colegio
    ConsentimientoBiometrico.objects.create(
        apoderado=usuario,
        estudiante=estudiante,
        colegio=colegio,
        apoderado_nombre=usuario.get_full_name() if usuario else '',
        apoderado_rut=(perfil.rut or '') if perfil else '',
        apoderado_email=usuario.email if usuario else '',
        estudiante_nombre=f'{estudiante.nombre} {estudiante.apellido}'.strip(),
        estudiante_rut=estudiante.rut or '',
        colegio_nombre=colegio.nombre if colegio else '',
        evento='otorgado' if autoriza else 'revocado',
        origen=origen,
        version_terminos=VERSION_VIGENTE,
        datos_eliminados=borrados,
        **_datos_conexion(request),
    )
    return borrados


@transaction.atomic
def registrar_aceptacion(usuario, origen, request):
    """Guarda la constancia de los términos y deja de exigirlos a esta cuenta.

    Desde la versión 1.2 los términos no incluyen la biometría: se autoriza por cada hijo
    (cambiar_biometria_estudiante).
    """
    from .models import AceptacionTerminos

    perfil = getattr(usuario, 'perfil_apoderado', None)
    colegio = usuario.colegio or (perfil.colegio if perfil else None)
    aceptacion, _ = AceptacionTerminos.objects.get_or_create(
        usuario=usuario,
        version=VERSION_VIGENTE,
        defaults={
            'colegio': colegio,
            'colegio_nombre': colegio.nombre if colegio else '',
            'rut': (perfil.rut or '') if perfil else '',
            'nombre': usuario.get_full_name(),
            'email': usuario.email,
            'huella_texto': huella_texto(texto_terminos()),
            'origen': origen,
            **_datos_conexion(request),
        },
    )
    usuario.terminos_version_aceptada = VERSION_VIGENTE
    usuario.save(update_fields=['terminos_version_aceptada'])
    return aceptacion
