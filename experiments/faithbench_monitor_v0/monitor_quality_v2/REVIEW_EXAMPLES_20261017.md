# 反馈监督实际样例（非模型生成结果）

以下为规则构造/助手审核参考；证据按真实ID回填。为便于阅读只展示所引证据，训练输入包含完整资料。尚未训练，不能据此声称Monitor会输出这些结果。

## feedback:ragtruth:8809:time_binding:wrong

```json
{
  "id": "feedback:ragtruth:8809:time_binding:wrong",
  "审核范围": "整个待核回答",
  "指定主张": null,
  "待核回答": "结构化hours记录显示，周四营业至19:00。 资料中的商家名称为“Delicious Expressions”。 资料中商家总体评分为5.0星。资料中所列第1条评论的评分为5.0星。",
  "相关证据": [
    {
      "id": "E012",
      "path": [
        "hours",
        "Thursday"
      ],
      "value": "8:0-18:0"
    },
    {
      "id": "E013",
      "path": [
        "name"
      ],
      "value": "Delicious Expressions"
    },
    {
      "id": "E020",
      "path": [
        "business_stars"
      ],
      "value": 5.0
    },
    {
      "id": "E021",
      "path": [
        "review_info",
        0,
        "review_stars"
      ],
      "value": 5.0
    }
  ],
  "目标参考": {
    "结论": "revise",
    "问题": [
      {
        "状态": "明确错误",
        "回答原文": "结构化hours记录显示，周四营业至19:00。",
        "证据ID": [
          "E012"
        ],
        "理由": "该记录的周四关门值为18:00，不能把其他值19:00用于这一天。",
        "建议": "将周四关门时间改为18:00，保留商家名称及其他有据内容。"
      }
    ],
    "保留": [
      {
        "回答原文": "资料中的商家名称为“Delicious Expressions”。",
        "证据ID": [
          "E013"
        ]
      },
      {
        "回答原文": "资料中商家总体评分为5.0星。",
        "证据ID": [
          "E020"
        ]
      },
      {
        "回答原文": "资料中所列第1条评论的评分为5.0星。",
        "证据ID": [
          "E021"
        ]
      }
    ],
    "说明": "只修正有依据的具体错误，保留其余有据主张。"
  }
}
```

## contract:000:mapping_policy_boundary:misreported

