"""Giai đoạn C bước 1: đếm trần TTFT nếu bộ phân loại cục bộ (Laya) chọn đúng loại tra cứu.

Chỉ đọc log có sẵn (không gọi LLM). In bảng markdown ra stdout.
Chạy: python scripts/dem_tran_laya.py > /tmp/out.md
"""
import glob, json, re, random, unicodedata, collections
import numpy as np

SETS = {
    "m1_final7": "runs/m1_final7/r*/s[123]/full.jsonl",
    "router_1116": "runs/ab_rerank_1116/router-*/full.jsonl",
    "noshort_1116": "runs/ab_noshort_1116/*/full.jsonl",
}
LOOKUP = {"catalog.search": "tra_san_pham", "inventory.check": "tra_san_pham", "pricing.get_quote": "tra_san_pham",
          "search_policy": "chinh_sach", "order.status": "don_hang"}
WRITE = {"order.create", "order.update", "pricing.quote_order", "handoff.transfer", "schedule.callback"}
LIMIT = 3000


def fold(s):
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


PRODUCTS = json.load(open("BTC-Data-Vong1-TEAMS/catalog/products.json", encoding="utf-8"))["products"]
PARENTS = {p["sku"]: p for p in PRODUCTS}
VARIANT = {v["variant_sku"]: (p["sku"], v) for p in PRODUCTS for v in p.get("variants", [])}
# "Máy lọc không khí AirPure X" -> alias "airpure x"; chỉ nói brand -> mọi sản phẩm của brand
ALIAS = {}
for p in PRODUCTS:
    name, brand = p["name"], p.get("brand") or ""
    i = name.find(brand) if brand else -1
    ALIAS[p["sku"]] = fold(name[i:] if i >= 0 else name)


def parent_of(sku):
    if sku in PARENTS:
        return sku
    if sku in VARIANT:
        return VARIANT[sku][0]
    return next((p for p in PARENTS if sku.startswith(p + "-")), sku)


def named_in(text):
    t = fold(text)
    exact = {s for s, a in ALIAS.items() if re.search(r"\b" + re.escape(a) + r"\b", t)}
    if exact:
        return exact
    return {p["sku"] for p in PRODUCTS if p.get("brand") and re.search(r"\b" + re.escape(fold(p["brand"])) + r"\b", t)}


def skus_in(obj):
    return set(re.findall(r"SKU-[A-Z0-9]+(?:-[A-Z0-9]+)*", json.dumps(obj, ensure_ascii=False)))


def load():
    rows = []
    for tag, pat in SETS.items():
        for f in sorted(glob.glob(pat)):
            for n, line in enumerate(open(f, encoding="utf-8")):
                y = json.loads(line)
                y["_set"], y["_file"], y["_n"] = tag, f, n
                rows.append(y)
    return rows


def label(y):
    d = y.get("latency_detail") or {}
    calls = [t for t in y["tool_calls"] if not t.get("speculative") and t.get("by") != "code"]
    names = {t["name"] for t in calls}
    if names & WRITE:
        return "ghi", calls
    kinds = {LOOKUP[n] for n in names if n in LOOKUP}
    if d.get("rounds_before_first_token", 0) == 0:
        return "khong_tra", calls
    if not calls:
        return ("vong_nhac_vo_ich" if d.get("nudged") else "vong_khong_tool"), calls
    if len(kinds) == 1 and names <= set(LOOKUP):
        return kinds.pop(), calls
    if len(kinds) > 1:
        return "nhieu_loai", calls
    return "khac", calls  # product.shortlist / crm.get_customer


def derivable(lab, calls, ctx_parents, cust_hist, this_text, prev_text):
    """Tham số có suy ra được từ thứ code có sẵn trước khi gọi LLM? (không hiểu ý khách)."""
    if lab == "chinh_sach":
        return True, "truy vấn = lời khách"
    if lab == "don_hang":
        for t in calls:
            oid = t["args"].get("order_id")
            if oid and oid not in cust_hist + prev_text:
                return False, f"mã đơn {oid} không có trong ngữ cảnh"
        return True, "tra theo SĐT phiên / mã đơn có trong lời khách"
    if lab != "tra_san_pham":
        return False, lab
    cand = set(ctx_parents) | named_in(this_text) | named_in(prev_text)
    called = {t["args"].get("sku") for t in calls if t["args"].get("sku")}
    if not called:
        return False, "gọi không có sku: " + json.dumps([t["args"] for t in calls], ensure_ascii=False)[:80]
    miss = {parent_of(s) for s in called} - cand
    if miss:
        return False, f"SKU {sorted(miss)} ngoài ngữ cảnh {sorted(cand)[:4]}"
    if len(cand) > 3:
        return False, f"ngữ cảnh quá rộng ({len(cand)} sản phẩm)"
    h = fold(cust_hist)
    for s in called:
        if s in VARIANT:
            v = VARIANT[s][1]
            if str(v.get("size", "")) and not re.search(r"\b%s\b" % re.escape(fold(str(v.get("size", "")))), h):
                return False, f"size {v.get('size')} của {s} khách chưa nêu"
            if v.get("color") and fold(v["color"]) not in h:
                return False, f"màu {v['color']} của {s} khách chưa nêu"
    return True, f"SKU {sorted(called)} ∈ ngữ cảnh {sorted(cand)}"


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


