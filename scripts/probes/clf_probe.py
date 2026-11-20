# Thử bộ phân loại nhỏ (TF-IDF + LR) đoán nhóm tool LLM sẽ gọi ở vòng 1, học m1_final8 → kiểm m1_final9. Không gọi LLM.
import json,collections,sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
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
import zlib
keep=None
def load(paths):
    X,y,t=[],[],[]
    for p in paths:
        prev={}
        for l in open(p,encoding='utf-8'):
            r=json.loads(l); key=(r['scenario_id'],r['call'])
            pa=prev.get(key,''); prev[key]=r.get('agent_text') or ''
            if not r.get('latency_detail') or (r.get('latency') or {}).get('ttft_ms') is None: continue
            if not keep(r["scenario_id"]): continue
            X.append('NV: '+pa[-300:]+' || KH: '+(r.get('customer_text') or '')); y.append(label(r)); t.append(r['latency']['ttft_ms'])
    return X,y,t
keep=lambda s: zlib.crc32(s.encode())%2==0
Xa,ya,_=load([f'm1_final8/cmp_full/r{i}/full.jsonl' for i in (1,2,3)])
keep=lambda s: zlib.crc32(s.encode())%2==1
Xb,yb,tb=load([f'm1_final9/cmp/r{i}/full.jsonl' for i in (1,2,3)])
print('train',len(Xa),collections.Counter(ya)); print('test',len(Xb),collections.Counter(yb))
v=TfidfVectorizer(analyzer='char_wb',ngram_range=(2,5),min_df=2,sublinear_tf=True)
m=LogisticRegression(max_iter=3000,C=4,class_weight='balanced').fit(v.fit_transform(Xa),ya)
P=m.predict_proba(v.transform(Xb)); cl=list(m.classes_)
pred=[cl[p.argmax()] for p in P]
print(classification_report(yb,pred,digits=2,zero_division=0))
for c in ('policy','lookup'):
    for th in (0.6,0.8,0.9):
        sel=[i for i,p in enumerate(P) if p[cl.index(c)]>=th]
        ok=sum(yb[i]==c for i in sel); slow=sum(yb[i]==c and tb[i]>3000 for i in sel)
        tot=sum(y==c for y in yb); tots=sum(y==c and t>3000 for y,t in zip(yb,tb))
        print(f'{c} p>={th}: chọn {len(sel)}, đúng {ok} (precision {ok/max(1,len(sel)):.2f}), phủ {ok}/{tot} lượt, {slow}/{tots} lượt chậm')
