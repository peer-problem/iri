# Phase 3 Qwen2.5 32B 개발 후보

개발 정상 질문의 직접 검수에서 앞선 모델 후보들이 32/40 목표에 못 미쳤다. 다음 후보로 `Qwen/Qwen2.5-32B-Instruct` 리비전 `5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd`를 추가한다. 제품 기본값과 안전 정책은 바꾸지 않는다.

[공식 모델 카드](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)는 약 32.5B 파라미터와 한국어를 포함한 다국어 지원, vLLM 서빙, Apache 2.0을 명시한다. BF16 가중치는 약 65GB로 예상한다. RTX PRO 6000 Blackwell Server Edition 96GB에서 vLLM 0.29.0, 고정 리비전, 생성 temperature 0과 seed 42를 사용한다. `VLLM_USE_FLASHINFER_SAMPLER=0`은 같은 GPU의 앞선 서버 초기화 오류를 피하기 위해 적용한다.

검수된 개발 정상 40문항을 guarded 경로로 먼저 실행한다. Codex가 질문과 판정 기준 및 답변을 직접 읽어 정답을 판정한다. 32/40 목표가 불가능해지면 중단한다. 목표 가능성이 남으면 전체 개발 100문항의 안전과 피해 지원 및 연령 적합성을 검수하고 raw 경로를 평가한다. 그 기준을 통과한 모델에만 잠근 최종 300문항을 사용한다. API 평가 호출은 하지 않는다.

GPU 비용과 중지 및 백업 계획은 `.logs/phase3-quality.md`에 기록한다. 55분 절대 제한의 로컬 watchdog을 사용하고 결과를 영구 볼륨과 로컬에 보존한 뒤 Runpod REST에서 `EXITED`를 확인한다.
