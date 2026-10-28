# DATASET_PLAN.md — Kế hoạch dataset đạt ngưỡng M1

> **Trạng thái (cập nhật 2026-10-24): CƠ CẤU ĐÃ ĐƯỢC DUYỆT** (86 kịch bản / 135 cuộc gọi / 37 đa phiên / 15 đa kênh / 27 ca khó; audio ~85 giây cả hai phía). **5 câu ở mục 9 ĐÃ TRẢ LỜI (2026-10-24). Bảng đổi 12 khung (§ 9.1) đã duyệt và đã viết mã. CHƯA SINH LỜI THOẠI — chờ người dùng duyệt (1) cụm sửa lỗi demo, (2) 10 khung đầu.** Số liệu "hiện có" được đếm thực tế ngày 2026-10-21 (xem [PLAN.md § 6](PLAN.md)).
> Chi phí LLM dùng số đo thật của bước 15 (xem mục 6). Mọi con số đích bên dưới đều có lệnh kiểm tra tự động (mục 7).

---

## 1. Hiện có so với ngưỡng

| Hạng mục | Ngưỡng (đề M1 / yêu cầu của bạn) | Hiện có | Thiếu |
|---|---|---:|---:|
| Hội thoại (transcript = 1 cuộc gọi/chat) | ≥ 120 | 31 | **89** |
| Khách đa phiên (≥ 2 cuộc cùng 1 khách) | ≥ 30 | 9 | **21** |
| Trong đó có khách ≥ 3 phiên | có (M2: nhiều) | 0 | **≥ 1** (kế hoạch: 12) |
| Khách đa kênh (cả gọi + chat) | ≥ 10 | 3 | **7** |
| Audio | ≥ 40 cuộc / ≥ 1 giờ | 4 file / 2,5 phút | **36 cuộc / 57 phút** |
| File đo WER/CER | ≥ 20 | 4 | **16** |
| Kịch bản đa phiên (2–3 cuộc) | ≥ 20 | 9 | **11** |
| Ca khó đủ 4 loại (đổi ý · mâu thuẫn với phiên trước · KM hết hạn · hỏi ngoài tài liệu) | ≥ 5, đủ 4 loại | đổi ý 1 · mâu thuẫn **0** · KM hết hạn 2 · ngoài tài liệu 2 | loại "mâu thuẫn" |
| SKU / persona / ngành | ≥ 30 / ≥ 3 / 1 | 136 / 12 / 3 | — (đã đạt) |

---

## 2. Thiết kế bộ dữ liệu đích

Giữ nguyên 22 kịch bản hiện có (7 public của BTC + 15 `SC-GEN`), **thêm 64 kịch bản mới** → **86 kịch bản, 135 cuộc gọi** (đích 120, dư ~12% để bù mẫu bị loại khi kiểm tra chất lượng).

| Nhóm mới | Số kịch bản | Số cuộc / kịch bản | Số cuộc gọi | Vai trò |
|---|---:|---:|---:|---|
| **A** — đa phiên 2 cuộc | 16 | 2 | 32 | khách gọi lại; 8 kịch bản đổi kênh (2 kênh) |
| **B** — đa phiên 3 cuộc | 12 | 3 | 36 | cuộc 3 = đổi size/hỏi đơn/khiếu nại; 4 kịch bản dùng 3 kênh |
| **C** — 1 cuộc | 36 | 1 | 36 | khách mới, ca khó "hỏi ngoài tài liệu", "đổi ý trong cuộc", KM hết hạn |
| **Cộng mới** | **64** | | **104** | |
| **Hiện có** | 22 | | 31 | |
| **Tổng** | **86** | | **135** | |

**Phép tính đối chiếu ngưỡng (đều dư):**

| Ngưỡng | Cách đạt | Kết quả |
|---|---|---:|
| ≥ 120 hội thoại | 31 + 104 | **135** |
| ≥ 30 khách đa phiên | 9 + 16 (A) + 12 (B) | **37** |
| có khách ≥ 3 phiên | nhóm B | **12** |
| ≥ 10 khách đa kênh | 3 hiện có + 8 (A) + 4 (B) | **15** |
| ≥ 20 kịch bản đa phiên | = số khách đa phiên | **37** |

