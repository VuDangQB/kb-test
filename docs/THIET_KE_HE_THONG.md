# Thiết kế hệ thống đánh giá tin tức chứng khoán

**Dự án:** InvestMate PoC – KB Securities · **Watchlist:** NVL, MSN, FPT, HPG, MWG
**Cập nhật:** 28/10/2026 · Mô tả đúng code hiện tại trong repo. Tiêu chí nghiệp vụ nằm ở `tieu_chi_v2.md`.

---

## 1. Hệ thống làm gì

Đầu vào là **một bài báo**: link, hoặc tiêu đề + nội dung + ngày đăng.
Đầu ra là **một kết quả cho mỗi mã trong watchlist mà bài có liên quan**:

| Trường | Giá trị | Ý nghĩa |
|---|---|---|
| Relevance | Trực tiếp / Gián tiếp / Không liên quan | Bài nói về mã ở mức nào |
| Priority | Cao / Trung bình / Thấp | Tin quan trọng tới đâu với mã |
| Ảnh hưởng | Tích cực / Tiêu cực / Trung lập | Hướng tác động của thông tin mới lên mã |
| Loại sự kiện | A01 … A36 | Bài thuộc loại sự kiện nào (bảng tra trong tiêu chí) |
| Mã quy tắc | VD `R-TT-1`, `A24`, `P-TH-09`, `I-TL-d` | Quy tắc nào đã dẫn tới nhãn, để truy vết |
| Số đã tính | VD "Tỷ lệ phát hành / CP lưu hành = 33,3%" | Do Python tính, không do model tự nhẩm |
| 3 lý giải | Relevance, Priority, Ảnh hưởng | 1–3 câu, có số liệu và mã quy tắc |
| Cờ | VD `missing_denominator`, `low_confidence` | Điểm cần người kiểm tra |

Một bài có thể cho nhiều kết quả. Ví dụ bản tin khối ngoại nhắc cả FPT lẫn NVL sẽ có kết quả riêng cho từng mã, và nhãn có thể khác nhau.

**Chưa làm trong giai đoạn này:** phần News Details (tóm tắt, "vì sao ảnh hưởng", "nên theo dõi gì").

---

## 2. Nguyên tắc thiết kế

1. **Model đọc, code quyết định.** Claude chỉ làm việc cần hiểu ngôn ngữ: đọc bài, tách sự kiện, trích số liệu, xác định vai trò của mã. Các ngưỡng, bậc và nhãn do **code Python** áp theo `tieu_chi_v2.md`. Cùng một bộ dữ kiện thì luôn ra cùng một nhãn, và mỗi nhãn truy được về một mã quy tắc.
2. **Chỉ hỏi model khi tiêu chí cần phán đoán.** Một số trường hợp tiêu chí không cho đáp án cố định, ví dụ M&A vào lĩnh vực mới tốt hay xấu, hoặc tin ngành. Khi đó code hỏi một **mô hình quyết định**. Mô hình này trả về đáp án kèm xác suất. Xác suất thấp thì gắn cờ `low_confidence`.
3. **Không có con số nào được bịa.** Mỗi số liệu model trích ra phải kèm câu trích nguyên văn từ bài. Lý giải chỉ được dùng số có trong bài, trong số đã tính hoặc trong hồ sơ mã. Bước kiểm tra cuối chặn mọi con số lạ.
4. **Thiếu dữ liệu thì gắn cờ, không đoán.** Thiếu mẫu số (tổng tài sản, số CP lưu hành…) thì không lên bậc Cao, và kết quả mang cờ `missing_denominator`.
5. **Không lấy nhầm bài.** Crawler thà báo "cần nhập tay" còn hơn trả về nội dung của bài khác.
6. **Nhãn Expected của KB là đáp án.** Mọi quy tắc được đối chiếu với nhãn của KB trong file test.

---

## 3. Kiến trúc tổng thể

