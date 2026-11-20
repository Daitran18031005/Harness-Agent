# Bước 2 (offline, không LLM): bộ phân loại nhóm tool vòng 1 bằng embedding Qwen3-Embedding-0.6B (+ LR), chia theo kịch bản (crc32 chẵn = học, lẻ = kiểm).
import json,collections,sys,zlib,time
sys.path.insert(0,'.')
import numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from src.memory.vector_rag import QwenEmbedBackend
READ={'pricing.get_quote','pricing.quote_order','inventory.check','catalog.search','product.shortlist','order.status','crm.get_customer'}
def label(r):
    s={t['name'] for t in r['tool_calls'] if t.get('by')=='llm'}
    if r['latency_detail']['rounds_before_first_token']==0 and not s: return 'none'
    if not s: return 'blocked'
    if s<={'search_policy'}: return 'policy'
    if 'order.update' in s or 'order.create' in s: return 'order'
    if 'handoff.transfer' in s: return 'handoff'
    if s<=READ|{'search_policy'}: return 'lookup'
    return 'other'
def load(paths,part):
    X,y,t=[],[],[]
    for p in paths:
        prev={}
        for l in open(p,encoding='utf-8'):
            r=json.loads(l); key=(r['scenario_id'],r['call']); pa=prev.get(key,''); prev[key]=r.get('agent_text') or ''
            if not r.get('latency_detail') or (r.get('latency') or {}).get('ttft_ms') is None or zlib.crc32(r['scenario_id'].encode())%2!=part: continue
            X.append('Nhân viên vừa nói: '+pa[-300:]+'\nKhách nói: '+(r.get('customer_text') or '')); y.append(label(r)); t.append(r['latency']['ttft_ms'])
    return X,y,t
runs=lambda d,sub:[f'{d}/{sub}/r{i}/full.jsonl' for i in (1,2,3)]
Xa,ya,_=load(runs('runs/m1_final8','cmp_full'),0)
Xb,yb,tb=load(runs('runs/m1_final9','cmp'),1)
print('học',len(Xa),'kiểm',len(Xb))
emb=QwenEmbedBackend(); t0=time.time()
def E(X): return np.vstack([emb._embed(X[i:i+32]).numpy() for i in range(0,len(X),32)])
Ea,Eb=E(Xa),E(Xb); print('embed',round(time.time()-t0,1),'s, mỗi câu ~',round((time.time()-t0)/(len(Xa)+len(Xb))*1000,1),'ms (theo lô 32)')
m=LogisticRegression(max_iter=5000,C=2,class_weight='balanced').fit(Ea,ya)
P=m.predict_proba(Eb); cl=list(m.classes_); pred=[cl[p.argmax()] for p in P]
print(classification_report(yb,pred,digits=2,zero_division=0))
for c in ('policy','lookup','order','handoff'):
    tot=sum(y==c for y in yb); tots=sum(y==c and t>3000 for y,t in zip(yb,tb))
    for th in (0.6,0.8,0.9):
        sel=[i for i,p in enumerate(P) if p[cl.index(c)]>=th]; ok=sum(yb[i]==c for i in sel); slow=sum(yb[i]==c and tb[i]>3000 for i in sel)
        print(f'{c} p>={th}: chọn {len(sel)}, precision {ok/max(1,len(sel)):.2f}, phủ {ok}/{tot}, lượt chậm {slow}/{tots}')