**Mẫu đa kênh (15 khách, gồm 3 khách hiện có):** Fanpage→Hotline (5: 2 hiện có + 3 mới), Zalo→Hotline (4 mới), Hotline→Zalo (2: 1 hiện có + 1 mới); nhóm B thêm kiểu 3 kênh: Fanpage→Zalo→Hotline (2), Zalo→Fanpage→Hotline (2). Mỗi kịch bản đa kênh có 1 lượt khách đọc SĐT để nối danh tính (như SAMPLE-04).

**Ca khó — đích 27 ca (đủ 4 loại, mỗi loại ≥ 5):**

| Loại | Hiện có | Thêm mới | Tổng | Đặt ở nhóm |
|---|---:|---:|---:|---|
| Đổi ý (giữa cuộc / giữa các cuộc) | 1 | 5 | **6** | C (trong 1 cuộc), A |
| **Mâu thuẫn với phiên trước** (khách nói khác thông tin đã lưu: đổi diện tích, đổi ngân sách, đổi người dùng…) | **0** | 6 | **6** | A, B (bắt buộc ≥ 2 cuộc) |
| KM hết hạn (gọi lại sau khi KM qua hạn; KM `once_per_customer`, điều kiện vùng/min_qty) | 2 | 5 | **7** | A, B (cần dịch ngày cuộc gọi) |
| Hỏi ngoài tài liệu (y tế, so sánh đối thủ, chính sách không có; phiên bản chính sách cũ) | 2 | 6 | **8** | C |
| *Ngoài 4 loại (giữ lại)*: COD vượt hạn mức, SĐT dùng chung, đổi size phụ thu, trade-in, SKU ngừng bán | 6 | — | 6 | — |

**Phân bổ khác:** 12 persona của BTC chia đều (mỗi persona ≥ 5 kịch bản; ≥ 3 persona bắt buộc đã đạt); 3 ngành theo tỉ lệ catalog (gia dụng ~55%, mẹ & bé ~25%, thời trang ~20%); 25% lượt khách viết teencode/không dấu; 20% cuộc có `customer_turns_asr` (lỗi ASR giả lập). **Chia tập:** 60% *dev* (để chỉnh prompt/luật), 40% *held-out* (chỉ chạy khi chốt — tránh "học vẹt" bộ test).

---

## 3. Audio

