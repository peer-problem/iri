# IRI

한국어 4~10세 대상 모델의 응답 생성과 안전 검사, 학습 및 평가 도구다. 현재 API는 성인 팀 내부 검증용 단일 턴 API다.

## 현재 상태

Phase 2는 종료했다. 다음 단계 모델은 `kakaocorp/kanana-2-3b-instruct` 원본이며 리비전은 `6a5d7889964c4c590299d16e309eabab1f73f8a9`다. 이번 QLoRA 어댑터는 품질 향상이 확인되지 않아 채택하지 않았다.

Phase 3의 첫 작업은 입력 판정과 피해 지원, 답변 정확도를 개선하는 비교 실험이다. 개선 설정은 선택해서 실행하며 기본값은 검증 전 후보를 자동 적용하지 않는 `baseline`이다.

- [Phase 3 첫 구현과 GPU 비교 결과](runpod/artifacts/phase3-quality-20260917/README.md)
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
python -m runpod.operations.evaluate --data runpod/artifacts/phase2-evaluation-20260917/base-run/dataset.jsonl --mode both
```

서빙과 평가 명령은 각각 별도 터미널에서 실행한다. 안전 검사에는 JSON schema 지원이 필요하다. 검증되지 않은 결과를 허용하기 위한 비구조화 판정으로의 자동 대체는 하지 않는다. 기존 400건은 변경 전 코드의 결과이며 최신 코드의 GPU 검증을 대신하지 않는다.

### Phase 3 품질 비교

`BEHAVIOR_PROFILE`로 API 설정을 선택한다. 평가에서는 `--behavior-profile`로 같은 설정을 지정한다.

| 설정 | 기준선에서 바뀌는 내용 |
| --- | --- |
| `baseline` | 기존 정책과 고정 피해 지원 문구 |
| `input_v2` | 피해 고백 우선 분류와 불필요한 재질문 축소 |
| `support_v2` | `input_v2`에 상황별 지원 답변 생성과 출력 검사 추가 |
| `full_v2` | `support_v2`에 사실 정확도와 간결한 설명 지침 추가 |

지원 답변이 출력 검사에서 차단되면 안전한 지원 문구로 돌아간다. 피해 고백을 위험 요청으로 바꾸어 표시하지 않는다.

```sh
python -m runpod.operations.quality_experiment \
  --data runpod/artifacts/phase2-evaluation-20260917/base-run/dataset.jsonl \
  --output runpod/runs/quality-comparison
```

네 설정 각각 동일한 개발 100문항을 raw와 guarded로 실행한다. 미검수 초안은 실행 전에 거부하며 결과 파일의 해시와 문항별 실행 쌍을 검사한다. 출력 폴더는 새 경로를 사용한다. `runpod/data/dev.jsonl`은 초안이므로 위의 동결된 검수본을 사용한다. 기대 행동 일치율은 정답률이나 유해 노출률을 대신하지 않는다.

## 자료 보관

`api/`는 HTTP API, `runpod/`는 학습과 평가를 담당한다. 공유 결과와 검수 자료는 `runpod/artifacts/`에서 Git으로 관리한다. 원본 가중치와 재개용 백업은 Git에서 제외한 `runpod/backups/`에 보관한다. 팀 검수 패킷의 `private/mapping.json`도 공유되므로 검수자는 먼저 자기 `reviewer_a/` 또는 `reviewer_b/`의 자료만 보고 판정한다.
