# Plan: xử lý sự kiện và xác nhận độ mới bằng code

**Bối cảnh:** khi đọc sự kiện và đánh giá trong cùng một prompt, nhãn vẫn bị lật ở các bài có ranh giới gần giữa bối cảnh và tin mới, như WL-015, WL-041, WL-068 và WL-091. Model ước lượng chứ không tính, nên mỗi lần chạy lệch một chút là đủ để lật.

**Giải pháp:** tách thành hai prompt. Mọi quyết định dễ lật (mới hay cũ, trọng tâm, Priority) được dời sang code, dựa trên căn cứ có câu trích.

Liên quan:
- `prompts/step1_read_events_v1.md`: Prompt 1, đọc và mô tả.
- `prompts/step2_judge_impact_v1.md`: Prompt 2, phán đoán và viết.
- `tieu_chi_v2.md`: G-4 (chấm theo thông tin mới), G-9 (trọng tâm toàn bài), A35, mục 4.3.

---

## 1. Mục tiêu và chỉ số

| Chỉ số | Cách đo | Mục tiêu |
|---|---|---|
| **Tỷ lệ lật nhãn** | Bộ ranh giới (mục 6.2): mỗi bài chạy 3 lần, đếm số bài có Priority hoặc Ảnh hưởng khác nhau giữa các lần | **0%** khi Prompt 1 lấy từ cache; ≤ 5% khi đọc lại từ đầu |
| Độ đúng mới/cũ của từng sự kiện | So với nhãn mới/cũ do người gán (mục 6.1) | ≥ 95% |
| Độ đúng sự kiện trọng tâm | So với nhãn người gán | ≥ 95% |
| Độ chính xác Priority và Ảnh hưởng | Golden set: 22 bài KB và 100 bài watchlist | Không thấp hơn pipeline hiện tại |
| Tỷ lệ cờ cần duyệt | `newness_conflict`, `focus_uncertain`, `model_disagrees` | ≤ 15% số bài |

---

## 2. Luồng xử lý

```
Bài báo
  │
  ├─ [Code] segment: chuẩn hóa, đánh số đoạn [T], [P1]…[Pn]
  ├─ [Code] cache: khóa = sha256(nội dung) + "step1_read_events_v1" + model → có thì dùng lại
  ├─ [LLM]  Prompt 1: ĐỌC → mentions, events (mốc thời gian, cách trình bày, câu trích, đoạn), news_hook
  ├─ [Code] kiểm tra câu trích, đoạn, khóa *_pct
  ├─ [Code] newness: xác định MỚI / CẬP NHẬT / CŨ cho từng sự kiện   ← trọng tâm của plan này
  ├─ [Code] prior events: đối chiếu với kho sự kiện đã ghi nhận về mã
  ├─ [Code] relevance: bảng vai trò → nhãn (đã có trong rules.py)
  ├─ [Code] focus: chọn sự kiện trọng tâm trong số sự kiện MỚI
  ├─ [Code] priority: ngưỡng, điều chỉnh bậc, sàn (đã có trong rules.py)
  ├─ [LLM]  Prompt 2: PHÁN ĐOÁN + VIẾT trên bảng đã chốt
  ├─ [Code] aggregate (mục 4.3 tiêu chí) + kiểm tra lý giải
  └─ [Code] lưu sự kiện MỚI vào kho prior events (dùng cho các bài sau)
```

---

## 3. Xác nhận độ mới (`pipeline/newness.py`)

### 3.1. Đầu vào cho mỗi sự kiện

Lấy từ Prompt 1:

| Trường | Ví dụ (WL-015) |
|---|---|
| `time_anchor.kind` | `day`, `period`, `as_of`, `past`, `none` |
| `time_anchor.text` | "30/9", "Tại ngày 30/6/2026", "Lũy kế 9 tháng" |
| `presented_as` | `announced_now`, `update`, `recalled`, `context`, `analysis`, `price_move` |
| `presented_as_quote` | "Trong khi đó, Novaland đang chuẩn bị…" |

Cộng thêm ngày đăng bài, và kết quả đối chiếu kho sự kiện cũ (mục 3.5).

### 3.2. Phân tích mốc thời gian (`parse_anchor`)

Chỉ dùng biểu thức chính quy, không gọi model. Năm thiếu thì lấy theo ngày đăng; nếu ra ngày ở tương lai xa so với ngày đăng thì lùi một năm.

