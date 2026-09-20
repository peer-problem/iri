# 제품 경로 회귀 실행

runpod/data/regression/phase2-failures.jsonl 의 시나리오를 제품 API /chat 으로
재실행하고 응답과 판정을 기록한다. 연구 평가 경로(runpod/operations/evaluate.py)가
아니라 배포된 가드 경로(api/app)를 측정한다.

## 실행

API를 먼저 띄운다. 레포 루트에서 실행한다.

    unset OPENAI_API_KEY
    .ops/run.sh

다른 터미널에서, 역시 레포 루트에서 실행한다.

    unset OPENAI_API_KEY
    runpod/.venv/bin/python api/regression/run_regression.py

인자는 --data, --output, --base-url, --timeout, --limit 이다.
결과는 api/regression/runs/<타임스탬프>/ 에 responses.jsonl 과 run.json 으로 쌓이며
이 디렉터리는 Git에서 제외한다. 보존할 결과는 runpod/artifacts/ 로 옮긴다.

## 환경변수 주의

환경에 OPENAI_API_KEY 가 있으면 .keys/.env 보다 우선해서 로드된다.
쉘 설정에 전역 export가 있으면 다음이 발생한다.

- 러너 실행 시 fallback이 401로 실패하고 /chat 이 503에 provider: unavailable 을 반환한다.
- 테스트 스위트가 26건 실패한다. has_fallback 이 True가 되어 MockTransport 기대와 어긋난다.

실행과 테스트 모두 unset OPENAI_API_KEY 또는 env -u OPENAI_API_KEY 로 해결한다.

## 측정 범위

- 내부 Bearer 인증을 쓰므로 브라우저 세션을 타지 않는다. 매 요청이 문맥 없는 단일 턴이고
  previous_action 이 없다. 다중 턴 지원 후속 분기는 이 경로로 검증되지 않는다.
- 어댑터 성능 평가가 아니다. 가드 경로의 동작 기록이며 독립 최종 평가를 대체하지 않는다.
- 기본 테스트 스위트에 포함하지 않는다. 실제 상위 모델을 호출하므로 네트워크와 크레딧이 필요하다.