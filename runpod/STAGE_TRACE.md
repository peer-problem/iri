# Phase 3 단계별 평가 기록

목적은 현재 baseline/v3의 실패 지점을 관측하는 것이다. Google Phase 문서의 2번 오류 진단, 6번 검사 단계의 실패·지연 분리, 7~8번 비교·검수에 필요한 보조 기록이다. 품질 개선 완료나 후보 채택을 뜻하지 않는다.

## 바꾸지 않는 것

- 원본 Kanana와 리비전, LoRA 미사용, BF16 및 서버 재현성 조건.
- 입력·생성·출력 프롬프트, 판정 JSON schema, 호출 순서와 횟수, fallback 동작.
- 검수된 개발 100문항, raw/guarded 구분, 기존 평가 기준과 점수 집계.
- 제품 API와 음성 계층. 추가 기록은 Runpod 평가 명령에서만 선택한다.

## 기록 형식

`--trace-stages`를 지정한 새 평가 폴더에 `stage-traces.jsonl`이 생긴다. 기존 `results.jsonl`의 답변·행동 및 검수 형식은 그대로다. 별도 기록은 시나리오와 경로당 한 행이며 `id`, `mode`, 턴 번호로 결과와 연결한다. 처리된 모델 오류나 시간 초과로 답변이 없는 마지막 턴도 기록한다.

- `stages.input_guard`, `generation`, `output_guard`: 실행 상태와 `seconds`.
- 입력·출력 단계의 `decision`: 유효하게 파싱된 실제 판정만 기록.
- `final_action`, `fallback_used`: 정상 반환한 최종 경로와 고정 문구 사용 여부. 오류로 반환하지 못하면 null.
- 상태는 `not_run`, `running`, `completed`, `error`, `interrupted`. 미실행 단계의 시간·판정은 null이며 0초나 통과로 해석하지 않는다.
- `error_code`: 고정 오류 코드만 기록. 외부 timeout에 의한 취소는 단계 안에서 `interrupted/cancelled`로 관측될 수 있으며 최종 오류는 기존 결과의 `error_detail`과 함께 본다.
- 각 단계의 `output_characters`: 앞뒤 공백을 제거한 반환 텍스트의 Python 문자 수다. 생성 단계에서는 답변 후보 길이이며, 검사 단계에서는 판정 JSON 길이다. 최종 고정 문구 길이가 아니다.
- `prompt_tokens`, `completion_tokens`: 서버가 `usage`에 제공한 0 이상의 정수만 기록한다. 누락·잘못된 형식은 null로 남긴다. 글자 수를 토큰 수로 추정하지 않는다.
- `finish_reason`: 알려진 종료 사유만 기록한다. 길이 제한에 걸린 응답의 측정값이 있어도 단계는 기존처럼 오류이며 성공한 답변으로 바뀌지 않는다.

원문 질문·생성 후보·검사기의 잘못된 원문·인증키·상류 오류 본문은 이 파일에 저장하지 않는다. 시간은 HTTP 대기와 모델 실행, 응답 처리 및 판정 파싱을 포함한 클라이언트 관측 시간이며 GPU 계산 시간만을 뜻하지 않는다. 글자 수·토큰 수와 시간을 함께 비교하되 길이와 지연의 상관만으로 인과를 확정하지 않는다. 서버의 캐시 사용량이나 순수 GPU 계산 시간을 측정한 것은 아니다.

측정은 작업별 컨텍스트로 분리하며 요청 본문, 모델 호출 수, provider 반환 형식을 바꾸지 않는다. 호출이 끝나거나 실패하면 컨텍스트를 복원한다. 기록 비활성 상태에서는 측정값을 보관하지 않는다.

한 시나리오가 끝날 때 파일을 flush하고, 정상 종료 또는 처리된 오류를 포함한 종료 시 metadata에 행 수와 SHA-256을 저장한다. 강제 프로세스 종료 시 진행 중인 시나리오는 남지 않을 수 있다. 그런 실행은 metadata의 `running` 상태를 유지하며 완료 결과로 사용하지 않는다. 기존 결과 파일도 같은 제한이 있다.