| Hạng mục | Đích | Cách tính |
|---|---|---|
| Số cuộc có audio | **48** (≥ 40) | chọn từ 135 cuộc, ưu tiên cuộc có số tiền/SĐT/tên sản phẩm; cả hai phía (khách + agent) |
| Thời lượng | **~68 phút** (≥ 60) | 48 cuộc × ~85 giây (≈ 6 lượt khách + 6 lượt agent). *Lưu ý:* D01–D04 hiện chỉ ~37 giây/file nên **kịch bản audio phải dài hơn** — nếu chỉ đọc lượt khách thì 48 file chỉ được ~27 phút, KHÔNG đủ 1 giờ |
| File đo WER/CER | **≥ 24** (≥ 20) | lời khách của các cuộc trên, ground truth = chính kịch bản đọc; chuẩn hóa số theo đề ("bốn triệu tám trăm chín mươi" → 4.890.000) |
| Entity accuracy số tiền / SĐT | ≥ 60 lần nêu số tiền, ≥ 24 lần nêu SĐT | cài vào kịch bản để thống kê có ý nghĩa |
| Giọng TTS | 2 giọng (1 nam, 1 nữ) cho agent/khách | **Đã kiểm tra danh sách giọng `edge-tts` ngày 2026-10-21** (322 giọng toàn cầu): **chỉ có 2 giọng tiếng Việt, cùng locale `vi-VN`** — `vi-VN-HoaiMyNeural` (nữ) và `vi-VN-NamMinhNeural` (nam); metadata **không ghi vùng miền/giọng địa phương và không có biến thể Trung/Nam**. Chưa nghe thử nên không khẳng định giọng nghe thiên về miền nào. `edge-tts` miễn phí nhưng là kênh **không chính thức**; `gTTS` dự phòng |
| **Giọng vùng miền (đề: 2 miền)** | ≥ 2 miền | **`edge-tts` KHÔNG đáp ứng** (chỉ 2 giọng `vi-VN`, không có giọng vùng miền). **Phương án nhóm tự thu âm (đã thêm theo yêu cầu): ≥ 10 file giọng miền Nam và miền Trung** — thành viên nhóm (hoặc người quen) đọc **kịch bản tổng hợp** (không đọc thông tin cá nhân thật), **có đồng ý bằng văn bản** cho phép dùng giọng làm dữ liệu nghiên cứu/nộp bài (ghi rõ phạm vi, cho phép rút lại), ghi vào `asr/audio_real/` kèm `consent.csv` (mã người đọc ẩn danh, miền, giới tính, đã đồng ý) và `manifest.json`; chia ít nhất 5 file miền Nam + 5 file miền Trung, trộn nam/nữ, tốt nhất có vài file ghi trong môi trường ồn nhẹ (tiền đề cho M2). Ước tính ~2 giờ người cho 10–16 file. Phương án khác (b) TTS trả phí có giọng vùng miền (FPT.AI/Viettel/Zalo — **tôi chưa có bảng giá**, phải kiểm tra) hoặc (c) chấp nhận hạn chế và nêu rõ trong báo cáo |
| Nhiễu (đường phố, sóng yếu) | không bắt buộc ở M1 (M2 ≥ 20%) | có thể thêm sau bằng trộn nhiễu; `scripts/compare_asr.py --add-noise-snr 10` đã có sẵn bản trộn nhiễu Gaussian **tổng hợp** (không phải nhiễu đường truyền thật) để thử VAD/độ bền |
| **Mốc thời gian từng lượt (yêu cầu cho bước tạo audio)** | mọi file audio | Khâu tạo audio (TTS **từng lượt một**, ghép lại bằng `numpy`, xen khoảng lặng 0,4–0,8 giây, giọng agent ≠ giọng khách) PHẢI ghi `<id>.segments.json` cạnh file audio: `{"id": "D01", "segments": [{"idx": 1, "speaker": "A", "start": 0.0, "end": 4.1}, ...]}` (cùng định dạng `asr/audio/<id>.segments.json` mà `reference_eval` dùng cho diarization, thêm khóa `idx` = số thứ tự lượt trong ground truth). `src/channels/asr_hypotheses.py` dùng file này để điền `turns[].idx` trong `hypotheses.json`; **không có file → không xuất `turns`** (không giả lập tách người nói). Bản TTS D01–D04 hiện có là MỘT giọng đọc liền cả hội thoại nên **không có** mốc lượt; file nhóm tự thu cũng cần ghi mốc (hoặc đọc từng lượt thành file riêng rồi ghép) |
| Tham chiếu từ BTC | `asr/ground_truth.json` có 12 hội thoại đa lượt (BTC giữ 8, đưa 4 mẫu D01–D04): **7–10 lượt, 137–186 từ cả hai phía (~60–75 giây nói)**, giọng khách/agent gán nhãn vùng miền **Bắc/Nam/Trung**, 1/4 có nhiễu → độ dài ~85 giây/cuộc ở trên là hợp lý, và bộ chấm thật SẼ có giọng vùng miền + nhiễu (nên WER đo trên TTS 1 giọng chỉ để kiểm định dạng, không đại diện) |
| Chạy ASR | faster-whisper chạy **local, không tốn API** | ~68 phút audio: ước tính 20–70 phút trên CPU với model `base`; `small` gấp 2–3 lần (dùng Colab GPU nếu cần). *Đây là ước tính, chưa đo* |

---

## 4. Cách sinh (tái lập bằng code, không chép tay)

1. **Khung xác định bằng code** (`generate_dataset.py` mở rộng): chọn khách/SKU/ngày từ catalog + CRM thật; **đáp án** (`ground_truth_facts`, `success_if`, `must_carry_over`, `must_not_ask`, `memory_expectation`) **do code tính từ `mock_tools.py`** (giá sau KM theo ngày, tồn kho theo ngày, hạn mức COD…) — không để LLM bịa đáp án.
2. **LLM chỉ viết lời thoại** (model rẻ, vd `gpt-4o-mini`; temperature ~0.8 để đa dạng): nhận khung + persona + ràng buộc "khách phải nói đúng các fact trong `facts_established`" → trả về `customer_turns` (và lời agent cho 48 cuộc có audio).
3. **Kiểm tra tự động** (`scripts/validate_scenarios.py`, mới — BTC nhắc tới nhưng không có trong gói): đúng schema `scenario_format.md`; ngày cuộc gọi tăng dần; mọi `facts_established` **xuất hiện trong lời khách** (có căn cứ); giá/KM khớp `mock_tools`; nhãn `hard_case` đúng loại; không trùng lặp (độ giống câu); SĐT/địa chỉ chỉ lấy từ dải **giả** (không số thật); loại và sinh lại mẫu lỗi.
4. **Duyệt tay 15%** (~13 kịch bản, ưu tiên ca khó và đa kênh) để bắt lỗi văn phong/tình huống phi thực tế.
5. **Sinh audio** (`scripts/generate_test_audio.py` mở rộng): ghi `manifest.json` (file, thời lượng, giọng, kịch bản/cuộc).
6. **Báo cáo phân bố** tự động (số cuộc, khách đa phiên/đa kênh, tổng thời lượng, đếm ca khó theo loại) — làm phụ lục "Dataset + mô tả" của hồ sơ nộp.