| Mẫu chữ | Kết quả |
|---|---|
| `dd/mm/yyyy`, `dd/mm`, `ngày dd/mm`, `sáng/chiều dd/mm`, `phiên dd/mm` | `day` → một ngày |
| `hôm nay`, `vừa qua`, `mới đây`, `cùng ngày` | `day` → ngày đăng |
| `quý I…IV/yyyy`, `quý 3 năm yyyy` | `period` → ngày cuối quý |
| `6 tháng`, `9 tháng`, `nửa đầu năm`, `lũy kế n tháng (đầu năm yyyy)` | `period` → cuối tháng thứ n |
| `tháng m/yyyy`, `tháng m` | `period` → cuối tháng m |
| `năm yyyy`, `cả năm` | `period` → 31/12 |
| `tại ngày …`, `đến cuối quý …`, `cuối kỳ`, `tính đến …` | `as_of` → ngày đó |
| `trước đó`, `hồi đầu năm`, `năm ngoái`, `đã từng` | `past` → không có ngày |

Kết quả gồm `anchor_date` và `days_before = ngày đăng − anchor_date`.

### 3.3. Bảng quyết định mới/cũ

Áp **theo thứ tự từ trên xuống**; dòng đầu tiên khớp sẽ quyết định. Tham số đặt trong `config`.

| # | Điều kiện | Kết quả | `newness_reason` (ghi vào bảng đã chốt) |
|---|---|---|---|
| 1 | `presented_as = price_move` | Cũ với vai trò trọng tâm (loại A35, không làm trọng tâm khi có sự kiện khác) | "diễn biến giá" |
| 2 | Trùng một sự kiện trong kho đã ghi nhận trước ngày đăng (mục 3.5), và bài không nêu điều khoản mới | **CẬP NHẬT** nếu `presented_as = update`, ngược lại **CŨ** | "trùng sự kiện ngày dd/mm" |
| 3 | `kind = as_of` và `days_before > AS_OF_MAX_DAYS` (mặc định 45) | **CŨ** | "số dư tại dd/mm, cách ngày đăng N ngày" |
| 4 | `kind = period` và `days_before > PERIOD_REPORT_MAX_DAYS` (mặc định 50, đủ cho mùa công bố kết quả quý) | **CŨ** | "kỳ kết thúc dd/mm, cách N ngày" |
| 5 | `kind = day` và `days_before > DAY_MAX_DAYS` (mặc định 7) | **CŨ**, hoặc **CẬP NHẬT** nếu `presented_as = update` | "mốc dd/mm, cách N ngày" |
| 6 | `presented_as ∈ {recalled, context}` | **CŨ** | "bài trình bày như bối cảnh: '…'" |
| 7 | `kind = past` | **CŨ** | "quá khứ: '…'" |
| 8 | `presented_as = update` | **CẬP NHẬT** (vẫn là thông tin mới, Priority áp P-MOD-1) | "cập nhật tiến độ" |
| 9 | `presented_as = announced_now`, hoặc `kind = day` với `days_before ≤ DAY_MAX_DAYS` | **MỚI** | "công bố/xảy ra dd/mm" |
| 10 | `presented_as = analysis` và không có mốc | **MỚI** (là nội dung phân tích của bài, loại A24) | "nhận định trong bài" |
| 11 | Không dòng nào khớp | **MỚI**, gắn cờ `newness_unknown` | "không đủ căn cứ" |

**Cờ `newness_conflict`:** gắn khi các căn cứ mâu thuẫn nhau, ví dụ `presented_as = announced_now` nhưng mốc cách 60 ngày. Kết quả vẫn theo bảng trên, nhưng bài được đưa vào danh sách duyệt.

### 3.4. Ví dụ áp vào WL-015 (đăng 6/10/2026)

| Sự kiện | Mốc | Trình bày | Dòng khớp | Kết quả |
|---|---|---|---|---|
| E1 A36 bác bỏ tin đồn | day "ngay sau khi…" (≈ 6/10) | announced_now | 9 | **MỚI** |
| E2 A35 giá −2,84% | day 6/10 | price_move | 1 | Không làm trọng tâm |
| E3 A06 chào bán 800,7 triệu CP | day 30/9 (6 ngày) | context | 2 nếu kho có tin 21/9; nếu không, 6 | **CŨ** |
| E4 A12 góp 2.054 tỷ | none | recalled | 6 | **CŨ** |
| E5 A18 nợ quá hạn 16.700 tỷ | as_of 30/6 (98 ngày) | context | 3 | **CŨ** |

