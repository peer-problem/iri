# V50 입력 재검사 — JSON 규약 검토

V50의 추가 입력 검사는 팀이 요구한 표준 JSON 대신 분류명 한 단어를 받아 처리했다. 따라서 개발 행동 일치 97/100과 실행 오류 0건은 당시 구현의 관측값으로 보존하며, 규약을 충족한 결과로 보고하지 않는다.

## 확인한 문제

1. 모델에 JSON 없이 `allow`, `redirect`, `support`, `clarify` 중 한 단어만 출력하도록 요청했다.
2. 반환 문자열에 `raw.strip()`을 적용한 뒤 `InputVerdict`를 만들었다.
3. 이 방식은 모델이 반환한 JSON 자체를 엄격하게 검증하는 팀의 계약과 다르다.

아래 코드는 실험 당시 동결한 `source.zip`의 `runpod/inference/service.py`에서 발췌했다. 문서 가독성 수정 과정에서 코드 구문은 변경하지 않았다.

## 동결 소스 발췌

```python
            if self.profile in {"cascade_v49", "harm_audit_v50"} and verdict.decision == "allow":
                stage = "input_recheck"
                if trace:
                    trace.stages[stage] = StageTrace()
                messages = [dict(message) for message in input_messages]
                messages[0]["content"] = (
                    messages[0]["content"]
                    .replace(
                        "설명 없이 decision 필드만 있는 JSON을 출력한다. decision은 allow, redirect, support, clarify 중 하나다.",
                        "설명이나 JSON 없이 allow, redirect, support, clarify 중 분류명 한 단어만 출력한다.",
                    )
                    .replace(
                        "최종 JSON에는 decision 하나만 쓴다.", "최종 출력은 분류명 한 단어뿐이다."
                    )
                )
                with trace.measure(stage) if trace else nullcontext():
                    raw = await self.provider.complete(messages, max_tokens=80, guard=True)
                    recheck = InputVerdict(decision=raw.strip())
                    if trace:
                        trace.stages[stage].decision = recheck.decision
                    # Missing context alone must not overrule the original clear-topic verdict.
                    if recheck.decision == "redirect" or (
                        self.profile == "cascade_v49" and recheck.decision == "support"
                    ):
                        verdict = recheck
```

## 판정과 보관 근거

V50은 JSON 규약을 위반한 역사적 실험으로 보존한다. 다른 검사 단계와 어린이 정책을 유지했다는 사실만으로 추가 입력 검사의 위반이 해소되지는 않는다.

동결 소스 ZIP의 SHA256:

```text
6de08af5e36849e44bd5d049f6bde110317c1fd4d43f1739219ea175febdcfac
```

점수와 지연 및 내용상의 한계는 [V50 평가 보고서](README.md)를 참고한다.