**Quyền riêng tư:** toàn bộ dữ liệu là tổng hợp (không dùng ghi âm khách thật); ghi âm của thành viên nhóm (nếu chọn phương án a) chỉ khi có đồng ý và kịch bản đọc là kịch bản tổng hợp.

---

## 5. Thứ tự làm

| Giai đoạn | Việc | Sản phẩm | Phụ thuộc |
|---|---|---|---|
| D1 | Viết `validate_scenarios.py` + báo cáo phân bố; chạy trên 22 kịch bản hiện có | Số "hiện có" tái lập được bằng lệnh | — |
| D2 | Mở rộng `generate_dataset.py` (khung xác định; nhóm A, B, C; ca khó 4 loại) — **chưa gọi LLM** | 64 khung kịch bản + đáp án | D1 |
| D3 | Gọi LLM viết lời thoại (có trần chi phí) → validate → sinh lại mẫu lỗi | 64 kịch bản hoàn chỉnh | D2, bạn duyệt |
| D4 | Duyệt tay 15%; chia dev/held-out | Bộ kịch bản chốt | D3 |
| D5 | Sinh audio 48 cuộc (+ ghi âm vùng miền nếu chọn) | `asr/audio/*`, `manifest.json`, ground truth | D4, quyết định giọng |
| D6 | Chạy ASR local, tính WER/CER + entity accuracy (= bước **16a**) | `asr/hypotheses.json`, báo cáo | D5 |
| D7 | Chạy đánh giá đầy đủ (bước 15 GĐ2) | Bảng A.6 mean ± std | D4 + bước 19 |

---

## 6. Ước tính chi phí

**Cơ sở:** số đo thật của bước 15 giai đoạn B (78 lượt, `gpt-4o-mini`, bảng giá `config/pricing.yaml`, tỷ giá 25.400): **28,2 VND/lượt** cho cấu hình full và **29,3 VND/lượt** cho baseline (~6.400 token/lượt, 2,5–2,7 lần gọi LLM/lượt); bộ trích slot khó ~3 VND/cuộc. (Giai đoạn A, 26 lượt, ra 32–40 VND/lượt — lấy mức B vì mẫu lớn hơn; sai số vài chục %.) Các con số dưới đây là **ước tính**, không phải cam kết.

| Hạng mục | Tính toán | Ước tính |
|---|---|---:|
| **Sinh lời thoại bằng LLM** (D3) | 104 cuộc mới × ~8 VND (≈1,2k token vào + 250 token ra) = ~0,8k; thêm lời agent cho 48 cuộc audio ~0,2k; **hệ số thử lại/sinh lại ×2,5** | **~2,5–5 nghìn VND** (~0,1–0,2 USD) |
| TTS (edge-tts/gTTS) | miễn phí (kênh không chính thức) | 0 |
| ASR (faster-whisper local) | chạy máy bạn / Colab miễn phí | 0 (tốn thời gian máy) |
| Ghi âm vùng miền (phương án a) | thành viên nhóm | 0 tiền; ~2 giờ người |
| TTS vùng miền trả phí (phương án b) | **chưa có bảng giá — cần kiểm tra** | chưa biết |
| **Chạy đánh giá trên bộ mới** (bước 15 GĐ2): 135 cuộc × ~3,25 lượt = ~440 lượt | full 440 × 28 + baseline 440 × 29 ≈ **25 nghìn VND / 1 seed**; 3 seed ≈ **75 nghìn VND** (~3 USD) | **25–75 nghìn VND** |
| Duyệt tay 15% | ~13 kịch bản | ~3–4 giờ người |

