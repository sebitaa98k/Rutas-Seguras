-- =====================================================================
-- Rutas Seguras - Script de creación de la base de datos
-- Motor: SQLite 3 (base de datos relacional)
-- Generado el 27/11/2026 a partir de las migraciones de Django del proyecto.
--
-- Crea todas las tablas, llaves primarias, llaves foráneas, restricciones
-- e índices. No contiene datos de personas.
--
-- Uso:  sqlite3 rutas_seguras.sqlite3 < 01_creacion_tablas.sql
-- Equivale a ejecutar "python manage.py migrate" en backend/.
-- =====================================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- Tabla: django_migrations
CREATE TABLE "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL);

-- Tabla: django_content_type
CREATE TABLE "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

-- Tabla: auth_group_permissions
CREATE TABLE "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: auth_permission
CREATE TABLE "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

-- Tabla: auth_group
CREATE TABLE "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

-- Tabla: usuarios_usuario_groups
CREATE TABLE "usuarios_usuario_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "usuario_id" bigint NOT NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_usuario_user_permissions
CREATE TABLE "usuarios_usuario_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "usuario_id" bigint NOT NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: django_admin_log
CREATE TABLE "django_admin_log" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "object_id" text NULL, "object_repr" varchar(200) NOT NULL, "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0), "change_message" text NOT NULL, "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" bigint NOT NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "action_time" datetime NOT NULL);

-- Tabla: authtoken_token
CREATE TABLE "authtoken_token" ("key" varchar(40) NOT NULL PRIMARY KEY, "created" datetime NOT NULL, "user_id" bigint NOT NULL UNIQUE REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: django_session
CREATE TABLE "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL);

-- Tabla: usuarios_codigorecuperacion
CREATE TABLE "usuarios_codigorecuperacion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "codigo" varchar(6) NOT NULL, "creado_en" datetime NOT NULL, "usado" bool NOT NULL, "usuario_id" bigint NOT NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_fcmtoken
CREATE TABLE "usuarios_fcmtoken" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "token" text NOT NULL UNIQUE, "device_name" varchar(100) NULL, "is_active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "usuario_id" bigint NOT NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_emergencia
CREATE TABLE "usuarios_emergencia" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "categoria" varchar(30) NOT NULL, "tipo_emergencia" varchar(100) NOT NULL, "descripcion" text NOT NULL, "creado_en" datetime NOT NULL, "conductor_id" bigint NOT NULL REFERENCES "usuarios_perfilconductor" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "ruta_id" bigint NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "furgon_id" bigint NULL REFERENCES "usuarios_furgon" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_estudiantes
CREATE TABLE "usuarios_ruta_estudiantes" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_estudiantes_abordados
CREATE TABLE "usuarios_ruta_estudiantes_abordados" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_paradas_completadas
CREATE TABLE "usuarios_ruta_paradas_completadas" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_estudiantes_ausentes
CREATE TABLE "usuarios_ruta_estudiantes_ausentes" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_estudiantes_entregados
CREATE TABLE "usuarios_ruta_estudiantes_entregados" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_inasistenciaestudiante
CREATE TABLE "usuarios_inasistenciaestudiante" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "fecha" date NOT NULL, "ida" bool NOT NULL, "vuelta" bool NOT NULL, "motivo" varchar(200) NOT NULL, "creado_en" datetime NOT NULL, "actualizado_en" datetime NOT NULL, "creado_por_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "inasistencia_unica_por_dia" UNIQUE ("estudiante_id", "fecha"));

-- Tabla: usuarios_notificacion
CREATE TABLE "usuarios_notificacion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "titulo" varchar(150) NOT NULL, "mensaje" text NOT NULL, "tipo" varchar(30) NOT NULL, "leido" bool NOT NULL, "creado_en" datetime NOT NULL, "estudiante_id" bigint NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "apoderado_id" bigint NULL REFERENCES "usuarios_perfilapoderado" ("id") DEFERRABLE INITIALLY DEFERRED, "destinatario_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_registroabordaje
CREATE TABLE "usuarios_registroabordaje" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "metodo_validacion" varchar(32) NOT NULL, "abordado_en" datetime NOT NULL, "colegio_id" bigint NOT NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "conductor_id" bigint NOT NULL REFERENCES "usuarios_perfilconductor" ("id") DEFERRABLE INITIALLY DEFERRED, "delegado_id" bigint NULL REFERENCES "usuarios_perfildelegado" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_estudiantes_llamados
CREATE TABLE "usuarios_ruta_estudiantes_llamados" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_ruta_estudiantes_no_recibidos
CREATE TABLE "usuarios_ruta_estudiantes_no_recibidos" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_recorridoruta
CREATE TABLE "usuarios_recorridoruta" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre_ruta" varchar(150) NOT NULL, "sentido" varchar(20) NOT NULL, "conductor_nombre" varchar(200) NOT NULL, "furgon_patente" varchar(20) NOT NULL, "hora_programada" time NULL, "minutos_atraso" integer NULL, "estudiantes" text NOT NULL CHECK ((JSON_VALID("estudiantes") OR "estudiantes" IS NULL)), "iniciado_en" datetime NULL, "finalizado_en" datetime NULL, "creado_en" datetime NOT NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "ruta_id" bigint NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "simulado" bool NOT NULL);

-- Tabla: usuarios_delegadosede
CREATE TABLE "usuarios_delegadosede" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "activo" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "delegado_id" bigint NOT NULL REFERENCES "usuarios_perfildelegado" ("id") DEFERRABLE INITIALLY DEFERRED, "sede_id" bigint NOT NULL REFERENCES "usuarios_sede" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "inspector_con_una_sola_sede" UNIQUE ("delegado_id"));

