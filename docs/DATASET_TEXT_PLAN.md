# DATASET_TEXT_PLAN.md — kế hoạch chi tiết sinh dataset VĂN BẢN (chưa sinh dữ liệu)

> **Trạng thái (2026-10-21, cập nhật): D1 (bộ kiểm S1–S14) ✅, D2 (khung xác định 10 mẫu) ✅, D3a (10 mẫu sinh bằng gpt-6-luna, 470,7/500 VND) ✅ — ĐANG CHỜ BẠN XEM `dataset/review/sample10.md`; D3b (54 kịch bản còn lại, ≤ 5.000 VND) chưa chạy.** Đã duyệt: model sinh = gpt-6-luna; trần 10 mẫu ≤ 500 VND, 54 kịch bản ≤ 5.000 VND. *(Bản kế hoạch gốc bên dưới giữ nguyên:)* **CHỈ LÀ KẾ HOẠCH, chờ bạn duyệt trước khi gọi LLM.** Cơ cấu tổng (86 kịch bản / 135 cuộc / 37 đa phiên / 15 đa kênh / 27 ca khó) đã duyệt ở [DATASET_PLAN.md](DATASET_PLAN.md). Tài liệu này chỉ chi tiết hóa việc làm **dataset văn bản** theo thứ tự bạn chốt: **bộ kiểm tra tự động → 10 kịch bản mẫu → bạn xem → sinh phần còn lại**. Audio (TTS + nhóm tự thu) làm sau, dùng đúng lời thoại từng lượt đã lưu ở đây.

## 0. Hai quyết định còn treo ở DATASET_PLAN § 9 (cần bạn chốt)

| # | Câu hỏi | Đề xuất của tôi |
|---|---|---|
| 4 | Model sinh lời thoại | **`gpt-4o-mini`** (đã dùng, giá đã đo: ~19 VND/lượt agent; sinh văn bản ngắn rẻ hơn nhiều). `gpt-6-luna` giữ làm **judge** (phải khác model agent) |
| 5 | Trần chi phí | **10 kịch bản mẫu: ≤ 500 VND**; phần còn lại (54 kịch bản): **≤ 5.000 VND**, mỗi lần chạy có `--max-cost-vnd` cứng (như `run_eval.py`). Ước tính thật ≈ 2,5–5 nghìn VND cho cả 64 kịch bản (DATASET_PLAN § 6) — chưa đo lại trên bài toán này |

(Câu 2/3 — giọng vùng miền, ai duyệt/ghi âm — thuộc phần audio, không chặn phần văn bản.)

## 1. Nguyên tắc thiết kế

1. **Đáp án do code tính, LLM chỉ viết lời.** Khung kịch bản (khách, SKU, ngày, KM, tồn kho, hạn mức COD, giá sau KM) lấy từ `catalog/*` và `eval/mock_tools.py` thật. `ground_truth_facts`, `success_if`, `must_carry_over`, `must_not_ask`, `memory_expectation` do code sinh.
2. **Lời agent dùng ô trống, không để LLM tự nêu số.** LLM viết lời agent với placeholder (`{price_vnd}`, `{promo_end}`, `{order_id}`, `{warranty_months}`…); code điền giá trị từ `mock_tools` → lời agent **luôn khớp sự thật** (đây cũng là transcript chuẩn của audio). Khách thì được nêu số theo `facts_established`.
3. **Mỗi cuộc lưu lời thoại theo TỪNG LƯỢT, cả hai phía** (không chỉ `customer_turns`), để sau này sinh audio + `segments.json` (xem § 3).
4. **Không đụng định dạng BTC:** file kịch bản vẫn đúng `schemas/scenario_format.md` (chỉ các trường BTC); lời thoại đầy đủ nằm ở file riêng (BTC không đọc, `ALLOWED_CALL_FIELDS` giữ nguyên).
5. **Dữ liệu tổng hợp:** SĐT/địa chỉ chỉ từ dải giả; không có thông tin cá nhân thật.

