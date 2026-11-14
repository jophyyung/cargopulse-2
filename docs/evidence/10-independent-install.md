# Independent clean-checkout installation review

Date: 2026-11-10. Reviewed commit: `e40c67671aff8889234c4af1dee490eb2da75999`.
Worktree: `/Users/pie/CargoPulse_Production_Build_Package/.worktrees/final-install`.
Branch: `codex/final-install`. Reviewer: independent delegated install operator.

## Result and boundary

**PASS: second-person local installation/runbook check only. Public L1 remains BLOCKED.**
The documented Docker setup successfully built and started a new isolated Compose
project with newly created PostgreSQL/object volumes and freshly generated ignored
secrets. No host node_modules or Python virtual environment was needed for image
build/start. Existing Docker layer caches and installed Docker/Colima were used;
this is not a cold download, new-host provisioning, or production infrastructure test.
The shared Python environment was used only as an HTTP test client, importing this
checkout's contracts and synthetic fixture generator.

Read before execution: README.md, docs/RUNNING.md, docs/CONTRACTS.md,
ops/02_RELEASE_GATES.md, RELEASE_REPORT.md. No repository AGENTS.md was present;
the supplied language/honesty instructions were followed.

## Executed observations

- New project `cargopulse-independent-install`, only `127.0.0.1:3112 -> web:3000/tcp`
  published. PostgreSQL, Redis, API and worker had no published host ports.
- PostgreSQL initialized successfully on its new volume as uid 999 / user `postgres`;
  `/usr/local/bin/gosu` was absent. Migration version was `0004`.
- All 15 public tables were owned by `cargopulse`. The API's actual database
  connection was `cargopulse_app`, `rolsuper=false`, `rolbypassrls=false`, owning zero
  public tables. These were real SQL queries against this isolated stack.
- Real 8-ULD synthetic import validation (202), commit (201), scenario (201),
  candidates (200), durable solve (202), job completion, plan read and alternatives.
  The generated snapshot used the authenticated fixture's registered policy.
- HiGHS returned OPTIMAL, independent validation PASS, an approvable proposal, and
  a matching canonical plan hash. Solve limit 10 seconds; baselines disabled.
- Exact quoted scenario/plan ETags, per-command Idempotency-Key, session cookies and
  CSRF echo were used. An APPROVE_IN_APP decision returned 201 and
  `external_write_performed=false`.
- JSON, CSV and PDF exports returned 200 before and after restart. JSON plan hash
  matched; CSV contained SYNTHETIC; PDF began `%PDF-`. Export hashes/byte lengths are
  in the scoped JSON. PDF layout was not visually reviewed.
- Separate-tenant controller-b received 404 for eight known operational-resource
  GETs: scenario, candidates, job, plan, alternatives, JSON/CSV/PDF export. Its
  decision command also returned 404. Import read returned 403 at the role gate;
  that import result alone is not evidence of cross-tenant object filtering.
- With worker/Redis stopped, readiness reported durable-database degradation,
  solve stayed QUEUED, an API restart preserved the session, and the same solve
  key returned the original job. Starting Redis/worker completed that job.
- Full `stop` then `start` preserved session, job-to-plan link, canonical plan hash,
  same-key decision receipt and all three exports. Redis readiness recovered.
- Authenticated `/operations` returned HTML 200 with SYNTHETIC notice. This was an
  HTTP server-rendered-page check, not a browser click-through/accessibility review.

The successful HTTP/drill sequence took 37.837 seconds. It is an
acceptance drill duration, not a solver throughput benchmark or SLA. The recorded
solver wall time was 32.982148 ms on this synthetic case.

## Failures and documentation gaps

No application failure remained in the executed installation/journey scope.
Two reviewer-harness assumptions failed before the successful run: validation was
initially expected to return 201 instead of the OpenAPI-defined 202; import read by
controller-b was initially expected to return 404 but correctly hit a role-level
403 first. Those assertions were corrected; the earlier attempts left additional
synthetic imports/scenarios in this review's own volume only.

