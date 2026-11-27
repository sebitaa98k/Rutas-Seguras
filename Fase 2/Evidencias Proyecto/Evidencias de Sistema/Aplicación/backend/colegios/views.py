from usuarios.papelera import desactivar_colegio, desactivar_sede
from usuarios.papelera_views import respuesta_desactivar
from django.http import Http404
import requests
from requests import RequestException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.models import Colegio, RutHabilitado, Sede, Usuario
from usuarios.permissions import IsAdministrador, IsAdminPlataforma, colegio_administrado, es_admin_colegio, es_admin_plataforma
from autenticacion.serializers import UsuarioResponseSerializer
from colegios.serializers import ColegioSerializer, SedeSerializer


class GeoCoincidenciasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('query', '').strip()
        if len(query) < 4:
            return Response(
                {'message': 'Ingrese una dirección de al menos 4 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            limite = max(1, min(int(request.query_params.get('limite', 6)), 10))
        except (TypeError, ValueError):
            limite = 6

        try:
            response = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={
                    'q': f'{query}, Chile',
                    'format': 'jsonv2',
                    'limit': limite,
                    'addressdetails': 1,
                    'countrycodes': 'cl',
                },
                headers={
                    'User-Agent': 'RutasSegurasCapstone/1.0 (contacto@rutasseguras.cl)',
                    'Accept-Language': 'es',
                },
                timeout=10,
            )
            response.raise_for_status()
            resultados = response.json()
        except (RequestException, ValueError):
            return Response(
                {'message': 'No fue posible consultar el servicio de direcciones. Intente nuevamente.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        coincidencias = []
        for item in resultados if isinstance(resultados, list) else []:
            try:
                # Nominatim suele ubicar solo la calle; se envían las partes para que el
                # frontend conserve la numeración que escribió el usuario.
                direccion = item.get('address') or {}
                coincidencias.append({
                    'latitud': float(item['lat']),
                    'longitud': float(item['lon']),
                    'nombreCompleto': item['display_name'],
                    'calle': direccion.get('road') or direccion.get('pedestrian') or '',
                    'numero': direccion.get('house_number') or '',
                    'comuna': (
                        direccion.get('city') or direccion.get('town') or direccion.get('village')
                        or direccion.get('suburb') or direccion.get('municipality') or ''
                    ),
                })
            except (KeyError, TypeError, ValueError):
                continue

        return Response({'total': len(coincidencias), 'coincidencias': coincidencias})


class ColegioListCreateView(APIView):
    def get_permissions(self):
        return [IsAdminPlataforma()] if self.request.method == 'POST' else [IsAuthenticated()]

    def get(self, request):
        if es_admin_plataforma(request.user):
            # Los colegios desactivados están en la papelera.
            colegios = Colegio.objects.filter(activo=True).order_by('-id')
        elif es_admin_colegio(request.user):
            colegios = Colegio.objects.filter(id=request.user.colegio_id)
        elif request.user.rol == 'apoderado':
            # Solo el colegio en que se validó su RUT.
            perfil = getattr(request.user, 'perfil_apoderado', None)
            ids_autorizados = RutHabilitado.objects.filter(
                activo=True, apoderado=perfil,
            ).values_list('colegio_id', flat=True) if perfil else []
            ids = set(ids_autorizados)
            if perfil and perfil.colegio_id:
                ids.add(perfil.colegio_id)
            colegios = Colegio.objects.filter(activo=True, id__in=ids).order_by('nombre')
        elif request.user.rol in ['conductor', 'delegado']:
            colegios = Colegio.objects.filter(activo=True).order_by('nombre')
        else:
            return Response({'message': 'No tiene permisos para ver los colegios.'}, status=403)
        if request.query_params.get('solo_activos') in ['true', '1', 'True']:
            colegios = colegios.filter(activo=True)
        return Response(ColegioSerializer(colegios, many=True).data)

    def post(self, request):
        serializer = ColegioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ColegioSerializer(serializer.save()).data, status=201)


class ColegioDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [IsAdminPlataforma()]
        if self.request.method == 'PATCH':
            return [IsAdministrador()]
        return [IsAuthenticated()]

    def get_object(self, request, pk):
        if es_admin_colegio(request.user) and request.user.colegio_id != pk:
            raise Http404
        try:
            colegio = Colegio.objects.get(pk=pk)
        except Colegio.DoesNotExist:
            raise Http404
        if not (es_admin_plataforma(request.user) or es_admin_colegio(request.user)) and not colegio.activo:
            raise Http404
        return colegio

    def get(self, request, pk):
        return Response(ColegioSerializer(self.get_object(request, pk)).data)

    def patch(self, request, pk):
        colegio_administrado(request, colegio_id=pk)
        colegio = self.get_object(request, pk)
        datos = request.data
        if es_admin_colegio(request.user):
            # El administrador de un colegio solo actualiza sus datos de contacto; el resto lo define la plataforma.
            datos = {campo: request.data[campo] for campo in ('telefono', 'email_contacto') if campo in request.data}
        serializer = ColegioSerializer(colegio, data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        respuesta = ColegioSerializer(serializer.save()).data
        if serializer.mensaje_plan:
            respuesta['message'] = serializer.mensaje_plan
        return Response(respuesta)

    def delete(self, request, pk):
        # Nada se borra: se desactiva si está vacío y queda en la papelera.
        return respuesta_desactivar(desactivar_colegio, self.get_object(request, pk))


class ColegioAdministradoresView(APIView):
    def get_permissions(self):
        return [IsAdminPlataforma()] if self.request.method == 'POST' else [IsAdministrador()]

    def get(self, request, colegio_id):
        colegio_administrado(request, colegio_id=colegio_id)
        admins = Usuario.objects.filter(rol='admin_colegio', colegio_id=colegio_id).order_by('-id')
        return Response(UsuarioResponseSerializer(admins, many=True).data)

    def post(self, request, colegio_id):
        colegio = colegio_administrado(request, colegio_id=colegio_id)
        if not colegio.activo:
            return Response({'message': 'No se pueden crear administradores para un colegio inactivo.'}, status=400)
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password', '')
        nombre = request.data.get('nombre', '').strip()
        apellido = request.data.get('apellido', '').strip()
        if not email or not password or not nombre or not apellido:
            return Response({'message': 'Debe ingresar nombre, apellido, correo electrónico y contraseña.'}, status=400)
        if Usuario.objects.filter(email=email).exists():
            return Response({'message': 'El correo electrónico ya se encuentra registrado.'}, status=400)
        usuario = Usuario.objects.create_user(username=email, email=email, password=password, first_name=nombre, last_name=apellido, rol='admin_colegio', colegio=colegio, debe_cambiar_password=True)
        return Response({'message': f'Administrador para {colegio.nombre} creado exitosamente.', 'usuario': UsuarioResponseSerializer(usuario).data}, status=201)


class ColegioAdministradorDetailView(APIView):
    """El administrador de plataforma edita la cuenta de un administrador de colegio."""

    permission_classes = [IsAdminPlataforma]

    def patch(self, request, colegio_id, usuario_id):
        colegio_administrado(request, colegio_id=colegio_id)
        admin = Usuario.objects.filter(pk=usuario_id, rol='admin_colegio', colegio_id=colegio_id).first()
        if not admin:
            raise Http404
        nombre = request.data.get('nombre')
        apellido = request.data.get('apellido')
        if nombre is not None:
            if not str(nombre).strip():
                return Response({'message': 'El nombre es obligatorio.'}, status=400)
            admin.first_name = str(nombre).strip()
        if apellido is not None:
            if not str(apellido).strip():
                return Response({'message': 'El apellido es obligatorio.'}, status=400)
            admin.last_name = str(apellido).strip()
        email = (request.data.get('email') or '').lower().strip()
        if email and email != admin.email:
            if Usuario.objects.filter(email=email).exclude(pk=admin.pk).exists():
                return Response({'message': 'El correo electrónico ya se encuentra registrado.'}, status=400)
            admin.email = email
            admin.username = email
        password = request.data.get('password') or ''
        if password:
            if len(password) < 6:
                return Response({'message': 'La contraseña debe tener al menos 6 caracteres.'}, status=400)
            # Contraseña nueva elegida por otra persona: debe cambiarla al ingresar.
            admin.set_password(password)
            admin.debe_cambiar_password = True
        admin.save()
        return Response({
            'message': 'Administrador actualizado.',
            'usuario': UsuarioResponseSerializer(admin).data,
        })


class SedeListCreateView(APIView):
    def get_permissions(self):
        # Crear sedes es de la plataforma: el colegio lo solicita por fuera (no se crean "de la nada").
        return [IsAdminPlataforma()] if self.request.method == 'POST' else [IsAuthenticated()]

    def get(self, request, colegio_id):
        if es_admin_plataforma(request.user) or es_admin_colegio(request.user):
            colegio_administrado(request, colegio_id=colegio_id)
        elif not Colegio.objects.filter(pk=colegio_id, activo=True).exists():
            raise Http404
        incluir_inactivas = request.query_params.get('incluir_inactivas') or request.query_params.get('todas')
        sedes = Sede.objects.filter(colegio_id=colegio_id)
        if incluir_inactivas not in ['true', '1', 'True'] or not (es_admin_plataforma(request.user) or es_admin_colegio(request.user)):
            sedes = sedes.filter(activa=True)
        # La principal va primero. En los colegios que no son multisede es la única (y la pantalla la oculta).
        return Response(SedeSerializer(sedes.order_by('-es_principal', 'nombre'), many=True).data)

    def post(self, request, colegio_id):
        colegio = colegio_administrado(request, colegio_id=colegio_id)
        if not colegio.activo:
            return Response({'message': 'El colegio está desactivado y no admite nuevas sedes.'}, status=400)
        if not colegio.es_multisede:
            return Response({
                'message': 'Solo los colegios con plan Avanzado (multisede) pueden tener más de una sede.',
            }, status=400)
        payload_colegio = request.data.get('colegio') or request.data.get('colegio_id')
        if payload_colegio is not None and str(payload_colegio).strip() != str(colegio.id):
            return Response({'message': 'No puede especificar un colegio diferente al autorizado.'}, status=403)
        data = request.data.copy()
        data['colegio'] = colegio.id
        serializer = SedeSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(SedeSerializer(serializer.save()).data, status=201)


# Lo único que el administrador de un colegio cambia en sus sedes (que no sean la principal).
CAMPOS_SEDE_ADMIN_COLEGIO = ('telefono',)


class SedeDetailView(APIView):
    permission_classes = [IsAdministrador]

    def get_object(self, request, pk):
        try:
            sede = Sede.objects.get(pk=pk)
        except Sede.DoesNotExist:
            raise Http404
        colegio_administrado(request, colegio_id=sede.colegio_id)
        return sede

    def patch(self, request, pk):
        sede = self.get_object(request, pk)
        data = request.data.copy()
        payload_colegio = data.get('colegio') or data.get('colegio_id')
        if payload_colegio is not None and str(payload_colegio).strip() != str(sede.colegio_id):
            return Response({'message': 'No puede modificar el colegio asignado a la sede.'}, status=403)
        if es_admin_colegio(request.user):
            # El colegio solo cambia el teléfono de sus sedes; nombre y dirección los define la plataforma,
            # porque mueven rutas y mapas. La principal copia los datos del colegio.
            if sede.es_principal:
                return Response({
                    'message': 'La sede principal usa los datos del colegio: cámbialos en "Editar datos de contacto".',
                }, status=403)
            data = {campo: request.data[campo] for campo in CAMPOS_SEDE_ADMIN_COLEGIO if campo in request.data}
        data['colegio'] = sede.colegio_id
        serializer = SedeSerializer(sede, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(SedeSerializer(serializer.save()).data)

    def delete(self, request, pk):
        # Desactivar una sede es de la plataforma (evita cerrar una por error). Solo se desactiva si no
        # tiene estudiantes, furgones, rutas ni inspectores activos.
        if not es_admin_plataforma(request.user):
            return Response({
                'message': 'Para desactivar una sede, solicítalo al administrador de la plataforma.',
            }, status=403)
        return respuesta_desactivar(desactivar_sede, self.get_object(request, pk))
