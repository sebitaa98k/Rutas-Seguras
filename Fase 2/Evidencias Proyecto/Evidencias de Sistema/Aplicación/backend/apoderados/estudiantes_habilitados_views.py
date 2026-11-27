"""Estudiantes habilitados: el colegio autoriza el par (RUT del apoderado, RUT del estudiante).

Cuando el apoderado agrega a su hijo desde la app, el colegio sale de esta habilitación. Habilitar a un
estudiante también habilita el RUT de su apoderado en el colegio (y lo vincula si ya tiene cuenta).
"""
import re

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.models import Estudiante, EstudianteHabilitado, PerfilApoderado
from usuarios.papelera import desactivar_estudiante_habilitado
from usuarios.papelera_views import respuesta_desactivar
from usuarios.permissions import IsAdministrador, IsApoderado, colegio_administrado
from usuarios.rut import formatear_rut, rut_valido
from usuarios.rut_unico import APODERADO, ESTUDIANTE, rut_ocupado
from usuarios.view_common import get_colegio_id_for_request
from usuarios.vinculos import habilitar_rut_apoderado

LIMITE_POR_CARGA = 2000
LIMITE_LISTADO = 500
MENSAJE_NO_HABILITADO = (
    'Este estudiante no está habilitado para tu cuenta. Pide a su colegio que lo habilite con tu RUT.'
)


def _datos_entrada(entrada, perfiles_por_rut):
    estudiante = entrada.estudiante
    perfil = perfiles_por_rut.get(entrada.rut_apoderado)
    return {
        'id': entrada.id,
        'rut': entrada.rut,
        'rut_apoderado': entrada.rut_apoderado,
        'colegio_id': entrada.colegio_id,
        'colegio_nombre': entrada.colegio.nombre,
        'estado': 'usado' if estudiante else 'disponible',
        'estudiante': {
            'id': estudiante.id, 'nombre': f'{estudiante.nombre} {estudiante.apellido}'.strip(),
        } if estudiante else None,
        'apoderado': {
            'nombre': perfil.usuario.get_full_name() or perfil.usuario.email,
            'email': perfil.usuario.email,
        } if perfil else None,
        'creado_en': entrada.creado_en,
        'usado_en': entrada.usado_en,
    }


def _leer_pares(texto):
    """Una línea por estudiante: "RUT apoderado, RUT estudiante" (también con ; tabulación o espacio)."""
    pares, invalidos = [], []
    for linea in str(texto or '').splitlines():
        linea = linea.strip()
        if not linea:
            continue
        valores = [valor for valor in re.split(r'[\s,;]+', linea) if valor]
        if len(valores) != 2:
            invalidos.append(linea)
            continue
        rut_apoderado, rut_estudiante = (formatear_rut(valor) for valor in valores)
        if not (rut_valido(rut_apoderado) and rut_valido(rut_estudiante)) or rut_apoderado == rut_estudiante:
            invalidos.append(linea)
            continue
        pares.append((rut_apoderado, rut_estudiante))
    return pares, invalidos


