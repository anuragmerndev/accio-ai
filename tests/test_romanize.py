from wisper.romanize import FEW_SHOTS, SYSTEM_PROMPT, build_messages


def test_messages_structure():
    msgs = build_messages("कल मीटिंग है")
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    roles = [m["role"] for m in msgs]
    assert roles == ["system"] + ["user", "assistant"] * len(FEW_SHOTS) + ["user"]
    assert msgs[-1]["content"] == "कल मीटिंग है"


def test_system_prompt_forbids_translation():
    assert "Do not translate" in SYSTEM_PROMPT
