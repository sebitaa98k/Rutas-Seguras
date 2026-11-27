"""Borra los datos de la base y carga un conjunto de prueba con nombres y RUT inventados.

Uso:  python manage.py cargar_datos_prueba --si

- Conserva solo las cuentas de administrador de plataforma (superusuarios).
- Todas las cuentas nuevas usan la contraseña Prueba1234, sin cambio obligatorio
  y con los términos ya aceptados.
- Las ubicaciones (latitud/longitud) quedan vacías para fijarlas a mano.
- No hay fotos ni vectores faciales: hay que subir fotos reales para probar el reconocimiento.
"""
from datetime import date, time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from usuarios.asignaciones import sincronizar_conductor_de_estudiantes
from usuarios.models import (
    AceptacionTerminos, CodigoQREntrega, CodigoRecuperacion, Colegio, DelegadoSede,
    Emergencia, Estudiante, EventoRecorrido, FCMToken, Furgon, InasistenciaEstudiante, Notificacion,
    PerfilApoderado, PerfilConductor, PerfilDelegado, PersonaAutorizada, RecorridoRuta,
    RegistroAbordaje, RegistroEntrega, Ruta, RutHabilitado, Sede, Usuario,
)
from usuarios.terminos import VERSION_VIGENTE, huella_texto, texto_terminos

PASSWORD = 'Prueba1234'
DOMINIO = 'prueba.cl'

COLEGIOS = [
    {
        'nombre': 'Colegio Los Aromos', 'rbd': '10101', 'comuna': 'Maipú',
        'direccion': 'Av. Los Aromos 1200', 'telefono': '+56 2 2345 1001',
        'sedes': ['Sede Central', 'Sede Básica'],
    },
    {
        'nombre': 'Colegio San Esteban', 'rbd': '20202', 'comuna': 'La Florida',
        'direccion': 'Calle San Esteban 455', 'telefono': '+56 2 2345 2002',
        'sedes': ['Sede Norte', 'Sede Sur'],
    },
    {
        'nombre': 'Liceo Valle Verde', 'rbd': '30303', 'comuna': 'Puente Alto',
        'direccion': 'Pasaje Valle Verde 78', 'telefono': '+56 2 2345 3003',
        'sedes': ['Sede Principal', 'Sede Anexa'],
    },
]

ADMINS = [('Paula', 'Contreras'), ('Rodrigo', 'Fuentes'), ('Marcela', 'Ibáñez')]

CONDUCTORES = [
    ('Luis', 'Pizarro'), ('Héctor', 'Navarro'), ('Carmen', 'Rojas'),
    ('Patricio', 'Lagos'), ('Ana', 'Valdés'), ('Jorge', 'Muñoz'),
    ('Rosa', 'Tapia'), ('Manuel', 'Araya'), ('Sergio', 'Cortés'),
]

FURGONES = [
    'Hyundai H-1', 'Toyota Hiace', 'Mercedes-Benz Sprinter', 'Peugeot Boxer', 'Renault Master',
    'Ford Transit', 'Kia Pregio', 'Fiat Ducato', 'Citroën Jumper',
]

# (nombre, apellido, colegio, [(hijo, apellido materno, curso, sede)])
APODERADOS = [
    ('Claudia', 'Morales', 0, [('Tomás', 'Soto', '3° Básico', 0), ('Isidora', 'Soto', '1° Básico', 0)]),
    ('Felipe', 'Herrera', 0, [('Martina', 'Ríos', '5° Básico', 1)]),
    ('Daniela', 'Vergara', 0, [('Benjamín', 'Castro', '2° Básico', 0), ('Agustina', 'Castro', '6° Básico', 1)]),
    ('Andrés', 'Salinas', 1, [('Florencia', 'Peña', '4° Básico', 0)]),
    ('Verónica', 'Espinoza', 1, [('Vicente', 'Olivares', '7° Básico', 1), ('Josefa', 'Olivares', '3° Básico', 0)]),
    ('Cristián', 'Reyes', 1, [('Maximiliano', 'Silva', '8° Básico', 0)]),
    ('Javiera', 'Bravo', 2, [('Emilia', 'Gallardo', '1° Medio', 0), ('Lucas', 'Gallardo', '5° Básico', 1)]),
    ('Gonzalo', 'Sepúlveda', 2, [('Catalina', 'Mena', '2° Medio', 0)]),
]