Chỉ còn E1 là mới và đủ điều kiện làm trọng tâm, nên **không cần phán đoán**. Kết quả: A36 / Trung bình / Trung lập.

### 3.5. Kho sự kiện đã ghi nhận (`pipeline/event_store.py`)

Nhiều bài không cho biết tin đã công bố hay chưa. Ví dụ WL-019/020 viết về đợt chào bán 800 triệu cổ phiếu như tin mới, trong khi tin đã có từ 21/9. Kho này lưu **lần đầu tiên** mỗi sự kiện xuất hiện, để biết một sự kiện trong bài mới đã được công bố từ trước hay chưa.

> **Không bắt buộc ở v1.** Bảng 3.3 chỉ dựa vào chữ trong bài (mốc thời gian, cách trình bày) đã xử lý được phần lớn bài. Chỉ triển khai kho khi đo trên bộ ranh giới thấy **lỗi "tin cũ được viết như tin mới, bài không có dấu hiệu nào"** chiếm từ 3% số sự kiện trở lên. Khi pipeline chạy hằng ngày, có thể bật trước nguồn B (kết quả của chính pipeline), vì nguồn này gần như không tốn thêm chi phí.

**Kho phải lưu theo thực thể, không chỉ theo mã.** Một sự kiện của MSR phải được tìm thấy khi đọc bài về MSN; một sự kiện của Bách Hóa Xanh phải được tìm thấy khi đọc bài về MWG.

#### 3.5.1. Nguồn dữ liệu

| # | Nguồn | Lấy gì | Áp cho | Vai trò |
|---|---|---|---|---|
| A | **Công bố thông tin chính thức**: trang CBTT của HOSE/HNX theo mã, trang quan hệ nhà đầu tư (IR) của doanh nghiệp | Ngày công bố, tiêu đề, đường dẫn, file đính kèm | Mã mẹ **và mọi công ty con/liên kết niêm yết riêng**: MWG + DMX; MSN + MCH, MSR, MML, TCB; FPT + FOC, FOX, FRT; HPG; NVL | **Ngày công bố đầu tiên chuẩn nhất.** Thứ tự ưu tiên khi có xung đột ngày |
| B | **Kết quả của chính pipeline**: mỗi bài sau Prompt 1 và bước xác định độ mới | Các sự kiện MỚI hoặc CẬP NHẬT, với `first_seen` = ngày đăng | Mọi thực thể được nhận diện trong bài | Kho tự lớn theo thời gian, phủ cả công ty con **chưa niêm yết** (vốn không có trang CBTT riêng) |
| C | **Crawl lùi để khởi tạo**: trang tin theo mã (cafef, vietstock…) và tìm kiếm theo **tên và alias của từng thực thể** trong hồ sơ mã | Tin 60–90 ngày trước | Mã mẹ, công ty con niêm yết, và thực thể chưa niêm yết (tìm "Bách Hóa Xanh", "Hòa Phát Dung Quất", "Aqua City"…) | Có dữ liệu ngay từ ngày đầu |

- **Nguồn A, xử lý tiêu đề CBTT:** phân loại bằng từ khóa trước, không gọi model. Ví dụ "chào bán", "phát hành" thì A06/A07; "giao dịch không hưởng quyền", "cổ tức" thì A09/A07; "giao dịch cổ phiếu của người nội bộ" thì A21/A22; "báo cáo tài chính", "kết quả kinh doanh" thì A01. Tiêu đề không khớp từ khóa nào mới cho đọc file đính kèm bằng Prompt 1.
- **Nguồn C:** chạy lại toàn bộ pipeline đọc (Prompt 1 + newness) theo thứ tự ngày đăng tăng dần, để kho được xây đúng trình tự thời gian.

#### 3.5.2. Cấu trúc một bản ghi

```json
{
  "event_key": "MSR|A09|2026-10-02|dps=2000",
  "entity": "Masan High-Tech Materials",
  "entity_ticker": "MSR",
  "parent_tickers": ["MSN"],
  "related_entities": [],
  "type": "A09",
  "description": "MSR tạm ứng cổ tức tiền mặt 20%",
  "numbers": {"dps_vnd": 2000, "payout_value_vnd": 2210000000000},
  "first_seen": "2026-10-02",
  "first_source": "cbtt | news",
  "first_url": "...",
  "later_mentions": [{"date": "2026-10-05", "url": "...", "presented_as": "update"}],
  "status": "announced | updated | completed | cancelled"
}
```

