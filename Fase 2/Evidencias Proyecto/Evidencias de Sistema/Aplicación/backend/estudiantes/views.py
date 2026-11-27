from usuarios.rut import MENSAJE_RUT_INVALIDO, formatear_rut, rut_valido
from apoderados.estudiantes_habilitados_views import MENSAJE_NO_HABILITADO, habilitacion_para
from usuarios.vinculos import vincular_apoderado
from usuarios.papelera import desactivar_estudiante
from usuarios.papelera_views import respuesta_desactivar
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from usuarios.models import Estudiante, PerfilDelegado, Usuario
from usuarios.permissions import IsAdministrador
from estudiantes.serializers import EstudianteSerializer, EstudianteUpdateSerializer
from usuarios.view_common import get_colegio_id_for_request
from usuarios.autorizaciones import normalizar_rut, notificar_actualizacion_autorizados, ruts_inspectores
from usuarios.models import PersonaAutorizada
from usuarios.terminos import biometria_autorizada, cambiar_biometria_estudiante
from usuarios.almacenamiento import FotoIlegibleError
from usuarios.inasistencias import (
    InasistenciaError,
    cancelar_inasistencia,
    estado_asistencia,
    interpretar_fecha,
    interpretar_tramos,
    marcar_inasistencia,
)

MENSAJE_BIOMETRIA_SIN_ACEPTAR = (
    'El apoderado no autorizó el reconocimiento facial de este estudiante: sube y baja con código QR '
    'o con el inspector. Se puede registrar su rostro cuando el apoderado lo autorice desde el detalle '
    'del hijo en la app.'
)


def _es_verdadero(valor):
    """Los formularios multipart mandan los booleanos como texto."""
    if isinstance(valor, bool):
        return valor
    return str(valor or '').strip().lower() in ('true', '1', 'si', 'sí', 'on')


def _respuesta_biometria_sin_aceptar():
    return Response({'message': MENSAJE_BIOMETRIA_SIN_ACEPTAR}, status=status.HTTP_409_CONFLICT)


CAMPOS_BLOQUEADOS_EN_RECORRIDO = ('sede', 'colegio')


def _id_enviado(valor):
    """El formulario puede mandar el id como número, texto o vacío."""
    if valor in (None, ''):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return valor


def ruta_en_curso_bloquea_cambio(estudiante, data):
    """Devuelve la ruta en curso si el cambio pedido mueve al estudiante de sede o colegio."""
    cambia = any(
        campo in data and _id_enviado(data.get(campo)) != getattr(estudiante, f'{campo}_id')
        for campo in CAMPOS_BLOQUEADOS_EN_RECORRIDO
    )
    if not cambia:
        return None
    return estudiante.rutas.filter(estado='en_ruta').first()


