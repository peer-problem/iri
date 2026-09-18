# V63 코드 검토 안내

V63은 같은 Kanana 모델의 입력 검사·지원 생성·출력 검사를 개선한 **선택 실행 후보**다. 별도 가중치가 없으며 서비스 기본값은 `baseline`이다. 실행 방법은 [V63 실행 안내](V63.md), V63 전체 평가·검수·진단 결과는 [자료 목록](artifacts/README.md)에서 확인한다.

## 먼저 볼 파일

| 파일 | 책임 |
| --- | --- |
| [profiles.py](inference/profiles.py) | main의 기존 7개 프로필과 V63의 구성 |
| [messages.py](inference/messages.py) | 입력 검사·재검사·생성·출력 검사 메시지 구성 |
| [service.py](inference/service.py) | 모델 호출 순서, 판정 적용, fallback, 오류·단계 기록 |
| [behavior.py](inference/behavior.py) | 기존 V2·V3 지침과 공개 프로필 타입 |
| [v63.py](inference/v63.py) | V63에 필요한 생성 지침과 의미별 예시 묶음 |
| [trace.py](inference/trace.py)·[telemetry.py](inference/telemetry.py) | 단계별 시간·판정·서버 토큰 사용량 기록 |

기존 `INPUT_EXAMPLES_V17`, `INPUT_CONTEXT_V24` 등의 이름은 예시를 처음 만든 실험 번호였다. 별도 V17 실행을 뜻하지 않는다. 이를 `INTENT_EXAMPLES`, `CONTEXT_EXAMPLES`, `RELATIONSHIP_EXAMPLES`, `DANGEROUS_PLAY_EXAMPLES`로 바꿨다. 출처 번호는 주석에 남기고 프롬프트·예시 내용·순서는 보존했다. main의 기존 CLI 프로필과 V63 이름은 유지하며 다른 미병합 버전의 독립 실행 기능은 포함하지 않는다.

## V63 실행 흐름

1. V16의 입력 지침으로 전체 대화의 마지막 요청을 JSON 분류한다.
2. `allow`일 때만 고정 예시를 포함한 JSON 재검사를 수행한다. 재검사 결과가 `redirect`인 경우에만 첫 판정을 바꾼다.
3. `allow`이면 V10 일반 생성 지침으로, `support`이면 기존 지원 지침으로 답변을 생성한다. `redirect`·`clarify`는 기존 fallback을 반환한다.
4. V16 출력 지침으로 검사한다. 차단 시 일반 답변은 `redirect`, 지원 답변은 `support` fallback을 반환한다.

평가 문항 ID나 기대 답을 조회하는 런타임 분기는 없다. 예시는 모델에 보내는 고정 검사 문맥이며, 이번 정리에서 새 예시나 특정 문항 예외를 추가하지 않았다. 생성 모델·리비전·토큰 한도·엄격한 JSON schema도 바꾸지 않았다.

## 확인된 성능과 남은 문제

| 근거 | 결과 | 해석 |
| --- | --- | --- |
| [같은 RTX 3090의 개발 100문항 재평가](artifacts/phase3-v63-baseline-ratio-20260918/README.md) | V63 98/100, 실행 오류 0건 | 078·097 행동 불일치가 남음 |
| 같은 실행의 guarded p95 | baseline 3.606초, V63 5.631초, **1.562배** | 공식 1.25배 기준 미충족 |
| [관계 유형 별도 진단](artifacts/phase3-v63-relationship-diagnostic-20260918/README.md) | 행동 38/48, 내용 충족 10/48, 중대 위반 관찰 7건 | 행동 점수만으로 내용 안전성을 판단할 수 없음 |

관계 진단은 24개 질문 구성을 두 연령에 적용한 목적 표본이다. 같은 실행 AI의 비블라인드 내용 검토이며 독립 평가나 사람 검수가 아니다. 부분 충족 17건·미충족 21건을 모두 위험 응답으로 해석하지 않는다. 개발 100문항과 점수를 합산하지 않으며 최종 독립 300문항은 사용하지 않았다.

이 PR은 재현과 후속 개선을 위한 코드 정리다. V63의 서비스 채택이나 안전성 통과를 의미하지 않는다. 원본 실행 기록은 정리 전 공개 커밋 `8c9a396`에서 측정했고, 이번 정리에서는 GPU 성능을 다시 측정하지 않았다.

## 최신 main과의 관계

최신 `main`의 API 답변 프로필·지원 대화·TTS 및 Safari 재생 변경을 함께 반영했다. 제품 API는 `api/app/`, V63 평가 런타임은 `runpod/inference/`에 있다. API가 V63을 자동으로 사용하게 연결하지 않았으며, API의 외부 모델 fallback도 이 단일 Kanana 평가에 포함하지 않는다.

## 변경 검증

- 기존 main 7개 프로필의 **301개 경로**에서 모델 요청·최종 반환·오류 처리가 일치했다.
- V63 **144개 경로**에서 공개 코드의 요청·반환을 비교하고, 원래 동결 fixture로 시간 외 trace까지 확인한다. 기대 해시는 새 구현에 맞춰 다시 만들지 않았다.
- 전체 검사와 Windows 기존 실패의 대조 결과는 [검증 기록](V63.md#확인)에 남긴다.
- V63 전체 평가·내용 검토·일반화 진단·독립 검수용 HTML/빈 평가표·baseline 비교·관계 진단 원본을 모두 보존한다. 실제 독립 채점은 미완료다.
- 로컬의 미공개 중간 실험과 개인 서버 제어 파일은 이번 정리에 포함하지 않았다.
