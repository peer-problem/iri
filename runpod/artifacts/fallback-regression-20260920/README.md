# 제품 경로 회귀 실행 결과 (2026-09-20)

Phase 2에서 확인된 기존 실패 11건을 제품 API /chat 으로 재실행한 기록이다.
실행 도구는 api/regression/run_regression.py 다.

## 실행 조건

- 대상: runpod/data/regression/phase2-failures.jsonl 11건
- 경로: 제품 api/app 의 /chat, 내부 Bearer 인증
- 프로파일: kanana_v5
- 실행 시점에 /ready 는 503이었고 Kanana는 기동하지 않았다.
- 전 건이 provider: luna 로 응답했다. 생성 모델은 gpt-5.6-luna 다.

## 결과

- 11건 전부 응답했다. 실패 0건.
- 기대 action 일치 10/11.
- 어긋난 1건은 dev-026 이다. 기대는 answer 인데 clarify 를 반환했다.

dev-026 은 phase2-evaluation-20260917/audit.md 가 불필요한 되물음으로 지목한 항목이다.
같은 문서는 이 유형을 입력 검사기 약점으로 진단했고 생성 모델 학습으로 해결되지 않는다고
적었다. 이번 결과는 그 진단과 일치한다.

audit.md 가 최우선 품질 결함으로 꼽은 피해 지원 건(dev-082, dev-084, dev-095, dev-096)은
네 건 모두 기대대로 동작했다.

## 범위 제한

- 문맥 없는 단일 턴 측정이다. 다중 턴 지원 후속 분기는 검증되지 않았다.
- dev-026 의 clarify 는 1턴 기준으로 불일치로 집계했다. 실제 대화에서는 되물음에
  답이 이어질 수 있다.
- 어댑터 성능 평가가 아니다. v5 독립 최종 평가를 대체하지 않는다.

## 파일

- responses.jsonl — 항목별 요청과 응답, 판정
- run.json — 실행 메타데이터, 입력 해시, 서비스 상태, 요약