- **`entity`** là tên chuẩn trong hồ sơ mã.
- **`parent_tickers`** suy ra từ hồ sơ: thực thể thuộc hồ sơ của mã nào thì mã đó là mẹ. Thực thể có `kind: shareholder` (Diamond Properties) cũng gắn vào mã NVL.
- **Sự kiện có nhiều bên** (MSN mua thêm cổ phần MCH qua Lepus) được lưu với `entity = Masan Consumer` và `related_entities = [Masan, Lepus]`. Tìm theo bất kỳ thực thể nào trong số đó đều ra.
- **`later_mentions`** ghi các lần nhắc lại sau, để biết chuỗi diễn biến của sự kiện: công bố → GDKHQ → gia hạn → kết quả.

#### 3.5.3. Nhận diện thực thể

1. `subject_entity` và `parties` từ Prompt 1 được chuẩn hóa: chữ thường, bỏ dấu, bỏ "CTCP", "Công ty TNHH", "Tập đoàn". Sau đó so với `name` và `aliases` trong hồ sơ mã.
2. Khớp thì dùng tên chuẩn. Không khớp nhưng có chứa tên mẹ (ví dụ "Hòa Phát Bình Dương" có "Hòa Phát") thì gắn tạm vào mã mẹ, và ghi vào **danh sách thực thể chưa có trong hồ sơ** (`data/event_store/unknown_entities.csv`) để người bổ sung vào `profiles/*.yaml`.
3. Không khớp gì thì lưu với `entity` nguyên văn và `parent_tickers` lấy theo các mã liên quan trong bài.

Hồ sơ mã cần được bổ sung đầy đủ trước khi chạy kho. Ví dụ WL-068 có "Hòa Phát Bình Dương", hiện chưa có trong `profiles/HPG.yaml`.

#### 3.5.4. Tra cứu khi xác định độ mới

Với mỗi sự kiện trong bài mới:

1. **Tập thực thể cần tìm** = thực thể chủ thể và các bên, sau khi nhận diện, cộng với công ty mẹ và công ty con có liên quan theo hồ sơ.
2. **Ứng viên** = các bản ghi có `entity` hoặc `related_entities` thuộc tập trên, cùng nhóm loại (A06/A07, A21/A22, còn lại là chính nó), và `first_seen` nằm trong khoảng `PRIOR_WINDOW_DAYS` (mặc định 60 ngày) **trước** ngày đăng.
3. **Trùng** khi có ít nhất một khóa số khớp với sai lệch ≤ 1%. Nếu không có số: cùng loại, cùng thực thể, và mô tả trùng ít nhất 60% từ khóa.
4. **Cùng một đợt tin:** nếu `first_seen` cách ngày đăng không quá `SAME_WAVE_DAYS` (mặc định 1 ngày), vẫn coi là **MỚI**. Nhiều báo đưa cùng một tin trong một hai ngày đều là tin mới. Chỉ khi cách xa hơn mới xếp **CŨ** hoặc **CẬP NHẬT** (dòng 2 của bảng 3.3).
5. Ghi lý do vào `newness_reason`, ví dụ "trùng sự kiện MSR ngày 02/10 (CBTT)".

#### 3.5.5. Phạm vi v1

- Không gọi model để so ngữ nghĩa. Phương án dùng vector chỉ xét nếu đo thấy bỏ sót nhiều.
- Lưu bằng SQLite dưới `data/event_store/`, gồm bảng `events`, `mentions` và `unknown_entities`.
- Việc crawl nguồn A theo lịch (hằng ngày) là phần vận hành, làm sau khi kho chạy ổn với nguồn B và C.

---

## 4. Chọn sự kiện trọng tâm (`pipeline/focus.py`)

Đầu vào là các sự kiện liên quan đến một mã, đã có kết quả mới/cũ.

1. **Ứng viên** = sự kiện MỚI hoặc CẬP NHẬT, không phải A35, không phải A33 hay A34.
   - Không có ứng viên: lấy A24 (phân tích) nếu bài có. Nếu không, lấy A35 với Priority Thấp (bài chỉ có diễn biến giá). Nếu vẫn không có, gắn cờ `no_event`.
