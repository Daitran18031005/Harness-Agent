# Danh sách lỗi cần sửa (2026-11-12)

Gom từ lần đo 277 kịch bản (`runs/m1_final2`), lượt so sánh 40 kịch bản (`runs/ab/base`), và lần chấm bằng LLM riêng (`runs/ab/judge`).
Mỗi mục có: hiện tượng → ca tái hiện → chỗ cần sửa → cách kiểm. Làm theo thứ tự nhóm; trong mỗi nhóm làm từ trên xuống.

Quy ước chung cho người/agent sửa:

- Chạy test bằng `C:/Users/GIGA/anaconda3/envs/nlp_env/python.exe -m unittest discover -s tests` với `MCP_TRANSPORT=inproc MEMORY_TRANSPORT=local PYTHONIOENCODING=utf-8`. Hiện 990 test xanh; mỗi mục sửa hành vi phải thêm ít nhất một test.
- Hiểu lời khách bằng LLM kèm trích dẫn nguyên văn; không thêm regex để đoán ý khách.
- Không sửa file trong `BTC-Data-Vong1-TEAMS/` trừ `test_set/team_eval/` (dữ liệu của nhóm).
- Chạy LLM thật phải có trần chi phí được chủ dự án duyệt. Kiểm một mục bằng `run_eval.py --only <kịch bản> --config full --max-cost-vnd <trần nhỏ>`.
- Không dùng câu đệm để giảm TTFT (quyết định của chủ dự án).

---

## Nhóm A — Lượt chốt tạo đơn (ưu tiên cao nhất, sai hành vi)

### A1. Tạo đơn sau khi cuộc gọi đã chuyển máy
- **Hiện tượng:** kịch bản yêu cầu chuyển máy, agent đã gọi `handoff.transfer`, nhưng lượt chốt vẫn tạo thêm một đơn.
- **Ca:** `SC-TV-03/call_3` trong `runs/ab/base/full.jsonl`.
- **Sửa:** `HarnessOrchestrator.has_open_order` và `_closing_driver` (`src/harness/orchestrator.py`) trả "không có đơn chờ" khi nhật ký cuộc gọi (`self._call_log[sid]`) có `handoff.transfer` thành công (kết quả có `ticket_id`). Khi chuyển máy thành công cũng nên xóa `self._gate_retry_args[sid]`.
- **Kiểm:** test đơn vị: mở đơn nháp → chuyển máy → `has_open_order` là False. Chạy lại `SC-TV-03`: không còn `order.create` ở cuộc 3.

### A2. Câu đọc lại ở lượt chốt thiếu thông tin dù hệ thống đã có
- **Hiện tượng:** câu đọc lại chỉ có "sản phẩm, tổng tiền, thanh toán". 12/23 đơn tạo ở lượt chốt có đủ địa chỉ nhưng không được đọc ra; không đơn nào có ngày giao. Tiêu chí J07 của BTC (PB-09) đòi: sản phẩm đúng biến thể, giá cuối, địa chỉ, thanh toán, thời gian giao → 0/20 đạt.
- **Ca:** `SC-GEN-05/call_1`, `SC-TV-01/call_3`, `TEST-01/call_2` (có địa chỉ mà không đọc).
- **Sửa:**
  1. `OrderGate.evaluate`, nhánh `st.closing` (`src/harness/order_gate.py`): thay câu `say` rút gọn bằng câu dựng từ ĐỦ các trường đang có (`fields`): sản phẩm + biến thể, giá một sản phẩm (nếu không phải giỏ lẫn giá), tổng, người nhận, số điện thoại, địa chỉ, thanh toán. Dùng lại `_readback` nhưng bỏ câu hỏi "xác nhận đặt đơn này giúp em nhé?" (không còn ai trả lời). Trường nào thiếu thì nói rõ là thiếu và nhân viên sẽ gọi lại (đang làm đúng, giữ nguyên).
  2. `_driver_create` / `_closing_driver` (`orchestrator.py`): sau khi `order.create` trả `estimated_delivery`, câu trả lời đã có "dự kiến giao ngày dd/mm" — kiểm nó còn nguyên khi ghép với câu đọc lại.
- **Kiểm:** sửa `tests/test_closing_turn.py::test_open_draft_is_created_with_cod_default` để khẳng định câu trả lời chứa địa chỉ (khi có) và ngày giao. Chấm lại J07 trên các ca trên.

