# dataset/ — dữ liệu do nhóm sinh (sắp xếp lại 2026-11-04)

Chỉ còn 4 thư mục, mỗi thư mục một mục đích. Dữ liệu BTC cấp (`BTC-Data-Vong1-TEAMS/`) và bộ kịch bản gõ tay dùng để chấm hằng ngày
(`BTC-Data-Vong1-TEAMS/test_set/team_eval/`) **không nằm ở đây**.

| Thư mục | Là gì | Ai đọc |
|---|---|---|
| `frames/` | **Khung kịch bản** — 64 file `SC-*.frame.json`: 10 khung mẫu (SC-A01…C05) + 54 khung `SC-D01…D54` dựng bằng mã (`src/dataset/frames54.py`, xác định, không tốn LLM) | `scripts/generate_dataset_text.py` (đọc khung → nhờ LLM viết lời thoại); `scripts/frames54_report.py` |
| `agent_eval/` | **Bộ đánh giá agent** — 20 kịch bản định dạng BTC (`SC-*.json`: `customer_turns`, `success_if`, `ground_truth_facts`…) ghép từ lời thoại đã sinh | `run_eval.py --scenarios dataset/agent_eval`; `scripts/validate_scenarios.py --scenarios dataset/agent_eval` |
| `asr/` | **Bộ sinh audio và đo ASR** — 29 file lời thoại từng cuộc (`SC-*.call_n.json`): mỗi lượt có `text_written` (chữ viết) và `text_spoken` (chữ đọc thành tiếng: số đọc bằng chữ, tên sản phẩm đọc theo tiếng Việt) + `speaker` + `entities` | khâu TTS tạo audio → ASR → so với `text_spoken`/`entities` (WER, entity accuracy); `scripts/check_dialogue_rules.py` |
| `reports/` | Sổ cái và bản duyệt: `generation_runs.jsonl` (**sổ cái chi phí — trần cứng 10.000 VND tính trên file này**, đừng xóa/sửa tay), `generation_log.json`, bản duyệt tay `sample10.md` / `frames54_dialogues.md` (checklist: `docs/DATASET_REVIEW_CHECKLIST.md`), báo cáo phân bố khung | người duyệt; `src/dataset/budget.py` |

## Trạng thái (2026-11-04)

- Đã sinh lời thoại: 10 khung mẫu (A/B/C) + 10 khung đại diện (SC-D03, D04, D24, D25, D26, D27, D28, D31, D47, D51) = 20 kịch bản / 29 cuộc; còn **44 khung D chưa sinh** (đang tạm dừng theo yêu cầu 2026-10-27).
- Sổ cái chi phí: 2.076,3 / 10.000 VND.
- Chưa có file audio trong `asr/` — audio thử D01–D04 (TTS) nằm ở `BTC-Data-Vong1-TEAMS/asr/audio/`, lời thoại của chúng ở `BTC-Data-Vong1-TEAMS/asr/ground_truth.json`.

## Lệnh

```bash
python scripts/generate_dataset_text.py --set frames54 --dry-run          # dựng khung vào dataset/frames, không gọi LLM
python scripts/validate_scenarios.py --no-existing --scenarios dataset/agent_eval --dialogues dataset/asr --report
python scripts/check_dialogue_rules.py                                    # luật P1–P4 trên dataset/asr, không tốn tiền
python scripts/frames54_report.py                                         # bảng phân bố + 5 khung ngẫu nhiên -> dataset/reports
```

Các thư mục cũ đã chuyển (không xóa) sang `../NotRelated/truoc_khi_sap_xep_2026-11-04/dataset/`:
`frames54/` (bản chép trùng của `frames/`, riêng D26/D28 là bản cũ lỗi thời) và `rules_report_after.txt`.
