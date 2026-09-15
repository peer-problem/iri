# 아동용 LLM 샌드박스

4~10세를 위한 한국어 대화 모델의 기본 성능과 안전성 검사 흐름을 비교하는 팀 내부 개발 프로젝트다.

현재 범위: 텍스트 API와 평가 도구. 추가로 음성 업로드 API 및 QLoRA 실행 코드를 준비했다. 실제 모델 응답, 유료 음성 인식과 GPU 학습은 아직 실행하지 않았다. 아동용 화면은 후속 단계다.

## 로컬 시작

Python 3.12와 [uv](https://docs.astral.sh/uv/)를 사용한다.

```bash
uv sync --frozen
uv run python -m scripts.init_local
uv run pytest
uv run python -m scripts.data --phase-one
uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

`.env`가 이미 있으면 init_local은 덮어쓰지 않는다. API 설명은 `http://127.0.0.1:8000/docs`에 있다. Authorize에 로컬 `.env`의 `SANDBOX_API_KEY`를 입력한다. 모델 연결 전 `/health`는 unconfigured이며 `/chat`은 503을 반환한다.

## 계정 준비와 협업

Runpod 계정과 결제 수단을 준비한다. Hugging Face에서 Gemma 3 4B 이용 조건에 동의하고 다운로드용 토큰을 로컬 `.env`에 `HF_TOKEN`으로 저장한다. Pod 생성과 실제 GPU 연결은 준비 완료 후 진행한다. OpenAI 키는 후속 음성 단계에서 필요하다.

코드는 GitHub 비공개 저장소에서 작업별 브랜치와 PR로 합친다. 학습한 어댑터는 후속 단계에 Hugging Face로 공유한다. `.env`, 모델 가중치와 실행 결과는 Git에 올리지 않는다. 이번 구현에서 원격 저장소 생성이나 push는 하지 않았다.

### 팀 합류 안내

저장소를 공유받으면 위의 로컬 시작 명령부터 실행한다. API 개발과 자동 테스트에는 GPU나 유료 API 키가 필요하지 않다. 각자 init_local로 개발용 키를 생성하고 개인 `.env`를 사용한다.

현재 구현한 범위는 인증된 텍스트 API, 안전성 검사 흐름, 음성 업로드 API와 평가 및 QLoRA 실행 도구다. 자동 테스트는 78개이며 실제 모델 성능과 아동 적합성을 검증한 결과는 아니다. Runpod 연결과 실제 모델 비교는 아직 진행하지 않았다.

다음 작업은 아래 단위로 담당자를 정하면 된다. 같은 파일을 동시에 바꾸기 전에 담당자끼리 조율한다.

| 작업 | 주로 수정할 위치 | 다음 결과물 |
|---|---|---|
| 화면과 음성 입력 | 새 프런트엔드 디렉터리 | 연령 선택, 입력, 인식문 확인과 답변 화면 |
| API와 검사 흐름 | backend/, configs/policy.json | 실제 모델을 연결한 요청과 오류 처리 검증 |
| 데이터 검수 | data/, scripts/candidate_review.py | 연령별로 사람이 승인한 질문과 답변 |
| GPU 실행과 평가 | scripts/serve_model.py, scripts/evaluate.py | Kanana와 Gemma 응답 및 지연 비교 |

`POST /chat`의 입력은 `age_band`와 `message`다. 연령 값은 `4-6` 또는 `7-10`이다. 응답은 `answer`, `action`, `request_id`를 반환한다. 상세 계약은 로컬 `/docs`와 `backend/schemas.py`를 기준으로 맞춘다.

```bash
# 공유 저장소의 main을 받은 뒤 작업별 브랜치 생성
git switch -c feat/작업명
# 작업 후 로컬 검사
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m scripts.data --phase-one
```

PR에는 변경 이유와 검증 결과를 적고 다른 팀원의 검토를 받은 뒤 main에 합친다. 원본 데이터와 검수 CSV는 Git에서 제외되므로 데이터 담당자는 아래 확보 명령으로 생성한다. 실제 아동 대화나 개인 정보가 담긴 파일은 저장소에 추가하지 않는다.

공유 전에 정할 항목은 비공개 GitHub 저장소의 소유자와 작업별 담당자다. GPU 작업은 한 명이 관리하며 실행할 때만 Pod를 켜고 종료 후 Stopped 상태를 확인한다.

## 모델 실행과 평가

로컬에서 `uv run python -m scripts.resolve_model kanana`로 모델 리비전을 확인한다. 출력된 MODEL_PROFILE과 MODEL_REVISION을 로컬 및 GPU의 `.env`에 반영하고 MODEL_API_KEY도 일치시킨다. GPU에는 HF_TOKEN을 별도로 설정한다.

```bash
# Linux NVIDIA GPU의 프로젝트 디렉터리에서
uv venv .venv-gpu --python 3.12
uv pip install --python .venv-gpu/bin/python -r pyproject.toml -r requirements-gpu.txt
.venv-gpu/bin/python -m scripts.serve_model

# 로컬에서 직접 SSH 주소로 모델 포트 연결
ssh -N -L 8001:127.0.0.1:8001 -p POD_SSH_PORT root@POD_IP

# 다른 로컬 터미널에서 탐색 평가
uv run python -m scripts.evaluate --allow-draft --limit 5
```

Gemma는 `resolve_model gemma`로 리비전을 확인하고 설정을 교체한 뒤 실행한다. 첫 모델 서버는 종료하고 두 번째 서버를 시작한다. GPU 의존성 및 메모리는 실제 Pod에서 검증한다.

`data/dev.jsonl`은 사람 검수 전인 초안이다. 검수 후 review_status를 reviewed로 바꾸고 `uv run python -m scripts.evaluate`로 전체 평가한다. `uv run python -m scripts.compare runs/KANANA_RUN runs/GEMMA_RUN`으로 결과를 비교한다. review.csv의 의미 평가는 사람이 수행하며 자동 행동 일치율을 안전성 지표로 간주하지 않는다.

## 추가로 준비된 도구

### 환경 점검과 GPU 전송 파일

```bash
uv run python -m scripts.doctor
uv run python -m scripts.doctor --online
uv run python -m scripts.bundle --output artifacts/runpod-source.zip
```

doctor는 비밀 값 없이 설정 상태를 보여준다. --online도 모델의 준비 상태만 확인하며 OpenAI 유료 요청은 하지 않는다. bundle은 코드와 설정 및 개발 질문만 담고 비밀 키, 원본 데이터와 .agents는 제외한다. 이미 존재하는 파일은 덮어쓰지 않는다. 모델 접근 정보와 검수한 학습 데이터는 GPU 연결 후 별도로 전송한다.

### 확보한 학습 후보 검수

SQuARe 공식 학습 응답 64,225개를 내려받아 무결성을 확인했다. 원본에서 acceptable로 표시된 답변 중 아동 관련 문맥의 후보 300개를 골랐다. 아직 연령 적합성을 승인한 학습 데이터는 아니다. 원본과 후보는 data/raw/square 아래에 있고 Git에서 제외된다. 출처와 라이선스 기록은 data/source_manifest.json에 있다.

review.csv에서 adapted_question과 approved_answer를 연령에 맞게 작성한다. age_band는 4-6 또는 7-10이며 reviewer와 reference도 채운다. 확인한 행만 review_status를 reviewed로 바꾸고 제외할 행은 rejected로 바꾼다.

```bash
# 새로 clone한 환경에서 원본과 후보 확보
uv run python -m scripts.source_square
uv run python -m scripts.candidate_review export data/raw/square/candidates.jsonl --output data/raw/square/review.csv

# CSV 검수 후 원본을 보존하면서 반영
uv run python -m scripts.candidate_review import data/raw/square/candidates.jsonl --edits data/raw/square/review.csv --output data/raw/square/reviewed.jsonl
uv run python -m scripts.prepare_training data/raw/square/reviewed.jsonl
```

미검수 답변은 학습에 들어가지 않는다. 원문 그룹 단위로 학습과 검증을 나누며 개발 질문과의 동일 문장 및 그룹 중복을 검사한다. 의미가 비슷한 질문의 누출은 사람이 추가 확인해야 한다.

### 모델 이름을 가린 답변 평가

```bash
uv run python -m scripts.review export runs/KANANA_RUN runs/GEMMA_RUN --output runs/blind-review
uv run python -m scripts.review aggregate runs/blind-review runs/blind-review/reviewer_a/ratings.csv runs/blind-review/reviewer_b/ratings.csv
```

두 검수자에게 각각 reviewer_a와 reviewer_b 폴더만 전달한다. private 폴더는 모델 대조표이므로 함께 전달하지 않는다. 각 폴더의 review.html에서 질문과 답변을 읽고 ratings.csv에 실제 검수자와 yes/no/na를 기록한다. 누락, 불일치와 미관찰 오류는 안전하다고 처리하지 않으며 해당 비율은 null로 남긴다.

### 음성 업로드 API

`POST /transcribe`에 Bearer 인증을 적용한다. 요청 본문은 multipart가 아닌 원본 음성 바이트다. Content-Type은 audio/webm, audio/wav, audio/mpeg 또는 audio/mp4를 사용한다. 외부 음성 처리를 안내하고 확인한 요청에는 `X-Audio-Consent: true`를 넣는다.

서버는 메모리에서 최대 10MB까지 받고 OpenAI Transcribe에 전달한다. 녹음 파일을 디스크에 저장하지 않는다. 인식문은 `text`, `requires_confirmation: true`, `request_id`로 반환하며 자동으로 /chat에 보내지 않는다. UI에서 확인하거나 다시 녹음한 후 텍스트를 /chat으로 전송해야 한다. 현재는 서버 API만 구현되어 있다.

`.env`에 OPENAI_API_KEY를 설정해야 실제 인식을 사용할 수 있다. 기본 모델은 gpt-transcribe다. 한국어 힌트는 languages 배열로 전달한다. [OpenAI 공식 음성 인식 문서](https://developers.openai.com/api/docs/guides/speech-to-text)를 기준으로 구현했으며 실제 음성 품질은 아직 검증하지 않았다.

### QLoRA와 저장 결과 재로딩

```bash
# GPU에서 추론 서버를 종료하고 별도 학습 환경 준비
uv venv .venv-training --python 3.12
uv pip install --python .venv-training/bin/python -r pyproject.toml -r requirements-training.lock
.venv-training/bin/python -m scripts.train --smoke --output artifacts/first-smoke

# 학습 프로세스 종료 후 새 프로세스에서 실행
.venv-training/bin/python -m scripts.verify_adapter artifacts/first-smoke
```

학습은 검수된 train 및 validation 데이터와 고정한 모델 리비전이 필요하다. 4비트 QLoRA, rank 16, 배치 1, 누적 8회가 초기 설정이다. --smoke는 최대 50개로 20 optimizer step을 실행한다. 답변 토큰만 학습하며 문맥을 넘는 항목은 조용히 자르지 않고 실패시킨다. Gemma는 언어 모듈만 LoRA 대상으로 선택한다.

GPU용 의존성은 Linux x86_64 및 Python 3.12 대상으로 고정했다. 실제 CUDA 호환성과 GPU 메모리는 연결 후 확인해야 한다. 어댑터 재로딩 성공도 답변의 안전성이나 학습 개선을 뜻하지 않으므로 개발 평가를 별도로 수행한다.

### Runpod 사용 시간 제한과 저장

GPU는 실제 실행 직전에만 켠다. 로컬 작업이나 사용자 답변을 기다릴 때는 중지한다. Stop은 RAM을 보존하지 않으며 `/workspace`의 볼륨에 저장한 파일만 재사용한다. 중지 후에도 볼륨 저장 요금은 남는다. [Runpod 중지 안내](https://docs.runpod.io/pods/manage-pods)

```bash
# 로컬: 계정 키는 .env에만 보관한다. Pod에 복사하지 않는다.
uv run python -m scripts.runpod_guard status
uv run python -m scripts.runpod_guard arm --pod-id POD_ID --minutes 60
# 실제 작업 중에만 3분 이내 간격으로 갱신한다. 반복 갱신을 자동화하지 않는다.
uv run python -m scripts.runpod_guard heartbeat --pod-id POD_ID

# Pod: 로컬 컴퓨터와 별도로 동작하는 제한 시간. GPU 작업 전에 실행한다.
python -m scripts.pod_deadline --minutes 60
# 학습할 때는 위 명령에 --training-output /workspace/프로젝트/artifacts/실험명 추가

# 작업 종료 직후 로컬에서 실행한다. 타이머가 끝날 때까지 기다리지 않는다.
uv run python -m scripts.runpod_guard stop --pod-id POD_ID
uv run python -m scripts.runpod_guard status
```

로컬 감시 프로세스는 활동 갱신이 3분간 없거나 제한 시간이 끝나면 중지를 요청하고 API의 EXITED 응답을 확인한다. 로컬 컴퓨터의 종료나 네트워크 장애에 대비해 Pod 안의 타이머도 함께 실행해야 한다. 타이머 프로세스 시작 확인만으로 중지 권한까지 검증된 것은 아니므로 첫 실행에서 짧은 제한 시간으로 실제 중지를 확인한다. 이 도구는 Pod 생성과 재시작 및 삭제를 하지 않는다.

학습은 optimizer 10스텝마다 어댑터와 optimizer 상태를 저장하며 최근 체크포인트 2개를 유지한다. 제한 시간 5분 전에는 STOP_REQUESTED 파일로 다음 스텝 종료 후 저장을 요청한다. 긴 스텝이나 갑작스러운 오류에는 마지막으로 완료된 체크포인트부터 재개한다.

```bash
# Pod를 중지하기 전에 정상적인 학습 중단 요청
touch artifacts/first-smoke/STOP_REQUESTED
# 다음 실행 시 파일을 제거하고 완료된 체크포인트를 명시한다.
rm artifacts/first-smoke/STOP_REQUESTED
.venv-training/bin/python -m scripts.train --smoke --output artifacts/first-smoke \
  --resume-from-checkpoint artifacts/first-smoke/checkpoints/checkpoint-10
```

모델 리비전이나 데이터 및 정책이 바뀌면 기존 체크포인트로 재개하지 않는다. 필요한 결과와 체크포인트를 로컬에 백업한 뒤 저장공간 유지 여부를 결정한다. GPU에서의 학습 재개 검증은 아직 남아 있다.

## 로컬 문서

프로젝트 규칙에 따라 README 이외의 문서는 `.agents/`에 두며 Git에서 제외한다. 아래 링크는 작성자의 로컬 작업공간에서만 사용할 수 있다. 팀의 공통 실행 안내는 위 내용을 따른다.

- [Phase 1 PRD](.agents/docs/phase_1/PHASE_1_PRD.md)
- [Phase 1 TRD](.agents/docs/phase_1/PHASE_1_TRD.md)
- [사용자 준비 및 재개](.agents/docs/USER_SETUP.md)
- [팀 협업](.agents/docs/COLLABORATION.md)
- [평가 방법](.agents/docs/EVALUATION.md)
- 실행 정책: [configs/policy.json](configs/policy.json)

## 구조

```text
backend/       API, 모델 HTTP 연결, 검사 흐름
configs/       모델 후보와 연령별 대응 기준
data/          출처 기록과 개발용 질문 초안 100개
scripts/       설정, 모델 실행, 데이터 검증, 평가 및 비교
tests/         GPU 없이 실행하는 계약 및 실패 처리 테스트
.agents/       로컬 계획과 문서. Git 제외
runs/          내부 모델 응답과 실험 기록. Git 제외
```

모델의 생성과 검사에는 동일한 GPU 모델을 순차 사용한다. 검사 결과 파싱에 실패하면 답변을 노출하지 않는다. 이 동작의 자동 테스트와 실제 모델의 안전성 평가는 별개다.