## 2. Bố cục thư mục (mới, chỉ thêm)

```
dataset/
  scenarios/SC-<id>.json            # đúng schema BTC (22 kịch bản cũ giữ nguyên ở test_set/, không chép lại)
  dialogues/SC-<id>.call_<n>.json   # lời thoại TỪNG LƯỢT, cả hai phía (§ 3)
  frames/SC-<id>.frame.json         # khung xác định bằng code (trước khi gọi LLM) — để tái lập/kiểm
  review/sample10.md                # bản dễ đọc cho bạn duyệt (10 kịch bản mẫu)
  manifest.json                     # danh sách + tập (dev 60% / held-out 40%) + người duyệt + mã băm
  reports/                          # đầu ra validate + phân bố
```

## 3. Định dạng lời thoại từng lượt (phục vụ audio)

`dataset/dialogues/SC-A07.call_2.json`:

```json
{ "scenario_id": "SC-A07", "call": "call_2", "channel": "hotline", "call_date": "2026-10-22",
  "turns": [
    {"idx": 1, "speaker": "A", "text_written": "Dạ em chào chị Thu, hôm 15/10 em có tư vấn chị AirPure Y 25m², giá 5.200.000đ ạ.",
     "text_spoken": "dạ em chào chị thu hôm mười lăm tháng mười em có tư vấn chị e pia y hai mươi lăm mét vuông giá năm triệu hai trăm nghìn ạ",
     "entities": {"sku": "SKU-AP-Y", "price_vnd": 5200000, "room_area_m2": 25}, "tool_basis": ["pricing.get_quote"]},
    {"idx": 2, "speaker": "C", "text_written": "ừ chị hỏi chồng rồi, lên đơn đi em", "text_spoken": "...", "entities": {"blocker_resolved": true}}
  ] }
```

- `speaker`: `A` (agent) / `C` (khách) — đúng ký hiệu của `asr/ground_truth.json`.
- `text_written`: như khách/agent sẽ gõ/nói (số, teencode…). `text_spoken`: **dạng đọc thành lời** (số bằng chữ, tên hãng đọc theo `config/product_aliases.json`, bỏ dấu câu) — là transcript chuẩn để đo WER và là văn bản đưa vào TTS, đúng quy ước của BTC (số bằng chữ). Sinh **bằng code** từ `text_written` (bộ "ITN ngược" `spoken_form()`, có test hai chiều: `ITN(spoken_form(x)) == x` cho số tiền/SĐT/ngày/diện tích), không để LLM tự đọc số.
- `entities`: thực thể của lượt (khóa như `ground_truth.json`: sku, price_vnd, promo_expiry, blocker…), **code gắn từ khung**, không do LLM khai.
- Với cuộc có `customer_turns_asr`: lưu thêm `text_asr` ở lượt khách (lỗi ASR giả lập đúng như `customer_turns_asr`).
- `customer_turns` trong file kịch bản = các `text_written` của lượt `C` (một nguồn duy nhất, sinh ra từ file này để không lệch).
- Audio sau này: ghép `text_spoken` từng lượt (giọng agent ≠ giọng khách), ghi `<id>.segments.json` = `[{idx, speaker, start, end}]` → `turns[].idx` trong `hypotheses.json`.

## 4. Các bước và đầu ra

