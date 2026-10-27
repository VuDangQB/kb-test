"""Crawler checks on canned HTML (no network)."""

from datetime import date

from pipeline.crawl import (from_embedded_state, is_noise, jsonld_objects, looks_like_code,
                            looks_like_listing, parse_date, pdf_links, published_date, quality, strip_noise)

TITLE = "NVL: Thông báo điều chỉnh thời gian thực hiện quyền mua trong đợt chào bán cổ phiếu ra công chúng"
BODY = ("Novaland (NVL) điều chỉnh thời gian thực hiện quyền mua trong đợt chào bán hơn 800 triệu cổ phiếu "
        "ra công chúng, gia hạn đăng ký và nộp tiền đến 26/11/2026. ") * 5
SIDEBAR = "\n".join([
    "Bà Nguyễn Thanh Hằng - Thành viên BKS CTCP Du lịch Đắk Lắk có kế hoạch mua 1 triệu cp DLD từ 28/10...",
    "Chủ tịch Everland mua thêm gần 1.5 triệu cp EVG khi thị giá liên tục lao dốc...",
    "Ông Đậu Trường Sinh đăng ký mua 200 ngàn cp trong giai đoạn...",
    "Ông Lê Hữu Báu vừa mua thành công 8 triệu cp SSB trong ngày...",
    "Ngày 21/10, HD Capital đã mua 2 triệu cp AAS để nâng sở hữu từ 10 triệu cp lên 12 triệu cp, tương ứng...",
])


def test_quality_accepts_article_and_rejects_sidebar_short_and_code():
    assert quality(BODY, [TITLE]) == ""
    assert "danh sách" in quality(SIDEBAR * 2, [TITLE])
    assert "ngắn" in quality("Novaland gia hạn.", [TITLE])
    assert "mã nguồn" in quality('c:["$","div",null,{"className":"w-full"}]' * 30, [TITLE])
    assert "khớp" in quality("Giá vàng hôm nay tăng mạnh trên thị trường thế giới. " * 20, [TITLE])


def test_sapo_counts_toward_title_match():
    body = "Nhóm cổ phiếu bất động sản trở thành điểm sáng trong phiên 9-10, NVL tăng trần. " * 10
    title = "Một cổ phiếu nhà Masan bị khối ngoại bán gần 9.600 tỉ đồng"
    sapo = "Khối ngoại bán cổ phiếu MCH của Masan với giá trị gần 9.600 tỉ đồng trong phiên 9-10."
    assert quality(body, [title]) != ""
    assert quality(body, [title], sapo) == ""


def test_noise_matches_whole_tokens_only():
    assert is_noise("realted-news w-1140") and is_noise("box-tin-lien-quan") and is_noise("article-share")
    assert not is_noise("detail-primary relative z-20") and not is_noise("article-content")
    html = ('<html><body><section class="detail-primary relative"><p>Nội dung chính</p></section>'
            '<div class="realted-news"><p>TTC Land teaser</p></div></body></html>')
    cleaned = strip_noise(html)
    assert "Nội dung chính" in cleaned and "TTC Land" not in cleaned


def test_listing_and_code_detection():
    assert looks_like_listing(SIDEBAR)
    assert not looks_like_listing(BODY)
    assert looks_like_code('self.__next_f "_next/static/chunks/a.js"')


def test_pdf_links_keep_only_related_attachments():
    html = ('<a href="https://x.vn/qc/Bang-gia-quang-cao.pdf">qc</a>'
            '<a href="https://cdn.vn/download/mwg-thong-bao-co-tuc.pdf?v=123">tb</a>')
    assert pdf_links(html, "https://x.vn/", ["MWG: ngày GDKHQ chi trả cổ tức"]) == [
        "https://cdn.vn/download/mwg-thong-bao-co-tuc.pdf?v=123"]


def test_dates_from_jsonld_meta_and_cafef_id():
    html = ('<script type="application/ld+json">{"@type":"NewsArticle","headline":"H",'
            '"datePublished":"2026-10-19T13:30:10+07:00","articleBody":"x"}</script>')
    assert published_date(html, jsonld_objects(html), "") == date(2026, 10, 19)
    assert published_date('<meta itemprop="datePublished" content="2002-01-01">', [], "") is None
    assert published_date("", [], "https://cafef.vn/fpt-lai-188261021093213162.chn") == date(2026, 10, 21)
    assert parse_date("19/10/2026 13:30") == date(2026, 10, 19)


def test_embedded_state_reads_next_data_html():
    html = ('<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"article":'
            '{"content":"<p>' + "Hòa Phát bán 10,3 triệu tấn thép trong 9 tháng. " * 10 + '</p>"}}}}</script>')
    assert from_embedded_state(html).startswith("Hòa Phát bán 10,3 triệu tấn")


def test_unrelated_link_list_is_dropped_but_article_bullets_kept():
    from pipeline.crawl import drop_link_lists
    title = "Tháng 10/2026, chạy thử Nhà máy sản xuất ray và thép đặc biệt Hòa Phát Dung Quất"
    junk = ("Nhà máy đạt 70% tiến độ.\n- Báo chí Việt Nam - Thái Lan tăng cường hợp tác\n"
            "- Quảng Trị tháo gỡ vướng mắc, tăng thu tiền sử dụng đất\n- Bộ Tài chính đề xuất cơ chế đặc thù\n"
            "Công suất 700.000 tấn/năm.")
    assert "Báo chí" not in drop_link_lists(junk, title) and "700.000" in drop_link_lists(junk, title)
    bullets = ("Kết quả:\n- Hòa Phát sản xuất 3,7 triệu tấn thép thô\n- Hòa Phát bán 3,8 triệu tấn thép\n"
               "- Thép cuộn cán nóng Hòa Phát tăng 64%")
    assert drop_link_lists(bullets, "Hòa Phát sản xuất và bán thép quý 3") == bullets
