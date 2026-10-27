"""Data contracts for the news-evaluation pipeline.

All monetary values are in VND (absolute, e.g. 8.007 tỷ = 8_007_000_000_000),
share counts in shares, percentages as plain numbers (33.3 means 33.3%).
"""

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Relevance(str, Enum):
    TT = "Trực tiếp"
    GT = "Gián tiếp"
    KLQ = "Không liên quan"


class Priority(str, Enum):
    THAP = "Thấp"
    TB = "Trung bình"
    CAO = "Cao"

    @property
    def rank(self) -> int:
        return {"Thấp": 0, "Trung bình": 1, "Cao": 2}[self.value]

    @classmethod
    def from_rank(cls, rank: int) -> "Priority":
        return [cls.THAP, cls.TB, cls.CAO][max(0, min(2, rank))]


class Impact(str, Enum):
    TICH_CUC = "Tích cực"
    TIEU_CUC = "Tiêu cực"
    TRUNG_LAP = "Trung lập"


class Article(BaseModel):
    title: str
    url: str = ""
    published_at: date
    content: str
    watchlist: list[str] = ["NVL", "MSN", "FPT", "HPG", "MWG"]


# ---------------------------------------------------------------------------
# Facts extracted by Claude (node `extract`)
# ---------------------------------------------------------------------------

MetricKey = Literal[
    "revenue_growth_pct",       # tăng trưởng doanh thu YoY (%), âm nếu giảm
    "npat_growth_pct",          # tăng trưởng LNST/LNTT YoY (%), âm nếu giảm
    "plan_completion_pct",      # % hoàn thành kế hoạch năm (>100 = vượt)
    "issue_shares",             # số CP phát hành / chào bán / chuyển đổi
    "issue_pct",                # % pha loãng so với CP lưu hành, nếu bài nêu
    "shares_outstanding",       # số CP lưu hành bài nêu
    "charter_capital_vnd",      # vốn điều lệ trước sự kiện (VND)
    "dps_vnd",                  # cổ tức tiền mặt mỗi CP (VND)
    "dividend_yield_pct",
    "payout_pct",               # tỷ lệ chi trả / LNST (%)
    "share_price_vnd",          # thị giá bài nêu
    "contract_value_vnd",
    "backlog_growth_pct",
    "investment_value_vnd",     # vốn đầu tư / góp vốn / giá trị M&A
    "transaction_value_vnd",    # giá trị giao dịch cổ phần (mua/bán)
    "project_value_vnd",        # tổng vốn dự án bị dừng/hủy
    "capacity_increase_pct",
    "kpi_yoy_pct",              # sản lượng, số cửa hàng, đơn hàng YoY (%)
    "foreign_net_vnd",          # khối ngoại mua(+)/bán(-) ròng riêng cho mã
    "foreign_cum_pct_shares",   # lũy kế bán/mua ròng theo % CP lưu hành
    "overdue_debt_vnd",
    "ownership_after_pct",      # tỷ lệ sở hữu sau giao dịch
    "other",
]


class Figure(BaseModel):
    metric: MetricKey
    value: float
    unit: str = Field(description="VND, cổ phiếu, %, tấn, ... đúng như đã quy đổi")
    quote: str = Field(description="Câu/cụm trích NGUYÊN VĂN từ bài chứa con số")


EventType = Literal[
    "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10",
    "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18", "A19", "A20",
    "A21", "A22", "A23", "A24", "A25", "A26", "A27", "A28", "A29", "A30",
    "A31", "A32", "A33", "A34", "A35", "A36",
]


