"""Build a self-contained, blind offline human review page (no network)."""
import argparse
import base64
import copy
import json
import mimetypes
from pathlib import Path

LABELS = {
    "tool_selection_quality": ["appropriate", "reasonable_but_redundant", "inappropriate", "unassessable"],
    "conflict_handling": ["addressed", "acknowledged_unresolved", "ignored", "not_applicable", "unassessable"],
    "stop_timing": ["appropriate", "premature", "overcalled", "no_legal_stop", "unassessable"],
    **{key: [True, False, "unassessable"] for key in ["evidence_sufficient", "premature_stop", "verdict_consistent", "unsupported_claim", "reasoning_faithful"]},
}


def image_uri(path):
    p = Path(path)
    return "data:" + (mimetypes.guess_type(p.name)[0] or "application/octet-stream") + ";base64," + base64.b64encode(p.read_bytes()).decode()


def render(data, destination):
    # Explicit allowlists exclude identity_map, original filenames and evaluator paths.
    common = ["record_id", "sample_id", "condition", "type", "review_priority", "needs_source", "evidence_references"]
    trajectory = ["agent_review", "confidence", "notes", "steps", "raw_final_output", "effective_final_output", "tool_cards"]
    call = ["step", "raw_attempt", "agent_label", "agent_confidence", "agent_reason", "evidence_gap", "expected_information_gain", "call_outcome", "trigger_reasons", "actor_request", "history", "previous_raw_retries", "budget", "exposed_tools", "tool_cards"]
    records, images, image_keys = [], {}, {}
    for original in data["trajectory_records"] + data["call_records"]:
        record = {k: copy.deepcopy(original[k]) for k in common + (trajectory if original["type"] == "trajectory" else call) if k in original}
        record["images"] = []
        paths = [original.get("image_path")] + original.get("crop_paths" if original["type"] == "trajectory" else "observed_crop_paths", [])
        for i, path in enumerate(paths):
            if path and Path(path).is_file():
                if path not in image_keys:
                    image_keys[path] = f"image_{len(images) + 1}"
                    images[image_keys[path]] = image_uri(path)
                record["images"].append({"label": "原图" if i == 0 else f"已观察裁片 {i}", "image_key": image_keys[path]})
            elif path:
                record["needs_source"] = True
        records.append(record)
    payload = json.dumps({"input_fingerprint": data["input_fingerprint"], "records": records, "images": images, "labels": LABELS}, ensure_ascii=False).replace("<", "\\u003c")
    html = PAGE.replace("__PAYLOAD__", payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")


PAGE = r'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Actor 独立人工复核</title><style>body{font:16px system-ui;margin:24px;max-width:1200px}button,select,textarea{font:inherit;margin:5px;padding:7px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f6;padding:12px}img{max-width:100%;max-height:550px}textarea{width:95%;height:90px}.labels{display:grid;grid-template-columns:repeat(2,1fr)}details{margin:12px 0}#message{color:#a33}</style>
<h1>Actor 独立人工复核</h1><p>先独立查看证据并锁定每个条件，再比较同图四条件。Agent 建议不是人工标签。CALL 仅展示调用之前的证据。暂存仅在本浏览器，请定期下载。</p>
<select id="kind"><option value="trajectory">80 条完整轨迹</option><option value="call">重点 CALL 队列</option></select><select id="picker"></select><button id="download">下载 human_reviews.json</button><label>载入 <input id="upload" type="file" accept=".json"></label><p id="progress"></p><p id="message"></p><main id="record"></main>
<script id="data" type="application/json">__PAYLOAD__</script><script>
const D=JSON.parse(document.getElementById('data').textContent), key='actor-human-review:'+D.input_fingerprint;
let reviews=JSON.parse(localStorage.getItem(key)||'{}');const $=id=>document.getElementById(id), escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function section(title,value){return '<details open><summary>'+escape(title)+'</summary><pre>'+escape(JSON.stringify(value,null,2))+'</pre></details>'}
function options(){let rows=D.records.filter(r=>r.type===$('kind').value);$('picker').innerHTML=rows.map(r=>'<option value="'+escape(r.record_id)+'">'+escape(r.record_id+' '+(r.review_priority||''))+'</option>').join('');show()}
function current(){return D.records.find(r=>r.record_id===$('picker').value)}
function show(){const r=current();if(!r)return;const h=reviews[r.record_id], proposed=r.type==='trajectory'?r.agent_review:r.agent_label;
let text='<h2>'+escape(r.sample_id+' / '+r.condition+(r.type==='call'?' / step '+r.step:''))+'</h2>'+(r.needs_source?'<p>本条存在缺源提示，必须核验后再判断。</p>':'');
text+=r.images.map(i=>'<figure><figcaption>'+escape(i.label)+'</figcaption><img src="'+D.images[i.image_key]+'"></figure>').join('');
if(r.type==='trajectory'){text+=section('可用工具说明',r.tool_cards)+section('完整 Actor 可见步骤（observation 与动作）',r.steps)+section('原始 STOP',r.raw_final_output)+section('有效终态',r.effective_final_output)}
else{text+=section('调用之前的历史',r.history)+section('同一步之前的原始重试',r.previous_raw_retries)+section('当前 Actor 请求',r.actor_request)+section('当前预算与可用工具',{budget:r.budget,exposed_tools:r.exposed_tools})+section('可用工具功能与规则',r.tool_cards)}
text+=section('Agent 建议（需人工核验）',r.type==='trajectory'?{labels:r.agent_review,confidence:r.confidence,notes:r.notes,evidence_references:r.evidence_references}:{label:r.agent_label,confidence:r.agent_confidence,reason:r.agent_reason,evidence_gap:r.evidence_gap,expected_information_gain:r.expected_information_gain,call_outcome:r.call_outcome,trigger_reasons:r.trigger_reasons,evidence_references:r.evidence_references});
text+='<div class="labels">';const fields=r.type==='trajectory'?D.labels:{call:D.labels.tool_selection_quality};for(const [field,values] of Object.entries(fields)){let value=h?h.human_label:proposed;if(r.type==='trajectory')value=value?.[field];text+='<label>'+escape(field)+' <select data-field="'+field+'">'+values.map(v=>'<option value="'+escape(JSON.stringify(v))+'" '+(v===value?'selected':'')+'>'+escape(v)+'</option>').join('')+'</select></label>'}text+='</div><textarea id="notes" placeholder="填写中文人工理由，引用具体证据"></textarea><p><label><input id="seen" type="checkbox">我已逐条阅读本记录的图像和证据</label></p><button data-status="confirmed">单条接受 Agent 建议</button><button data-status="modified">保存人工修改</button><button data-status="needs_source">缺少证据</button><button data-status="disputed">争议待裁决</button><p>本条状态：'+escape(h?.review_status||'未人审')+'</p>';
const peers=D.records.filter(p=>p.type==='trajectory'&&p.sample_id===r.sample_id);if(r.type==='trajectory'&&peers.length===4&&peers.every(p=>['confirmed','modified'].includes(reviews[p.record_id]?.review_status))){text+=section('已完成四条件独立锁定：现在可作配对比较',peers.map(p=>({condition:p.condition,steps:p.steps,raw_final_output:p.raw_final_output,effective_final_output:p.effective_final_output,human_review:reviews[p.record_id]})))}
$('record').innerHTML=text;$('notes').value=h?.human_notes||'';document.querySelectorAll('[data-status]').forEach(b=>b.onclick=()=>save(b.dataset.status));$('progress').textContent='已暂存 '+Object.keys(reviews).length+' / '+D.records.length+' 条';}
function save(status){const r=current(),notes=$('notes').value.trim();if(['confirmed','modified'].includes(status)&&(!$('seen').checked||!notes)){ $('message').textContent='确认或修改前必须勾选已阅读证据，并填写人工理由。';return}
let label=r.type==='trajectory'?{}:null;document.querySelectorAll('[data-field]').forEach(s=>{const v=JSON.parse(s.value);if(r.type==='trajectory')label[s.dataset.field]=v;else label=v});if(status==='confirmed'){const agent=r.type==='trajectory'?r.agent_review:r.agent_label;const equal=r.type==='trajectory'?Object.keys(D.labels).every(f=>label[f]===agent[f]):label===agent;if(!equal){ $('message').textContent='标签已改变，请使用保存人工修改。';return}}
reviews[r.record_id]={reviewer_type:'human',review_status:status,human_label:label,human_notes:notes,reviewed_at:new Date().toISOString(),evidence_read:$('seen').checked};localStorage.setItem(key,JSON.stringify(reviews));$('message').textContent='已暂存。';show()}
$('download').onclick=()=>{const blob=new Blob([JSON.stringify({version:1,input_fingerprint:D.input_fingerprint,records:reviews},null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='human_reviews.json';a.click();URL.revokeObjectURL(a.href)};
$('upload').onchange=async e=>{try{const v=JSON.parse(await e.target.files[0].text());if(v.version!==1||v.input_fingerprint!==D.input_fingerprint)throw Error('输入指纹或版本不匹配');for(const [id,h] of Object.entries(v.records)){const r=D.records.find(r=>r.record_id===id);if(!r||h.reviewer_type!=='human'||!['confirmed','modified','needs_source','disputed'].includes(h.review_status))throw Error('记录或状态无效');const vals=r.type==='trajectory'?D.labels:{call:D.labels.tool_selection_quality};for(const [f,allowed] of Object.entries(vals)){const value=r.type==='trajectory'?h.human_label?.[f]:h.human_label;if(!allowed.includes(value))throw Error('标签枚举无效')}if(['confirmed','modified'].includes(h.review_status)&&(!h.evidence_read||!h.human_notes?.trim()||!h.reviewed_at))throw Error('人工证据确认信息缺失')}
reviews=v.records;localStorage.setItem(key,JSON.stringify(reviews));$('message').textContent='已载入。';show()}catch(err){$('message').textContent=err.message}};
$('kind').onchange=options;$('picker').onchange=show;options();</script></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(__file__).with_name("review_data.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "review_packets/human_review.html")
    args = parser.parse_args()
    render(json.loads(args.data.read_text(encoding="utf-8")), args.output)
    print(f"已生成离线人审页面：{args.output}")


if __name__ == "__main__":
    main()
