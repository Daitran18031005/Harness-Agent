# Điều tra lỗi sau lần đo m1_final5 (2026-11-13)

**Mã đang đo:** commit `73958d2` (nhánh `dialogs-va-do-tre`).

**Dữ liệu dùng:**
- Trace bản mới: `runs/m1_final5/cmp/{r1,r2,r3}/full.jsonl`.
- Trace bản trước: `runs/m1_final5/cmp/prev_final4_{r1,r2,r3}/full.jsonl`.
- Kịch bản: `runs/m1_final3/scen_all`.
- Chấm bằng `reference_eval.py` của BTC.

**Ký hiệu loại lỗi:**
- (a) lỗi mã
- (b) model biến thiên
- (c) đáp án kịch bản sai, hoặc dữ liệu kịch bản sai
- (d) cách chấm của BTC

Bước này **chưa sửa mã**.

---

## Nhóm 1: RQR tăng gấp đôi (xác nhận SĐT lần 2) (a)

**Số liệu.** Số câu hỏi thừa ở 3 lượt mới là 19, 17 và 12, trong đó câu "xác nhận SĐT" chiếm 14, 12 và 9. Ở 3 lượt bản trước con số là 7, 9 và 7 (câu SĐT: 6, 6, 6). Các ca mới bị: `TEST-141`, `150`, `159`, `192`, `195`, `209`, `54`, `91`, `97` (cùng cuộc `call_2`, lượt 2).

**Ví dụ.** `TEST-141/call_2`
- **Lượt 1:** khách nói "nay Hùng gọi chốt nha". Ở bản mới, code mở đơn nháp ngay lượt này. Gate hỏi "xác nhận lại: số điện thoại …, đúng không ạ? Mình cho em xin địa chỉ…".
- **Lượt 2:** khách đọc địa chỉ, tên và COD, nhưng không nói gì về SĐT. Gate hỏi lại y nguyên "Dạ em xin xác nhận lại: số điện thoại …, đúng không ạ?", và câu này bị tính là câu hỏi thừa.
- **Bản trước:** đơn nháp chỉ mở ở lượt 2, nên câu xác nhận chỉ xuất hiện một lần.

**Nguyên nhân.**
- Ở `src/harness/order_gate.py:214-220`, khi khách trả lời lượt có câu xác nhận mà không "đồng ý chung" (`lenient_consent`) và không nêu riêng mục đó (`affirmed`), mục đó không được ghi là đã xác nhận. `pending_confirm` bị xoá.
- Lượt sau, ở `order_gate.py:290`, SĐT vẫn là `known`, chưa `confirmed`, nên `to_confirm` lại có `recipient_phone`. Dòng `order_gate.py:386-401` dựng lại đúng câu cũ.
- RQR tăng vì code mở đơn nháp sớm hơn một lượt: sửa `reading.qty` / `_named_in_call` ở commit `73958d2` giúp `_maybe_open_gate` nhận ra sản phẩm ngay lượt 1, nên câu xác nhận rơi vào lượt 1 rồi bị lặp ở lượt 2. Bản thân lỗi "hỏi lại" thì đã có từ trước (6 ca ở bản trước).

**Cách sửa đề xuất.**
- Gate ghi các mục đã hỏi xác nhận trong cuộc (`confirm_asked`). Không bao giờ hỏi xác nhận cùng một mục lần 2.
- Khách đã nghe câu xác nhận mà trả lời bằng thông tin khác, không phản đối (bộ đọc không trả `declines`, không có SĐT mới) thì coi mục đó là `confirmed`. Câu đọc lại đơn cuối cùng vẫn đọc SĐT, nên khách vẫn có cơ hội sửa.
- **Test:** tái hiện `TEST-141/call_2`, gồm lượt 1 có câu xác nhận và lượt 2 khách đọc địa chỉ.

## Nhóm 2: câu hỏi mở "sản phẩm nào" ở cuộc gọi lại

| Ca | Chuyện gì xảy ra | Loại |
|---|---|---|
| `SC-TV-11/call_2` lượt 2 | Khách: "hơi mắc nên thôi nha". LLM gọi `product.shortlist` (ngân sách 600k) và nhận `no_basis`. Code thay lời bằng câu mẫu trong `_no_basis_reply`, kết thúc bằng "đang cần loại sản phẩm nào để em tư vấn đúng hơn ạ?", dù `brief.product_advised` đã có. | (a) `src/harness/orchestrator.py:1868-1883` |
| `SC-TV-13/call_2` lượt 1, 2; `call_3` lượt 1 | LLM tự hỏi "Chị muốn đặt sản phẩm nào trong hai lựa chọn này" (máy S1 hay combo), và "Chị có muốn tham khảo sản phẩm nào khác không" sau khi khách từ chối. | (b) |