### A3. Đọc lại đơn bằng mã thô, không có tổng tiền
- **Hiện tượng:** câu đọc lại là "1 SPECTRA-S1; thanh toán khi nhận hàng (COD)", đơn không được tạo.
- **Ca:** `SC-TV-13/call_3`.
- **Sửa:** mã "SPECTRA-S1" không phải SKU thật (SKU đúng là `SKU-MB-PUMP1`), tức LLM đưa tên/mã tự đặt vào `order.create` và `price_basket` trả lỗi. Trong `_gate_order_create`: khi `price_basket` trả `{"error": ...}` thì không được đi tiếp tới đọc lại; thử `_canonical_sku` / `_repair_unknown_sku` trước, không sửa được thì chặn bằng `_gate_block` với câu hỏi lại sản phẩm. Ở lượt chốt: không tạo, nói rõ chưa xác định được sản phẩm.
- **Kiểm:** test đơn vị với `order.create(sku="SPECTRA-S1")`: không có câu đọc lại chứa mã thô, không tạo đơn.

---

## Nhóm B — Địa chỉ

### B1. Không nhận ra địa chỉ khi câu thiếu chữ "số/đường/quận"
- **Hiện tượng:** khách nói "giao 14 Trần Phú, Hà Đông, COD nhé" nhưng đơn không có địa chỉ.
- **Ca:** `SC-ULTRA-14/call_2`; tương tự `TEST-130/call_1` (lời khách không dấu: "gui ve so 129 khu nam viet a ngu hanh son da nang").
- **Sửa (LLM-first):** thêm vào bộ đọc hiểu (`src/harness/reply_reader.py`, `PROMPT` + `verify`) hai khóa `address` và `address_quote` (trích nguyên văn, có kiểm chứng như các khóa khác). Trong `_driver_merge` (`orchestrator.py`): khi lời khách không có token `<ADDR_n>` mà bộ đọc trả `address` đã kiểm chứng thì đăng ký địa chỉ đó vào `PiiVault` và dùng token mới. Không nới regex trong `pii_vault.py`.
- **Kiểm:** test `verify()` với hai câu trên; chạy lại hai kịch bản.

### B2. Khách nói "giao về địa chỉ cũ" nhưng bộ nhớ không có địa chỉ
- **Hiện tượng:** agent hỏi "cho em xin địa chỉ nhận hàng" như thể khách chưa nói gì; ở lượt chốt thì tạo đơn không địa chỉ.
- **Ca:** `SAMPLE-01/call_2`.
- **Sửa:** không bịa địa chỉ. Câu của gate nên nói thẳng: "Em chưa có địa chỉ đã lưu của mình, mình cho em xin địa chỉ nhận hàng ạ". Cần bộ đọc hiểu báo khách đang tham chiếu địa chỉ cũ (thêm giá trị vào khóa `affirmed`: `"address"` đã có sẵn — dùng nó khi `known.address` rỗng).
- **Kiểm:** test gate: `affirmed=["address"]` + không có địa chỉ đã lưu → câu hỏi nêu rõ chưa có địa chỉ cũ.

### B3. Tám kịch bản không có địa chỉ ở đâu cả
- **Ca:** `SAMPLE-02, 03, 04, 05`, `SC-GEN-06/call_2`, `SC-TV-08/call_3`, `SC-TV-20/call_3`.
- **Không sửa bằng code.** Bộ chấm tự động đòi `order.create`, tiêu chí J07 đòi đọc địa chỉ. Chủ dự án hỏi BTC; giữ hành vi hiện tại (tạo đơn, báo nhân viên gọi lại) cho tới khi có trả lời.

---

## Nhóm C — Chuyển máy

### C1. Phiếu chuyển máy ghi tên khách là "Quý khách"
- **Ca:** `SC-TV-10/call_3`.
- **Sửa:** `_complete_handoff_brief` (`orchestrator.py`): coi `customer_name` là "thiếu" khi bằng "Quý khách"/rỗng, lấy tên khách đã nêu trong cuộc (`brief.customer_name` sau khi `extract_easy_slots` cập nhật, hoặc fact `customer_name` trong hồ sơ).
- **Kiểm:** test đơn vị cho hàm.

### C2. Phiếu chuyển máy ghi sai sản phẩm
- **Ca:** `SC-TV-07/call_3` (phiếu ghi `SKU-MB-STR1`, cuộc gọi nói về sản phẩm khác).
- **Sửa:** kiểm thứ tự ưu tiên của `focus_sku` trong lời gọi `_complete_handoff_brief`: hiện là `_focus()` rồi tới `product_mentions(...)` trên TOÀN BỘ lời khách của cuộc — sản phẩm nhắc đầu tiên thắng. Đổi thành sản phẩm được nhắc/tra GẦN NHẤT. Nếu LLM tự điền `product_advised` khác sản phẩm đang bàn thì giá trị của code thắng.
- **Kiểm:** test với cuộc gọi nhắc hai sản phẩm; chạy lại `SC-TV-07`.