| Bước | Việc | Đầu ra | Kiểm |
|---|---|---|---|
| **D1** | **`scripts/validate_scenarios.py`** (bộ kiểm tra tự động, viết TRƯỚC) + `--report` phân bố; chạy trên 22 kịch bản hiện có | số "hiện có" tái lập bằng lệnh | test đơn vị cho từng luật (ca đúng + ca cố tình sai) |
| **D2** | Sinh **khung xác định** cho 10 kịch bản mẫu (không LLM): chọn khách/SKU/ngày từ catalog+CRM, tính đáp án từ `mock_tools` | `dataset/frames/*` | validate khung (đáp án khớp mock) |
| **D3a** | LLM viết lời thoại **10 mẫu** (≤ 500 VND, `--max-cost-vnd`) → code điền ô trống, gắn `entities`, sinh `text_spoken`, `customer_turns` → validate → sinh lại mẫu lỗi (tối đa 2 lần) | `dataset/scenarios`, `dialogues`, `review/sample10.md` | validate xanh + báo cáo lần sinh lại |
| **— DỪNG: bạn xem 10 mẫu —** | | | duyệt/sửa quy tắc văn phong |
| D3b | Sinh 54 kịch bản còn lại (≤ 5.000 VND) | đủ 64 kịch bản mới | validate + phân bố đạt ngưỡng |
| D4 | Duyệt tay 15% (≈ 13 kịch bản, ưu tiên ca khó/đa kênh); chia dev/held-out | `manifest.json` | — |

## 5. Bộ kiểm tra tự động (`validate_scenarios.py`) — danh sách luật

Mỗi luật có mã, mức (LỖI chặn / CẢNH BÁO), test riêng:

| Mã | Luật | Mức |
|---|---|---|
| S1 | Đúng schema `scenario_format.md`: trường bắt buộc, `calls` chỉ `call_1..call_3` liên tục, chỉ trường cho phép, `expected_outcome` ∈ {hen_goi_lai, chot_don, chuyen_may, tu_choi} | LỖI |
| S2 | Ngày: `call_date` hoặc `days_later`; ngày cuộc sau > cuộc trước; đều ≥ 2026-10-15 | LỖI |
| S3 | **Mọi `facts_established` xuất hiện trong lời khách** của cuộc đó (sau ITN: số tiền, diện tích, size, màu, blocker theo từ khóa) | LỖI |
| S4 | `ground_truth_facts.price_vnd`/`promo_active`/`in_stock` **khớp `mock_tools`** tại ngày cuộc gọi (đúng thứ `scan_btc_data.py` đã làm cho 7 mẫu) | LỖI |
| S5 | `success_if.tool_called` + `args_match` khớp chữ ký tool trong `tools.schema.json`; SKU tồn tại trong catalog | LỖI |
| S6 | `must_carry_over` ⊆ `facts_established` của cuộc trước; `must_not_ask` ⊆ `must_carry_over`; cuộc 1 không có `must_*` | LỖI |
| S7 | Nhãn `hard_case` đúng 1 trong 4 loại (đổi ý · mâu thuẫn · KM hết hạn · ngoài tài liệu) hoặc 5 loại giữ lại, và **đúng cấu trúc loại đó** (vd "mâu thuẫn" phải có ≥ 2 cuộc và `memory_expectation.superseded`) | LỖI |
| S8 | Đa kênh: `channel_identity` đúng dạng kênh; có lượt khách đọc SĐT ở cuộc đổi kênh (để nối danh tính); SĐT thuộc dải giả | LỖI |
| S9 | Không số thật: SĐT/địa chỉ/CCCD chỉ từ dải giả; không trùng SĐT với khách khác (trừ ca "SĐT dùng chung") | LỖI |
| S10 | Lời thoại: không trống; ≥ 3 lượt khách/cuộc; lượt khách ≤ 40 từ; không trùng ≥ 85% (độ giống câu) với kịch bản khác | CẢNH BÁO (trùng → LỖI) |
| S11 | Lời agent: mọi số tiền/ngày trong `text_written` của agent **bằng giá trị code điền** (không có số tự do); không xuất hiện ô trống chưa điền `{…}` | LỖI |
| S12 | `text_spoken` đúng: `ITN(text_spoken)` trả lại các số trong `text_written`; không còn chữ số, dấu câu | LỖI |
| S13 | `customer_turns` trong kịch bản == các lượt `C` của file lời thoại | LỖI |
| S14 | Phân bố: đếm số cuộc, khách đa phiên / ≥ 3 phiên / đa kênh, ca khó theo loại, persona, ngành; so với ngưỡng, in ✔/✗ (`--report`) | báo cáo |