**Cách sửa đề xuất.**
- **(a)** Ở `_no_basis_reply`: khi cuộc gọi đã có sản phẩm (`brief.product_advised` hoặc sản phẩm đã tra trong cuộc), không gắn câu hỏi "loại sản phẩm nào". Chỉ liệt kê giá, hoặc trả về `None` để giữ lời LLM.
- **Test:** `_no_basis_reply` với brief có `product_advised` thì câu trả lời không còn "sản phẩm nào".
- **(b)** Không sửa mã.

## Nhóm 3: 10 cuộc trượt cả 3 lượt vì không có `order.create` khớp

| Ca | Nguyên nhân (đọc trace) | Loại | Chỗ trong mã / dữ liệu |
|---|---|---|---|
| `TEST-130`, `TEST-157`, `TEST-196`, `TEST-58` | Kịch bản `input_mode=chat_teencode`, nên runner gửi `customer_turns_asr`. Bản ASR **bỏ mất câu đọc SĐT** có trong `customer_turns` (ví dụ `TEST-157`: "Số di động nhận hàng của Sơn là 0911243394"). Khách chat không có số gọi đến, nên gate hỏi SĐT, và lượt chốt không tạo được đơn. | (c) | `BTC-Data-Vong1-TEAMS/test_set/team_eval/TEST-{130,157,196,58}.json`, trường `customer_turns_asr` |
| `TEST-179/call_1` | Khách nói "Warmly bản L **be**". LLM báo giá `SKU-JK-DWN-L-DEN`. Code đã tra đúng `inventory.check SKU-JK-DWN-L-BE`, nhưng đơn nháp vẫn giữ SKU của LLM (L-DEN), nên tạo đơn sai màu. | (a) | `_maybe_open_gate` / `_gate_order_create`: biến thể code tra theo lời khách (`_check_named_variants`) không thắng biến thể LLM điền |
| `TEST-148` | Lượt 1 khách nói "size 40 màu trắng", và LLM tra đúng `SKU-SN-TRK-40-TRANG`. Lượt 3 LLM báo giá bằng SKU cha `SKU-SN-TRK`, nên đơn nháp mở bằng SKU cha. Gate hỏi size/màu ("Mình vẫn lấy màu trắng đúng không ạ?"), và lượt chốt dừng vì thiếu `item`. | (a) | Biến thể khách đã nói ở lượt trước trong cuộc không được dùng cho đơn nháp (`_driver_merge` / `_gate_order_create`) |
| `TEST-44` | Khách: "ok lên đơn **combo đó**". Code mở đơn bằng `SKU-AP-Y` (báo giá gần nhất), không phải `SKU-BDL-AIR`. `_named_in_call` chỉ khớp **tên đầy đủ** ("Combo AirPure Y + 2 màng lọc"), mà khách nói "combo đó". | (a) | `orchestrator.py:1274-1292` (`_simple_product_in_play`), `_named_in_call` |
| `TEST-49` | Lượt 1 đơn nháp mở với 2 máy. Lượt 2 khách "giảm xuống lấy 1 chiếc trả COD", và đơn nháp bị huỷ: không còn quyết định gate nào ở lượt 2, 3. Lượt 3 khách cho địa chỉ và tên nhưng không có đơn nháp, không có lượt chốt. Khả năng cao bộ đọc trả `declines` cho câu "ngại chuyển khoản lắm, giảm xuống…". Trace không lưu `reply_reading` nên chưa xác minh 100 %. | (a) | `order_gate.py:207-213`: mọi `declines` đều huỷ đơn nháp, kể cả khi khách chỉ đổi số lượng hoặc cách trả tiền |
| `TEST-67` r1 | LLM gọi `pricing.quote_order` với SKU thiếu tiền tố (`"AP-Y"`, `"XM-4L"`). Phần sửa A3 tìm tên khớp, thấy 2 sản phẩm nên không chọn được, và chặn bằng `unknown_product`. Agent hỏi lại tên sản phẩm, dù khách đã nói rõ cả hai. | (a) | A3 ở `_gate_order_create` (`orchestrator.py:1068`…) |
| `TEST-67` r2, r3 | Đơn đúng (2 dòng, 1.495.000đ), nhưng câu đọc lại không nêu "AIR-2ND-50" / "50%", nên thiếu `must_say_any`. | (a) | `order_gate.py` `_readback` và câu `allow_closing`: không đọc mã KM đã áp |
| `TEST-151` | Đạt cả 3 lượt ở m1_final5 (danh sách nhóm 3 lấy từ lần đo cũ). | — | — |