### C3. Không chuyển máy khi kịch bản yêu cầu
- **Ca:** `SC-ULTRA-09/call_3`, `SC-ULTRA-02/call_5`.
- **Sửa:** đọc trace trước. Xem `authorize_handoff` (`reply_reader.py`) có từ chối không (`handoff_blocked`) hay LLM không gọi tool. Chưa có kết luận nguyên nhân.

### C4. Chuyển máy thừa
- **Ca:** `SC-ULTRA-01/call_4`, `SC-ULTRA-04/call_4`, `SC-ULTRA-10/call_4`, `SC-ULTRA-12/call_3`, `TEST-208/call_2` (3 ca cuối baseline cũng dính).
- **Sửa:** đọc trace từng ca; chưa có kết luận nguyên nhân.

---

## Nhóm D — Guardrail và câu bắt buộc

### D1. Lặp lại chữ nhạy cảm của khách khi từ chối
- **Hiện tượng:** agent từ chối đúng nhưng nói "em không thể tiết lộ giá nhập" → trace dính mẫu cấm `giá nhập`, `giá sàn`, `biên lợi nhuận`.
- **Ca:** `TEST-135`, `TEST-154`, `TEST-21`, `TEST-71`.
- **Sửa:** tầng đầu ra (`src/harness/guardrail.py`): khi lời agent chứa các cụm trong danh sách thuật ngữ nội bộ, thay cụm đó bằng "thông tin nội bộ". Đây là lọc lời AGENT (đầu ra), không phải đoán ý khách. Thêm một dòng trong system prompt: khi từ chối không nhắc lại tên loại thông tin nội bộ.
- **Kiểm:** test guardrail; chạy lại `TEST-135`.

### D2. Thiếu câu bắt buộc
| Nội dung phải nói | Ca | Hướng xem |
|---|---|---|
| Quá hạn đổi trả 7 ngày | `TEST-111/call_2`, `TEST-179/call_2`, `TEST-211/call_2` | agent có tra chính sách không; router có chọn đúng bản hiện hành |
| Sản phẩm ngừng bán | `SC-GEN-14/call_1`, `TEST-11`, `TEST-12` (còn nói "còn hàng") | `catalog.search` trả `discontinued`/`successor_sku`; guardrail tồn kho |
| Phụ kiện tiêu hao không thuộc bảo hành | `TEST-142`, `TEST-81`, `TEST-217` | tra chính sách bảo hành |
| Ngưỡng 500.000đ của MOM-FREESHIP | `TEST-76`, `TEST-80` | kết quả `ineligible_promos` có `reason: min_order` — agent không diễn giải |
| KM loại trừ size 43 | `TEST-08` | `ineligible_promos` / `exclude_variant_size` |

Chưa phân tích từng ca. Đọc trace trước, phân loại "lỗi hệ thống" hay "đáp án sai", rồi mới sửa.

---

## Nhóm E — Script chấm bằng LLM (`scripts/llm_judge.py`)

### E1. Xóa số điện thoại làm phiếu chuyển máy bị chấm "thiếu SĐT"
- **Sửa:** trong `scrub()`: thay giá trị số điện thoại bằng chuỗi `"<đã có SĐT>"` thay vì bỏ hẳn khóa.

### E2. Model chấm áp tiêu chí cho cuộc không liên quan
- **Hiện tượng:** 9/14 ca trượt J05 là cuộc không có chuyển máy; tương tự có thể xảy ra với J07, J12.
- **Sửa:** quyết định "có áp dụng không" bằng CODE trước khi hỏi LLM: J05 chỉ khi trace có `handoff.transfer` hoặc kịch bản kỳ vọng nó; J07 chỉ khi trace có `order.create` thành công; J01 chỉ khi `call != call_1`. Chỉ gửi các tiêu chí áp dụng; bỏ lựa chọn "NA".

