# Base de datos — Rutas Seguras

- **Tipo:** relacional.
- **Motor:** SQLite 3.
- **Cómo se genera:** la estructura sale de los modelos de Django del proyecto (`backend/`).

## Contenido

| Archivo | Qué hace |
|---|---|
| `Scripts/01_creacion_tablas.sql` | Crea las 43 tablas con sus llaves primarias, llaves foráneas, restricciones y 102 índices. No contiene datos de personas. |
| `Scripts/02_usuarios_y_roles.sql` | Documenta los roles del sistema y crea la cuenta inicial del administrador de plataforma. |
| `Scripts/03_datos_prueba.sql` | Carga datos de prueba de dos colegios de Huechuraba: cuentas de todos los roles, furgones, rutas de ida y vuelta, apoderados, estudiantes, personas autorizadas y un día de historial. Al inicio del archivo está la lista de cuentas. |
| `Diagramas/Modelo_ER_RutasSeguras.pdf` | Modelo entidad-relación, con su diagrama y la descripción de cada tabla. |

## Orden de ejecución

```powershell
sqlite3 rutas_seguras.sqlite3 ".read Scripts/01_creacion_tablas.sql"
sqlite3 rutas_seguras.sqlite3 ".read Scripts/02_usuarios_y_roles.sql"
sqlite3 rutas_seguras.sqlite3 ".read Scripts/03_datos_prueba.sql"
```

Todas las cuentas usan la contraseña `Capstone26`. Los datos de personas son ficticios, aunque los colegios y las calles son reales. No se incluyen datos biométricos: todos los estudiantes parten en "Solo QR".

Ejecutar `python manage.py migrate` dentro de `backend/` da el mismo resultado que el script `01`.

## Usuarios y roles

SQLite no tiene usuarios ni permisos propios del motor: no existen `CREATE USER` ni `GRANT`. El control de acceso lo hace la aplicación. Cada persona es una fila de la tabla `usuarios_usuario`, y su columna `rol` define lo que puede hacer en el sistema:

- **Administrador de plataforma** (`admin_plataforma`): administra los colegios y sus planes.
- **Administrador de colegio** (`admin_colegio`): administra sedes, estudiantes, conductores, furgones y rutas de su colegio.
- **Apoderado** (`apoderado`): gestiona a sus hijos y sigue el recorrido.
- **Conductor** (`conductor`): realiza las rutas y registra subidas y entregas.
- **Delegado** (`delegado`): inspector o persona autorizada para recibir a un estudiante.

Las contraseñas se guardan cifradas con PBKDF2-SHA256. Los datos biométricos se guardan cifrados con Fernet (AES) y solo cuando el apoderado lo autoriza por cada hijo.

## Tablas principales

| Tabla | Contenido |
|---|---|
| `usuarios_colegio` / `usuarios_sede` | Colegios, su plan y sus sedes. |
| `usuarios_usuario` | Cuentas de acceso y su rol. |
| `usuarios_perfilapoderado` / `usuarios_perfilconductor` / `usuarios_perfildelegado` | Datos propios de cada rol. |
| `usuarios_estudiante` | Estudiantes, su domicilio y su autorización biométrica. |
| `usuarios_furgon` / `usuarios_ruta` | Vehículos y rutas (ida y vuelta) con sus estudiantes. |
| `usuarios_recorridoruta` / `usuarios_eventorecorrido` | Cada recorrido realizado y lo que pasó en él. |
| `usuarios_registroabordaje` / `usuarios_registroentrega` | Subidas y entregas de cada estudiante. |
| `usuarios_consentimientobiometrico` | Registro inmutable de autorizaciones y retiros de la biometría (Ley 21.719). |
| `usuarios_aceptacionterminos` | Aceptación de los términos y condiciones. |
| `usuarios_emergencia` / `usuarios_notificacion` | Emergencias reportadas y avisos enviados. |