-- Tabla: usuarios_furgon
CREATE TABLE "usuarios_furgon" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "patente" varchar(20) NOT NULL UNIQUE, "marca_modelo" varchar(100) NOT NULL, "capacidad" integer NOT NULL, "conductor_asignado" varchar(150) NOT NULL, "estado" varchar(20) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "sede_id" bigint NULL REFERENCES "usuarios_sede" ("id") DEFERRABLE INITIALLY DEFERRED, "activo" bool NOT NULL, "desactivado_en" datetime NULL);

-- Tabla: usuarios_ruta
CREATE TABLE "usuarios_ruta" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "conductor" varchar(150) NOT NULL, "estudiantes_count" integer NOT NULL, "estado" varchar(20) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "colegio_texto_legacy" varchar(200) NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "sede_id" bigint NULL REFERENCES "usuarios_sede" ("id") DEFERRABLE INITIALLY DEFERRED, "conductor_perfil_id" bigint NULL REFERENCES "usuarios_perfilconductor" ("id") DEFERRABLE INITIALLY DEFERRED, "furgon_id" bigint NULL REFERENCES "usuarios_furgon" ("id") DEFERRABLE INITIALLY DEFERRED, "origen_direccion" varchar(255) NOT NULL, "destino_direccion" varchar(255) NOT NULL, "origen_latitud" decimal NULL, "origen_longitud" decimal NULL, "destino_latitud" decimal NULL, "destino_longitud" decimal NULL, "iniciada_en" datetime NULL, "finalizada_en" datetime NULL, "sentido" varchar(20) NOT NULL, "ultima_latitud" decimal NULL, "ultima_longitud" decimal NULL, "precision_gps_metros" decimal NULL, "ubicacion_actualizada_en" datetime NULL, "hora_programada" time NULL, "reparto_iniciado_en" datetime NULL, "origen_recalculo_latitud" real NULL, "origen_recalculo_longitud" real NULL, "simulacion_activa" bool NOT NULL, "activo" bool NOT NULL, "desactivado_en" datetime NULL);

-- Tabla: usuarios_aceptacionterminos
CREATE TABLE "usuarios_aceptacionterminos" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "colegio_nombre" varchar(200) NOT NULL, "nombre" varchar(300) NOT NULL, "email" varchar(254) NOT NULL, "version" varchar(20) NOT NULL, "huella_texto" varchar(64) NOT NULL, "acepta_biometria" bool NOT NULL, "origen" varchar(20) NOT NULL, "ip" char(39) NULL, "dispositivo" varchar(255) NOT NULL, "aceptado_en" datetime NOT NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "rut" varchar(12) NOT NULL, CONSTRAINT "aceptacion_unica_por_version" UNIQUE ("usuario_id", "version"));

-- Tabla: usuarios_eventorecorrido
CREATE TABLE "usuarios_eventorecorrido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tipo" varchar(20) NOT NULL, "estudiante_nombre" varchar(300) NOT NULL, "metodo" varchar(60) NOT NULL, "persona_nombre" varchar(200) NOT NULL, "persona_rol" varchar(60) NOT NULL, "detalle" text NOT NULL, "creado_en" datetime NOT NULL, "estudiante_id" bigint NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "recorrido_id" bigint NOT NULL REFERENCES "usuarios_recorridoruta" ("id") DEFERRABLE INITIALLY DEFERRED, "persona_rut" varchar(12) NOT NULL);

-- Tabla: usuarios_perfilapoderado
CREATE TABLE "usuarios_perfilapoderado" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "telefono" varchar(20) NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "usuario_id" bigint NOT NULL UNIQUE REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "foto" varchar(100) NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "rut" varchar(12) NULL UNIQUE);

-- Tabla: usuarios_perfilconductor
CREATE TABLE "usuarios_perfilconductor" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "telefono" varchar(20) NULL, "licencia_conducir" varchar(50) NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "usuario_id" bigint NOT NULL UNIQUE REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "rut" varchar(12) NULL UNIQUE);

