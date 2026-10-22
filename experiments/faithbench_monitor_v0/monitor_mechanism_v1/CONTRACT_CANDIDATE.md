# 显式审核契约候选（M2，尚未批准执行）

2026-10-13。依据[D1结果](REPORT_D1_20261013.md)，准备一个可审阅的下一步候选。M1与M2都沿用已经冻结的M1 system/user与原四例packet；M2在packet中额外加入下列`review_contract`，并在system末尾追加本文的解释指令。原工具事实、动作、预算和schema不改，未决不变成合理gold。

这包含显式规则清单与解释指令两项耦合改动，不能把效果归于单个字段。未生成新请求包、冻结、评分或API；没有批准读取新来源、闭环或改Actor。

```json
{
  "review_contract": {
    "provided_rules": {
      "STOP_VERDICT": {
        "source": "parser_contract.STOP_verdict",
        "rule": "STOP最终verdict只允许real/fake；不是证据direction的枚举。"
      },
      "DIRECTION_ENUM": {
        "source": "action_schema.properties.current_evidence.items.properties.direction.enum",
        "rule": "使用实际给定的direction枚举；none合法，但枚举本身不定义字段如何映射工具信号。"
      },
      "TOOL_FACT": {
        "source": "trajectory.steps中当时已返回的tool_observation",
        "rule": "核对实际提供的文字和数值；工具卡returns未列出不等于实际返回不存在。"
      },
      "NON_DIRECTIONAL_GLOBAL": {
        "source": "tool_cards.global_forensic_analyzer.limitations及主方案的非方向证据规则",
        "rule": "表征偏离不作真假方向票；无异常也不自动支持real。"
      },
      "SUMMARY_LIMIT": {
        "source": "实际返回的scope/observations/most_atypical_regions",
        "rule": "top-3、异常计数和检查数分别核对；未提供全量数据时不得无依据扩写全区值/均值。"
      },
      "EFFECTIVE_SIGNAL": {
        "source": "tool_cards的signal说明及实际tool_observation.signal",
        "rule": "保留真实工具信号及其限制；明确相反的原始方向信号不能称一致。原始信号冲突与direction字段映射是不同检查，不能因字段inconclusive就抹去已经保留的real_like/synthetic_like信号。"
      },
      "ACTION_BUDGET": {
        "source": "budget/available_tools/parser_contract/action_schema",
        "rule": "预算和动作枚举按实际输入核对；剩余预算不等于必须补证。"
      }
    },
    "unspecified_rules": {
      "DIRECTION_MAPPING": "没有规定current_evidence.direction必须机械复制每个工具信号或视觉印象。保留原信号/解释但字段为inconclusive时，要求澄清，不能仅凭映射差异判明确错误。",
      "HIGH_DEVIATION_TERM": "没有定义Actor文字中的高偏离必然等于过异常阈值。可以区分top-3和异常数，不能把相对排序措辞自动判成阈上计数捏造。",
      "STOP_CONSENSUS": "没有规定存在模型冲突或未达成一致就禁止低置信度二选一。缺少取舍解释可澄清，不能仅凭无共识认定二元verdict矛盾。",
      "MODEL_WEIGHTS_CONFIDENCE": "没有冻结模型综合权重或置信度充分性政策，不能规定哪一个工具必然优先或置信度必须升降。",
      "VISUAL_DIRECTION": "Monitor没有像素，视觉语义/弱倾向与direction的映射未冻结；对视觉事实和方向冲突指控分别核对，不凭字段或工具没对象名作确定判断。"
    }
  }
}
```

追加解释指令：

```text
输入中的review_contract是本次明确给出的审核契约，不是逐例参考答案。明确错误指控须注明适用的provided_rules规则ID，并说明真实返回/Actor原句如何违反它。unspecified_rules所列规则没有冻结：依赖这些规则才能成立的指控应标未决或澄清建议，不得标明确错误或提出强制修正。禁止用提供的枚举规则偷换成未提供的机械映射/综合权重规则。即使定位原核心成功，也要逐条核对自己的附加指控是否依赖未定义规则。对可确认的事实错误仍须指出并修复，不要因有未决边界而笼统放行整个案例。
```

候选比较为同四例M1/M2各一次，共8个新请求、生成上限16384/请求、拟费用封顶$0.30，不用GPU、不执行反馈、不使用44保留组。提示包针对已曝光失误设计，进一步结果只能作开发诊断。此前8请求授权不覆盖这批。

本地内存预核：输入token保守字节上界271778、总生成上限131072，高峰口径上界$0.2388198，低于拟$0.30封顶。规则清单无case编号/特定阈值答案；除新增契约外原packet字段和值不变，M1条件与上一批M1逐字相同。未保存新请求包或发送新请求；实际冻结前仍须核对最终版本。

实际冻结前检查JSON规则源与当前schema/工具卡相符、没有case编号/数值答案/GT、共用部分逐字一致、输入开销与费用仍在上限内，并另存事前参考。仍按D1原可判锚点与未决边界评价，不靠降低标准通过。若模型错误引用provided_rules解释未决指控，同样不算通过；路径或规则ID存在并不证明语义依据。
