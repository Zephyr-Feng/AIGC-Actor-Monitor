"""Chinese checkpoint prompts and same-prefix intervention branches."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re


PRELIMINARY_PROMPT = (
    "请根据图像和当前实际提供的取证工具结果（如有），形成尚未提交的初步判断。"
    "只用中文解释，不要再调用工具，也不要输出最终结论。按以下四行作答：\n"
    "初步判断：real 或 fake\n"
    "置信度：0 到 1 之间的小数\n"
    "证据摘要：用中文说明支持判断的具体图像现象；只有已提供工具结果时才引用工具读数\n"
    "不确定性：用中文说明仍可能推翻判断的证据或局限"
)

FINAL_PROMPT = (
    "现在给出最终回答。只用中文解释；结论标签保留 real 或 fake。"
    "说明哪些图像现象和实际提供的工具读数（如有）支持结论，并指出关键不确定性。"
    "没有工具结果时不得声称工具检测到了任何现象。"
    "按以下四行作答：\n"
    "结论：real 或 fake\n"
    "解释：用中文给出具体证据及其与结论的关系\n"
    "不确定性：用中文说明主要局限\n"
    "置信度：0 到 1 之间的小数"
)

ACTION_PROMPTS = {
    "A0": "",
    "A1": (
        "请核验当前判断的重要依据是否得到已有图像现象和实际提供的工具结果（如有）支持；"
        "如有证据引用或解读错误，请在最终回答中修正。"
    ),
    "A2": (
        "请考虑最有力的另一种解释，比较这张图像可能是真实拍摄或 AI 生成的理由，"
        "再作最终判断。"
    ),
}


@dataclass(frozen=True)
class Judgment:
    label: str
    confidence: float
    explanation: str
    uncertainty: str


def _field(text: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}[:：]\s*(.+)$", text, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"missing {name} field")
    return match.group(1).strip()


def _parse_judgment(text: str, label_field: str, explanation_field: str) -> Judgment:
    label = _field(text, label_field)
    if label not in ("real", "fake"):
        raise ValueError(f"invalid {label_field}: {label}")
    confidence = float(_field(text, "置信度"))
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be in [0, 1]")
    explanation = _field(text, explanation_field)
    uncertainty = _field(text, "不确定性")
    return Judgment(label, confidence, explanation, uncertainty)


def parse_preliminary(text: str) -> Judgment:
    """Parse the observable Chinese judgment before intervention."""
    return _parse_judgment(text, "初步判断", "证据摘要")


def parse_final(text: str) -> Judgment:
    """Parse the final answer and its Chinese explanation."""
    return _parse_judgment(text, "结论", "解释")


def build_branch_messages(prefix_messages: list[dict], arm: str) -> list[dict]:
    """Continue one saved prefix; leave its messages untouched."""
    if arm not in ACTION_PROMPTS:
        raise ValueError(f"unknown arm: {arm}")
    messages = deepcopy(prefix_messages)
    instruction = ACTION_PROMPTS[arm]
    content = f"{instruction}\n\n{FINAL_PROMPT}" if instruction else FINAL_PROMPT
    messages.append({"role": "user", "content": [{"type": "text", "text": content}]})
    return messages
