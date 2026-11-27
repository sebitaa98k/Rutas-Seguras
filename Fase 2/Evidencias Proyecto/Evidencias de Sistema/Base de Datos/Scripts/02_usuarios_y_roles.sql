-- =====================================================================
-- Rutas Seguras - Usuarios y roles
-- Motor: SQLite 3
-- Generado el 27/11/2026. Ejecutar después de 01_creacion_tablas.sql.
--
-- SQLite no tiene usuarios ni permisos a nivel de motor (no existe
-- CREATE USER ni GRANT). El control de acceso lo hace la aplicación:
-- cada persona es una fila de la tabla usuarios_usuario y su columna
-- "rol" define qué puede hacer en el sistema.
--
-- Roles del sistema (columna usuarios_usuario.rol):
--   admin_plataforma   Administrador de Plataforma
--   admin_colegio      Administrador de Colegio
--   apoderado          Apoderado
--   conductor          Conductor
--   admin              Administrador (antiguo)
--   delegado           Delegado (inspector o persona autorizada)
--
-- Reglas de la base para los roles:
--   - El administrador de plataforma no pertenece a ningún colegio
--     (restricción admin_plataforma_sin_colegio).
--   - Los demás roles se asocian a un colegio (columna colegio_id) y,
--     según el rol, a un perfil: usuarios_perfilapoderado,
--     usuarios_perfilconductor o usuarios_perfildelegado.
--
-- Cuenta inicial: administrador de plataforma (también superusuario de Django)
--   Correo:      admin@rutasseguras.cl
--   Contraseña:  Capstone26   (se guarda cifrada con PBKDF2-SHA256)
-- =====================================================================

PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

INSERT INTO "usuarios_usuario" ("id", "password", "last_login", "is_superuser", "username", "first_name", "last_name", "is_staff", "is_active", "date_joined", "email", "rol", "colegio_id", "debe_cambiar_password", "terminos_version_aceptada", "desactivado_en") VALUES (1, 'pbkdf2_sha256$1500000$NVXvoYTSYuGkvXvLCtlmRx$4Ya2pxgggPvIsS4Ufg+QIpBNn8iPHO9G9OF5grB+7ZA=', NULL, 1, 'AdminRutas', 'Admin', 'Rutas', 1, 1, '2026-11-18 20:45:33.885023', 'admin@rutasseguras.cl', 'admin_plataforma', NULL, 0, '', NULL);

COMMIT;
