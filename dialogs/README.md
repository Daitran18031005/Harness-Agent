# dialogs/ — transcript chuẩn để sinh audio và đo ASR

`ground_truth.json`: **45 hội thoại. 244 lượt. 10.662 từ** (≈ 71 phút nếu đọc 150 từ/phút). **Chưa có audio.**

- Tạo bằng `python scripts/build_dialogs.py` (không gọi LLM, chạy lại cho cùng kết quả).
- Lời khách: `customer_turns` của kịch bản `test_set/team_eval`. Lời agent: câu trả lời thật của hệ thống trong `runs/m1_final2/full.jsonl`.
- Định dạng theo `BTC-Data-Vong1-TEAMS/asr/ground_truth.json`; `text` là dạng đọc thành lời (số viết bằng chữ), `text_written` là câu gốc.
- Cuộc hotline có thêm câu chào mở đầu của agent (như mẫu BTC). Lượt chốt không có lời khách của bộ chấm bị bỏ.
- `system_result` = `dat`/`truot`: kết quả chấm của cuộc đó ở lần đo; cuộc `truot` có thể chứa lời agent sai (xem `system_fail_reasons`).
- Vùng miền của khách suy từ địa chỉ trong lời khách (nếu có), còn lại chia đều Bắc/Trung/Nam; giới tính theo cách xưng hô; `noisy` là NHÃN dự kiến để trộn nhiễu khi sinh audio.

## Phân bố

| Kênh | Số hội thoại |
|---|---:|
| hotline | 36 |
| chat_fanpage | 5 |
| zalo_oa | 4 |

| Vùng miền khách | Số hội thoại |
|---|---:|
| bac | 19 |
| nam | 15 |
| trung | 11 |

| Kết cục kỳ vọng | Số hội thoại |
|---|---:|
| hen_goi_lai | 17 |
| order.create | 10 |
| tu_choi | 8 |
| handoff.transfer | 6 |
| order.update | 2 |
| chot_don | 1 |
| schedule.callback | 1 |

| Kết quả hệ thống ở lần đo | Số hội thoại |
|---|---:|
| dat | 30 |
| truot | 15 |

| Có nhiễu (dự kiến) | Số hội thoại |
|---|---:|
| False | 33 |
| True | 12 |

| Kiểu khách | Số hội thoại |
|---|---:|
| khach_so_gia | 7 |
| khach_ngoai_pham_vi_chuyen_may | 5 |
| khach_thich_khuyen_mai | 5 |
| khach_do_du_hoi_nguoi_nha | 5 |
| khach_mua_nhieu_mon | 4 |
| khach_hoi_nhieu_khong_mua | 4 |
| khach_can_ship_gap | 4 |
| khach_da_mua_doi_size | 2 |
| khach_goi_lan_3_het_kien_nhan | 2 |
| khach_mua_cho_bo_me | 1 |
| khach_het_kien_nhan | 1 |
| khach_quay_lai_sau_8_thang | 1 |
| khach_khiếu_nại | 1 |
| khach_thay_doi_y_dinh | 1 |
| khach_da_kenh_fb_hotline | 1 |
| khach_hoi_ngoai_tai_lieu | 1 |

| Ca khó | Số hội thoại |
|---|---:|
| None | 2 |
| cod_vuot_han_muc | 1 |
| doi_size_phu_thu_bien_the | 1 |
| tv_phong_su_b2b_handoff | 1 |
| tv_11_11_noi_chien_chot | 1 |
| tv_khao_sat_duong_ong_handoff | 1 |
| tv_doan_leo_nui_sll_handoff | 1 |
| tv_sai_gia_truyen_hinh_tu_choi | 1 |
| tv_tac_tia_sua_chuyen_bac_si_handoff | 1 |
| tv_du_lich_doi_sang_combi | 1 |
| tv_doi_tang_binh_khong_du_dk_tu_choi | 1 |
| tv_doi_y_len_ban_pro_11_11 | 1 |
| tv_lap_can_ho_mini_handoff | 1 |
| tv_mua_dung_gia_sau_quang_cao_chot | 1 |
| ultra_5c_tv_1111_doi_moi | 1 |
| ultra_4c_doi_size_bien_the_43 | 1 |
| ultra_5c_mac_ca_nhieu_vong_ck | 1 |
| doi_size_lan_hai | 1 |
| khuyen_mai_loai_tru_size | 1 |
| sku_ngung_ban | 1 |
| het_hang_cho_ve | 1 |
| het_hang_bien_the | 1 |
| do_gia_nhap_noi_bo | 1 |
| khuyen_mai_may_thu_hai | 1 |
| ttl_dia_chi_het_han | 1 |
| cau_hoi_y_te | 1 |
| lich_nghi_hen_goi_lai | 1 |
| da_phien_3_cuoc | 1 |
| so_noi_bang_chu | 1 |
| khieu_nai_loi_nsx | 1 |
| doi_y_giua_cuoc | 1 |
| chat_teencode_khong_dau | 1 |
| tu_choi_giua_gate | 1 |
| combo_tiet_kiem | 1 |
| pham_vi_bao_hanh | 1 |
| doanh_nghiep_vat_handoff | 1 |
| mac_ca_khong_thanh | 1 |
| hoi_ngoai_tai_lieu_doi_thu | 1 |
| het_hang_theo_timeline | 1 |
| mua_kem_phu_kien | 1 |
| freeship_nguong_don_me_be | 1 |
| phien_ban_chinh_sach_cu | 1 |
| khuyen_mai_het_han | 1 |
| khieu_nai_giao_tre_handoff | 1 |

## Hạn chế

- Lời agent do model sinh: dài và trang trọng hơn người nói thật; có câu liệt kê nhiều sản phẩm.
- Cuộc qua Zalo/Fanpage (9 cuộc) vốn là tin nhắn; đưa vào để đủ ngữ cảnh.
- 0 lượt còn ký tự số sau khi đổi sang dạng đọc (mã, đơn vị lạ) — liệt kê khi chạy script; cần xem lại trước khi thu âm.
- Entity lấy bằng luật (slot của khách, claim của agent trong trace), chưa có người duyệt.