-- Tabla: usuarios_perfildelegado
CREATE TABLE "usuarios_perfildelegado" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "telefono" varchar(20) NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "usuario_id" bigint NOT NULL UNIQUE REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "foto" varchar(100) NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "tipo_delegado" varchar(20) NOT NULL, "rut" varchar(12) NULL UNIQUE);

-- Tabla: usuarios_personaautorizada
CREATE TABLE "usuarios_personaautorizada" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(200) NOT NULL, "telefono" varchar(20) NOT NULL, "activa" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "apoderado_id" bigint NOT NULL REFERENCES "usuarios_perfilapoderado" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_id" bigint NOT NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "perfil_delegado_id" bigint NULL REFERENCES "usuarios_perfildelegado" ("id") DEFERRABLE INITIALLY DEFERRED, "rut" varchar(12) NOT NULL, CONSTRAINT "autorizado_unico_por_estudiante" UNIQUE ("estudiante_id", "rut"));

-- Tabla: usuarios_registroentrega
CREATE TABLE "usuarios_registroentrega" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tipo_receptor" varchar(30) NOT NULL, "receptor_nombre" varchar(200) NOT NULL, "metodo_validacion" varchar(20) NOT NULL, "destino" varchar(255) NOT NULL, "entregado_en" datetime NOT NULL, "conductor_id" bigint NOT NULL REFERENCES "usuarios_perfilconductor" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NOT NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "persona_autorizada_id" bigint NULL REFERENCES "usuarios_personaautorizada" ("id") DEFERRABLE INITIALLY DEFERRED, "perfil_delegado_id" bigint NULL REFERENCES "usuarios_perfildelegado" ("id") DEFERRABLE INITIALLY DEFERRED, "ruta_id" bigint NOT NULL REFERENCES "usuarios_ruta" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_id" bigint NOT NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "receptor_rut" varchar(12) NOT NULL);

-- Tabla: usuarios_ruthabilitado
CREATE TABLE "usuarios_ruthabilitado" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "usado_en" datetime NULL, "creado_en" datetime NOT NULL, "liberado_en" datetime NULL, "cuenta_liberada" varchar(320) NOT NULL, "apoderado_id" bigint NULL REFERENCES "usuarios_perfilapoderado" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_id" bigint NOT NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "creado_por_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "liberado_por_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "activo" bool NOT NULL, "desactivado_en" datetime NULL, "rut" varchar(12) NOT NULL, CONSTRAINT "rut_habilitado_unico_por_colegio" UNIQUE ("colegio_id", "rut"));

-- Tabla: usuarios_codigoqrentrega
CREATE TABLE "usuarios_codigoqrentrega" ("id" char(32) NOT NULL PRIMARY KEY, "expira_en" datetime NOT NULL, "usado_en" datetime NULL, "creado_en" datetime NOT NULL, "estudiante_id" bigint NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" bigint NOT NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "estatico" bool NOT NULL);

-- Tabla: usuarios_colegio
CREATE TABLE "usuarios_colegio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(200) NOT NULL UNIQUE, "rbd" varchar(50) NULL, "direccion" varchar(255) NULL, "telefono" varchar(50) NULL, "email_contacto" varchar(254) NULL, "activo" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "latitud" decimal NULL, "longitud" decimal NULL, "comuna" varchar(100) NOT NULL, "region" varchar(100) NOT NULL, "desactivado_en" datetime NULL, "plan" varchar(20) NOT NULL);

-- Tabla: usuarios_sede
CREATE TABLE "usuarios_sede" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "direccion" varchar(255) NULL, "telefono" varchar(50) NULL, "activa" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "colegio_id" bigint NOT NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "latitud" decimal NULL, "longitud" decimal NULL, "comuna" varchar(100) NOT NULL, "region" varchar(100) NOT NULL, "desactivado_en" datetime NULL, "es_principal" bool NOT NULL);

-- Tabla: usuarios_estudiantehabilitado
CREATE TABLE "usuarios_estudiantehabilitado" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "rut" varchar(12) NOT NULL, "rut_apoderado" varchar(12) NOT NULL, "usado_en" datetime NULL, "creado_en" datetime NOT NULL, "activo" bool NOT NULL, "desactivado_en" datetime NULL, "colegio_id" bigint NOT NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "creado_por_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_usuario
CREATE TABLE "usuarios_usuario" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "first_name" varchar(150) NOT NULL, "last_name" varchar(150) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "email" varchar(254) NOT NULL UNIQUE, "rol" varchar(30) NOT NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "debe_cambiar_password" bool NOT NULL, "terminos_version_aceptada" varchar(20) NOT NULL, "desactivado_en" datetime NULL, CONSTRAINT "admin_plataforma_sin_colegio" CHECK ((NOT ("rol" = 'admin_plataforma') OR "colegio_id" IS NULL)), CONSTRAINT "admin_colegio_con_colegio" CHECK ((NOT ("rol" = 'admin_colegio') OR "colegio_id" IS NOT NULL)));

