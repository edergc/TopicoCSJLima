-- =============================================================================
--  Tópico CSJ Lima — Bootstrap de PostgreSQL (ejecución única por base de datos)
--
--  Ejecutar con un SUPERUSUARIO (normalmente "postgres") mediante psql >= 15.
--  Lo invoca bootstrap.ps1, pero también puede ejecutarse manualmente:
--
--    export TOPICO_OWNER_PASSWORD='...'  TOPICO_APP_PASSWORD='...'
--    psql -h localhost -U postgres -d postgres -v db_name=topico_csj -f bootstrap.sql
--
--  Es idempotente: puede re-ejecutarse (actualiza contraseñas y privilegios).
--
--  Roles:
--    topico_owner     Propietario del esquema. Ejecuta migraciones y backups.
--    topico_app       Rol de la aplicación. Solo DML mínimo (otorgado por migraciones).
--    topico_readonly  Rol de grupo (NOLOGIN) de solo lectura para reportes/BI.
--                     Para usarlo: CREATE ROLE x LOGIN ...; GRANT topico_readonly TO x;
-- =============================================================================

\set ON_ERROR_STOP on
\getenv owner_password TOPICO_OWNER_PASSWORD
\getenv app_password TOPICO_APP_PASSWORD

\if :{?db_name}
\else
  \echo 'ERROR: falta la variable db_name (-v db_name=...)'
  \quit
\endif
\if :{?owner_password}
\else
  \echo 'ERROR: falta la variable de entorno TOPICO_OWNER_PASSWORD'
  \quit
\endif
\if :{?app_password}
\else
  \echo 'ERROR: falta la variable de entorno TOPICO_APP_PASSWORD'
  \quit
\endif

-- ---------------------------------------------------------------------------
-- 1. Roles (a nivel de clúster)
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE topico_owner LOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'topico_owner') \gexec
SELECT 'CREATE ROLE topico_app LOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'topico_app') \gexec
SELECT 'CREATE ROLE topico_readonly NOLOGIN'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'topico_readonly') \gexec

ALTER ROLE topico_owner WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD :'owner_password';
ALTER ROLE topico_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    CONNECTION LIMIT 60 PASSWORD :'app_password';
ALTER ROLE topico_readonly WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;

-- ---------------------------------------------------------------------------
-- 2. Base de datos
-- ---------------------------------------------------------------------------
SELECT format('CREATE DATABASE %I OWNER topico_owner ENCODING %L TEMPLATE template0',
              :'db_name', 'UTF8')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec

ALTER DATABASE :"db_name" OWNER TO topico_owner;
-- Todos los instantes se almacenan en UTC; la conversión a America/Lima la hace la aplicación.
ALTER DATABASE :"db_name" SET timezone TO 'UTC';
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO topico_app, topico_readonly;
ALTER ROLE topico_owner IN DATABASE :"db_name" SET search_path TO topico, public;
ALTER ROLE topico_app   IN DATABASE :"db_name" SET search_path TO topico, public;

-- ---------------------------------------------------------------------------
-- 3. Dentro de la base: extensiones y esquema
-- ---------------------------------------------------------------------------
\connect :"db_name"

-- btree_gist: restricciones de exclusión (vigencias sin solapamiento).
-- pg_trgm:    búsqueda rápida por nombre de trabajador.
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm    WITH SCHEMA public;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA IF NOT EXISTS topico AUTHORIZATION topico_owner;
ALTER SCHEMA topico OWNER TO topico_owner;
GRANT USAGE ON SCHEMA topico TO topico_app, topico_readonly;

\echo 'Bootstrap completado para la base de datos' :"db_name"