class EstudiantesHabilitadosView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        entradas = EstudianteHabilitado.objects.filter(activo=True).select_related('colegio', 'estudiante')
        colegio_id = get_colegio_id_for_request(request)
        if colegio_id:
            entradas = entradas.filter(colegio_id=colegio_id)

        buscar = (request.query_params.get('buscar') or '').strip()
        if buscar:
            rut_buscado = re.sub(r'[\s.]', '', buscar).upper()
            entradas = entradas.filter(
                Q(rut__icontains=rut_buscado) | Q(rut_apoderado__icontains=rut_buscado)
                | Q(estudiante__nombre__icontains=buscar) | Q(estudiante__apellido__icontains=buscar)
            )
        if request.query_params.get('estado') == 'disponible':
            entradas = entradas.filter(estudiante__isnull=True)
        elif request.query_params.get('estado') == 'usado':
            entradas = entradas.filter(estudiante__isnull=False)

        entradas = list(entradas[:LIMITE_LISTADO])
        perfiles_por_rut = {
            perfil.rut: perfil
            for perfil in PerfilApoderado.objects.select_related('usuario').filter(
                rut__in={entrada.rut_apoderado for entrada in entradas},
            )
        }
        return Response({
            'limite': LIMITE_LISTADO,
            'estudiantes': [_datos_entrada(entrada, perfiles_por_rut) for entrada in entradas],
        })

    @transaction.atomic
    def post(self, request):
        # El administrador de plataforma debe elegir el colegio en el filtro de arriba.
        colegio = colegio_administrado(request)
        if not colegio.activo:
            return Response({'message': 'El colegio está desactivado.'}, status=400)
        pares, formato_invalido = _leer_pares(request.data.get('pares'))
        if not pares and not formato_invalido:
            return Response({'message': 'Ingresa al menos un par: RUT del apoderado y RUT del estudiante.'}, status=400)
        if len(pares) > LIMITE_POR_CARGA:
            return Response({'message': f'Puedes cargar hasta {LIMITE_POR_CARGA} estudiantes a la vez.'}, status=400)

        agregados, repetidos, en_otro_colegio, ya_registrados = [], [], [], []
        en_otro_rol = []
        cuentas_vinculadas = 0
        vistos = set()
        for rut_apoderado, rut_estudiante in pares:
            if rut_estudiante in vistos:
                repetidos.append(rut_estudiante)
                continue
            vistos.add(rut_estudiante)
            if Estudiante.todos.filter(rut=rut_estudiante).exists():
                # Ya inscrito: no necesita habilitación (y no puede inscribirse dos veces).
                ya_registrados.append(rut_estudiante)
                continue
            # Un RUT es una sola persona con un solo rol en todo el sistema (también entre colegios).
            if rut_ocupado(rut_estudiante, permitir={ESTUDIANTE}) or rut_ocupado(rut_apoderado, permitir={APODERADO}):
                en_otro_rol.append(rut_estudiante)
                continue
            actual = EstudianteHabilitado.objects.filter(rut=rut_estudiante, activo=True).first()
            if actual and actual.colegio_id != colegio.id:
                en_otro_colegio.append(rut_estudiante)
                continue
            if actual:
                if actual.rut_apoderado == rut_apoderado:
                    repetidos.append(rut_estudiante)
                    continue
                # Se corrige el apoderado de una habilitación aún sin usar.
                actual.rut_apoderado = rut_apoderado
                actual.save(update_fields=['rut_apoderado'])
            else:
                EstudianteHabilitado.objects.create(
                    colegio=colegio, rut=rut_estudiante, rut_apoderado=rut_apoderado, creado_por=request.user,
                )
            # El apoderado queda habilitado en el colegio junto con su hijo.
            _, vinculada = habilitar_rut_apoderado(colegio, rut_apoderado, creado_por=request.user)
            cuentas_vinculadas += int(vinculada)
            agregados.append(rut_estudiante)

        return Response({
            'message': f'Estudiantes habilitados: {len(agregados)}.',
            'agregados': len(agregados),
            'cuentas_vinculadas': cuentas_vinculadas,
            'repetidos': repetidos,
            'en_otro_colegio': en_otro_colegio,
            'ya_registrados': ya_registrados,
            'en_otro_rol': en_otro_rol,
            'formato_invalido': formato_invalido,
        }, status=201)


class EstudianteHabilitadoDetalleView(APIView):
    permission_classes = [IsAdministrador]

    def delete(self, request, entrada_id):
        entradas = EstudianteHabilitado.objects.filter(activo=True)
        colegio_id = get_colegio_id_for_request(request)
        if colegio_id:
            entradas = entradas.filter(colegio_id=colegio_id)
        return respuesta_desactivar(desactivar_estudiante_habilitado, get_object_or_404(entradas, id=entrada_id))


def habilitacion_para(perfil, rut_estudiante):
    """La habilitación con que el apoderado puede inscribir a ese estudiante, o None."""
    rut = formatear_rut(rut_estudiante or '')
    if not perfil.rut or not rut_valido(rut):
        return None
    return EstudianteHabilitado.objects.select_related('colegio').filter(
        rut=rut, rut_apoderado=perfil.rut, activo=True, estudiante__isnull=True, colegio__activo=True,
    ).first()


class ConsultarHabilitacionView(APIView):
    """App del apoderado: a qué colegio va el hijo que quiere agregar (lo decide el colegio, no el apoderado)."""

    permission_classes = [IsApoderado]

    def get(self, request):
        perfil = getattr(request.user, 'perfil_apoderado', None)
        entrada = habilitacion_para(perfil, request.query_params.get('rut')) if perfil else None
        if entrada is None:
            return Response({'message': MENSAJE_NO_HABILITADO, 'habilitado': False}, status=404)
        return Response({
            'habilitado': True,
            'rut': entrada.rut,
            'colegio_id': entrada.colegio_id,
            'colegio_nombre': entrada.colegio.nombre,
            'es_multisede': entrada.colegio.es_multisede,
        })
