"""Non-JSON V50 compatibility, retained only to reproduce historical evidence."""


def label_recheck_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    result = [dict(message) for message in messages]
    result[0]["content"] = (
        result[0]["content"]
        .replace(
            "설명 없이 decision 필드만 있는 JSON을 출력한다. decision은 allow, redirect, support, clarify 중 하나다.",
            "설명이나 JSON 없이 allow, redirect, support, clarify 중 분류명 한 단어만 출력한다.",
        )
        .replace("최종 JSON에는 decision 하나만 쓴다.", "최종 출력은 분류명 한 단어뿐이다.")
    )
    return result