def main():
    rows = load()
    groups = collections.defaultdict(list)
    for y in rows:
        groups[(y["_file"], y.get("run_id"), y["scenario_id"])].append(y)
    out = []
    for g in groups.values():
        g.sort(key=lambda y: y["_n"])
        ctx, hist, prev_agent = set(), "", ""
        for y in g:
            d = y.get("latency_detail") or {}
            lab, calls = label(y)
            spec_parents = {parent_of(t["args"]["sku"]) for t in y["tool_calls"]
                            if (t.get("speculative") or t.get("by") == "code") and t["args"].get("sku")}
            hist += " " + (y.get("customer_text") or "")
            ok, why = derivable(lab, calls, ctx | spec_parents, hist, y.get("customer_text") or "", prev_agent)
            rec = dict(set=y["_set"], sc=y["scenario_id"], lab=lab, ok=ok, why=why,
                       ttft=y["latency"]["ttft_ms"], text=y.get("customer_text") or "", mode=y.get("customer_input_mode"),
                       rounds=d.get("rounds_before_first_token", 0), nudged=bool(d.get("nudged")))
            rm = d.get("round_ms") or []
            pre = sum(rm[:rec["rounds"]])
            rec.update(pre=pre, tool=d.get("tool_ms", 0) or 0, final=d.get("final_round_ttft_ms") or 0)
            rec["prep"] = rec["ttft"] - pre - rec["tool"] - rec["final"]
            rec["round_list"] = rm[:rec["rounds"]]
            out.append(rec)
            # cập nhật ngữ cảnh code biết được sau lượt này
            ctx |= {parent_of(s) for s in skus_in([t["args"] for t in y["tool_calls"]])} & set(PARENTS)
            ctx |= named_in(y.get("agent_text") or "")
            prev_agent = y.get("agent_text") or ""
    report(out)


def ceiling_ttft(r):
    # 0 vòng: chuẩn bị + tool tra trước (thời gian tool thật) + token đầu vòng cuối
    return r["prep"] + r["tool"] + r["final"]


