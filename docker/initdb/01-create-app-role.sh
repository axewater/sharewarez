#!/bin/bash
# Creates the application's database role on FIRST initialisation of the data
# volume. The postgres image runs everything in /docker-entrypoint-initdb.d/
# once, when PGDATA is empty, so this never touches an existing install.
#
# WHY: the app used to connect as the `postgres` superuser, which holds rights
# over every database in the cluster and can run shell commands on the database
# host via COPY..TO PROGRAM — to do one app's CRUD. It now connects as a role
# that owns this one database and can do nothing else. That only works if the
# role actually exists, which is what this script is for: without it a fresh
# install fails with `role "sharewarez_app" does not exist`.
set -e

if [ -z "${APP_DB_USER:-}" ] || [ -z "${APP_DB_PASSWORD:-}" ]; then
  echo "FATAL: APP_DB_USER and APP_DB_PASSWORD must be set (see .env.docker.example)." >&2
  exit 1
fi
if [ "$APP_DB_PASSWORD" = "change-me-to-a-long-random-string" ]; then
  echo "FATAL: APP_DB_PASSWORD is still the example value. Set a real one in .env." >&2
  exit 1
fi

# :"ident" quotes an identifier and :'literal' quotes a string, so neither the
# name nor the password is pasted into SQL text — a password containing a quote
# is a config choice, not a syntax error.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_user="$APP_DB_USER" -v app_pass="$APP_DB_PASSWORD" -v db_name="$POSTGRES_DB" <<-'EOSQL'
	CREATE ROLE :"app_user" LOGIN PASSWORD :'app_pass'
	  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

	-- Owning its own database is what lets db.create_all() and updateschema.py's
	-- ALTER TABLE / CREATE INDEX work: those check ownership, so DML grants alone
	-- would leave a startup path that fails on a healthy system. It is still not a
	-- superuser, and it can reach no other database.
	ALTER DATABASE :"db_name" OWNER TO :"app_user";

	-- A database anyone may connect to is not scoped by its grants.
	REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
	GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
EOSQL

echo "Created least-privilege role '$APP_DB_USER' and gave it ownership of '$POSTGRES_DB'."
