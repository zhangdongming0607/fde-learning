"""W2 learner extraction: configure, extract, inspect, review and check."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"platform"))
from fde_product.interview_extraction import (Workspace,CheckError,ExtractionModel,load_config,batches,extract,
    validate_run,validate_facts,start_review,evidence_view,require,VERSION)
from fde_product.models import ModelError


def initialize(ws):
    files=[("templates/w02_extraction/extraction.json","customer/w02/extraction.json"),
           ("templates/w02_extraction/extraction_prompt.txt","customer/w02/extraction_prompt.txt")]
    for _,target in files: require(not ws.path(target).exists(),"OUTPUT_EXISTS",target)
    for source,target in files: ws.write(target,(ROOT/source).read_bytes(),raw=True)
    return {"status":"initialized","next":"填写 sources、scope_id、提取问题并调整提示词，然后 inspect。"}


def convert(ws,source,target):
    public=ws.load(source)
    if "contract_version" in public:
        ws.schema("transcript",public)
        ws.write(target,ws.raw(source),raw=True)
        return {"status":"copied","path":target,"week":public["week"]}
    required={"meeting_id","week","role_id","scenario_version","state","purpose","mode","messages"}
    require(isinstance(public,dict) and required<=public.keys() and public.keys()<=required|{"charged","project_decisions","summary_state"},"PUBLIC_EXPORT_REQUIRED")
    require(type(public["week"]) is int and public["week"] in (1,2),"PUBLIC_EXPORT_REQUIRED")
    require(isinstance(public["mode"],str) and public["mode"] in ("live","scripted","fixture","replay"),"PUBLIC_EXPORT_REQUIRED")
    require(isinstance(public["messages"],list) and all(isinstance(m,dict) and set(m)=={"id","speaker","content"}
        and all(isinstance(v,str) for v in m.values()) and m["speaker"] in ("assistant","user","system") for m in public["messages"]),"PUBLIC_EXPORT_REQUIRED")
    result={"contract_version":VERSION,"scope_id":"qinghe","origin":"fixture" if public["mode"]=="scripted" else public["mode"],
            **{k:public[k] for k in ("meeting_id","week","role_id","scenario_version","purpose")},
            "state":"ended" if public["state"]=="compensated" else public["state"],
            "messages":[m for m in public["messages"] if m["speaker"]!="system"]}
    ws.schema("transcript",result);ws.write(target,result)
    return {"status":"converted","path":target,"week":result["week"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("init")
    for action in ("inspect","extract"):
        cmd=sub.add_parser(action);cmd.add_argument("--config",default="customer/w02/extraction.json")
    for action in ("check-run","check-facts","evidence"):
        cmd=sub.add_parser(action);cmd.add_argument("path")
    cmd=sub.add_parser("review-start");cmd.add_argument("path");cmd.add_argument("--output",required=True)
    cmd=sub.add_parser("convert");cmd.add_argument("source");cmd.add_argument("--output",required=True)
    args=parser.parse_args();ws=Workspace(args.workspace)
    try:
        if args.action=="init": result=initialize(ws)
        elif args.action=="convert": result=convert(ws,args.source,args.output)
        elif args.action in ("inspect","extract"):
            config,transcripts=load_config(ws,args.config)
            parts=batches(transcripts,config)
            if args.action=="inspect": result={"status":"input_checked","meetings":len(transcripts),"batches":len(parts),"planned_model_calls":len(parts)+1,"scope_id":config["scope_id"],"profile":config["profile"]}
            else:
                model=ExtractionModel(profile=config["profile"],timeout=90)
                path=extract(ws,args.config,model);run=ws.load(path)
                result={"status":run["status"],"run":path,"error":run["error"]}
        elif args.action=="review-start": result={"status":"pending_review","path":start_review(ws,args.path,args.output)}
        elif args.action=="evidence": result=evidence_view(ws,args.path)
        elif args.action=="check-run":
            run=validate_run(ws,args.path)
            result={"status":"structure_checked","run_status":run["status"],"mode":run["mode"],"semantic_review":"required"}
        else:
            facts=ws.load(args.path);claims=validate_facts(ws,facts,reviewed=True,origin=True)
            result={"status":"structure_checked","claims":len(claims),"semantic_review":"required"}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if isinstance(result,dict) and result.get("status")=="failed" else 0
    except (CheckError,ModelError,OSError,UnicodeError) as exc:
        print(json.dumps({"status":"failed","code":getattr(exc,"code","FILE_OPERATION_FAILED"),"location":getattr(exc,"location","")},ensure_ascii=False))
        return 2
    except (KeyError,TypeError,ValueError,StopIteration):
        print(json.dumps({"status":"failed","code":"RUN_RECORD_INVALID"}))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