### E3. Chấm lại
- Sau E1–E2 và sau khi sửa nhóm A: chấm lại trên trace mới. Xuất lại `manual_20.csv` cho người chấm tay (≥ 20 mẫu, tính Cohen's kappa bằng lệnh `agreement`).

### E4. Hai tiêu chí chưa xem
- "Không bịa số liệu" 38/60 và "Câu mở đầu tiếp nối" 11/30: chưa đối chiếu với trace. Làm sau E2; có thể lẫn lỗi chấm.

---

## Nhóm F — Độ trễ (TTFT p95 ≈ 6,6 s, Total p95 ≈ 8,0 s; ngưỡng 3 s / 8 s)

Số đo từng phần (40 kịch bản): đọc hiểu lời khách 1,1 s (p95 2,6 s) ở 68 % lượt có LLM; vòng gọi đầu 1,2 s (p95 2,2 s); token đầu của vòng cuối 0,8 s; 26 % lượt có LLM cần ≥ 3 vòng.

### F1. Bước đọc hiểu dùng model nhỏ hơn
- **Sửa:** cho `read_reply` một client riêng, model đặt qua biến môi trường (mặc định = model agent). Đo độ chính xác trước khi đổi mặc định.
- **Kiểm:** `scripts/eval_consent_guard.py` và `eval_gate_open.py` (cần bộ câu có nhãn) + lượt 40 kịch bản.

### F2. Vòng gọi bị lãng phí
- **Hiện tượng:** 34/239 lượt tốn 2 vòng mà trace không có tool nào: LLM gọi lại tool mà code đã tra sẵn, nhận kết quả từ bộ đệm, rồi mới trả lời.
- **Ca:** `SAMPLE-04/call_2` lượt 2, `SAMPLE-05/call_2` lượt 2.
- **Sửa:** xem prompt có nêu đủ rõ "số liệu hôm nay đã tra, dùng luôn" không; cân nhắc ẩn tool đọc khỏi danh sách tool ở lượt mà mọi dữ liệu cần đã nằm trong Call Brief.

### F3. Chạy song song bước đọc hiểu với vòng gọi đầu
- Rủi ro cao (đụng `process_turn`, order gate). Thiết kế: chạy LLM chính ở luồng phụ, tool chỉ được chạy sau khi bước đọc hiểu xong; nếu code quyết định tự xử lý lượt thì bỏ kết quả LLM. Chỉ làm khi F1–F2 chưa đủ và chủ dự án đồng ý.

### F4. Kiểm lại hai thay đổi đã làm
- "Gắn giá + tồn kho vào kết quả `catalog.search`": lượt đo lại không thấy lợi rõ (2,42 → 2,35 vòng; TTFT không giảm). CCR nhảy 59,6 → 77,5 % cần kiểm: có thể do lời gọi tool của code được tính vào, không phải agent nhớ tốt hơn. Quyết định giữ hay bỏ sau khi kiểm.
- Lưu ý sai số: hai lượt gần giống nhau lệch 5 điểm TSR và 0,4 s TTFT. Mọi kết luận về độ trễ cần ≥ 3 lượt chạy.

---

## Nhóm G — Dữ liệu

### G1. Đáp án giá của kịch bản "hỏi A rồi chuyển sang B"
- 25/26 claim giá bị tính sai là giá đúng của sản phẩm khác đáp án. Chờ BTC trả lời (`docs/BAO_CAO_HR_GUI_BTC.md`). Không tự sửa.

### G2. Hồ sơ một ô sản phẩm / một ô giá mỗi khách (D3 trong `CHECKING.md` § 10)
- Khách được giới thiệu nhiều sản phẩm thì chỉ nhớ cái cuối. Thay đổi lớn (bảng `product_interests`); không làm trước hạn nộp trừ khi chủ dự án yêu cầu.

### G3. Việc nhỏ
- `dialogs/ground_truth.json` hội thoại T31 lượt 2 còn "…mươik" (`src/dataset/spoken.py`, số 4 chữ số dính "k").
- `tests/test_pipeline_lifecycle.py::test_background_sweeper_finalizes_an_abandoned_call` thỉnh thoảng đỏ khi chạy cả bộ (phụ thuộc thời gian).
- 21 cuộc "không có `order.create` khớp đáp án" ở `runs/m1_final2/report.md` chưa phân loại. Một ca đã xem (`TEST-130`): khách chat không có SĐT nhận hàng → trùng B1.

---

## Sau khi sửa

1. Chạy lại lượt 40 kịch bản (`runs/ab_launch.sh` chỉ phần `base`, ≈ 7.000 VND) và `scripts/ab_report.py`.
2. Chấm lại bằng `scripts/llm_judge.py` (≈ 2.500 VND).
3. Khi ổn: đo lại cả bộ 277 kịch bản (≈ 63.000 VND, cần duyệt) và cập nhật `submission/`.
