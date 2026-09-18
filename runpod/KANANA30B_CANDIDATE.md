# Phase 3 Kanana 2 30B 개발 평가 이력

앞선 3B와 8B 및 Qwen 개발 후보는 Codex의 직접 검수에서 정상 정답 또는 안전 목표에 못 미쳤다. 이 문서는 `kakaocorp/kanana-2-30b-a3b-instruct-2601`의 과거 개발 평가를 기록한다. 고정 리비전은 `4a781fe5027da4af8d8208cb21bc5108b913bb62`이다. 사용자 비용 지시에 따라 이 고가 후보는 현재 실행 프로필에서 제외했다. 제품 기본값과 안전 정책은 변경하지 않았다.

[공식 모델 카드](https://huggingface.co/kakaocorp/kanana-2-30b-a3b-instruct-2601)는 한국어 지원, 약 30B 전체 파라미터와 3B 활성 파라미터 및 vLLM 서빙을 설명한다. BF16 가중치의 크기는 약 61GB로 예상한다. [Kanana License](https://huggingface.co/kakaocorp/kanana-2-30b-a3b-instruct-2601/blob/main/LICENSE)는 앞선 Apache 2.0 모델과 다르므로 서비스 채택 전 표시 의무와 사용 조건을 별도로 확인한다. 이번 실행은 개발 평가다.

Secure RTX PRO 6000 Blackwell Server Edition 96GB에서 vLLM 0.29.0, BF16, 생성 temperature 0과 seed 42로 실행했다. 검수된 개발 100문항 중 정상 질문 40개를 guarded로 실행하고 Codex가 답변 원문을 직접 판정했다. 목표 32/40에 미달해 조기 중단했다. raw 및 잠근 최종 300문항은 실행하지 않았다.

GPU 가격과 시간 제한 및 저장 비용은 `.logs/phase3-quality.md`에 기록했다. Pod 중지와 REST `EXITED` 상태를 확인했다. 결과와 환경 기록을 영구 볼륨과 로컬에 백업해 SHA-256을 대조했다.

## 개발 결과

[정상 질문 40개 실행과 Codex 직접 검수](artifacts/phase3-kanana30b-normal40-20260918/README.md)에서 정답 27/40, 오답 13/40, 실행 오류 0건을 기록했다. 아이의 실제 이름을 요구한 응답 1건도 있었다. 목표 32/40에 못 미쳐 후보를 미채택했다. 안전과 지원의 전체 개발 평가 및 최종 300문항은 실행하지 않았다. 원본을 영구 볼륨과 로컬에 백업하고 Runpod에서 Pod의 `EXITED` 상태를 확인했다.
