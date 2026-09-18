# Phase 3 종료 기록

## 결정

사용자의 최신 범위에 따라 제품 답변 모델은 고정 리비전의 Kanana 2 3B Instruct와 이 프로젝트의 QLoRA 어댑터로 한정한다. 입력 및 출력 검사도 같은 Kanana 원본을 사용한다. 다른 답변 LLM으로 전환하지 않는다. 품질 목표와 최종 300문항 평가는 이번 데모 운영 인수인계의 선행 조건에서 제외한다. 이는 품질 달성이나 아동 대상 공개 출시 승인이 아니다.

## 확인된 산출물

- Hugging Face: `jbaehova/Kanana-IRI-3B-QLoRA`, 커밋 `6eb9580da2e2e92875e30f6a6b41a7493fdccf15`
- 기본 모델: `kakaocorp/kanana-2-3b-instruct`, 리비전 `6a5d7889964c4c590299d16e309eabab1f73f8a9`
- 어댑터 가중치 SHA-256: `7e65cf058a51407cef1a0526673253f30f5aafd4d2e192843e71516e43fe71d5`
- 새 A40 Pod의 vLLM 0.29.0에서 원본과 어댑터 별칭, 실제 생성 응답 다섯 건을 검증했다. 실행 보고서는 로컬 백업 `runpod/backups/phase3-hf-serving-20260919/iri-serving-verification.json`에 있다.
- 웹과 API의 답변 대체 LLM 경로를 제거했다. 로컬 테스트 585개와 Ruff, 웹 빌드가 통과했다.
- Vercel과 Contabo에 배포했다. GPU 중지 상태에서 운영 API의 `/health`는 200, `/ready`는 503, `/chat`은 `provider: unavailable`의 503을 반환했다. 데모 웹은 200이며 `Powered by Kanana`를 표시한다.
- 검증용 A40 Pod는 보고서와 환경 기록의 원격 및 로컬 해시를 대조한 뒤 Runpod REST에서 `EXITED`를 확인하고 삭제했다. 추가 영구 볼륨은 없다. 기존 아홉 Pod도 모두 `EXITED`다.

## 운영 인수인계

`runpod/HF_SERVING.md`에 모델 재기동, 인증된 터널, 준비 확인, 중지, 백업 순서를 적었다. GPU는 데모 시간에만 한 대 시작한다. 현재 상시 서빙은 중지되어 있으므로 채팅은 사용 불가 응답을 반환한다. 데모에서 실제 채팅을 사용하려면 GPU Pod와 Contabo 사이의 인증된 터널을 열고 `/ready` 및 `/chat`을 다시 확인해야 한다. 상세 GPU 비용과 환경 기록은 `.logs/phase3-quality.md`에 있다.

## 남은 제한

어댑터는 Phase 2 개발 평가에서 원본보다 정상 질문 정답이 낮았다. 최종 300문항에 대한 raw 및 guarded 응답 생성과 Codex 직접 판정은 수행하지 않았다. 현재 결과로 아동 안전성 또는 공개 출시 품질을 주장하지 않는다. 실제 기기의 마이크 및 스피커와 Kanana를 연결한 전체 음성 대화도 이번 배포에서 검증하지 않았다.