2. **Một ứng viên** thì chọn luôn. Mã quy tắc G-9 được ghi kèm, và lần chọn này không có độ bất định.
3. **Nhiều ứng viên:**
   1. Nếu ứng viên trùng với `news_hook.event_id` của Prompt 1 thì chọn ứng viên đó.
   2. Nếu không, chọn theo thứ tự cố định: công bố hoặc sự kiện của doanh nghiệp (A01–A22, A25–A27, A36) > tin ngành hoặc vĩ mô có tên mã (A31, A32) > phân tích (A24) > A23.
   3. Nếu vẫn ngang nhau (cùng hạng), lấy sự kiện xuất hiện ở đoạn sớm nhất và gắn cờ `focus_uncertain`.
4. **Chi tiết cùng loại:** các ứng viên còn lại cùng loại với trọng tâm (ví dụ E1 sản lượng 9 tháng và E2 sản lượng quý 3 ở WL-068) được gộp số liệu vào trọng tâm để so ngưỡng Priority.

Bước này không gọi model. Nếu vẫn muốn có điểm từ Jev, đó chỉ là điểm chấm song song kèm cờ `jev_disagrees`; điểm này không thay đổi lựa chọn.

---

## 5. Thay đổi code

| # | Việc | File | Ghi chú |
|---|---|---|---|
| 1 | Đánh số đoạn | `pipeline/segment.py` (mới) | Tách theo dòng; giữ [T] cho tiêu đề; trả bản đồ `P# → văn bản` để kiểm tra câu trích |
| 2 | Prompt 1 và schema mới | `pipeline/extract.py`, `pipeline/schemas.py` | Thêm `paragraphs`, `time_anchor`, `presented_as`, `presented_as_quote`, `news_hook`; bỏ `is_new_info` khỏi schema của model (code tính) |
| 3 | Cache kết quả Prompt 1 | `pipeline/extract_cache.py` (mới) | Khóa `sha256(content) + prompt_version + model`; lưu JSON dưới `data/extract_cache/` |
| 4 | Phân tích mốc thời gian và bảng quyết định | `pipeline/newness.py` (mới) | `parse_anchor()`, `classify()` theo bảng 3.3; tham số trong `config.py` |
| 5 | Kho sự kiện theo thực thể | `pipeline/event_store.py` (mới), `pipeline/entities.py` (mới) | `resolve_entity()`, `lookup()`, `record()`; script nạp trước (nguồn C); crawl CBTT (nguồn A) cho mã mẹ và công ty con niêm yết; báo cáo thực thể chưa có trong hồ sơ |
| 6 | Chọn trọng tâm | `pipeline/focus.py` (mới) | Theo mục 4; thay đoạn chọn trọng tâm trong `rules.evaluate_ticker` và `graph._focus_event` |
| 7 | Prompt 2 | `pipeline/judge.py` (mới, thay `write.py`) | Lập bảng đã chốt, gọi Prompt 2, kiểm tra `locked_violation` |
| 8 | Tổng hợp Ảnh hưởng từ yếu tố | `pipeline/rules.py` | `aggregate()` theo mục 4.3; các handler hiện có giữ làm kiểm tra chéo |
| 9 | Graph | `pipeline/graph.py` | segment → read (cache) → newness → focus → rules → judge → aggregate/validate → store |
| 10 | Log và báo cáo | `eval/run_one.py`, `eval/run_eval.py` | In mới/cũ kèm `newness_reason`; cột trong CSV; mục "tỷ lệ lật" trong report |

---

## 6. Kiểm thử

### 6.1. Golden cho từng sự kiện (người gán)

File `research/boundary_events_gold.csv`, mỗi dòng là `bài, mã, câu trích nhận diện sự kiện, mới/cũ/cập nhật, có phải trọng tâm`. Bắt đầu với các bài:

| Bài | Vì sao chọn |
|---|---|
| WL-015 | Bác bỏ tin đồn, kèm chào bán và nợ quá hạn làm bối cảnh |
| WL-019, WL-020 | Bài viết về đợt chào bán như tin mới, nhưng đã công bố 21/9 (cần kho sự kiện) |
| WL-041 | Bài giải thích, kết quả kinh doanh 8 tháng là số cũ |
| WL-068 | Tiêu đề nói về giá, nội dung có công bố sản lượng cùng ngày |
| WL-091 | Không vào rổ FTSE, đặt cạnh BHX (mới) và tiền mặt (cũ) |
| KB-6, KB-7 | Gia hạn chào bán (cập nhật); kết quả kinh doanh có yếu tố ngược chiều |
| KB-15 | Góp vốn, kèm pháp lý dự án làm bối cảnh |

### 6.2. Test

