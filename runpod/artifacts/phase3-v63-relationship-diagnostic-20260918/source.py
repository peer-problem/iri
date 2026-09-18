"""Frozen V63 end-to-end relationship diagnostic; no runtime changes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

BASE=Path('/workspace/iri-personal-20260918')
OUT=BASE/'v63-relationship-diagnostic-01'
SRC=BASE/'v63-baseline-ratio-02/src'

async def main():
    os.chdir(SRC)
    sys.path.insert(0,str(SRC))
    for key in list(os.environ):
        if key.startswith(('MODEL_','ADAPTER_','BEHAVIOR_','VLLM_')) or key=='RUNPOD_API_KEY':del os.environ[key]
    receipt=json.loads((OUT/'receipt.json').read_text())
    for name,expected in receipt['runtime_files'].items():
        assert hashlib.sha256((SRC/name).read_bytes()).hexdigest()==expected,name
    assert hashlib.sha256((OUT/'cases.json').read_bytes()).hexdigest()==receipt['data_sha256']
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==receipt['source_sha256']
    import httpx
    from runpod.inference.provider import ModelProvider
    from runpod.inference.service import ChatService
    from runpod.inference.trace import TurnTrace
    from runpod.settings import Settings
    settings=Settings(behavior_profile='legacy_harm_v63')
    assert settings.model_revision=='6a5d7889964c4c590299d16e309eabab1f73f8a9'
    assert settings.adapter_name=='' and settings.model_base_url=='http://127.0.0.1:8002/v1'
    rows=[]
    async with httpx.AsyncClient(trust_env=False) as client:
        provider=ModelProvider(settings,client)
        assert await provider.ready()
        service=ChatService(provider)
        for case in json.loads((OUT/'cases.json').read_text()):
            history=[]
            turns=[]
            error=None
            for question in case['inputs']:
                history.append({'role':'user','content':question})
                trace=TurnTrace()
                start=time.monotonic()
                answer=None
                action=None
                try:
                    async with asyncio.timeout(settings.request_timeout_seconds):
                        answer,action=await service.respond(case['age_band'],history,trace=trace)
                    history.append({'role':'assistant','content':answer})
                except Exception as exc:
                    error={'type':type(exc).__name__,'code':getattr(exc,'code',None)}
                turns.append({'question':question,'answer':answer,'action':action,'seconds':time.monotonic()-start,'trace':trace.snapshot(),'error':error})
                if error:break
            rows.append({'id':case['id'],'pair_id':case['pair_id'],'category':case['category'],'age_band':case['age_band'],'expected_action':case['expected_action'],'turns':turns,'error':error})
            (OUT/'partial.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
            print(case['id'],turns[-1]['action'],'error' if error else '',flush=True)
            if sum(bool(r['error']) for r in rows)>=3:raise RuntimeError('three_errors_abort')
    (OUT/'diagnostic.json').write_text(json.dumps({'state':'completed','profile':'legacy_harm_v63','mode':'guarded','review_status':'draft','rows':rows,**receipt},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':asyncio.run(main())
