#!/bin/sh
set -eu
# Runs only on first initialization of a new Postgres volume.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v grafana_password="$GRAFANA_DB_PASSWORD" -v db_name="$POSTGRES_DB" <<'SQL'
CREATE ROLE grafana_reader LOGIN PASSWORD :'grafana_password';
GRANT CONNECT ON DATABASE :"db_name" TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;
SQL
