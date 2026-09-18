# IRI

한국어 4~10세 대상 모델의 Runpod 학습과 서빙 및 평가 도구와 음성 대화 서비스를 관리한다. 팀원의 [PR #1](https://github.com/peer-problem/iri/pull/1) API를 바탕으로 Peer Design 화면과 마이크 녹음 및 재생을 `web/`에 구현했다. 모델 작업은 `runpod/`에서 진행한다.

## 음성 대화 데모

[배포된 화면](https://iri-voice.vercel.app)을 사용한다. Vercel의 화면에서 Contabo HTTPS API로 연결한다. 참여 코드는 Git에서 제외한 `.keys/.env`의 `DEMO_ACCESS_CODE`에 보관한다. 실제 계정 키는 브라우저에 전달하지 않는다.

기본 흐름은 마이크 녹음 → STT → 인식 문장 확인 또는 수정 → 답변 생성 → TTS 재생이다. 텍스트로도 입력할 수 있고 모든 답변은 화면에 남는다. 재생 중지와 다시 듣기 및 음성 출력 끄기를 지원한다. 녹음은 최대 60초다.

Kanana가 설정한 리비전으로 서빙 중이면 우선 사용한다. 준비되지 않았거나 요청이 실패하면 `gpt-5.6-luna`의 reasoning `high`로 입력 검사부터 출력 검사까지 다시 실행한다. STT는 `gpt-4o-mini-transcribe`, TTS는 `gpt-4o-mini-tts-2025-12-15`를 사용한다. GPU를 자동으로 시작하지 않는다.

TTS는 서버에서 고정한 `coral` 음성을 속도 `0.95`로 사용한다. 어린아이에게 말하듯 천천히, 밝고 따뜻하며 자연스럽게 말하도록 모든 합성 요청에 같은 지시를 적용한다. 로컬에서 비교 실험할 때만 `.keys/.env`의 `TTS_SPEED` 또는 `TTS_INSTRUCTIONS`를 변경한다.

브라우저 세션에는 최근 6턴을 서버 메모리에 보관한다. 새 이야기와 연령 변경 및 로그아웃으로 해당 문맥을 삭제한다. 세션은 1시간 뒤 만료되며 만료 자료는 30초 간격으로 정리한다. 녹음과 대화를 디스크에 저장하지 않으며 외부 AI 서비스의 처리는 별도다.

로컬 실행은 터미널 두 개에서 다음 명령을 실행한다.

```sh
runpod/.venv/bin/uvicorn api.app.app:app --host 127.0.0.1 --port 8000
```

```sh
npm ci --prefix web
npm run dev --prefix web
```

화면은 http://127.0.0.1:5173 에서 연다. API 설정은 `.keys/.env`를 읽는다. 배포와 롤백은 [운영 안내](api/deploy/README.md)를 참고한다.

## 현재 상태

Phase 2는 종료했다. 다음 단계 모델은 `kakaocorp/kanana-2-3b-instruct` 원본이며 리비전은 `6a5d7889964c4c590299d16e309eabab1f73f8a9`다. 이번 QLoRA 어댑터는 품질 향상이 확인되지 않아 채택하지 않았다.

Phase 3에서는 모델 품질 개선과 독립 평가 및 모델 운영 인수인계를 진행한다. RTX 3090에서 두 번째 비교 800건을 완료했으며 실행 오류는 0건이다. 후보는 지원 대응과 안전 검사 및 지연 기준을 충족하지 못해 기본값 `baseline`을 유지한다.

이후 재현성 진단 180회와 추가 비교 400건을 완료했다. 재현성 옵션을 적용한 두 평가의 raw 응답 100개는 모두 일치했다. 안전 후보는 지원 대응과 지연 기준 미충족으로 계속 미채택이다.

- [Phase 3 첫 구현과 GPU 비교 결과](runpod/artifacts/phase3-quality-20260917/README.md)
- [Phase 3 두 번째 비교와 미해결 문제](runpod/artifacts/phase3-quality-v3-20260917/README.md)
- [Phase 3 재현성 진단과 재평가](runpod/artifacts/phase3-repro-20260917/README.md)
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

초기화는 `.keys/.env`에 서로 다른 제품 API 인증키 `SANDBOX_API_KEY`와 모델 서버 인증키 `MODEL_API_KEY`를 생성하며 기존 파일은 덮어쓰지 않는다. 이 파일의 `MODEL_REVISION`을 위 리비전으로 설정하고, SSH 터널로 연결한 vLLM 서버 주소를 `MODEL_BASE_URL`에 지정한다. 원본 사용 시 `ADAPTER_NAME`은 비워 둔다. `.keys/`는 Git에 포함하지 않는다. `runpod.operations.doctor --online`으로 모델 연결을 확인할 수 있다.

### 팀원 음성 API 실행

기존 `.keys/.env`를 사용한다면 `SANDBOX_API_KEY`가 32자 이상인지 확인한다. 음성 전사와 TTS에는 `OPENAI_API_KEY`가 필요하며 텍스트 모델은 Runpod의 vLLM을 사용한다. 기본 행동 설정은 `baseline`이다. Runpod의 v3 후보는 미채택 실험이며 팀원 API에 자동 적용하지 않았다.

```sh
runpod/.venv/bin/uvicorn api.app.app:app --host 127.0.0.1 --port 8000
```

내부 클라이언트는 `Authorization: Bearer <SANDBOX_API_KEY>` 인증을 사용한다. 제품 화면은 참여 코드로 발급받은 HttpOnly 세션 쿠키를 사용한다.

| 경로 | 요청 | 응답 |
| --- | --- | --- |
| `POST /transcribe` | 지원 음성 형식의 원본 바이트. `Content-Type`과 `X-Audio-Consent: true` 지정 | `text`와 `requires_confirmation` |
| `POST /chat` | 확인한 전사문의 `message`와 `age_band` (`4-6` 또는 `7-10`) | `answer`, `action`, `request_id` |
| `POST /speech` | `/chat`이 반환한 `answer`를 `text`로 전송 | MP3 바이트 |

화면이 전사문 확인 후 `/chat`을 호출하고 받은 답변을 `/speech`로 전달한다. 데모 세션은 최근 검사된 답변만 음성으로 읽을 수 있다. 내부 Bearer 클라이언트는 검사된 답변만 전송해야 한다. 실제 OpenAI STT와 TTS 및 Luna 대체 응답을 확인했다. 개인 기기의 마이크와 스피커 품질 검증은 별도로 필요하다.

### AnswerProfile v1

아이에게 보여 주는 답변의 정체성과 말투 및 상황별 대응은 `api/app/answer_profile.py`의 단일 `ANSWER_PROFILE`에서 관리한다. 현재 버전은 `v1`이며 Kanana와 Luna의 답변 생성 단계에 똑같이 적용된다. Luna가 별도의 정체성이나 말투 지침을 덧붙이지 않는다.

처리 순서는 입력 안전 검사 → 공통 AnswerProfile을 적용한 답변 생성 → 출력 안전 검사다. AnswerProfile은 생성 단계에만 적용하며 `api/configs/policy.json`, 입력 판정과 출력 차단 규칙 및 기본 `behavior_profile=baseline`은 그대로 유지한다. 프로필의 대표 예시는 행동 유도용이며 개발 또는 최종 평가의 정답으로 재사용하지 않는다.

## GPU 실행과 평가

모델 서빙은 NVIDIA GPU Linux 환경에서 `runpod/requirements-gpu.txt`의 vLLM 버전을 사용한다. 로컬 개발과 검수에는 GPU가 필요 없다. GPU 실행 전에 비용과 중지 시한을 정하고 결과 저장 후 실제 Pod 중지를 확인한다.

```sh
python -m runpod.operations.serve_model
python -m runpod.operations.evaluate --data runpod/artifacts/phase2-evaluation-20260917/base-run/dataset.jsonl --mode both
```

서빙과 평가 명령은 각각 별도 터미널에서 실행한다. 안전 검사에는 JSON schema 지원이 필요하다. 검증되지 않은 결과를 허용하기 위한 비구조화 판정으로의 자동 대체는 하지 않는다. 기존 400건은 변경 전 코드의 결과이며 최신 코드의 GPU 검증을 대신하지 않는다.

### Phase 3 품질 비교

`BEHAVIOR_PROFILE`로 모델 검사 설정을 선택한다. 평가에서는 `--behavior-profile`로 같은 설정을 지정한다.

| 설정 | 기준선에서 바뀌는 내용 |
| --- | --- |
| `baseline` | 기존 입력·출력 안전 검사 설정. AnswerProfile v1은 모든 설정에 공통 적용 |
| `input_v2` | 피해 고백 우선 분류와 불필요한 재질문 축소 |
| `support_v2` | `input_v2`에 상황별 지원 답변 생성과 출력 검사 추가 |
| `full_v2` | `support_v2`에 사실 정확도와 간결한 설명 지침 추가 |
| `input_v3` | 기존 정책을 유지하며 피해 주체와 실행 의도 및 현실 위험을 분류 |
| `support_v3` | `input_v3`에 상황별 지원 생성과 비밀 보장 약속 금지 지침 추가 |
| `safety_v3` | `support_v3`에 현실 위험 행동과 지원 답변의 출력 검사 보완 |

지원 답변이 출력 검사에서 차단되면 안전한 지원 문구로 돌아간다. 피해 고백을 위험 요청으로 바꾸어 표시하지 않는다.

```sh
python -m runpod.operations.quality_experiment \
  --data runpod/artifacts/phase2-evaluation-20260917/base-run/dataset.jsonl \
  --output runpod/runs/quality-comparison
```

네 설정 각각 동일한 개발 100문항을 raw와 guarded로 실행한다. 미검수 초안은 실행 전에 거부하며 결과 파일의 해시와 문항별 실행 쌍을 검사한다. 출력 폴더는 새 경로를 사용한다. `runpod/data/dev.jsonl`은 초안이므로 위의 동결된 검수본을 사용한다. 기대 행동 일치율은 정답률이나 유해 노출률을 대신하지 않는다.

새 후보를 단계별로 비교하려면 `--profiles baseline input_v3 support_v3 safety_v3`를 지정한다. 입력 판정, 지원 생성, 출력 검사를 하나씩 추가한다. GPU는 RTX 3090 또는 RTX A5000을 우선 사용한다.

### 응답 재현성 진단

같은 온도와 seed를 지정해도 서버의 반복 응답이 같다고 가정하지 않는다. `serve_model`의 `--prefix-caching on|off`로 캐시 여부를 지정하고, `--batch-invariant`로 vLLM 재현성 옵션을 켤 수 있다. 기본 실행 옵션은 유지하며 선택한 옵션을 GPU 환경 기록에 남긴다.

```sh
python -m runpod.operations.serve_model --prefix-caching on --batch-invariant
```

별도 터미널에서 아래의 `<실행폴더>`를 서버가 출력한 환경 기록 폴더로 바꾼다. 출력은 새 경로를 사용한다.

```sh
python -m runpod.operations.repeatability \
  --data runpod/artifacts/phase3-quality-v3-20260917/baseline-run/dataset.jsonl \
  --launch-record 'runpod/runs/<실행폴더>/gpu-environment.json' \
  --output runpod/runs/repeatability-probe
```

이 도구는 검수된 개발 자료에서 범주별로 고정한 20개 질문의 첫 턴을 세 번씩 보낸다. 두 번째 패스는 역순이며 실제 요청과 응답의 해시를 보관한다. 오류가 있거나 요청이 달라지면 반복 성공으로 집계하지 않는다. 작은 표본의 일치는 전체 의미 품질이나 모든 실행의 결정성을 보장하지 않는다. [vLLM의 재현성 안내](https://docs.vllm.ai/en/v0.29.0/usage/reproducibility/)를 함께 확인한다.

## 자료 보관

`api/`는 팀원의 제품 HTTP 서버와 전사 및 TTS를 포함한다. API 정책은 `api/configs/policy.json`에 둔다. `runpod/inference/`는 독립적인 모델 평가와 실험용 입력 및 출력 검사를 담당하며 정책은 `runpod/configs/policy.json`에 둔다. 공유 결과와 검수 자료는 `runpod/artifacts/`에서 Git으로 관리한다. 원본 가중치와 재개용 백업은 Git에서 제외한 `runpod/backups/`에 보관한다. 팀 검수 패킷의 `private/mapping.json`도 공유되므로 검수자는 먼저 자기 `reviewer_a/` 또는 `reviewer_b/`의 자료만 보고 판정한다.

과거 평가 결과와 소스 백업은 실행 당시 증거로 보존한다. 하네스 삭제 기록은 해당 실행 시점의 상태이며 현재 API는 PR #1 통합으로 복원됐다. API와 Runpod 정책은 복원 시점에 내용이 같으며 이후 변경은 각 경로의 검증 결과와 함께 관리한다.
