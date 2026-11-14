"""Resume only the stopped, already owned second stack for one Chrome test."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import httpx

WORK=Path(__file__).resolve().parents[2]
ROOT=Path('/Users/pie/CargoPulse_Production_Build_Package')
PATH=WORK/'docs/evidence/23-final-independent-install.json'
REPORT=json.loads(PATH.read_text())
assert REPORT['project']=='cargopulse-final-install-2' and REPORT['base_url']=='http://localhost:3116'
assert REPORT['status']=='FAIL' and REPORT['failure']['summary'].startswith('Chrome supplement failed')
assert REPORT['bootstrap']['migration']=='0005' and REPORT['journey']['independent_validation']=='PASS'
assert REPORT['stop_start_persistence']['exports_byte_identical']
PRIVATE=(WORK/REPORT['private_evidence_directory']).resolve()
assert PRIVATE.is_relative_to(WORK/'.local/final-install')
CORE_SECONDS=json.loads((PRIVATE/'before-chrome-correction.json').read_text())['seconds']
assert hashlib.sha256((PRIVATE/'compose.yaml').read_bytes()).hexdigest()==REPORT['private_configuration']['compose_sha256']
SECRETS=[line.split('=',1)[1] for line in (PRIVATE/'install.env').read_text().splitlines() if line.startswith(('POSTGRES_PASSWORD=','REDIS_PASSWORD='))]
ENV=dict(os.environ,DOCKER_HOST='unix:///Users/pie/.colima/default/docker.sock',DOCKER_CONFIG=str(ROOT/'.local/docker-config'),CARGOPULSE_PORT='3116')
for key in ('DOCKER_CONTEXT','COMPOSE_FILE','COMPOSE_PROJECT_NAME','POSTGRES_PASSWORD','REDIS_PASSWORD'):ENV.pop(key,None)
ENV['PATH']=str(ROOT/'.local/tools/node-v24.22.2-darwin-arm64/bin')+':'+ENV['PATH']
DOCKER=str(ROOT/'.local/tools/docker/docker')
PREFIX=[str(ROOT/'.local/tools/docker-compose'),'--project-directory',str(WORK),'--env-file',str(PRIVATE/'install.env'),'-p',REPORT['project'],'-f',str(PRIVATE/'compose.yaml'),'-f',str(PRIVATE/'images.json')]
START=time.monotonic()
OWNED=False

def clean(value):
    for secret in SECRETS:value=value.replace(secret,'<redacted>')
    return value

def run(command,env=ENV,timeout=180):
    r=subprocess.run(command,cwd=WORK,env=env,capture_output=True,text=True,timeout=timeout)
    entry={'command':command,'exit_code':r.returncode,'stdout':clean(r.stdout),'stderr':clean(r.stderr),'phase':'chrome-only completion'}
    REPORT['commands'].append(entry)
    with (PRIVATE/'chrome-completion-operations.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
    assert r.returncode==0,'Scoped Chrome completion operation failed; see private phase log'
    return r.stdout

def cp(*args):return run([*PREFIX,*args])

try:
    ids=run([DOCKER,'ps','-aq','--no-trunc','--filter','label=com.docker.compose.project='+REPORT['project']]).splitlines()
    assert set(ids)=={x['id'] for x in REPORT['initial_containers'].values()}
    for identifier in ids:
        data=json.loads(run([DOCKER,'inspect',identifier,'--format','{"image":{{json .Image}},"running":{{json .State.Running}},"project":{{json (index .Config.Labels "com.docker.compose.project")}}}']))
        assert data['project']==REPORT['project'] and not data['running']
        assert data['image'] in REPORT['resolved_image_ids'].values()
    OWNED=True
    cp('start')
    with httpx.Client(timeout=3,trust_env=False) as c:
        until=time.monotonic()+120
        while True:
            try:
                r=c.get(REPORT['base_url']+'/api/v1/health/ready')
                if r.status_code==200:break
            except httpx.HTTPError:pass
            assert time.monotonic()<until,'Second stack did not become ready'
            time.sleep(.3)
    chrome_env=dict(ENV,CARGOPULSE_E2E_URL=REPORT['base_url'],CARGOPULSE_BROWSER_CHANNEL='chrome')
    command=[str(WORK/'node_modules/.bin/playwright'),'test','--config','apps/web/playwright.config.ts','apps/web/tests/session-boundary.spec.ts','--grep','logout unmounts both tabs and preserves unrelated storage','--trace','off','--reporter','line','--output',str(PRIVATE/'browser-results-corrected')]
    output=run(command,env=chrome_env,timeout=120)
    (PRIVATE/'chrome-corrected.txt').write_text(output)
    assert '1 passed' in output
    old_failure=REPORT.pop('failure')
    old_guard_failure=REPORT.pop('chrome_completion_failure',None)
    REPORT['historical_failures']=[
        {'phase':'first fresh project mount assertion','report':'docs/evidence/23-final-independent-install-initial.json','sha256':hashlib.sha256((WORK/'docs/evidence/23-final-independent-install-initial.json').read_bytes()).hexdigest(),'http_journey_executed':False},
        {'phase':'second project initial Chrome selector','report':str((PRIVATE/'before-chrome-correction.json').relative_to(WORK)),'sha256':hashlib.sha256((PRIVATE/'before-chrome-correction.json').read_bytes()).hexdigest(),'failure':old_failure,'browser_tests_executed':0},
        {'phase':'Chrome completion read-only ID guard','report':str((PRIVATE/'chrome-guard-short-id-failure.json').relative_to(WORK)),'sha256':hashlib.sha256((PRIVATE/'chrome-guard-short-id-failure.json').read_bytes()).hexdigest(),'failure':old_guard_failure,'services_started':False,'browser_tests_executed':0},
    ]
    REPORT['initial_fresh_install_and_http_seconds']=CORE_SECONDS
    REPORT['chrome']={'exit_code':0,'tests_requested':1,'tests_passed':1,'trace_recording':False,'actual_base_url':REPORT['base_url'],'browser_channel':'chrome','scope':'real Chrome login/view/cross-tab logout DOM removal and server-session rejection; queued-storage-event subcase is injected','authorship_independence_claimed':False}
    REPORT['reviewer_role']='Second-person installation/runbook operator for lead/backend/runtime integration; operator also authored the frontend boundary and does not claim independent security review of that feature.'
    REPORT['status']='PASS'
except BaseException as error:
    REPORT['status']='FAIL'
    REPORT['chrome_completion_failure']={'type':type(error).__name__,'summary':clean(str(error))}
    raise
finally:
    if OWNED:
        try:
            cp('stop')
            assert not cp('ps','-q').strip()
            assert not run([DOCKER,'ps','-q','--filter','label=com.docker.compose.project=cargopulse-final-install']).strip()
            REPORT['final_disposition']['services_stopped']=True
            REPORT['final_disposition']['first_and_second_projects_stopped']=True
        except BaseException as error:
            REPORT['status']='FAIL';REPORT['chrome_completion_cleanup_failure']={'type':type(error).__name__,'summary':clean(str(error))}
    REPORT['chrome_completion_seconds']=round(time.monotonic()-START,3)
    REPORT['active_execution_seconds']=round(CORE_SECONDS+REPORT['chrome_completion_seconds'],3)
    REPORT['finished_utc']=datetime.now(timezone.utc).isoformat()
    REPORT['seconds']=round((datetime.fromisoformat(REPORT['finished_utc'])-datetime.fromisoformat(REPORT['started_utc'])).total_seconds(),3)
    PATH.write_text(json.dumps(REPORT,indent=2)+'\n')
print(json.dumps({'status':REPORT['status'],'chrome':REPORT.get('chrome'),'final_disposition':REPORT['final_disposition'],'active_execution_seconds':REPORT['active_execution_seconds']},indent=2))
