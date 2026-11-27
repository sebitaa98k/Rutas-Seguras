# Rutas Seguras

Sistema de gestión y seguimiento de transporte escolar desarrollado como proyecto Capstone.

Rutas Seguras permite administrar colegios, sedes, estudiantes, conductores, vehículos y rutas. También incluye una aplicación móvil para apoderados, conductores e inspectores/delegados.

## Aplicaciones

- `backend/`: API REST desarrollada con Django, más un servicio de mapas (`api.js`) para el trazado de rutas.
- `mobile-app/`: aplicación móvil Ionic y Angular.
- `web-admin/`: panel administrativo Angular.
- `apk/`: aplicación Android lista para instalar.

## Roles

### Apoderado
- Registrar y consultar hijos.
- Autorizar el reconocimiento facial por cada hijo (opcional).
- Seguir la ruta escolar en el mapa.
- Recibir notificaciones.
- Mostrar su código QR para la subida y la entrega.
- Gestionar datos personales y personas autorizadas.

### Conductor
- Consultar estudiantes asignados.
- Registrar subidas y entregas mediante QR o reconocimiento facial.
- Iniciar y finalizar rutas.
- Compartir el seguimiento del recorrido.
- Registrar emergencias.

### Inspector o delegado
- Consultar alumnos del colegio o sede asignada.
- Consultar rutas y su seguimiento.
- Generar códigos QR de validación institucional.

### Administrador de colegio
- Administrar sedes, estudiantes, apoderados, conductores e inspectores.
- Asignar vehículos y rutas.
- Consultar el seguimiento, los reportes y la auditoría.

### Administrador de plataforma
- Administrar colegios y sus planes.
- Revisar la papelera y la auditoría general.

## Tecnologías

### Backend
- Python 3.12
- Django 6.1 y Django REST Framework
- SQLite
- OpenCV y NumPy (reconocimiento facial)
- Firebase Admin (notificaciones push)
- Gmail SMTP (correos de recuperación de contraseña)
- Node.js (servicio de mapas con OSRM)

### Aplicación móvil
- Ionic 8
- Angular 20
- Capacitor 8
- TypeScript
- Leaflet

### Panel administrativo
- Angular 21
- Leaflet

## Requisitos

- Python 3.12 o superior.
- Node.js 22.
- npm.
- Android Studio, solamente para generar o ejecutar la aplicación Android.

## Instalación

### 1. Obtener el código

El código fuente completo está en esta carpeta. Abre una terminal dentro de ella para seguir los pasos.

### 2. Configurar el backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item backend\.env.example backend\.env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Pega la clave que se muestra en `BIOMETRIA_CLAVE_CIFRADO=` dentro de `backend\.env`. Es necesaria para el reconocimiento facial.

```powershell
cd backend
python manage.py migrate
python manage.py cargar_datos_prueba --si
python manage.py createsuperuser
python manage.py shell -c "from usuarios.models import Usuario; Usuario.objects.filter(email='TU_CORREO').update(rol='admin_plataforma', colegio=None)"
python manage.py runserver
```

- `cargar_datos_prueba` crea colegios, sedes, rutas y cuentas de ejemplo. Todas usan la contraseña `Prueba1234`.
- `createsuperuser` crea la cuenta y el comando siguiente le asigna el rol de administrador de plataforma. Cambia `TU_CORREO` por el correo que ingresaste en `createsuperuser`.
- Sin `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD` no se envían correos, y sin la credencial de Firebase no llegan las notificaciones push. El resto funciona igual.

### 3. Ejecutar el servicio de mapas

En otra terminal, desde esta carpeta:

```powershell
node backend/api.js
```

### 4. Ejecutar la aplicación móvil

En otra terminal:

```powershell
cd mobile-app
npm install
npm start -- --port 8100
```

Si solo quieres probar la aplicación en un celular Android, la carpeta `apk/` contiene la aplicación lista para instalar (`RutasSeguras-demo.apk`). No es necesario compilarla.

Al abrirla, en el inicio de sesión toca "Servidor" e ingresa la dirección del computador donde corre el backend (por ejemplo `http://192.168.1.10:8000/api`). El celular y el computador deben estar en la misma red wifi, y el backend debe iniciarse con `python manage.py runserver 0.0.0.0:8000`.

Para generar la versión Android:

```powershell
npm run build
npx cap sync android
npm run cap:open
```

### 5. Ejecutar el panel administrativo

En otra terminal:

```powershell
cd web-admin
npm install
npm start
```

## Base de datos

El sistema usa una base de datos relacional SQLite. Las tablas se crean con `python manage.py migrate`. El script SQL de creación y el modelo entidad-relación están en la carpeta "Base de datos" de las evidencias.

## Autores

Proyecto Capstone desarrollado por Constanza Reyes, Sebastián Delso y Chris Bugman.