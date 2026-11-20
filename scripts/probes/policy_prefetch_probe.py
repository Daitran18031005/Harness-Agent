# Bước 1 (offline, không LLM): reranker tra trước theo lời khách trên m1_final9; lượt nào chặn được search_policy an toàn.
import json,glob,sys,os,time
from datetime import datetime,timedelta
sys.path.insert(0,'.')
os.environ.setdefault('VECTOR_BACKEND','qwen_rerank'); os.environ.setdefault('HF_HUB_OFFLINE','1')
from src.memory.service import MemoryService
dates={}
for f in glob.glob('runs/m1_final9/scen_all/*.json'):
    d=json.load(open(f,encoding='utf-8')); prev='2026-10-15'
    for name,c in d['calls'].items():
        cd=c.get('call_date') or (datetime.strptime(prev,'%Y-%m-%d')+timedelta(days=c.get('days_later',0))).strftime('%Y-%m-%d')
        dates[(d['scenario_id'],name)]=cd; prev=cd
mem=MemoryService(enable_persistence=False)
out={}; t0=time.time()
for i in (1,2,3):
    for l in open(f'runs/m1_final9/cmp/r{i}/full.jsonl',encoding='utf-8'):
        r=json.loads(l); k=(r['scenario_id'],r['call'],r.get('customer_text') or '')
        if k in out or not k[2].strip(): continue
        ch=mem.prefetch_policy(k[2], dates.get((r['scenario_id'],r['call']),'2026-10-15'))
        out[k]=[(c['chunk_id'],c['score']) for c in ch]
json.dump([[list(k),v] for k,v in out.items()],open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False)
print(len(out),'câu',round(time.time()-t0,1),'s')
