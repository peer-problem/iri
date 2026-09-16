# IRI

한국어 4~10세 대상 모델의 응답 생성과 안전 검사, 학습 및 평가 도구다. 현재 API는 성인 팀 내부 검증용 단일 턴 API다.

## 현재 상태

Phase 2는 종료했다. 다음 단계 모델은 `kakaocorp/kanana-2-3b-instruct` 원본이며 리비전은 `6a5d7889964c4c590299d16e309eabab1f73f8a9`다. 이번 QLoRA 어댑터는 품질 향상이 확인되지 않아 채택하지 않았다.

- [Phase 2 종료 보고서](runpod/artifacts/phase2-evaluation-20260917/README.md)
- [전체 검토와 보완 내역](runpod/artifacts/phase2-evaluation-20260917/audit.md)
- [Phase 3 인수인계](runpod/artifacts/phase2-evaluation-20260917/phase3-handoff.md)
- [팀 검수 자료](runpod/artifacts/README.md)

## 로컬 개발

저장소 루트에서 실행한다. Python 3.12와 uv가 필요하다.

```sh
uv sync --project runpod --frozen
runpod/.venv/bin/python -m runpod.operations.init_local
runpod/.venv/bin/python -m pytest -q -c runpod/pyproject.toml
runpod/.venv/bin/ruff check --config runpod/pyproject.toml api runpod
```

초기화는 `.keys/.env`에 별도 API 인증키를 생성하며 기존 파일은 덮어쓰지 않는다. 이 파일의 `MODEL_REVISION`을 위 리비전으로 설정하고, SSH 터널로 연결한 모델 서버 주소를 `MODEL_BASE_URL`에 지정한다. 원본 사용 시 `ADAPTER_NAME`은 비워 둔다. `.keys/`는 Git에 포함하지 않는다.

```sh
runpod/.venv/bin/python -m uvicorn api.app.app:app --host 127.0.0.1 --port 8000
```

`GET /health`는 설정 상태만 확인한다. 모델 연결은 인증된 `GET /ready`로 확인한다. `POST /chat`은 `Authorization: Bearer <SANDBOX_API_KEY>`와 `{"age_band":"4-6","message":"비는 왜 내려?"}`를 받는다. 연령은 `4-6` 또는 `7-10`이다. 대화 기록은 요청 사이에 저장하지 않는다.

## GPU 실행과 평가

모델 서빙은 NVIDIA GPU Linux 환경에서 `runpod/requirements-gpu.txt`의 vLLM 버전을 사용한다. 로컬 개발과 검수에는 GPU가 필요 없다. GPU 실행 전에 비용과 중지 시한을 정하고 결과 저장 후 실제 Pod 중지를 확인한다.

```sh
python -m runpod.operations.serve_model
python -m runpod.operations.evaluate --data runpod/data/dev.jsonl --mode both
```

서빙과 평가 명령은 각각 별도 터미널에서 실행한다. 안전 검사에는 JSON schema 지원이 필요하다. 검증되지 않은 결과를 허용하기 위한 비구조화 판정으로의 자동 대체는 하지 않는다. 기존 400건은 변경 전 코드의 결과이며 최신 코드의 GPU 검증을 대신하지 않는다.

## 자료 보관

`api/`는 HTTP API, `runpod/`는 학습과 평가를 담당한다. 공유 결과와 검수 자료는 `runpod/artifacts/`에서 Git으로 관리한다. 원본 가중치와 재개용 백업은 Git에서 제외한 `runpod/backups/`에 보관한다. 팀 검수 패킷의 `private/mapping.json`도 공유되므로 검수자는 먼저 자기 `reviewer_a/` 또는 `reviewer_b/`의 자료만 보고 판정한다.