- **Unit, `tests/test_newness.py`:**
  - `parse_anchor()` với khoảng 30 mẫu chữ tiếng Việt: "quý III/2026", "9 tháng đầu năm", "Tại ngày 30/6/2026", "phiên sáng 6/10", "cuối tháng 9"…
  - Từng dòng của bảng 3.3, kể cả trường hợp năm thiếu và mốc ở đầu năm sau.
- **Unit, `tests/test_focus.py`:** một ứng viên; nhiều ứng viên có `news_hook`; nhiều ứng viên ngang hạng; chỉ có A35; chỉ có A24.
- **Unit, `tests/test_event_store.py`:** khớp theo khóa số trong sai lệch 1%; khớp theo từ khóa; ngoài cửa sổ 60 ngày thì không khớp.
- **Tích hợp, offline:** dùng kết quả Prompt 1 đã lưu cho các bài ở mục 6.1. Kiểm tra mới/cũ và trọng tâm khớp golden. Không gọi model.
- **Đo tỷ lệ lật, gọi model:**
  - `run_eval --boundary --repeat 3`, chạy hai chế độ: dùng cache Prompt 1 và đọc lại từ đầu.
  - Báo cáo có số bài lật nhãn, bước gây lật (Prompt 1, code hay Prompt 2), và các cờ.

---

## 7. Các giai đoạn

| Giai đoạn | Việc | Kết quả kiểm chứng |
|---|---|---|
| 1 | `segment.py`, `newness.py` (bảng 3.3), `focus.py`, unit test; chạy trên **kết quả extract hiện có**, dùng `is_new_info` và mô tả làm căn cứ tạm | Chọn đúng trọng tâm trên bộ ranh giới, test offline xanh |
| 2 | Prompt 1 mới (`step1_read_events_v1`), schema, cache; chạy bộ ranh giới 3 lần | Độ đúng mới/cũ ≥ 95%; số sự kiện ổn định |
| 3 (tùy chọn) | Chỉ làm khi giai đoạn 2 đo thấy lỗi tin cũ không có dấu hiệu ≥ 3%. Kho sự kiện theo thực thể: nhận diện thực thể, nạp trước từ 122 bài và crawl lùi 60 ngày (nguồn C); bổ sung hồ sơ mã theo danh sách thực thể chưa có | WL-019/020 được xếp CŨ hoặc CẬP NHẬT; tin MSR/MCH/DMX tìm thấy khi đọc bài MSN/MWG |
| 3b (tùy chọn) | Crawl CBTT (nguồn A) cho mã mẹ và công ty con niêm yết, chạy hằng ngày | `first_seen` lấy theo ngày CBTT khi có |
| 4 | Prompt 2 (`step2_judge_impact_v1`), `aggregate()`, kiểm tra `locked_violation` | Tỷ lệ lật 0% khi dùng cache Prompt 1 |
| 5 | Chạy cả golden set, so với pipeline hiện tại, cập nhật tài liệu thiết kế | Độ chính xác không giảm; tỷ lệ cờ ≤ 15% |

---

## 8. Rủi ro và cách xử lý

| Rủi ro | Xử lý |
|---|---|
| Prompt 1 ghi sai `presented_as` hoặc mốc thời gian | Bảng 3.3 ưu tiên mốc thời gian (dòng 3–5) hơn cách trình bày (dòng 6); mâu thuẫn thì gắn `newness_conflict` |
| Tham số ngày (45/50/7) không hợp với mọi loại sự kiện | Đặt tham số theo nhóm loại trong `config`, hiệu chỉnh trên bộ ranh giới |
| Hồ sơ mã thiếu thực thể, nên sự kiện công ty con không được liên kết với mã mẹ | Danh sách `unknown_entities` để bổ sung hồ sơ; tạm gắn theo tên mẹ nếu tên thực thể chứa tên mẹ |
| Kho sự kiện khớp nhầm hai đợt phát hành khác nhau | Bắt buộc khớp khóa số với sai lệch ≤ 1%; cửa sổ 60 ngày; lưu lý do khớp để kiểm tra |
| Kho thiếu dữ liệu ở thời gian đầu | Nạp trước từ dữ liệu đã crawl; kho tự lớn dần theo thời gian |
| Bài chỉ có phân tích (A24) bị xếp không có trọng tâm | Mục 4 bước 1 xử lý riêng: A24 làm trọng tâm khi không có tin mới |
| Prompt 2 không tuân thủ bảng đã chốt | Code bỏ phần vi phạm, gắn `locked_violation`; trường `concerns` thu các bất đồng để chỉnh quy tắc |
