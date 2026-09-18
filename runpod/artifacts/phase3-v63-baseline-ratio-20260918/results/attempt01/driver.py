"""Run the published baseline and V63 on one unchanged model server."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

BASE = Path('/workspace/iri-personal-20260918')
ROUND = BASE / 'v63-baseline-ratio-01'
SRC = ROUND / 'src'
STATE = {'state': 'preparing', 'started_at': time.time(), 'source_commit': '8c9a3965ef1ec38127cf77f51fe1beb8b1a0e4bf', 'runs': {}}

def save():
    STATE['updated_at'] = time.time()
    target = ROUND/'state.json'
    pending = target.with_suffix('.tmp')
    pending.write_text(json.dumps(STATE, indent=2))
    pending.replace(target)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

async def main():
    receipt = json.loads((ROUND/'receipt.json').read_text())
    assert digest(ROUND/'source.zip') == receipt['source_sha256']
    with zipfile.ZipFile(ROUND/'source.zip') as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            assert (SRC/name).resolve().is_relative_to(SRC.resolve()) and '\\' not in name
            assert '.keys' not in Path(name).parts
        archive.extractall(SRC)
    # Reuse only localhost model auth; never copy the Runpod account credential.
    (SRC/'.keys').mkdir(mode=0o700)
    shutil.copyfile(BASE/'src/.keys/.env', SRC/'.keys/.env')
    (SRC/'.keys/.env').chmod(0o600)
    for path in (BASE/'src/runpod/runs').glob('gpu-*'):
        shutil.copytree(path, SRC/'runpod/runs'/path.name)
    sys.path.insert(0, str(SRC))
    os.chdir(SRC)
    from runpod.operations.evaluate import evaluate
    from runpod.operations.quality_experiment import verify_stage_traces
    from runpod.settings import Settings
    settings = Settings()
    assert settings.model_revision == '6a5d7889964c4c590299d16e309eabab1f73f8a9'
    assert settings.adapter_name == '' and settings.model_base_url == 'http://127.0.0.1:8002/v1'
    data = SRC/'runpod/artifacts/phase3-v63-full-20260918/full100/legacy_harm_v63/20260918T043434Z-kanana-ef6530db/dataset.jsonl'
    assert digest(data) == '026c3c85fa2ab1622e721f2a5d70cb3f6194ba10869e3465b581f6cd68371297'
    packages = subprocess.check_output([sys.executable,'-m','pip','freeze']).decode()
    (ROUND/'gpu-packages.txt').write_text(packages)
    gpu = subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,driver_version,memory.total','--format=csv,noheader']).decode().strip()
    STATE.update(state='running', gpu=gpu, dataset_sha256=digest(data), order=['baseline','legacy_harm_v63'], warmup_scenarios_per_profile=2, expected_scored_rows=200)
    save()
    for phase, limit in [('warmup',2),('full100',None)]:
        for profile in STATE['order']:
            STATE.update(active_phase=phase, active_profile=profile)
            save()
            out = ROUND/phase/profile
            args=argparse.Namespace(data=data, output=out, mode='guarded', allow_draft=False,limit=limit,adapter_run=None,behavior_profile=profile,trace_stages=True)
            code=await evaluate(args)
            files=list(out.glob('*/metadata.json'))
            assert len(files)==1
            run=files[0].parent
            meta=json.loads(files[0].read_text())
            rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
            assert code==0 and len(rows)==(limit or 100)
            assert len({r['id'] for r in rows})==len(rows)
            assert all(not r['error'] and r['mode']=='guarded' for r in rows)
            assert digest(run/'results.jsonl')==meta['results_sha256']
            verify_stage_traces(run,meta,rows)
            STATE['runs'][phase+'/'+profile]={'path':run.relative_to(ROUND).as_posix(),'results_sha256':meta['results_sha256'],'summary':json.loads((run/'summary.json').read_text())}
            save()
    base=STATE['runs']['full100/baseline']['summary']['guarded/all']['p95_seconds']
    candidate=STATE['runs']['full100/legacy_harm_v63']['summary']['guarded/all']['p95_seconds']
    STATE.update(state='completed', p95_ratio=candidate/base, criterion_limit=1.25, criterion_pass=candidate/base<=1.25, finished_at=time.time())

if __name__ == '__main__':
    save()
    try:
        asyncio.run(main())
    except BaseException as exc:
        STATE.update(state='failed', error_type=type(exc).__name__)
        raise
    finally:
        save()
