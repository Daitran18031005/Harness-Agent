# Phân bố 54 khung kịch bản còn lại (chưa sinh lời thoại, 0 VND)

54 kịch bản · **87 cuộc gọi** (cộng 10 mẫu = 17 cuộc và 22 kịch bản hiện có = 31 cuộc → **135 cuộc**, đúng cơ cấu đã duyệt) · 23 khách đa phiên · 12 kịch bản đa kênh · 42 cuộc có tạo đơn (đều qua order gate) · 1 cuộc teencode.

## Ràng buộc bạn đặt ra

| ràng buộc | đạt? | chi tiết |
|---|---|---|
| ≥ 3 ca vượt ngân sách > 20% (nhánh HAI LỰA CHỌN) | ✔ | 4: SC-D31, SC-D32, SC-D33, SC-D34 |
| ≥ 2 khách cũ có sẵn địa chỉ (gate chỉ xác nhận) | ✔ | 3: SC-D11, SC-D12, SC-D13 |
| Tổng đúng cơ cấu 54 (A 13 + B 10 + C 31) | ✔ | {'A': 13, 'B': 10, 'C': 31} |
| Số cuộc gọi mới = 87 (+17 mẫu + 31 hiện có = 135) | ✔ | 87 |
| ≥ 2 khung mâu thuẫn phiên trước với persona khach_da_kenh_mau_thuan (duyệt 2026-10-24) | ✔ | 2: SC-D03, SC-D04 |
| Mỗi kiểu tái hiện lỗi demo có ≥ 1 khung (mặc cả · từ chối/hoãn giữa gate · hết hàng biến thể · tự nhận khách cũ chưa có SĐT · số nói bằng chữ) | ✔ | {'mac_ca': 2, 'tu_choi/hoan_giua_gate': 2, 'het_hang_bien_the': 2, 'tu_nhan_khach_cu_chua_sdt': 2, 'so_noi_bang_chu': 2} |

**Nhóm**

| giá trị | số kịch bản |
|---|---|
| C | 31 |
| A | 13 |
| B | 10 |
| *tổng* | *54* |

**Số cuộc gọi mỗi kịch bản**

| giá trị | số kịch bản |
|---|---|
| 1 | 31 |
| 2 | 13 |
| 3 | 10 |

**Persona (BTC `personas.json`)**

| giá trị | số kịch bản |
|---|---|
| khach_so_gia | 12 |
| khach_da_mua_doi_size | 7 |
| khach_goi_lan_3_het_kien_nhan | 7 |
| khach_hoi_nhieu_khong_mua | 6 |
| khach_do_du_hoi_nguoi_nha | 5 |
| khach_mua_nhieu_mon | 5 |
| khach_hoi_ngoai_tai_lieu | 4 |
| khach_da_kenh_fb_hotline | 3 |
| khach_da_kenh_mau_thuan | 2 |
| khach_ngoai_pham_vi_chuyen_may | 2 |
| khach_quay_lai_sau_8_thang | 1 |

**Loại ca khó (`hard_case`)**

| giá trị | số kịch bản |
|---|---|
| (không) | 18 |
| mau_thuan_phien_truoc | 5 |
| vuot_ngan_sach_2_lua_chon | 4 |
| cod_vuot_han_muc | 3 |
| doi_y_giua_cuoc | 3 |
| hoi_ngoai_tai_lieu_doi_thu | 3 |
| khuyen_mai_het_han | 3 |
| het_hang_bien_the | 2 |
| hoi_ngoai_tai_lieu_y_te | 2 |
| khieu_nai_loi_nsx | 2 |
| mac_ca | 2 |
| so_noi_bang_chu | 2 |
| tu_nhan_khach_cu_chua_sdt | 2 |
| hoan_giua_gate | 1 |
| hoi_ngoai_tai_lieu_chinh_sach | 1 |
| tu_choi_giua_gate | 1 |

**Kênh — tính theo CUỘC gọi**

| giá trị | số kịch bản |
|---|---|
| hotline | 61 |
| chat_fanpage | 13 |
| zalo_oa | 13 |

**Kênh của cuộc ĐẦU TIÊN**

| giá trị | số kịch bản |
|---|---|
| hotline | 33 |
| chat_fanpage | 11 |
| zalo_oa | 10 |

**Ngành hàng**

| giá trị | số kịch bản |
|---|---|
| máy lọc không khí | 18 |
| giày | 9 |
| mẹ & bé | 8 |
| máy lọc nước | 6 |
| nồi chiên | 6 |
| áo khoác | 5 |
| quạt | 2 |

**Miền giao hàng**

| giá trị | số kịch bản |
|---|---|
| miền Bắc | 40 |
| miền Nam | 14 |

**Kiểu kịch bản (archetype)**