**Cách sửa đề xuất.**
- **TEST-179, TEST-148:** khi đơn nháp là SKU cha hoặc biến thể khác, mà trong cuộc khách đã nói một biến thể và code đã tra đúng biến thể đó (`_check_named_variants` trên **mọi** lời khách của cuộc), thì dùng biến thể ấy cho đơn nháp.
- **TEST-44 (theo LLM-first):** bộ đọc trả thêm `product`, là tên một sản phẩm **trong danh sách sản phẩm đã tra của cuộc** mà khách đang chốt, kèm trích dẫn nguyên văn (ví dụ "combo đó"). Code chỉ nhận tên nằm trong danh sách đó. Không đoán bằng regex.
- **TEST-49:** bộ đọc phân biệt "không mua nữa" với "đổi số lượng / đổi cách trả". Nếu `reading.qty` hoặc `payment` có giá trị thì không huỷ đơn nháp mà cập nhật.
- **TEST-67 r1:** trước khi tìm theo tên, thử `SKU-` + mã nếu mã đó có trong danh mục.
- **TEST-67 r2/r3:** câu đọc lại nêu mã KM đã áp trong `price_basket` (ví dụ "áp mã AIR-2ND-50 giảm 50% máy thứ hai").
- **(c) 4 ca chat:** đề xuất thêm câu SĐT vào `customer_turns_asr` dạng teencode (ví dụ "sdt nhan hang cua son la 0911243394"). Bằng chứng: `customer_turns` và `facts_established.phone_provided` đều có số này, chỉ bản ASR thiếu. **Chờ bạn đồng ý.**

## Nhóm 4: 11 cuộc thiếu câu bắt buộc

| Ca | Nguyên nhân | Loại | Đề xuất |
|---|---|---|---|
| `SC-GEN-14`, `TEST-11` (ngừng bán) | Khách hỏi "AirPure X **bản 2024**". Danh mục có `SKU-AP-X-2024` "— NGỪNG BÁN", nhưng `catalog.search` của mock **ẩn hàng ngừng bán** khi tìm theo từ khoá (`mock_tools.py:73`, `include_discontinued=False`). LLM chỉ thấy `SKU-AP-X` nên nói "vẫn còn bán". | (a) | Khi code hoặc LLM tìm theo tên sản phẩm, gọi kèm `include_discontinued=True`. Kết quả có hàng ngừng bán thì đưa vào prompt cờ "ngừng bán, thay bằng `successor_sku`". |
| `TEST-111/call_2`, `TEST-179/call_2`, `TEST-211/call_2` (quá hạn 7 ngày) | Khách: "nhận 12 hôm rồi… đổi cỡ được không". LLM gọi `order.update exchange_size` luôn và nói "đổi được" (`TEST-211`: "trong vòng 30 ngày"). Mock `order_update` **không kiểm hạn đổi trả**, và code cũng không. | (a) | Code chặn `order.update` (đổi/trả) khi ngày gọi − ngày giao > `return_days` của sản phẩm. Ngày giao lấy từ đơn (`estimated_delivery`) hoặc từ số ngày khách nói (bộ đọc, có trích dẫn). Khi chặn, trả lỗi `return_window_expired` kèm câu "đã quá hạn đổi trả 7 ngày (DT-01)". |
| `TEST-76`, `TEST-80` (freeship mẹ & bé ≥ 500.000) | `pricing.quote_order` của mock chỉ đặt `freeship` khi có `NAM-SHIP0` hoặc tổng ≥ 2 triệu. `MOM-FREESHIP` xét theo **từng chiếc** (490.000 < 500.000), nên tool trả "không freeship" cho đơn 980.000đ / 595.000đ. Đáp án đòi nói "500/freeship/MOM-FREESHIP". Agent đọc đúng dữ liệu tool. | (c) | Chính sách VC-02 nói đơn ≥ 500.000 ngành Mẹ & Bé được freeship, còn tool BTC thì không áp. Đề xuất hỏi BTC (cùng nhóm G1), hoặc đổi `must_say_any` của 2 kịch bản team_eval. **Chờ bạn quyết.** |
| `TEST-142` (phụ kiện tiêu hao) | Agent nói đúng ý: "không nằm trong phạm vi bảo hành… bộ phận hao mòn", nhưng không dùng chữ "tiêu hao / phụ kiện / không thuộc / BH-01". | (b) / (d) | Không sửa mã. |
| `TEST-08` (KM loại trừ size 43) | Tool trả lý do `exclude_variant_size`, và LLM nói nguyên mã đó: "không đủ điều kiện (exclude_variant_size)". Không nói "không áp dụng cho size 43". | (a) | Code dịch lý do `ineligible_promos` sang câu dễ hiểu, có giá trị cụ thể (ví dụ "mã RUN-10 không áp dụng cho size 43"), trước khi đưa kết quả tool cho LLM. Đồng thời không để mã nội bộ lọt ra lời agent. |
| `TEST-188` (nghỉ lễ) | Khách xin "9h sáng thứ Hai 26/10". LLM đặt `callback_at=2026-10-19` (sai tuần), nên mock không dời và không có câu "nghỉ / 27/10". | (b), có thể chặn bằng mã | Bộ đọc trích ngày giờ khách xin gọi lại (có trích dẫn). Code so với `callback_at` LLM truyền, lệch thì dùng ngày khách nói. |
| `SC-ULTRA-06/call_4` (đổi miễn phí) | `call_3` đã tạo phiếu đổi L→XL (phí 0). `call_4` khách chỉ hỏi lại phí, nhưng LLM gọi `order.update exchange_size` **lần 2**. Mock tính đổi lần 2 (60.000đ), nên agent báo "phí 60.000đ" (sai). Đúng ra phải là "miễn phí, đổi lần đầu, nguyên tem". | (a) | Code chặn `order.update` trùng (cùng `order_id`, `action`, `new_variant_sku`) đã thành công ở cuộc trước. Trả kết quả phiếu cũ thay vì tạo phiếu mới. |

