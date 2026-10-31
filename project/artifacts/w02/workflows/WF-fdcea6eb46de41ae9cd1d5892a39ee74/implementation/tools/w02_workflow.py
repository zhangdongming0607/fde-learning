"""W02 AI extraction workflow with explicit human review and confirmation."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"platform"))
from fde_product.extraction_workflow import *


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,default=Path.cwd())
    subs=p.add_subparsers(dest="action",required=True)
    subs.add_parser("init")
    for action in ("inspect","start"):
        c=subs.add_parser(action);c.add_argument("--task",default=DEFAULT_TASK)
        if action=="start": c.add_argument("--previous")
    for action in ("resume","status","apply","report","review","revise"):
        c=subs.add_parser(action);c.add_argument("session",nargs="?",default="latest")
        if action in ("review","revise"):
            g=c.add_mutually_exclusive_group(required=True);g.add_argument("--feedback");g.add_argument("--feedback-file",type=Path)
    a=p.parse_args();ws=Workspace(a.workspace)
    try:
        if hasattr(a,"session"): a.session=resolve_session(ws,a.session)
        if getattr(a,"previous",None): a.previous=resolve_previous(ws,a.previous)
        if a.action=="status": result=public_status(load_session(ws,a.session),a.session)
        elif a.action=="report":
            from fde_product.workflow_report import render_report
            result={"report":str(render_report(ws,a.session))}
        else:
            with lock(ws):
                if a.action=="init": result=initialize(ws)
                elif a.action=="inspect":
                    task,cfg,ts=inspect_task(ws,a.task)
                    result={"goal":task["goal"],"materials":len(ts),"batches":len(batches(ts,cfg)),"skill":task["skill"],"profile":cfg["profile"]}
                elif a.action in ("review","revise"):
                    feedback=a.feedback if a.feedback is not None else a.feedback_file.read_text()
                    result=public_status((review if a.action=="review" else revise)(ws,a.session,feedback),a.session)
                elif a.action=="apply": result=public_status(apply(ws,a.session),a.session)
                else:
                    if a.action=="start":
                        _,cfg,_=inspect_task(ws,a.task)
                        # Validate model settings before creating a runnable session.
                        model=WorkflowModel(profile=cfg["profile"],timeout=90)
                        path=start(ws,a.task,a.previous)
                    else:
                        path=a.session;s=load_session(ws,path);model=WorkflowModel(profile=s["profile"],timeout=90)
                    extractor=ExtractionModel(profile=model.profile,timeout=90)
                    try:
                        result=public_status(advance(ws,path,model,extractor),path)
                    except KeyboardInterrupt:
                        # advance() has already saved the session; show where it stopped instead of a traceback.
                        print(json.dumps(public_status(load_session(ws,path),path),ensure_ascii=False,indent=2));return 130
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get("status")=="failed" else 0
    except (CheckError,ModelError,OSError,UnicodeError) as e:
        print(json.dumps({"status":"failed","code":getattr(e,"code","FILE_OPERATION_FAILED"),"location":getattr(e,"location","")},ensure_ascii=False));return 2

if __name__=="__main__": raise SystemExit(main())
