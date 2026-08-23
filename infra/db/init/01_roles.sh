#!/bin/bash
# Creates the two database identities Slice 0 relies on.
#
# app_owner  owns the tables and is used ONLY by the one-shot seeder.
# app_ro     is what the API connects as. It holds CONNECT + USAGE + SELECT and
#            nothing else, so a write is refused by PostgreSQL rather than by a
#            convention any code path could opt out of.
#
# Runs once, as superuser, when the data volume is empty (docker-entrypoint-initdb.d).
# The postgres entrypoint already runs with `set -e`, and ON_ERROR_STOP aborts
# initialisation if any statement fails, so a half-configured database can never
# come up looking healthy.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
CREATE ROLE "${APP_OWNER_USER}" LOGIN PASSWORD '${APP_OWNER_PASSWORD}';
CREATE ROLE "${APP_RO_USER}" LOGIN PASSWORD '${APP_RO_PASSWORD}';

GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO "${APP_OWNER_USER}", "${APP_RO_USER}";

-- Only the owner may create objects; the API role may look inside the schema but
-- cannot add to it.
GRANT USAGE, CREATE ON SCHEMA public TO "${APP_OWNER_USER}";
GRANT USAGE ON SCHEMA public TO "${APP_RO_USER}";

-- Any table the owner creates from now on is readable by the API role automatically,
-- so Slice 1 tables do not need this file to be revisited.
ALTER DEFAULT PRIVILEGES FOR ROLE "${APP_OWNER_USER}" IN SCHEMA public
    GRANT SELECT ON TABLES TO "${APP_RO_USER}";
EOSQL