## Nhóm 5: `TEST-21`, `TEST-71` chứa chữ "giá nhập" (a)

- Lời agent không có "giá nhập": guardrail D1 đã thay chữ này.
- Mẫu cấm `/giá\s*nhập/` khớp trong **`memory_writes`**: bộ trích bộ nhớ ghi `objection = "bớt cho anh sát giá nhập"` (`TEST-21` lượt 2) và `"bí mật kinh doanh không tiết lộ giá nhập"` (`TEST-71` lượt 3). `_blob` của BTC chấm cả `memory_writes`.
- **Chỗ:** `src/memory/memory_extractor.py` (trường `objection`, prompt ở dòng 199). `memory_writes` không qua guardrail.
- **Đề xuất:**
  - Áp cùng bộ lọc `COST_TERMS` của guardrail (`guardrail.py:40`, thay bằng "thông tin nội bộ") cho mọi giá trị trước khi ghi bộ nhớ.
  - **Test:** objection chứa "giá nhập" thì `memory_writes` không còn chữ đó.

## Nhóm 6: `TEST-153` thiếu sản phẩm trong `also_ordered` (a)

- Khách: "lấy một Máy lọc nước RO Karofi 9 lõi **kèm thêm một Bộ lõi lọc thay thế RO 1-2-3 (390.000đ)** trong một đơn".
- Không ai tra sản phẩm thứ hai: LLM chỉ gọi tool cho `SKU-WF-RO9`. `_basket_in_play` (`orchestrator.py:1388`) chỉ lấy sản phẩm từ `call_log`, nên đơn chỉ có 1 dòng, thiếu bộ lõi.
- **Đề xuất (LLM-first):**
  - Bộ đọc trả thêm danh sách món khách muốn trong đơn (`items`: tên kèm trích dẫn, số lượng).
  - Món nào chưa có trong `call_log` thì code gọi `catalog.search` theo đúng tên khách nói. Ra đúng 1 sản phẩm thì thêm dòng vào giỏ, ra 0 hoặc nhiều thì hỏi lại.
  - **Test:** giỏ có 2 dòng.

## Nhóm 7: các lỗi đã biết