def report(out):
    P = print
    P("## 1. Phân rã TTFT (lượt có ≥1 vòng gọi tool trước token đầu)\n")
    for tag in list(SETS) + ["TẤT CẢ"]:
        s = [r for r in out if r["set"] == tag or tag == "TẤT CẢ"]
        w = [r for r in s if r["rounds"] > 0]
        z = [r for r in s if r["rounds"] == 0]
        P(f"**{tag}**: {len(s)} lượt, {len(w)} có vòng tool ({len(w)/len(s):.0%}), {len(z)} không vòng\n")
        P("| phần | p50 ms | p95 ms |\n|---|---|---|")
        for k, vals in [("TTFT (lượt có vòng)", [r["ttft"] for r in w]), ("chuẩn bị", [r["prep"] for r in w]),
                        ("vòng 1", [r["round_list"][0] for r in w]),
                        ("vòng 2+ (lượt có)", [x for r in w for x in r["round_list"][1:]]),
                        ("tổng các vòng", [r["pre"] for r in w]), ("tool", [r["tool"] for r in w]),
                        ("token đầu vòng cuối", [r["final"] for r in w]),
                        ("TTFT lượt 0 vòng", [r["ttft"] for r in z]), ("chuẩn bị lượt 0 vòng", [r["prep"] for r in z]),
                        ("token đầu lượt 0 vòng", [r["final"] for r in z]), ("TTFT tất cả", [r["ttft"] for r in s])]:
            P(f"| {k} | {pct(vals,50):.0f} | {pct(vals,95):.0f} |")
        P()

    P("## 2. Nhãn (việc LLM thật sự làm trước khi nói)\n")
    labs = collections.Counter(r["lab"] for r in out)
    P("| nhãn | số lượt | % | TTFT p50 | TTFT p95 | >3 s | suy ra được |\n|---|---|---|---|---|---|---|")
    for l, n in labs.most_common():
        s = [r for r in out if r["lab"] == l]
        t = [r["ttft"] for r in s]
        ok = sum(r["ok"] for r in s) if l in ("tra_san_pham", "don_hang", "chinh_sach") else "–"
        P(f"| {l} | {n} | {n/len(out):.1%} | {pct(t,50):.0f} | {pct(t,95):.0f} | {sum(x>LIMIT for x in t)} | {ok} |")
    P()

    P("## 3. Suy ra được tham số?\n")
    random.seed(0)
    for l in ("tra_san_pham", "don_hang", "chinh_sach"):
        s = [r for r in out if r["lab"] == l]
        y = [r for r in s if r["ok"]]
        n = [r for r in s if not r["ok"]]
        P(f"**{l}**: suy ra được {len(y)}/{len(s)}, không {len(n)}\n")
        P("| loại | ví dụ | kịch bản | lời khách | lý do |\n|---|---|---|---|---|")
        for tag, grp in (("được", y), ("không", n)):
            for i, r in enumerate(random.sample(grp, min(10, len(grp)))):
                txt = r["text"].replace("|", "/")[:90]
                P(f"| {tag} | {i+1} | {r['sc']} | {txt} | {r['why'].replace('|','/')[:110]} |")
        P()
    whys = collections.Counter(r["why"].split(" ")[0] + " " + r["why"].split(" ")[1] for r in out
                               if r["lab"] == "tra_san_pham" and not r["ok"])
    P("Lý do không suy ra (tra_san_pham): " + ", ".join(f"{k}: {v}" for k, v in whys.most_common(6)) + "\n")

    P("## 4. Trần TTFT\n")
    P("Lượt suy ra được → 0 vòng: TTFT mới = chuẩn bị + tool tra trước + token đầu vòng cuối. "
      "Phủ k % = chọn ngẫu nhiên k % lượt suy ra được (trung bình 200 lần). Vòng nhắc vô ích: bỏ hết các vòng trước.\n")
    P("| bộ | kịch bản | TTFT p95 ms | lượt >3 s | % >3 s | đạt ≤5 %? |\n|---|---|---|---|---|---|")
    for tag in list(SETS) + ["TẤT CẢ"]:
        s = [r for r in out if r["set"] == tag or tag == "TẤT CẢ"]
        elig = [i for i, r in enumerate(s) if r["ok"] and r["lab"] in ("tra_san_pham", "don_hang", "chinh_sach")]
        nud = {i for i, r in enumerate(s) if r["lab"] == "vong_nhac_vo_ich"}
        base = [r["ttft"] for r in s]

        def run(cov, drop_nudge, reps):
            p95s, overs = [], []
            for rep in range(reps):
                rng = random.Random(rep)
                pick = set(rng.sample(elig, round(cov * len(elig)))) if cov else set()
                if drop_nudge:
                    pick |= nud
                t = [ceiling_ttft(r) if i in pick else r["ttft"] for i, r in enumerate(s)]
                p95s.append(pct(t, 95)); overs.append(sum(x > LIMIT for x in t))
            return np.mean(p95s), np.mean(overs)

        for name, cov, dn in [("hiện tại", 0, False), ("chỉ bỏ vòng nhắc vô ích", 0, True), ("phủ 100 %", 1, False),
                              ("phủ 80 %", .8, False), ("phủ 60 %", .6, False), ("phủ 100 % + bỏ nhắc", 1, True),
                              ("cận dưới: MỌI lượt 0 vòng", None, False)]:
            if cov is None:
                t = [ceiling_ttft(r) for r in s]
                p, o = pct(t, 95), sum(x > LIMIT for x in t)
            else:
                p, o = run(cov, dn, 1 if cov in (0, 1) else 200)
            P(f"| {tag} | {name} | {p:.0f} | {o:.0f} | {o/len(s):.1%} | {'ĐẠT' if o/len(s) <= .05 else 'không'} |")
    P()
    z = [r for r in out if r["rounds"] == 0]
    est = [ceiling_ttft(r) for r in out if r["ok"] and r["lab"] in ("tra_san_pham", "don_hang", "chinh_sach")]
    P(f"Đối chiếu: TTFT thật lượt 0 vòng p50/p95 = {pct([r['ttft'] for r in z],50):.0f}/{pct([r['ttft'] for r in z],95):.0f} ms, "
      f">3 s {sum(r['ttft']>LIMIT for r in z)/len(z):.1%}; TTFT ước tính lượt được chuyển p50/p95 = {pct(est,50):.0f}/{pct(est,95):.0f} ms, "
      f">3 s {sum(x>LIMIT for x in est)/max(1,len(est)):.1%}.\n")

    P("## 5. Dữ liệu huấn luyện\n")
    scs = sorted({r["sc"] for r in out})
    P(f"{len(out)} lượt, {len(scs)} kịch bản. Chế độ lời khách: " +
      ", ".join(f"{k}: {v} ({v/len(out):.1%})" for k, v in collections.Counter(r["mode"] for r in out).most_common()) + "\n")
    rng = random.Random(42)
    test = set(rng.sample(scs, round(.2 * len(scs))))
    P("| nhãn | train | test |\n|---|---|---|")
    for l, _ in labs.most_common():
        P(f"| {l} | {sum(r['lab']==l and r['sc'] not in test for r in out)} | {sum(r['lab']==l and r['sc'] in test for r in out)} |")
    P(f"\nChia THEO KỊCH BẢN, seed 42, 20 % kịch bản làm test ({len(test)} kịch bản). "
      "Lưu ý: cùng kịch bản lặp 3 lần chạy + các bộ 1116 → mẫu trùng lời khách, dedupe theo (kịch bản, lời khách) trước khi train.")
    uniq = {(r["sc"], r["text"], r["lab"]) for r in out}
    P(f"Sau dedupe (kịch bản, lời khách, nhãn): {len(uniq)} mẫu; " +
      ", ".join(f"{k}: {v}" for k, v in collections.Counter(l for _, _, l in uniq).most_common()))


if __name__ == "__main__":
    main()
