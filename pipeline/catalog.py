"""Event catalog (tieu_chi_v2 Phụ lục A) and short rule descriptions.

`threshold` names a function in rules.THRESHOLDS; `impact` is either a fixed
Impact, the name of a handler in rules.IMPACT_HANDLERS, or "DM" (delegate to
the DecisionModel).
"""

from dataclasses import dataclass

from .schemas import Impact, Priority

TB, CAO, THAP = Priority.TB, Priority.CAO, Priority.THAP
POS, NEG, NEU = Impact.TICH_CUC, Impact.TIEU_CUC, Impact.TRUNG_LAP


@dataclass(frozen=True)
class EventSpec:
    code: str
    name: str
    priority: Priority | None          # default when no threshold applies
    threshold: str | None = None       # key in rules.THRESHOLDS
    floor_tb: bool = False             # Mục 3.4
    impact: Impact | str = "DM"
    impact_rule: str = ""              # rule id cited when impact is fixed


CATALOG: dict[str, EventSpec] = {s.code: s for s in [
    EventSpec("A01", "KQKD của mã", CAO, "results", impact="results"),
    EventSpec("A02", "KPI vận hành / KQKD của mã hoặc đơn vị không niêm yết riêng", TB, "kpi", impact="kpi"),
    EventSpec("A03", "Hoạt động/KQKD/cổ tức của công ty con có mã riêng", TB, impact="subsidiary"),
    EventSpec("A04", "Mã mẹ bán cổ phần công ty con có mã riêng cho bên ngoài", TB, "transaction", impact=POS, impact_rule="I-YT-6"),
    EventSpec("A05", "Mã mẹ mua thêm cổ phần công ty con có mã riêng", TB, "investment", impact=POS, impact_rule="I-YT-7"),
    EventSpec("A06", "Phát hành cho cổ đông hiện hữu", CAO, "issuance", impact="issuance"),
    EventSpec("A07", "Gia hạn/điều chỉnh lịch đợt phát hành đã công bố", CAO, "issuance", impact=NEU, impact_rule="I-TL-a"),
    EventSpec("A08", "Cổ phiếu thưởng / chia tách", TB, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A09", "Cổ tức tiền mặt", TB, "dividend", floor_tb=True, impact="dividend"),
    EventSpec("A10", "ESOP / chứng quyền thưởng cho lãnh đạo", TB, "issuance", impact="esop"),
    EventSpec("A11", "Hợp đồng ký mới", TB, "contract", impact=POS, impact_rule="I-YT-3"),
    EventSpec("A12", "M&A, góp vốn, đầu tư lớn", TB, "investment", impact="DM"),
    EventSpec("A13", "Ra mắt sản phẩm/dịch vụ thương mại thuộc mảng cốt lõi", TB, floor_tb=True, impact=POS, impact_rule="I-YT-3"),
    EventSpec("A14", "Hợp tác kỹ thuật/MOU/dữ liệu không có giá trị thương mại", THAP, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A15", "Tiến triển pháp lý dự án", TB, "legal", impact=POS, impact_rule="I-YT-5"),
    EventSpec("A16", "Thuế/phạt/rào cản thương mại đã ban hành", TB, "penalty", impact=NEG, impact_rule="I-YT-5"),
    EventSpec("A17", "Dừng/hủy dự án", TB, "project_stop", impact=NEG, impact_rule="I-YT-3"),
    EventSpec("A18", "Chậm trả gốc/lãi (mã hoặc công ty con hợp nhất)", CAO, impact=NEG, impact_rule="I-YT-6"),
    EventSpec("A19", "Chậm trả tại đơn vị hệ sinh thái chưa xác nhận sở hữu", TB, impact=NEG, impact_rule="I-YT-6"),
    EventSpec("A20", "Ý kiến kiểm toán nhấn mạnh hoạt động liên tục", CAO, impact="DM"),
    EventSpec("A21", "Người nội bộ/người liên quan/cổ đông lớn mua", TB, "insider", floor_tb=True, impact=POS, impact_rule="I-YT-8"),
    EventSpec("A22", "Người nội bộ/người liên quan/cổ đông lớn bán", TB, "insider", floor_tb=True, impact="insider_sell"),
    EventSpec("A23", "Khối ngoại mua/bán ròng có giá trị riêng cho mã, khối ngoại là trọng tâm bài (bản tin dòng tiền/phiên)", TB, "foreign", floor_tb=True, impact="foreign"),
    EventSpec("A24", "Khuyến nghị/dự báo của CTCK; bài phân tích/giải thích diễn biến giá tổng hợp nhiều yếu tố, không có sự kiện mới", TB, floor_tb=True, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A25", "Vào chỉ số toàn cầu", CAO, impact=POS, impact_rule="I-YT-8"),
    EventSpec("A26", "Vào chỉ số nội địa / dự báo dòng vốn", TB, impact=POS, impact_rule="I-YT-8"),
    EventSpec("A27", "Bị loại / nguy cơ loại / không được thêm vào rổ", TB, impact="index_out"),
    EventSpec("A28", "Bổ nhiệm nhân sự đơn vị con không cốt lõi", THAP, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A29", "Bổ nhiệm nhiều đơn vị / đơn vị chiến lược", TB, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A30", "Cải tiến vận hành nhỏ", THAP, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A31", "Tin ngành có chiều tác động rõ", TB, impact="DM"),
    EventSpec("A32", "Tin vĩ mô có nêu tên mã kèm phân tích riêng", TB, impact="DM"),
    EventSpec("A33", "Tin vĩ mô tổng quát", None, impact=NEU),
    EventSpec("A34", "Nhắc tên minh họa / khoản đầu tư lịch sử", THAP, impact=NEU, impact_rule="I-TL-d"),
    EventSpec("A35", "Chỉ có diễn biến giá / phân tích kỹ thuật", THAP, impact=NEU, impact_rule="G-1"),
    EventSpec("A36", "Tin đồn kèm bác bỏ chính thức", TB, impact=NEU, impact_rule="I-TL-a"),
]}

# Short descriptions, given to the writer so it can cite rules correctly.
RULES: dict[str, str] = {
    "G-1": "Không dùng văn phong, tiêu đề hay diễn biến giá làm căn cứ",
    "G-4": "Chấm theo thông tin mới của bài",
    "G-5": "Chấm theo góc nhìn của mã đang xét",
    "G-6": "Bài nhiều sự kiện mới: không xác định được trọng tâm thì lấy sự kiện có Priority cao nhất",
    "G-8": "Mẫu số lấy từ bài, nếu không có thì từ hồ sơ mã tại ngày đăng",
    "G-9": "Loại sự kiện theo trọng tâm của toàn bài, không theo một đoạn/con số riêng lẻ",
    "R-TT-1": "Bài nói về chính công ty, lãnh đạo/cổ đông chủ chốt hoặc cổ phiếu của công ty",
    "R-TT-2": "Bài nói về công ty con/thương hiệu/dự án không niêm yết riêng",
    "R-TT-3": "Công ty là một bên của sự kiện (mua/bán/góp vốn/đối tác)",
    "R-TT-4": "Bài rộng hơn nhưng nêu số liệu riêng của mã",
    "R-GT-a1": "Bài nói về công ty con/liên kết có mã riêng, mã đang xét không là một bên",
    "R-GT-a2": "Dự án liên danh hoặc bên liên quan chưa xác nhận sở hữu",
    "R-GT-a3": "Mã chỉ được nhắc minh họa/lịch sử",
    "R-GT-b": "Nội dung chính là biến số ngành của mã",
    "R-KLQ-1": "Mã chỉ xuất hiện trong danh sách liệt kê, không kèm số liệu riêng",
    "R-KLQ-2": "Tin vĩ mô tổng quát, không phân tích riêng mã",
    "P-TH-01": "Ngưỡng KQKD: Cao nếu DT tăng/giảm >10% hoặc LN >15% hoặc vượt/hụt kế hoạch năm",
    "P-TH-02": "Ngưỡng phát hành: Cao nếu >10% CP lưu hành; 3–10% (gồm đúng 10%) là Trung bình",
    "P-TH-03": "Cổ tức tiền mặt: Cao nếu lợi suất ≥6% hoặc chi trả ≥60% LNST; còn lại Trung bình",
    "P-TH-04": "Hợp đồng: Cao nếu ≥10% DT TTM hoặc backlog +≥20%",
    "P-TH-05": "Đầu tư: Cao nếu >10% TTS, >20% VCSH, công suất +>20% hoặc nghìn tỷ vào lĩnh vực mới",
    "P-TH-06": "KPI vận hành: Cao nếu ≥30% YoY tại mảng trọng yếu",
    "P-TH-08": "Chỉ số: Cao nếu vào/ra chỉ số toàn cầu",
    "P-TH-09": "Khối ngoại: Trung bình; Cao nếu lũy kế lớn có mẫu số và là trọng tâm bài",
    "P-TH-10": "Giao dịch nội bộ: Trung bình; Cao nếu thay đổi quyền kiểm soát",
    "P-TH-11": "Pháp lý dự án: Cao nếu dự án trọng yếu kèm số lượng cụ thể",
    "P-TH-12": "Dừng dự án: theo quy mô vốn dự án như P-TH-05",
    "P-MOD-1": "Bản cập nhật của sự kiện đã công bố: hạ 1 bậc",
    "P-MOD-2": "Relevance Gián tiếp: trần Trung bình",
    "P-MOD-3": "Tin công ty con có mã riêng chưa định lượng tác động lên mã mẹ: trần Trung bình",
    "P-MOD-4": "Bài đa mã: mặc định Trung bình",
    "P-MOD-5": "Loại sự kiện quan trọng nhưng thiếu số để lượng hóa: tối đa Trung bình",
    "P-SAN": "Sàn Trung bình cho cổ tức tiền mặt, giao dịch nội bộ, khối ngoại, khuyến nghị CTCK, ra mắt sản phẩm",
    "P-TH-07": "Nợ/thanh khoản: Cao nếu chậm trả có số và đối chiếu tiền mặt",
    "I-YT-1": "Yếu tố doanh thu/lợi nhuận",
    "I-YT-2": "Yếu tố chi phí & biên",
    "I-YT-3": "Yếu tố tăng trưởng & mở rộng",
    "I-YT-4": "Yếu tố vị thế cạnh tranh",
    "I-YT-5": "Yếu tố pháp lý",
    "I-YT-6": "Yếu tố thanh khoản & nợ / huy động vốn từ bên ngoài",
    "I-YT-7": "Yếu tố lợi ích cổ đông hiện hữu",
    "I-YT-8": "Yếu tố dòng vốn & niềm tin (chỉ số, khối ngoại, người nội bộ mua)",
    "I-YT-9": "Yếu tố công bố thông tin & quản trị",
    "I-YT-10": "Yếu tố định giá tài sản liên quan",
    "I-TL-a": "Trung lập: hai chiều nội tại, không lượng hóa tác động ròng",
    "I-TL-b": "Trung lập: thiếu số liệu xác định hướng",
    "I-TL-c": "Trung lập: hướng không đồng nhất giữa các mã",
    "I-TL-d": "Trung lập: sự kiện kỹ thuật/hành chính, khuyến nghị CTCK, hợp tác không có giá trị thương mại",
    "I-TL-e": "Trung lập: chuyển giao nội bộ tập đoàn",
    "I-TL-f": "Trung lập: người nội bộ bán, không thay đổi quyền kiểm soát",
}

for _code, _spec in CATALOG.items():
    RULES.setdefault(_code, _spec.name)