```
                 ┌───────────────────────────────────────────────────────────┐
  URL bài báo ──►│ BƯỚC 0  CRAWL  (pipeline/crawl.py)              — code      │
                 │ tải trang → tách tiêu đề, sapo, thân bài, ngày đăng         │
                 └──────────────────────────┬────────────────────────────────┘
                                            │ Article
                 ┌──────────────────────────▼────────────────────────────────┐
                 │ BƯỚC 1  EXTRACT  (pipeline/extract.py)          — Claude    │
                 │ đọc cả bài → sự kiện, số liệu + câu trích, vai trò từng mã  │
                 └──────────────────────────┬────────────────────────────────┘
                                            │ ArticleFacts
                         BƯỚC 2  FAN-OUT: mỗi mã watchlist có trong bài
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
             ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
             │  nhánh FPT  │         │  nhánh MSN  │   ...   │  nhánh HPG  │   (chạy song song)
             └──────┬──────┘         └─────────────┘         └─────────────┘
                    │
   BƯỚC 3  RELEVANCE      code (bảng vai trò → nhãn); "unclear" → mô hình quyết định
   BƯỚC 4  RULES          code: chọn sự kiện chính → ngưỡng → điều chỉnh bậc → sàn → Priority
                          (Không liên quan → dừng nhánh)
   BƯỚC 5  IMPACT         code nếu tiêu chí có đáp án cố định; còn lại → mô hình quyết định
   BƯỚC 6  WRITE          Claude viết 3 lý giải cho nhãn đã chốt (không được đổi nhãn)
   BƯỚC 7  VALIDATE       code kiểm tra lý giải; sai → quay lại WRITE (tối đa 2 lần)
   BƯỚC 8  FINISH         gắn cờ, trả TickerResult
                    │
                    ▼
        list[TickerResult]  (sắp theo thứ tự watchlist)
```

Phần điều phối dùng **LangGraph**: một graph cấp bài (extract → fan-out) và một graph con cho mỗi mã (bước 3–8). Các nhánh mã chạy song song bằng `Send`.

### Bản đồ file

| File | Vai trò |
|---|---|
| `pipeline/crawl.py` | Bước 0: tải và tách nội dung bài |
| `pipeline/extract.py` | Bước 1: prompt và lời gọi Claude để trích dữ kiện |
| `pipeline/graph.py` | Điều phối LangGraph, bước 2–8; hàm `evaluate(article)` |
| `pipeline/rules.py` | Tiêu chí v2 viết bằng code: relevance, ngưỡng, điều chỉnh bậc, phần cố định của Ảnh hưởng |
| `pipeline/catalog.py` | Bảng 36 loại sự kiện (A01–A36) và mô tả mọi mã quy tắc |
| `pipeline/decision.py` | Mô hình quyết định: `JevBackend` (TypeSafe Jev, mặc định khi có key) hoặc `ClaudeBackend` |
| `pipeline/write.py` | Bước 6: prompt viết lý giải |
| `pipeline/validate.py` | Bước 7: kiểm tra lý giải |
| `pipeline/profiles.py`, `profiles/*.yaml` | Hồ sơ mã: công ty con, ngày niêm yết, số liệu tài chính |
| `pipeline/schemas.py` | Kiểu dữ liệu: `Article`, `ArticleFacts`, `TickerResult`… |
| `pipeline/llm.py` | Lớp gọi Claude: structured output, prompt cache, đo thời gian và token |
| `pipeline/tracing.py` | Gửi trace sang Phoenix (tùy chọn) |
| `pipeline/config.py` | Model, effort, ngưỡng độ tin cậy |
| `tieu_chi_v2.md` | Tiêu chí nghiệp vụ; cũng được đưa nguyên văn vào prompt |
| `eval/` | Công cụ chấm: `run_one` (từng bài), `run_eval` (bộ test KB), cache bài đã crawl |
| `research/watchlist_labels_v2.csv` | Golden set 100 bài watchlist |
| `tests/` | Test offline (không gọi API) |

---

## 4. Xử lý từng bước

Phần này đi qua từng bước. Cuối mỗi bước là ví dụ thật với bài **WL-041 "Vì sao cổ phiếu FPT giảm miệt mài dù kinh doanh vẫn tốt?"** (dantri, 13/10/2026).

### Bước 0 — Crawl: lấy nội dung bài từ link

**Vào:** URL. **Ra:** `CrawlResult` gồm tiêu đề, sapo, thân bài, ngày đăng, cách lấy và cảnh báo.
**Ai làm:** code (`pipeline/crawl.py`).

Báo Việt Nam có nhiều kiểu trang: trang tĩnh, trang Next.js render bằng JavaScript, trang công bố thông tin chỉ có file PDF. Vì vậy crawler **thử lần lượt 5 cách**, và mỗi kết quả phải qua kiểm tra chất lượng mới được nhận:

| Thứ tự | Cách | Dùng cho |
|---|---|---|
| 1 | JSON-LD `articleBody` | Trang có dữ liệu cấu trúc cho SEO |
| 2 | Dữ liệu nhúng của Next.js/Nuxt (`__NEXT_DATA__`, `self.__next_f`) | Trang render bằng JS |
| 3 | trafilatura trên HTML đã **lọc nhiễu** (bỏ khối "tin liên quan", sidebar, chia sẻ) | Đa số báo |
| 4 | trafilatura trên HTML gốc | Khi bước lọc nhiễu xóa nhầm |
| 5 | Bản AMP của trang, rồi PDF đính kèm có lớp chữ | Trang khó, trang công bố thông tin |

**Kiểm tra chất lượng** (hàm `quality`):
- Ít nhất 400 ký tự.
- Không phải mã nguồn trang.
- Không phải danh sách tin (sidebar).
- Đủ từ khóa trùng với tiêu đề hoặc sapo.

Sau khi nhận nội dung, crawler còn làm thêm:
- Ghép sapo vào đầu bài.
- Bỏ các cụm danh sách link không liên quan.
- Nếu bài quá ngắn mà có PDF đính kèm thì nối thêm nội dung PDF.

**Ngày đăng** được lấy lần lượt từ JSON-LD, thẻ meta, trafilatura, rồi mã ngày trong URL cafef. Chỉ nhận năm từ 2015 trở đi, để tránh các ngày giả như 2002-01-01 trên một số trang.

**Khi thất bại:** trả `status = needs_manual` kèm lý do, ví dụ trang chặn truy cập (HTTP 403) hoặc PDF scan không có chữ. Khi đó người dùng đặt nội dung vào `eval/cache/manual/<sha1(url)>.txt`.
Kết quả thử trên 122 link: **119 lấy được**. 3 link cần nhập tay (2 bài investing.com chặn kết nối, 1 bài là PDF scan).

> **WL-041:** lấy bằng cách 3 (trafilatura sau khi lọc nhiễu), khoảng 5.900 ký tự, ngày 13/10/2026.

### Bước 1 — Extract: Claude đọc bài và trích dữ kiện

**Vào:** `Article`. **Ra:** `ArticleFacts`. **Ai làm:** Claude, 1 lần gọi mỗi bài.

Claude **không gán nhãn** ở bước này. Nó chỉ điền một bảng dữ kiện có cấu trúc theo schema:

- **Danh sách sự kiện** (`events`). Mỗi sự kiện gồm:
  - Loại sự kiện A01–A36. Theo nguyên tắc G-9, loại được xác định theo **trọng tâm của toàn bài**, không theo một đoạn riêng lẻ.
  - Mô tả 1 câu và chủ thể của sự kiện.
  - `is_new_info`: thông tin mới hay chỉ nhắc lại.
  - `is_update_of_announced_event`: chỉ là cập nhật tiến độ của sự kiện đã công bố.
  - **Số liệu** theo bộ khóa cố định, ví dụ `issue_shares`, `foreign_net_vnd`, `kpi_yoy_pct`. Giá trị đã quy đổi đơn vị, kèm **câu trích nguyên văn**.
  - Các cờ ngữ nghĩa, ví dụ `new_business_line`, `intra_group_transfer`, `proceeds_for_debt`, `offsetting_factor`.
- **Vai trò của từng mã** (`ticker_mentions`): `subject`, `party`, `data`, `sector`, `ecosystem`, `illustrative`, `list_only`, `macro` hoặc `unclear`. Nếu bài nói qua công ty con hoặc thương hiệu (ví dụ "Điện Máy Xanh") thì ghi tên thực thể đó.
- **Cờ bài:** `multi_ticker_equal` (bài phân tích nhiều mã ngang nhau) và `conflicting_numbers` (bài có số liệu mâu thuẫn).

**Prompt gồm ba khối cố định**, được cache để các lần gọi sau rẻ hơn:
1. Hướng dẫn trích xuất cùng bảng loại sự kiện.
2. Toàn văn `tieu_chi_v2.md`.
3. Hồ sơ của 5 mã.

Nội dung bài nằm ở phần tin nhắn người dùng.

