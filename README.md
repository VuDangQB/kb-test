# Pipeline đánh giá tin tức chứng khoán (InvestMate PoC – KB)

Hệ thống chính gọi `evaluate(article)` cho mỗi bài báo. Kết quả là một `TickerResult` cho mỗi mã watchlist (NVL, MSN, FPT, HPG, MWG) có liên quan: Priority, Ảnh hưởng, Relevance, mã quy tắc đã áp, số liệu đã tính, 3 lý giải và các cờ.
Tiêu chí áp dụng: `tieu_chi_v2.md`. Thiết kế: `docs/superpowers/specs/2026-10-28-news-eval-pipeline-design.md`.

## Cài đặt

```bash
uv sync
export ANTHROPIC_API_KEY=...          # model mặc định: claude-sonnet-5-5
```

## Dùng từ hệ thống chính

```python
from datetime import date
from pipeline import Article, evaluate

results = evaluate(Article(title="...", url="...", published_at=date(2026, 10, 21), content="..."))
for r in results:
    print(r.ticker, r.priority, r.impact, r.rule_ids, r.flags)
```

Nếu chỉ có link bài báo, crawl trước rồi đánh giá:

```python
from pipeline import evaluate
from pipeline.crawl import CrawlError, article_from_url

try:
    article = article_from_url(url, title_hint="tiêu đề nếu có")
except CrawlError as e:          # trang chặn, PDF scan, nội dung không khớp tiêu đề...
    print(e.result.status, e.result.error)  # không bao giờ trả về nội dung của bài khác
else:
    results = evaluate(article)
```

Crawler thử lần lượt: JSON-LD → dữ liệu Next.js nhúng → trafilatura (có lọc khối tin liên quan/sidebar) → trafilatura trên HTML gốc → bản AMP → PDF đính kèm có lớp chữ. Mỗi kết quả phải qua kiểm tra chất lượng (độ dài, không phải danh sách tin, không phải mã nguồn, khớp tiêu đề) mới được nhận.

## Chạy thử từng bài

```bash
set -a; source .env; set +a
uv run python -m eval.run_one WL-041                 # theo id bài watchlist (so với research/watchlist_labels_v2.csv)
uv run python -m eval.run_one WL-041 WL-043 KB-4     # nhiều bài; KB-n = cột STT trong sheet Template, KB-VD = dòng ví dụ
uv run python -m eval.run_one "https://..."          # theo URL; URL có trong bộ golden thì tự so nhãn
uv run python -m eval.run_one WL-041 --extract-only  # chỉ bước trích xuất (1 lần gọi): xem loại sự kiện, vai trò mã, số liệu
# --refresh : crawl lại   --title "..." : tiêu đề cho URL ngoài bộ golden   --xlsx / KB_XLSX : đường dẫn file KB
```

In ra nhãn của từng mã kèm ✅/❌ so với golden, mã quy tắc, số đã tính, cờ và 3 lý giải; lưu JSON ở `eval/out/one/<id>.json`.

## Đo độ chính xác trên file test của KB

```bash
uv run python -m eval.run_eval "/mnt/c/Users/VuDang/Downloads/KB Test Template for AI News Article Evaluation_2026.10.20.xlsx"
# --fetch-only : chỉ tải bài vào cache   --limit N : chạy N bài đầu   --workers 4
```

- Script chỉ chấm theo cột **Expected của KB** (cột F và J).
- Kết quả nằm ở `eval/out/report.md` (định dạng giống sheet "Tổng hợp" của KB) và `eval/out/results.csv`.
- Bài không tải được: đặt nội dung vào `eval/cache/manual/<sha1(url)>.txt`. Dòng đầu có thể ghi `date: YYYY-MM-DD`.

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Model cho extract / write / quyết định |
| `EFFORT_EXTRACT`, `EFFORT_WRITE`, `EFFORT_DECISION` | `medium` | Effort cho từng node |
| `CLAUDE_THINKING` | `adaptive` | `between_tools` để bỏ bước suy nghĩ trước khi trả lời |
| `DECISION_BACKEND` | `claude` (hoặc `jev` nếu có `TYPESAFE_API_KEY`) | JevBackend chưa nối API |
| `LOW_CONFIDENCE` | `0.6` | Ngưỡng gắn cờ `low_confidence` |

## Test (không cần API key)

```bash
uv run pytest -q
```

## Việc cần bổ sung

- Số liệu tài chính trong `profiles/*.yaml` (`revenue_ttm`, `total_assets`, `equity`, `shares_outstanding`). Khi thiếu, các quy tắc tính theo mẫu số sẽ gắn cờ `missing_denominator`.
- Ngày niêm yết gần đúng của MCH, MSR, MML, FOC, FOX (đang ghi 2017-01-01), tỷ lệ sở hữu DMX, và việc TopZone thuộc DMX hay MWG.