## 6. 10 kịch bản mẫu (bạn xem trước khi sinh tiếp)

Chọn để **phủ mọi loại cấu trúc** và các lỗi lớn nhất đã gặp:

| # | Nhóm | Nội dung | Ca khó / kiểm gì |
|---|---|---|---|
| 1 | A (2 cuộc, đổi kênh Fanpage→Hotline) | tư vấn máy lọc không khí có trẻ nhỏ → gọi lại chốt | nối danh tính qua SĐT; blocker "hỏi chồng" |
| 2 | A (2 cuộc) | giày chạy bộ, khách đổi diện tích/size so với lần trước | **mâu thuẫn với phiên trước** (chưa có loại nào) |
| 3 | A (2 cuộc, Zalo→Hotline) | KM có hạn → khách gọi sau hạn | **KM hết hạn** (dịch ngày) |
| 4 | B (3 cuộc, 3 kênh) | hỏi giá → chốt đơn → đổi size có phụ thu | đa kênh + phụ thu biến thể |
| 5 | B (3 cuộc) | mẹ & bé: máy hút sữa → hỏi đơn → khiếu nại giao trễ | cuộc 3 hỏi đơn/khiếu nại; handoff |
| 6 | C (1 cuộc) | khách đổi ý giữa cuộc (từ mẫu X sang mẫu Y) | **đổi ý** |
| 7 | C | hỏi tác dụng y tế của máy hút sữa | **hỏi ngoài tài liệu** (phải từ chối khéo/chuyển) |
| 8 | C | so sánh với đối thủ + chính sách không có trong tài liệu | **hỏi ngoài tài liệu** (loại khác) |
| 9 | C | COD vượt hạn mức 10 triệu | ca giữ lại (tool lỗi thật) |
| 10 | C | khách viết teencode/không dấu + `customer_turns_asr` | chuẩn hóa tiếng Việt |

Trong 10 mẫu, **4 kịch bản (1, 3, 6, 10) có lời agent đủ cả hai phía** ngay từ đầu để kiểm đường `text_spoken` → audio; các mẫu còn lại cũng có lời agent (rẻ), nên **toàn bộ 135 cuộc đều lưu hai phía** (chi phí thêm ~1–2 nghìn VND) và chọn 48 cuộc có audio sau.

## 7. Cách bạn xem 10 mẫu

`dataset/review/sample10.md`: mỗi kịch bản một mục — tình huống, bảng lượt thoại hai phía (`written` và `spoken`), đáp án do code tính (giá/KM/ngày kèm nguồn `mock_tools`), kết quả validate từng luật, chi phí thật của lần sinh. Bạn đánh dấu: *duyệt / sửa văn phong / loại*. Phản hồi của bạn được chuyển thành quy tắc cho prompt (ghi lại), rồi mới chạy D3b.

## 8. Chưa làm / rủi ro

- Chưa sinh gì; chưa viết `validate_scenarios.py` (đó là việc đầu tiên khi bạn duyệt).
- `spoken_form()` (ITN ngược) và bảng cách đọc tên sản phẩm cho **28/32 SKU còn lại** do nhóm tự đoán — chỉ D01–D04 kiểm chứng; sẽ nghe thử TTS ở bước audio.
- Văn phong LLM có thể đều/lịch sự → đã chuẩn bị persona + teencode + lỗi ASR; 10 mẫu chính là để bắt lỗi này sớm.
- Luật ASR đã **khóa** (`config/asr_rules.lock.json`): audio sinh từ dataset này là **tập CHƯA THẤY** cho entity accuracy; số đo trên đó báo riêng, và luật không được chỉnh theo kết quả đó trừ khi có phiên bản luật mới ghi lý do.