Sau khi nhận kết quả, code lọc chỉ giữ các mã thuộc watchlist.

> **WL-041** (khoảng 6 giây):
> - **E1 – A24**, bài giải thích diễn biến giá. Số liệu kèm câu trích: giá 56.900đ, khối ngoại bán 91 tỷ trong phiên và 14.700 tỷ từ đầu năm, P/E 12,5 lần. Cờ `offsetting_factor = true`.
> - **E2 – A01**, kết quả kinh doanh 8 tháng. `is_new_info = false` vì đây là số đã công bố.
> - FPT: `role = subject`.

### Bước 2 — Fan-out: tách nhánh theo mã

**Ai làm:** code (`fan_out` trong `graph.py`).
Mỗi mã trong `ticker_mentions` được tách thành một nhánh và các nhánh chạy song song. Bài không nhắc mã nào trong watchlist thì kết thúc với danh sách rỗng.

> **WL-041:** 1 nhánh (FPT).

### Bước 3 — Relevance: bài liên quan đến mã ở mức nào

**Ai làm:** code (`decide_relevance`). Riêng vai trò `unclear` thì hỏi mô hình quyết định.

| Vai trò | Nhãn | Mã quy tắc |
|---|---|---|
| `subject`, không qua thực thể nào, hoặc qua cổ đông/lãnh đạo | Trực tiếp | R-TT-1 |
| `subject` qua công ty con **chưa niêm yết** | Trực tiếp | R-TT-2 |
| `subject` qua công ty con **đã niêm yết riêng tại ngày đăng bài** (VD DMX từ 06/08/2026, MCH, MSR) | Gián tiếp | R-GT-a1 |
| `party`: mã là một bên giao dịch | Trực tiếp | R-TT-3 |
| `data`: bài rộng hơn nhưng có số liệu riêng của mã | Trực tiếp | R-TT-4 |
| `sector` / `ecosystem` / `illustrative` | Gián tiếp | R-GT-b / R-GT-a2 / R-GT-a3 |
| `list_only` / `macro` | Không liên quan | R-KLQ-1 / R-KLQ-2 |

Ngày niêm yết lấy từ hồ sơ mã. Vì vậy cùng một tin về Điện Máy Xanh, nếu đăng trước 06/08/2026 thì là Trực tiếp, đăng sau thì là Gián tiếp với MWG.

> **WL-041:** `subject`, không qua thực thể nào → **Trực tiếp (R-TT-1)**.

### Bước 4 — Rules: chọn sự kiện chính và tính Priority

**Ai làm:** code (`evaluate_ticker` và `priority_for_event`). Không gọi model.

Nếu Relevance là Không liên quan thì nhánh dừng tại đây và mã này không xuất hiện trong kết quả. Ngược lại, code làm 5 việc:

1. **Chọn sự kiện để chấm.** Chỉ xét các sự kiện có thông tin mới (G-4), hoặc là bản cập nhật của sự kiện đã công bố. Nếu có nhiều sự kiện thì lấy sự kiện có Priority cao nhất (G-6).
2. **Áp ngưỡng định lượng** theo loại sự kiện (mục 3.2 của tiêu chí). Ví dụ:
   - Phát hành: % pha loãng = số CP phát hành / số CP lưu hành. Trên 10% là Cao, 3–10% là Trung bình.
   - Kết quả kinh doanh: doanh thu tăng hơn 10%, lợi nhuận tăng hơn 15% hoặc vượt kế hoạch thì là Cao.
   - Cổ tức tiền mặt: Cao khi lợi suất ≥ 6% hoặc tỷ lệ chi trả ≥ 60% LNST.

   Các chỉ tiêu % tăng trưởng, % kế hoạch và lợi suất cổ tức **chỉ lấy khi bài nêu sẵn**. Code không tự tính từ số tuyệt đối, giống hệ thống chính. Phần code tính lợi suất từ cổ tức / thị giá đã được comment out trong `th_dividend`.
   - Đầu tư/M&A: so với tổng tài sản hoặc vốn chủ sở hữu. Từ 1.000 tỷ trở lên vào lĩnh vực mới thì là Cao.
   - Khối ngoại: mặc định Trung bình. Cao chỉ khi lũy kế là trọng tâm bài **và** có mẫu số.

   Mẫu số lấy theo thứ tự: bài, rồi hồ sơ mã tại ngày đăng (G-8). Không có mẫu số thì giữ ở Trung bình và gắn cờ `missing_denominator`.
