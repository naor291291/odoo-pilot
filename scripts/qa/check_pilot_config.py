"""Validate resolved synthetic Compose JSON without printing any environment values."""
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text())
services = config['services']
app = services['odoo']
assert set(app['networks']) == {'database'}, 'Odoo must have only the internal network'
assert config['networks']['database']['internal'] is True
assert not app.get('ports') and not services['db'].get('ports')
assert set(services['proxy']['networks']) == {'database', 'edge'}
for key in ('FIELD_WORK_EMAIL_MODE', 'FIELD_WORK_WHATSAPP_MODE'):
    assert app['environment'][key] == 'off'
for key in ('FIELD_WORK_WHATSAPP_INBOUND', 'FIELD_WORK_AUTO_STAGES'):
    assert str(app['environment'][key]) == '0'
for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    assert not app['environment'].get(key)
for service, target in [('odoo','/var/lib/odoo'),('db','/var/lib/postgresql/data')]:
    assert any(v['type']=='volume' and v['target']==target for v in services[service]['volumes'])
    assert services[service]['logging']['options']['max-size'] == '10m'
print('PASS: 7 closed-pilot configuration groups (network, ports, proxy, integrations, outbound proxy variables, persistent data, bounded logs)')