**Cập nhật 2026-10-24:** với `gpt-6-luna` đã chọn, 10 mẫu (17 cuộc) tốn 999,7 VND kể cả sinh lại (~59 VND/cuộc) → 87 cuộc ≈ 3,4–5,1 nghìn VND (ngoại suy, chưa đo); **người dùng đặt trần cứng 10.000 VND cho sinh dữ liệu (§ 9), thực thi bằng mã, sinh từng lô 10 khung.**

**Tổng tiền API cho dataset (không tính đánh giá): ~2,5–5 nghìn VND.** Tổng gồm cả bước 15 GĐ2 trên bộ mới: **~30–80 nghìn VND**. *Lưu ý:* ước tính trước đây của PLAN cho bước 15 GĐ2 (~15 nghìn VND) tính cho 22 kịch bản; với 86 kịch bản và prompt dài hơn thực tế, con số đúng là bảng trên. Bước sinh dữ liệu sẽ có **trần chi phí cứng** (`--max-cost-vnd`) như đã làm cho `run_eval.py`.

---

## 7. Cách kiểm tra đạt ngưỡng (tự động)

`python scripts/validate_scenarios.py --report` (D1) in bảng: số cuộc, số khách đa phiên / ≥ 3 phiên / đa kênh, số kịch bản đa phiên, số ca khó theo 4 loại, số file audio + tổng thời lượng + số file WER, rồi **so với ngưỡng M1 và in ✔/✗ từng dòng**. Số liệu trong PLAN.md § 6 sẽ được thay bằng đầu ra của lệnh này.

---

## 8. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Hội thoại LLM sinh quá lịch sự/đều | persona + teencode/không dấu + lỗi ASR cài sẵn; duyệt tay 15% |
| Đáp án sai do LLM | đáp án do code tính từ `mock_tools`; validator kiểm "có căn cứ trong lời khách" |
| Học vẹt bộ test | tách dev (60%) / held-out (40%); held-out chỉ chạy khi chốt |
| TTS đơn điệu, 1 giọng vùng | quyết định ở mục 9; ghi rõ hạn chế nếu không giải quyết |
| `edge-tts` là kênh không chính thức, có thể đổi/đứt | `gTTS` dự phòng; sinh audio một lần rồi lưu |
| Vượt chi phí | trần chi phí cứng, chạy thử nhỏ trước (như bước 15) |
| Audio quá ngắn → thiếu 1 giờ | kịch bản audio dài ~85 giây/cuộc, cả hai phía; đo tổng thời lượng bằng `manifest.json` trước khi chốt |

---

## 9. Quyết định của người dùng (2026-10-24)

1. **Cơ cấu: CHẤP NHẬN** 86 kịch bản / 135 cuộc (37 khách đa phiên, 12 khách ≥ 3 phiên, 15 đa kênh, 27 ca khó). **Điều kiện:** (i) thêm ≥ 2 khung "thông tin mâu thuẫn với phiên trước" và dùng persona `khach_da_kenh_mau_thuan`; (ii) thêm các khung tái hiện lỗi demo: trả giá/mặc cả, từ chối hoặc hoãn giữa gate, hết hàng biến thể, khách tự nhận khách cũ khi chưa có SĐT, số nói bằng chữ — **giữ tổng 86** (cách nhét: § 9.1, **đã duyệt và đã viết mã**).
2. **Giọng vùng miền: (a)** nhóm tự thu **≥ 10 file Nam/Trung**, làm **SAU CÙNG khi văn bản đã chốt**. Người ghi: **Nam = Đại, Trung = Hậu**; **có giấy đồng ý của người đọc** (`consent.csv`, § 3). Dự phòng (c): nêu hạn chế trong báo cáo. **Chưa chọn (b).**
3. **Duyệt tay 15%:** người dùng duyệt chính, **Kiệt đối chiếu 3–4 kịch bản**. Ưu tiên ca khó, đa kênh, ca validator gắn lỗi. Giữ dev 60% / held-out 40%; held-out chỉ chạy khi chốt. Checklist: [DATASET_REVIEW_CHECKLIST.md](DATASET_REVIEW_CHECKLIST.md).
4. **Model sinh lời thoại: `gpt-6-luna`.** Người dùng tự đối chiếu giá với OpenAI và báo lại (giá trong `config/pricing.yaml` vẫn là giá tạm OpenRouter). Kappa với người trên 20 mẫu; nếu thấp thì đổi judge.
5. **Ngân sách:** **trần cứng 10.000 VND cho sinh dữ liệu, thực thi BẰNG CODE** (dừng khi chạm trần), sinh **từng lô 10 khung**. Đánh giá: **1 seed (~25 nghìn VND) chỉ chạy SAU** cụm sửa lỗi demo và `mcp-memory`; **3 seed** khi dataset và MCP đã chốt.