**(a) "Tắt vòng nhắc" (`expect_tools=False`, `src/llm/client.py:429`; `orchestrator.py:644`).**
- Còn khoảng 40–47 lượt/lượt chạy có câu kiểu "em sẽ tiến hành tạo đơn / chuyển yêu cầu" mà không gọi tool ghi.
- Phần lớn là câu có điều kiện, đi kèm câu hỏi của gate ("Nếu đúng, em sẽ tiến hành tạo đơn ngay ạ"), không gây trượt.
- Ca gây trượt thật: `SC-TV-10/call_3` (trượt r1, r2). Khách hỏi giá sỉ B2B, LLM nói "em sẽ chuyển yêu cầu… bộ phận sỉ B2B" nhưng không gọi `handoff.transfer`. Bộ đọc không đặt `asks_transfer` vì khách không xin gặp người, nên đường C3 không chạy.
- **Loại:** (a), một phần (b).
- **Đề xuất:** khi lời LLM hứa chuyển (đã có `_PROMISES_LOOKUP`) mà chưa gọi `handoff.transfer`, chạy `authorize_handoff` trên lời khách. Căn cứ là `scope_safety` (ngoài phạm vi, ví dụ B2B) thì code gọi `handoff.transfer`; không được duyệt thì bỏ câu hứa.

**(b) `SC-TV-18`.** Khách đổi sang Xiaomi Smart 4 Pro. **Đã hết lỗi:** `call_3` đạt cả 3 lượt, đơn `SKU-XM-4P`, giá 4.666.500đ (nhờ `_named_in_call` ở commit `73958d2`).

---

## Tóm tắt

| Nhóm | Ca | Loại | Sửa |
|---|---|---|---|
| 1 RQR | Xác nhận SĐT lặp (`TEST-141` …) | (a) | Không hỏi xác nhận một mục 2 lần, khách không phản đối thì coi là đã xác nhận |
| 2 | `SC-TV-11` | (a) | `_no_basis_reply` bỏ câu "sản phẩm nào" khi đã biết sản phẩm |
| 2 | `SC-TV-13` | (b) | — |
| 3 | `TEST-130`, `157`, `196`, `58` | (c) | Thêm câu SĐT vào `customer_turns_asr` (chờ duyệt) |
| 3 | `TEST-179/c1`, `TEST-148` | (a) | Biến thể khách đã nói thắng biến thể LLM điền |
| 3 | `TEST-44` | (a) | Bộ đọc chọn sản phẩm khách chốt trong danh sách đã tra |
| 3 | `TEST-49` | (a) | Đổi số lượng hoặc cách trả không huỷ đơn nháp |
| 3 | `TEST-67` | (a) | Sửa SKU thiếu "SKU-", câu đọc lại nêu mã KM |
| 4 | `SC-GEN-14`, `TEST-11` | (a) | Tìm kèm hàng ngừng bán |
| 4 | `TEST-111`, `179`, `211` `/c2` | (a) | Chặn đổi/trả quá `return_days` |
| 4 | `TEST-76`, `TEST-80` | (c) | Tool BTC không áp `MOM-FREESHIP` cho đơn nhiều món: hỏi BTC hoặc sửa đáp án (chờ duyệt) |
| 4 | `TEST-142` | (b)/(d) | — |
| 4 | `TEST-08` | (a) | Dịch lý do KM không áp, không lộ mã nội bộ |
| 4 | `TEST-188` | (b) | Kiểm ngày gọi lại theo lời khách (có thể làm) |
| 4 | `SC-ULTRA-06/c4` | (a) | Chặn `order.update` trùng |
| 5 | `TEST-21`, `TEST-71` | (a) | Lọc `COST_TERMS` trong `memory_writes` |
| 6 | `TEST-153` | (a) | Bộ đọc trả danh sách món, code tra món chưa tra |
| 7a | `SC-TV-10/c3` | (a)/(b) | Hứa chuyển mà không gọi thì code kiểm và chuyển |
| 7b | `SC-TV-18` | — | Đã hết lỗi |

---

## Kết quả bước 3: sửa lỗi loại (a), kiểm chứng LLM thật ngày 2026-11-13

**Chi phí kiểm chứng:** 2.961 VND (trần 8.000). Ba lần chạy: `runs/fix_0113/full.jsonl` (24 kịch bản), `full2.jsonl` và `full3.jsonl` (chạy lại các ca sửa thêm). Cả bộ test 1022 xanh.

