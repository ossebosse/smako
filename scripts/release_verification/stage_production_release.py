"""Stage the approved pinned release configuration; never start services."""
import hashlib
import json
import subprocess
from pathlib import Path

release = Path('/opt/smako/releases/lund-08c137475d9c')
containers = json.loads(subprocess.check_output(['docker', 'inspect', 'smako-app-1', 'smako-scheduler-1']))
values = {}
for container in containers:
    values.update(dict(s.split('=', 1) for s in container['Config']['Env'] if '=' in s))
for line in Path('/opt/smako/production.env').read_text().splitlines():
    if line.startswith('ACME_EMAIL='):
        values['ACME_EMAIL'] = line.split('=', 1)[1].strip().strip('"').strip("'")
caddy = json.loads(subprocess.check_output(['docker', 'inspect', 'smako-caddy-1']))[0]
caddy_env = dict(s.split('=', 1) for s in caddy['Config']['Env'] if '=' in s)
# Existing proxy has no ACME contact and stays running unchanged. The upstream
# Compose requires a value even for an excluded service; this marker is never
# passed to a running Caddy. All activation commands target named app jobs only.
values['ACME_EMAIL'] = caddy_env['ACME_EMAIL'] or 'unused-existing-proxy@example.invalid'
policy = json.loads((release / 'deploy/policies/lund-own-five-base-20260928-v1.json').read_text())
values.update(
    BUILD_ID='08c137475d9ca96a6ef7673245a639c8c5c9e922',
    PYTHONPATH='/srv/app/backend:/srv/app',
    SMAKO_RELEASE_IMAGE='sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7',
    RUNTIME_ROOT='/srv/smako/data', OWN_SOURCES_ONLY='true',
    PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS=','.join(policy['required_context_ids']),
    REFRESH_MUNICIPALITY_CODE='1281',
    SOURCE_RELAY_INBOX='/srv/app/var/raw_snapshots/source-inbox/municipality-1281',
    INTERNAL_APP_BASE_URL='http://app:8000', WILLYS_COLLECTION_LOCATION='LOCAL_RELAY',
    COOP_ALLOW_FULL_CRAWL='true', COOP_ONLINE_CONTEXT_IDS='730400',
    HEMKOP_ALLOW_FULL_CRAWL='true', HEMKOP_STORE_EXTERNAL_IDS='4123,4224',
    DEMAND_REFRESH_ENABLED='true', DEMAND_REFRESH_CRON='*/15 * * * *',
    MAX_PRICE_AGE_HOURS='48', PRICE_AGE_WARNING_HOURS='36',
)
for prefix, directory in [('COOP', 'coop-municipal'), ('HEMKOP', 'hemkop-municipal'), ('LIDL', 'lidl-municipal')]:
    values.update({prefix + '_MUNICIPAL_ROOT': '/srv/app/var/grocery/' + directory,
                   prefix + '_MUNICIPAL_OFFERS_ROOT': '/srv/app/var/grocery/' + directory,
                   prefix + '_MUNICIPALITY_CODE': '1281', prefix + '_MUNICIPAL_ENABLED': 'true',
                   prefix + '_MUNICIPAL_OFFERS_ENABLED': 'true'})
values.update(COOP_XTRA_OFFERS_ENABLED='true', ICA_STRUCTURED_OFFERS_ENABLED='true',
              ICA_STRUCTURED_OFFERS_ROOT='/srv/app/var/grocery/ica-structured',
              WILLYS_FLYER_ENABLED='true', WILLYS_FLYER_MUNICIPALITY_CODE='1281',
              WILLYS_FLYER_ROOT='/srv/app/var/grocery/willys-flyer',
              WILLYS_MUNICIPAL_CONFIG='/srv/app/var/grocery/willys-config.json')
private = release / 'activation-private.env'
values['SMAKO_RELEASE_ENV_FILE'] = str(private)
assert Path('/opt/smako/current').resolve() != release, 'Never rewrite an active configuration'
if private.exists():
    previous = private.read_bytes()
    saved = release / ('activation-private.before-' + hashlib.sha256(previous).hexdigest()[:12] + '.env')
    if not saved.exists():
        saved.write_bytes(previous)
        saved.chmod(0o600)
private.write_text(''.join(k + "='" + v.replace('\\', '\\\\').replace("'", "\\'") + "'\n"
                           for k, v in sorted(values.items()) if k.isidentifier()))
private.chmod(0o600)
proxy_exclusion = release / 'keep-existing-proxy.yaml'
proxy_exclusion.write_text('services:\n  caddy:\n    profiles: [existing-proxy-not-part-of-activation]\n')
command = ['docker', 'compose', '-p', 'smako', '--profile', 'ops', '--env-file', str(private),
           '-f', str(release / 'deploy/compose.yaml'), '-f', '/opt/smako/compose.vps.yaml',
           '-f', str(release / 'deploy/compose.release.yaml'), '-f', str(proxy_exclusion),
           'config', '--format', 'json']
result = subprocess.run(command, capture_output=True, text=True, check=False)
if result.returncode:
    error = release / 'render-error.private'
    error.write_text(result.stderr)
    error.chmod(0o600)
    raise RuntimeError('Compose render failed; inspect private stderr')
config = json.loads(result.stdout)
assert 'caddy' not in config['services'], 'Never recreate the existing proxy in this activation'
rendered = release / 'rendered.private.json'
rendered.write_text(result.stdout)
rendered.chmod(0o600)
services = ['app', 'scheduler', 'migrate', 'refresh-once', 'backup-once']
assert all(config['services'][s]['image'] == values['SMAKO_RELEASE_IMAGE'] and
           'build' not in config['services'][s] for s in services)
for name in ['app', 'scheduler', 'refresh-once']:
    env = config['services'][name]['environment']
    for key in ['OWN_SOURCES_ONLY', 'PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS', 'SOURCE_RELAY_INBOX',
                'REFRESH_MUNICIPALITY_CODE', 'DEMAND_REFRESH_ENABLED', 'DEMAND_REFRESH_CRON']:
        assert env[key] == values[key], (name, key)
    assert env['SECRET_KEY'] == values['SECRET_KEY']
    assert env['BETA_ADMIN_TOKEN'] == values['BETA_ADMIN_TOKEN']
for name, readonly in [('app', True), ('scheduler', False)]:
    for mount in config['services'][name]['volumes']:
        if mount['target'] in ['/srv/app/var/raw_snapshots', '/srv/app/var/price_universes']:
            assert bool(mount.get('read_only', False)) == readonly
print(json.dumps({'render_only': True, 'private_configuration': str(private),
                  'pinned_images': {s: config['services'][s]['image'] for s in services},
                  'required_context_ids': policy['required_context_ids'],
                  'existing_auth_preserved': True, 'app_raw_prices_readonly': True,
                  'existing_proxy_excluded_and_unchanged': True,
                  'server_demand_schedule_approved': True, 'active_configuration_changed': False}, indent=2))
