# Pipeline đánh giá tin tức chứng khoán — Thiết kế

Ngày: 2026-10-28 · Trạng thái: chờ duyệt
Tiêu chí áp dụng: [tieu_chi_v2.md](../../../tieu_chi_v2.md)

## 1. Mục tiêu và phạm vi

Một pipeline Python để **hệ thống chính** (InvestMate) gọi vào. Pipeline nhận một bài báo và trả về đánh giá cho từng mã watchlist liên quan (NVL, MSN, FPT, HPG, MWG). Đi kèm là một script đo độ chính xác trên bộ test của KB.

Chuẩn đánh giá duy nhất là **nhãn Expected của KB**. Cột "AI trả ra" trong file test của KB đến từ một hệ thống khác và không được dùng.

**Ngoài phạm vi:** crawl bài, lưu trữ, API server, UI, Morning Summary, cảnh báo real-time, gom cụm sự kiện giữa nhiều bài.

## 2. Giao diện

```python
from pipeline import evaluate

results: list[TickerResult] = evaluate(Article(
    title=..., url=..., published_at=date(...), content=..., watchlist=["NVL","MSN","FPT","HPG","MWG"],
))
```

`TickerResult` (Pydantic):

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `ticker` | str | |
| `relevance` | `TT` / `GT` / `KLQ` | Dùng nội bộ. Nếu là KLQ thì mã đó không có trong kết quả trả về |
| `priority` | `Cao` / `Trung bình` / `Thấp` | |
| `priority_confidence` | float | |
| `impact` | `Tích cực` / `Tiêu cực` / `Trung lập` | |
| `impact_confidence` | float | |
| `event_type` | str | Mã loại sự kiện A01–A36 |
| `rule_ids` | list[str] | Các quy tắc v2 đã áp, theo thứ tự |
| `evidence` | list[Evidence] | Câu trích nguyên văn từ bài, kèm con số |
| `relevance_reason`, `priority_reason`, `impact_reason` | str | 1–3 câu cho mỗi trường. Có trích mã quy tắc v2 và số liệu từ bài |
| `flags` | list[str] | `missing_denominator`, `conflicting_numbers`, `low_confidence`, `validation_failed`, `needs_review` |

## 3. Luồng xử lý (LangGraph)

```
extract ─► [fan-out theo mã] ─► relevance ─► rules ─► impact ─► write ─► validate ─► [gom kết quả]
```

| Node | Công cụ | Đầu vào → đầu ra |
|---|---|---|
| `extract` | Claude, `messages.parse` | Chạy một lần cho mỗi bài. Đầu vào là bài báo và hồ sơ mã. Đầu ra `ArticleFacts`: danh sách thực thể đã map về mã; danh sách sự kiện, mỗi sự kiện gồm loại A01–A36, chủ thể, các bên tham gia, `is_update_of_announced_event`, `is_new_info`; danh sách con số, mỗi số gồm giá trị, đơn vị, ý nghĩa, câu trích, sự kiện liên quan |
| `relevance` | `DecisionModel.choice` | Đầu vào là facts và hồ sơ mã (ngày niêm yết, sở hữu). Đầu ra là TT / GT / KLQ kèm xác suất |
| `rules` | Python thuần | Chọn sự kiện **mới** quan trọng nhất (G-4, G-6) → bậc mặc định theo Phụ lục A → ngưỡng P-TH (dùng mẫu số trong bài, nếu không có thì lấy từ hồ sơ mã) → điều chỉnh P-MOD-1 đến P-MOD-5 → sàn ở Mục 3.4. Đầu ra là Priority và `rule_ids` |
| `impact` | Python, sau đó `DecisionModel.choice` | Python áp các cơ chế Trung lập tất định (I-TL-d, I-TL-e, I-TL-f) và chiều mặc định trong Phụ lục A khi không có điều kiện đổi nhãn. Các trường hợp còn lại do DecisionModel chọn Tích cực / Tiêu cực / Trung lập, có đưa các yếu tố ở Mục 4.1 làm ngữ cảnh |
| `write` | Claude Sonnet 5.5, `messages.parse` | Đầu vào là bài, facts, các nhãn đã chốt và `rule_ids`. Đầu ra là **3 lý giải**: Relevance, Priority, Ảnh hưởng. Không được đổi nhãn. News Details (Summary và 3 phần phân tích) **tạm chưa làm** |
| `validate` | Python thuần | Kiểm tra: Cao ⇒ TT; mỗi con số trong `evidence` và trong 3 lý giải phải tìm được trong `content` hoặc hồ sơ mã (so khớp sau chuẩn hóa dấu phẩy, dấu chấm); mỗi lý giải trích ít nhất một mã quy tắc nằm trong `rule_ids`; không có cụm khuyến nghị ("nên mua", "nên bán", "nắm giữ", "khuyến nghị mua"…); `impact_reason` không mâu thuẫn chiều với `impact`. Lỗi ở `write` thì retry `write` 1 lần, vẫn lỗi thì gắn cờ |

