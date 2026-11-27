"""Identificación de estudiantes por reconocimiento facial durante la ruta."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notificaciones.serializers import NotificacionSerializer

from usuarios.asignaciones import estudiantes_del_conductor
from usuarios.models import Ruta

from .abordaje import (
    registrar_abordaje,
    registrar_entrega,
    ruta_en_curso_del_estudiante,
    ruta_iniciada_del_estudiante,
)
from .comun import obtener_conductor_autenticado


class RutaEscaneoFacialView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        imagen_raw = request.data.get('imagen') or request.data.get('imagen_base64')
        modo = request.data.get('modo', 'abordar')
        confirmar = request.data.get('confirmar', False)

        if not imagen_raw:
            return Response({'message': 'Se requiere una imagen para procesar el escaneo facial.'}, status=status.HTTP_400_BAD_REQUEST)

        conductor_perfil = obtener_conductor_autenticado(request)

        if not conductor_perfil:
            return Response({'message': 'Acceso denegado. No se encontró perfil de conductor asociado.'}, status=status.HTTP_403_FORBIDDEN)

        from usuarios.face_recognition_service import procesar_identificacion_facial
        resultado = procesar_identificacion_facial(conductor_perfil, imagen_raw, modo=modo)

        if not resultado['coincidencia']:
            return Response(resultado, status=status.HTTP_200_OK)

        ruta_seleccionada = None
        estudiante_solicitado = request.data.get('estudiante_id')
        ruta_solicitada = request.data.get('ruta_id')
        if modo == 'abordar' and (estudiante_solicitado or ruta_solicitada):
            try:
                estudiante_solicitado = int(estudiante_solicitado)
                ruta_solicitada = int(ruta_solicitada)
            except (TypeError, ValueError):
                return Response({'message': 'La seleccion de ruta y estudiante no es valida.'}, status=400)
            ruta_seleccionada = Ruta.objects.filter(
                pk=ruta_solicitada,
                conductor_perfil=conductor_perfil,
                sentido='desde_colegio',
                estado__in=('activa', 'en_ruta'),
                estudiantes__id=estudiante_solicitado,
            ).first()
            if not ruta_seleccionada:
                return Response({'message': 'El estudiante no pertenece a la ruta seleccionada.'}, status=403)
            if resultado.get('estudiante_id') != estudiante_solicitado:
                resultado.update({
                    'coincidencia': False,
                    'evento_registrado': False,
                    'requiere_verificacion_alternativa': True,
                    'mensaje': 'El rostro no corresponde al estudiante seleccionado.',
                })
                return Response(resultado, status=status.HTTP_200_OK)

        if modo == 'entregar' and estudiante_solicitado:
            try:
                estudiante_solicitado = int(estudiante_solicitado)
            except (TypeError, ValueError):
                return Response({'message': 'La seleccion de estudiante no es valida.'}, status=400)
            if resultado.get('estudiante_id') != estudiante_solicitado:
                resultado.update({
                    'coincidencia': False,
                    'evento_registrado': False,
                    'requiere_verificacion_alternativa': True,
                    'mensaje': 'El rostro no corresponde al estudiante seleccionado.',
                })
                return Response(resultado, status=status.HTTP_200_OK)

        if confirmar:
            estudiante_id = resultado.get('estudiante_id')
            estudiante = estudiantes_del_conductor(conductor_perfil).filter(id=estudiante_id).first()

            if estudiante:
                notificacion = None
                if modo == 'abordar':
                    ruta = ruta_seleccionada or ruta_en_curso_del_estudiante(conductor_perfil, estudiante)
                    if not ruta:
                        return Response({'message': 'El estudiante no pertenece a una ruta activa.'}, status=400)
                    try:
                        abordaje = registrar_abordaje(ruta, estudiante, metodo='facial')
                    except ValueError as exc:
                        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
                    notificacion = abordaje.pop('notificacion', None)
                    resultado['abordaje'] = abordaje
                else:
                    ruta = ruta_iniciada_del_estudiante(conductor_perfil, estudiante)
                    if not ruta:
                        return Response(
                            {'message': 'El estudiante no pertenece a la ruta activa del conductor.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if ruta.sentido != 'desde_colegio':
                        return Response(
                            {'message': 'En la ida, la recepción se registra con el QR del inspector del colegio.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    try:
                        entrega = registrar_entrega(ruta, estudiante, None, 'facial')
                        notificacion = entrega.pop('notificacion', None)
                        resultado['entrega'] = entrega
                    except ValueError as exc:
                        return Response(
                            {'message': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                resultado['evento_registrado'] = True
                resultado['notificacion'] = NotificacionSerializer(notificacion).data if notificacion else None

        return Response(resultado, status=status.HTTP_200_OK)