| Ca | Trước (m1_final5, 3 lượt) | Sau sửa | Sửa ở đâu |
|---|---|---|---|
| RQR trên 24 kịch bản | 23,3 % (r1) | **0 %** | `order_gate.py` `begin_turn`: không phản đối = đã xác nhận |
| `SC-GEN-14`, `TEST-11` | trượt 3/3 | **đạt** | `_discontinued_named`: nhận bản ngừng bán theo đủ các từ của tên. Không sửa `config/product_aliases.json` vì file này bị khoá luật ASR. |
| `TEST-08` | trượt 3/3 | **đạt** | `_explain_ineligible` |
| `TEST-111/c2`, `TEST-179/c2` | trượt 3/3 | **đạt** | `_return_window_expired` và `reply_reader.days_since_received` |
| `TEST-179/c1` | trượt 3/3 | **đạt** | `_resolve_variant_by_attributes` khớp nguyên từ ("m" trong "mua" từng thành size M) |
| `TEST-44` | trượt 3/3 | **đạt** | bộ đọc trả `product` (chọn trong danh sách sản phẩm đã nhắc) |
| `TEST-49` | trượt 3/3 | **đạt** | đổi số lượng/cách trả không huỷ đơn nháp |
| `TEST-67` | trượt 3/3 | **đạt** (lần chạy `full3`; lần `full` LLM vẫn báo giá lẻ) | SKU thiếu "SKU-", câu đọc lại nêu mã KM |
| `TEST-153` | trượt 3/3 | **đạt** | `_basket_in_play` ưu tiên báo giá cả giỏ; lượt chốt lấy giỏ mới nhất; bộ đọc trả `extra_items` |
| `TEST-21`, `TEST-71` | trượt 3/3 | **đạt** | `memory_extractor.validate_hard_slots` lọc `COST_TERMS` |
| `SC-TV-10/c3` | trượt 2/3 | **đạt** | lời hứa chuyển máy mà không gọi tool: chốt rồi code chuyển, hoặc bỏ lời hứa |
| `SC-TV-11/c2` | — | không còn hỏi "sản phẩm nào" | `_no_basis_reply` |
| `SC-TV-18/c3` | đạt 3/3 | hỏng ở lần chạy `full` (LLM không tra 4 Pro), **đạt lại** sau khi sửa | `_named_in_call` nhận tên khớp chính xác dù chưa tra |
| `SC-ULTRA-06/c4` | trượt 3/3 | vẫn trượt: không còn phí "đổi lần 2", nhưng agent nói "phụ thu 40.000đ" thay vì "miễn phí giao" (b) | chặn `order.update` trùng (lưu `exchange_ticket`) |

**Còn trượt:**
- `TEST-148`: nguyên nhân mới tìm ra (a). Khách chat chỉ đọc SĐT ở lượt 3, nên hệ thống nhận diện lại khách và **đổi `working_session_id` giữa cuộc** (`SESS-<id>-<ngày>`). Lời khách ở lượt 1 ("size 40 màu trắng"), `call_log` và trạng thái gate nằm ở phiên cũ. Muốn sửa phải chuyển trạng thái phiên khi danh tính đổi giữa cuộc gọi. Việc này đụng mọi bộ nhớ theo phiên và việc tách phiên đồng thời của API, nên **chưa làm, chờ bạn duyệt**.
- `TEST-211/c2`: LLM không gọi `order.update`, nói "30 ngày" (b).
- `TEST-188`: LLM đặt lịch sai tuần (b).
- `TEST-76`: đáp án sai (c), chờ bạn quyết.

### Bổ sung: `TEST-148` (phiên đổi giữa cuộc gọi)

- **Đã sửa.** `_carry_session` (orchestrator) nhớ phiên theo (liên hệ, ngày, cuộc). Khi khách chat đọc SĐT làm `customer_id` đổi giữa cuộc, toàn bộ trạng thái của cuộc được chuyển sang phiên mới: lời khách, tool đã chạy, đơn nháp, bảng token PII, hội thoại. Hai liên hệ khác nhau không bao giờ bị gộp.
- **Kiểm chứng:** `TEST-148` đạt (`runs/fix_0113/full4.jsonl`, `full5.jsonl`).
- **Hỏng mới phát hiện khi kiểm chứng:** ở `SC-TV-13/c3`, khách nói "một bộ Spectra S1" nhưng bộ đọc chọn combo, vì combo là tên duy nhất đã tra.
  - **Sửa:** tên khách gọi đúng thắng, bộ đọc chỉ dùng cho cách gọi tắt; prompt dặn trả null khi khách gọi sản phẩm ngoài danh sách. Sau đó ca này đạt lại.
- **Còn biến thiên:** `TEST-44` đạt 2 trên 3 lần chạy; lần trượt, bộ đọc không trả `product` (b).
- **Chi phí kiểm chứng thêm:** 1.167 VND. Tổng bước 3: 4.128 VND.