Ngưỡng confidence để gắn `low_confidence` mặc định là 0,6, đặt trong config.

## 4. Thành phần

```
kb-test/
├── tieu_chi_v2.md
├── profiles/{NVL,MSN,FPT,HPG,MWG}.yaml
├── pipeline/
│   ├── __init__.py        # export evaluate, Article, TickerResult
│   ├── config.py          # model ID, effort cho từng node, ngưỡng confidence, backend quyết định
│   ├── schemas.py         # Article, ArticleFacts, Event, Figure, Evidence, TickerResult
│   ├── profiles.py        # đọc YAML; listed_on(entity, date); ownership(entity, date)
│   ├── llm.py             # Anthropic client, kiểm tra model ID lúc khởi động, cache system prompt
│   ├── extract.py
│   ├── decision.py        # DecisionModel (Protocol), ClaudeBackend, JevBackend
│   ├── rules.py           # tiêu chí v2 bằng code: bảng A01–A36, P-TH, P-MOD, sàn, I-TL
│   ├── write.py
│   ├── validate.py
│   └── graph.py           # dựng LangGraph StateGraph; evaluate()
├── eval/
│   ├── fetch.py           # httpx + trafilatura; cache tại eval/cache/<sha1(url)>.txt; cho phép file .txt đặt tay
│   └── run_eval.py        # đọc xlsx của KB → chạy → báo cáo + CSV
└── tests/
    ├── test_rules.py      # 22 case KB, dùng ArticleFacts viết tay, không gọi API
    └── test_validate.py
```

### 4.1. Claude

- **Model:** `claude-sonnet-5-5` (Claude Sonnet 5.5, phát hành 28/09/2026; đã đối chiếu tài liệu chính thức của Anthropic). Dùng cho mọi node gọi Claude: `extract`, `write`, và `ClaudeBackend` của DecisionModel. Model đặt trong `config.CLAUDE_MODEL`, có thể ghi đè bằng biến môi trường. Khi khởi động, `llm.py` gọi `client.models.retrieve(...)` để dừng sớm nếu ID sai hoặc tài khoản không có quyền dùng model.
- **SDK:** gọi trực tiếp Anthropic SDK chính thức (`anthropic`), dùng `client.messages.parse(..., output_format=PydanticModel)`. LangGraph chỉ lo điều phối, không dùng wrapper `langchain_anthropic`.
- **Ràng buộc của Sonnet 5.5** (các tham số dưới đây gây lỗi 400 nên **không** được dùng):
  - `temperature`, `top_p`, `top_k`
  - prefill (câu trả lời mồi sẵn của assistant)
  - `thinking: {type: "disabled"}` và `budget_tokens`
  - `tool_choice` dạng `any` hoặc `tool`

  Muốn có JSON đúng schema thì dùng structured output (`messages.parse`), không dùng cách ép gọi tool.
- **Thinking và effort:** điểm khởi đầu là adaptive thinking với `output_config.effort = "medium"` cho cả `extract` và `write`. Lý do: tài liệu khuyến nghị `medium` hoặc `low` cho tác vụ cần độ trễ thấp; mặc định của API là `high`. Phương án rẻ hơn cần đo khi chạy eval: `thinking: {type: "between_tools"}` (bỏ bước suy nghĩ trước khi trả lời, chỉ dùng được ở effort `low` đến `high`). Chọn cấu hình cuối cùng dựa trên kết quả eval với 22 case KB.
- **Prompt caching:** system prompt cố định cho mỗi node (gồm `tieu_chi_v2.md` và 5 hồ sơ mã đã sắp xếp ổn định), đặt `cache_control` ở cuối system. Nội dung bài nằm trong `messages`. Sonnet 5.5 cache được từ 512 token; giá đọc cache là $0,10/MTok. Kiểm tra cache hoạt động qua `usage.cache_read_input_tokens`.
- **Cách viết prompt cho phần lý giải:** yêu cầu "căn cứ dẫn đến nhãn": mã quy tắc v2 và số liệu trích từ bài. **Không** yêu cầu model "trình bày suy nghĩ" hay "giải thích quá trình suy luận". Sonnet 5.5 có thể từ chối với nhóm `reasoning_extraction` khi được yêu cầu chép lại suy luận nội bộ, và cơ chế fallback phía server không xử lý nhóm này.
- **Lỗi:** dùng retry mặc định của SDK cho lỗi 429 và 5xx. Kiểm tra `stop_reason`; nếu là `refusal`, `max_tokens` hoặc `model_context_window_exceeded` thì gắn cờ `needs_review` (kèm `stop_details.category` nếu có), không đoán kết quả. Không bật server-side fallback: trên Sonnet 5.5 nó chỉ chạy lại các lần từ chối thuộc nhóm `cyber` và `frontier_llm`, không liên quan bài toán này.
- **Đọc response:** structured output lấy qua `parsed_output`; các block `thinking` (mặc định không có nội dung) được bỏ qua.

