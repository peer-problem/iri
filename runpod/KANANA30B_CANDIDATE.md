# Phase 3 Kanana 2 30B 개발 후보

앞선 3B와 8B 및 Qwen 개발 후보는 Codex의 직접 검수에서 정상 정답 또는 안전 목표에 못 미쳤다. 다음 개발 후보는 `kakaocorp/kanana-2-30b-a3b-instruct-2601`의 고정 리비전 `4a781fe5027da4af8d8208cb21bc5108b913bb62`이다. 제품 기본값과 안전 정책은 변경하지 않는다.

[공식 모델 카드](https://huggingface.co/kakaocorp/kanana-2-30b-a3b-instruct-2601)는 한국어 지원, 약 30B 전체 파라미터와 3B 활성 파라미터 및 vLLM 서빙을 설명한다. BF16 가중치의 크기는 약 61GB로 예상한다. [Kanana License](https://huggingface.co/kakaocorp/kanana-2-30b-a3b-instruct-2601/blob/main/LICENSE)는 앞선 Apache 2.0 모델과 다르므로 서비스 채택 전 표시 의무와 사용 조건을 별도로 확인한다. 이번 실행은 개발 평가다.

Secure RTX PRO 6000 Blackwell Server Edition 96GB에서 vLLM 0.29.0, BF16, 생성 temperature 0과 seed 42를 기록한다. 검수된 개발 100문항 중 정상 질문 40개부터 guarded로 실행하고 Codex가 답변 원문을 직접 판정한다. 목표 32/40이 불가능해지면 조기 중단한다. 가능성이 남으면 전체 개발 100문항의 안전, 지원과 연령 적합성까지 직접 검수한다. raw 및 잠근 최종 300문항은 개발 기준을 통과한 후에만 실행한다.

GPU 가격과 시간 제한 및 저장 비용은 `.logs/phase3-quality.md`에 기록한다. Pod는 55분 전에 중지하고 REST에서 `EXITED`를 확인한다. 결과와 환경 기록은 영구 볼륨과 로컬에 백업해 SHA-256을 대조한다.