| giá trị | số kịch bản |
|---|---|
| off_doc | 6 |
| exchange | 5 |
| status_complaint | 5 |
| over_budget | 4 |
| change_mind | 3 |
| cod_limit | 3 |
| promo_expired | 3 |
| saved_address | 3 |
| size_conflict | 3 |
| adv | 2 |
| bargain | 2 |
| claims_returning | 2 |
| cross_conflict | 2 |
| defect | 2 |
| gate_decline | 2 |
| spoken_numbers | 2 |
| variant_oos | 2 |
| inquiry_only | 1 |
| simple_buy | 1 |
| teencode_buy | 1 |

## Chéo: nhóm × kiểu × số cuộc

| nhóm | kiểu | số cuộc | số kịch bản |
|---|---|---|---|
| A | adv | 2 calls | 2 |
| A | cross_conflict | 2 calls | 2 |
| A | promo_expired | 2 calls | 3 |
| A | saved_address | 2 calls | 3 |
| A | size_conflict | 2 calls | 3 |
| B | exchange | 3 calls | 5 |
| B | status_complaint | 3 calls | 5 |
| C | bargain | 1 calls | 2 |
| C | change_mind | 1 calls | 3 |
| C | claims_returning | 1 calls | 2 |
| C | cod_limit | 1 calls | 3 |
| C | defect | 1 calls | 2 |
| C | gate_decline | 1 calls | 2 |
| C | inquiry_only | 1 calls | 1 |
| C | off_doc | 1 calls | 6 |
| C | over_budget | 1 calls | 4 |
| C | simple_buy | 1 calls | 1 |
| C | spoken_numbers | 1 calls | 2 |
| C | teencode_buy | 1 calls | 1 |
| C | variant_oos | 1 calls | 2 |

## Danh sách