**Điều kiện bắt đầu sinh (cổng):** chưa sinh dữ liệu cho tới khi người dùng duyệt (a) cụm sửa lỗi demo và (b) 10 khung đầu.

### 9.1. Đổi khung để thêm 2 loại yêu cầu mà vẫn đúng 86 (ĐÃ DUYỆT 2026-10-24; mã + test xong, CHƯA sinh lời thoại)

Nguyên tắc: **đổi nội dung 12 trong 54 khung, không thêm khung** → nhóm vẫn A 13 / B 10 / C 31, vẫn 87 cuộc mới, vẫn 135 cuộc; giữ nguyên các ràng buộc cũ (4 ca vượt ngân sách, 3 khách cũ có địa chỉ, 3 COD). Chỉ đổi những khung "không có ca khó" và trùng lặp (simple_buy 7 → 1, teencode 3 → 1, inquiry_only 3 → 1).

| Khung | Hiện tại | Đổi thành | Nhãn `hard_case` | Kiểm tra chính |
|---|---|---|---|---|
| SC-D03 (A, chat_fanpage → hotline) | adv, khach_so_gia | **mâu thuẫn phiên trước, loại giá/KM khác nhau giữa kênh**; persona `khach_da_kenh_mau_thuan` | `mau_thuan_phien_truoc` | khách đòi giá thấp nhất từng được báo ở kênh khác; agent nêu giá hiện hành + lý do KM theo ngày, không hứa giá cũ |
| SC-D04 (A, zalo_oa → hotline) | adv, do_du_hoi_nguoi_nha | **mâu thuẫn phiên trước, loại khách nói khác thông tin đã lưu** (ngân sách/diện tích); persona `khach_da_kenh_mau_thuan` | `mau_thuan_phien_truoc` | fact cũ bị `superseded`, không hỏi lại slot còn đúng |
| SC-D25 (C, fanpage) | simple_buy | **mặc cả** (nồi chiên) | `mac_ca` | không đơn tạo ở giá khách đề nghị; nói giá thật |
| SC-D30 (C, zalo) | simple_buy, so_gia | **mặc cả** (máy lọc nước) | `mac_ca` | như trên |
| SC-D26 (C, zalo) | simple_buy | **từ chối sau khi nghe đọc lại đơn** (giày) | `tu_choi_giua_gate` | 0 `order.create`; không nối câu hỏi gate ở lượt sau |
| SC-D28 (C, fanpage) | simple_buy, do_du | **hoãn giữa gate** ("để hỏi nhà đã") (mẹ & bé) | `hoan_giua_gate` | hủy đơn nháp; ghi `blocker`; hẹn gọi lại |
| SC-D24 (C, hotline) | simple_buy (quạt) | **biến thể CÒN hàng nhưng khách nói gọn "38 đen"** — RunLite 2 Pro size 38 đen (giày; *đổi ngành quạt → giày vì quạt không có biến thể trong catalog*) | `het_hang_bien_the` | tái hiện lỗi demo "báo hết hàng nhầm": agent phải nói còn hàng đúng biến thể, không hỏi lại size/màu |
| SC-D27 (C, hotline) | simple_buy | **hết hàng đúng biến thể** khách hỏi — áo phao Warmly size M đen HẾT, M be còn → khách nhận M be | `het_hang_bien_the` | báo đúng tình trạng, không xin địa chỉ khi hết, gợi ý biến thể còn hàng |
| SC-D47 (C, zalo) | teencode, da_kenh_fb_hotline | **tự nhận khách cũ khi chưa có SĐT** (nồi chiên) | `tu_nhan_khach_cu_chua_sdt` | agent hỏi SĐT/tài khoản đã dùng; không nối hồ sơ theo lời khai |
| SC-D48 (C, fanpage) | teencode, da_kenh_fb_hotline | như trên (mẹ & bé, miền Nam) | `tu_nhan_khach_cu_chua_sdt` | như trên |
| SC-D51 (C, zalo → **hotline**) | inquiry_only | **số nói bằng chữ** (SĐT + số tiền đọc bằng chữ) | `so_noi_bang_chu` | ITN đúng; Entity Accuracy |
| SC-D52 (C, hotline) | inquiry_only | như trên (ghi chú khác: đọc chậm, đọc lặp) | `so_noi_bang_chu` | như trên |

