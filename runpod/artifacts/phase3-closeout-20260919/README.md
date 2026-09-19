# Phase 3 종료 기록

## 결정

제품의 우선 답변 모델은 고정 리비전의 Kanana 2 3B Instruct와 이 프로젝트의 QLoRA 어댑터다. 입력 및 출력 검사도 같은 Kanana 원본을 사용한다. Kanana가 준비되지 않으면 기존 제품 설계대로 Luna high가 전체 검사 경로를 다시 실행한다. Qwen 등 다른 개발 후보는 사용하지 않는다. 품질 목표와 최종 300문항 평가는 이번 데모 운영 인수인계의 선행 조건에서 제외한다. 이는 품질 달성이나 아동 대상 공개 출시 승인이 아니다.

## 확인된 산출물

- Hugging Face: `peerproblem/Kanana-IRI-3B-QLoRA`, 현재 v5 게시 커밋 `0880ce0372cedf22aec91b190f8a7b9499ccc176`
- 기본 모델: `kakaocorp/kanana-2-3b-instruct`, 리비전 `6a5d7889964c4c590299d16e309eabab1f73f8a9`
- 현재 v5 어댑터 가중치 SHA-256: `0ecacdb7d7f743652a24ff7b7e7c59d0e2ae238e63476e64b2d6d95e8fbe2e02`
- A40 vLLM 실행 보고서 `runpod/backups/phase3-hf-serving-20260919/iri-serving-verification.json`은 이전 v1 가중치에 대한 증거다. v5는 새 프로세스 PEFT 재로딩까지 확인했으며 v5 vLLM 서빙 검증은 아직 수행하지 않았다.
- 웹과 API는 Kanana를 우선 사용하고 장애 시 Luna high가 전체 검사 경로를 다시 실행한다. 로컬 테스트와 Ruff, 웹 빌드가 통과했다.
- 과거 Vercel과 Contabo 배포 기록은 현재 코드 정상화 변경의 배포 완료 증거가 아니다. UI는 응답별 실제 제공자를 표시하도록 수정했으며 이번 변경은 로컬 검증만 수행했다.
- 검증용 A40 Pod는 보고서와 환경 기록의 원격 및 로컬 해시를 대조한 뒤 Runpod REST에서 `EXITED`를 확인하고 삭제했다. 추가 영구 볼륨은 없다. 기존 아홉 Pod도 모두 `EXITED`다.

## 운영 인수인계

`runpod/HF_SERVING.md`에 모델 재기동, 인증된 터널, 준비 확인, 중지, 백업 순서를 적었다. GPU는 데모 시간에만 한 대 시작한다. 현재 상시 Kanana 서빙은 중지되어 있으므로 채팅은 Luna high 경로를 사용한다. Kanana 데모를 시작할 때 GPU Pod와 Contabo 사이의 인증된 터널을 열고 `/ready` 및 `/chat`을 다시 확인해야 한다. 상세 GPU 비용과 환경 기록은 `.logs/phase3-quality.md`에 있다.

## 남은 제한

v1 어댑터는 Phase 2 개발 평가에서 원본보다 정상 질문 정답이 낮았다. v5의 최종 300문항 raw 및 guarded 응답 생성, Codex 직접 판정과 vLLM 서빙 검증은 수행하지 않았다. 현재 결과로 아동 안전성 또는 공개 출시 품질을 주장하지 않는다. 실제 기기의 마이크 및 스피커와 Kanana를 연결한 전체 음성 대화도 검증하지 않았다.
