# KHUNG TIÊU CHÍ ĐÁNH GIÁ TIN TỨC CHỨNG KHOÁN — v2

Phiên bản: v2 (2026-10-27) · Thay thế: `tieu_chi.md` (v1, giữ nguyên để đối chiếu)
Phạm vi: InvestMate PoC – KB Securities · Mã: NVL, MSN, FPT, HPG, MWG

**Cách đọc nguồn gốc quy tắc** (cột "Nguồn" trong các bảng):
- `v1` – giữ từ tiêu chí v1.
- `KB#n` – rút ra từ nhãn Expected của KB trong file test 20/10/2026 (n = STT dòng trong sheet Template; `KB#VD` = dòng ví dụ).
- `ĐX` – đề xuất mới, **chưa được KB xác nhận**. Cần KB duyệt trước khi coi là chuẩn.

---

## 0. Đầu ra cần đánh giá

Với mỗi cặp (bài báo, mã cổ phiếu) hệ thống trả ra:

| Trường | Giá trị | Hiển thị |
|---|---|---|
| Relevance | Trực tiếp / Gián tiếp / Không liên quan | Nội bộ (dùng để áp trần, không hiển thị) |
| Priority | Cao / Trung bình / Thấp | Badge |
| Ảnh hưởng | Tích cực / Tiêu cực / Trung lập | Badge |
| Lý giải Priority, Lý giải Ảnh hưởng | Văn bản, **bắt buộc trích mã quy tắc** (VD: `P-TH-01`, `I-TL-e`) và số liệu dẫn chứng | Nội bộ / phục vụ test |
| News Details | Summary · Đề cập gì · Vì sao ảnh hưởng · Theo dõi tiếp | Màn News Detail (xem Mục 5) |

Relevance = Không liên quan → không gán Priority, Ảnh hưởng; bài không gắn vào mã đó.

---

## 1. NGUYÊN TẮC CHUNG

| Mã | Nguyên tắc | Nguồn |
|---|---|---|
| G-1 | Gán nhãn theo **nội dung bài báo**, không theo dự đoán giá. Văn phong, tiêu đề giật gân và diễn biến giá không phải căn cứ kết luận. | v1, Overview E |
| G-2 | Giả định thông tin trong bài là đúng khi đánh giá mức độ quan trọng. | v1 |
| G-3 | Không có bằng chứng thì không có kết luận. Mọi con số dùng để kết luận phải trích được từ bài (hoặc từ hồ sơ mã ở Mục 6, ghi rõ nguồn). | v1 |
| G-4 | **Chấm theo thông tin mới của bài.** Bối cảnh nhắc lại (phương án đã công bố, KQKD kỳ trước, lịch sử) không làm tăng Priority. Bài chỉ cập nhật tiến độ/thủ tục của sự kiện đã công bố → áp `P-MOD-1`. | KB#10, KB#22 |
| G-5 | **Chấm theo góc nhìn của mã đang xét.** Một bài có thể cho nhãn khác nhau với từng mã. Sự kiện xảy ra ở công ty con/liên kết có mã riêng chỉ được tính phần tác động lên mã đang xét mà bài định lượng được. | KB#15, KB#16 |
| G-6 | Bài có nhiều sự kiện về cùng một mã: Priority theo sự kiện **mới** quan trọng nhất; Ảnh hưởng theo tác động ròng của các sự kiện mới (xem `I-TL-a`). | ĐX |
| G-7 | Số liệu mâu thuẫn trong bài (hoặc giữa bài và hồ sơ mã) → không dùng số đó làm căn cứ lên bậc; ghi cờ "số liệu mâu thuẫn" trong lý giải và trong Summary. | Overview E |
| G-8 | Mẫu số: ưu tiên mẫu số có trong bài; nếu bài không có, được dùng số liệu trong hồ sơ mã (Mục 6) **tại thời điểm đăng bài**, và phải ghi nguồn mẫu số. | ĐX |
| G-9 | **Loại sự kiện theo trọng tâm của toàn bài**, không theo một đoạn hay một con số riêng lẻ. Bài giải thích/phân tích diễn biến giá nêu nhiều nguyên nhân (dòng tiền, KQKD đã công bố, rủi ro, nhận định CTCK, định giá) mà không có sự kiện mới → A24; số liệu trong bài chỉ dùng làm dẫn chứng. | KB#VD (sửa 28/10/2026) |

---

## 2. RELEVANCE — Mức độ liên quan

### 2.1. Trực tiếp

Sự kiện đi vào mã không qua tầng trung gian nào: mã (hoặc thực thể mà mã hợp nhất kết quả **và không niêm yết riêng**) là chủ thể sự kiện, hoặc bài trình bày dữ liệu/luận điểm riêng cho mã. Thỏa bất kỳ:

| Mã | Tiêu chí | Ví dụ |
|---|---|---|
| R-TT-1 | Bài nói về chính công ty, lãnh đạo/cổ đông chủ chốt và người liên quan, hoặc cổ phiếu của công ty (phát hành, cổ tức, chỉ số, khối ngoại, giao dịch nội bộ…). | Vợ ông Bùi Thành Nhơn bán CP NVL (KB#12) |
| R-TT-2 | Bài nói về công ty con/đơn vị trực thuộc/chuỗi/thương hiệu/dự án **không niêm yết riêng** (kể cả đơn vị không cốt lõi). | Bách Hóa Xanh → MWG; Hòa Phát Nông nghiệp → HPG (KB#18) |
| R-TT-3 | Công ty (hoặc công ty con không niêm yết) là **một bên** của sự kiện: bên mua/bán, bên góp vốn, đối tác, bên nhận thầu — **kể cả khi tài sản giao dịch là cổ phần của một công ty có mã riêng**. | MSN mua thêm CP MCH (KB#14); công ty con của MSN bán 4,99% MSR cho Elmet (KB#15) |
| R-TT-4 | Bài phạm vi rộng (ngành, thị trường, vĩ mô, bài về mã khác) nhưng nêu riêng mã kèm thông tin/số liệu của chính mã. | Bài về CP ngân hàng có nêu giá trị khối ngoại bán FPT (KB#8) |

### 2.2. Gián tiếp

| Mã | Tiêu chí |
|---|---|
| R-GT-a1 | Bài nói về công ty con/liên kết **có mã riêng** (hoặc thương hiệu thuộc công ty đó), và mã đang xét **không** là một bên của sự kiện. VD: KQKD, cổ tức, ngành hàng mới của DMX với MWG (KB#25); cổ tức MSR với MSN (KB#16). |
| R-GT-a2 | Dự án liên danh; bên liên quan chưa xác nhận quan hệ sở hữu ("hệ sinh thái", liên quan qua cổ đông). |
| R-GT-a3 | Mã chỉ được nhắc để minh họa/lịch sử, không có sự kiện mới về mã. |
| R-GT-b | Nội dung chính của bài là **biến số ngành của mã** (giá thép, quặng sắt, hạn ngạch thép EU → HPG; sức mua bán lẻ → MWG). Biến số phải có sẵn trong bài, không suy luận nhiều bước. |

> Ghi chú về R-TT-3 và R-GT-a1: cùng một tin về MSR, MSN là **Trực tiếp** nếu MSN/công ty con của MSN là bên giao dịch, là **Gián tiếp** nếu sự kiện chỉ diễn ra bên trong MSR. Dù Trực tiếp, Priority vẫn bị áp trần bởi `P-MOD-3` nếu bài không định lượng được tác động lên mã mẹ.

### 2.3. Không liên quan

| Mã | Tiêu chí |
|---|---|
| R-KLQ-1 | Mã chỉ xuất hiện trong danh sách liệt kê (bảng top mã, bản tin thị trường) **không kèm số liệu riêng**. |
| R-KLQ-2 | Tin vĩ mô/thị trường tổng quát, không phải biến số ngành của mã và không phân tích riêng mã. |
| R-KLQ-3 | Trùng tên/nhận diện nhầm thực thể. |

---

## 3. PRIORITY — Mức độ quan trọng

### 3.1. Định nghĩa bậc

| Bậc | Định nghĩa | Dấu hiệu trong lý giải |
|---|---|---|
| **Cao** | Thông tin mới có số liệu cho thấy độ lớn vượt ngưỡng vật chất so với quy mô doanh nghiệp, hoặc làm thay đổi cấu trúc (vốn, quyền kiểm soát, thanh khoản, dòng sản phẩm/lĩnh vực, trạng thái chỉ số toàn cầu) đến mức có thể buộc nhà đầu tư điều chỉnh mô hình định giá. | Có ít nhất một con số **có mẫu số so sánh**; Relevance = Trực tiếp; không có câu phủ định dữ liệu. |
| **Trung bình** | Có ý nghĩa thực chất nhưng: (a) độ lớn ở dải trung gian; (b) loại sự kiện quan trọng nhưng bài thiếu số để lượng hóa; hoặc (c) bị áp trần/hạ bậc (Mục 3.3). Là bậc sàn của một số loại sự kiện (Mục 3.4). | Cấu trúc "có ý nghĩa… nhưng chưa…". |
| **Thấp** | Không tạo thay đổi lượng hóa được với doanh thu, lợi nhuận, cấu trúc vốn hay rủi ro trong chân trời đầu tư thông thường; hoặc mã chỉ mang tính minh họa. | Câu phủ định dữ liệu không được bù bởi con số có mẫu số: "chưa lượng hóa", "chưa có giá trị hợp đồng", "mang tính minh họa"… |

### 3.2. Ngưỡng định lượng

Khi một sự kiện có nhiều thước đo, lấy **bậc cao nhất** trong các thước đo có dữ liệu.

| Mã | Loại sự kiện | Cao | Trung bình | Thấp | Nguồn |
|---|---|---|---|---|---|
| P-TH-01 | KQKD (doanh thu/LNST) của mã | Tăng/giảm > ~10% DT TTM hoặc > ~15% LNST TTM; hoặc vượt/hụt kế hoạch năm | Biến động trong dải 5–10% / 5–15% | < 5% | v1, KB#1, #9, #20 |
| P-TH-02 | Phát hành/pha loãng | > 10% CP lưu hành | Đúng 10% hoặc 3–<10%; CP thưởng/chia tách mọi tỷ lệ | < 3% | v1 |
| P-TH-03 | Cổ tức tiền mặt của mã | Lợi suất ≥ 6% hoặc tỷ lệ chi trả ≥ 60% LNST | **Mọi khoản cổ tức tiền mặt đã công bố dưới ngưỡng Cao** (gồm thông báo chốt quyền/GDKHQ) | — | KB#22 (thay ngưỡng v1, xem Phụ lục B) |
| P-TH-04 | Hợp đồng ký mới | Giá trị ≥ 10% DT TTM, hoặc backlog tăng ≥ ~20% | 3–<10% DT TTM, hoặc backlog tăng 5–<20%; hoặc HĐ đã ký nhưng không công bố giá trị (gắn cờ) | < 3% DT TTM | v1 (thống nhất ngưỡng) |
| P-TH-05 | Vốn đầu tư/góp vốn/M&A của mã | Vốn > ~10% tổng tài sản hoặc > ~20% VCSH; công suất tăng > 20%; **hoặc đầu tư quy mô nghìn tỷ vào lĩnh vực/dòng sản phẩm mới** | 3–10% TTS hoặc 5–20% VCSH; công suất +5–20%; M&A không công bố giá trị | < 3% TTS, < 5% VCSH, công suất < +5% | v1, KB#19 |
| P-TH-06 | KPI vận hành cốt lõi (sản lượng, số cửa hàng, đơn hàng) | Biến động ≥ ~30% YoY tại mảng/đơn vị trọng yếu | 10–30% YoY, hoặc KPI ở mảng không cốt lõi | < 10% | v1, KB#17, #18 |
| P-TH-07 | Nợ, thanh khoản | Chậm trả gốc/lãi có số + đối chiếu tiền mặt; ý kiến kiểm toán về hoạt động liên tục kèm thanh lý tài sản nghìn tỷ | Nghĩa vụ trái phiếu của đơn vị "hệ sinh thái"; gia hạn nghĩa vụ không có số | — | v1 |
| P-TH-08 | Chỉ số | Vào/ra chỉ số toàn cầu (FTSE Global All Cap và tương đương) | Chỉ số nội địa; dự báo vào/ra rổ; không được thêm vào danh sách | — | v1 |
| P-TH-09 | Dòng vốn khối ngoại | Lũy kế nhiều phiên, là trọng tâm bài và có mẫu số (% CP lưu hành, % room) | Giá trị mua/bán ròng riêng cho mã trong một hoặc vài phiên | — | v1, KB#8, #21 (ngưỡng Cao: ĐX) |
| P-TH-10 | Giao dịch của người nội bộ/người liên quan/cổ đông lớn | Làm thay đổi quyền kiểm soát/chi phối, hoặc vượt/xuống dưới ngưỡng sở hữu then chốt (36%, 50%, 65%) | **Mọi giao dịch còn lại** (đăng ký, kết quả mua/bán) | — | KB#12, #20, #23 (ngưỡng Cao: ĐX) |
| P-TH-11 | Pháp lý dự án | Dự án trọng yếu + số lượng sản phẩm đủ điều kiện mở bán | Tiến triển pháp lý chưa có số liệu tài chính | Tạm dừng thủ tục hành chính | v1 |
| P-TH-12 | Dừng/hủy dự án | Vốn dự án vượt ngưỡng Cao của P-TH-05 | Vốn trong dải TB, hoặc mới ở giai đoạn đề xuất/nghiên cứu với chi phí đã bỏ ra nhỏ | — | ĐX |

### 3.3. Điều chỉnh bậc (áp theo thứ tự)

| Mã | Quy tắc | Nguồn |
|---|---|---|
| P-MOD-1 | **Cập nhật của sự kiện đã công bố** (gia hạn, điều chỉnh lịch, chốt quyền, GDKHQ, kết quả giao dịch đã đăng ký, nhắc lại): **hạ 1 bậc** so với Priority của sự kiện gốc, nhưng không thấp hơn sàn của loại sự kiện (Mục 3.4). Trừ khi bản cập nhật làm thay đổi đáng kể quy mô/điều kiện (đổi giá, đổi khối lượng ≥ 20%, hủy) → chấm như sự kiện mới. | KB#10 |
| P-MOD-2 | Relevance = Gián tiếp → **trần Trung bình**. | v1 |
| P-MOD-3 | Sự kiện liên quan đến công ty con có mã riêng mà bài **không định lượng tác động lên mã mẹ** (lợi nhuận hợp nhất, nợ, EPS, dòng tiền về mẹ) → **trần Trung bình**, kể cả khi mã mẹ là một bên giao dịch. | KB#15 |
| P-MOD-4 | Bài đa mã (≥ 2 mã được phân tích ngang nhau, VD danh mục khuyến nghị) → mặc định Trung bình cho từng mã, trừ khi bài có số liệu riêng vượt ngưỡng Cao cho mã đó. | v1 |
| P-MOD-5 | Loại sự kiện quan trọng nhưng bài thiếu số để lượng hóa → tối đa Trung bình. | v1 |

### 3.4. Sàn theo loại sự kiện

Các loại sau **không xuống dưới Trung bình**: cổ tức tiền mặt (P-TH-03), giao dịch của người nội bộ/cổ đông lớn (P-TH-10), dòng vốn khối ngoại có giá trị riêng cho mã (P-TH-09), khuyến nghị/dự báo của CTCK có luận điểm riêng cho mã, ra mắt sản phẩm/dịch vụ thương mại thuộc mảng cốt lõi. Nguồn: KB#3, #5, #8, #12, #20, #21, #22, #23.

---

## 4. ẢNH HƯỞNG — Tích cực / Tiêu cực / Trung lập

### 4.1. Các yếu tố xác định hướng

Mã trích dẫn: yếu tố #n có mã `I-YT-n` (VD yếu tố #8 → `I-YT-8`).

| # | Yếu tố | Tích cực | Tiêu cực |
|---|---|---|---|
| 1 | Doanh thu / lợi nhuận | Tăng trưởng đã ghi nhận; vượt kế hoạch | Giảm, lỗ, lỗ lũy kế; hụt kế hoạch |
| 2 | Chi phí & biên | Giảm chi phí, tăng năng suất | Tăng chi phí vốn, tăng thuế nhập khẩu |
| 3 | Tăng trưởng & mở rộng | Mở điểm bán có lãi, thị trường mới, công suất mới, **sản phẩm/dịch vụ thương mại mới** | Dừng dự án, mất thị trường |
| 4 | Vị thế cạnh tranh | Vào chuỗi cung ứng toàn cầu, năng lực kỹ thuật mới | Rào cản thương mại, mất lợi thế |
| 5 | Pháp lý | Được chấp thuận, đủ điều kiện mở bán | Thuế/phạt/thanh tra đã ban hành |
| 6 | Thanh khoản & nợ | Huy động được vốn **từ bên ngoài tập đoàn**, thu tiền bán tài sản | Chậm trả gốc/lãi, phải gia hạn nghĩa vụ |
| 7 | Lợi ích cổ đông hiện hữu | Cổ tức tiền mặt, phát hành ≥ thị giá, **tăng sở hữu tại công ty con đang tạo lợi nhuận** | Pha loãng thuần, phát hành dưới thị giá, ESOP/chứng quyền thưởng lớn |
| 8 | Dòng vốn & niềm tin | Vào rổ chỉ số, khối ngoại mua ròng, **người nội bộ/người liên quan mua vào** | Bị loại khỏi rổ, khối ngoại bán ròng, áp lực bán cơ học |
| 9 | Công bố thông tin & quản trị | Ý kiến kiểm toán cải thiện, minh bạch hơn | Nhấn mạnh hoạt động liên tục, chậm công bố |
| 10 | Định giá tài sản liên quan | Tài sản liên quan được định giá lại cao hơn (VD bán cổ phần công ty con cho bên ngoài ở định giá cao) | Tài sản liên quan mất câu chuyện định giá |

Nguồn bổ sung: KB#5 (#3), KB#14 (#7), KB#20 (#8), KB#15 (#6, #10).

### 4.2. Trung lập — gán khi thỏa bất kỳ cơ chế nào

| Mã | Cơ chế | Ví dụ | Nguồn |
|---|---|---|---|
| I-TL-a | **Hai chiều nội tại**: có cả yếu tố lợi và bất lợi ở quy mô tương đương, bài không lượng hóa tác động ròng. | NVL lãi vượt kế hoạch nhưng 9 tháng chỉ bán mới 218 căn (KB#11); phát hành pha loãng để trả nợ (KB#10); góp 8.000 tỷ vào lĩnh vực mới chưa có dữ liệu hiệu quả (KB#19) | v1 |
| I-TL-b | **Thiếu số liệu xác định hướng.** | DMX mở ngành hàng AI & Robotics, chưa có mô hình/chỉ tiêu (KB#25) | v1 |
| I-TL-c | **Hướng không đồng nhất giữa các mã** (bài đa mã). | | v1 |
| I-TL-d | **Sự kiện kỹ thuật/hành chính thuần**: CP thưởng, chia tách, điều chỉnh giá tham chiếu, bổ nhiệm, đổi địa chỉ, nhắc lại thông tin; khuyến nghị/điều chỉnh dự báo của CTCK, bài phân tích/giải thích diễn biến giá không có sự kiện mới (A24); hợp tác kỹ thuật/dữ liệu/MOU không có giá trị thương mại. | Vietcap điều chỉnh dự báo FPT (KB#7); Vì sao CP FPT giảm dù kinh doanh tốt (KB#VD); FPT–NVIDIA mở rộng dữ liệu giả lập (KB#6) | v1, KB#6, #7, KB#VD |
| I-TL-e | **Chuyển giao nội bộ tập đoàn**: dòng tiền chỉ di chuyển giữa các đơn vị hợp nhất (công ty con trả cổ tức cho mẹ, mẹ cấp vốn cho con), giá trị hợp nhất không đổi; trừ khi bài nói rõ mã mẹ dùng tiền vào việc gì có tác động định lượng. | MSR tạm ứng cổ tức 20% (KB#16) | KB#16 |
| I-TL-f | **Người nội bộ/người liên quan bán ra** mà không làm thay đổi quyền kiểm soát: động cơ bán đa dạng (nhu cầu cá nhân, cân đối danh mục), không đủ bằng chứng xác định hướng. | Ông Đoàn Văn Hiểu Em bán 1 triệu CP MWG (KB#23); vợ ông Bùi Thành Nhơn bán CP NVL (KB#12) | KB#12, #23 |

> Ngoại lệ `I-TL-f` (ĐX, cần KB xác nhận): bán làm mất quyền kiểm soát/phủ quyết, hoặc bán dồn dập nhiều đợt kèm sự kiện bất lợi khác trong cùng bài → Tiêu cực.

### 4.3. Quy tắc kết hợp

1. Liệt kê các yếu tố ở 4.1 có bằng chứng trong **thông tin mới** của bài.
2. Nếu thỏa một cơ chế Trung lập ở 4.2 → Trung lập.
3. Nếu các yếu tố cùng một hướng → hướng đó.
4. Nếu hai hướng: một hướng có số liệu và rõ ràng lớn hơn → hướng đó; ngược lại → Trung lập (`I-TL-a`).
5. Diễn biến giá cổ phiếu tự thân **không phải** yếu tố (G-1). Dòng vốn khối ngoại là yếu tố #8.

---

## 5. YÊU CẦU NỘI DUNG NEWS DETAILS

| Phần | Đạt khi | Lỗi cần tránh |
|---|---|---|
| Summary | Nêu đúng sự kiện chính và số liệu quan trọng nhất (ưu tiên LNTT/LNST, % tăng giảm, giá trị giao dịch); số đúng đơn vị; không thêm thông tin ngoài bài; ngắn gọn. Gắn cờ nếu số liệu mâu thuẫn (G-7). | Bỏ sót ý chính hoặc nửa sau bài; sai số; quá dài |
| Bài báo đang đề cập đến điều gì? | 1–2 câu, đúng trọng tâm, gắn với **mã đang xét** (nêu rõ quan hệ nếu chủ thể là công ty con: "MSR, công ty con Masan sở hữu ~87,46%…"). Không lặp nguyên văn Summary. | Chỉ nêu một phần sự kiện; nói về mã khác |
| Vì sao thông tin này có thể ảnh hưởng đến cổ phiếu? | Nhất quán với Badge và trích yếu tố ở Mục 4; nêu cả chiều thuận lợi và bất lợi nếu có, **kèm số liệu**; với tin công ty con, **quy đổi về mã mẹ theo tỷ lệ sở hữu** khi có đủ dữ liệu (VD: 87,46% × 2.210 tỷ ≈ 1.933 tỷ đồng về MSN); dùng "có thể ảnh hưởng". | Chung chung; mâu thuẫn Badge; suy luận vượt nội dung bài |
| Nhà đầu tư nên theo dõi điều gì tiếp theo? | 1–3 điểm cụ thể, kiểm chứng được: mốc thời gian, chỉ tiêu, số liệu đối chiếu (VD: kết quả chào bán sau 26/11/2026; room ngoại 20,56%). | "Theo dõi diễn biến thị trường"; không liên quan bài |
| Áp dụng cả 4 phần | Văn phong dễ hiểu; **không** khuyến nghị mua/bán/nắm giữ; không dự đoán giá; không dùng tiêu đề giật gân làm căn cứ. | |

Nguồn: Overview mục E; nhận xét KB#VD, KB#16.

---

## 6. HỒ SƠ MÃ (dữ liệu tham chiếu bắt buộc)

Bản đồ thực thể quyết định Relevance (R-TT-2 vs R-GT-a1) và mẫu số (G-8). Mỗi thực thể phải có **trạng thái niêm yết theo ngày**: tin trước ngày niêm yết là Trực tiếp, sau ngày niêm yết là Gián tiếp.

| Mã | Thực thể | Niêm yết riêng | Sở hữu của mã mẹ | Ghi chú |
|---|---|---|---|---|
| MWG | DMX – Điện Máy Xanh | **Có, HOSE từ 06/08/2026** | Cần xác minh | Tin DMX sau 06/08/2026 → Gián tiếp (KB#25) |
| MWG | TopZone | Cần xác minh thuộc DMX hay MWG | | |
| MWG | Bách Hóa Xanh, An Khang, AVAKids, EraBlue | Chưa ghi nhận | Cần xác minh | |
| MSN | MCH – Masan Consumer | Có | ~69,4% → ~74,9% (đăng ký mua 10/2026) | |
| MSN | MSR – Masan High-Tech Materials | Có (UPCoM) | ~87,46% sau Elmet; có kế hoạch bán thêm 5,01% | |
| MSN | WinCommerce, Phúc Long, Masan MEATLife | Cần xác minh | | |
| FPT | FOC – FPT Online | Có | Cần xác minh | |
| FPT | FRT – FPT Retail (Long Châu, FPT Shop) | Có | Liên kết | |
| FPT | FPT Software, FPT Smart Cloud, FPT Education | Không | | |
| HPG | Hòa Phát Dung Quất, Hòa Phát Nông nghiệp, BĐS Hòa Phát | Cần xác minh | | |
| NVL | Diamond Properties, NovaGroup | — | Cổ đông lớn / người liên quan | Giao dịch của họ → R-TT-1, P-TH-10 |

Số liệu tài chính theo kỳ (doanh thu và LNST TTM, tổng tài sản, VCSH, số CP lưu hành, công suất, giá đóng cửa ngày đăng bài) do pipeline nạp từ nguồn dữ liệu, **không** viết tay vào tài liệu này.

---

## 7. QUY TRÌNH ĐÁNH GIÁ (cho người và cho AI)

1. **Nhận diện mã**: liệt kê mọi mã watchlist và thực thể thuộc hồ sơ mã (Mục 6) xuất hiện trong bài.
2. **Relevance** cho từng mã (Mục 2). Không liên quan → dừng.
3. **Xác định thông tin mới** của bài (G-4) và **loại sự kiện** theo Phụ lục A.
4. **Priority**: bậc mặc định của loại sự kiện → áp ngưỡng định lượng 3.2 (lấy bậc cao nhất có dữ liệu) → áp điều chỉnh 3.3 theo thứ tự → kiểm tra sàn 3.4.
5. **Ảnh hưởng** theo 4.3.
6. **Kiểm tra nhất quán**: Cao ⇒ Trực tiếp + có con số có mẫu số + không có câu phủ định dữ liệu; lý giải trích mã quy tắc; News Details nhất quán với Badge.

---

## PHỤ LỤC A — BẢNG TRA THEO LOẠI SỰ KIỆN

Đây là **prior**. Luôn kiểm tra lại bằng ngưỡng 3.2 và điều chỉnh 3.3.

| # | Loại sự kiện | Relevance | Priority mặc định | Ảnh hưởng mặc định | Điều kiện đổi nhãn | Nguồn |
|---|---|---|---|---|---|---|
| A01 | KQKD của mã (tăng trưởng > 10% / vượt kế hoạch) | TT | Cao | Tích cực | Giảm, lỗ → Tiêu cực; có yếu tố bất lợi tương đương → Trung lập (I-TL-a) | v1, KB#1, #9, #11, #20 |
| A02 | KQKD/KPI công ty con không niêm yết riêng | TT | Cao nếu mảng trọng yếu và vượt ngưỡng P-TH-06; TB nếu mảng không cốt lõi | Theo hướng KQKD | — | v1, KB#18 |
| A03 | KQKD/cổ tức/hoạt động của công ty con có mã riêng | GT | TB | Theo giá trị tài sản liên quan; cổ tức về mẹ → Trung lập (I-TL-e) | Bài định lượng tác động lên mẹ → xét lại | v1, KB#16, #25 |
| A04 | Mã mẹ bán cổ phần công ty con có mã riêng cho bên ngoài | TT | TB (trần P-MOD-3) | Tích cực (thu tiền, định giá lại) | Bài định lượng giảm nợ/lợi nhuận của mẹ vượt ngưỡng → Cao | KB#15 |
| A05 | Mã mẹ mua thêm cổ phần công ty con có mã riêng | TT | Theo P-TH-05 (giá trị so TTS/VCSH của mẹ) | Tích cực nếu công ty con đang tạo lợi nhuận | — | KB#14 |
| A06 | Phát hành cho cổ đông hiện hữu > 10% CP | TT | Cao | Trung lập nếu dùng trả nợ; Tiêu cực nếu pha loãng thuần | Kiểm tra mục đích sử dụng vốn | v1 |
| A07 | Gia hạn/điều chỉnh lịch đợt phát hành đã công bố | TT | Hạ 1 bậc so với sự kiện gốc (P-MOD-1) | Trung lập | Đổi giá/khối lượng/hủy → chấm như sự kiện mới | KB#10 |
| A08 | Cổ phiếu thưởng / chia tách | TT | TB | Trung lập | — | v1 |
| A09 | Cổ tức tiền mặt (công bố, chốt quyền, GDKHQ) | TT | TB; Cao nếu lợi suất ≥ 6% hoặc chi trả ≥ 60% LNST | Tích cực | Giảm, hoãn, chuyển sang CP → Tiêu cực | v1, KB#22 |
| A10 | ESOP / chứng quyền thưởng cho lãnh đạo | TT | Theo P-TH-02 (% pha loãng tối đa) | Tiêu cực nếu pha loãng thuần; Trung lập nếu gắn điều kiện hiệu quả rõ ràng | — | ĐX |
| A11 | Hợp đồng ký mới có giá trị | TT | Theo P-TH-04 | Tích cực | Không công bố giá trị → TB + cờ | v1 |
| A12 | M&A, góp vốn, đầu tư lớn | TT | Theo P-TH-05; Cao nếu nghìn tỷ vào lĩnh vực mới | Theo chiến lược; chưa có dữ liệu hiệu quả → Trung lập | — | v1, KB#19 |
| A13 | Ra mắt sản phẩm/dịch vụ thương mại thuộc mảng cốt lõi | TT | TB | Tích cực | Có số doanh thu/khách hàng vượt ngưỡng → xét Cao | KB#5 |
| A14 | Hợp tác kỹ thuật, MOU, chia sẻ dữ liệu, mục tiêu xếp hạng, không có giá trị thương mại | TT | Thấp | Trung lập | Có giá trị HĐ → A11 | v1, KB#6 |
| A15 | Tiến triển pháp lý dự án | TT | TB; Cao nếu dự án trọng yếu + số lượng cụ thể | Tích cực | — | v1 |
| A16 | Thuế/phạt/rào cản thương mại đã ban hành | TT | TB; Cao nếu ảnh hưởng thị trường chính | Tiêu cực | — | v1 |
| A17 | Dừng/hủy dự án | TT | Theo P-TH-12 | Tiêu cực | Chuyển nguồn lực sang dự án khác có số liệu → xét I-TL-a | ĐX |
| A18 | Chậm trả gốc/lãi (mã hoặc công ty con hợp nhất) | TT | Cao | Tiêu cực | — | v1 |
| A19 | Chậm trả tại đơn vị "hệ sinh thái" chưa xác nhận sở hữu | GT | TB | Tiêu cực | — | v1 |
| A20 | Ý kiến kiểm toán nhấn mạnh hoạt động liên tục | TT | Cao | Tiêu cực; Trung lập nếu có yếu tố bù trừ có số liệu | — | v1 |
| A21 | Người nội bộ/người liên quan/cổ đông lớn **mua** | TT | TB (Cao nếu thay đổi quyền kiểm soát) | Tích cực | — | KB#20 |
| A22 | Người nội bộ/người liên quan/cổ đông lớn **bán** | TT | TB (Cao nếu thay đổi quyền kiểm soát) | Trung lập (I-TL-f) | Mất quyền kiểm soát/phủ quyết → Tiêu cực (ĐX) | KB#12, #23 |
| A23 | Khối ngoại mua/bán ròng có giá trị riêng cho mã | TT | TB; Cao nếu lũy kế lớn có mẫu số và là trọng tâm bài | Theo chiều mua/bán ròng | Chỉ khi khối ngoại là trọng tâm bài (bản tin dòng tiền/phiên); bài giải thích diễn biến giá chỉ nêu khối ngoại như một nguyên nhân → A24 (G-9) | v1, KB#8, #21 |
| A24 | Khuyến nghị/điều chỉnh dự báo của CTCK có luận điểm riêng; bài phân tích/giải thích diễn biến giá tổng hợp nhiều yếu tố (dòng tiền, KQKD đã công bố, rủi ro, định giá), không có sự kiện mới | TT | TB | Trung lập | — | v1, KB#7, KB#VD |
| A25 | Vào chỉ số toàn cầu | TT | Cao | Tích cực | — | v1 |
| A26 | Vào chỉ số nội địa / dự báo dòng vốn | TT | TB | Tích cực | — | v1 |
| A27 | Bị loại / nguy cơ loại / không được thêm vào rổ | TT | TB | Tiêu cực | Có yếu tố cơ bản bù trừ có số liệu → Trung lập | v1 |
| A28 | Bổ nhiệm nhân sự (đơn vị con không cốt lõi) | TT | Thấp | Trung lập | — | v1 (sửa Relevance GT → TT theo R-TT-2) |
| A29 | Bổ nhiệm nhiều đơn vị / đơn vị chiến lược | TT | TB | Trung lập | Kèm mục tiêu tài chính → xét lại | v1 |
| A30 | Cải tiến vận hành nhỏ (thiết bị, năng lượng nội bộ) | TT | Thấp | Trung lập | — | v1 |
| A31 | Tin ngành có chiều tác động rõ | GT | TB | Theo chiều nêu trong bài | Chiều không rõ → Trung lập | v1 |
| A32 | Tin vĩ mô có nêu tên mã kèm phân tích riêng | TT | TB | Trung lập nếu phân hóa | — | v1 |
| A33 | Tin vĩ mô tổng quát, không phân tích riêng mã | KLQ | — | — | — | v1 |
| A34 | Nhắc tên minh họa / khoản đầu tư lịch sử | GT | Thấp | Trung lập | — | v1 |
| A35 | Chỉ có diễn biến giá / phân tích kỹ thuật, không có thông tin cơ bản mới | TT | Thấp | Trung lập (G-1) | Khối ngoại là trọng tâm bài → A23; bài giải thích nhiều nguyên nhân, có nội dung cơ bản → A24 (G-9) | ĐX |
| A36 | Tin đồn kèm bác bỏ chính thức của doanh nghiệp | TT | TB | Trung lập (G-2: giả định lời bác bỏ đúng) | Số liệu mới trong bài (VD nợ quá hạn) → chấm như sự kiện riêng | ĐX |

---

## PHỤ LỤC B — THAY ĐỔI SO VỚI v1

| # | Thay đổi | Lý do |
|---|---|---|
| 1 | Thêm G-4 (chấm theo thông tin mới) và P-MOD-1 (hạ 1 bậc cho bản cập nhật) | KB#10: NVL gia hạn chào bán → KB gán TB dù sự kiện gốc (pha loãng ~33%) là Cao |
| 2 | Thêm G-5, P-MOD-3, A03–A05 (góc nhìn mã mẹ với công ty con có mã riêng) | KB#15 (Elmet–MSR → TB), KB#16 (cổ tức MSR → Trung lập), KB#14 (MSN mua MCH → TB/Tích cực) |
| 3 | Thêm I-TL-e (chuyển giao nội bộ tập đoàn) | KB#16 |
| 4 | Thêm P-TH-10, A21, A22, I-TL-f (giao dịch nội bộ: TB; mua → Tích cực, bán → Trung lập) | KB#12, #20, #23. v1 không có dòng này. **Thay** đề xuất trước đó của Claude (bán → Tiêu cực) |
| 5 | Cổ tức tiền mặt: bỏ bậc Thấp (< 3%), sàn là TB | KB#22 gán TB cho cổ tức 1.000đ/CP của MWG (lợi suất ~1,3%), mâu thuẫn ngưỡng v1. **Cần KB xác nhận** |
| 6 | Thống nhất ngưỡng hợp đồng ký mới (Cao ≥ 10% DT TTM hoặc backlog ≥ 20%) | v1 có 2 ngưỡng mâu thuẫn (5% và 10%) |
| 7 | Thêm định nghĩa "Không liên quan" (2.3) | v1 dùng nhãn này nhưng không định nghĩa |
| 8 | A28: bổ nhiệm tại đơn vị con không cốt lõi đổi Relevance GT → TT | Mâu thuẫn với mục 1.1 của v1 |
| 9 | Bỏ các tham chiếu không tồn tại (N3, N4, N5-i, N5-ii, N7, N8, N10, Mục 8.4), thay bằng mã quy tắc tường minh | v1 tham chiếu tới phần không có trong file |
| 10 | Thêm A13 (ra mắt sản phẩm thương mại → TB/Tích cực), tách khỏi A14 (hợp tác kỹ thuật → Thấp/Trung lập) | KB#5 vs KB#6 |
| 11 | P-TH-05 thêm điều kiện "nghìn tỷ vào lĩnh vực mới" → Cao | KB#19 (HPG góp 8.000 tỷ vào chủ đầu tư siêu đô thị → Cao/Trung lập) |
| 12 | Thêm A35, A36, A17, A10 cho các loại bài gặp trong 100 bài watchlist | Đề xuất, **chưa có case KB** |
| 13 | Thêm Mục 5 (yêu cầu News Details) và Mục 6 (hồ sơ mã theo ngày niêm yết) | Overview mục E; phát hiện DMX niêm yết 06/08/2026 |
| 14 | Thêm G-9 (loại sự kiện theo trọng tâm toàn bài); mở rộng A24 cho bài giải thích diễn biến giá; A23 chỉ khi khối ngoại là trọng tâm | KB#VD sửa từ Cao / Tiêu cực (A23) sang TB / Trung lập (A24), 28/10/2026 |

---

## PHỤ LỤC C — ĐỐI CHIẾU 22 CASE CỦA KB (file test 20/10/2026)

Mục đích: kiểm tra v2 cho ra đúng nhãn Expected của KB (nhãn chuẩn). Cột "AI trả ra" trong file test là của một hệ thống khác, không dùng làm căn cứ.

| KB# | Mã | Bài (rút gọn) | Expected KB | Quy tắc v2 cho ra Expected | Khớp v2 |
|---|---|---|---|---|---|
| VD | FPT | Vì sao CP FPT giảm dù kinh doanh tốt | TB / Trung lập | A24: bài giải thích diễn biến giá, khối ngoại chỉ là 1 trong nhiều nguyên nhân, không có sự kiện mới; I-TL-d: áp lực khối ngoại, rủi ro AI/Mỹ/yen đặt cạnh KQKD đã công bố, AI Factory hòa vốn, P/E 12,5x | ✅ (sửa 28/10/2026 từ Cao / Tiêu cực) |
| 5 | FPT | FPT lãi > 2.700 tỷ Q3, kỷ lục | Cao / Tích cực | A01 | ✅ |
| 6 | FPT | FPT–NVIDIA mở rộng 10 lần dữ liệu giả lập | Thấp / Trung lập | A14, I-TL-d | ✅ |
| 7 | FPT | Vietcap điều chỉnh dự báo FPT | TB / Trung lập | A24 | ✅ |
| 8 | FPT | CP ngân hàng bị khối ngoại xả ~500 tỷ (có số FPT) | TB / Tiêu cực | R-TT-4, A23 | ✅ |
| 9 | FPT | FPT ra mắt 3 giải pháp AI | TB / Tích cực | A13 | ✅ |
| 10 | NVL | Gia hạn chào bán > 800 triệu CP | TB / Trung lập | A07, P-MOD-1 (gốc Cao → TB); I-TL-a | ✅ |
| 11 | NVL | Lãi vượt KH, 9 tháng chỉ bán mới 218 căn | Cao / Trung lập | A01; I-TL-a | ✅ |
| 12 | NVL | Vợ ông Bùi Thành Nhơn muốn bán CP | TB / Trung lập | A22, I-TL-f | ✅ |
| 13 | MSN | Lãi > 10.000 tỷ 9 tháng, vượt KH năm | Cao / Tích cực | A01 | ✅ |
| 14 | MSN | Nâng sở hữu MCH lên ~74,9% | TB / Tích cực | R-TT-3, A05 (~10.400 tỷ, dải TB của P-TH-05 — cần TTS MSN để xác nhận) | ✅ |
| 15 | MSN | Elmet mua 4,99% MSR | TB / Tích cực | R-TT-3, A04, P-MOD-3 | ✅ |
| 16 | MSN | MSR tạm ứng cổ tức 20% | TB / Trung lập | R-GT-a1, A03, I-TL-e | ✅ |
| 17 | HPG | Bán gần 5,5 triệu tấn HRC 9 tháng | Cao / Tích cực | A02/P-TH-06 (HRC +59% YoY) | ✅ |
| 18 | HPG | Bán 151.000 con heo, 87 triệu trứng Q3 | TB / Tích cực | R-TT-2, A02 (mảng không cốt lõi → TB) | ✅ |
| 19 | HPG | Góp vốn 8.000 tỷ vào chủ đầu tư siêu đô thị | Cao / Trung lập | A12, P-TH-05 (nghìn tỷ vào lĩnh vực mới); I-TL-a | ✅ |
| 20 | HPG | Con trai ông Long muốn mua 50 triệu CP HPG | TB / Tích cực | A21, sàn 3.4 | ✅ |
| 21 | HPG | Khối ngoại bán ròng 14 phiên, HPG hút > 100 tỷ | TB / Tích cực | A23 | ✅ |
| 22 | MWG | GDKHQ cổ tức 1.000đ/CP | TB / Tích cực | A09, P-TH-03 (sàn TB) | ✅ (thay ngưỡng v1) |
| 23 | MWG | Ông Đoàn Văn Hiểu Em bán 1 triệu CP MWG | TB / Trung lập | A22, I-TL-f, sàn 3.4 | ✅ |
| 24 | MWG | Thu 5,7 tỷ USD 9 tháng, BHX mới có lãi | Cao / Tích cực | A01 | ✅ |
| 25 | MWG | DMX mở ngành hàng AI & Robotics | TB / Trung lập | R-GT-a1 (DMX niêm yết 06/08/2026), P-MOD-2; I-TL-b | ✅ |