```json
{
  "id": "contract:000:mapping_policy_boundary:misreported",
  "审核范围": "核对原始信号归因及direction记法是否违反给定映射规则；事实错误与缺规则分别处理。",
  "指定主张": null,
  "待核回答": "local原始signal为synthetic_like；Actor保留这个原始信号，并将direction记为inconclusive。 当前剩余工具调用额度为0次。局部工具实际返回的原始signal是real_like。局部工具可能对真实图像误报，分数强度不代表校准概率。",
  "相关证据": [
    {
      "id": "E008",
      "path": [
        "local_return"
      ],
      "value": {
        "tool": "local_texture_analyzer",
        "signal": "real_like",
        "strength": "moderate",
        "limitations": "真实图像也可能出现局部误报，不应单独作为最终结论。强度是原始分数幅度的固定描述，不代表校准概率。"
      }
    },
    {
      "id": "E007",
      "path": [
        "mapping_policy"
      ],
      "value": "未提供原始signal到Actor证据direction的强制映射规则。"
    },
    {
      "id": "E003",
      "path": [
        "actor_evidence"
      ],
      "value": {
        "observation": "local原始signal为real_like",
        "direction": "inconclusive"
      }
    },
    {
      "id": "E001",
      "path": [
        "budget"
      ],
      "value": {
        "remaining_calls": 0,
        "available_tools": [
          "provenance_inspector"
        ],
        "used_tools": [
          "global_forensic_analyzer",
          "local_texture_analyzer",
          "complementary_forensic_analyzer"
        ]
      }
    },
    {
      "id": "E002",
      "path": [
        "rules"
      ],
      "value": {
        "tool_cards": {
          "global_forensic_analyzer": {
            "purpose": "检查图像区域表征与独立真实图参考库的偏离，并提供可定位区域和图块供核查。",
            "evidence_type": "参考表征偏离证据",
            "useful_when": "需要检查区域表征是否偏离真实参考分布，并决定是否获取其他独立证据。",
            "returns": [
              "scope: 检查区域数",
              "observations 或 findings: 区域偏离统计与空间模式",
              "most_atypical_regions 或 highlighted_regions: top-3 区域的 bbox、偏离百分位和图块",
              "limitations: 证据局限"
            ],
            "limitations": "偏离百分位是相对真实参考图块的距离位置，不是假图概率，也不能证明图像来源；罕见真实内容和后处理也可能高度偏离。本工具不返回 real/fake signal 或 classifier score。"
          },
          "local_texture_analyzer": {
            "purpose": "检查局部纹理与残差特征中的合成倾向模式。",
            "evidence_type": "局部纹理/残差证据",
            "useful_when": "全局证据不确定，或需要不同空间尺度的补充证据。",
            "returns": [
              "signal: real_like 或 synthetic_like",
              "score: raw_score",
              "strength: low/moderate/high"
            ],
            "limitations": "真实图像也可能出现局部误报，不应单独作为最终结论。强度是原始分数幅度的固定描述，不代表校准概率。"
          },
          "complementary_forensic_analyzer": {
            "purpose": "使用不同训练与表征流程的额外模型，给出补充取证意见。",
            "evidence_type": "互补学习型取证证据",
            "useful_when": "现有证据较弱、不完整或互相矛盾。",
            "returns": [
              "signal: real 或 fake",
              "score: synthetic_score",
              "strength: low/moderate/high"
            ],
            "limitations": "分布变化时可能不可靠，应与其他证据共同解释；决策阈值沿用独立校准结果。"
          },
          "provenance_inspector": {
            "purpose": "检查 C2PA、EXIF、XMP、相机信息和软件信息等非像素来源线索。",
            "evidence_type": "来源凭据/元数据证据",
            "useful_when": "图像来源、拍摄或编辑链条可能提供独立证据。",
            "returns": [
              "signal: real/fake/inconclusive",
              "score: null",
              "strength: none/weak/moderate/strong"
            ],
            "limitations": "没有元数据或 C2PA 凭据不代表图像由 AI 生成；缺少来源信息必须视为 inconclusive。未经验证或不可信的声明不能证明来源。"
          }
        },
        "review_contract": {
          "NON_DIRECTIONAL_GLOBAL": "global表征偏离不是真假概率或方向票；无异常也不能据此证明真实。",
          "SUMMARY_LIMIT": "检查总数、阈上异常数和top-3成员分别核对；异常阈值为95。没有全量值时，不能捏造未返回均值。",
          "ACTION_BUDGET": "当前剩余调用额度为0时不能追加CALL，但可根据已有材料修正说明。",
          "TOOL_FACT": "只核实际提供的返回。工具卡不是文字/字段白名单；部分节选不足以证明完整返回从未包含某内容。",
          "UNSPECIFIED": "没有冻结综合权重、置信度充分性或冲突下STOP政策，不因此强定哪种最终标签或必须继续调用。"
        }
      }
    }
  ],
  "目标参考": {
    "结论": "revise",
    "问题": [
      {
        "状态": "明确错误",
        "回答原文": "local原始signal为synthetic_like",
        "证据ID": [
          "E008"
        ],
        "理由": "原返回为real_like，此处却抄成相反的synthetic_like。映射规则未定不使这个原始事实错误变成未决。",
        "建议": "把原始signal改回real_like并保留局限；direction映射另列未决，不强改字段。"
      },
      {
        "状态": "未决",
        "回答原文": "将direction记为inconclusive",
        "证据ID": [
          "E007",
          "E003"
        ],
        "理由": "实际direction确为inconclusive，但未提供强制映射规则，不能单凭字段不同判错。",
        "建议": "保留该映射判断未决，先明确规则，不擅自规定必须抄原始signal。"
      }
    ],
    "保留": [
      {
        "回答原文": "当前剩余工具调用额度为0次。",
        "证据ID": [
          "E001"
        ]
      },
      {
        "回答原文": "局部工具实际返回的原始signal是real_like。",
        "证据ID": [
          "E008"
        ]
      },
      {
        "回答原文": "局部工具可能对真实图像误报，分数强度不代表校准概率。",
        "证据ID": [
          "E002"
        ]
      }
    ],
    "说明": "只纠正明确违反所给事实或契约的主张，不替Actor指定真假结论。"
  }
}
```

## natural_review:ragtruth:1886:0:problem