### 4.2. DecisionModel

```python
class DecisionModel(Protocol):
    def choice(self, state: str, question: str, options: list[str]) -> tuple[str, dict[str, float]]: ...
```

- `ClaudeBackend` là mặc định. Gọi Claude với structured output trả về `{answer, probabilities}`.
- `JevBackend` là adapter cho TypeSafe Jev (câu hỏi Choice), bật khi có `TYPESAFE_API_KEY`. Hình dạng API chính xác sẽ đọc từ tài liệu Jev khi triển khai.

### 4.3. Hồ sơ mã (`profiles/*.yaml`)

```yaml
ticker: MWG
entities:
  - name: Điện Máy Xanh
    aliases: [DMX, ĐMX, Điện Máy Xanh]   # TopZone: chưa rõ thuộc DMX hay MWG, cần xác minh
    listed_ticker: DMX
    listed_since: 2026-08-06
    ownership: []                         # danh sách {as_of, pct}; rỗng = chưa có dữ liệu
    core: true
financials:            # bạn cần điền; null → quy tắc liên quan gắn cờ missing_denominator
  - as_of: 2026-06-30
    revenue_ttm: null
    npat_ttm: null
    total_assets: null
    equity: null
    shares_outstanding: null
sector_variables: [sức mua bán lẻ, CPI, giá iPhone...]
```

Pipeline luôn chọn bản ghi có `as_of` gần nhất nhưng không sau `published_at`.

## 5. Đo độ chính xác

`python -m eval.run_eval "<đường dẫn xlsx KB>"`

1. Đọc sheet `Template`, lấy từ dòng 4 (VD) đến dòng 204. Chỉ lấy dòng có Title. Dùng các cột: B (Mã), C (Title), D (Link), F (Priority Expected), J (Ảnh hưởng Expected).
2. `fetch.py` tải nội dung bài. Bài không tải được ghi `fetch_failed` và bỏ qua trong thống kê; danh sách các bài này được in ra để đặt file text tay.
3. Chạy `evaluate()`, lấy kết quả của đúng mã ở cột B.
4. Báo cáo ra màn hình và file `eval/out/report.md`:
   - Tỷ lệ Pass cho Priority, Ảnh hưởng, Badge
   - Ma trận nhầm lẫn Priority và Ảnh hưởng (Expected × Pipeline)
   - Kết quả theo mã
   - Danh sách các bài Fail, kèm `rule_ids` và lý giải
   - Cấu trúc giống sheet "Tổng hợp" của KB
5. `eval/out/results.csv`: mỗi bài một dòng, gồm STT, Mã, Title, Priority, Ảnh hưởng (theo thứ tự cột E và I của Template), Relevance, `rule_ids`, ba lý giải và `flags`.

`tests/test_rules.py`: với mỗi case trong 22 case KB, viết tay `ArticleFacts` tối thiểu, rồi kiểm tra `rules` và phần tất định của `impact` cho ra đúng Expected. Test chạy không cần API key.

## 6. Phụ thuộc

`anthropic`, `langgraph`, `pydantic`, `pyyaml`, `httpx`, `trafilatura`, `openpyxl`, `pytest`. Python ≥ 3.10. Môi trường hiện tại thiếu `python3-venv` và `pip` bị khóa theo PEP 668, nên cần cài venv (hoặc `uv`) trước.

## 7. Điểm còn mở

| # | Vấn đề | Ảnh hưởng | Mặc định nếu chưa có trả lời |
|---|---|---|---|
| 1 | Tài khoản Anthropic đã có quyền dùng `claude-sonnet-5-5` và có API key chưa | Pipeline không khởi động được | Kiểm tra lúc khởi động và báo lỗi |
| 1b | News Details (Summary và 3 phần phân tích) | Chưa có trong đầu ra | Để sau; node `write` mở rộng được mà không đổi graph |
| 2 | Số liệu tài chính trong hồ sơ mã | Các ngưỡng P-TH-01/04/05 cần mẫu số | Gắn cờ `missing_denominator`; dùng mẫu số có trong bài nếu có |
| 3 | Các quy tắc "ĐX" và 4 điểm cần KB xác nhận trong v2 | Có thể đổi nhãn ở một số loại bài | Áp như v2 hiện tại |
| 4 | Key Jev | | Dùng `ClaudeBackend` |
