"""Node `extract`: one Claude call per article -> ArticleFacts."""

from functools import lru_cache
from pathlib import Path

from . import config, llm
from .catalog import CATALOG
from .profiles import load_profiles
from .schemas import Article, ArticleFacts

CRITERIA_PATH = Path(__file__).resolve().parent.parent / "tieu_chi_v2.md"

INSTRUCTIONS = """Bạn là chuyên viên phân tích tin tức chứng khoán Việt Nam. Nhiệm vụ: đọc một bài báo và TRÍCH XUẤT DỮ KIỆN có cấu trúc để hệ thống quy tắc phía sau gán nhãn. Bạn KHÔNG gán Priority hay Ảnh hưởng.

Nguyên tắc:
- Chỉ dùng thông tin có trong bài. Không thêm kiến thức ngoài bài, trừ việc nhận diện thực thể bằng hồ sơ mã bên dưới.
- Mỗi con số phải kèm `quote` là cụm trích NGUYÊN VĂN từ bài (giữ nguyên dấu chấm/phẩy, đơn vị) chứa con số đó.
- Quy đổi `value` về đơn vị gốc: tiền về VND đầy đủ (8.007 tỷ đồng = 8007000000000; 125 triệu USD giữ đơn vị USD và ghi unit="USD"), số cổ phiếu về số cổ phiếu, phần trăm là số thường (33,3% → 33.3). Chỉ dùng metric "*_vnd" khi giá trị là VND.
- Số âm cho giảm/bán ròng (khối ngoại bán ròng 107 tỷ → foreign_net_vnd = -107000000000).
- Các chỉ tiêu phần trăm (revenue_growth_pct, npat_growth_pct, plan_completion_pct, dividend_yield_pct, payout_pct, issue_pct, kpi_yoy_pct...): CHỈ điền khi bài NÊU SẴN con số phần trăm đó; không tự tính từ số tuyệt đối. Bài chỉ có số tuyệt đối (VD lãi 2.800 tỷ, cùng kỳ lỗ) thì bỏ trống chỉ tiêu phần trăm.
- LIỆT KÊ ĐẦY ĐỦ mọi sự kiện/thông tin về các mã watchlist có trong bài, mỗi thông tin có thể đứng riêng thành một tin là một event: sự kiện chính, chi tiết/số liệu đi kèm, thông tin được đặt cạnh để so sánh hoặc bù trừ, nhận định của CTCK, bối cảnh và số liệu nhắc lại. KHÔNG gộp, KHÔNG bỏ bớt và KHÔNG cần quyết định event nào là chính: bước sau sẽ xác định ranh giới và vai trò của từng event. Mỗi event giữ số liệu và câu trích của riêng nó. Đánh dấu `is_new_info=false` cho phần bối cảnh/nhắc lại; `is_update_of_announced_event=true` khi bài chỉ cập nhật tiến độ/thủ tục (gia hạn, chốt quyền, ngày GDKHQ, kết quả giao dịch đã đăng ký) của sự kiện đã công bố trước đó.
- Chỉ đặt các cờ ngữ nghĩa (control_change, intra_group_transfer, offsetting_factor, ...) = true khi bài có căn cứ rõ ràng.
- `subject_entity`: dùng đúng tên thực thể trong hồ sơ mã nếu khớp (VD "Điện Máy Xanh", "Masan High-Tech Materials").

Vai trò của mã trong `ticker_mentions` (chỉ liệt kê các mã thuộc watchlist có xuất hiện trực tiếp hoặc qua thực thể trong hồ sơ):
- subject: chính công ty, công ty con/thương hiệu/dự án của nó, lãnh đạo, cổ đông chủ chốt hoặc người liên quan là chủ thể sự kiện. Nếu chủ thể là một thực thể trong hồ sơ, ghi tên thực thể đó vào `via_entity`.
- party: công ty (hoặc công ty con) là một bên giao dịch (mua/bán/góp vốn/đối tác), kể cả khi tài sản giao dịch là cổ phần của công ty có mã riêng. Ghi thực thể bị giao dịch vào `via_entity` nếu có.
- data: bài nói về chủ đề khác (thị trường, ngành, mã khác) nhưng nêu SỐ LIỆU RIÊNG của mã (VD giá trị khối ngoại mua/bán mã đó).
- sector: nội dung chính là biến số ngành của mã (giá thép, hạn ngạch, sức mua bán lẻ...).
- ecosystem: bên liên quan chưa xác nhận quan hệ sở hữu, dự án liên danh.
- illustrative: nhắc tên minh họa/lịch sử, không có sự kiện mới.
- list_only: chỉ có tên trong danh sách liệt kê, không kèm số liệu riêng.
- macro: tin vĩ mô tổng quát.
- unclear: không xác định được.

Phân loại event_type theo bảng sau (chọn loại khớp nhất với THÔNG TIN MỚI của sự kiện). Đọc HẾT bài trước khi phân loại: loại sự kiện theo trọng tâm của toàn bài (G-9), không theo một đoạn hay một con số riêng lẻ:
{catalog}

Ghi chú phân loại:
- KQKD/sản lượng của chính mã: A01 nếu là doanh thu/lợi nhuận; A02 nếu là KPI vận hành (sản lượng, số cửa hàng, đơn hàng) hoặc KQKD của đơn vị không niêm yết riêng.
- Mọi hoạt động/KQKD/cổ tức/ngành hàng mới của công ty con CÓ MÃ RIÊNG mà mã mẹ không là một bên: A03.
- Gia hạn/điều chỉnh lịch đợt phát hành đã công bố: A07.
- Người nội bộ/người liên quan/cổ đông lớn mua: A21; bán: A22 (gồm cả đăng ký giao dịch).
- Bài chỉ có diễn biến giá, phân tích kỹ thuật, không có thông tin cơ bản mới: A35.
- Bài phân tích/giải thích diễn biến giá tổng hợp nhiều yếu tố (dòng tiền, KQKD đã công bố, rủi ro, nhận định CTCK/giới phân tích, định giá), không có sự kiện doanh nghiệp mới: A24, kể cả khi bài có nêu số khối ngoại. Chỉ dùng A23 khi khối ngoại là TRỌNG TÂM bài (bản tin dòng tiền/bản tin phiên).
- multi_ticker_equal = true khi bài phân tích từ 2 mã trở lên ngang nhau (VD danh mục khuyến nghị nhiều mã).
- conflicting_numbers: liệt kê nếu bài có số liệu mâu thuẫn nhau.
"""


