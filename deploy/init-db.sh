#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username postgres <<'SQL'
\getenv odoo_password ODOO_DB_PASSWORD
CREATE ROLE odoo LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'odoo_password';
CREATE DATABASE field_crm OWNER odoo;
SQL