3. **Điều chỉnh bậc** theo thứ tự:
   - **P-MOD-1:** bài chỉ cập nhật sự kiện đã công bố → hạ 1 bậc.
   - **P-MOD-2:** Relevance Gián tiếp → tối đa Trung bình.
   - **P-MOD-3:** công ty con niêm yết riêng mà bài không định lượng tác động lên mã mẹ → tối đa Trung bình.
   - **P-MOD-4:** bài đa mã → tối đa Trung bình.
   - **P-MOD-5:** thiếu số liệu → tối đa Trung bình.
4. **Sàn (P-SAN):** một số loại không bao giờ xuống dưới Trung bình, gồm cổ tức tiền mặt, giao dịch của người nội bộ, khối ngoại và khuyến nghị của CTCK.
5. **Ghi lại** mã quy tắc đã áp, số đã tính và câu trích làm bằng chứng.

> **WL-041:** E2 là thông tin cũ nên bị loại. Sự kiện chính là E1 (A24). A24 không có ngưỡng định lượng, bậc mặc định là **Trung bình (A24)**.

### Bước 5 — Impact: hướng ảnh hưởng

**Ai làm:** code nếu tiêu chí có đáp án cố định, còn lại hỏi mô hình quyết định.

Mỗi loại sự kiện trong `catalog.py` khai báo cách xác định Ảnh hưởng theo một trong ba kiểu:

| Kiểu | Ví dụ | Cách làm |
|---|---|---|
| Cố định | A14 (MOU không có giá trị) → Trung lập `I-TL-d`; A24 (khuyến nghị, phân tích) → Trung lập `I-TL-d` | Gán thẳng |
| Hàm quy tắc | Kết quả kinh doanh: tăng → Tích cực, giảm → Tiêu cực, có yếu tố ngược chiều → chuyển sang mô hình quyết định với gợi ý `I-TL-a`. Phát hành để trả nợ → Trung lập, pha loãng thuần → Tiêu cực. Cổ tức từ công ty con về công ty mẹ → Trung lập `I-TL-e`. Người nội bộ bán → Trung lập `I-TL-f` | Code xét số liệu và cờ |
| Cần phán đoán (`DM`) | A12 (M&A, đầu tư lớn), A20 (ý kiến kiểm toán), A31 (tin ngành), A32 (vĩ mô có tên mã) | Hỏi mô hình quyết định |

**Mô hình quyết định** (`DecisionModel.choice`) nhận dữ kiện đã trích, nội dung bài, câu hỏi và **mô tả ngắn của từng lựa chọn** (lấy từ mục 2 và mục 4 của tiêu chí). Nó trả về đáp án, **xác suất cho từng lựa chọn** và **độ tin cậy**. Độ tin cậy dưới `LOW_CONFIDENCE` thì gắn cờ `low_confidence`.

Có hai backend, chọn bằng `DECISION_BACKEND`:

| | `JevBackend` (TypeSafe Jev, `jev-latest`) | `ClaudeBackend` |
|---|---|---|
| Cách gọi | `typesafe-sdk`, `system_one` với 1 câu hỏi `Choice` | `messages.parse` |
| Đầu vào | Dữ kiện, bài, câu hỏi, mô tả lựa chọn (khoảng 2.500–3.500 token) | Như bên trái, cộng toàn văn tiêu chí trong system prompt |
| Thời gian đo được | khoảng 0,3s | vài giây (có bước suy nghĩ) |
| Độ tin cậy | Trường `confidence` của Jev, chặt hơn xác suất (≈0,45 khi xác suất đáp án ≈0,63) | Xác suất của đáp án |

Jev chỉ trả lời câu hỏi lựa chọn, có/không và chấm điểm. Nó **không sinh văn bản**, nên không thay được bước extract (cần trích số liệu kèm câu trích) và bước write (cần viết lý giải).

> **WL-041:** A24 có Ảnh hưởng cố định → **Trung lập (I-TL-d)**. Không cần gọi mô hình quyết định.

### Bước 6 — Write: viết 3 lý giải

**Ai làm:** Claude, 1 lần gọi mỗi mã.

