# Phase 3 Kanana 1.5 8B 개발 후보

기존 Kanana 2 3B와 Qwen 개발 후보는 Codex의 개발 답변 직접 검수에서 정상 정답 목표에 도달하지 못했다. 한국어 대화 성능 개선 가능성을 확인하기 위해 `kakaocorp/kanana-1.5-8b-instruct-2505`를 선택 가능한 개발 프로필로 추가했다. 제품 기본 프로필 `kanana`와 안전 정책은 변경하지 않는다.

[공식 모델 카드](https://huggingface.co/kakaocorp/kanana-1.5-8b-instruct-2505)는 한국어 지원, vLLM 서빙과 Apache 2.0 라이선스를 명시한다. 리비전은 `c963a5f4f6496c749f94064a20b33028b0db9f19`로 고정하고 temperature 0, seed 42로 생성한다. 검사 JSON은 기존 temperature 0, seed 42를 유지한다. vLLM 0.29.0, BF16, prefix caching, batch invariance를 기록한다.

검수된 개발 100문항의 guarded 결과를 먼저 저장한다. Codex가 질문과 기준 및 답변 원문을 직접 읽어 정상 정답, 과도한 거절, 지원 적절성, 유해 노출, 연령 적합성을 판정한다. 단일 비블라인드 AI 평가라고 표기한다. 개발 기준을 통과할 때 raw 경로를 이어서 평가한다. 정상 정답과 안전 및 지연 목표를 모두 충족하기 전에 최종 300문항을 열어 모델을 조정하거나 채택하지 않는다.

Runpod 비용과 절대 중지 기한, 백업 및 실제 EXITED 확인은 `.logs/phase3-quality.md`에 기록한다. 원본 개발 결과를 영구 볼륨과 로컬에 보존하고 SHA256을 대조한다.

## 개발 결과

`baseline` guarded 정상 질문 첫 30개에서 Codex가 오답 9개를 확인해 목표 32/40 달성이 불가능했다. `safety_v3` guarded 100개는 [원본과 직접 판정](artifacts/phase3-kanana8b-safety-v3-20260918/README.md)을 보존했다. 정상 정답은 29/40, 실행 오류 미판정 1건이며 최선도 30/40이다. 지원 적절성은 4/9, 유해 노출은 2/100이고 실행 오류는 총 3건이다. `dev-053`과 `dev-080`에서 안전 결함을 확인했다. 후보를 미채택했고 raw와 최종 300문항은 실행하지 않았다.
