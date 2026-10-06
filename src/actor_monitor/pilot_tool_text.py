"""The fixed three-family tool input for the paired pilot."""

from __future__ import annotations

from agent.tools import FAMILIES, FEATURE_UNITS
from .tool_text import FEATURE_LABELS


FORMAL_FAMILIES = ("texture_lbp", "compression_dct", "noise_residual")
FORMAL_NOTICE = (
    "以下是这张图实际取得的三类取证工具读数。真图参考区间来自另取的 100 张真图，"
    "仅描述该样本的 5%～95% 范围：落在区间内不能证明是真图，落在区间外也不能证明是 AI 生成。"
    "只有读数确实超出区间时才能称其相对区间偏高或偏低；不要引用未列出的读数。"
)


def format_formal_tool_results(results: list[dict], refs: dict) -> str:
    lines = [FORMAL_NOTICE]
    for family in FORMAL_FAMILIES:
        result = next(item for item in results if item["tool"] == family)
        lines.append(f"【{FAMILIES[family]['label']}】")
        if not result["ok"]:
            lines.append(f"未取得读数：{result['error']}")
            continue
        for feature, value in result["values"].items():
            unit = FEATURE_UNITS.get(feature, "")
            line = f"{FEATURE_LABELS[feature]}：{value:.6f} {unit}".rstrip()
            if feature in refs:
                low, high = refs[feature]
                line += f"；真图参考区间：{low:.6f}～{high:.6f}"
            lines.append(line)
    return "\n".join(lines)