`quality_experiment --trace-stages`는 기록 해시, 시나리오별 raw/guarded 쌍과 실패 턴을 포함한 턴 번호를 확인한다. 로그는 독립 평가 점수가 아니며 블라인드 검수 화면에 추가하지 않는다.

## GPU 실행 전 준비

2026-09-17 새 L4에서 아래 진단을 완료하고 GPU 중지·백업 해시를 확인했다. [실행 결과](artifacts/phase3-stage-diagnosis-20260917/README.md)를 참조한다. 이는 품질 개선 완료가 아니다. 아래는 재실행 참고 명령이며 자동 재개 승인이 아니다. 실행 전 팀의 GPU 사용 여부, 비용 한도, 중지 감시와 백업 경로를 새로 확인한다.

서버 재현성 설정을 이전 검증 조건과 맞춘 뒤, 새 출력 경로로 기존 baseline과 safety_v3를 비교한다. 아래는 저장소 루트의 Linux GPU 환경 명령이다.

```sh
python -m runpod.operations.quality_experiment \
  --data runpod/artifacts/phase2-evaluation-20260917/base-run/dataset.jsonl \
  --profiles baseline safety_v3 \
  --trace-stages \
  --output runpod/runs/stage-trace-comparison
```

각 설정의 기존 100문항 × raw/guarded = 200건, 총 400건이다. 별도 평가 문항을 추가하지 않는다. 이번에는 v3를 고치기 전 실패 단계를 기록하는 진단이며 새 개선 후보가 아니다. 기록의 작은 실행 오버헤드가 있을 수 있으므로 비교하는 두 설정에 같은 옵션을 적용한다. 결과와 로그를 함께 백업하고 GPU 중지 및 실제 EXITED 확인 후 검토한다.

## 고정 답변의 출력 검사 재실행

`runpod.operations.output_replay`는 저장된 답변과 당시 대화 이력을 동결해 기존 출력 검사만 실행한다. 입력 검사와 새 답변 생성은 호출하지 않는다. 이 표적 진단은 전체 100문항 raw/guarded 평가를 대체하지 않으며 독립 평가 점수를 만들지 않는다.

### 로컬 준비 — 모델 연결 없음

```sh
python -m runpod.operations.output_replay prepare \
  --run runpod/artifacts/phase3-repro-20260917/safety_v3-run \
  --mode guarded \
  --ids dev-009 dev-053 dev-071 dev-077 dev-078 dev-079 dev-080 dev-084 \
  --output runpod/runs/output-replay-prep-20260917
```

문제 후보는 도로 놀이, 신체 경계의 모순, 두 비밀 유지 약속이다. 비교 후보는 정상 과학 설명, 교육 질문, 두려움 지원, 계정 보호 안내다. 후자는 무조건 차단하는 검사를 탐지하기 위한 비교 자료이며 독립적인 안전 승인 정답지는 아니다. 후보 선택은 결과를 본 뒤 한 탐색적 선택으로 공개하며 대표성 있는 안전 정확도라고 보고하지 않는다. ID는 명령의 선택값일 뿐 추론 코드의 하드코딩 규칙이 아니다.

`--ids`를 생략하면 원본 100개 시나리오의 선택한 경로 전체를 준비한다. 여러 턴 문항은 모든 관찰된 턴을 후보로 만들고 각 턴 직전까지의 해당 경로 이력을 보존한다. raw 이력과 guarded 이력을 섞지 않는다.

도구는 완료된 원본 모델 개발 200건의 데이터·결과·정책 해시와 전체 id/mode 쌍을 확인한다. `packet.json`에 후보와 문맥, 출처, 선택 범위를 기록하고 `source/`에 원본 네 파일을 바이트 그대로 복사한다. 준비 과정은 `.keys/.env`를 읽거나 모델 서버를 호출하지 않는다. 기존 출력 경로는 거절한다.