| id | nhóm | kiểu | persona | ca khó | ngành | kênh các cuộc |
|---|---|---|---|---|---|---|
| SC-D01 | A | adv | khach_do_du_hoi_nguoi_nha | - | máy lọc không khí | chat_fanpage → hotline |
| SC-D02 | A | adv | khach_do_du_hoi_nguoi_nha | - | máy lọc không khí | zalo_oa → hotline |
| SC-D03 | A | cross_conflict | khach_da_kenh_mau_thuan | mau_thuan_phien_truoc | máy lọc không khí | chat_fanpage → hotline |
| SC-D04 | A | cross_conflict | khach_da_kenh_mau_thuan | mau_thuan_phien_truoc | máy lọc không khí | zalo_oa → hotline |
| SC-D05 | A | size_conflict | khach_hoi_nhieu_khong_mua | mau_thuan_phien_truoc | giày | hotline → hotline |
| SC-D06 | A | size_conflict | khach_hoi_nhieu_khong_mua | mau_thuan_phien_truoc | giày | hotline → hotline |
| SC-D07 | A | size_conflict | khach_hoi_nhieu_khong_mua | mau_thuan_phien_truoc | áo khoác | hotline → hotline |
| SC-D08 | A | promo_expired | khach_so_gia | khuyen_mai_het_han | giày | chat_fanpage → hotline |
| SC-D09 | A | promo_expired | khach_so_gia | khuyen_mai_het_han | máy lọc không khí | zalo_oa → hotline |
| SC-D10 | A | promo_expired | khach_so_gia | khuyen_mai_het_han | máy lọc không khí | chat_fanpage → hotline |
| SC-D11 | A | saved_address | khach_da_mua_doi_size | - | giày | hotline → hotline |
| SC-D12 | A | saved_address | khach_quay_lai_sau_8_thang | - | máy lọc không khí | hotline → hotline |
| SC-D13 | A | saved_address | khach_da_mua_doi_size | - | mẹ & bé | hotline → hotline |
| SC-D14 | B | exchange | khach_da_mua_doi_size | - | giày | chat_fanpage → zalo_oa → hotline |
| SC-D15 | B | exchange | khach_da_mua_doi_size | - | giày | zalo_oa → zalo_oa → hotline |
| SC-D16 | B | exchange | khach_da_mua_doi_size | - | giày | chat_fanpage → chat_fanpage → hotline |
| SC-D17 | B | exchange | khach_da_mua_doi_size | - | áo khoác | zalo_oa → chat_fanpage → hotline |
| SC-D18 | B | exchange | khach_da_mua_doi_size | - | áo khoác | chat_fanpage → zalo_oa → hotline |
| SC-D19 | B | status_complaint | khach_goi_lan_3_het_kien_nhan | - | mẹ & bé | hotline → hotline → hotline |
| SC-D20 | B | status_complaint | khach_goi_lan_3_het_kien_nhan | - | máy lọc không khí | hotline → hotline → hotline |
| SC-D21 | B | status_complaint | khach_goi_lan_3_het_kien_nhan | - | quạt | hotline → hotline → hotline |
| SC-D22 | B | status_complaint | khach_goi_lan_3_het_kien_nhan | - | mẹ & bé | hotline → hotline → hotline |
| SC-D23 | B | status_complaint | khach_goi_lan_3_het_kien_nhan | - | nồi chiên | hotline → hotline → hotline |
| SC-D24 | C | variant_oos | khach_mua_nhieu_mon | het_hang_bien_the | giày | hotline |
| SC-D25 | C | bargain | khach_so_gia | mac_ca | nồi chiên | chat_fanpage |
| SC-D26 | C | gate_decline | khach_so_gia | tu_choi_giua_gate | giày | zalo_oa |
| SC-D27 | C | variant_oos | khach_mua_nhieu_mon | het_hang_bien_the | áo khoác | hotline |
| SC-D28 | C | gate_decline | khach_do_du_hoi_nguoi_nha | hoan_giua_gate | mẹ & bé | chat_fanpage |
| SC-D29 | C | simple_buy | khach_do_du_hoi_nguoi_nha | - | máy lọc không khí | hotline |
| SC-D30 | C | bargain | khach_so_gia | mac_ca | máy lọc nước | zalo_oa |
| SC-D31 | C | over_budget | khach_so_gia | vuot_ngan_sach_2_lua_chon | máy lọc không khí | hotline |
| SC-D32 | C | over_budget | khach_do_du_hoi_nguoi_nha | vuot_ngan_sach_2_lua_chon | máy lọc không khí | zalo_oa |
| SC-D33 | C | over_budget | khach_so_gia | vuot_ngan_sach_2_lua_chon | máy lọc không khí | hotline |
| SC-D34 | C | over_budget | khach_so_gia | vuot_ngan_sach_2_lua_chon | máy lọc không khí | chat_fanpage |
| SC-D35 | C | change_mind | khach_so_gia | doi_y_giua_cuoc | máy lọc nước | hotline |
| SC-D36 | C | change_mind | khach_so_gia | doi_y_giua_cuoc | nồi chiên | hotline |
| SC-D37 | C | change_mind | khach_so_gia | doi_y_giua_cuoc | mẹ & bé | hotline |
| SC-D38 | C | off_doc | khach_ngoai_pham_vi_chuyen_may | hoi_ngoai_tai_lieu_y_te | mẹ & bé | hotline |
| SC-D39 | C | off_doc | khach_ngoai_pham_vi_chuyen_may | hoi_ngoai_tai_lieu_y_te | máy lọc không khí | hotline |
| SC-D40 | C | off_doc | khach_hoi_ngoai_tai_lieu | hoi_ngoai_tai_lieu_doi_thu | máy lọc không khí | hotline |
| SC-D41 | C | off_doc | khach_hoi_ngoai_tai_lieu | hoi_ngoai_tai_lieu_doi_thu | máy lọc nước | hotline |
| SC-D42 | C | off_doc | khach_hoi_ngoai_tai_lieu | hoi_ngoai_tai_lieu_doi_thu | nồi chiên | hotline |
| SC-D43 | C | off_doc | khach_hoi_ngoai_tai_lieu | hoi_ngoai_tai_lieu_chinh_sach | quạt | hotline |
| SC-D44 | C | cod_limit | khach_mua_nhieu_mon | cod_vuot_han_muc | máy lọc không khí | hotline |
| SC-D45 | C | cod_limit | khach_mua_nhieu_mon | cod_vuot_han_muc | máy lọc nước | hotline |
| SC-D46 | C | cod_limit | khach_mua_nhieu_mon | cod_vuot_han_muc | nồi chiên | hotline |
| SC-D47 | C | claims_returning | khach_da_kenh_fb_hotline | tu_nhan_khach_cu_chua_sdt | nồi chiên | zalo_oa |
| SC-D48 | C | claims_returning | khach_da_kenh_fb_hotline | tu_nhan_khach_cu_chua_sdt | mẹ & bé | chat_fanpage |
| SC-D49 | C | teencode_buy | khach_da_kenh_fb_hotline | - | áo khoác | zalo_oa |
| SC-D50 | C | inquiry_only | khach_hoi_nhieu_khong_mua | - | máy lọc nước | hotline |
| SC-D51 | C | spoken_numbers | khach_hoi_nhieu_khong_mua | so_noi_bang_chu | máy lọc không khí | hotline |
| SC-D52 | C | spoken_numbers | khach_hoi_nhieu_khong_mua | so_noi_bang_chu | mẹ & bé | hotline |
| SC-D53 | C | defect | khach_goi_lan_3_het_kien_nhan | khieu_nai_loi_nsx | máy lọc không khí | hotline |
| SC-D54 | C | defect | khach_goi_lan_3_het_kien_nhan | khieu_nai_loi_nsx | máy lọc nước | hotline |
