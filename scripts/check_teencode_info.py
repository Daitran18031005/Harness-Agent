"""Kiểm `customer_turns_asr` có giữ đủ thông tin của `customer_turns` không, theo từng lượt.

    python scripts/check_teencode_info.py                       # quét BTC-Data-Vong1-TEAMS/test_set/team_eval
    python scripts/check_teencode_info.py --root <thư mục> -v   # -v: in cả câu gốc và câu _asr của lượt bị mất

Thoát mã 1 nếu có lượt mất thông tin. Loại thông tin được kiểm: SĐT, giá/tiền, số lượng, size, màu, địa chỉ (số nhà + từ sau "đường/phố/…"),
tên người nhận. Kịch bản ASR hotline đọc số thành chữ ("năm triệu rưỡi") được chấp nhận với số nhỏ (1–10).

GIỚI HẠN: chỉ bắt thông tin có DẤU HIỆU RÕ — con số đứng riêng, chữ sau "màu", "tên"/"giao cho"/"người nhận", "size"/"cỡ" + số.
KHÔNG bắt: tên không có chữ "tên" ("cho anh Duy", "alo Sơn"), màu không có chữ "màu" ("đen 42"), size chữ sau "cỡ" ("cỡ L"),
địa chỉ toàn chữ không có số nhà. "0 lượt mất" chỉ đúng trong phạm vi đó; lượt mới vẫn nên đọc tay."""
import argparse, glob, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOT = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "test_set", "team_eval")
COLORS = ["den", "trang", "xam", "be", "navy", "do", "hong", "xanh", "vang", "nau", "tim", "kem"]
NUM_WORDS = {"1": "mot", "2": "hai", "3": "ba", "4": "bon", "5": "nam", "6": "sau", "7": "bay", "8": "tam", "9": "chin", "10": "muoi"}


def fold(t):
    t = unicodedata.normalize("NFD", (t or "").lower().replace("đ", "d"))
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def _digits(t):
    return re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", t)


def items(orig):
    """[(loại, giá trị)] thông tin có dấu hiệu rõ trong câu gốc."""
    o, f = _digits(orig), fold(orig)
    out = [("SĐT", m) for m in re.findall(r"\b0\d{9}\b", o)]
    out += [("giá/tiền", m) for m in re.findall(r"(?<![\w.,])(\d{5,9})(?!\d)", o) if not re.fullmatch(r"0\d{9}", m)]
    out += [("giá/tiền", m) for m in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*(?:triệu|tr|k|nghìn|ngàn)\b", o, re.I)]
    out += [("số lượng", m) for m in re.findall(r"\b(\d{1,2})\s+(?:chiếc|cái|bộ|món|máy|đôi|hộp|gói|túi|bình|cặp|thùng)\b", o, re.I)]
    out += [("size", m.lower()) for m in re.findall(r"\b(?:size|cỡ|sz)\s*(\d{2}|xxl|xl)\b", o, re.I)]
    out += [("màu", c) for c in COLORS if re.search(rf"\bmau {c}\b", f)]
    out += [("địa chỉ", f"{n} {fold(w)}") for n, w in re.findall(r"\bsố\s+(\d+[a-z]?(?:/\d+)?)\s+(?:đường|phố|khu|ngõ|hẻm|kiệt|tổ|ấp|thôn)\s+(\S+)", orig, re.I)]
    out += [("tên người nhận", fold(m)) for m in re.findall(r"\b(?:tên|người nhận(?: là)?|giao cho(?: anh| chị| em)?)\s+([A-ZĐÂĂÊÔƠƯ][\wÀ-ỹ]*)", orig)]
    return list(dict.fromkeys(out))


def present(kind, val, asr):
    a, ad = fold(asr), _digits(asr)
    if kind in ("SĐT", "giá/tiền", "số lượng"):
        if val in NUM_WORDS and re.search(rf"(?<!\w){NUM_WORDS[val]}(?!\w)", a):           # số đọc bằng chữ (kịch bản ASR hotline, cố ý)
            return True
        if re.search(rf"(?<!\d){re.escape(val)}(?!\d)", ad) or re.search(rf"(?<!\d){re.escape(val.replace(',', '.'))}(?!\d)", ad):
            return True
        if kind == "giá/tiền" and val.isdigit() and int(val) >= 1000:
            k, m = str(int(val) // 1000), f"{int(val) / 1e6:g}"
            return bool(re.search(rf"(?<!\d){k}\s*(k|nghin|ngan)", a) or re.search(rf"(?<!\d){re.escape(m)}\s*(tr|trieu|cu)", a))
        return False
    if kind == "địa chỉ":
        num, word = val.split(" ", 1)
        return bool(re.search(rf"(?<!\d){re.escape(num)}(?!\d)", a)) and word in a
    return bool(re.search(rf"(?<!\w){re.escape(val)}(?!\w)", a))


def scan(root=DEFAULT_ROOT):
    """[(scenario_id, call, lượt, input_mode, [(loại, giá trị) bị mất], câu gốc, câu _asr)] — lượt 0 = số lượt hai bản khác nhau."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "*.json"))):
        if os.path.basename(p).startswith("_"):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for call, spec in sorted((d.get("calls") or {}).items()):
            asr, orig = spec.get("customer_turns_asr"), spec.get("customer_turns") or []
            if not asr:
                continue
            if len(orig) != len(asr):
                out.append((d.get("scenario_id"), call, 0, spec.get("input_mode"), [("số lượt", f"{len(orig)} vs {len(asr)}")], "", ""))
            for i, (o, a) in enumerate(zip(orig, asr), 1):
                lost = [(k, v) for k, v in items(o) if not present(k, v, a)]
                if lost:
                    out.append((d.get("scenario_id"), call, i, spec.get("input_mode"), lost, o, a))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    rows = scan(a.root)
    print(f"{len(rows)} lượt mất thông tin")
    for sid, call, i, mode, lost, o, s in rows:
        print(f"{sid} | {call} | lượt {i} | {mode} | " + "; ".join(f"{k}={v}" for k, v in lost))
        if a.v:
            print(f"  gốc: {o}\n  asr: {s}")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