class EventFact(BaseModel):
    event_id: str
    event_type: EventType
    description: str = Field(description="1 câu mô tả sự kiện, đủ để hiểu khi đọc riêng (nêu chủ thể và nội dung chính)")
    subject_entity: str = Field(description="Thực thể là chủ thể sự kiện, đúng tên trong hồ sơ mã nếu có")
    parties: list[str] = Field(default_factory=list, description="Các bên tham gia (mua, bán, đối tác, nhận vốn)")
    is_new_info: bool = Field(description="False nếu chỉ là bối cảnh/nhắc lại thông tin đã công bố")
    is_update_of_announced_event: bool = Field(
        description="Bài chỉ cập nhật tiến độ/thủ tục của sự kiện đã công bố (gia hạn, chốt quyền, GDKHQ...)")
    update_changes_terms: bool = Field(
        default=False, description="Bản cập nhật đổi giá/khối lượng ≥20%/hủy sự kiện")
    figures: list[Figure] = Field(default_factory=list)
    # Cờ ngữ nghĩa dùng cho quy tắc (chỉ đặt True khi bài có căn cứ rõ)
    core_segment: bool = Field(default=True, description="Thuộc mảng kinh doanh cốt lõi/trọng yếu của mã")
    new_business_line: bool = Field(default=False, description="Đầu tư vào lĩnh vực/dòng sản phẩm mới")
    control_change: bool = Field(default=False, description="Giao dịch làm thay đổi quyền kiểm soát hoặc vượt/xuống ngưỡng 36/50/65%")
    parent_impact_quantified: bool = Field(default=False, description="Bài định lượng tác động lên công ty mẹ (LN hợp nhất, nợ, EPS, dòng tiền về mẹ)")
    intra_group_transfer: bool = Field(default=False, description="Dòng tiền chỉ di chuyển giữa các đơn vị hợp nhất")
    proceeds_for_debt: bool = Field(default=False, description="Tiền huy động dùng chủ yếu để trả nợ")
    dividend_cut: bool = Field(default=False, description="Cổ tức giảm/hoãn/chuyển sang cổ phiếu")
    performance_conditions: bool = Field(default=False, description="ESOP/chứng quyền gắn điều kiện hiệu quả rõ ràng")
    offsetting_factor: bool = Field(default=False, description="Bài nêu yếu tố bất lợi/thuận lợi ngược chiều ở quy mô tương đương")
    material_project_with_numbers: bool = Field(default=False, description="Dự án trọng yếu kèm số lượng sản phẩm cụ thể")
    affects_main_market: bool = Field(default=False, description="Thuế/phạt/rào cản ảnh hưởng thị trường chính")
    foreign_cumulative_focus: bool = Field(default=False, description="Bài tập trung vào dòng vốn ngoại lũy kế nhiều phiên")


TickerRole = Literal[
    "subject",       # mã/đơn vị của mã/lãnh đạo, cổ đông chủ chốt là chủ thể
    "party",         # mã (hoặc cty con không niêm yết) là một bên giao dịch
    "data",          # bài rộng hơn nhưng nêu số liệu riêng của mã
    "sector",        # nội dung chính là biến số ngành của mã
    "ecosystem",     # bên liên quan chưa xác nhận sở hữu, dự án liên danh
    "illustrative",  # nhắc tên minh họa/lịch sử
    "list_only",     # chỉ có tên trong danh sách liệt kê
    "macro",         # tin vĩ mô tổng quát
    "unclear",
]


class TickerMention(BaseModel):
    ticker: str
    role: TickerRole
    via_entity: str = Field(default="", description="Tên thực thể trong hồ sơ mã mà bài nhắc tới (nếu bài nói qua công ty con/thương hiệu)")
    event_ids: list[str] = Field(default_factory=list)


class ArticleFacts(BaseModel):
    events: list[EventFact]
    ticker_mentions: list[TickerMention]
    multi_ticker_equal: bool = Field(default=False, description="Bài phân tích ≥2 mã ngang nhau (danh mục khuyến nghị...)")
    conflicting_numbers: list[str] = Field(default_factory=list, description="Mô tả các số liệu mâu thuẫn trong bài")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

# Role of an extracted event in the article's story about one ticker (event boundaries, judged by Jev).
ROLE_FOCUS, ROLE_DETAIL, ROLE_OFFSET, ROLE_OTHER, ROLE_BACKGROUND = (
    "Trọng tâm", "Chi tiết của trọng tâm", "Ngược chiều", "Tin khác", "Bối cảnh")


class Evidence(BaseModel):
    quote: str
    metric: str = ""


class Reasons(BaseModel):
    relevance_reason: str
    priority_reason: str
    impact_reason: str


class TickerResult(BaseModel):
    ticker: str
    relevance: Relevance
    priority: Priority | None = None
    priority_confidence: float = 1.0
    impact: Impact | None = None
    impact_confidence: float = 1.0
    event_type: str = ""
    relevance_rule_ids: list[str] = Field(default_factory=list)
    priority_rule_ids: list[str] = Field(default_factory=list)
    impact_rule_ids: list[str] = Field(default_factory=list)
    computed: dict[str, str] = Field(default_factory=dict, description="Tỷ lệ do Python tính, dạng đã định dạng")
    evidence: list[Evidence] = Field(default_factory=list)
    relevance_reason: str = ""
    priority_reason: str = ""
    impact_reason: str = ""
    flags: list[str] = Field(default_factory=list)
    scores: dict[str, dict] = Field(default_factory=dict, description="Điểm Jev theo câu hỏi (jev_scorecard)")

    @property
    def rule_ids(self) -> list[str]:
        return self.relevance_rule_ids + self.priority_rule_ids + self.impact_rule_ids