Claude nhận nhãn **đã chốt**, mã quy tắc của từng nhãn (kèm mô tả), số đã tính, câu trích và nội dung bài. Yêu cầu với mỗi lý giải:
- 1–3 câu, nêu đúng tên nhãn và **không được đổi nhãn**.
- Trích ít nhất một mã quy tắc của đúng trường đó.
- Dẫn số liệu cụ thể từ bài.
- Nếu Priority chưa đạt Cao thì nêu điều còn thiếu.
- Không khuyến nghị mua/bán, không dự đoán giá.

> **WL-041** (khoảng 5 giây), lý giải Priority: *"Nhãn 'Trung bình': bài giải thích diễn biến giá tổng hợp nhiều yếu tố (khối ngoại bán ròng hơn 14.700 tỷ đồng từ đầu năm, rủi ro AI, thị trường Mỹ/Nhật…) nhưng không có sự kiện mới, KQKD 8 tháng chỉ là số đã công bố nên không lên Cao (A24, G-9)."*

### Bước 7 — Validate: kiểm tra lý giải

**Ai làm:** code (`validate.check`). Không gọi model.

| Kiểm tra | Lỗi khi |
|---|---|
| Nhất quán nhãn | Priority Cao mà Relevance không phải Trực tiếp |
| Nêu nhãn | Lý giải không nhắc tên nhãn |
| Trích quy tắc | Không trích mã nào trong danh sách của trường đó, hoặc trích mã không tồn tại |
| Số liệu | Có con số (từ 3 chữ số) không xuất hiện trong bài, trong số đã tính, trong câu trích hoặc trong hồ sơ mã |
| Văn phong | Có câu kiểu "nên mua/bán", "giá sẽ tăng", "cơ hội mua vào" |

Nếu có lỗi, danh sách lỗi được gửi lại bước 6 để viết lại, **tối đa 2 lần**. Vẫn sai thì kết quả mang cờ `validation_failed` kèm chi tiết lỗi.

> **WL-041:** đạt ngay lần đầu.

### Bước 8 — Finish: trả kết quả

Code gom kết quả các nhánh, sắp theo thứ tự watchlist và trả `list[TickerResult]`.

> **WL-041, kết quả cuối:** FPT · Trực tiếp · **A24** · **Trung bình** · **Trung lập** · `R-TT-1 A24 I-TL-d`.
> Tổng khoảng 11,8 giây, 2 lần gọi Claude. Chạy lặp 3 lần đều cho cùng một nhãn và đều khớp golden set.

---

## 5. Dữ liệu tham chiếu

### 5.1. Tiêu chí và mã quy tắc

`tieu_chi_v2.md` là nguồn duy nhất cho nghiệp vụ. Mỗi quy tắc có một mã để code, prompt và lý giải cùng trích dẫn:

| Nhóm | Mã | Nội dung |
|---|---|---|
| Nguyên tắc chung | G-1 … G-9 | VD G-1: không dùng diễn biến giá làm căn cứ. G-4: chấm theo thông tin mới. G-9: loại sự kiện theo trọng tâm toàn bài |
| Relevance | R-TT-*, R-GT-*, R-KLQ-* | Mục 2 |
| Priority | P-TH-01…12 (ngưỡng), P-MOD-1…5 (điều chỉnh), P-SAN (sàn) | Mục 3 |
| Ảnh hưởng | I-YT-1…10 (yếu tố tạo hướng), I-TL-a…f (cơ chế Trung lập) | Mục 4 |
| Loại sự kiện | A01 … A36 | Phụ lục A: mỗi loại có Relevance, Priority và Ảnh hưởng mặc định |

Các quy tắc ghi **ĐX** là đề xuất của nhóm, chưa được KB xác nhận.

### 5.2. Hồ sơ mã (`profiles/*.yaml`)

Mỗi mã có:
- **Bản đồ thực thể:** công ty con, thương hiệu, cổ đông lớn, kèm **mã niêm yết riêng và ngày niêm yết**. Ví dụ MWG → Điện Máy Xanh (gồm TopZone, EraBlue), niêm yết từ 06/08/2026.
- **Số liệu tài chính theo kỳ:** doanh thu TTM, tổng tài sản, vốn chủ sở hữu, số CP lưu hành. Code chỉ dùng số liệu của kỳ **trước hoặc bằng ngày đăng bài**.
- Biến số ngành, ví dụ giá thép hoặc sức mua bán lẻ.