The Docker CLI warned that buildx was unavailable and used the classic builder;
all image builds nevertheless completed. The supplied local Docker tool paths were
used because this environment provides them outside the ordinary PATH.

README documents the alternate port, but docs/RUNNING.md shows only port 3000 and
neither page gives a complete alternate-port **and project-name** isolation example.
The top-level Compose name is fixed (`cargopulse-local`), so a second checkout must
supply `-p` to avoid sharing the first checkout's resources. The explicit delegation
provided that missing isolation instruction. This did not prevent this run.
No documented code/configuration correction was needed to initialize hardened
PostgreSQL or migration0004. Source/application/contracts were not changed.

## Exact operator commands

All commands were run inside this worktree. Secrets were not printed.

```sh
export DOCKER_HOST=unix:///Users/pie/.colima/default/docker.sock
export DOCKER_CONFIG=/Users/pie/CargoPulse_Production_Build_Package/.local/docker-config
export CARGOPULSE_PORT=3112
python3 scripts/configure_local.py
/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker-compose -p cargopulse-independent-install up --build -d
/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker-compose -p cargopulse-independent-install logs --tail=40 migrate api worker web
/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker-compose -p cargopulse-independent-install exec -T postgres sh -c 'id; test ! -e /usr/local/bin/gosu'
/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker-compose -p cargopulse-independent-install exec -T postgres psql -U cargopulse -d cargopulse -c "SELECT version_num FROM alembic_version; SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'cargopulse_app'; SELECT tableowner, count(*) FROM pg_tables WHERE schemaname = 'public' GROUP BY tableowner;"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=packages/contracts/python:services/api:services/worker:.
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python /tmp/cargopulse-independent-install-check.py
/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker-compose -p cargopulse-independent-install stop
```

The shell test and SQL in the display above were originally issued together in a
single `exec -T postgres sh -c` command; separating them here preserves their exact
operations and outputs without nested shell-quote noise. The actual API-role query
was run inside the API container using SQLAlchemy's DATABASE_URL without printing
that URL:

```sql
SELECT current_user, r.rolsuper, r.rolbypassrls
FROM pg_roles r WHERE r.rolname=current_user;
SELECT count(*) FROM pg_tables
WHERE schemaname='public' AND tableowner=current_user;
```

Container inspection selected only image IDs, configured users, state, mounts and
port bindings. Full inspect environment variables were never logged. The final
solver field was read from `plan.plan.solver.status`; the HTTP script's preliminary
`plan.plan.status` recording was null and corrected by this authenticated read.

## Runtime image identities

- `postgres`: `sha256:e833fa4f2aadb8e93fb4c56a7a131abff194d1b142ba99eab73fcef2fc0b218c`
- `redis`: `sha256:fe9daae35cd4fd6ec22416aa4fe0cf6b3e36741e06ff45b9986253fe2a81c041`
- `api`: `sha256:9f098864022455d0f7d9889554a5fe71382ad3a13eef07e5da88906d5f4e3861`
- `worker`: `sha256:9f098864022455d0f7d9889554a5fe71382ad3a13eef07e5da88906d5f4e3861`
- `migrate`: `sha256:9f098864022455d0f7d9889554a5fe71382ad3a13eef07e5da88906d5f4e3861`
- `web`: `sha256:c75d62e9bdb90c558ba4cb9f05a4d3a356b6dae1dfcde49bb4235c82d5914e68`

## Reproducible HTTP/drill script

This is the successful script used at the temporary path in the command above.
It creates only synthetic state in this dedicated project. Cookie values, passwords,
Idempotency-Key values and source bodies are not logged. The final structured
evidence is docs/evidence/10-independent-install.json.

