"""Offline, read-only report derived from a real workflow session and source snapshots."""
from html import escape
import difflib
import json
from pathlib import Path
from .extraction_workflow import load_session, facts, text, ROOT
from .interview_extraction import evidence_view

STYLE = """
:root{--ink:#303248;--green:#008f70;--mint:#00cd96;--bg:#f4faf8;--muted:#667085}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:19px/1.55 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif}header{padding:22px 38px 15px;border-bottom:1px solid #cde6de;background:#fff}h1{font-size:32px;margin:0 0 6px}h2{font-size:25px;margin:0 0 14px}h3{font-size:20px;color:var(--green);margin:0 0 9px}p{margin:0 0 12px}.meta{font-size:15px;color:var(--muted)}nav{padding:15px 38px;display:flex;gap:12px;border-bottom:1px solid #cde6de;background:#fff}nav a{color:var(--ink);text-decoration:none;font-size:17px;padding:6px 12px;border-radius:6px}nav a.selected{background:#ddf5ec;color:#006d53;font-weight:650}main{padding:25px 38px;max-width:1660px;margin:auto}section{display:none}section.active{display:block}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{background:white;border:1px solid #d5e9e2;border-radius:10px;padding:20px 24px;margin-bottom:16px}.tag{display:inline-block;background:#dff5eb;border-radius:5px;padding:2px 9px;color:#006b50;font-size:15px}.status{background:#fef2da;color:#865000}.small{font-size:16px;line-height:1.6}.doc{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;margin:0;font-size:18px;line-height:1.65}.code{font:16px/1.65 ui-monospace,SFMono-Regular,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;border-radius:8px;padding:15px}.claim{font-size:22px;font-weight:650;line-height:1.6}.quote{border-left:4px solid var(--mint);padding-left:16px;margin:10px 0;white-space:pre-wrap}.bad{color:#b54708}summary{cursor:pointer;color:var(--green)}table{width:100%;border-collapse:collapse;font-size:17px}td,th{padding:10px;border-bottom:1px solid #e4ede8;vertical-align:top;text-align:left}.line{color:#8a94a0;display:inline-block;width:40px;user-select:none}select{font:18px inherit;padding:8px;margin-bottom:16px}button{cursor:pointer}a{color:#007f63}.notice{border-left:4px solid #e2a83b;padding-left:15px;color:#705222}ul{padding-left:24px}footer{margin-top:20px;font-size:14px;color:var(--muted)}
"""

def e(value): return escape(str(value),quote=True)
def doc(value): return '<pre class="doc">'+e(value)+'</pre>'
def card(title,body): return '<div class="card"><h3>'+e(title)+'</h3>'+body+'</div>'
def code(value): return '<pre class="code">'+e(value)+'</pre>'

