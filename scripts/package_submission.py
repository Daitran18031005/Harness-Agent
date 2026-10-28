"""
Tạo gói nộp bài: nén thư mục Code/ đã LOẠI SẴN `.env`, `backup_*/`, cache, DB/trace cục bộ, rồi KIỂM TRA
trong gói không còn chuỗi nào giống API key (cả mẫu `sk-...` lẫn giá trị thật đọc từ `.env`).

Dùng:
    python scripts/package_submission.py                       # -> ../Code_submission.zip
    python scripts/package_submission.py --out D:/nop/Code.zip
    python scripts/package_submission.py --include-db          # kèm data/*.db (mặc định loại)
    python scripts/package_submission.py                       # MẶC ĐỊNH kèm model_ASR/ (Gipformer + Silero VAD, LICENSE, README, NOTICE; ≈ 54 MB nén)
    python scripts/package_submission.py --no-model            # không kèm model (gói nhẹ; người nhận tải theo README § ASR)

Thoát mã 0 nếu gói sạch; mã 1 (và XÓA gói) nếu phát hiện chuỗi giống khóa bí mật.
Script không bao giờ in giá trị khóa ra màn hình, chỉ in tên file + loại mẫu khớp.
"""
import argparse
import fnmatch
import os
import re
import sys
import zipfile
from typing import Dict, List, Optional, Set, Tuple

DEFAULT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if DEFAULT_ROOT not in sys.path:
    sys.path.insert(0, DEFAULT_ROOT)      # để import src.channels.offline_asr khi chạy `python scripts/package_submission.py`

# Thư mục bị loại ở mọi độ sâu
EXCLUDED_DIR_PATTERNS = ["backup_*", "__pycache__", ".pytest_cache", ".git", ".vscode", ".idea", ".venv", "venv", "node_modules"]
# File bị loại (so khớp theo đường dẫn tương đối, dùng '/')
EXCLUDED_FILE_PATTERNS = [".env", ".env.*", "*.pyc", "runs/demo.jsonl", "runs/ui_session.jsonl"]
KEEP_FILES = {".env.example"}
DB_PATTERNS = ["data/*.db*"]   # gồm .db-wal, .db-shm và bản sao lưu .db.pre_v2.bak
MODEL_DIRS = ("model_ASR", "models")   # trọng số ASR: gói nộp kèm mặc định (--no-model để bỏ); repo Git thì không chứa (.gitignore)
# LICENSE của Gipformer: TÁC GIẢ KHÔNG PHÁT HÀNH file này (GitHub và HF đều 404) nên bản gốc không bao giờ có. Gói nộp chấp nhận
# `LICENSE_STATUS: derived-from-author-declaration` (mẫu MIT dựng theo tuyên bố của tác giả) NẾU `NOTICE.md` ghi đủ bằng chứng; vẫn chấp nhận
# `upstream` (nếu sau này tác giả phát hành). Mọi giá trị khác (vd `derived` cũ) hoặc thiếu bằng chứng → chặn.
LICENSE_OK_STATUSES = {"derived-from-author-declaration", "upstream"}
LICENSE_EVIDENCE = [          # (chuỗi bắt buộc phải có trong NOTICE.md, mô tả bằng chứng)
    ("ggroup-ai-lab/gipformer", "kết quả kiểm repo GitHub (đường dẫn)"),
    ("0cac5b18", "commit đã kiểm của repo GitHub"),
    ("g-group-ai-lab/gipformer1.5-68M-rnnt", "kết quả kiểm repo Hugging Face (đường dẫn)"),
    ("404", "ghi nhận LICENSE không tồn tại (404)"),
    ("licensed under the MIT License", "tuyên bố MIT trong README GitHub"),
    ("pyproject.toml", "tuyên bố MIT trong pyproject.toml"),
    ("license: mit", "tuyên bố MIT trong model card HF"),
]
MODEL_REQUIRED_EXTRA = ("LICENSE", "README.md", "NOTICE.md")   # đi kèm trọng số: giấy phép MIT, model card của tác giả, nguồn gốc

