#!/usr/bin/env python3
"""W2 natural-language model: initialize documents, inspect, ask and compare."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'platform'))
from fde_product.natural_knowledge import (CONFIG,Workspace,SnapshotReader,ContextModel,CheckError,
    require,initialize,load_task,messages_for,check_run)
from fde_product.models import ModelError


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,default=Path.cwd())
    sub=p.add_subparsers(dest='action',required=True)
    c=sub.add_parser('init');c.add_argument('--from-extraction');c.add_argument('--replace',action='store_true',help='已有配置时改用指定提取，重写 knowledge.json；不改两份文档。')
    for action in ('inspect','run','compare'):
        c=sub.add_parser(action);c.add_argument('--config',default=CONFIG)
        c.add_argument('--question',required=action!='inspect');c.add_argument('--expected',default='')
        if action=='run':c.add_argument('--without-knowledge',action='store_true')
    c=sub.add_parser('check-run');c.add_argument('path')
    args=p.parse_args();ws=Workspace(args.workspace)
    try:
        if args.action=='init':result=initialize(ws,args.from_extraction,replace=args.replace)
        elif args.action=='check-run':
            run,*_=check_run(ws,args.path);result={'status':'structure_checked','run_status':run['status'],
                'mode':run['mode'],'semantic_review':'required'}
        else:
            reader=SnapshotReader(args.workspace);config,document,prompt,_,_=load_task(reader,args.config)
            question=args.question or '业务定义检查'
            require(len(json.dumps(messages_for(document,prompt,question,True),ensure_ascii=False))<=config['max_context_chars'],'CONTEXT_LIMIT')
            if args.action=='inspect':result={'status':'input_checked','scope_id':config['scope_id'],
                'business_model':config['business_model'],'extraction_run':config['extraction_run'],
                'planned_model_calls':0,'compare_model_calls':2,'tools':[]}
            else:
                from fde_product.agent import Agent
                agent=Agent(ws.path('.runtime/w02-knowledge'),ContextModel(profile=config['profile'],timeout=90))
                try:
                    pair_id='PAIR-'+uuid4().hex if args.action=='compare' else None
                    includes=[False,True] if pair_id else [not args.without_knowledge]
                    runs=[]
                    for included in includes:
                        r=agent.answer_business_model(args.workspace,args.config,question,
                            include_knowledge=included,expected=args.expected,pair_id=pair_id,reader=reader)
                        r['include_knowledge']=included;runs.append(r)
                        if r['status']=='failed':break
                    result={'status':'succeeded' if len(runs)==len(includes) and all(r['status']=='succeeded' for r in runs) else 'failed',
                            'pair_id':pair_id,'runs':runs,'next':'查看 request.json 和 answer.json，在访谈与核查记录中写判读。'}
                finally:agent.close()
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result.get('status')=='failed' else 0
    except (CheckError,ModelError,OSError,UnicodeError) as exc:
        print(json.dumps({'status':'failed','code':getattr(exc,'code','FILE_OPERATION_FAILED'),'location':getattr(exc,'location','')},ensure_ascii=False));return 2
    except (KeyError,TypeError,ValueError,StopIteration):
        print(json.dumps({'status':'failed','code':'RUN_RECORD_INVALID'}));return 2


if __name__=='__main__':raise SystemExit(main())
