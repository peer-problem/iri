# V50 JSON 계약 감사

동결소스ZIP의 runpod/inference/service.py 에서 발췌했다. source.zip SHA256 `6de08af5e36849e44bd5d049f6bde110317c1fd4d43f1739219ea175febdcfac`. 입력재검사만단어판정으로바뀌며표준JSON계약이탈이다. 기록된97점과실행오류0을규약준수로해석하지않는다.

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