# Mẫu giống API key (bytes để quét được cả file nhị phân)
SECRET_PATTERNS: List[Tuple[str, "re.Pattern[bytes]"]] = [
    ("openai_key (sk-...)", re.compile(rb"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}")),
    ("assignment KEY=<giá trị dài>", re.compile(rb"(?:API_?KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*['\"]?[A-Za-z0-9_\-\.]{24,}", re.I)),
    ("aws_access_key", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("private_key_block", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
SECRET_ENV_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.I)


def load_env_secret_values(root: str) -> Set[bytes]:
    """Giá trị bí mật thật trong .env (tên biến chứa KEY/TOKEN/SECRET/PASSWORD, dài ≥ 12) — để dò đúng giá trị đó
    trong gói. Chỉ giữ trong bộ nhớ, không in."""
    values: Set[bytes] = set()
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return values
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            value = value.strip().strip("'\"")
            if SECRET_ENV_NAME.search(name) and len(value) >= 12:
                values.add(value.encode("utf-8"))
    return values


def _match(rel: str, patterns: List[str]) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(base, p) for p in patterns)


def collect_files(root: str, include_db: bool, out_path: Optional[str] = None,
                  include_model: bool = False) -> Tuple[List[str], Dict[str, int]]:
    """Trả về (danh sách đường dẫn tương đối được đưa vào gói, số lượng bị loại theo nhóm)."""
    included: List[str] = []
    skipped = {"dirs": 0, "files": 0}
    out_abs = os.path.abspath(out_path) if out_path else None
    for dirpath, dirnames, filenames in os.walk(root):
        keep_dirs = []
        for d in dirnames:
            if _match(d, EXCLUDED_DIR_PATTERNS):
                skipped["dirs"] += 1
            else:
                keep_dirs.append(d)
        dirnames[:] = keep_dirs
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if out_abs and os.path.abspath(full) == out_abs:
                continue
            if rel not in KEEP_FILES:
                if _match(rel, EXCLUDED_FILE_PATTERNS) or (not include_db and _match(rel, DB_PATTERNS)):
                    skipped["files"] += 1
                    continue
                if not include_model and rel.split("/", 1)[0] in MODEL_DIRS:
                    skipped["model_files"] = skipped.get("model_files", 0) + 1
                    continue
            included.append(rel)
    return sorted(included), skipped


def scan_bytes(data: bytes, secret_values: Set[bytes]) -> List[str]:
    hits = [name for name, pat in SECRET_PATTERNS if pat.search(data)]
    if any(v in data for v in secret_values):
        hits.append("giá trị khóa thật từ .env")
    return hits


def scan_zip(zip_path: str, secret_values: Set[bytes], skip_model_binaries: bool = False) -> List[Tuple[str, str]]:
    """Quét lại CHÍNH file zip đã tạo (tên + nội dung). Trả về [(tên_trong_gói, loại_mẫu)]."""
    findings: List[Tuple[str, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            base = info.filename.rsplit("/", 1)[-1]
            if base == ".env" or (base.startswith(".env.") and base != ".env.example") or info.filename.startswith("backup_"):
                findings.append((info.filename, "file/thư mục bị cấm có mặt trong gói"))
                continue
            if skip_model_binaries and _is_model_binary(info.filename):
                continue
            for hit in scan_bytes(zf.read(info), secret_values):
                findings.append((info.filename, hit))
    return findings


def license_problem(model_dir: str) -> Optional[str]:
    """Lý do chặn nếu LICENSE/NOTICE chưa đủ để kèm model; None nếu hợp lệ."""
    with open(os.path.join(model_dir, "NOTICE.md"), encoding="utf-8") as fh:
        notice = fh.read()
    with open(os.path.join(model_dir, "LICENSE"), encoding="utf-8", errors="replace") as fh:
        lic = fh.read()
    status = re.search(r"^LICENSE_STATUS:\s*([\w-]+)", notice, re.M | re.I)
    if not status:
        return "NOTICE.md thiếu dòng `LICENSE_STATUS: derived-from-author-declaration` (hoặc `upstream`)"
    value = status.group(1).lower()
    if value not in LICENSE_OK_STATUSES:
        return f"`LICENSE_STATUS: {value}` không hợp lệ (chấp nhận: {', '.join(sorted(LICENSE_OK_STATUSES))})"
    if "MIT License" not in lic or "Permission is hereby granted" not in lic:
        return "LICENSE không phải văn bản MIT"
    missing = [desc for token, desc in LICENSE_EVIDENCE if token not in notice]
    if missing:
        return "NOTICE.md thiếu bằng chứng: " + "; ".join(missing)
    return None


def _is_model_binary(rel: str) -> bool:
    return rel.split("/", 1)[0] in MODEL_DIRS and rel.lower().endswith((".onnx", ".model"))


def build_package(root: str, out_path: str, include_db: bool = False, include_model: bool = False) -> Dict[str, object]:
    root = os.path.abspath(root)
    out_path = os.path.abspath(out_path)
    secret_values = load_env_secret_values(root)
    files, skipped = collect_files(root, include_db, out_path, include_model)
    if include_model:
        # Trọng số nhị phân: không quét "khóa bí mật" trên 73 MB nhị phân, thay bằng kiểm SHA-256 đúng như khi nạp model.
        from src.channels.audio_vad import SILERO_SHA256_PREFIX
        from src.channels.offline_asr import ASRModelError, GipformerASR, sha256_prefix
        mdir = os.path.join(root, "model_ASR")
        try:
            GipformerASR(model_dir=mdir).verify_files()
            missing = [f for f in MODEL_REQUIRED_EXTRA if not os.path.isfile(os.path.join(mdir, f))]
            if missing:
                raise ASRModelError("thiếu " + ", ".join(missing) + " (bắt buộc kèm LICENSE, NOTICE.md và README.md = model card của tác giả)")
            problem = license_problem(mdir)
            if problem:
                raise ASRModelError("LICENSE/NOTICE chưa hợp lệ: " + problem)
            vad = os.path.join(mdir, "silero_vad.onnx")
            if not os.path.isfile(vad):
                raise ASRModelError("thiếu silero_vad.onnx (xem README § ASR)")
            if sha256_prefix(vad, len(SILERO_SHA256_PREFIX)) != SILERO_SHA256_PREFIX:
                raise ASRModelError("silero_vad.onnx SAI SHA-256")
        except ASRModelError as e:
            return {"files": len(files), "skipped": skipped, "out": out_path, "ok": False, "nested_archives": [],
                    "findings": [("model_ASR/", f"không đính kèm được model: {e}")]}

    # Quét nguồn trước khi nén (phát hiện sớm), rồi quét lại gói sau khi nén (kiểm chứng cuối cùng).
    pre_findings: List[Tuple[str, str]] = []
    for rel in files:
        if _is_model_binary(rel):
            continue
        with open(os.path.join(root, rel), "rb") as fh:
            for hit in scan_bytes(fh.read(), secret_values):
                pre_findings.append((rel, hit))

    result: Dict[str, object] = {"files": len(files), "skipped": skipped, "out": out_path,
                                 "findings": pre_findings, "ok": False,
                                 "nested_archives": [f for f in files if f.lower().endswith((".zip", ".rar", ".7z"))]}
    if pre_findings:
        return result  # không tạo gói

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(os.path.join(root, rel), arcname=rel)

    post_findings = scan_zip(out_path, secret_values, skip_model_binaries=True)
    if post_findings:
        os.remove(out_path)
        result["findings"] = post_findings
        return result
    result["ok"] = True
    result["size_bytes"] = os.path.getsize(out_path)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đóng gói nộp bài đã loại .env và backup_*/, kiểm tra không lộ khóa.")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="Thư mục cần nén (mặc định: Code/)")
    ap.add_argument("--out", default=None, help="Đường dẫn file .zip (mặc định: <root>/../Code_submission.zip)")
    ap.add_argument("--include-db", action="store_true", help="Kèm data/*.db (mặc định loại)")
    ap.add_argument("--no-model", action="store_true",
                    help="KHÔNG kèm model_ASR/. Mặc định gói nộp kèm model (kiểm SHA-256 + có LICENSE và README của tác giả); "
                         "repo Git vẫn không chứa model (đã nằm trong .gitignore)")
    ap.add_argument("--include-model", action="store_true", help=argparse.SUPPRESS)   # giữ để tương thích lệnh cũ (nay là mặc định)
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    out = args.out or os.path.join(os.path.dirname(root), "Code_submission.zip")
    result = build_package(root, out, include_db=args.include_db, include_model=not args.no_model)

    if not result["ok"]:
        print("✖ KHÔNG tạo gói. Lý do (khóa bí mật / file bị cấm / model hoặc LICENSE chưa hợp lệ):")
        for name, kind in result["findings"]:
            print(f"   - {name}: {kind}")
        print("  Hãy xử lý các mục trên rồi chạy lại.")
        return 1

    sk = result["skipped"]
    print(f"✔ Đã tạo {result['out']}")
    print(f"  {result['files']} file, {result['size_bytes']/1024/1024:.1f} MB; đã loại {sk['dirs']} thư mục (backup_*, __pycache__, ...) và {sk['files']} file (.env, DB, trace cục bộ, ...)")
    print("  Kiểm tra sau khi nén: không có .env, không có backup_*/, không có chuỗi giống API key.")
    if not args.no_model:
        print("  Đã kèm model_ASR/ (SHA-256 khớp; có LICENSE, README của tác giả, NOTICE, Silero VAD).")
    else:
        print("  Không kèm model ASR (--no-model): người nhận tải theo README § ASR.")
    if result["nested_archives"]:
        print("  ⚠ Gói chứa file nén lồng nhau (không quét được bên trong):", ", ".join(result["nested_archives"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
