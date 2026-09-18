# V50 실행·재현 안내

이 버전은 추가 학습이나 별도 가중치 없이 같은 Kanana 모델의 지침과 검사 절차를 선택한다. 이 폴더는 평가 근거를 보관하고, 실행 코드는 공통 `runpod/inference/`에서 관리한다.

**V50은 비JSON 재검사 규약 위반을 그대로 재현하는 역사적 실험이다. 서비스 채택 후보로 사용하지 않는다.**

## 실행 코드와 준비

- 프로필: `harm_audit_v50`
- [입력·재검사·출력 처리](../../inference/service.py)
- [동결 지침과 합성 예시](../../inference/selected_profiles.py)
- [프로필 등록](../../inference/behavior.py), [설정 로더](../../settings.py)
- [새 PC 및 GPU 준비](../../SELECTED_PROFILES.md): 저장소 복제, Python 3.12, 인증 설정, 고정 리비전 서빙

공통 준비를 마치고 모델 서버를 실행한 상태에서, **저장소 루트**에서 아래 명령을 실행한다. 첫 실행은 `--limit 2`를 추가해 연결을 확인할 수 있다. 전체 평가는 해당 옵션 없이 실행한다.

```console
uv run --project runpod python -X utf8 -m runpod.operations.evaluate --behavior-profile harm_audit_v50 --mode guarded --trace-stages --data runpod/artifacts/phase3-v50-full-20260918/full100/harm_audit_v50/20260918T025438Z-kanana-833527d6/dataset.jsonl --output runpod/runs/v50-reproduction
```

결과는 지정한 출력 폴더 아래 새 타임스탬프 폴더에 저장된다. 기존 보고서의 결과·검수표는 덮어쓰지 않는다. API로 사용할 경우 해당 실행 환경의 `BEHAVIOR_PROFILE=harm_audit_v50`를 명시한다. 환경 변수가 없을 때의 기본값은 `baseline`이다.

## 검증 범위

- 공개 구현을 이 버전의 **원래 동결 소스 ZIP**과 비교했다. 출처 해시는 [공유 목록](share-manifest.json)에 있다.
- 두 연령대, 단일·다중 대화, 입력·출력 판정 및 오류 경로 144개에서 모델 요청과 반환 행동·오류·단계 기록이 동일했다.
- 기존 개발 100문항의 실제 대화 110턴을 입력으로 사용한 요청 비교도 일치했다. 이 검사는 모의 모델 응답을 사용한 코드 동등성 검사다.
- 새 PC/GPU에서 100문항 점수와 p95가 재측정된 것은 아니다. 보고서의 수치는 원래 실험 결과이며, 장비·드라이버·패키지에 따른 차이는 새 결과로 확인한다.
- 행동 일치와 내용 안전성·정확성은 별개다. 독립 답변 검수는 아직 완료하지 않았다.

로컬 요청 계약 테스트:

```console
uv run --project runpod python -X utf8 -m pytest -c runpod/pyproject.toml runpod/tests/test_selected_profiles.py -q
```
