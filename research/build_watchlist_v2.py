"""Build watchlist_v2.md + research/watchlist_labels_v2.csv from the hand labels below.

Labels: Claude, theo tieu_chi_v2.md, sau khi đọc toàn văn (research/watchlist_texts/).
Cột `src`: "kb" = trùng bài/sự kiện KB đã gán nhãn; "title" = không crawl được, gán theo tiêu đề.
"""

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TT, GT, KLQ = "Trực tiếp", "Gián tiếp", "Không liên quan"
CAO, TB, THAP = "Cao", "Trung bình", "Thấp"
POS, NEG, NEU = "Tích cực", "Tiêu cực", "Trung lập"

# id: (relevance, event, priority, impact, rules, reason, src, other_tickers)
L = {
 # ---------------- NVL ----------------
 "WL-001": (TT, "A06", TB, NEU, "R-TT-1; A06, P-TH-02, G-4, P-MOD-1; I-TL-a",
   "Bài phân tích đợt chào bán ~800,7 triệu CP (~33,3% CP lưu hành, VĐL 24.020 tỷ) đã công bố từ 21/9, không có thông tin mới nên hạ Cao → Trung bình. Pha loãng nhưng ~8.007 tỷ dùng trả nợ (≈11% dư nợ 72.911 tỷ) → Trung lập.", "", ""),
 "WL-002": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10; I-TL-f",
   "Diamond Properties (liên quan Chủ tịch) bán 2,58 triệu CP; nhóm gia đình còn 39,75%, vẫn trên ngưỡng 36% nên chưa thay đổi quyền phủ quyết → Trung bình, Trung lập.", "", ""),
 "WL-003": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10, P-MOD-1, P-SAN; I-TL-f",
   "Kết quả bán 2,58 triệu CP (7,53% → 7,43%) của giao dịch đã đăng ký; phiên tăng trần không phải căn cứ (G-1).", "", ""),
 "WL-004": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10, P-MOD-1, P-SAN; I-TL-f",
   "Diamond Properties bán 2,58 triệu CP lần thứ 3 trong năm, sở hữu còn 7,43%, không đổi quyền kiểm soát.", "", ""),
 "WL-005": (TT, "A30", THAP, NEU, "R-TT-1; G-4; I-TL-d",
   "Báo cáo tiến độ sử dụng vốn ESOP 2025 (đã dùng 461,4/487,5 tỷ, còn 26,1 tỷ): thủ tục hành chính, quy mô nhỏ; tin Diamond và chào bán chỉ là nhắc lại.", "", ""),
 "WL-006": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10, P-MOD-1, P-SAN; I-TL-f",
   "Như WL-003: kết quả bán 2,58 triệu CP; diễn biến tăng trần không phải căn cứ.", "", ""),
 "WL-007": (TT, "A35", THAP, NEU, "R-TT-1; A35, G-4; G-1",
   "Trọng tâm là phiên tăng trần 10.950đ, thanh khoản >70 triệu CP; chuyển đổi trái phiếu BNP và đợt chào bán là thông tin đã công bố.", "", ""),
 "WL-008": (TT, "A01", CAO, POS, "R-TT-1; A01, P-TH-01; I-YT-1",
   "LNST 9T ước >2.800 tỷ ≈ 1,5 lần kế hoạch năm; doanh thu Q3 +~200% YoY → Cao, Tích cực. Phần bác tin đồn là thông tin phụ.", "", ""),
 "WL-009": (TT, "A06", THAP, POS, "R-TT-1; A06, P-TH-02; I-YT-7",
   "Phát hành 1.737.080 CP chuyển đổi ~59 tỷ trái phiếu ≈ 0,07% CP lưu hành (<3%) → Thấp; giá chuyển đổi 34.000đ ≈ 3,3 lần thị giá 10.400đ (phát hành ≥ thị giá), giảm nợ → Tích cực.", "", ""),
 "WL-010": (TT, "A06", THAP, POS, "R-TT-1; A06, P-TH-02; I-YT-7",
   "Như WL-009: chuyển đổi 10 trái phiếu (~2,36 triệu USD) thành ~1,73 triệu CP ở giá 34.000đ.", "", ""),
 "WL-011": (TT, "A06", THAP, POS, "R-TT-1; A06, P-TH-02; I-YT-7",
   "Như WL-009 (bản tin gốc nghị quyết HĐQT ngày 6/10).", "", ""),
 "WL-012": (TT, "A01", CAO, POS, "R-TT-1; A01, P-TH-01; I-YT-1",
   "Như WL-008: LNST 9T >2.800 tỷ ≈ 1,5 lần KH năm, Q3 >1.100 tỷ.", "", ""),
 "WL-013": (TT, "A36", TB, NEU, "R-TT-1; A36; I-TL-a, G-2",
   "Novaland bác tin 'phá sản'; giả định lời bác bỏ là đúng (G-2). Giá giảm (−21% từ đầu tháng 9) không phải căn cứ.", "", ""),
 "WL-014": (TT, "A36", TB, NEU, "R-TT-1; A36; I-TL-a, G-2",
   "Thông cáo chính thức bác tin 'phá sản', 'mất khả năng hoạt động'; không có số liệu mới.", "", ""),
 "WL-015": (TT, "A36", TB, NEU, "R-TT-1; A36, G-6; I-TL-a, G-1",
   "Giá NVL −2,84% sau thông cáo bác tin đồn; sự kiện mới quan trọng nhất là lời bác bỏ (Trung bình), diễn biến giá không phải căn cứ.", "", ""),
 "WL-016": (TT, "A06", TB, NEU, "R-TT-1; A06, P-TH-02, P-MOD-1; I-TL-a",
   "Thông báo GDKHQ 30/9 và giá tham chiếu điều chỉnh 10.225đ của đợt chào bán 800,68 triệu CP (~33%) đã công bố 21/9 → cập nhật, hạ Cao → Trung bình; pha loãng vs trả nợ → Trung lập.", "", ""),
 "WL-017": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10; I-TL-f",
   "Diamond Properties đăng ký bán 2,7 triệu CP (7,536% → 7,424%), không đổi quyền kiểm soát.", "", ""),
 "WL-018": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10; I-TL-f",
   "Như WL-017 (đăng ký bán lần thứ 4); mức giảm ~40% của cổ phiếu không phải căn cứ.", "", ""),
 "WL-019": (TT, "A06", CAO, NEU, "R-TT-1; A06, P-TH-02; I-TL-a",
   "Công bố chính thức đợt chào bán (GCN UBCK 14/9): 800,7 triệu CP / ~2.402 triệu CP lưu hành ≈ 33,3% >10% → Cao; ~8.007 tỷ dùng trả nợ và nghĩa vụ quá hạn → Trung lập. Nếu KB coi đây là cập nhật của phương án ĐHĐCĐ đã thông qua thì hạ về Trung bình.", "", ""),
 "WL-020": (TT, "A06", CAO, NEU, "R-TT-1; A06, P-TH-02; I-TL-a",
   "Như WL-019 (5.953,3 tỷ trả gốc 13 mã trái phiếu, phần còn lại góp vốn 2 công ty con để trả trái phiếu).", "", ""),
 # ---------------- MSN ----------------
 "WL-021": (GT, "A03", TB, NEU, "R-GT-a1; A03, P-MOD-2; I-TL-e, I-TL-b",
   "Bài về MCH (MSN sở hữu ~69,4%): định hướng lợi ích cổ đông 20–25%/năm, chi trả tới 80% LNST, DT Q3 sơ bộ +16%. Không định lượng tác động lên MSN; cổ tức về mẹ là chuyển giao nội bộ → Trung lập.", "", ""),
 "WL-022": (TT, "A04", TB, POS, "R-TT-3; A04, G-4; I-YT-6",
   "MSN nhận ~350 triệu USD (225 triệu USD cổ tức MSR + 125 triệu USD bán 4,99% MSR cho Elmet); phần lớn là thông tin đã công bố → Trung bình; dòng tiền từ bên ngoài và giảm đòn bẩy → Tích cực.", "", ""),
 "WL-023": (TT, "A04", TB, POS, "R-TT-3; A04, G-4; I-YT-6", "Như WL-022.", "", ""),
 "WL-024": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-d",
   "KHÔNG CRAWL ĐƯỢC (investing.com từ chối kết nối) — gán theo tiêu đề: góc nhìn CTCK về MCH (công ty con có mã riêng). Cần đọc lại.", "title", ""),
 "WL-025": (GT, "A03", TB, NEU, "R-GT-a1; A03, P-MOD-2; I-TL-e, I-TL-b", "Như WL-021 (bản tiếng Anh).", "", ""),
 "WL-026": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7",
   "MSN (qua Lepus) đăng ký mua 73 triệu CP MCH ≈ 10.439 tỷ, nâng sở hữu 69,4% → 74,9% — cùng sự kiện KB#14 (Trung bình/Tích cực). Văn phong phản biện của bài không phải căn cứ (G-1).", "kb", ""),
 "WL-027": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-e",
   "MSR lập đỉnh 67.900đ và đề xuất tạm ứng cổ tức 50% (~5.500 tỷ): cổ tức về MSN là chuyển giao nội bộ (như KB#16); giá cổ phiếu không phải căn cứ.", "", ""),
 "WL-028": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b",
   "Khối ngoại bán ròng 9.594 tỷ cổ phiếu MCH (công ty con có mã riêng); MSN đi ngang; bài không nêu tác động lên MSN → Trung lập.", "",
   "NVL: Trực tiếp/Trung bình/Tích cực (R-TT-4, A23 — được mua ròng ~78 tỷ); FPT: Không liên quan (chỉ 'bán ròng hàng trăm tỷ', không có giá trị riêng)"),
 "WL-029": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b", "Như WL-028.", "",
   "NVL: Trực tiếp/Trung bình/Tích cực (A23 — mua ròng 77,9 tỉ); FPT: Trực tiếp/Trung bình/Tiêu cực (A23 — bán ròng 120,6 tỉ)"),
 "WL-030": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7, I-YT-6",
   "MSN mua thêm 73 triệu CP MCH; nguồn ~420 triệu USD (295 cổ tức MCH+MSR, 125 Elmet); Nợ vay ròng/EBITDA dự kiến 2,4 → 2,3 lần → Trung bình/Tích cực (KB#14).", "kb", ""),
 "WL-031": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7, I-YT-6", "Như WL-030.", "kb", ""),
 "WL-032": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7", "Như WL-030; kèm DT sơ bộ Q3 của MCH +16%.", "kb", ""),
 "WL-033": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7",
   "Lepus (công ty con ~98% của MSN) đăng ký mua 73 triệu CP MCH (5,584%), ~10.300 tỷ theo giá 141.000đ.", "kb", ""),
 "WL-034": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7",
   "Trùng bài KB#10 (MSN nâng sở hữu MCH lên ~74,9%) — nhãn KB.", "kb", ""),
 "WL-035": (TT, "A05", TB, POS, "R-TT-3; A05, P-TH-05; I-YT-7", "Như WL-034 (bản tin ĐTCK).", "kb", ""),
 "WL-036": (TT, "A24", TB, NEU, "R-TT-1; A24; I-TL-d",
   "HSBC (111.100đ) và J.P. Morgan (110.000đ) nâng giá mục tiêu MSN → khuyến nghị của tổ chức phân tích: Trung bình/Trung lập (như KB#7). KQKD 8T là thông tin đã công bố.", "", ""),
 "WL-037": (TT, "A04", TB, POS, "R-TT-3; A04, P-MOD-3; I-YT-6, I-YT-10",
   "Công ty con 100% của MSN hoàn tất bán 55,13 triệu CP MSR (4,99%) cho Elmet ~124,75 triệu USD (định giá MSR 2,5 tỷ USD), sở hữu 92,45% → 87,46% — như KB#15. Cổ tức MSR 5.000đ/CP là chuyển giao nội bộ.", "kb", ""),
 "WL-038": (TT, "A04", TB, POS, "R-TT-3; A04, P-MOD-3; I-YT-10",
   "MSN sẽ bán thêm tối đa 55,36 triệu CP MSR (5,01%) cho tổ chức với giá tương đương thương vụ Elmet; không định lượng tác động lên MSN → trần Trung bình.", "", ""),
 "WL-039": (TT, "A04", TB, POS, "R-TT-3; A04, P-MOD-3; I-YT-6, I-YT-10",
   "Elmet mua 4,99% MSR từ công ty con của MSN (~125 triệu USD, định giá 2,5 tỷ USD) — cùng sự kiện KB#15.", "kb", ""),
 "WL-040": (TT, "A04", TB, POS, "R-TT-3; A04, P-MOD-3; I-YT-6, I-YT-10", "Như WL-039.", "kb", ""),
 # ---------------- FPT ----------------
 "WL-041": (TT, "A24", TB, NEU, "R-TT-1; A24; I-TL-d",
   "Trùng dòng VD. Bài giải thích vì sao giá giảm, không có sự kiện mới: khối ngoại bán ròng (14.700 tỷ từ đầu năm) chỉ là 1 nguyên nhân; rủi ro AI, Mỹ +0,8%, yen (TCBS) đặt cạnh DT 8T +13,5%, LNTT +17,5% (đã công bố), AI Factory ~10.900 tỷ đã hòa vốn, P/E 12,5x → Trung bình/Trung lập.", "kb", ""),
 "WL-042": (TT, "A23", TB, NEG, "R-TT-1; A23; I-YT-8",
   "Bản tin 13/10: FPT về 56.300đ (đáy 52 tuần), khối ngoại bán ròng ~106,8 tỷ trong phiên → Trung bình/Tiêu cực.", "",
   "MWG, NVL: Không liên quan (chỉ có biến động giá trong danh sách)"),
 "WL-043": (TT, "A23", TB, NEG, "R-TT-1; A23, P-TH-09; I-YT-8",
   "Bản tin phiên nhiều mã: FPT bị bán ròng 107 tỷ, phiên thứ 11 liên tiếp; lũy kế 180 triệu CP/14.700 tỷ từ đầu năm nhưng chỉ là một phần của bản tin, không có mẫu số → Trung bình (chưa đạt ngưỡng Cao của P-TH-09). Chỉ thuật lại dòng tiền, không có mặt đối trọng → Tiêu cực (khác WL-041, như KB#8).", "",
   "MSN, HPG, MWG: Không liên quan (chỉ có tên trong danh sách)"),
 "WL-044": (TT, "A24", TB, NEU, "R-TT-1; A24; I-TL-d",
   "Bài định giá (P/E 12,5x vs trung vị 20,2x), giá mục tiêu Vietcap 90.300đ, đặt cạnh áp lực khối ngoại và rủi ro AI → Trung bình/Trung lập (KB#7, cùng dạng với WL-041).", "", ""),
 "WL-045": (TT, "A24", TB, NEU, "R-TT-1; A24; I-TL-d",
   "Cùng nội dung với WL-041 (khối ngoại bán ròng, rủi ro AI, KQKD 8T đã công bố, AI Factory, định giá) → Trung bình/Trung lập.", "kb", ""),
 "WL-046": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d",
   "MOU FPT–NAVER Cloud, 'không nêu giá trị tài chính hay thời hạn' → Thấp/Trung lập (như KB#6).", "", ""),
 "WL-047": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d", "Như WL-046.", "", ""),
 "WL-048": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d", "Như WL-046.", "", ""),
 "WL-049": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d", "Như WL-046.", "", ""),
 "WL-050": (TT, "A30", THAP, NEU, "R-TT-2; I-TL-d",
   "FPT Smart Cloud (không niêm yết riêng) nhận giải Top 5 Better Choice Awards — PR/giải thưởng, không lượng hóa.", "", ""),
 "WL-051": (KLQ, "A33", "", "", "R-KLQ-2",
   "KHÔNG CRAWL ĐƯỢC (investing.com từ chối kết nối) — gán theo tiêu đề 'Vietstock Daily: Sức ép chưa dứt?': bản tin thị trường chung. Cần đọc lại.", "title", ""),
 "WL-052": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d", "Như WL-046.", "", ""),
 "WL-053": (TT, "A02", TB, POS, "R-TT-1; A02, P-TH-06, G-4; I-YT-3",
   "Đơn hàng ký mới nước ngoài 8T 33.285 tỷ (+28,2%, <30%); DT Nhật +20,8%; mục tiêu 1 tỷ USD tại Nhật năm 2027; thương vụ Nippon Seiki không công bố giá trị. Số liệu 8T đã công bố → Trung bình/Tích cực.", "", ""),
 "WL-054": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d",
   "Toyota Tsusho NEXTY làm việc lần 2 về phân phối PMIC, chưa có hợp đồng/giá trị → Thấp/Trung lập.", "", ""),
 "WL-055": (TT, "A14", THAP, NEU, "R-TT-3; A14; I-TL-d", "Như WL-054.", "", ""),
 "WL-056": (GT, "A30", THAP, NEU, "R-GT-a1; I-TL-d",
   "Long Châu và FPT Shop thuộc FPT Retail (FRT, có mã riêng) nhận giải thưởng → không lượng hóa.", "", ""),
 "WL-057": (TT, "A30", THAP, NEU, "R-TT-1; I-TL-d", "Thông báo sự kiện FPT TRANSFORM 2026 (17/10) — PR.", "", ""),
 "WL-058": (GT, "A28", THAP, NEU, "R-GT-a1; A28; I-TL-d", "Bổ nhiệm TGĐ FPT Online (FOC, công ty con có mã riêng).", "", ""),
 "WL-059": (TT, "A08", TB, NEU, "R-TT-1; A08, P-TH-02; I-TL-d",
   "Phát hành 171 triệu CP thưởng tỷ lệ 10:1 (đúng 10%) → Trung bình/Trung lập.", "", ""),
 "WL-060": (TT, "A08", TB, NEU, "R-TT-1; A08, P-TH-02; I-TL-d", "Như WL-059 (VĐL 17.143 → 18.858 tỷ).", "", ""),
 # ---------------- HPG ----------------
 "WL-061": (TT, "A35", THAP, NEU, "R-TT-1; A35; G-1",
   "Phân tích kỹ thuật: HPG dưới MA200 gần 5 tháng, −12,17% từ đầu năm; dự báo LN Q3 của CTCK là bối cảnh.", "", ""),
 "WL-062": (TT, "A35", THAP, NEU, "R-TT-1; A35; G-1",
   "HPG đi ngang quanh 20.100đ gần 5 tháng; số liệu sản lượng là bối cảnh.", "", ""),
 "WL-063": (TT, "A02", CAO, POS, "R-TT-1; A02, P-TH-06; I-YT-3",
   "Q3 bán 3,8 triệu tấn (+54% YoY), HRC >2 triệu tấn (+64%); 9T 10,3 triệu tấn (+39%) → KPI cốt lõi ≥30% → Cao/Tích cực (cùng sự kiện KB#13).", "kb", ""),
 "WL-064": (TT, "A24", TB, NEU, "R-TT-1; A24, P-MOD-4; I-TL-d",
   "MBS khuyến nghị KHẢ QUAN, giá mục tiêu 32.000đ; bài 3 mã (HPG, VPB, VCG) → Trung bình/Trung lập.", "", ""),
 "WL-065": (TT, "A02", CAO, POS, "R-TT-1; A02, P-TH-06; I-YT-3", "Như WL-063.", "kb", ""),
 "WL-066": (TT, "A02", CAO, POS, "R-TT-1; A02, P-TH-06; I-YT-3", "Như WL-063.", "kb", ""),
 "WL-067": (TT, "A23", TB, POS, "R-TT-1; A23; I-YT-8",
   "Khối ngoại mua ròng HPG 128,14 tỷ, dẫn đầu chiều mua → Trung bình/Tích cực (như KB#17).", "kb",
   "NVL: Trực tiếp/Trung bình/Tích cực (A23 — mua ròng 18,03 tỷ); FPT: Trực tiếp/Trung bình/Tiêu cực (A23 — bán ròng 91,16 tỷ)"),
 "WL-068": (TT, "A02", CAO, POS, "R-TT-1; A02, P-TH-06, G-6; I-YT-3",
   "Có thông tin mới cùng ngày: sản lượng 9T 10,3 triệu tấn (+39%), HRC +59%; Hòa Phát tăng giá thép cây 100đ/kg và HRC ~10 USD/tấn. Diễn biến giá cổ phiếu không phải căn cứ.", "kb", ""),
 "WL-069": (TT, "A14", THAP, NEU, "R-TT-2; A14; I-TL-b",
   "Mục tiêu nâng lên 10 KCN trong 10 năm, BĐS chiếm 5–7% cơ cấu; chưa có vốn/hợp đồng cụ thể → Thấp/Trung lập.", "", ""),
 "WL-070": (GT, "A31", THAP, NEU, "R-GT-b; A31; I-TL-b",
   "Bản tin giá thép hằng ngày: quặng sắt 90,7 USD/tấn (thấp nhất từ 9/2024), thép Hòa Phát giữ 14.920đ/kg — biến số ngành, chiều tác động không rõ; tin định kỳ → Thấp (ĐX).", "", ""),
 "WL-071": (TT, "A17", THAP, NEU, "R-TT-1; A17, P-MOD-1; I-TL-b",
   "Buổi làm việc với tỉnh Đắk Lắk sau đề xuất dừng nghiên cứu dự án 86.000 tỷ; chưa có quyết định mới → cập nhật, Thấp/Trung lập.", "", ""),
 "WL-072": (TT, "A17", THAP, NEU, "R-TT-1; A17, P-MOD-1; I-TL-b", "Như WL-071.", "", ""),
 "WL-073": (TT, "A17", TB, NEU, "R-TT-1; A17, P-TH-12, G-4; I-TL-a",
   "Đề xuất dừng nghiên cứu tổ hợp gang thép 86.000 tỷ (6 triệu tấn/năm), mới chi ~200 tỷ, chuyển nguồn lực sang KCN Hòa Tâm và cảng Bãi Gốc → giai đoạn nghiên cứu → Trung bình; hai chiều (tránh rủi ro vốn lớn vs mất hướng tăng công suất) → Trung lập.", "", ""),
 "WL-074": (TT, "A17", TB, NEU, "R-TT-1; A17, P-TH-12; I-TL-a", "Như WL-073.", "", ""),
 "WL-075": (TT, "A12", TB, POS, "R-TT-2; A12, P-TH-05, P-MOD-1; I-YT-3",
   "Nhà máy ray và thép đặc biệt Dung Quất (>10.000 tỷ, 700.000 tấn/năm ≈ 4,4% công suất 16 triệu tấn) đạt ~70%, ra lò Q1/2027 — cập nhật tiến độ dự án đã công bố → Trung bình; đúng tiến độ, dòng sản phẩm mới → Tích cực.", "", ""),
 "WL-076": (TT, "A17", TB, NEU, "R-TT-1; A17, P-TH-12; I-TL-a",
   "Bản tin đầu tiên: Hòa Phát đề xuất không tiếp tục nghiên cứu dự án gang thép 86.000 tỷ, chuyển nguồn lực sang KCN Hòa Tâm; tỉnh chưa quyết định.", "", ""),
 "WL-077": (TT, "A12", TB, POS, "R-TT-2; A12, P-TH-05; I-YT-3",
   "Đề xuất mở rộng thêm 77 ha, +2 triệu tấn/năm (≈12,5% công suất 16 triệu tấn), vốn ~20.000 tỷ; còn vướng mặt bằng → Trung bình; mở rộng công suất → Tích cực (mới ở mức đề xuất).", "", ""),
 "WL-078": (GT, "A31", TB, NEU, "R-GT-b; A31; I-TL-b",
   "Hạn ngạch thép EU (HRC 415.000 tấn cho Việt Nam) — biến số ngành của HPG, bài không nêu tên HPG; HRC được đánh giá ít chịu áp lực, tôn mạ chịu áp lực → chiều với HPG không rõ.", "", ""),
 "WL-079": (TT, "A12", TB, POS, "R-TT-2; A12, P-TH-05, P-MOD-1; I-YT-3", "Như WL-075.", "", ""),
 "WL-080": (TT, "A12", TB, POS, "R-TT-2; A12, P-TH-05, P-MOD-1; I-YT-3", "Như WL-075 (chạy thử tháng 10/2026).", "", ""),
 # ---------------- MWG ----------------
 "WL-081": (GT, "A03", TB, NEU, "R-GT-a1; A03, P-MOD-2; I-TL-a",
   "DMX (niêm yết riêng từ 06/08/2026) trình TP kèm chứng quyền cho 15 lãnh đạo (tối đa 126,7 triệu CP @74.000đ), gắn điều kiện LN và giá CP 2026–2030.", "", ""),
 "WL-082": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-e",
   "DMX trình chính sách cổ tức ≥50% LNST, tạm ứng 2.000đ/CP (~2.535 tỷ) và TP 100 tỷ; cổ tức về MWG là chuyển giao nội bộ (như KB#16).", "", ""),
 "WL-083": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-e", "Như WL-082 (TP 100 tỷ để trả nợ MUFG 113,9 tỷ).", "", ""),
 "WL-084": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-e", "Như WL-082.", "", ""),
 "WL-085": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b",
   "DMX mở ngành hàng AI & Robotics (House of Future), chưa có số liệu — như KB#25. CEO DMX mua 732.000 CP DMX là giao dịch tại DMX.", "kb", ""),
 "WL-086": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b", "Như WL-085.", "kb", ""),
 "WL-087": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b", "Trùng bài KB#21 — nhãn KB.", "kb", ""),
 "WL-088": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b", "Như WL-085.", "kb", ""),
 "WL-089": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-b", "Như WL-085.", "kb", ""),
 "WL-090": (TT, "A31", TB, POS, "R-TT-4; A31, P-MOD-4; I-YT-1",
   "Bài ngành bán lẻ Q3: BHX 8T ~40.100 tỷ, DMX 8T 87.050 tỷ (+29%), biên gộp MWG Q2 22,2%; số liệu đã công bố, nhiều doanh nghiệp → Trung bình; chiều thuận lợi rõ → Tích cực.", "", ""),
 "WL-091": (TT, "A27", TB, NEU, "R-TT-1; A27; I-TL-a",
   "MWG không có tên trong 117 cổ phiếu được FTSE bổ sung, nhưng bài nêu yếu tố cơ bản bù trừ có số: BHX 8T +32%, tiền mặt ròng 34.569 tỷ → Trung lập.", "", ""),
 "WL-092": (GT, "A03", TB, POS, "R-GT-a1; A03; I-YT-10",
   "TopZone (chuỗi thuộc DMX): 180.000 đơn đặt trước iPhone 18 (gần gấp đôi năm trước), giao gần 20.000 máy ngày đầu → Gián tiếp, Trung bình; tài sản liên quan tăng trưởng → Tích cực. Bài mang tính PR.", "", ""),
 "WL-093": (GT, "A31", TB, POS, "R-GT-a1, R-GT-b; A31; I-YT-1",
   "Doanh thu iPhone 18 ngày đầu >1.500 tỷ toàn thị trường, TopZone ≥833 tỷ → chiều thuận lợi cho bán lẻ điện thoại.", "",
   "FPT: Gián tiếp/Thấp/Trung lập (FPT Shop thuộc FRT, ≥124 tỷ)"),
 "WL-094": (GT, "A03", TB, POS, "R-GT-a1; A03; I-YT-10", "Như WL-092.", "", ""),
 "WL-095": (GT, "A31", THAP, NEU, "R-GT-b; A31; I-TL-b",
   "Bài về mở bán iPhone 18 của các đại lý khác (Minh Tuấn, Di Động Việt), không có số liệu của MWG/DMX → Thấp/Trung lập.", "", ""),
 "WL-096": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-e", "DMX triệu tập ĐHĐCĐ bất thường 29/10 (cổ tức tiền mặt, TP kèm chứng quyền).", "", ""),
 "WL-097": (GT, "A03", TB, NEU, "R-GT-a1; A03; I-TL-e", "Như WL-096; KQKD H1 của DMX là bối cảnh.", "", ""),
 "WL-098": (TT, "A01", CAO, POS, "R-TT-1; A01, P-TH-01; I-YT-1",
   "DT 8T 129.431 tỷ (+30% YoY), 70% kế hoạch năm → Cao/Tích cực.", "", ""),
 "WL-099": (TT, "A02", CAO, POS, "R-TT-2; A02, P-TH-06; I-YT-3",
   "Bách Hóa Xanh (không niêm yết riêng): DT 8T ~40.100 tỷ (+~32%), >1.000 cửa hàng mở mới có lãi hoạt động → KPI cốt lõi ≥30% → Cao/Tích cực.", "", ""),
 "WL-100": (TT, "A22", TB, NEU, "R-TT-1; A22, P-TH-10; I-TL-f",
   "TV HĐQT Đoàn Văn Hiểu Em đăng ký bán 1 triệu CP (0,15% → 0,09%) → Trung bình/Trung lập (như KB#23).", "kb", ""),
}

