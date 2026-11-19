import json,sys,collections
pf={tuple(k):v for k,v in json.load(open(sys.argv[1],encoding='utf-8'))}
allr=[]
for i in (1,2,3): allr+=[json.loads(l) for l in open(f'runs/m1_final9/cmp/r{i}/full.jsonl',encoding='utf-8')]
tt=[r for r in allr if (r.get('latency') or {}).get('ttft_ms') is not None]
n=len(tt); K=min(n-1,int(round(0.95*n+0.5))-1); p95=lambda v:sorted(v)[K]
def llm_pol(r): return [t for t in r['tool_calls'] if t.get('by')=='llm' and t['name']=='search_policy']
def other_llm(r): return [t for t in r['tool_calls'] if t.get('by')=='llm' and t['name']!='search_policy']
def got(r): return [c['chunk_id'] for t in llm_pol(r) for c in (t.get('result') or {}).get('chunks',[])]
print('lượt LLM gọi search_policy:',sum(1 for r in tt if llm_pol(r)),'| chỉ search_policy, 1 vòng:',sum(1 for r in tt if llm_pol(r) and not other_llm(r) and (r.get('latency_detail') or {}).get('rounds_before_first_token')==1))
W=int(sys.argv[2]) if len(sys.argv)>2 else 0
for th in (0.8,0.9,0.95):
    st=collections.Counter(); v=[]
    for r in tt:
        pre=pf.get((r['scenario_id'],r['call'],r.get('customer_text') or ''),[])
        top=pre[0][1] if pre else 0; ids=[c for c,_ in pre]
        x=r["latency"]["ttft_ms"]+(W if r.get("latency_detail") else 0)
        if top>=th:
            if not llm_pol(r): st['chặn, LLM vốn không gọi (vô hại)']+=1
            else:
                g=got(r); top1_ok=bool(g) and g[0] in ids; all_ok=bool(g) and set(g)<=set(ids)
                st['LLM gọi, chunk đầu LLM nhận có trong tra trước' if top1_ok else 'LLM gọi, tra trước KHÁC (rủi ro)']+=1
                if all_ok: st['  trong đó đủ cả 3 chunk']+=1
                ld=r.get('latency_detail') or {}
                if top1_ok and not other_llm(r) and ld.get('rounds_before_first_token')==1:
                    x=x-ld['round_ms'][0]-ld['tool_ms']; st['bỏ được vòng 1']+=1
                    if r['latency']['ttft_ms']>3000: st['  trong đó lượt > 3 s']+=1
        v.append(x)
    print(f'\nngưỡng {th}: p95 {p95(v)} ms (gốc {p95([r["latency"]["ttft_ms"] for r in tt])}), lượt > 3 s {sum(a>3000 for a in v)} (gốc {sum(r["latency"]["ttft_ms"]>3000 for r in tt)})')
    for k,c in st.items(): print('  ',k,c)