# (nombre, apellido, colegio, sede): un inspector por sede, y dos en la primera para mostrar que puede haber varios.
INSPECTORES = [
    ('Ricardo', 'Alarcón', 0, 0), ('Lorena', 'Figueroa', 0, 1), ('Tomás', 'Riquelme', 1, 0),
    ('Paola', 'Saavedra', 1, 1), ('Iván', 'Carrasco', 2, 0), ('Gloria', 'Paredes', 2, 1),
    ('Mauricio', 'Vidal', 0, 0),
]

# (nombre, apellido, índice del apoderado, índice del hijo): persona autorizada con cuenta.
AUTORIZADOS = [('Teresa', 'Morales', 0, 0), ('Pablo', 'Salinas', 3, 0)]

CALLES = [
    'Los Pinos', 'Las Acacias', 'El Roble', 'Los Olmos', 'Santa Julia', 'Las Camelias',
    'El Quillay', 'Los Castaños', 'La Esperanza', 'Las Violetas', 'El Boldo', 'Los Cerezos',
]


def digito_verificador(cuerpo):
    suma, factor = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resto, str(resto))


class GeneradorRut:
    def __init__(self, inicio):
        self.actual = inicio

    def siguiente(self):
        self.actual += 7919
        return f'{self.actual}-{digito_verificador(self.actual)}'


