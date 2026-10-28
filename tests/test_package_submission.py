"""scripts/package_submission.py — gói nộp loại .env, backup_*/ và không chứa chuỗi giống API key."""
import os
import shutil
import tempfile
import unittest
import unittest.mock
import zipfile
from tests import _helpers  # noqa: F401
from scripts import package_submission as pkg

# Dựng khóa giả lúc chạy (không viết sẵn trong mã nguồn để chính file test không khớp mẫu quét).
FAKE_KEY = "sk-" + "a1B2" * 8


def write(root, rel, content=b"x"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content if isinstance(content, bytes) else content.encode("utf-8"))


class _PackageBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "Code")
        self.out = os.path.join(self.tmp, "out", "pkg.zip")
        write(self.root, "main.py", "print('hi')\n")
        write(self.root, "src/a.py", "x = 1\n")
        write(self.root, ".env", f"OPENAI_API_KEY={FAKE_KEY}\nLLM_MODEL=gpt-4o-mini\n")
        write(self.root, ".env.example", "OPENAI_API_KEY=\nLLM_MODEL=gpt-4o-mini\n")
        write(self.root, "backup_2026-10-21/CHECKING.md", "backup")
        write(self.root, "src/__pycache__/a.cpython-312.pyc", b"\x00")
        write(self.root, "data/harness_memory.db", b"sqlite")
        write(self.root, "runs/full.jsonl", "{}\n")
        write(self.root, "runs/demo.jsonl", "{}\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def names(self):
        with zipfile.ZipFile(self.out) as zf:
            return set(zf.namelist())


class PackageSubmissionTest(_PackageBase):
    def test_clean_package_excludes_env_backup_cache_db(self):
        res = pkg.build_package(self.root, self.out)
        self.assertTrue(res["ok"], res["findings"])
        names = self.names()
        self.assertIn("main.py", names)
        self.assertIn(".env.example", names)
        self.assertIn("runs/full.jsonl", names)
        self.assertNotIn(".env", names)
        self.assertFalse([n for n in names if n.startswith("backup_")])
        self.assertFalse([n for n in names if "__pycache__" in n])
        self.assertNotIn("data/harness_memory.db", names)
        self.assertNotIn("runs/demo.jsonl", names)

    def test_include_db_flag(self):
        res = pkg.build_package(self.root, self.out, include_db=True)
        self.assertTrue(res["ok"])
        self.assertIn("data/harness_memory.db", self.names())

    def test_secret_in_source_blocks_package(self):
        write(self.root, "src/config.py", f'KEY = "{FAKE_KEY}"\n')
        res = pkg.build_package(self.root, self.out)
        self.assertFalse(res["ok"])
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(any(f[0] == "src/config.py" for f in res["findings"]))

    def test_real_env_value_detected_even_without_sk_pattern(self):
        secret = "Zq9" + "Xk7" * 6  # giá trị không giống mẫu sk-
        write(self.root, ".env", f"OPENAI_API_KEY={secret}\n")
        write(self.root, "notes.txt", f"đừng quên dùng {secret} nhé")
        res = pkg.build_package(self.root, self.out)
        self.assertFalse(res["ok"])
        self.assertIn("giá trị khóa thật từ .env", [f[1] for f in res["findings"]])

    def test_findings_never_contain_the_secret_value(self):
        write(self.root, "src/config.py", f'KEY = "{FAKE_KEY}"\n')
        res = pkg.build_package(self.root, self.out)
        self.assertNotIn(FAKE_KEY, str(res["findings"]))

    def test_scan_zip_flags_forbidden_members(self):
        os.makedirs(os.path.dirname(self.out), exist_ok=True)
        with zipfile.ZipFile(self.out, "w") as zf:
            zf.writestr(".env", "A=1")
            zf.writestr("backup_x/a.txt", "a")
        kinds = {f[0] for f in pkg.scan_zip(self.out, set())}
        self.assertEqual(kinds, {".env", "backup_x/a.txt"})

    def test_output_inside_root_is_not_packaged_into_itself(self):
        inside = os.path.join(self.root, "pkg.zip")
        res = pkg.build_package(self.root, inside)
        self.assertTrue(res["ok"])
        with zipfile.ZipFile(inside) as zf:
            self.assertNotIn("pkg.zip", zf.namelist())


class ModelPackagingTest(_PackageBase):
    def test_model_dir_excluded_by_default(self):
        write(self.root, "model_ASR/encoder.int8.onnx", b"\x00" * 64)
        write(self.root, "model_ASR/README.md", "model readme")
        res = pkg.build_package(self.root, self.out)
        self.assertTrue(res["ok"], res["findings"])
        self.assertFalse([n for n in self.names() if n.startswith("model_ASR/")])
        self.assertEqual(res["skipped"].get("model_files"), 2)

    NOTICE_EVIDENCE = ("Kiểm GitHub ggroup-ai-lab/gipformer commit 0cac5b18: không có LICENSE (404). "
                       "HF g-group-ai-lab/gipformer1.5-68M-rnnt: LICENSE 404. README: licensed under the MIT License; "
                       "pyproject.toml: license = MIT; model card: license: mit.")
    MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person ..."

    def _fake_model(self, notice, license_text=None, with_readme=True, with_license=True):
        from src.channels import offline_asr
        for name in offline_asr.GIPFORMER_FILES:
            write(self.root, f"model_ASR/{name}", b"gia mao")
        if with_license:
            write(self.root, "model_ASR/LICENSE", license_text if license_text is not None else self.MIT)
        if with_readme:
            write(self.root, "model_ASR/README.md", "card")
        write(self.root, "model_ASR/NOTICE.md", notice)
        return unittest.mock.patch.object(offline_asr.GipformerASR, "verify_files", lambda self_: None)

    def test_include_model_requires_license_readme_and_vad(self):
        from src.channels import offline_asr
        for name in offline_asr.GIPFORMER_FILES:
            write(self.root, f"model_ASR/{name}", b"gia mao")
        with unittest.mock.patch.object(offline_asr.GipformerASR, "verify_files", lambda self_: None):
            res = pkg.build_package(self.root, self.out, include_model=True)
        self.assertFalse(res["ok"])
        self.assertIn("LICENSE", res["findings"][0][1])
        with self._fake_model("LICENSE_STATUS: derived-from-author-declaration\n" + self.NOTICE_EVIDENCE):
            res = pkg.build_package(self.root, self.out, include_model=True)
        self.assertFalse(res["ok"])
        self.assertIn("silero_vad.onnx", res["findings"][0][1])            # LICENSE/NOTICE đã hợp lệ → lỗi kế tiếp là thiếu VAD

    def test_derived_from_author_declaration_with_evidence_is_accepted(self):
        with self._fake_model("LICENSE_STATUS: derived-from-author-declaration\n" + self.NOTICE_EVIDENCE):
            self.assertIsNone(pkg.license_problem(os.path.join(self.root, "model_ASR")))

    def test_upstream_status_still_accepted(self):
        with self._fake_model("LICENSE_STATUS: upstream\n" + self.NOTICE_EVIDENCE):
            self.assertIsNone(pkg.license_problem(os.path.join(self.root, "model_ASR")))

    def test_notice_without_evidence_blocks(self):
        with self._fake_model("LICENSE_STATUS: derived-from-author-declaration\nchỉ ghi cho có"):
            problem = pkg.license_problem(os.path.join(self.root, "model_ASR"))
        self.assertIn("thiếu bằng chứng", problem)
        for needed in ("GitHub", "Hugging Face", "pyproject.toml"):
            self.assertIn(needed, problem)

    def test_old_derived_status_and_missing_status_block(self):
        with self._fake_model("LICENSE_STATUS: derived\n" + self.NOTICE_EVIDENCE):
            self.assertIn("không hợp lệ", pkg.license_problem(os.path.join(self.root, "model_ASR")))
        with self._fake_model(self.NOTICE_EVIDENCE):
            self.assertIn("thiếu dòng", pkg.license_problem(os.path.join(self.root, "model_ASR")))

    def test_missing_license_or_readme_blocks_packaging(self):
        for kw, word in (({"with_license": False}, "LICENSE"), ({"with_readme": False}, "README.md")):
            with self._fake_model("LICENSE_STATUS: derived-from-author-declaration\n" + self.NOTICE_EVIDENCE, **kw):
                res = pkg.build_package(self.root, self.out, include_model=True)
            self.assertFalse(res["ok"])
            self.assertIn(word, res["findings"][0][1])
            shutil.rmtree(os.path.join(self.root, "model_ASR"), ignore_errors=True)

    def test_license_that_is_not_mit_text_blocks(self):
        with self._fake_model("LICENSE_STATUS: derived-from-author-declaration\n" + self.NOTICE_EVIDENCE, license_text="Tự do dùng"):
            self.assertIn("không phải văn bản MIT", pkg.license_problem(os.path.join(self.root, "model_ASR")))

    def test_real_model_dir_notice_is_valid_now(self):
        """NOTICE.md/LICENSE thật của dự án phải đủ bằng chứng theo luật mới."""
        real = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(pkg.__file__))), "model_ASR")
        if not os.path.isfile(os.path.join(real, "NOTICE.md")):
            self.skipTest("không có model_ASR/")
        self.assertIsNone(pkg.license_problem(real))

    def test_include_model_refuses_files_with_wrong_hash(self):
        for name in ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt", "bpe.model"):
            write(self.root, f"model_ASR/{name}", b"gia mao")
        res = pkg.build_package(self.root, self.out, include_model=True)
        self.assertFalse(res["ok"])
        self.assertIn("SAI SHA-256", res["findings"][0][1])
        self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