준비된 묶음은 유해한 모델 답변이 포함된 성인 팀 내부 자료다. 아동 UI에 노출하지 않는다. 차단되기 전 내부 생성 후보는 과거 결과에 없으므로 복원했다고 표시하지 않는다. 고정 문구와 동일한 답변은 `fallback_text`로 표시하며 그 뒤에 숨은 원래 후보를 검사한 것으로 해석하지 않는다.

### 서버 연결 후 실행 — 실행 이력은 위 결과 참조

```sh
python -m runpod.operations.output_replay run \
  --packet runpod/runs/output-replay-prep-20260917 \
  --expected-sha256 <prepare가_출력한_packet_sha256> \
  --launch-record runpod/runs/<현재_서버_실행폴더>/gpu-environment.json \
  --profiles baseline safety_v3 \
  --passes 1 \
  --output runpod/runs/output-replay-result
```

위의 8개 후보라면 출력 검사 16회다. 이는 전에 철회한 신규 16문항 트랙이 아니라 **기존 8개 답변 × 출력 검사 설정 2개**의 호출 수다. 전체 개발 비교는 별도로 400개 시나리오 결과를 생성한다. 반복 확인에는 `--passes`를 명시하고 비용을 다시 계산한다.

현재 원본 Kanana 리비전과 정책, LoRA 미사용, BF16, vLLM 0.29.0, 캐시 on, batch invariance on, 문맥 4096, 동시 시퀀스 1을 실행 기록과 대조한다. 기록 검사는 현재 GPU의 실제 설정을 원격 증명하는 기능이 아니다. 현재 서버의 새 실행 기록을 사용하고 SSH/서빙 검증 및 팀 사용 여부·예산·중지 감시를 별도로 확인한다. 과거 실행 기록을 붙여 새 서버를 검증했다고 표시하지 않는다. 이 명령은 Pod 시작·중지·비용 감시를 자동 수행하지 않는다.

실행 결과에는 후보 문맥 해시, 실제 전송 본문 해시, 프로필·반복·턴, allow/block 또는 오류, 검사 시간·출력 길이·서버 토큰 사용량을 기록한다. `candidate_characters`는 저장된 답변 길이이며 재생성 비용이 아니다. 결과 JSONL에는 질문·답변·잘못된 판정 원문·키를 중복 기록하지 않는다. 재현용 `packet.json`과 `source/`에는 기존 평가 원문이 있으므로 결과 디렉터리 전체는 내부 검수 자료로 취급한다.

동결 묶음의 해시를 반드시 지정하며 복사 후에도 원본과 후보·문맥을 다시 대조한다. 결과는 매 호출 후 flush하고 종료 시 행 수와 해시를 기록한다. 취소 시 관찰된 마지막 오류까지 남기고 전체는 failed로 표시한다. 프로세스 강제 종료에는 저장이 보장되지 않으므로 running/불완전 실행을 완료로 세지 않는다. 오류를 block으로 대체하지 않는다.

GPU 결과는 영구 공간과 로컬에 백업·해시 확인한 뒤 해당 Pod를 Stop하고 실제 EXITED를 확인한다. 로컬 검수나 사용자 대기 중 GPU를 유지하지 않는다.

## Windows 로컬 검증

```powershell
$env:PYTHONUTF8='1'
runpod/.venv/Scripts/python.exe -m pytest -q -c runpod/pyproject.toml runpod/tests/test_output_replay.py runpod/tests/test_stage_trace.py runpod/tests/test_inference.py runpod/tests/test_data_and_evaluation.py runpod/tests/test_quality_experiment.py runpod/tests/test_repeatability.py
runpod/.venv/Scripts/python.exe -m ruff check --config runpod/pyproject.toml api runpod
```

테스트 경로를 명시해 보관된 옛 소스의 테스트를 수집하지 않는다. 기존 전체 테스트의 Windows 줄바꿈 해시·POSIX 권한·심볼릭 링크 실패는 이번 기록 기능과 구분한다. 모의 모델 요청·응답의 동일성 테스트는 실제 GPU 응답 품질 검증을 대신하지 않는다.