```python
import hashlib,json,subprocess,time
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
import httpx
from cargopulse_contracts import canonical_hash
from packages.domain_fixtures.generator import make_snapshot
base='http://localhost:3112'
compose=['/Users/pie/CargoPulse_Production_Build_Package/.local/tools/docker-compose','-p','cargopulse-independent-install']
result={'scope':'independent fresh-volume local synthetic install at e40c67671aff8889234c4af1dee490eb2da75999','started_utc':datetime.now(timezone.utc).isoformat(),'project':'cargopulse-independent-install','base_url':base,'requests':[]}
started=time.monotonic()
def command(*args):
 subprocess.run(compose+list(args),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def wait(fn,timeout=90):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  try:
   got=fn()
   if got:return got
  except (httpx.HTTPError,ValueError):pass
  time.sleep(.3)
 raise TimeoutError('Expected runtime state not reached')
def req(c,method,path,body=None,expected=200,key=None,etag=None):
 headers={}
 if method=='POST':headers['Idempotency-Key']=key or str(uuid4())
 if etag:headers['If-Match']=etag
 response=c.request(method,path,json=body,headers=headers)
 result['requests'].append({'method':method,'path':path,'status':response.status_code})
 assert response.status_code==expected,(method,path,response.status_code)
 return response
with httpx.Client(base_url=base+'/api/v1',timeout=20,headers={'Origin':base}) as c:
 wait(lambda:c.get('/health/ready').status_code==200)
 health=req(c,'GET','/health/ready').json()
 assert health['dependencies']['redis_hint_broker']=='ok'
 req(c,'POST','/auth/development',{'identity_id':'manager'})
 c.headers['X-CSRF-Token']=c.cookies['cp_csrf']
 policy=req(c,'GET','/fixtures/recover').json()['policy']
 source=make_snapshot(8).model_dump(mode='json');source['policy']=policy
 batch=req(c,'POST','/imports/validate',{'snapshot':source},202).json()
 receipt=req(c,'POST',f"/imports/{batch['id']}/commit",expected=201).json()
 scenario=req(c,'POST','/scenarios',{'source_snapshot_id':receipt['snapshot_id'],'title':'Independent clean install 8 ULD'},201).json()
 req(c,'GET',f"/scenarios/{scenario['id']}/candidates")
 command('stop','worker','redis')
 try:
  assert req(c,'GET','/health/ready').json()['dependencies']['redis_hint_broker']=='degraded_durable_database_polling'
  solve={'max_wall_seconds':10,'compare_baselines':False};solve_key=str(uuid4())
  job=req(c,'POST',f"/scenarios/{scenario['id']}/solve",solve,202,solve_key,scenario['etag']).json()
  assert req(c,'GET',f"/jobs/{job['id']}").json()['status']=='QUEUED'
  command('restart','api')
  wait(lambda:c.get('/health/ready').status_code==200)
  req(c,'GET','/me')
  assert req(c,'POST',f"/scenarios/{scenario['id']}/solve",solve,202,solve_key,scenario['etag']).json()['id']==job['id']
 finally:command('start','redis','worker')
 def completed():
  state=c.get(f"/jobs/{job['id']}").raise_for_status().json()
  if state['status']=='FAILED':raise RuntimeError('Worker failed: '+str(state.get('error_code')))
  return state if state['status']=='COMPLETED' else None
 job=wait(completed)
 plan=req(c,'GET',f"/plans/{job['plan_id']}").json()
 assert plan['plan']['independent_validation']['status']=='PASS'
 assert plan['approvable']
 assert canonical_hash(plan['plan'])==plan['plan_hash']
 req(c,'GET',f"/plans/{plan['id']}/alternatives")
 decision_body={'action':'APPROVE_IN_APP','reason_code':'INDEPENDENT_INSTALL','comment':'Synthetic independent local installation check','expected_snapshot_hash':scenario['snapshot_hash'],'expected_plan_hash':plan['plan_hash']}
 decision_key=str(uuid4())
 decision=req(c,'POST',f"/plans/{plan['id']}/decisions",decision_body,201,decision_key,plan['etag']).json()
 assert decision['external_write_performed'] is False
 exports={}
 for fmt in ['json','csv','pdf']:
  r=req(c,'GET',f"/reports/{plan['id']}/export?format={fmt}")
  assert len(r.content)>0
  if fmt=='json':assert canonical_hash(r.json()['plan'])==plan['plan_hash']
  if fmt=='csv':assert 'SYNTHETIC' in r.text
  if fmt=='pdf':assert r.content.startswith(b'%PDF-')
  exports[fmt]={'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'content_type':r.headers['content-type']}
 with httpx.Client(base_url=base+'/api/v1',timeout=20,headers={'Origin':base}) as b:
  req(b,'POST','/auth/development',{'identity_id':'controller-b'})
  b.headers['X-CSRF-Token']=b.cookies['cp_csrf']
  req(b,'GET',f"/imports/{batch['id']}",expected=403)
  denied=[]
  for path in [f"/scenarios/{scenario['id']}",f"/scenarios/{scenario['id']}/candidates",f"/jobs/{job['id']}",f"/plans/{plan['id']}",f"/plans/{plan['id']}/alternatives",f"/reports/{plan['id']}/export?format=json",f"/reports/{plan['id']}/export?format=csv",f"/reports/{plan['id']}/export?format=pdf"]:
   req(b,'GET',path,expected=404);denied.append(path)
  req(b,'POST',f"/plans/{plan['id']}/decisions",decision_body,404,etag=plan['etag'])
 command('stop');command('start')
 wait(lambda:c.get('/health/ready').status_code==200)
 req(c,'GET','/me')
 assert req(c,'GET',f"/jobs/{job['id']}").json()['plan_id']==plan['id']
 persisted=req(c,'GET',f"/plans/{plan['id']}").json()
 assert canonical_hash(persisted['plan'])==plan['plan_hash']
 assert req(c,'POST',f"/plans/{plan['id']}/decisions",decision_body,201,decision_key,plan['etag']).json()['id']==decision['id']
 for fmt in ['json','csv','pdf']:req(c,'GET',f"/reports/{plan['id']}/export?format={fmt}")
 assert req(c,'GET','/health/ready').json()['dependencies']['redis_hint_broker']=='ok'
 ui=c.get(base+'/operations',follow_redirects=True)
 assert ui.status_code==200
 assert 'SYNTHETIC' in ui.text
 result.update(status='PASS',seconds=round(time.monotonic()-started,3),cargo_units=8,scenario_id=scenario['id'],import_id=batch['id'],job_id=job['id'],plan_id=plan['id'],decision_id=decision['id'],snapshot_hash=scenario['snapshot_hash'],plan_hash=plan['plan_hash'],independent_validation=plan['plan']['independent_validation']['status'],solver_status=plan['plan'].get('status'),external_write_performed=decision['external_write_performed'],exports=exports,cross_tenant_get_denials=len(denied),cross_tenant_decision_denial=True,redis_outage_durable_queue=True,api_restart_session_and_idempotent_solve=True,full_stack_stop_start_persistence=True,idempotent_decision_after_restart=True,operations_html_status=ui.status_code,operations_synthetic_notice=True)
Path('docs/evidence/10-independent-install.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='requests'},indent=2))
```

## Remaining unverified work and disposition

No hosted CI, new image vulnerability scan, public deployment, production OIDC,
cloud storage/TLS/backup/monitoring, intended-environment load, browser interaction
or airline access was performed. Existing release image findings and real
infrastructure conditions remain external blockers; this review does not waive
them, certify safety, sign a public release or claim L1 success.

The dedicated stack was stopped after verification. Its named volumes and
containers are preserved for inspection; `down --volumes` was never run. Other
projects, root services and native PostgreSQL/Redis were not modified. Tracked
source remained at the reviewed commit; only this report and its scoped JSON were
added. The generated `.env` is ignored and mode 0600. No commits or pushes were made.