@lru_cache
def system_blocks() -> list[str]:
    catalog = "\n".join(f"- {s.code}: {s.name}" for s in CATALOG.values())
    profiles = "\n\n".join(p.raw_yaml for _, p in sorted(load_profiles().items()))
    return [
        INSTRUCTIONS.format(catalog=catalog),
        "# Tiêu chí đánh giá (tham khảo để hiểu các khái niệm)\n\n" + CRITERIA_PATH.read_text(encoding="utf-8"),
        "# Hồ sơ mã (bản đồ thực thể, ngày niêm yết)\n\n" + profiles,
    ]


def article_message(article: Article) -> str:
    return (f"Watchlist: {', '.join(article.watchlist)}\n"
            f"Ngày đăng: {article.published_at.isoformat()}\n"
            f"Tiêu đề: {article.title}\n"
            f"URL: {article.url}\n\n"
            f"<bai_bao>\n{article.content}\n</bai_bao>")


def extract(article: Article) -> ArticleFacts:
    facts = llm.parse(system_blocks(), article_message(article), ArticleFacts, effort=config.EFFORT["extract"],
                      stage="extract")
    for ev in facts.events:  # a percentage metric must quote a percentage from the article (no computed %)
        for f in ev.figures:
            if f.metric.endswith("_pct") and "%" not in f.quote and "phần trăm" not in f.quote.lower():
                f.metric = "other"
    watch = {t.upper() for t in article.watchlist}
    seen, mentions = set(), []
    for m in facts.ticker_mentions:
        m.ticker = m.ticker.upper().strip()
        if m.ticker in watch and m.ticker not in seen:
            seen.add(m.ticker)
            mentions.append(m)
    facts.ticker_mentions = mentions
    return facts