class Command(BaseCommand):
    help = 'Borra los datos actuales y carga datos de prueba (colegios, sedes, cuentas, estudiantes y rutas).'

    def add_arguments(self, parser):
        parser.add_argument('--si', action='store_true', help='Confirma que se borrarán los datos actuales.')

    def handle(self, *args, **opciones):
        if not opciones['si']:
            raise CommandError('Esto borra todos los datos salvo los superusuarios. Repite con --si para confirmar.')
        if not settings.DEBUG:
            raise CommandError('Solo se permite con DEBUG=True (entorno de desarrollo).')

        with transaction.atomic():
            self._borrar_todo()
            cuentas = self._cargar()
        self._borrar_fotos()
        self._resumen(cuentas)

    # ------------------------------------------------------------------ borrado

    def _borrar_todo(self):
        # Primero lo que protege a otros registros (PROTECT), después el resto.
        for modelo in (
            EventoRecorrido, RecorridoRuta, RegistroEntrega, RegistroAbordaje, Emergencia,
            CodigoQREntrega, InasistenciaEstudiante, Notificacion, FCMToken, CodigoRecuperacion,
            AceptacionTerminos, RutHabilitado, PersonaAutorizada, Ruta, Furgon,
            Estudiante, DelegadoSede, PerfilApoderado, PerfilConductor, PerfilDelegado,
        ):
            # `todos`: también borra lo que estaba en la papelera (este comando reinicia la base de desarrollo).
            getattr(modelo, 'todos', modelo.objects).all().delete()
        Usuario.objects.filter(is_superuser=False).delete()
        Sede.objects.all().delete()
        Colegio.objects.all().delete()

    def _borrar_fotos(self):
        # Las fotos de los registros borrados quedarían huérfanas en el disco.
        for carpeta in ('fotos_estudiantes', 'fotos_apoderados', 'fotos_delegados'):
            ruta = settings.MEDIA_ROOT / carpeta
            if ruta.is_dir():
                for archivo in ruta.iterdir():
                    if archivo.is_file():
                        archivo.unlink()

    # ------------------------------------------------------------------ carga

    def _usuario(self, correo, nombre, apellido, rol, colegio):
        usuario = Usuario(
            email=correo, username=correo, first_name=nombre, last_name=apellido,
            rol=rol, colegio=colegio, debe_cambiar_password=False,
            terminos_version_aceptada=VERSION_VIGENTE if rol == 'apoderado' else '',
        )
        usuario.set_password(PASSWORD)
        usuario.save()
        return usuario

    def _cargar(self):
        ruts = GeneradorRut(10_000_000)
        ruts_menores = GeneradorRut(23_000_000)
        huella = huella_texto(texto_terminos())
        ahora = timezone.now()
        cuentas = []
        colegios, sedes_por_colegio = [], []

        for i, datos in enumerate(COLEGIOS):
            colegio = Colegio.objects.create(
                nombre=datos['nombre'], rbd=datos['rbd'], direccion=datos['direccion'],
                comuna=datos['comuna'], region='Región Metropolitana', telefono=datos['telefono'],
                email_contacto=f'contacto{i + 1}@{DOMINIO}',
                # Los colegios de prueba tienen dos sedes: son multisede.
                plan=Colegio.PLAN_AVANZADO,
            )
            sedes = [
                Sede.objects.create(
                    colegio=colegio, nombre=nombre_sede, es_principal=(j == 0),
                    direccion=f"{datos['direccion'].rsplit(' ', 1)[0]} {300 + 150 * j}",
                    comuna=datos['comuna'], region='Región Metropolitana', telefono=datos['telefono'],
                )
                for j, nombre_sede in enumerate(datos['sedes'])
            ]
            colegios.append(colegio)
            sedes_por_colegio.append(sedes)

            nombre, apellido = ADMINS[i]
            correo = f'admin{i + 1}@{DOMINIO}'
            self._usuario(correo, nombre, apellido, 'admin_colegio', colegio)
            cuentas.append(('Admin colegio', correo, f'{nombre} {apellido}', colegio.nombre))

        # Conductores y furgones: los dos primeros de cada colegio en la sede 1, el tercero en la sede 2.
        conductores_por_sede = {}
        for n, (nombre, apellido) in enumerate(CONDUCTORES):
            i, k = divmod(n, 3)
            colegio = colegios[i]
            sede = sedes_por_colegio[i][0 if k < 2 else 1]
            correo = f'conductor{n + 1}@{DOMINIO}'
            usuario = self._usuario(correo, nombre, apellido, 'conductor', colegio)
            perfil = PerfilConductor.objects.create(
                usuario=usuario, colegio=colegio, rut=ruts.siguiente(),
                telefono=f'+56 9 6{n + 1:03d} {4100 + n:04d}', licencia_conducir='Clase A3',
            )
            furgon = Furgon.objects.create(
                colegio=colegio, sede=sede, patente=f'TST{n + 1:03d}', marca_modelo=FURGONES[n],
                capacidad=12, conductor_asignado=f'{nombre} {apellido}',
            )
            conductores_por_sede.setdefault(sede.id, []).append((perfil, furgon))
            cuentas.append(('Conductor', correo, f'{nombre} {apellido}', f'{colegio.nombre} - {sede.nombre}'))

        # Apoderados (con su RUT habilitado ya usado y su aceptación de términos) e hijos.
        apoderados, hijos_por_apoderado = [], []
        estudiantes_por_sede = {}
        calle = 0
        for a, (nombre, apellido, i, hijos) in enumerate(APODERADOS):
            colegio = colegios[i]
            correo = f'apoderado{a + 1}@{DOMINIO}'
            usuario = self._usuario(correo, nombre, apellido, 'apoderado', colegio)
            rut = ruts.siguiente()
            perfil = PerfilApoderado.objects.create(
                usuario=usuario, colegio=colegio, rut=rut, telefono=f'+56 9 7{a + 1:03d} {5200 + a:04d}',
            )
            RutHabilitado.objects.create(colegio=colegio, rut=rut, apoderado=perfil, usado_en=ahora)
            AceptacionTerminos.objects.create(
                usuario=usuario, colegio=colegio, colegio_nombre=colegio.nombre, rut=rut,
                nombre=f'{nombre} {apellido}', email=correo, version=VERSION_VIGENTE,
                huella_texto=huella, origen='registro',
                dispositivo='Carga de datos de prueba',
            )
            direccion = f'{CALLES[calle % len(CALLES)]} {100 + 37 * a}'
            calle += 1
            lista = []
            for h, (hijo, materno, curso, indice_sede) in enumerate(hijos):
                sede = sedes_por_colegio[i][indice_sede]
                estudiante = Estudiante.objects.create(
                    apoderado=perfil, nombre=hijo, apellido=f'{apellido} {materno}',
                    rut=ruts_menores.siguiente(), fecha_nacimiento=date(2012 + a % 6, 1 + (a + h) % 12, 10 + h),
                    colegio=colegio, sede=sede, curso=curso, direccion_principal=direccion,
                    comuna=COLEGIOS[i]['comuna'], region='Región Metropolitana',
                )
                lista.append(estudiante)
                estudiantes_por_sede.setdefault(sede.id, []).append(estudiante)
            apoderados.append(perfil)
            hijos_por_apoderado.append(lista)
            cuentas.append(('Apoderado', correo, f'{nombre} {apellido}',
                            f"{colegio.nombre} - hijos: {', '.join(e.nombre for e in lista)}"))

        # RUT habilitados libres, para probar el registro de un apoderado nuevo desde la app.
        libres = []
        for colegio in colegios:
            for _ in range(2):
                rut = ruts.siguiente()
                RutHabilitado.objects.create(colegio=colegio, rut=rut)
                libres.append((colegio.nombre, rut))

        # Inspectores: cada uno con su sede.
        for d, (nombre, apellido, i, s) in enumerate(INSPECTORES):
            colegio = colegios[i]
            sede = sedes_por_colegio[i][s]
            correo = f'inspector{d + 1}@{DOMINIO}'
            usuario = self._usuario(correo, nombre, apellido, 'delegado', colegio)
            perfil = PerfilDelegado.objects.create(
                usuario=usuario, colegio=colegio, rut=ruts.siguiente(),
                telefono=f'+56 9 8{d + 1:03d} {6300 + d:04d}', tipo_delegado='inspector',
            )
            DelegadoSede.objects.create(sede=sede, delegado=perfil)
            cuentas.append(('Inspector', correo, f'{nombre} {apellido}', f'{colegio.nombre} - {sede.nombre}'))

        # Personas autorizadas con cuenta de delegado.
        for d, (nombre, apellido, a, h) in enumerate(AUTORIZADOS):
            estudiante = hijos_por_apoderado[a][h]
            colegio = estudiante.colegio
            correo = f'autorizado{d + 1}@{DOMINIO}'
            usuario = self._usuario(correo, nombre, apellido, 'delegado', colegio)
            rut = ruts.siguiente()
            telefono = f'+56 9 9{d + 1:03d} {7400 + d:04d}'
            perfil = PerfilDelegado.objects.create(
                usuario=usuario, colegio=colegio, rut=rut, telefono=telefono, tipo_delegado='autorizado',
            )
            PersonaAutorizada.objects.create(
                estudiante=estudiante, apoderado=estudiante.apoderado, colegio=colegio,
                perfil_delegado=perfil, nombre=f'{nombre} {apellido}', rut=rut, telefono=telefono,
            )
            cuentas.append(('Persona autorizada', correo, f'{nombre} {apellido}',
                            f'{colegio.nombre} - retira a {estudiante.nombre} {estudiante.apellido}'))

        # Rutas: una de ida y una de vuelta por conductor, con los estudiantes de su sede repartidos.
        ids = set()
        for sede_id, pares in conductores_por_sede.items():
            estudiantes = estudiantes_por_sede.get(sede_id, [])
            for c, (perfil, furgon) in enumerate(pares):
                asignados = estudiantes[c::len(pares)]
                nombre_conductor = perfil.usuario.get_full_name()
                for sentido, hora, etiqueta in (
                    ('hacia_colegio', time(7, 15), 'Ida'),
                    ('desde_colegio', time(16, 30), 'Vuelta'),
                ):
                    ruta = Ruta.objects.create(
                        nombre=f'{etiqueta} {furgon.sede.nombre} - {perfil.usuario.first_name}',
                        sentido=sentido, conductor=nombre_conductor, colegio=furgon.colegio,
                        sede=furgon.sede, conductor_perfil=perfil, furgon=furgon,
                        estudiantes_count=len(asignados), hora_programada=hora,
                        **self._extremos(sentido, furgon.sede, asignados),
                    )
                    ruta.estudiantes.set(asignados)
                ids.update(e.id for e in asignados)
        sincronizar_conductor_de_estudiantes(ids)

        self.libres = libres
        return cuentas

    @staticmethod
    def _extremos(sentido, sede, estudiantes):
        if not estudiantes:
            return {}
        casa = estudiantes[0] if sentido == 'hacia_colegio' else estudiantes[-1]
        if sentido == 'hacia_colegio':
            return {'origen_direccion': casa.direccion_completa[:255],
                    'destino_direccion': sede.direccion_completa[:255]}
        return {'origen_direccion': sede.direccion_completa[:255],
                'destino_direccion': casa.direccion_completa[:255]}

    # ------------------------------------------------------------------ resumen

    def _resumen(self, cuentas):
        self.stdout.write(self.style.SUCCESS('Datos de prueba cargados.'))
        self.stdout.write(f'Contraseña de todas las cuentas: {PASSWORD}\n')
        for rol, correo, nombre, detalle in cuentas:
            self.stdout.write(f'  {rol:<19} {correo:<26} {nombre:<20} {detalle}')
        self.stdout.write('\nRUT habilitados libres (para registrar un apoderado nuevo en la app):')
        for colegio, rut in self.libres:
            self.stdout.write(f'  {rut:<12} {colegio}')
        self.stdout.write(
            f'\nTotales: {Colegio.objects.count()} colegios, {Sede.objects.count()} sedes, '
            f'{Estudiante.objects.count()} estudiantes, {Furgon.objects.count()} furgones, '
            f'{Ruta.objects.count()} rutas.'
        )
        self.stdout.write('Faltan: ubicaciones (latitud/longitud) y fotos de los estudiantes.')
