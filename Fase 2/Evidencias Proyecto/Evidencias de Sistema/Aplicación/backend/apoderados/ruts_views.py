from usuarios.papelera import desactivar_rut_habilitado
from usuarios.papelera_views import respuesta_desactivar
import re
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.models import FCMToken, PerfilApoderado, RutHabilitado
from usuarios.permissions import IsAdministrador, colegio_administrado
from usuarios.rut import formatear_rut, rut_valido
from usuarios.rut_unico import APODERADO, rut_ocupado
from usuarios.view_common import get_colegio_id_for_request
from usuarios.vinculos import colegios_del_apoderado, vincular_apoderado

LIMITE_POR_CARGA = 2000
LIMITE_LISTADO = 500


def _datos_entrada(entrada):
    perfil = entrada.apoderado
    usuario = perfil.usuario if perfil else None
    return {
        'id': entrada.id,
        'rut': entrada.rut,
        'colegio_id': entrada.colegio_id,
        'colegio_nombre': entrada.colegio.nombre,
        'estado': 'usado' if perfil else 'disponible',
        'cuenta': {
            'nombre': usuario.get_full_name() or usuario.email,
            'email': usuario.email,
            'telefono': perfil.telefono or '',
            'estudiantes': perfil.estudiantes.count(),
        } if usuario else None,
        'usado_en': entrada.usado_en,
        'creado_en': entrada.creado_en,
        'liberado_en': entrada.liberado_en,
        'cuenta_liberada': entrada.cuenta_liberada,
    }


def _entrada_del_colegio(request, entrada_id):
    entradas = RutHabilitado.objects.select_related('colegio', 'apoderado__usuario')
    colegio_id = get_colegio_id_for_request(request)
    if colegio_id:
        entradas = entradas.filter(colegio_id=colegio_id)
    return get_object_or_404(entradas, id=entrada_id)


class RutsHabilitadosView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        entradas = RutHabilitado.objects.filter(activo=True).select_related('colegio', 'apoderado__usuario')
        colegio_id = get_colegio_id_for_request(request)
        if colegio_id:
            entradas = entradas.filter(colegio_id=colegio_id)

        buscar = (request.query_params.get('buscar') or '').strip()
        if buscar:
            rut_buscado = re.sub(r'[\s.]', '', buscar).upper()
            entradas = entradas.filter(
                Q(rut__icontains=rut_buscado)
                | Q(apoderado__usuario__first_name__icontains=buscar)
                | Q(apoderado__usuario__last_name__icontains=buscar)
                | Q(apoderado__usuario__email__icontains=buscar)
            )
        if request.query_params.get('estado') == 'disponible':
            entradas = entradas.filter(apoderado__isnull=True)
        elif request.query_params.get('estado') == 'usado':
            entradas = entradas.filter(apoderado__isnull=False)

        return Response({
            'limite': LIMITE_LISTADO,
            'ruts': [_datos_entrada(item) for item in entradas[:LIMITE_LISTADO]],
        })

    def post(self, request):
        """Acepta uno o varios RUT separados por saltos de línea, comas, punto y coma o espacios."""
        colegio = colegio_administrado(request)
        valores = [valor for valor in re.split(r'[\s,;]+', str(request.data.get('ruts') or '')) if valor]
        if not valores:
            return Response({'message': 'Ingresa al menos un RUT.'}, status=400)
        if len(valores) > LIMITE_POR_CARGA:
            return Response({'message': f'Puedes cargar hasta {LIMITE_POR_CARGA} RUT a la vez.'}, status=400)

        formato_invalido, candidatos, en_otro_rol = [], [], []
        for valor in valores:
            rut = formatear_rut(valor)
            if not rut_valido(rut):
                formato_invalido.append(valor)
            elif rut_ocupado(rut, permitir={APODERADO}):
                # Ya es conductor, inspector o estudiante (en este u otro colegio): no puede ser apoderado.
                if rut not in en_otro_rol:
                    en_otro_rol.append(rut)
            elif rut not in candidatos:
                candidatos.append(rut)

        # Volver a cargar un RUT que estaba en la papelera lo reactiva.
        reactivados = list(
            RutHabilitado.objects.filter(colegio=colegio, rut__in=candidatos, activo=False).values_list('rut', flat=True)
        )
        RutHabilitado.objects.filter(colegio=colegio, rut__in=reactivados).update(activo=True, desactivado_en=None)
        existentes = set(
            RutHabilitado.objects.filter(colegio=colegio, rut__in=candidatos).values_list('rut', flat=True)
        ) - set(reactivados)
        nuevos = [rut for rut in candidatos if rut not in existentes and rut not in reactivados]
        RutHabilitado.objects.bulk_create(
            [RutHabilitado(colegio=colegio, rut=rut, creado_por=request.user) for rut in nuevos]
        )
        perfiles_por_rut = {
            perfil.rut: perfil
            for perfil in PerfilApoderado.objects.filter(rut__in=candidatos)
        }
        vinculados = 0
        for entrada in RutHabilitado.objects.filter(
            colegio=colegio, rut__in=candidatos, activo=True, apoderado__isnull=True,
        ):
            perfil = perfiles_por_rut.get(entrada.rut)
            # El apoderado ya tiene cuenta (en otro colegio): queda vinculado también a este y se le avisa.
            if perfil and vincular_apoderado(perfil, colegio, creado_por=request.user):
                vinculados += 1
        return Response({
            'message': f'RUT agregados: {len(nuevos) + len(reactivados)}.',
            'agregados': len(nuevos) + len(reactivados),
            'cuentas_vinculadas': vinculados,
            'repetidos': sorted(existentes),
            'formato_invalido': formato_invalido,
            'en_otro_rol': en_otro_rol,
        }, status=201)


