"""Finite acceptance on an absent, explicitly scoped Compose project only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
from uuid import uuid4

import httpx
from cargopulse_contracts import canonical_hash
from packages.domain_fixtures.generator import make_snapshot

WORK = Path(__file__).resolve().parents[2]
ROOT = Path('/Users/pie/CargoPulse_Production_Build_Package')
PROJECT = 'cargopulse-final-install-2'
PORT = 3116
BASE = f'http://localhost:{PORT}'
STAMP = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
PRIVATE = Path(__file__).resolve().parent / STAMP
PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=False)
DOCKER = str(ROOT / '.local/tools/docker/docker')
COMPOSE = str(ROOT / '.local/tools/docker-compose')
IMAGES = {
    'api': 'sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34',
    'worker': 'sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34',
    'migrate': 'sha256:9cf0c09fa13a647693567599f5451ca519cf2047efe104c0c753d4ef3693be34',
    'web': 'sha256:863d7eced8da07b5970629c6dbcad1c466ae456b985af5abc122d09e99139d8f',
    'postgres': 'sha256:07b174247e8b27ee2c6e66c8edd418b3f1d3de6907c27634f3e8ffb12bb1e1d3',
    'redis': 'sha256:fe9daae35cd4fd6ec22416aa4fe0cf6b3e36741e06ff45b9986253fe2a81c041',
}
ENV = dict(os.environ, DOCKER_HOST='unix:///Users/pie/.colima/default/docker.sock',
           DOCKER_CONFIG=str(ROOT / '.local/docker-config'), CARGOPULSE_PORT=str(PORT))
for key in ('DOCKER_CONTEXT', 'COMPOSE_FILE', 'COMPOSE_PROJECT_NAME', 'POSTGRES_PASSWORD', 'REDIS_PASSWORD'):
    ENV.pop(key, None)
ENV['PATH'] = str(ROOT / '.local/tools/node-v24.22.2-darwin-arm64/bin') + ':' + ENV['PATH']
REPORT = {'status': 'IN_PROGRESS', 'started_utc': datetime.now(timezone.utc).isoformat(),
          'project': PROJECT, 'base_url': BASE, 'private_evidence_directory': str(PRIVATE.relative_to(WORK)),
          'requested_images': IMAGES, 'commands': [], 'http_requests': []}
PASSWORDS = []
OWNED = False
START = time.monotonic()
PREFIX = None
REDIS_ANONYMOUS = None

def scrub(text):
    for value in PASSWORDS:
        text = text.replace(value, '<redacted>')
    return text

def save():
    (WORK/'docs/evidence/23-final-independent-install.json').write_text(json.dumps(REPORT, indent=2)+'\n')

def run(command, expected=0, timeout=180):
    result = subprocess.run(command, cwd=WORK, env=ENV, capture_output=True, text=True, timeout=timeout)
    entry = {'command': command, 'exit_code': result.returncode,
             'stdout': scrub(result.stdout), 'stderr': scrub(result.stderr)}
    REPORT['commands'].append(entry)
    with (PRIVATE/'operations.jsonl').open('a') as log:
        log.write(json.dumps(entry)+'\n')
    if expected is not None and result.returncode != expected:
        raise RuntimeError('Scoped operation failed: '+str(command[:4])+'; see private operations log')
    return result.stdout

def docker(*args, **kwargs):
    return run([DOCKER,*args], **kwargs)

def cp(*args, **kwargs):
    assert PREFIX is not None
    return run([*PREFIX,*args], **kwargs)

def query(statement):
    return cp('exec','-T','postgres','psql','-X','-qAt','-v','ON_ERROR_STOP=1',
              '-U','cargopulse','-d','cargopulse','-c',statement).strip()

def wait_ready(timeout=120):
    until=time.monotonic()+timeout
    with httpx.Client(timeout=3,trust_env=False) as c:
        while time.monotonic()<until:
            try:
                r=c.get(BASE+'/api/v1/health/ready')
                if r.status_code==200: return r.json()
            except httpx.HTTPError:
                pass
            time.sleep(.4)
    raise RuntimeError('Isolated stack did not become ready')

def req(client,method,path,body=None,expected=200,key=None,etag=None):
    headers={}
    if method=='POST':
        headers['Idempotency-Key']=key or str(uuid4())
        if path!='/auth/development':
            token=req(client,'GET','/auth/csrf').json()['csrf']
            headers['X-CSRF-Token']=token
    if etag:headers['If-Match']=etag
    r=client.request(method,path,json=body,headers=headers)
    REPORT['http_requests'].append({'method':method,'path':path,'status':r.status_code})
    assert r.status_code==expected,(method,path,r.status_code,'expected',expected)
    return r

def exports(client,plan_id):
    result={}
    folder=PRIVATE/'exports';folder.mkdir(exist_ok=True,mode=0o700)
    for fmt in ('json','csv','pdf'):
        r=req(client,'GET',f'/reports/{plan_id}/export?format={fmt}')
        assert r.content
        if fmt=='json': assert canonical_hash(r.json()['plan'])==REPORT['journey']['plan_hash']
        if fmt=='csv': assert 'SYNTHETIC' in r.text
        if fmt=='pdf': assert r.content.startswith(b'%PDF-')
        file=folder/('plan.'+fmt)
        file.write_bytes(r.content);file.chmod(0o600)
        result[fmt]={'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),
                     'content_type':r.headers.get('content-type'),
                     'attachment':r.headers.get('content-disposition','').startswith('attachment;')}
        assert result[fmt]['attachment']
    return result

try:
    # Read only resource names/labels/port bindings; never inspect other envs/data.
    existing=docker('ps','-aq','--filter','label=com.docker.compose.project='+PROJECT).strip()
    volumes=docker('volume','ls','--filter','name='+PROJECT,'--format','{{.Name}}').splitlines()
    networks=docker('network','ls','--filter','name='+PROJECT,'--format','{{.Name}}').splitlines()
    published=docker('ps','-aq','--filter','publish='+str(PORT)).strip()
    assert not existing and not volumes and not networks and not published,'Project/volume/network/port already exists; refusing initialization'
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1',PORT))
    existing_volumes=set(docker('volume','ls','--format','{{.Name}}').splitlines())
    (PRIVATE/'preflight-volume-names.json').write_text(json.dumps(sorted(existing_volumes),indent=2)+'\n')
    REPORT['preflight']={'project_absent':True,'volumes_absent':True,'network_absent':True,'port_absent':PORT,
                         'existing_volume_name_count':len(existing_volumes),
                         'existing_volume_names_sha256':hashlib.sha256('\n'.join(sorted(existing_volumes)).encode()).hexdigest()}
    resolved={name:json.loads(docker('image','inspect',image,'--format','{{json .Id}}')) for name,image in IMAGES.items()}
    REPORT['resolved_image_ids']=resolved
    raw=(ROOT/'compose.yaml').read_bytes()
    config=PRIVATE/'compose.yaml';config.write_bytes(raw);config.chmod(0o600)
    override=PRIVATE/'images.json'
    override.write_text(json.dumps({'services':{name:{'image':image,'pull_policy':'never'} for name,image in IMAGES.items()}},indent=2)+'\n')
    override.chmod(0o600)
    envfile=PRIVATE/'install.env'
    env_exists=(WORK/'.env').exists()
    if not env_exists:
        run([str(ROOT/'.venv/bin/python'),'scripts/configure_local.py'])
        values=dict(line.split('=',1) for line in (WORK/'.env').read_text().splitlines() if '=' in line)
    else:
        # Do not read or overwrite an existing checkout's credentials.
        values={key:secrets.token_urlsafe(36) for key in ('POSTGRES_PASSWORD','REDIS_PASSWORD')}
    PASSWORDS.extend(values[key] for key in ('POSTGRES_PASSWORD','REDIS_PASSWORD'))
    fd=os.open(envfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        for key in ('POSTGRES_PASSWORD','REDIS_PASSWORD'):f.write(key+'='+values[key]+'\n')
        f.write('CARGOPULSE_PORT='+str(PORT)+'\n')
    REPORT['private_configuration']={'existing_worktree_env_preserved':env_exists,'env_mode':oct(envfile.stat().st_mode&0o777),
                                     'compose_sha256':hashlib.sha256(raw).hexdigest(),
                                     'override_sha256':hashlib.sha256(override.read_bytes()).hexdigest()}
    PREFIX=[COMPOSE,'--project-directory',str(WORK),'--env-file',str(envfile),'-p',PROJECT,'-f',str(config),'-f',str(override)]
    parsed=json.loads(cp('config','--format','json'))
    # Full resolved config contains our private credentials: remove it from logs.
    REPORT['commands'][-1]['stdout']='<private config parsed in memory; omitted>'
    # Rebuild the safe operations log without the last raw resolved-config stdout.
    (PRIVATE/'operations.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in REPORT['commands']))
    assert parsed['name']==PROJECT
    assert parsed['services']['api']['environment']['APP_BASE_URL']==BASE
    assert parsed['services']['migrate']['environment']['APP_BASE_URL']==BASE
    assert {v['name'] for v in parsed['volumes'].values()}=={PROJECT+'_postgres_alpine',PROJECT+'_objects'}
    assert all(parsed['services'][name]['image']==image for name,image in IMAGES.items())
    assert parsed['services']['web']['ports'][0]['host_ip']=='127.0.0.1'
    assert str(parsed['services']['web']['ports'][0]['published'])==str(PORT)
    assert not parsed['services']['redis'].get('volumes'), 'Redis must use only its image-created anonymous data volume'
    REPORT['resolved_configuration']={'project':PROJECT,'app_base_url':BASE,'volumes':[PROJECT+'_postgres_alpine',PROJECT+'_objects'],
                                      'web_binding':f'127.0.0.1:{PORT}:3000','builds_used':False}
    save()
    OWNED=True
    cp('up','--no-build','--pull','never','--wait','-d',timeout=240)
    REPORT['initial_health']=wait_ready()
    states={}
    for name in IMAGES:
        identifier=cp('ps','-a','-q',name).strip();assert identifier and '\n' not in identifier
        selected=json.loads(docker('inspect',identifier,'--format',
            '{"id":{{json .Id}},"image":{{json .Image}},"user":{{json .Config.User}},"state":{{json .State}},"mounts":{{json .Mounts}},"ports":{{json .HostConfig.PortBindings}},"project":{{json (index .Config.Labels "com.docker.compose.project")}}}'))
        assert selected['project']==PROJECT and selected['image']==resolved[name]
        for mount in selected['mounts']:
            assert mount.get('Type')!='bind','No host bind mounts are permitted in this acceptance stack'
            if mount.get('Type')=='volume':
                volume=mount.get('Name')
                if name=='redis' and mount.get('Destination')=='/data':
                    assert re.fullmatch(r'[a-f0-9]{64}',volume or ''), 'Expected image-created anonymous Redis data volume'
                    assert volume not in existing_volumes, 'Refuse any preflight-existing Redis volume'
                    assert REDIS_ANONYMOUS is None, 'Expected exactly one Redis data mount'
                    REDIS_ANONYMOUS=volume
                else:
                    assert volume in (PROJECT+'_postgres_alpine',PROJECT+'_objects'), (name,mount.get('Destination'))
        if name!='web':assert not selected['ports']
        states[name]=selected
    assert REDIS_ANONYMOUS,'Official Redis anonymous data mount missing'
    REPORT['redis_anonymous_volume']={'name':REDIS_ANONYMOUS,'container_id':states['redis']['id'],
                                       'destination':'/data','absent_from_preflight':True,
                                       'created_with_this_new_container':True}
    REPORT['initial_containers']=states
    assert states['postgres']['user']=='postgres'
    assert states['migrate']['state']['ExitCode']==0 and not states['migrate']['state']['Running']
    schema=json.loads(query("SELECT json_build_object('migration',(SELECT version_num FROM alembic_version),'tables',(SELECT count(*) FROM pg_tables WHERE schemaname='public'),'forced_rls',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relrowsecurity AND c.relforcerowsecurity),'assurance_column',(SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='sessions' AND column_name='authentication_context_hash'),'disable_trigger',(SELECT count(*) FROM pg_trigger WHERE tgname='identities_revoke_disabled_sessions' AND NOT tgisinternal),'invalid_public_indexes',(SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND (NOT indisvalid OR NOT indisready)))"))
    assert schema=={'migration':'0005','tables':15,'forced_rls':12,'assurance_column':1,'disable_trigger':1,'invalid_public_indexes':0},schema
    assert query('SELECT count(*) FROM ingest_batches')=='0'
    assert query('SELECT count(*) FROM scenarios')=='0'
    assert query('SELECT count(*) FROM sessions')=='0'
    assert query('SHOW password_encryption')=='scram-sha-256'
    app_probe="import os,json; from sqlalchemy import create_engine,text; e=create_engine(os.environ['DATABASE_URL']); c=e.connect(); print(json.dumps(dict(c.execute(text(\"SELECT current_user AS db_user,rolsuper,rolbypassrls,(SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user) AS owned_tables FROM pg_roles WHERE rolname=current_user\")).mappings().one()))); c.close(); e.dispose()"
    app_role=json.loads(cp('exec','-T','api','python','-c',app_probe))
    assert app_role=={'db_user':'cargopulse_app','rolsuper':False,'rolbypassrls':False,'owned_tables':0},app_role
    pg_uid=cp('exec','-T','postgres','id','-u').strip();assert pg_uid=='70'
    REPORT['bootstrap']={**schema,'fresh_business_state_empty':True,'password_encryption':'scram-sha-256','postgres_uid':70,'app_role':app_role}
    save()
    with httpx.Client(base_url=BASE+'/api/v1',timeout=20,headers={'Origin':BASE},trust_env=False) as c:
        req(c,'POST','/auth/development',{'identity_id':'manager'})
        one=req(c,'GET','/auth/csrf');two=req(c,'GET','/auth/csrf')
        assert one.json()['csrf']==two.json()['csrf']
        lifetime=int(two.headers['x-session-expires-in']);assert 0<lifetime<=28800
        REPORT['csrf']={'stable_body_across_two_reads':True,'proxy_expiry_header_seconds':lifetime,'cookie_name_dependency':False}
        policy=req(c,'GET','/fixtures/recover').json()['policy']
        source=make_snapshot(8).model_dump(mode='json');source['policy']=policy
        batch=req(c,'POST','/imports/validate',{'snapshot':source},202).json()
        receipt=req(c,'POST',f"/imports/{batch['id']}/commit",expected=201).json()
        scenario=req(c,'POST','/scenarios',{'source_snapshot_id':receipt['snapshot_id'],'title':'Final independent fresh-volume install','allow_external_write':False},201).json()
        req(c,'GET',f"/scenarios/{scenario['id']}/candidates")
        job=req(c,'POST',f"/scenarios/{scenario['id']}/solve",{'max_wall_seconds':10,'compare_baselines':False},202,etag=scenario['etag']).json()
        until=time.monotonic()+90
        while True:
            job=req(c,'GET',f"/jobs/{job['id']}").json()
            if job['status']=='COMPLETED':break
            assert job['status'] not in ('FAILED','CANCELLED'),job.get('error_code')
            assert time.monotonic()<until,'Solve completion timeout'
            time.sleep(.25)
        plan=req(c,'GET',f"/plans/{job['plan_id']}").json()
        assert plan['approvable'] and plan['plan']['independent_validation']['status']=='PASS'
        assert canonical_hash(plan['plan'])==plan['plan_hash']
        req(c,'GET',f"/plans/{plan['id']}/alternatives")
        decision_body={'action':'APPROVE_IN_APP','reason_code':'FINAL_INDEPENDENT_INSTALL','comment':'Synthetic final independent local installation acceptance','expected_snapshot_hash':scenario['snapshot_hash'],'expected_plan_hash':plan['plan_hash']}
        decision=req(c,'POST',f"/plans/{plan['id']}/decisions",decision_body,201,etag=plan['etag']).json()
        assert decision['external_write_performed'] is False
        REPORT['journey']={'cargo_units':8,'import_id':batch['id'],'scenario_id':scenario['id'],'job_id':job['id'],'plan_id':plan['id'],'decision_id':decision['id'],'snapshot_hash':scenario['snapshot_hash'],'plan_hash':plan['plan_hash'],'solver_status':plan['plan']['solver']['status'],'independent_validation':'PASS','external_write_performed':False}
        REPORT['exports']=exports(c,plan['id'])
        with httpx.Client(base_url=BASE+'/api/v1',timeout=20,headers={'Origin':BASE},trust_env=False) as b:
            req(b,'POST','/auth/development',{'identity_id':'controller-b'})
            denied=[f"/scenarios/{scenario['id']}",f"/scenarios/{scenario['id']}/candidates",f"/jobs/{job['id']}",f"/plans/{plan['id']}",f"/plans/{plan['id']}/alternatives",*[f"/reports/{plan['id']}/export?format={fmt}" for fmt in ('json','csv','pdf')]]
            for path in denied:req(b,'GET',path,expected=404)
            req(b,'POST',f"/plans/{plan['id']}/decisions",decision_body,404,etag=plan['etag'])
            req(b,'GET',f"/imports/{batch['id']}",expected=403)
            req(b,'POST','/auth/logout')
        REPORT['cross_tenant']={'known_resource_gets_404':len(denied),'decision_404':True,'import_role_gate_403':True,'import_403_not_claimed_as_object_isolation':True}
        object_probe="import os,json,hashlib; from pathlib import Path; p=Path(os.environ['OBJECT_STORE_ROOT']); f=[v for v in p.rglob('*') if v.is_file()]; print(json.dumps({'count':len(f),'all_sha256_names_match':all(v.name==hashlib.sha256(v.read_bytes()).hexdigest() for v in f),'all_files_0600':all(v.stat().st_mode&511==384 for v in f)}))"
        REPORT['private_objects']=json.loads(cp('exec','-T','api','python','-c',object_probe))
        assert REPORT['private_objects']=={'count':1,'all_sha256_names_match':True,'all_files_0600':True}
        before_hash=REPORT['journey']['plan_hash']
        cp('stop');cp('start',timeout=180);wait_ready()
        req(c,'GET','/me')
        after=req(c,'GET',f"/plans/{plan['id']}").json()
        assert after['plan_hash']==before_hash and canonical_hash(after['plan'])==before_hash
        assert exports(c,plan['id'])==REPORT['exports']
        REPORT['stop_start_persistence']={'session_survived':True,'same_plan_hash':True,'exports_byte_identical':True}
        save()
    chrome_env=dict(ENV,CARGOPULSE_E2E_URL=BASE,CARGOPULSE_BROWSER_CHANNEL='chrome')
    command=[str(WORK/'node_modules/.bin/playwright'),'test','--config','apps/web/playwright.config.ts','apps/web/tests/session-boundary.spec.ts','--grep','logout unmounts both tabs and preserves unrelated storage','--trace','off','--reporter','line','--output',str(PRIVATE/'browser-results')]
    browser=subprocess.run(command,cwd=WORK,env=chrome_env,capture_output=True,text=True,timeout=120)
    (PRIVATE/'chrome.txt').write_text(scrub(browser.stdout+browser.stderr))
    REPORT['chrome']={'exit_code':browser.returncode,'tests_requested':1,'trace_recording':False,'scope':'real Chrome sign-in/view/cross-tab sign-out privacy plus an explicitly injected queued storage notification'}
    assert browser.returncode==0,'Chrome supplement failed; see scoped chrome log'
    REPORT['status']='PASS'
except BaseException as error:
    REPORT['status']='FAIL'
    REPORT['failure']={'type':type(error).__name__,'summary':scrub(str(error))}
    raise
finally:
    if OWNED:
        try:
            cp('stop',timeout=120)
            remaining=cp('ps','-q').strip()
            assert not remaining,'Some final-install services are still running'
            REPORT['final_disposition']={'services_stopped':True,'volumes_preserved':[PROJECT+'_postgres_alpine',PROJECT+'_objects']+([REDIS_ANONYMOUS] if REDIS_ANONYMOUS else []),'no_volume_deletion':True,
                                         'initial_project_and_volumes_untouched':True}
        except BaseException as stop_error:
            REPORT['status']='FAIL'
            REPORT['cleanup_failure']={'type':type(stop_error).__name__,'summary':scrub(str(stop_error))}
    REPORT['finished_utc']=datetime.now(timezone.utc).isoformat()
    REPORT['seconds']=round(time.monotonic()-START,3)
    REPORT['limits']=['Prebuilt pinned images and existing local Docker VM/cache; not cold/new-host provisioning.','Synthetic local acceptance only; no real enterprise IdP/MFA, hosted CI, cloud TLS/storage/monitoring or public release verified.','PDF bytes/header verified; PDF layout not visually reviewed.','Chrome storage-notification injection is not native BFCache acceptance.']
    save()
print(json.dumps({'status':REPORT['status'],'seconds':REPORT['seconds'],'evidence':str(PRIVATE),'bootstrap':REPORT.get('bootstrap'),'journey':REPORT.get('journey'),'cross_tenant':REPORT.get('cross_tenant'),'chrome':REPORT.get('chrome'),'final_disposition':REPORT.get('final_disposition')},indent=2))
