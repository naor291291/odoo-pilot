"""Staxa DB environment adapter. Never print credentials or put them in argv."""
import configparser
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit


class ConfigurationError(ValueError):
    pass


def clean(value):
    if not value or any(c in value for c in '\r\n\x00'):
        raise ConfigurationError('Missing or unsafe configuration value')
    return value


def settings(env):
    keys = ('DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME')
    present = [bool(env.get(k)) for k in keys]
    sslmode = env.get('DB_SSLMODE', 'require')
    if all(present):
        host, port, user, password, database = (clean(env[k]) for k in keys)
    elif any(present):
        # Never silently combine credentials for different databases.
        raise ConfigurationError('Set all five DB_* variables or DATABASE_URL alone')
    else:
        try:
            url = urlsplit(clean(env.get('DATABASE_URL', '')))
            if url.scheme not in ('postgres', 'postgresql') or url.fragment:
                raise ValueError()
            host, port = url.hostname, str(url.port or 5432)
            user, password = unquote(url.username or ''), unquote(url.password or '')
            database = unquote(url.path.removeprefix('/'))
            query = parse_qs(url.query)
            if set(query) - {'sslmode'} or any(len(v) != 1 for v in query.values()):
                raise ValueError()
            sslmode = env.get('DB_SSLMODE', query.get('sslmode', ['require'])[0])
        except (ValueError, TypeError):
            raise ConfigurationError('Invalid PostgreSQL connection URL') from None
        host, user, password, database = map(clean, (host, user, password, database))
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ConfigurationError('Invalid DB_PORT')
    if user == 'postgres':
        raise ConfigurationError('Odoo needs a dedicated non-postgres database role')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', database):
        raise ConfigurationError('Unsupported DB_NAME')
    if sslmode not in ('require', 'verify-ca', 'verify-full', 'disable'):
        raise ConfigurationError('Unsupported DB_SSLMODE')
    master = clean(env.get('ODOO_ADMIN_PASSWORD', ''))
    if len(master) < 32:
        raise ConfigurationError('ODOO_ADMIN_PASSWORD must contain at least 32 characters')
    mode = env.get('STAXA_ODOO_MODE', 'serve')
    if mode not in ('serve', 'init'):
        raise ConfigurationError('STAXA_ODOO_MODE must be serve or init')
    if env.get('PORT', '8069') != '8069':
        raise ConfigurationError('Configure the Staxa application port as 8069')
    config = {
        'db_host': host, 'db_port': port, 'db_user': user, 'db_password': password,
        'db_name': database, 'dbfilter': '^' + re.escape(database) + '$',
        'db_sslmode': sslmode, 'admin_passwd': master,
        'addons_path': '/mnt/extra-addons', 'data_dir': '/var/lib/odoo',
        'http_interface': '0.0.0.0', 'http_port': '8069', 'proxy_mode': 'True',
        'list_db': 'False', 'server_wide_modules': 'base,web',
        'workers': '0', 'max_cron_threads': '0', 'db_maxconn': '8',
        'log_handler': ':INFO,werkzeug:WARNING',
    }
    return config, mode


def write_config(config, directory=None):
    # mkstemp creates a new private 0600 file; no predictable secret-file path.
    fd, name = tempfile.mkstemp(prefix='staxa-odoo-', suffix='.conf', dir=directory)
    with os.fdopen(fd, 'w') as stream:
        parser = configparser.RawConfigParser()
        parser['options'] = config
        parser.write(stream)
    return name


def launch(env):
    config, mode = settings(env)
    path = write_config(config)
    child_env = dict(env)
    for key in ('DB_PASSWORD', 'DATABASE_URL', 'ODOO_ADMIN_PASSWORD'):
        child_env.pop(key, None)
    # Synthetic pilot only: no transport or automatic business actions.
    child_env.update(FIELD_WORK_EMAIL_MODE='off', FIELD_WORK_WHATSAPP_MODE='off',
                     FIELD_WORK_WHATSAPP_INBOUND='0', FIELD_WORK_AUTO_STAGES='0')
    command = ['odoo', '--config', path]
    if mode == 'init':
        command += ['--init', 'field_work_photos', '--without-demo=all', '--stop-after-init', '--no-http']
    return command, child_env


def main():
    try:
        if len(sys.argv) != 1:
            raise ConfigurationError('Configure startup via environment; extra arguments are not accepted')
        command, env = launch(os.environ)
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    os.execvpe(command[0], command, env)


if __name__ == '__main__':
    sys.exit(main())