-- Tabla: usuarios_cambiobiometria
CREATE TABLE "usuarios_cambiobiometria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "colegio_nombre" varchar(200) NOT NULL, "nombre" varchar(300) NOT NULL, "rut" varchar(12) NOT NULL, "email" varchar(254) NOT NULL, "autoriza" bool NOT NULL, "origen" varchar(20) NOT NULL, "fotos_eliminadas" integer unsigned NOT NULL CHECK ("fotos_eliminadas" >= 0), "ip" char(39) NULL, "dispositivo" varchar(255) NOT NULL, "creado_en" datetime NOT NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED);

-- Tabla: usuarios_estudiante
CREATE TABLE "usuarios_estudiante" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "apellido" varchar(150) NOT NULL, "rut" varchar(12) NOT NULL UNIQUE, "fecha_nacimiento" date NOT NULL, "curso" varchar(100) NOT NULL, "direccion_principal" varchar(255) NOT NULL, "direccion_alternativa" varchar(255) NULL, "persona_autorizada" varchar(200) NULL, "rut_persona_autorizada" varchar(12) NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "apoderado_id" bigint NOT NULL REFERENCES "usuarios_perfilapoderado" ("id") DEFERRABLE INITIALLY DEFERRED, "foto" varchar(100) NULL, "conductor_id" bigint NULL REFERENCES "usuarios_perfilconductor" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_texto_legacy" varchar(200) NULL, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "sede_id" bigint NULL REFERENCES "usuarios_sede" ("id") DEFERRABLE INITIALLY DEFERRED, "latitud" decimal NULL, "longitud" decimal NULL, "ubicacion_confirmada" bool NOT NULL, "embedding_facial_version" varchar(100) NULL, "comuna" varchar(100) NOT NULL, "region" varchar(100) NOT NULL, "embedding_facial" text NULL, "activo" bool NOT NULL, "desactivado_en" datetime NULL, "autoriza_biometria" bool NOT NULL, "autoriza_biometria_en" datetime NULL);

-- Tabla: usuarios_consentimientobiometrico
CREATE TABLE "usuarios_consentimientobiometrico" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "apoderado_nombre" varchar(300) NOT NULL, "apoderado_rut" varchar(12) NOT NULL, "apoderado_email" varchar(254) NOT NULL, "estudiante_nombre" varchar(300) NOT NULL, "estudiante_rut" varchar(12) NOT NULL, "colegio_nombre" varchar(200) NOT NULL, "evento" varchar(10) NOT NULL, "origen" varchar(20) NOT NULL, "version_terminos" varchar(20) NOT NULL, "datos_eliminados" bool NOT NULL, "ip" char(39) NULL, "dispositivo" varchar(255) NOT NULL, "creado_en" datetime NOT NULL, "apoderado_id" bigint NULL REFERENCES "usuarios_usuario" ("id") DEFERRABLE INITIALLY DEFERRED, "colegio_id" bigint NULL REFERENCES "usuarios_colegio" ("id") DEFERRABLE INITIALLY DEFERRED, "estudiante_id" bigint NULL REFERENCES "usuarios_estudiante" ("id") DEFERRABLE INITIALLY DEFERRED);

-- =====================================================================
-- Índices
-- =====================================================================

CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id");
CREATE UNIQUE INDEX "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id");
CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id");
CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id");
CREATE UNIQUE INDEX "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename");
CREATE INDEX "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log" ("content_type_id");
CREATE INDEX "django_admin_log_user_id_c564eba6" ON "django_admin_log" ("user_id");
CREATE UNIQUE INDEX "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model");
CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session" ("expire_date");
CREATE INDEX "usuarios_aceptacionterminos_colegio_id_735ecbc7" ON "usuarios_aceptacionterminos" ("colegio_id");
CREATE INDEX "usuarios_aceptacionterminos_usuario_id_afda1c90" ON "usuarios_aceptacionterminos" ("usuario_id");
CREATE INDEX "usuarios_cambiobiometria_colegio_id_b93e3c1f" ON "usuarios_cambiobiometria" ("colegio_id");
CREATE INDEX "usuarios_cambiobiometria_usuario_id_69c87a02" ON "usuarios_cambiobiometria" ("usuario_id");
CREATE INDEX "usuarios_codigoqrentrega_estudiante_id_fd8c698c" ON "usuarios_codigoqrentrega" ("estudiante_id");
CREATE INDEX "usuarios_codigoqrentrega_usuario_id_828d0dc5" ON "usuarios_codigoqrentrega" ("usuario_id");
CREATE INDEX "usuarios_codigorecuperacion_usuario_id_4f3ab418" ON "usuarios_codigorecuperacion" ("usuario_id");
CREATE INDEX "usuarios_consentimientobiometrico_apoderado_id_b29dc118" ON "usuarios_consentimientobiometrico" ("apoderado_id");
CREATE INDEX "usuarios_consentimientobiometrico_colegio_id_112a6e4c" ON "usuarios_consentimientobiometrico" ("colegio_id");
CREATE INDEX "usuarios_consentimientobiometrico_estudiante_id_216a1611" ON "usuarios_consentimientobiometrico" ("estudiante_id");
CREATE INDEX "usuarios_delegadosede_delegado_id_f858b52d" ON "usuarios_delegadosede" ("delegado_id");
CREATE INDEX "usuarios_delegadosede_sede_id_dbbbadd4" ON "usuarios_delegadosede" ("sede_id");
CREATE INDEX "usuarios_emergencia_colegio_id_75c3f5e8" ON "usuarios_emergencia" ("colegio_id");
CREATE INDEX "usuarios_emergencia_conductor_id_5ace7034" ON "usuarios_emergencia" ("conductor_id");
CREATE INDEX "usuarios_emergencia_estudiante_id_8ff65669" ON "usuarios_emergencia" ("estudiante_id");
CREATE INDEX "usuarios_emergencia_furgon_id_f524a726" ON "usuarios_emergencia" ("furgon_id");
CREATE INDEX "usuarios_emergencia_ruta_id_0e07f90a" ON "usuarios_emergencia" ("ruta_id");
CREATE INDEX "usuarios_estudiante_apoderado_id_1888f8dd" ON "usuarios_estudiante" ("apoderado_id");
CREATE INDEX "usuarios_estudiante_colegio_id_c50db8a4" ON "usuarios_estudiante" ("colegio_id");
CREATE INDEX "usuarios_estudiante_conductor_id_a16354aa" ON "usuarios_estudiante" ("conductor_id");
CREATE INDEX "usuarios_estudiante_sede_id_1f1de055" ON "usuarios_estudiante" ("sede_id");
CREATE UNIQUE INDEX "estudiante_habilitado_en_un_solo_colegio" ON "usuarios_estudiantehabilitado" ("rut") WHERE "activo" = 1;
CREATE INDEX "usuarios_estudiantehabilitado_colegio_id_fc365d92" ON "usuarios_estudiantehabilitado" ("colegio_id");
CREATE INDEX "usuarios_estudiantehabilitado_creado_por_id_9ef3c765" ON "usuarios_estudiantehabilitado" ("creado_por_id");
CREATE INDEX "usuarios_estudiantehabilitado_estudiante_id_fcae6361" ON "usuarios_estudiantehabilitado" ("estudiante_id");
CREATE INDEX "usuarios_eventorecorrido_estudiante_id_cf1ed898" ON "usuarios_eventorecorrido" ("estudiante_id");
CREATE INDEX "usuarios_eventorecorrido_recorrido_id_c3aaab17" ON "usuarios_eventorecorrido" ("recorrido_id");
CREATE INDEX "usuarios_fcmtoken_usuario_id_2ec9bac2" ON "usuarios_fcmtoken" ("usuario_id");
CREATE INDEX "usuarios_furgon_colegio_id_e6ddb898" ON "usuarios_furgon" ("colegio_id");
CREATE INDEX "usuarios_furgon_sede_id_357693e1" ON "usuarios_furgon" ("sede_id");
CREATE INDEX "usuarios_inasistenciaestudiante_creado_por_id_e0ec89f5" ON "usuarios_inasistenciaestudiante" ("creado_por_id");
CREATE INDEX "usuarios_inasistenciaestudiante_estudiante_id_ed8846c8" ON "usuarios_inasistenciaestudiante" ("estudiante_id");
CREATE INDEX "usuarios_notificacion_apoderado_id_92986ac4" ON "usuarios_notificacion" ("apoderado_id");
CREATE INDEX "usuarios_notificacion_destinatario_id_2fd04e0c" ON "usuarios_notificacion" ("destinatario_id");
CREATE INDEX "usuarios_notificacion_estudiante_id_deac89b1" ON "usuarios_notificacion" ("estudiante_id");
CREATE INDEX "usuarios_perfilapoderado_colegio_id_0d167e4f" ON "usuarios_perfilapoderado" ("colegio_id");
CREATE INDEX "usuarios_perfilconductor_colegio_id_594f63f1" ON "usuarios_perfilconductor" ("colegio_id");
CREATE INDEX "usuarios_perfildelegado_colegio_id_24cfa11b" ON "usuarios_perfildelegado" ("colegio_id");
CREATE INDEX "usuarios_personaautorizada_apoderado_id_8e32322a" ON "usuarios_personaautorizada" ("apoderado_id");
CREATE INDEX "usuarios_personaautorizada_colegio_id_2a45599c" ON "usuarios_personaautorizada" ("colegio_id");
CREATE INDEX "usuarios_personaautorizada_estudiante_id_2f09b8f8" ON "usuarios_personaautorizada" ("estudiante_id");
CREATE INDEX "usuarios_personaautorizada_perfil_delegado_id_ce0ee396" ON "usuarios_personaautorizada" ("perfil_delegado_id");
CREATE INDEX "usuarios_recorridoruta_colegio_id_75f99f88" ON "usuarios_recorridoruta" ("colegio_id");
CREATE INDEX "usuarios_recorridoruta_ruta_id_a25f40f8" ON "usuarios_recorridoruta" ("ruta_id");
CREATE INDEX "usuarios_registroabordaje_colegio_id_34f17a59" ON "usuarios_registroabordaje" ("colegio_id");
CREATE INDEX "usuarios_registroabordaje_conductor_id_a247515b" ON "usuarios_registroabordaje" ("conductor_id");
CREATE INDEX "usuarios_registroabordaje_delegado_id_70b5a60d" ON "usuarios_registroabordaje" ("delegado_id");
CREATE INDEX "usuarios_registroabordaje_estudiante_id_40050819" ON "usuarios_registroabordaje" ("estudiante_id");
CREATE INDEX "usuarios_registroabordaje_ruta_id_51914410" ON "usuarios_registroabordaje" ("ruta_id");
CREATE INDEX "usuarios_registroentrega_colegio_id_46edd2ed" ON "usuarios_registroentrega" ("colegio_id");
CREATE INDEX "usuarios_registroentrega_conductor_id_b51a40cb" ON "usuarios_registroentrega" ("conductor_id");
CREATE INDEX "usuarios_registroentrega_estudiante_id_179326a5" ON "usuarios_registroentrega" ("estudiante_id");
CREATE INDEX "usuarios_registroentrega_perfil_delegado_id_b21a182e" ON "usuarios_registroentrega" ("perfil_delegado_id");
CREATE INDEX "usuarios_registroentrega_persona_autorizada_id_9d737057" ON "usuarios_registroentrega" ("persona_autorizada_id");
CREATE INDEX "usuarios_registroentrega_ruta_id_289befa3" ON "usuarios_registroentrega" ("ruta_id");
CREATE INDEX "usuarios_ruta_colegio_id_4c369f10" ON "usuarios_ruta" ("colegio_id");
CREATE INDEX "usuarios_ruta_conductor_perfil_id_6acb173b" ON "usuarios_ruta" ("conductor_perfil_id");
CREATE INDEX "usuarios_ruta_furgon_id_3e3bc0a9" ON "usuarios_ruta" ("furgon_id");
CREATE INDEX "usuarios_ruta_sede_id_2f2f4305" ON "usuarios_ruta" ("sede_id");
CREATE INDEX "usuarios_ruta_estudiantes_estudiante_id_672870c4" ON "usuarios_ruta_estudiantes" ("estudiante_id");
CREATE UNIQUE INDEX "usuarios_ruta_estudiantes_ruta_id_estudiante_id_2301b538_uniq" ON "usuarios_ruta_estudiantes" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_ruta_id_f97e77ea" ON "usuarios_ruta_estudiantes" ("ruta_id");
CREATE INDEX "usuarios_ruta_estudiantes_abordados_estudiante_id_15747616" ON "usuarios_ruta_estudiantes_abordados" ("estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_abordados_ruta_id_b15fb3ce" ON "usuarios_ruta_estudiantes_abordados" ("ruta_id");
CREATE UNIQUE INDEX "usuarios_ruta_estudiantes_abordados_ruta_id_estudiante_id_fb2f5152_uniq" ON "usuarios_ruta_estudiantes_abordados" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_ausentes_estudiante_id_29a14ae4" ON "usuarios_ruta_estudiantes_ausentes" ("estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_ausentes_ruta_id_d65289de" ON "usuarios_ruta_estudiantes_ausentes" ("ruta_id");
CREATE UNIQUE INDEX "usuarios_ruta_estudiantes_ausentes_ruta_id_estudiante_id_d38e45fb_uniq" ON "usuarios_ruta_estudiantes_ausentes" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_entregados_estudiante_id_05ebf7b2" ON "usuarios_ruta_estudiantes_entregados" ("estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_entregados_ruta_id_5d36b47d" ON "usuarios_ruta_estudiantes_entregados" ("ruta_id");
CREATE UNIQUE INDEX "usuarios_ruta_estudiantes_entregados_ruta_id_estudiante_id_ff9b991d_uniq" ON "usuarios_ruta_estudiantes_entregados" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_llamados_estudiante_id_f96d8dbf" ON "usuarios_ruta_estudiantes_llamados" ("estudiante_id");
CREATE UNIQUE INDEX "usuarios_ruta_estudiantes_llamados_ruta_id_estudiante_id_f60ca019_uniq" ON "usuarios_ruta_estudiantes_llamados" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_llamados_ruta_id_f1cea76b" ON "usuarios_ruta_estudiantes_llamados" ("ruta_id");
CREATE INDEX "usuarios_ruta_estudiantes_no_recibidos_estudiante_id_6cfd5a8e" ON "usuarios_ruta_estudiantes_no_recibidos" ("estudiante_id");
CREATE INDEX "usuarios_ruta_estudiantes_no_recibidos_ruta_id_0321b56a" ON "usuarios_ruta_estudiantes_no_recibidos" ("ruta_id");
CREATE UNIQUE INDEX "usuarios_ruta_estudiantes_no_recibidos_ruta_id_estudiante_id_034a8cd2_uniq" ON "usuarios_ruta_estudiantes_no_recibidos" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruta_paradas_completadas_estudiante_id_e4224c59" ON "usuarios_ruta_paradas_completadas" ("estudiante_id");
CREATE INDEX "usuarios_ruta_paradas_completadas_ruta_id_3ef1c8fc" ON "usuarios_ruta_paradas_completadas" ("ruta_id");
CREATE UNIQUE INDEX "usuarios_ruta_paradas_completadas_ruta_id_estudiante_id_62c19e0a_uniq" ON "usuarios_ruta_paradas_completadas" ("ruta_id", "estudiante_id");
CREATE INDEX "usuarios_ruthabilitado_apoderado_id_4c0d2642" ON "usuarios_ruthabilitado" ("apoderado_id");
CREATE INDEX "usuarios_ruthabilitado_colegio_id_a80ffde7" ON "usuarios_ruthabilitado" ("colegio_id");
CREATE INDEX "usuarios_ruthabilitado_creado_por_id_a24f6c91" ON "usuarios_ruthabilitado" ("creado_por_id");
CREATE INDEX "usuarios_ruthabilitado_liberado_por_id_c817e841" ON "usuarios_ruthabilitado" ("liberado_por_id");
CREATE UNIQUE INDEX "una_sede_principal_por_colegio" ON "usuarios_sede" ("colegio_id") WHERE "es_principal" = 1;
CREATE INDEX "usuarios_sede_colegio_id_c4e90f4a" ON "usuarios_sede" ("colegio_id");
CREATE INDEX "usuarios_usuario_colegio_id_980bfe51" ON "usuarios_usuario" ("colegio_id");
CREATE INDEX "usuarios_usuario_groups_group_id_e77f6dcf" ON "usuarios_usuario_groups" ("group_id");
CREATE INDEX "usuarios_usuario_groups_usuario_id_7a34077f" ON "usuarios_usuario_groups" ("usuario_id");
CREATE UNIQUE INDEX "usuarios_usuario_groups_usuario_id_group_id_4ed5b09e_uniq" ON "usuarios_usuario_groups" ("usuario_id", "group_id");
CREATE INDEX "usuarios_usuario_user_permissions_permission_id_4e5c0f2f" ON "usuarios_usuario_user_permissions" ("permission_id");
CREATE INDEX "usuarios_usuario_user_permissions_usuario_id_60aeea80" ON "usuarios_usuario_user_permissions" ("usuario_id");
CREATE UNIQUE INDEX "usuarios_usuario_user_permissions_usuario_id_permission_id_217cadcd_uniq" ON "usuarios_usuario_user_permissions" ("usuario_id", "permission_id");

-- =====================================================================
-- Registro de migraciones aplicadas (para que Django reconozca la base)
-- =====================================================================

INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('contenttypes', '0001_initial', '2026-11-27 21:08:43.711704');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('contenttypes', '0002_remove_content_type_name', '2026-11-27 21:08:43.725098');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0001_initial', '2026-11-27 21:08:43.743063');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0002_alter_permission_name_max_length', '2026-11-27 21:08:43.755234');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0003_alter_user_email_max_length', '2026-11-27 21:08:43.763032');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0004_alter_user_username_opts', '2026-11-27 21:08:43.773007');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0005_alter_user_last_login_null', '2026-11-27 21:08:43.780427');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0006_require_contenttypes_0002', '2026-11-27 21:08:43.787000');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0007_alter_validators_add_error_messages', '2026-11-27 21:08:43.795673');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0008_alter_user_username_max_length', '2026-11-27 21:08:43.803679');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0009_alter_user_last_name_max_length', '2026-11-27 21:08:43.810724');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0010_alter_group_name_max_length', '2026-11-27 21:08:43.821185');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0011_update_proxy_permissions', '2026-11-27 21:08:43.832143');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('auth', '0012_alter_user_first_name_max_length', '2026-11-27 21:08:43.840249');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0001_initial', '2026-11-27 21:08:43.862705');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('admin', '0001_initial', '2026-11-27 21:08:43.884936');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('admin', '0002_logentry_remove_auto_add', '2026-11-27 21:08:43.902309');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('admin', '0003_logentry_add_action_flag_choices', '2026-11-27 21:08:43.912114');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('authtoken', '0001_initial', '2026-11-27 21:08:43.928050');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('authtoken', '0002_auto_20160226_1747', '2026-11-27 21:08:43.966971');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('authtoken', '0003_tokenproxy', '2026-11-27 21:08:43.973637');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('authtoken', '0004_alter_tokenproxy_options', '2026-11-27 21:08:43.984146');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('sessions', '0001_initial', '2026-11-27 21:08:43.995849');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0002_estudiante', '2026-11-27 21:08:44.018786');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0003_estudiante_foto', '2026-11-27 21:08:44.030583');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0004_codigorecuperacion', '2026-11-27 21:08:44.048974');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0005_perfilconductor', '2026-11-27 21:08:44.067560');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0006_fcmtoken_notificacion', '2026-11-27 21:08:44.100859');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0007_estudiante_conductor', '2026-11-27 21:08:44.122234');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0008_furgon_ruta', '2026-11-27 21:08:44.132535');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0009_alter_usuario_rol_perfildelegado', '2026-11-27 21:08:44.163097');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0010_estudiante_embedding_facial_and_more', '2026-11-27 21:08:44.321389');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0011_emergencia', '2026-11-27 21:08:44.349313');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0012_colegio_estudiante_colegio_texto_legacy_and_more', '2026-11-27 21:08:44.701881');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0013_migrar_datos_colegios', '2026-11-27 21:08:44.735790');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0014_ruta_gestion_operativa', '2026-11-27 21:08:44.972159');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0015_sede_ubicacion_ruta_sentido', '2026-11-27 21:08:45.057928');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0016_hash_legacy_plaintext_passwords', '2026-11-27 21:08:45.080145');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0017_mark_empty_passwords_unusable', '2026-11-27 21:08:45.107074');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0018_usuario_admin_colegio_constraints', '2026-11-27 21:08:45.165012');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0019_codigoqrentrega', '2026-11-27 21:08:45.192663');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0020_delegadosede', '2026-11-27 21:08:45.287218');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0021_perfildelegado_tipo_delegado', '2026-11-27 21:08:45.341137');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0022_ruta_estudiantes_abordados', '2026-11-27 21:08:45.372943');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0023_estudiante_ubicacion_confirmada', '2026-11-27 21:08:45.426058');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0024_colegio_ubicacion', '2026-11-27 21:08:45.454490');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0025_ruta_paradas_completadas', '2026-11-27 21:08:45.486138');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0026_ruta_ubicacion_gps', '2026-11-27 21:08:45.560079');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0027_version_embedding_facial', '2026-11-27 21:08:45.633261');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0028_sincronizar_conductor_desde_rutas', '2026-11-27 21:08:45.667162');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0029_direccion_comuna_region', '2026-11-27 21:08:45.815791');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0030_ruta_estudiantes_ausentes', '2026-11-27 21:08:45.869815');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0031_ruta_estudiantes_entregados', '2026-11-27 21:08:45.903928');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0032_inasistencia_estudiante', '2026-11-27 21:08:45.934895');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0033_emergencia_contexto_operacional', '2026-11-27 21:08:46.142140');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0034_personas_autorizadas_registro_entrega', '2026-11-27 21:08:46.319734');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0035_notificacion_destinatario', '2026-11-27 21:08:46.450385');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0036_registroentrega_colegio', '2026-11-27 21:08:46.601982');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0037_contrato', '2026-11-27 21:08:46.688126');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0038_registroabordaje', '2026-11-27 21:08:46.733070');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0039_historial_por_recorrido', '2026-11-27 21:08:46.810799');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0040_entrega_con_rostro_estudiante', '2026-11-27 21:08:46.936799');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0041_auditoria_recorridos', '2026-11-27 21:08:47.049837');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0042_debe_cambiar_password', '2026-11-27 21:08:47.103698');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0043_reparto_vuelta', '2026-11-27 21:08:47.174948');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0044_no_recibido_vuelta', '2026-11-27 21:08:47.295106');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0045_origen_recalculo', '2026-11-27 21:08:47.379755');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0046_ruts_habilitados_y_terminos', '2026-11-27 21:08:47.532036');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0047_apoderados_actuales_rut_habilitado', '2026-11-27 21:08:47.584426');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0048_cifrar_embedding_estudiante', '2026-11-27 21:08:48.009999');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0049_simulador_de_ruta', '2026-11-27 21:08:48.103887');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0050_cifrar_fotos_estudiantes', '2026-11-27 21:08:48.196809');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0051_inspector_una_sede', '2026-11-27 21:08:48.299053');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0052_papelera', '2026-11-27 21:08:48.670599');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0053_rut_formato_unico', '2026-11-27 21:08:49.171849');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0054_qr_estatico_demo', '2026-11-27 21:08:49.221741');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0055_planes_y_sede_principal', '2026-11-27 21:08:49.357354');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0056_estudiantes_habilitados', '2026-11-27 21:08:49.413125');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0057_autoriza_biometria', '2026-11-27 21:08:49.610296');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0058_historial_biometria', '2026-11-27 21:08:49.654704');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0059_normalizar_nombres', '2026-11-27 21:08:49.695221');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0060_eliminar_contratos', '2026-11-27 21:08:49.730475');
INSERT INTO "django_migrations" ("app", "name", "applied") VALUES ('usuarios', '0061_biometria_por_hijo', '2026-11-27 21:08:50.033933');

COMMIT;
