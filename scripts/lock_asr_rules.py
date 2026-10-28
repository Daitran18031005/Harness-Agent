"""
KHÓA luật ITN + trích thực thể ASR + bảng cách đọc SKU (ghi hash/phiên bản vào `config/asr_rules.lock.json`).

Vì sao: các luật này được viết SAU KHI đã xem D01–D04 (tập phát triển). Để số đo trên audio MỚI (tập chưa thấy) có ý nghĩa, luật phải
đứng yên từ lúc đó: `tests/test_asr_rules_lock.py` ĐỎ nếu bất kỳ phần nào đổi mà chưa cập nhật khóa có chủ đích.

    python scripts/lock_asr_rules.py --check                         # so hash hiện tại với khóa (mã thoát 1 nếu lệch)
    python scripts/lock_asr_rules.py --update --version asr-rules-v2 --reason "lý do đổi luật"   # CHỈ khi cố ý đổi luật
"""
import argparse
import hashlib
import inspect
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)
LOCK_PATH = os.path.join(CODE_DIR, "config", "asr_rules.lock.json")
FILES = ["config/product_aliases.json", "src/channels/asr_entities.py", "src/channels/asr_postprocess.py"]
DEV_SET = ["D01", "D02", "D03", "D04"]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(rel: str) -> str:
    with open(os.path.join(CODE_DIR, rel), "rb") as fh:
        return _sha(fh.read().replace(b"\r\n", b"\n"))          # không phụ thuộc kiểu xuống dòng của hệ điều hành


def itn_hash() -> str:
    """Hash phần ITN của normalizer (hàm đổi chữ→số, từ vựng số, ASR_FIXES) — không băm cả file để thay đổi khác của normalizer
    (teencode, PII…) không làm đỏ khóa."""
    from src.channels import normalizer as n
    parts = [inspect.getsource(getattr(n, name)) for name in (
        "_vocab_token", "_parse_section", "_parse_number_run", "itn_phone_digits", "itn_number_words", "itn_digit_units", "_fmt_money")]
    def canon(v):                      # set có thứ tự lặp thay đổi giữa các lần chạy (băm chuỗi ngẫu nhiên hóa) → sắp xếp trước khi băm
        return repr(sorted(v)) if isinstance(v, (set, frozenset)) else repr(v)
    parts += [canon(getattr(n, name)) for name in ("_DIGITS", "_FILLERS", "_MAGS", "_VOCAB", "_ASCII", "_PHONE_DIGIT_WORDS")]
    parts.append(repr(sorted(n.RequestNormalizer.ASR_FIXES.items())))
    return _sha("\n".join(parts).replace("\r\n", "\n").encode("utf-8"))


def current() -> dict:
    return {"files": {rel: file_hash(rel) for rel in FILES}, "normalizer_itn": itn_hash()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--version", default=None)
    ap.add_argument("--reason", default=None)
    args = ap.parse_args(argv)
    now = current()
    if args.update:
        if not args.version or not args.reason:
            print("--update cần --version và --reason (đổi luật phải có lý do ghi lại).")
            return 2
        lock = {"version": args.version, "locked_on": date.today().isoformat(), "reason": args.reason, "dev_set": DEV_SET,
                "note": "Luật viết SAU KHI xem D01–D04. Mọi số entity accuracy trên D01–D04 là 'trong tập phát triển'; "
                        "số trên audio mới chưa từng thấy phải báo RIÊNG.", **now}
        with open(LOCK_PATH, "w", encoding="utf-8") as fh:
            json.dump(lock, fh, ensure_ascii=False, indent=1)
        print("đã ghi", LOCK_PATH, "—", args.version)
        return 0
    lock = json.load(open(LOCK_PATH, encoding="utf-8"))
    diffs = [rel for rel in FILES if lock["files"].get(rel) != now["files"][rel]]
    if lock.get("normalizer_itn") != now["normalizer_itn"]:
        diffs.append("src/channels/normalizer.py (phần ITN/ASR_FIXES)")
    print(f"khóa {lock['version']} ({lock['locked_on']}):", "KHỚP" if not diffs else "LỆCH → " + ", ".join(diffs))
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