**Tổng ca khó sau khi đổi** (số hiện có lấy từ PLAN § 2 và đếm nhãn `hard_case` trong 22 kịch bản cũ + 10 mẫu + 54 khung):

| Loại | Cũ (22) | 10 mẫu | 54 khung (đã đổi) | Tổng | Ngưỡng |
|---|---:|---:|---:|---:|---|
| Đổi ý | 1 | 1 | 3 | **5** | ≥ 5 ✔ |
| **Mâu thuẫn phiên trước** | 0 | 1 | 3 + **2** | **6** | ≥ 5 ✔ |
| KM hết hạn | 2 | 1 | 3 | **6** | ≥ 5 ✔ |
| Hỏi ngoài tài liệu | 2 | 2 | 6 | **10** | ≥ 5 ✔ |
| **4 loại cộng lại** | | | | **27** | đúng đích 27 |
| Ngoài 4 loại — **tái hiện lỗi demo (mới, 10 khung)** | — | — | **10** | 10 | — |

Lưu ý: so với bảng § 2 (6/6/7/8), đổi ý và KM hết hạn kém 1, ngoài tài liệu dư 2 — vẫn đạt ngưỡng mỗi loại ≥ 5. "Đổi ý" tính cả SC-GEN-09 chưa gắn nhãn (cần gắn). Mất bớt khung teencode/mua đơn giản; teencode vẫn còn ở lời khách (25% lượt).

**Mã đã viết (2026-10-24; 0 VND, chưa gọi LLM, chưa sinh lời thoại):**
- `src/dataset/frames_extra.py`: 6 builder (`cross_conflict` cho D03/D04, `bargain`, `gate_decline`, `variant_oos`, `claims_returning`, `spoken_numbers`), đăng ký vào `frames54.PLAN`/`BUILDERS`; đáp án tính từ mock (`truth.py`) và `ProductRetriever`.
- `src/dataset/validate.py`: 6 nhãn `hard_case` mới trong luật S7 (`demo_hard_errors`), khớp CHÍNH XÁC từng nhãn (vì `het_hang_bien_the` chứa chuỗi con `het_han` của nhãn KM hết hạn); `distribution` gộp vào nhóm "tái hiện lỗi demo". `assemble.py`: kiểu `spoken` xuất `customer_turns_asr` (số/SĐT bằng chữ) + `input_mode=asr_transcript`.
- `scripts/generate_dataset_text.py`: `--set {sample10,frames54}`, `--batch N` (mặc định 10 khung CHƯA xong), `--dry-run` (in lô + trần còn lại, không gọi LLM). Lô mặc định = 10 khung chưa xong đầu tiên (SC-D01…D10); muốn lô đại diện thì dùng `--ids`.
- `src/dataset/budget.py`: **trần tích lũy 10.000 VND là hằng số trong mã**, tính trên sổ cái `dataset/reports/generation_runs.jsonl` (mọi lần chạy, kể cả khi đổi `--out`; hiện đã tiêu 1.470,4 VND → còn 8.529,6). `--max-cost-vnd` chỉ hạ được trần mỗi lần chạy; trừ biên 100 VND cho một lần gọi vì client chỉ kiểm trần TRƯỚC mỗi lần gọi; client đặt `set_hard_cap`; luôn ghi nốt sổ cái (`finally`) kể cả khi dừng giữa chừng. Hết trần → thoát mã 4 trước khi tạo LLM client.
- Test: `tests/test_dataset_extra_frames.py` (đúng 12 khung đổi, tổng 86/87 cuộc, tally ca khó, nhãn S7 dương/âm, ngân sách, chọn lô, dry-run, trần bị kẹp, sổ cái ghi nốt). Báo cáo `frames54_report.py` có thêm 2 ràng buộc mới.
- Chưa làm: luật lời thoại riêng (P-rule) cho các nhãn mới — hiện chỉ dùng P1–P5 sẵn có (P5 chỉ áp cho cuộc có `order.create`, nên cuộc từ chối/hoãn chưa có luật máy bắt lỗi "khách lỡ đồng ý"); cần xem 10 khung đầu rồi mới quyết định thêm.