> Hiện **chưa điền số liệu tài chính**. Các quy tắc cần mẫu số sẽ dừng ở Trung bình và gắn cờ `missing_denominator`.

### 5.3. Kiểu dữ liệu chính (`pipeline/schemas.py`)

```
Article        title, url, published_at, content, watchlist
ArticleFacts   events[EventFact], ticker_mentions[TickerMention], multi_ticker_equal, conflicting_numbers
  EventFact    event_type (A01–A36), description, subject_entity, is_new_info,
               is_update_of_announced_event, figures[Figure(metric, value, unit, quote)], cờ ngữ nghĩa
  TickerMention ticker, role, via_entity, event_ids
TickerResult   ticker, relevance, priority(+confidence), impact(+confidence), event_type,
               relevance/priority/impact_rule_ids, computed, evidence, 3 lý giải, flags
```

---

## 6. Mô hình và cấu hình

| Hạng mục | Giá trị |
|---|---|
| Model | `claude-sonnet-5-5` (biến `CLAUDE_MODEL`), gọi qua Anthropic SDK chính thức |
| Kiểu gọi | `messages.parse` với schema Pydantic, nên đầu ra luôn đúng cấu trúc |
| Suy nghĩ | `thinking: adaptive`; effort `medium` cho cả 3 loại gọi (chỉnh bằng `EFFORT_*`) |
| Prompt cache | Khối hệ thống (tiêu chí và hồ sơ mã, khoảng 46.000 token) được cache. Lần gọi đầu ghi cache, các lần sau chỉ đọc |
| Số lần gọi mỗi bài | 1 (extract) + với mỗi mã liên quan: 1 (write) + 0–2 (mô hình quyết định) + 0–1 (viết lại) |
| Mô hình quyết định | `DECISION_BACKEND=jev` (TypeSafe Jev qua `typesafe-sdk`, mặc định khi có `TYPESAFE_API_KEY`) hoặc `claude` |

**Ràng buộc của Sonnet 5.5** mà code tuân theo: không truyền `temperature`, `top_p`, `top_k` hay `budget_tokens`; không prefill câu trả lời; không ép `tool_choice`. Prompt viết lý giải không yêu cầu model tái hiện quá trình suy luận của nó.

**Model dừng bất thường** (từ chối, hết `max_tokens`, vượt ngữ cảnh) thì sinh lỗi `LLMStopError`:
- Ở bước extract: cả bài báo lỗi.
- Ở bước write: kết quả vẫn trả về, kèm cờ `needs_review`.

---

## 7. Cờ trên kết quả

| Cờ | Nghĩa | Việc nên làm |
|---|---|---|
| `missing_denominator` | Có số nhưng thiếu mẫu số để so ngưỡng | Điền hồ sơ mã |
| `missing_numbers`, `contract_value_missing` | Bài không có số để lượng hóa | Đọc lại bài |
| `conflicting_numbers` | Bài có số liệu mâu thuẫn | Kiểm tra trước khi dùng |
| `low_confidence` | Mô hình quyết định chắc dưới 60% | Người duyệt |
| `validation_failed`, `validate:*` | Lý giải vẫn sai sau 2 lần viết | Người duyệt lý giải; nhãn vẫn đúng theo quy tắc |
| `needs_review`, `write_stopped:*` | Model dừng khi viết lý giải | Người duyệt |
| `no_event` | Không tìm được sự kiện để chấm | Xem lại bước extract |

---

## 8. Đánh giá chất lượng

### 8.1. Bộ đáp án (golden set)

| Bộ | Số bài | Nguồn nhãn | File |
|---|---|---|---|
| Bộ test KB | 21 bài và 1 dòng ví dụ (VD) | Nhãn Expected của KB | File xlsx "KB Test Template…" |
| Watchlist | 100 bài | Gán tay theo tiêu chí v2 và đối chiếu KB | `research/watchlist_labels_v2.csv`, `watchlist_v2.md` |

Cột "AI trả ra" trong file của KB là của một hệ thống khác và **không được dùng** làm tham chiếu.

### 8.2. Công cụ