HINT = {"POSITIVE": POS, "NEGATIVE": NEG, "NEUTRAL": NEU}
ROW = re.compile(r"\| (WL-\d+) \| ([\d-]+) \| ([^|]+) \| \[(.+?)\]\((.+?)\) \| ([^|]*) \| (\w+) \| ([^|]*) \|")
TICKER_OF = {range(1, 21): "NVL", range(21, 41): "MSN", range(41, 61): "FPT", range(61, 81): "HPG", range(81, 101): "MWG"}


def ticker_for(wl: str) -> str:
    n = int(wl[3:])
    return next(t for r, t in TICKER_OF.items() if n in r)


def main() -> None:
    src_rows = {m[1]: m for m in ROW.finditer((ROOT / "watchlist.md").read_text(encoding="utf-8"))}
    assert len(src_rows) == 100 and set(src_rows) == set(L), set(src_rows) ^ set(L)

    records = []
    for wl in sorted(L):
        rel, ev, pri, imp, rules, reason, src, others = L[wl]
        m = src_rows[wl]
        records.append(dict(id=wl, ticker=ticker_for(wl), date=m[2], source=m[3].strip(), title=m[4], url=m[5],
                            relevance=rel, event_type=ev, priority=pri, impact=imp, rules=rules, reason=reason,
                            old_hint=HINT.get(m[7], m[7]), cluster=m[8].strip(), src=src, other_tickers=others))

    with open(ROOT / "research" / "watchlist_labels_v2.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

    changed = [r for r in records if r["impact"] and r["impact"] != r["old_hint"]]
    out = ["# Watchlist — đánh giá lại 100 bài theo tiêu chí v2", "",
           "Đánh giá: Claude, ngày 2026-10-28, theo `tieu_chi_v2.md`, sau khi crawl và đọc toàn văn "
           "(`research/watchlist_texts/`). Bản gốc `watchlist.md` giữ nguyên; cột `Hint cũ` là `impact_hint` trong bản gốc.",
           "", "**Ghi chú nguồn nhãn:** 🅺 = trùng bài/sự kiện KB đã gán nhãn, theo nhãn KB · "
           "⚠️ = không crawl được, gán theo tiêu đề, cần đọc lại.", "",
           "## Tổng quan", "",
           "| | Cao | Trung bình | Thấp | Tích cực | Tiêu cực | Trung lập | Gián tiếp | Không liên quan | Đổi Ảnh hưởng so với hint cũ |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for t in ["NVL", "MSN", "FPT", "HPG", "MWG", "Tổng"]:
        rs = records if t == "Tổng" else [r for r in records if r["ticker"] == t]
        p, i, rel = Counter(r["priority"] for r in rs), Counter(r["impact"] for r in rs), Counter(r["relevance"] for r in rs)
        ch = sum(1 for r in rs if r in changed)
        out.append(f"| **{t}** | {p[CAO]} | {p[TB]} | {p[THAP]} | {i[POS]} | {i[NEG]} | {i[NEU]} | {rel[GT]} | {rel[KLQ]} | {ch}/{len(rs)} |")

    moves = Counter((r["old_hint"], r["impact"]) for r in changed)
    out += ["", "**Hint cũ → nhãn v2 (các bài đổi Ảnh hưởng):** " +
            ", ".join(f"{a} → {b}: {n}" for (a, b), n in moves.most_common()), ""]

    for t in ["NVL", "MSN", "FPT", "HPG", "MWG"]:
        out += [f"## {t}", "", "| ID | Ngày | Tiêu đề | Relevance | Loại | Priority | Ảnh hưởng | Hint cũ | Quy tắc | Lý giải |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for r in (r for r in records if r["ticker"] == t):
            mark = {"kb": " 🅺", "title": " ⚠️"}.get(r["src"], "")
            hint = r["old_hint"] if r["impact"] == r["old_hint"] else f"~~{r['old_hint']}~~"
            reason = r["reason"] + (f" **Mã khác:** {r['other_tickers']}" if r["other_tickers"] else "")
            out.append(f"| {r['id']}{mark} | {r['date']} | [{r['title']}]({r['url']}) | {r['relevance']} | {r['event_type']} | "
                       f"{r['priority'] or '—'} | {r['impact'] or '—'} | {hint} | {r['rules']} | {reason} |")
        out.append("")

    (ROOT / "watchlist_v2.md").write_text("\n".join(out), encoding="utf-8")
    print(f"{len(records)} bài; đổi Ảnh hưởng so với hint cũ: {len(changed)}")
    print(moves.most_common())


if __name__ == "__main__":
    main()