def render_report(ws,path):
    s=load_session(ws,path);sn=s['snapshots'];task=s['task']
    status={'active':'等待继续调用','awaiting_review':'等待 FDE 核查','awaiting_apply':'等待 FDE 确认修改','completed':'本轮已确认并保存','failed':'本轮中断','applying':'保存中，可恢复'}[s['status']]
    before=text(ws,sn['business_model']['path']);notes=text(ws,sn['notes']['path'])
    sections={}
    sections['task']=card('本轮要解决的问题','<p class="claim">'+e(task['goal'])+'</p>')
    sections['task']+='<div class="grid">'+card('已有业务模型',doc(before))+card('已有核查记录与待核项',doc(notes))+'</div>'
    cfg=ws.verify(sn['extraction_config'])
    sections['task']+=card('学员调整的位置',code(json.dumps({'goal':task['goal'],'sources':cfg['sources'],'focus_questions':cfg['focus_questions'],'prompt':cfg['prompt'],'skill':task['skill']},ensure_ascii=False,indent=2)))
    sections['skill']=card('本轮实际加载的 Skill',doc(text(ws,sn['skill']['path'])))
    sections['skill']+=card('执行中的工具','<p>inspect_materials → extract_candidates → show_evidence → request_review → propose_update</p><p class="small">以上为可调用能力。实际调用顺序由本轮模型消息与工具记录核对；核查反馈和写入确认来自 FDE。</p>')
    events=''.join('<tr><td>'+str(t['step'])+'</td><td>'+e(t['name'])+'</td><td>'+e(t['result'].get('status',t['result'].get('semantic_review','已返回结果')))+'</td></tr>' for t in s['tool_events'])
    sections['calls']=card('实际模型与工具调用','<p><span class="tag">'+e('真实模型调用' if any(c['mode']=='live' for c in s['calls']) else '机制测试／固定回复')+'</span> <span class="tag status">'+e(status)+'</span></p><table><tr><th>步骤</th><th>模型选择的工具</th><th>工具返回</th></tr>'+events+'</table>')
    sections['calls']+=card('提取运行与定位',code(s['extraction_run'] or '尚未运行提取')+('<p class="bad">'+e(s['error'])+'</p>' if s['error'] else '')+'<p class="small">请求、公开返回、工具结果及采用版本由程序保存；结构与来源检查通过后，业务含义仍由 FDE 核查。</p>')
    for call in s['calls']:
        if call['request'] and call['response']:
            response=ws.verify(call['response'])
            sections['calls']+='<details class="card"><summary>第 '+str(call['step'])+' 次公开模型返回</summary>'+code(json.dumps(response,ensure_ascii=False,indent=2))+'</details>'
    sections['review']=''
    if s['extraction_run']:
        try:
            f,fp=facts(ws,s);ev=evidence_view(ws,fp)
            options=''.join('<option value="'+e(v['claim']['id'])+'">'+e(v['claim']['id']+' · '+v['claim']['statement'][:38])+'</option>' for v in ev)
            sections['review']+='<label>选择候选：<select id="claim-choice">'+options+'</select></label>'
            for i,v in enumerate(ev):
                c=v['claim'];quotes=''.join('<p class="meta">'+e(m['meeting_id']+' / '+m['message']['id']+' / '+m['role_id'])+'</p><div class="quote">'+e(m['message']['content'])+'</div>' for m in v['source_messages'])
                feedback=''.join(doc(h['feedback']) for h in s['human_reviews'] if c['id'] in h['claim_ids']) or '<p class="notice">尚待 FDE 核查与反馈。</p>'
                sections['review']+='<div class="evidence" data-claim="'+e(c['id'])+'" style="display:'+('block' if i==0 else 'none')+'"><div class="grid">'+card('材料原文',quotes)+card('AI 候选 '+c['id'],'<p class="claim">'+e(c['statement'])+'</p>'+doc('限定：'+'；'.join(c['qualifiers']))+'<p class="meta">提取状态：'+e(c['evidence_status'])+'；不等于业务事实已核实。</p>')+'</div>'+card('FDE 的核查反馈',feedback)+'</div>'
            sections['review']+=card('反查本轮覆盖','<p>从本轮目标和原文检查：借阅关系、保留期的不同说法、自动提醒的未知，有没有被遗漏？</p>' if s['scope_id']=='fictional-library' else '<p>从本轮目标和材料反查，检查未出现在候选中的内容。</p>')
        except Exception:
            sections['review']=card('提取尚未成功','<p>先在调用记录中查看失败位置，保留已有证据，再组织新一轮。</p>')
    else: sections['review']=card('尚无候选','<p>等待实际提取结果。</p>')
    proposal=s['proposal']
    after=proposal['business_model'] if proposal else '尚未形成修改草稿。'
    sections['model']='<p><span class="tag status">'+e('已由 FDE 确认写入' if s['status']=='completed' else 'AI 修改草稿，尚未写入')+'</span></p><div class="grid">'+card('本轮开始前',doc(before))+card('本轮修改'+('结果' if s['status']=='completed' else '建议'),doc(after))+'</div>'
    if proposal:
        sections['model']+=card('修改理由',doc(proposal['summary']))
        sections['model']+='<details class="card"><summary>查看逐行修改</summary>'+code(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='修改前',tofile='修改建议')))+'</details>'
    sections['handoff']=card('本轮状态','<p class="claim">'+e(status)+'</p>')
    if proposal:
        sections['handoff']+='<div class="grid">'+card('核查记录增量',doc(proposal['notes_update']))+card('下一轮工作起点','<ul>'+''.join('<li>'+e(q)+'</li>' for q in proposal['next_questions'])+'</ul>')+'</div>'
        sections['handoff']+=card('两份文档与下一条视频',code(task['business_model']+'\n'+task['notes'])+'<p>当前业务模型交给 V06 验证 Agent 是否实际采用；新材料与待核实问题接续下一轮提取。</p>')
    sections['handoff']+=card('学员接下来做什么','<p>换成自己的访谈材料和调查问题，调整目标与必要任务要求，实际运行；逐项核查并解释取舍，再确认模型修改。</p><p>课程工具负责通用读取、调用、检查和留存；业务判断由学员完成。</p>')
    ranges=[('请求怎样组成','platform/fde_product/extraction_workflow.py','def start(', 'def load_session('),('原文与人工核查','platform/fde_product/extraction_workflow.py','def tool(', 'def advance('),('真实调用与留存','platform/fde_product/extraction_workflow.py','def advance(', 'def review('),('确认后写入','platform/fde_product/extraction_workflow.py','def apply(', 'def public_status(')]
    sections['code']=''
    for title,p,start,end in ranges:
        ref=next(x for x in s['implementation'] if x['path'].endswith('/'+p));raw=text(ws,ref['path'],180000);lines=raw.splitlines();a=next(i for i,l in enumerate(lines) if l.startswith(start));b=next(i for i,l in enumerate(lines) if l.startswith(end))
        body='\n'.join('<span class="line">'+str(i+1)+'</span>'+e(lines[i]) for i in range(a,b))
        sections['code']+=card(title,'<p class="meta">'+e(p)+' · 本次运行的源码快照</p><pre class="code">'+body+'</pre>')
    labels={'task':'本轮任务','skill':'Skill 与工具','calls':'调用记录','review':'逐项核查','model':'模型修改','handoff':'本轮收尾','code':'代码走读'}
    nav=''.join('<a href="#'+k+'" data-tab="'+k+'">'+label+'</a>' for k,label in labels.items())
    body=''.join('<section id="'+k+'">'+v+'</section>' for k,v in sections.items())
    script="""function tab(){let key=location.hash.slice(1)||'task';document.querySelectorAll('section').forEach(x=>x.classList.toggle('active',x.id===key));document.querySelectorAll('nav a').forEach(x=>x.classList.toggle('selected',x.dataset.tab===key));}window.addEventListener('hashchange',tab);tab();document.getElementById('claim-choice')?.addEventListener('change',ev=>{document.querySelectorAll('.evidence').forEach(x=>x.style.display=x.dataset.claim===ev.target.value?'block':'none')});"""
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>W02 材料提取工作流 · 运行报告</title><style>'+STYLE+'</style><header><h1>材料提取与业务模型更新</h1><div class="meta">'+e(task['goal'])+' · '+e(s['scope_id'])+'</div></header><nav>'+nav+'</nav><main>'+body+'<footer>只读运行报告 · 原始材料、AI 输出与人工反馈分别保留 · '+e(s['folder'])+'</footer></main><script>'+script+'</script></html>'
    out=ws.path(s['folder']+'/report.html');out.write_text(page,encoding='utf-8');return out