class EstudianteSinAsignarListView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        colegio_id = get_colegio_id_for_request(request)
        estudiantes = Estudiante.objects.filter(conductor__isnull=True)
        if colegio_id:
            estudiantes = estudiantes.filter(colegio_id=colegio_id)
        serializer = EstudianteSerializer(estudiantes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def datos_persona_autorizada(persona):
    return {
        'id': persona.id, 'nombre': persona.nombre, 'rut': persona.rut,
        'telefono': persona.telefono, 'activa': persona.activa,
        'tiene_cuenta': bool(persona.perfil_delegado_id),
    }


class PersonasAutorizadasEstudianteView(APIView):
    permission_classes = [IsAuthenticated]

    def estudiante_del_apoderado(self, request, estudiante_id):
        if not hasattr(request.user, 'perfil_apoderado'):
            return None
        estudiantes = Estudiante.objects.filter(
            pk=estudiante_id, apoderado=request.user.perfil_apoderado,
        )
        return estudiantes.first()

    def get(self, request, estudiante_id):
        estudiante = self.estudiante_del_apoderado(request, estudiante_id)
        if not estudiante:
            raise Http404
        return Response([datos_persona_autorizada(p) for p in estudiante.personas_autorizadas.filter(activa=True)])

    def post(self, request, estudiante_id):
        estudiante = self.estudiante_del_apoderado(request, estudiante_id)
        if not estudiante:
            raise Http404
        nombre = (request.data.get('nombre') or '').strip()
        rut = (request.data.get('rut') or '').strip()
        if not nombre or not rut:
            return Response({'message': 'Nombre y RUT son obligatorios.'}, status=400)
        if not rut_valido(formatear_rut(rut)):
            return Response({'message': MENSAJE_RUT_INVALIDO}, status=400)
        rut = formatear_rut(rut)
        anterior = next((p for p in estudiante.personas_autorizadas.all()
                         if normalizar_rut(p.rut) == normalizar_rut(rut)), None)
        if anterior and anterior.activa:
            return Response({'message': 'La persona ya está autorizada para este estudiante.'}, status=400)
        if normalizar_rut(rut) in ruts_inspectores():
            return Response({'message': 'Ese RUT es de un inspector del colegio: no se registra como persona autorizada.'}, status=400)
        perfil = next((p for p in PerfilDelegado.objects.filter(tipo_delegado='autorizado')
                       if normalizar_rut(p.rut) == normalizar_rut(rut)), None)
        telefono = (request.data.get('telefono') or '').strip()
        if anterior:
            # Se había quitado antes: se reactiva con los datos nuevos.
            anterior.activa, anterior.nombre, anterior.telefono, anterior.perfil_delegado = True, nombre, telefono, perfil
            anterior.save(update_fields=['activa', 'nombre', 'telefono', 'perfil_delegado', 'updated_at'])
            persona = anterior
        else:
            persona = PersonaAutorizada.objects.create(
                estudiante=estudiante, apoderado=estudiante.apoderado, colegio=estudiante.colegio,
                perfil_delegado=perfil, nombre=nombre, rut=rut, telefono=telefono,
            )
        notificar_actualizacion_autorizados(estudiante)
        return Response(datos_persona_autorizada(persona), status=201)


class PersonaAutorizadaEstudianteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, estudiante_id, persona_id):
        persona = self._obtener(request, estudiante_id, persona_id)
        if not persona:
            raise Http404
        if 'nombre' in request.data:
            persona.nombre = (request.data.get('nombre') or '').strip()
        if 'telefono' in request.data:
            persona.telefono = (request.data.get('telefono') or '').strip()
        if not persona.nombre:
            return Response({'message': 'El nombre es obligatorio.'}, status=400)
        persona.save(update_fields=['nombre', 'telefono', 'updated_at'])
        notificar_actualizacion_autorizados(persona.estudiante)
        return Response(datos_persona_autorizada(persona))

    def _obtener(self, request, estudiante_id, persona_id):
        if not hasattr(request.user, 'perfil_apoderado'):
            return None
        personas = PersonaAutorizada.objects.select_related('estudiante').filter(
            pk=persona_id, estudiante_id=estudiante_id,
            apoderado=request.user.perfil_apoderado,
        )
        return personas.first()

    def delete(self, request, estudiante_id, persona_id):
        persona = self._obtener(request, estudiante_id, persona_id)
        if not persona:
            raise Http404
        estudiante = persona.estudiante
        # No se borra: queda inactiva y, si se vuelve a agregar, se reactiva.
        persona.activa = False
        persona.save(update_fields=['activa', 'updated_at'])
        notificar_actualizacion_autorizados(estudiante)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EstudianteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.rol in ['admin_plataforma', 'admin_colegio'] or request.user.is_superuser or request.user.is_staff:
            colegio_id = get_colegio_id_for_request(request)
            estudiantes = Estudiante.objects.all()
            if colegio_id:
                estudiantes = estudiantes.filter(colegio_id=colegio_id)
            estudiantes = estudiantes.order_by('-id')
        elif hasattr(request.user, 'perfil_apoderado'):
            estudiantes = Estudiante.objects.filter(apoderado=request.user.perfil_apoderado).order_by('-id')
        else: 
            return Response({'message': 'No tiene permisos para consultar estudiantes.'}, status=status.HTTP_403_FORBIDDEN)

        from usuarios.dashboard_alerts import anotar_estado_alertas_estudiantes
        estudiantes = anotar_estado_alertas_estudiantes(estudiantes)
        serializer = EstudianteSerializer(estudiantes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.rol in ['admin_plataforma', 'admin_colegio'] or request.user.is_superuser or request.user.is_staff:
            target_colegio_id = get_colegio_id_for_request(request) or request.data.get('colegio_id')
            data = request.data.copy()
            if target_colegio_id:
                data['colegio'] = target_colegio_id
            if not data.get('colegio'):
                return Response({
                    'message': 'Error al registrar el estudiante.',
                    'errors': {'colegio': ['Debe seleccionar el colegio del estudiante.']}
                }, status=status.HTTP_400_BAD_REQUEST)
            if not data.get('apoderado'):
                return Response({
                    'message': 'Error al registrar el estudiante.',
                    'errors': {'apoderado': ['Debe seleccionar un apoderado responsable.']}
                }, status=status.HTTP_400_BAD_REQUEST)
            # El colegio no puede dar el consentimiento biométrico: lo da el apoderado por cada hijo
            # desde la app. Un estudiante nuevo creado en la web parte en QR y sin foto.
            if data.get('foto'):
                return _respuesta_biometria_sin_aceptar()
            serializer = EstudianteSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Estudiante registrado exitosamente.',
                    'estudiante': serializer.data
                }, status=status.HTTP_201_CREATED)
            return Response({
                'message': 'Error al registrar el estudiante.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        if not hasattr(request.user, 'perfil_apoderado'):
            return Response({
                'message': 'El usuario autenticado no tiene un perfil de apoderado asignado.'
            }, status=status.HTTP_403_FORBIDDEN)

        # El colegio no lo elige el apoderado: sale del estudiante que su colegio habilitó con el RUT
        # del apoderado. Así un apoderado con hijos en dos colegios no inscribe a uno en el equivocado.
        perfil_apoderado = request.user.perfil_apoderado
        habilitacion = habilitacion_para(perfil_apoderado, request.data.get('rut'))
        if habilitacion is None:
            return Response({
                'message': MENSAJE_NO_HABILITADO,
                'errors': {'rut': [MENSAJE_NO_HABILITADO]},
            }, status=status.HTTP_403_FORBIDDEN)
        colegio_solicitado = habilitacion.colegio_id
        data = request.data.copy()
        data['colegio'] = colegio_solicitado

        selected_sede = data.get('sede') or data.get('sede_id')
        if selected_sede:
            data['sede'] = selected_sede

        # Consentimiento biométrico de ESTE hijo (interruptor al inscribirlo). Sin él, se inscribe
        # sin foto y sube y baja con QR o con el inspector. Si llegara una foto, no se guarda.
        autoriza_biometria = _es_verdadero(request.data.get('autoriza_biometria'))
        if not autoriza_biometria:
            data.pop('foto', None)
            serializer = EstudianteSerializer(data=data)
            if not serializer.is_valid():
                return Response({
                    'message': 'Error al registrar el estudiante.',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                estudiante = serializer.save(apoderado=perfil_apoderado)
                habilitacion.estudiante = estudiante
                habilitacion.usado_en = timezone.now()
                habilitacion.save(update_fields=['estudiante', 'usado_en'])
                vincular_apoderado(perfil_apoderado, habilitacion.colegio, notificar=False)
            return Response({
                'message': 'Estudiante registrado. Subirá y bajará con código QR o con el inspector.',
                'estudiante': serializer.data,
                'tiene_biometria': False,
            }, status=status.HTTP_201_CREATED)

        foto_rostro = request.FILES.get('foto')
        if not foto_rostro:
            return Response({
                'message': 'Antes de registrar al estudiante, toma una foto de su rostro.',
                'errors': {'foto': ['La captura facial es obligatoria para registrar al estudiante.']},
                'requiere_captura_facial': True,
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = EstudianteSerializer(data=data)
        if serializer.is_valid():
            foto_bytes = foto_rostro.read()
            foto_rostro.seek(0)
            from usuarios.biometric_config import BIOMETRIC_PIPELINE_VERSION
            from usuarios.face_recognition_service import FaceRecognitionEngine
            exito, resultado = FaceRecognitionEngine().procesar_foto_estudiante(foto_bytes)
            if not exito:
                return Response({
                    'message': resultado,
                    'errors': {'foto': [resultado]},
                    'requiere_captura_facial': True,
                }, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                estudiante = serializer.save(
                    apoderado=request.user.perfil_apoderado,
                    embedding_facial=resultado,
                    embedding_facial_version=BIOMETRIC_PIPELINE_VERSION,
                )
                # Constancia inmutable del consentimiento de este hijo.
                cambiar_biometria_estudiante(estudiante, True, origen='agregar_hijo', request=request)
                habilitacion.estudiante = estudiante
                habilitacion.usado_en = timezone.now()
                habilitacion.save(update_fields=['estudiante', 'usado_en'])
                # El apoderado queda vinculado al colegio de su hijo.
                vincular_apoderado(perfil_apoderado, habilitacion.colegio, notificar=False)
            return Response({
                'message': 'Estudiante registrado exitosamente.',
                'estudiante': serializer.data,
                'tiene_biometria': True,
            }, status=status.HTTP_201_CREATED)
        return Response({
            'message': 'Error al registrar el estudiante.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class EstudianteDetailView(APIView):
    """Permite consultar, modificar y eliminar un estudiante respetando las reglas de rol y colegio."""
    permission_classes = [IsAuthenticated]

    def get_object(self, request, estudiante_id):
        if request.user.rol in ['admin_plataforma', 'admin_colegio'] or request.user.is_superuser or request.user.is_staff:
            colegio_id = get_colegio_id_for_request(request)
            qs = Estudiante.objects.filter(id=estudiante_id)
            if colegio_id:
                qs = qs.filter(colegio_id=colegio_id)
            try:
                return qs.get()
            except Estudiante.DoesNotExist:
                raise Http404
        elif hasattr(request.user, 'perfil_apoderado'):
            try:
                return Estudiante.objects.get(id=estudiante_id, apoderado=request.user.perfil_apoderado)
            except Estudiante.DoesNotExist:
                raise Http404
        raise Http404

    def get(self, request, estudiante_id):
        estudiante = self.get_object(request, estudiante_id)
        return Response(EstudianteSerializer(estudiante).data, status=status.HTTP_200_OK)

    def patch(self, request, estudiante_id):
        estudiante = self.get_object(request, estudiante_id)
        is_admin = request.user.rol in ['admin_plataforma', 'admin_colegio'] or request.user.is_superuser or request.user.is_staff

        data = request.data.copy()
        if request.user.rol == 'admin_colegio':
            data['colegio'] = request.user.colegio_id
        if not is_admin:
            data.pop('colegio', None)
        if data.get('foto') and not biometria_autorizada(estudiante):
            return _respuesta_biometria_sin_aceptar()

        ruta_en_curso = ruta_en_curso_bloquea_cambio(estudiante, data)
        if ruta_en_curso:
            return Response({
                'message': (
                    f'No se puede cambiar la sede ni el colegio mientras la ruta "{ruta_en_curso.nombre}" '
                    'está en curso. Espera a que el conductor la finalice.'
                ),
            }, status=status.HTTP_409_CONFLICT)

        serializer_class = EstudianteSerializer if is_admin else EstudianteUpdateSerializer
        serializer = serializer_class(
            estudiante,
            data=data,
            partial=True
        )
        if not serializer.is_valid():
            return Response({
                'message': 'Error al actualizar el estudiante.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response({
            'message': 'Información del estudiante actualizada.',
            'estudiante': EstudianteSerializer(estudiante).data
        }, status=status.HTTP_200_OK)

    def put(self, request, estudiante_id):
        return self.patch(request, estudiante_id)

    def delete(self, request, estudiante_id):
        return respuesta_desactivar(desactivar_estudiante, self.get_object(request, estudiante_id))


class EstudianteFotoView(APIView):
    """Entrega la foto privada solo al apoderado dueño del estudiante."""
    permission_classes = [IsAuthenticated]

    def get(self, request, estudiante_id):
        if not hasattr(request.user, 'perfil_apoderado'):
            raise Http404
        try:
            estudiante = Estudiante.objects.get(
                id=estudiante_id,
                apoderado=request.user.perfil_apoderado
            )
        except Estudiante.DoesNotExist:
            # No revela si existe un estudiante perteneciente a otra cuenta.
            raise Http404
        if not estudiante.foto:
            raise Http404
        try:
            archivo = estudiante.foto.open('rb')
        except FotoIlegibleError:
            # Cifrada con otra clave: se trata como si no tuviera foto.
            raise Http404

        respuesta = FileResponse(archivo, content_type='image/jpeg')
        respuesta['Cache-Control'] = 'private, no-store, max-age=0'
        respuesta['X-Content-Type-Options'] = 'nosniff'
        return respuesta




## RECUPERAR CONTRASEÑA

class RegistrarRostroView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, estudiante_id):
        # 1. Obtener los bytes de la imagen (vía archivo subido multipart o string base64)
        imagen_bytes = None

        archivo = request.FILES.get('foto') or request.FILES.get('imagen')
        if archivo:
            from usuarios.biometric_config import (
                ALLOWED_BIOMETRIC_CONTENT_TYPES,
                MAX_BIOMETRIC_IMAGE_BYTES,
            )
            if archivo.content_type.lower() not in ALLOWED_BIOMETRIC_CONTENT_TYPES:
                return Response(
                    {'message': 'Formato no admitido. Selecciona una imagen JPG, JPEG o PNG.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if archivo.size > MAX_BIOMETRIC_IMAGE_BYTES:
                return Response(
                    {'message': 'La imagen supera el máximo permitido de 5 MB.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            imagen_bytes = archivo.read()
        else:
            imagen_bytes = request.data.get('imagen') or request.data.get('foto')

        if not imagen_bytes:
            return Response(
                {'message': 'Se requiere seleccionar una fotografía para generar el registro biométrico.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        estudiantes = Estudiante.objects.filter(id=estudiante_id)
        if request.user.rol in ['admin_plataforma', 'admin_colegio'] or request.user.is_superuser:
            colegio_id = get_colegio_id_for_request(request)
            if colegio_id:
                estudiantes = estudiantes.filter(colegio_id=colegio_id)
        elif hasattr(request.user, 'perfil_apoderado'):
            estudiantes = estudiantes.filter(apoderado=request.user.perfil_apoderado)
        else:
            return Response(
                {'message': 'No tiene permisos para registrar la biometria de este estudiante.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        estudiante = estudiantes.first()
        if not estudiante:
            return Response({'message': 'Estudiante no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not biometria_autorizada(estudiante):
            return _respuesta_biometria_sin_aceptar()

        from usuarios.biometric_config import BIOMETRIC_PIPELINE_VERSION
        from usuarios.face_recognition_service import FaceRecognitionEngine
        if isinstance(imagen_bytes, str):
            import base64
            import binascii
            if ',' in imagen_bytes:
                imagen_bytes = imagen_bytes.split(',', 1)[1]
            try:
                imagen_bytes = base64.b64decode(imagen_bytes, validate=True)
            except (binascii.Error, ValueError):
                return Response(
                    {'message': 'La imagen biométrica no tiene un formato válido.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        engine = FaceRecognitionEngine()
        exito, resultado = engine.procesar_foto_estudiante(imagen_bytes)

        if not exito:
            return Response({'message': resultado}, status=status.HTTP_400_BAD_REQUEST)

        # Guardar la foto privada y el embedding de la misma captura.
        from django.core.files.base import ContentFile
        foto_anterior = estudiante.foto.name if estudiante.foto else None
        foto_normalizada = EstudianteSerializer._normalizar_foto(
            ContentFile(imagen_bytes, name='rostro.jpg')
        )
        estudiante.foto.save('foto.jpg', foto_normalizada, save=False)
        estudiante.embedding_facial = resultado
        estudiante.embedding_facial_version = BIOMETRIC_PIPELINE_VERSION
        estudiante.save(update_fields=['foto', 'embedding_facial', 'embedding_facial_version', 'updated_at'])
        if foto_anterior and foto_anterior != estudiante.foto.name:
            estudiante.foto.storage.delete(foto_anterior)

        return Response({
            'message': f"¡Rostro de {estudiante.nombre} {estudiante.apellido} procesado y vector biométrico guardado exitosamente!",
            'estudiante_id': estudiante.id,
            'tiene_biometria': True,
            'pipeline_biometrico': BIOMETRIC_PIPELINE_VERSION,
        }, status=status.HTTP_200_OK)


class InasistenciasEstudianteView(APIView):
    """
    El apoderado avisa que hoy o mañana no enviará a su hijo en el furgón (ida, vuelta o ambos),
    o cancela el aviso ("sí asistirá"). La ruta del conductor lo considera de inmediato.
    """

    permission_classes = [IsAuthenticated]

    def _estudiante_del_apoderado(self, request, estudiante_id):
        perfil = getattr(request.user, 'perfil_apoderado', None)
        if request.user.rol != 'apoderado' or perfil is None:
            return None, Response(
                {'message': 'Solo el apoderado puede avisar inasistencias.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        estudiante = Estudiante.objects.filter(pk=estudiante_id, apoderado=perfil).first()
        if not estudiante:
            return None, Response({'message': 'Estudiante no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return estudiante, None

    def get(self, request, estudiante_id):
        estudiante, error = self._estudiante_del_apoderado(request, estudiante_id)
        if error:
            return error
        return Response(estado_asistencia(estudiante))

    def post(self, request, estudiante_id):
        estudiante, error = self._estudiante_del_apoderado(request, estudiante_id)
        if error:
            return error
        try:
            fecha = interpretar_fecha(request.data.get('fecha'))
            tramos = interpretar_tramos(request.data.get('tramo'))
            mensaje = marcar_inasistencia(
                estudiante, fecha, tramos,
                motivo=str(request.data.get('motivo') or '').strip(),
                usuario=request.user,
            )
        except InasistenciaError as exc:
            return Response({'message': str(exc), **estado_asistencia(estudiante)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': mensaje, **estado_asistencia(estudiante)})

    def delete(self, request, estudiante_id):
        estudiante, error = self._estudiante_del_apoderado(request, estudiante_id)
        if error:
            return error
        datos = request.query_params or request.data
        try:
            fecha = interpretar_fecha(datos.get('fecha'))
            tramos = interpretar_tramos(datos.get('tramo'))
            mensaje = cancelar_inasistencia(estudiante, fecha, tramos)
        except InasistenciaError as exc:
            return Response({'message': str(exc), **estado_asistencia(estudiante)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': mensaje, **estado_asistencia(estudiante)})


class EstudianteBiometriaView(APIView):
    """El apoderado autoriza o revoca el reconocimiento facial de UN hijo (Ley 21.719).

    Revocar es tan fácil como autorizar: borra al tiro y de forma definitiva la foto y el vector de
    ese hijo, que pasa a QR. Cada cambio deja una constancia inmutable (ConsentimientoBiometrico).
    Solo lo puede hacer su apoderado: el colegio no da ni retira este consentimiento.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, estudiante_id):
        perfil = getattr(request.user, 'perfil_apoderado', None)
        if request.user.rol != 'apoderado' or perfil is None:
            return Response(
                {'message': 'Solo el apoderado puede autorizar o retirar el reconocimiento facial de su hijo.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        estudiante = Estudiante.objects.filter(pk=estudiante_id, apoderado=perfil).first()
        if not estudiante:
            return Response({'message': 'Estudiante no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        autoriza = request.data.get('autoriza')
        if not isinstance(autoriza, bool):
            return Response({'message': 'Indica si autorizas o no el reconocimiento facial.'}, status=400)

        borrados = cambiar_biometria_estudiante(estudiante, autoriza, origen='detalle_hijo', request=request)
        nombre = estudiante.nombre
        if autoriza:
            mensaje = (
                f'Reconocimiento facial autorizado para {nombre}. Registra su foto para que el conductor '
                'pueda usarlo; mientras tanto sube y baja con tu código QR.'
            )
        else:
            mensaje = (
                f'Reconocimiento facial desactivado para {nombre}. '
                + ('Se eliminaron su foto y sus datos faciales. ' if borrados else '')
                + 'Desde ahora sube y baja con tu código QR o con el inspector.'
            )
        return Response({
            'message': mensaje,
            'datos_eliminados': borrados,
            'estudiante': EstudianteSerializer(estudiante).data,
        })