```bash
uv run pytest -q                                        # test offline: quy tắc, crawler, graph, validate
uv run python -m eval.run_one WL-041                    # chạy 1 bài, so với golden
uv run python -m eval.run_one WL-041 --extract-only     # chỉ bước 1 (1 lần gọi) để xem phân loại
uv run python -m eval.run_one WL-041 --repeat 5         # chạy 5 lần: độ ổn định, thời gian, token
uv run python -m eval.run_eval "<file KB>.xlsx" --repeat 3   # cả bộ KB → eval/out/report.md, results.csv
```

- **`run_one`** in nhãn kèm ✅/❌ so với golden, quy tắc, số đã tính, lý giải, thời gian từng bước và token. Với `--repeat` thì in thêm phân bố nhãn qua các lần, ví dụ `A24×4, A23×1 (đồng nhất 80%)`.
- **`run_eval`** tạo báo cáo theo định dạng sheet "Tổng hợp" của KB:
  - Badge pass, ma trận nhầm lẫn Priority và Ảnh hưởng, kết quả theo mã, danh sách bài Fail.
  - Với `--repeat`: độ chính xác từng lần và danh sách bài đổi nhãn giữa các lần.

### 8.3. Giám sát bằng Phoenix

```bash
uv run phoenix serve                               # http://localhost:6006
uv run python -m eval.run_one WL-041 --phoenix
```

Mỗi bài là một trace:
`LangGraph → extract (→ lần gọi Claude) → ticker → relevance / rules / impact / write (→ lần gọi Claude) / validate`.

- Mỗi lần gọi Claude ghi model, token vào/ra/cache và độ trễ.
- Các lần lặp của cùng một bài nằm chung một session.
- Khi bật Phoenix, tracing riêng của Anthropic SDK bị tắt để token không bị đếm hai lần.

---

## 9. Hiệu năng đo được

Bài WL-041 (1 mã liên quan, Ảnh hưởng xác định bằng quy tắc), chạy 3 lần:

| Chỉ số | Giá trị |
|---|---|
| Thời gian mỗi bài | Trung bình 11,8s (extract 6,3s, write 5,4s), dao động ±0,4s |
| Số lần gọi Claude | 2 |
| Token mỗi bài | Khoảng 6.400 input thường, 46.091 đọc từ cache, khoảng 1.570 output |
| Độ ổn định | 3/3 lần cùng nhãn |

Bài có nhiều mã liên quan, hoặc cần mô hình quyết định, sẽ tốn thêm khoảng 5 giây và 1 lần gọi cho mỗi mã hoặc mỗi câu hỏi. Các nhánh mã chạy song song.

---

## 10. Hạn chế và việc còn mở

| # | Việc | Ảnh hưởng |
|---|---|---|
| 1 | Điền số liệu tài chính vào `profiles/*.yaml` | Các ngưỡng theo mẫu số (đầu tư, hợp đồng, phát hành không nêu số CP lưu hành) đang dừng ở Trung bình |
| 2 | Xác minh ngày niêm yết gần đúng (MCH, MSR, MML, FOC, FOX đang ghi 2017-01-01) và tỷ lệ sở hữu của MWG tại DMX | Có thể làm sai Relevance hoặc phép quy đổi tác động về mã mẹ |
| 3 | KB xác nhận các quy tắc ĐX, ví dụ ngưỡng Cao của khối ngoại, A35, A36 | Nhãn của các bài thuộc nhóm này chưa chắc chắn |
| 4 | Hiệu chỉnh ngưỡng `low_confidence` cho Jev trên bộ test | `confidence` của Jev thấp hơn xác suất, với ngưỡng 0,6 thì gần như mọi quyết định đều bị gắn cờ |
| 5 | Lý giải đôi khi xếp P/E vào yếu tố thuận lợi hoặc bất lợi; đôi khi trích mã quy tắc ngoài danh sách | Chỉ ảnh hưởng lý giải, không ảnh hưởng nhãn |
| 6 | Khối ngoại một phiên và lũy kế đang dùng chung khóa `foreign_net_vnd` | Có thể lấy nhầm số với bài A23 |
| 7 | 3 link cần nhập tay (investing.com chặn, PDF scan) | Thêm vào `eval/cache/manual/` |
| 8 | File xlsx của KB vẫn ghi nhãn cũ ở dòng VD (Cao / Tiêu cực) | Dòng VD sẽ bị chấm Fail cho tới khi cập nhật file |
| 9 | Chưa làm News Details | Ngoài phạm vi giai đoạn này |