```json
{
  "id": "natural_review:ragtruth:1886:0:problem",
  "审核范围": "仅核对指定主张；不声称整篇其余内容正确。",
  "指定主张": "in a South Korean supermarket",
  "待核回答": "Korea's \"buddha jjigae,\" also known as army stew, has origins dating back to the Korean War when cooks had to make do with US Army rations. One popular ingredient in this type of stew is canned Spam. The dish has become a classic example of \"necessity being the mother of deliciousness.\" During the premiere episode of \"Parts Unknown\" on Sunday, April 26, at 9 p.m. ET/PT, Anthony Bourdain discussed the history and flavor of budae-jjigae while cooking it up in a South Korean supermarket. To make budae-jjigae, cooks must first simmer the anchovy kelp broth, which will serve as the base for the stew. They should also thinly slice the Spam, hot dogs, and Korean rice cakes and chop the garlic and green onions. Once the broth is ready, add the meat, vegetables, and seasonings to the pot and let it simmer for several minutes until the ingredients are cooked through. The dish is best served with steamed rice or enjoyed on its own.",
  "相关证据": [
    {
      "id": "E001",
      "path": [],
      "value": "Korea's buddae-jjigae -- or \"army stew\" as it's often called -- dates back to the scarce years of the Korean War when local cooks had to get inventive with U.S. Army rations. While jiigae can refer to any variety of stews, this particular version just happens to feature a variety of canned, precooked meat, most notably SPAM in all its glazed and gelatinous glory. \"It's, in fact, a classic example of necessity being the mother of deliciousness,\" Anthony Bourdain says of the dish during the premiere episode of \"Parts Unknown\" on Sunday, April 26, at 9 p.m. ET/PT. The host of CNN's \"Parts Unknown\" recently stopped by Anderson Cooper's kitchen to cook up the spicy and funky stew, and talk about his 24 intoxicating hours in the country's capital of Seoul. So, it's probably a good thing budda-jiigae is also a storied hangover cure. Budae-jjigae. (Serves 2-4) Courtesy of Choi Ji-hwang. Ingredients:. 1 12-oz can of Spam, cut into ½-inch slices. 1½ cups tong baechu kimchi, or traditional fermented cabbage (can be found in a well-stocked supermarket or Korean specialty store) 8 oz. sliced Korean rice cakes (can be found in a well-stocked supermarket or Korean specialty store) 1 white onion, thinly sliced. 2 spring onions, thinly sliced. 5 garlic cloves, crushed. 3 hot dogs, thinly sliced. 8 oz. ground pork. 3 tablespoons soy sauce. 2 tablespoons gochujang, or hot pepper paste (can be found in a well-stocked supermarket or Korean specialty store) 3 tablespoons gochukaru, or hot pepper flakes (can be found in a well-stocked supermarket or Korean specialty store) 3 tablespoons cheongju, or a clear rice wine similar to sake. 3 cups anchovy kelp broth (recipe below) 3 tablespoons baked beans. 1½ cups water. 1 package ramen noodles (just the noodles) For the anchovy kelp broth:. 1 dried shiitake mushroom. 4 large dried anchovies, heads and guts removed, wrapped in cheesecloth. 1 5x3\" sheet of dried, edible kelp or kombu (can be found in a well-stocked supermarket or Korean specialty store) 4 cups water. ½ teaspoon salt. Cooking instructions:. 1. Place the ingredients for the anchovy broth in a pot and simmer for 20-30 minutes until the flavors are fully infused. Strain and set aside. 2. Place the Spam, kimchi, rice cakes, onions, garlic, hot dogs and ground pork in small separate piles in the bottom of a shallow pot. 3. Add the soy, gochujang, gochukaru and cheongju to the pot and slowly pour the anchovy kelp broth in. Put the baked beans on top and add the water. Place pot over high heat and bring contents to a steady simmer. 4. Cook for 5-10 minutes, then add the ramen noodles. Ladle broth over the noodles to help them break apart. Continue to cook for 2-3 minutes until noodles are just about cooked through, but definitely still chewy. Serve with steamed rice or enjoy on its own.\n"
    }
  ],
  "目标参考": {
    "结论": "revise",
    "问题": [
      {
        "状态": "明确错误",
        "回答原文": "in a South Korean supermarket",
        "证据ID": [
          "E001"
        ],
        "理由": "来源说Bourdain到Anderson Cooper的厨房烹饪；韩国超市出现在配料购买说明中，不是这次烹饪地点。",
        "建议": "把这处地点改为Anderson Cooper的厨房；节目首播和厨房访问没有被明确说成同一事件，不额外合并时间。"
      }
    ],
    "保留": [
      {
        "回答原文": "One popular ingredient in this type of stew is canned Spam.",
        "证据ID": [
          "E001"
        ]
      }
    ],
    "说明": "仅对指定主张及明确保留项作来源核查，不宣称全文无其他错误。"
  }
}
```
