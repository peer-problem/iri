# V16·V25·V50·V63 실행 안내

V63의 코드 구조·검사 순서·최신 측정 한계를 먼저 보려면 [V63 코드 검토 안내](V63_REVIEW.md)를 참고한다.

네 버전 모두 같은 `kakaocorp/kanana-2-3b-instruct`를 사용한다. 차이는 지침과 검사 절차이며, 별도 학습 가중치나 어댑터가 필요하지 않다. 저장소를 복제한 팀원도 GPU와 아래 환경을 준비하면 실행할 수 있다.

| 버전 | 프로필 | 사용 목적 |
| --- | --- | --- |
| [V16](artifacts/phase3-v16-full-20260918/REPRODUCE.md) | `output_v16` | 비교·복귀 기준 |
| [V25](artifacts/phase3-v25-full-20260918/REPRODUCE.md) | `boundary_v25` | 예시 추가와 일반화 회귀를 재현하는 미채택 실험 |
| [V50](artifacts/phase3-v50-full-20260918/REPRODUCE.md) | `harm_audit_v50` | 비JSON 재검사 규약 위반을 보존한 역사적 실험 |
| [V63](artifacts/phase3-v63-full-20260918/REPRODUCE.md) | `legacy_harm_v63` | 엄격한 JSON 재검사를 쓰는 후속 개발 후보 |

서비스 기본값은 `baseline`이다. V50은 과거 결과의 재현을 위해 선택 가능하게 보관하며 서비스 채택 대상으로 해석하지 않는다. 평가 문항 ID나 정답을 조회하는 런타임 분기는 없다.

## 1. 새 PC에서 준비

Git, Python 3.12와 uv가 필요하다. Windows에서도 평가 클라이언트와 테스트를 실행할 수 있다. 모델 서빙은 Linux NVIDIA GPU 환경에서 실행한다. 원래 실험은 VRAM 24GB의 RTX 3090을 사용했다.

```console
git clone --branch fix/child-safety-guards https://github.com/peer-problem/iri.git
cd iri
uv sync --project runpod --frozen
uv run --project runpod python -X utf8 -m runpod.operations.init_local
```

이후 모든 명령은 `iri` 저장소 루트에서 실행한다. 초기화 도구가 만든 `.keys/.env`는 Git에서 제외되며, 기존 파일은 덮어쓰지 않는다. 생성된 `MODEL_API_KEY`를 유지하고 아래 설정을 편집한다.

```dotenv
MODEL_PROFILE=kanana
MODEL_REVISION=6a5d7889964c4c590299d16e309eabab1f73f8a9
MODEL_BASE_URL=http://127.0.0.1:8002/v1
ADAPTER_NAME=
BEHAVIOR_PROFILE=baseline
```

모델 파일은 고정 리비전으로 Hugging Face에서 내려받는다. 접근 인증이 필요한 환경에서는 자신의 `HF_TOKEN`을 같은 비공개 파일에 설정한다. GPU를 직접 준비했다면 Runpod 계정이나 Runpod API 키는 필요하지 않다.

## 2. GPU 서버에서 모델 실행

GPU 서버에도 같은 브랜치를 복제하고 위 초기화를 수행한다. GPU와 평가 클라이언트의 `MODEL_API_KEY` 값은 같아야 한다. 서버의 `MODEL_REVISION`도 위의 전체 SHA로 고정한다.

다음 명령은 **Linux GPU 서버의 저장소 루트**에서 실행한다. NVIDIA 드라이버가 동작하는지 `nvidia-smi`로 먼저 확인한다.

```console
uv venv --python 3.12 .venv-gpu
uv pip install --python .venv-gpu/bin/python -r runpod/requirements-gpu.txt
uv pip install --python .venv-gpu/bin/python "pydantic-settings>=2.7,<3" "httpx>=0.28,<1"
.venv-gpu/bin/python -X utf8 -m runpod.operations.serve_model --prefix-caching on --batch-invariant
```

런처는 vLLM 0.29.0, BF16, 최대 문맥 4096, 동시 시퀀스 1, eager 실행을 사용한다. 생성은 `temperature=0`, `seed=42`, 최대 384토큰이며 검사는 최대 80토큰이다. 모델과 tokenizer 리비전은 같다. 실제 GPU 정보와 설치 패키지는 `runpod/runs/gpu-*`에 기록된다. 원래 환경은 각 보고서의 `results/gpu-environment.json`을 참고한다.

원격 GPU를 쓸 때는 로컬 PC의 별도 터미널에서 아래 SSH 터널을 유지한다. 대문자로 적힌 값은 자신의 서버 접속 정보로 바꾼다.

```console
ssh -N -L 8002:127.0.0.1:8002 -p SSH_PORT -i PATH_TO_PRIVATE_KEY USER@GPU_HOST
```

서버가 같은 PC의 Linux 환경이라면 터널 없이 연결할 수 있다. 모델 서버는 localhost에 바인딩되므로 원격 주소를 그대로 HTTP URL에 넣는 대신 터널을 사용한다. 연결 포트를 바꿨다면 클라이언트의 `MODEL_BASE_URL`도 맞춘다.

## 3. 후보 실행 및 결과 확인

위 표의 각 버전 안내에 **고정된 개발 100문항 경로와 전체 실행 명령**이 있다. `--behavior-profile`은 이번 평가에만 적용된다. 먼저 `--limit 2`로 연결을 확인하고 전체 평가를 실행한다.

검사 단계가 포함된 비교에는 `--mode guarded --trace-stages`를 사용한다. 결과 폴더의 `results.jsonl`, `summary.json`, `metadata.json`, `stage-traces.jsonl`을 함께 확인한다. V50 재검사는 예외적으로 JSON schema 없이 단어를 받으며 새 메타데이터에도 이를 기록한다.

다른 GPU에서 과거 점수나 지연의 완전한 일치를 보장하지 않는다. 공개를 위한 코드 정리에서는 동결 소스와의 모델 요청·분기·오류 동등성을 검증했으며 GPU 전체 평가를 새로 수행하지 않았다. 기존 점수는 행동 일치이고, 생성 답변의 내용 안전성과 독립 검수 완료를 뜻하지 않는다.

## 4. GPU 없이 코드 확인

```console
uv run --project runpod python -X utf8 -m pytest -c runpod/pyproject.toml runpod/tests/test_selected_profiles.py runpod/tests/test_behavior_v10.py runpod/tests/test_stage_trace.py -q
uv run --project runpod python -X utf8 -m runpod.operations.evaluate --help
```

선택 프로필 테스트는 각 버전의 동결 소스에서 얻은 요청·분기 해시와 비교한다. 모의 모델 응답을 사용하므로 실제 생성 성능 평가는 아니다. 전체 테스트 중 기존 POSIX 파일 권한·심볼릭 링크·줄바꿈 가정이 있는 검수 도구 테스트는 Windows에서 실패할 수 있다. 해당 한계와 이번 변경의 검증 결과는 [공개 검증 기록](SELECTED_PROFILES_VALIDATION.md)에 구분해서 기록한다.