class RutHabilitadoDetalleView(APIView):
    permission_classes = [IsAdministrador]

    def delete(self, request, entrada_id):
        return respuesta_desactivar(desactivar_rut_habilitado, _entrada_del_colegio(request, entrada_id))


class LiberarRutView(APIView):
    """Desactiva la cuenta que usó el RUT para que la persona correcta pueda registrarse."""

    permission_classes = [IsAdministrador]

    @transaction.atomic
    def post(self, request, entrada_id):
        entrada = _entrada_del_colegio(request, entrada_id)
        perfil = entrada.apoderado
        if perfil is None:
            return Response({'message': 'Este RUT ya está disponible.'}, status=409)

        if colegios_del_apoderado(perfil) - {entrada.colegio_id}:
            return Response({
                'message': (
                    'Esta cuenta también está en otro colegio, así que no se puede liberar desde aquí. '
                    'Si no es su apoderado, desactívalo desde Apoderados: solo se desvinculará de este colegio.'
                ),
            }, status=409)

        cantidad = perfil.estudiantes.count()
        if cantidad:
            return Response({
                'message': (
                    f'Esta cuenta tiene {cantidad} estudiante(s) asociado(s). '
                    'Reasígnalos o elimínalos antes de liberar el RUT.'
                ),
            }, status=409)

        usuario = perfil.usuario
        descripcion = f'{usuario.get_full_name()} ({usuario.email})'.strip()

        # El correo y el RUT son únicos: se liberan para poder registrarse de nuevo.
        correo_libre = f'liberado-{uuid4().hex}@cuenta-liberada.invalid'
        usuario.email = correo_libre
        usuario.username = correo_libre
        usuario.is_active = False
        usuario.save(update_fields=['email', 'username', 'is_active'])
        Token.objects.filter(user=usuario).delete()
        FCMToken.objects.filter(usuario=usuario).update(is_active=False)

        perfil.rut = None
        perfil.save(update_fields=['rut'])

        RutHabilitado.objects.filter(apoderado=perfil).exclude(id=entrada.id).update(
            apoderado=None, usado_en=None,
        )
        entrada.apoderado = None
        entrada.usado_en = None
        entrada.liberado_en = timezone.now()
        entrada.liberado_por = request.user
        entrada.cuenta_liberada = descripcion[:320]
        entrada.save(update_fields=['apoderado', 'usado_en', 'liberado_en', 'liberado_por', 'cuenta_liberada'])

        return Response({
            'message': 'RUT liberado. La cuenta quedó desactivada.',
            'rut': _datos_entrada(entrada),
        })
