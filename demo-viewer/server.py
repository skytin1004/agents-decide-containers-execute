"""Local presentation viewer. Every observation has a source; no timed stage animation."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from urllib.parse import quote, unquote, urlparse

VIEWER_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = VIEWER_ROOT.parent
STATIC_ROOT = VIEWER_ROOT / 'dist'
EVIDENCE_ROOT = REPOSITORY_ROOT / 'samples' / 'cloud-validation'
RUN_ROOT = REPOSITORY_ROOT / '.artifacts' / 'viewer'
REQUEST_ID = re.compile(r'docops-[a-z0-9][a-z0-9-]{0,55}\Z')
sys.path.insert(0, str(REPOSITORY_ROOT))
STAGE_DEFINITIONS = [
    ('routine', 'Microsoft Foundry Routine'), ('agent', 'Foundry hosted agent'),
    ('validation', 'Python request validation'), ('queue', 'Azure Queue Storage'),
    ('job', 'Azure Container Apps Job'), ('report', 'Azure Blob Storage'),
]

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def initial_stages():
    return [dict(id=key, name=name, status='waiting', detail='No evidence yet', source=None, updated_at=None)
            for key, name in STAGE_DEFINITIONS]

@dataclass
class DemoRun:
    id: str
    mode: str
    request_id: str
    status: str = 'running'
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    monitor_only: bool = False
    stages: list = field(default_factory=initial_stages)
    actions: list = field(default_factory=list)
    report: dict | None = None
    evidence: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    error: str | None = None
    recovery: str | None = None

RUNS = {}
RUNS_LOCK = threading.RLock()

def azure_portal_source(data):
    """Link only an observed report to its matching configured storage account."""
    unavailable = lambda note: dict(url=None, note=note)
    if data['mode'] == 'local':
        return unavailable('Local files only · no Azure resource.')
    if data['mode'] == 'replay':
        return unavailable('This recording has no live Azure account reference.')
    if data['status'] != 'completed' or not data.get('report'):
        return unavailable('Available after an Azure report is verified.')
    resource_id = os.getenv('AZURE_STORAGE_RESOURCE_ID', '').strip()
    match = re.fullmatch(
        r'/subscriptions/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
        r'/resourceGroups/[A-Za-z0-9_.()-]+/providers/Microsoft.Storage/storageAccounts/([a-z0-9]{3,24})',
        resource_id)
    if not match:
        return unavailable('Set AZURE_STORAGE_RESOURCE_ID in the server .env to enable this link.')
    evidence = data.get('evidence', {})
    try:
        blob = urlparse(evidence.get('blob_url', ''))
        container, report_path = evidence.get('blob_path', '').split('/', 1)
        valid = (blob.scheme == 'https' and blob.netloc == f'{match[1]}.blob.core.windows.net'
                 and not blob.query and not blob.fragment
                 and re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', container)
                 and REQUEST_ID.fullmatch(data['request_id'])
                 and data['report'].get('request_id') == data['request_id']
                 and report_path == f"reports/{data['request_id']}/report.json"
                 and unquote(blob.path) == '/' + evidence['blob_path'])
    except (ValueError, TypeError):
        valid = False
    if not valid:
        return unavailable('The report source does not match the configured Azure account.')
    # ContainerMenuBlade route verified in Azure Portal; the Blob opens in a context pane.
    url = ('https://portal.azure.com/#view/Microsoft_Azure_Storage/ContainerMenuBlade/~/overview/'
           f'storageAccountId/{quote(resource_id, safe="")}/path/{quote(container, safe="")}')
    return dict(url=url, note='Report container · opens in a new tab.', report_path=report_path)

def snapshot(run):
    with RUNS_LOCK:
        data = asdict(run)
    data['azure_source'] = azure_portal_source(data)
    return data

def event(run, stage, message, source, *, at=None, kind='observed'):
    with RUNS_LOCK:
        run.events.append(dict(sequence=len(run.events) + 1, stage=stage, message=message,
                               source=source, kind=kind, timestamp=at or utc_now(), observed_at=utc_now()))

def update_stage(run, stage_id, status, detail, source, *, at=None):
    with RUNS_LOCK:
        stage = next(s for s in run.stages if s['id'] == stage_id)
        if (stage['status'], stage['detail']) == (status, detail):
            return
        stage.update(status=status, detail=detail, source=source, updated_at=at or utc_now())
        event(run, stage_id, detail, source, at=at, kind=status)

def persist(run):
    folder = RUN_ROOT / run.id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'run.json'
    temp = folder / 'run.json.tmp'
    temp.write_text(json.dumps(snapshot(run), indent=2), encoding='utf-8')
    temp.replace(target)

def finish_run(run, report, evidence=None):
    with RUNS_LOCK:
        run.report = report
        run.status = 'completed'
        run.finished_at = utc_now()
        run.evidence.update(evidence or {})
    persist(run)

def fail_run(run, error, *, observation=False):
    # A reader failure says nothing about the worker's execution outcome.
    with RUNS_LOCK:
        run.status = 'observation_error' if observation else 'failed'
        run.finished_at = utc_now()
        run.error = f'{type(error).__name__}: {error}'[:1500]
        run.recovery = ('The Azure workload may still be running or already completed. Use Check existing request; do not dispatch again.'
                        if observation else 'Inspect the evidence, correct the local error, then start a new local run.')
        for stage in run.stages:
            if stage['status'] == 'running':
                stage.update(status='unverified' if observation else 'failed',
                             detail='Outcome not observed' if observation else 'Local execution failed')
        event(run, 'viewer', run.error, 'Viewer observer' if observation else 'Local Python exception', kind='error')
    persist(run)

def run_replay(run):
    try:
        envelope = load_json(EVIDENCE_ROOT / 'both-checks.json')
        provenance = load_json(EVIDENCE_ROOT / 'provenance.json')
        worker = load_json(EVIDENCE_ROOT / 'worker-log.json')
        report = envelope['report']
        run.actions = report['actions']
        run.evidence.update(label='Recorded Azure evidence', recorded_at=provenance['recorded_at'],
                            routine_run_id=provenance['routine_run']['id'], job_execution=worker['execution'],
                            blob_path='docops-results/reports/docops-both-001/report.json',
                            state_etag=provenance['request_state_etag'], worker_completed_utc=provenance['worker_completed_utc'],
                            report_sha256=hashlib.sha256((EVIDENCE_ROOT / 'both-checks.json').read_bytes()).hexdigest(),
                            hash_scope='Saved report envelope (both-checks.json)')
        ended = datetime.fromtimestamp(provenance['routine_run']['ended_at'], timezone.utc).isoformat()
        update_stage(run, 'routine', 'recorded', 'Routine run finished · saved API record', 'provenance.json', at=ended)
        update_stage(run, 'agent', 'inferred', 'Both actions are present in the saved report', 'both-checks.json', at=provenance['recorded_at'])
        update_stage(run, 'validation', 'inferred', 'Bounded repository and actions match the contract', 'both-checks.json + Python contract', at=provenance['recorded_at'])
        update_stage(run, 'queue', 'inferred', 'Worker received this request · inferred from its log', 'worker-log.json', at=worker['events'][0]['timestamp'])
        update_stage(run, 'job', 'recorded', f"Worker completed · {worker['execution']}", 'worker-log.json', at=provenance['worker_completed_utc'])
        for entry in worker['events']:
            event(run, 'job', json.dumps(entry, ensure_ascii=False), 'Recorded Azure console log', at=entry['timestamp'], kind='recorded')
        if report['request_id'] != run.request_id or report['status'] != 'completed':
            raise ValueError('Recorded report does not match this request')
        update_stage(run, 'report', 'recorded', f"{report['finding_count']} findings · saved completion evidence", 'both-checks.json + provenance.json', at=provenance['recorded_at'])
        finish_run(run, report)
    except Exception as exc:
        fail_run(run, exc)

def run_local(run):
    try:
        from docops.contracts import WorkRequest
        from docops.local import LocalStore
        folder = RUN_ROOT / run.id
        folder.mkdir(parents=True, exist_ok=True)
        update_stage(run, 'routine', 'simulated', 'Manual local trigger · no Foundry Routine', 'Viewer local trigger')
        request_data = load_json(REPOSITORY_ROOT / 'samples' / 'request.json')
        request_data['request_id'] = run.request_id
        (folder / 'request.json').write_text(json.dumps(request_data, indent=2), encoding='utf-8')
        run.actions = request_data['actions']
        update_stage(run, 'agent', 'simulated', 'Two scripted actions · no model call', 'samples/request.json')
        request = WorkRequest.parse(request_data)
        update_stage(run, 'validation', 'completed', 'Contract accepted docs-fixture-v1 and two actions', 'WorkRequest.parse')
        store = LocalStore(folder)
        queued = store.submit(request)
        update_stage(run, 'queue', 'completed', f"SQLite committed request: {queued['status']}", 'LocalStore.submit / work.db')
        update_stage(run, 'job', 'running', 'Python worker running locally · no Azure container', 'LocalStore.run_one')
        report = store.run_one()
        update_stage(run, 'job', 'completed', 'Python worker finished both checks', 'LocalStore.run_one / work.db')
        report_dir = store.export(run.request_id)
        report_file = report_dir / 'report.json'
        # Read the artifact back; do not prove completion with an in-memory result alone.
        report = load_json(report_file)
        update_stage(run, 'report', 'completed', f"Read back report.json · {report['finding_count']} findings", str(report_file))
        finish_run(run, report, dict(label='Local execution · no Azure or LLM',
            job_execution='Local Python worker (no Azure Job)', report_path=str(report_file),
            queue_path=str(store.db), request_path=str(folder / 'request.json'),
            report_sha256=hashlib.sha256(report_file.read_bytes()).hexdigest(), hash_scope='Report file bytes',
            worker_completed_utc=utc_now()))
    except Exception as exc:
        fail_run(run, exc)

def azure_available():
    modules = ['dotenv', 'azure.ai.projects', 'azure.identity', 'azure.storage.blob', 'azure.storage.queue']
    missing = []
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        return False, 'Missing Python packages: ' + ', '.join(missing) + '. Start with start.ps1 or the repository .venv.'
    from dotenv import load_dotenv
    load_dotenv(REPOSITORY_ROOT / '.env')
    missing = [key for key in ['FOUNDRY_PROJECT_ENDPOINT', 'AZURE_STORAGE_ACCOUNT'] if not os.getenv(key)]
    if missing:
        return False, 'Missing configuration: ' + ', '.join(missing)
    return True, 'SDK and configuration present; Azure access is checked before dispatch.'

def observe_store(run, store):
    """Read actual state and exact report bytes; this function never writes to Azure."""
    from azure.core.exceptions import ResourceNotFoundError
    state_blob = store.state_blob(run.request_id)
    try:
        download = state_blob.download_blob()
        request_state = json.loads(download.readall())
    except ResourceNotFoundError:
        update_stage(run, 'report', 'running', 'No committed request found yet', 'Azure Blob request lookup')
        return False
    if request_state.get('request_id') != run.request_id:
        raise ValueError('Stored request ID does not match the inspected request')
    props = download.properties
    run.evidence.update(state_etag=str(props.etag), state_last_modified=props.last_modified.isoformat(),
                        state_status=request_state.get('status'), observed_at=utc_now())
    from docops.contracts import WorkRequest
    bounded = WorkRequest.parse({key: request_state.get(key) for key in
                                 ['schema_version', 'request_id', 'repository_id', 'actions']})
    run.actions = list(bounded.actions)
    update_stage(run, 'agent', 'inferred', 'Requested actions recovered from stored request', 'Azure Blob request state')
    update_stage(run, 'validation', 'inferred', 'Stored request names the bounded repository and actions', 'Azure Blob request state')
    if request_state.get('status') != 'completed':
        update_stage(run, 'queue', 'unverified', 'Request exists; queue delivery is not yet proven', 'Azure Blob request state')
        update_stage(run, 'job', 'unverified', 'Worker completion not yet observed', 'Azure Blob request state')
        return False
    blob_path = f'reports/{run.request_id}/report.json'
    report_download = store.container.download_blob(blob_path)
    raw = report_download.readall()
    report = json.loads(raw)
    if (report.get('request_id') != run.request_id or report.get('status') != 'completed'
            or report.get('repository_id') != bounded.repository_id
            or sorted(report.get('actions', [])) != sorted(bounded.actions)):
        raise ValueError('Report identity or completion status does not match the request')
    update_stage(run, 'queue', 'inferred', 'Delivery inferred from committed worker result', 'Azure Blob completion state')
    update_stage(run, 'job', 'inferred', 'Worker committed completion; execution ID not captured', 'Azure Blob completion state')
    update_stage(run, 'report', 'completed', f"Read report.json from Azure · {report['finding_count']} findings", 'Azure Blob report + completion state', at=report_download.properties.last_modified.isoformat())
    finish_run(run, report, dict(label='Azure evidence read now',
        blob_path=f'{store.container.container_name}/{blob_path}', blob_url=store.container.get_blob_client(blob_path).url,
        report_sha256=hashlib.sha256(raw).hexdigest(), hash_scope='Downloaded Blob bytes',
        report_etag=str(report_download.properties.etag),
        completion_state_last_modified=props.last_modified.isoformat(),
        job_execution='Not captured in this worker report', observed_at=utc_now()))
    return True

def run_azure(run):
    try:
        available, reason = azure_available()
        if not available:
            raise RuntimeError(reason)
        from docops.azure_io import AzureStore
        store = AzureStore()
        # Verify the observer works BEFORE creating external work.
        store.container.get_container_properties()
        event(run, 'viewer', 'Blob read access verified', 'Azure Blob container properties')
        if run.monitor_only:
            update_stage(run, 'routine', 'unverified', 'Existing request lookup · no new dispatch', 'Viewer read-only lookup')
        else:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
            prompt = (f'request_id: {run.request_id}. Repository: docs-fixture-v1. '
                      'Run both documentation checks in one submission: check_links and check_translation_drift. '
                      'The actions list must include both checks.')
            update_stage(run, 'routine', 'running', 'Submitting one explicit Routine dispatch', 'Foundry Routines API')
            with DefaultAzureCredential() as credential, AIProjectClient(
                endpoint=os.environ['FOUNDRY_PROJECT_ENDPOINT'], credential=credential
            ) as project:
                result = project.beta.routines.dispatch(routine_name='docops-maintenance',
                    payload={'type': 'invoke_agent_responses_api', 'input': prompt})
                result = result.as_dict()
            run.evidence['dispatch_receipt'] = result
            run.evidence['dispatched_at'] = utc_now()
            run.evidence['dispatch_id'] = result.get('dispatch_id')
            # Use only a named run identifier returned by the API, never fabricate one.
            run.evidence['routine_run_id'] = result.get('run_id') or result.get('runId')
            update_stage(run, 'routine', 'completed', 'Dispatch accepted · downstream execution not yet verified', 'Foundry Routines API response')
        deadline = time.monotonic() + (20 if run.monitor_only else 180)
        while True:
            if observe_store(run, store):
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('The observation window ended without a committed report. Worker outcome is unknown.')
            time.sleep(3)
    except Exception as exc:
        fail_run(run, exc, observation=True)

def get_run(run_id):
    with RUNS_LOCK:
        if run_id in RUNS:
            return snapshot(RUNS[run_id])
    path = RUN_ROOT / run_id / 'run.json'
    if path.exists():
        return recovered_snapshot(load_json(path))
    return None

def recovered_snapshot(data):
    if data['status'] == 'running':
        data['status'] = 'observation_error'
        data['error'] = 'The viewer restarted before this observation finished.'
        data['recovery'] = 'Inspect the same Azure request without dispatching again.' if data['mode'] == 'azure' else 'Inspect retained local files or load the recording again.'
        for stage in data['stages']:
            if stage['status'] == 'running':
                stage.update(status='unverified', detail='Outcome not observed before restart')
    data['azure_source'] = azure_portal_source(data)
    return data

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def log_message(self, format, *args):
        if '/api/runs/' not in str(args[0] if args else ''):
            print('[viewer] ' + format % args, flush=True)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/health':
            available, reason = azure_available()
            return self.send_json(dict(status='ok', version=2, modes={
                'replay': {'available': True}, 'local': {'available': True},
                'azure': {'available': available, 'reason': reason}}))
        if path == '/api/runs':
            items = {}
            for p in RUN_ROOT.glob('*/run.json'):
                try:
                    items[p.parent.name] = recovered_snapshot(load_json(p))
                except (OSError, ValueError):
                    continue
            with RUNS_LOCK:
                items.update({key: snapshot(run) for key, run in RUNS.items()})
            recent = sorted(items.values(), key=lambda x: x['started_at'], reverse=True)[:20]
            return self.send_json({'runs': [dict(id=x['id'], request_id=x['request_id'], mode=x['mode'], status=x['status'], started_at=x['started_at']) for x in recent]})
        match = re.fullmatch(r'/api/runs/([a-f0-9]{32})(/report)?', path)
        if match:
            run = get_run(match.group(1))
            if not run:
                return self.send_json({'error': 'Run not found'}, 404)
            return self.send_json((run['report'] or {'status': run['status']}) if match.group(2) else run)
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != '/api/runs':
            return self.send_json({'error': 'Not found'}, 404)
        origin = self.headers.get('Origin')
        if origin and origin != f'http://{self.headers.get("Host")}':
            return self.send_json({'error': 'Origin is not this local viewer'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request body size')
            payload = json.loads(self.rfile.read(length))
            mode = payload.get('mode', 'replay')
            if mode not in {'replay', 'local', 'azure'}:
                raise ValueError('mode must be replay, local, or azure')
            monitor_only = payload.get('monitor_only', False)
            if not isinstance(monitor_only, bool):
                raise ValueError('monitor_only must be a boolean')
            if monitor_only and (mode != 'azure' or not payload.get('request_id')):
                raise ValueError('Existing Azure lookup requires a request_id')
            request_id = 'docops-both-001' if mode == 'replay' else (payload.get('request_id') or
                'docops-' + ('local-' if mode == 'local' else 'live-') + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S') + '-' + uuid.uuid4().hex[:6])
            if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
                raise ValueError('Invalid request_id')
            if mode == 'azure':
                available, reason = azure_available()
                if not available:
                    return self.send_json({'error': reason}, 409)
            run = DemoRun(id=uuid.uuid4().hex, mode=mode, request_id=request_id, monitor_only=monitor_only)
            with RUNS_LOCK:
                if any(r.status == 'running' for r in RUNS.values()):
                    return self.send_json({'error': 'Another observation is still in progress'}, 409)
                RUNS[run.id] = run
            persist(run)
            target = {'replay': run_replay, 'local': run_local, 'azure': run_azure}[mode]
            threading.Thread(target=target, args=(run,), daemon=True).start()
            return self.send_json(snapshot(run), 202)
        except (ValueError, TypeError, AttributeError) as exc:
            return self.send_json({'error': str(exc)}, 400)

def main():
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv(REPOSITORY_ROOT / '.env')
    parser = argparse.ArgumentParser(description='Run the execution evidence viewer')
    parser.add_argument('--host', default='127.0.0.1', choices=['127.0.0.1', 'localhost', '::1'])
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not STATIC_ROOT.exists():
        raise SystemExit('Run npm run build in demo-viewer first.')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Execution evidence viewer: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
