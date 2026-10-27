from pipeline.schemas import Evidence, Impact, Priority, Relevance, TickerResult
from pipeline.validate import check

CONTENT = "Novaland chào bán 800,7 triệu cổ phiếu, giá 10.000 đồng, dự kiến thu 8.007 tỷ đồng."


def result(**kw):
    base = dict(
        ticker="NVL", relevance=Relevance.TT, priority=Priority.TB, impact=Impact.TRUNG_LAP,
        relevance_rule_ids=["R-TT-1"], priority_rule_ids=["A07", "P-TH-02", "P-MOD-1"], impact_rule_ids=["I-TL-a"],
        computed={"Tỷ lệ phát hành / CP lưu hành": "33,3%"},
        evidence=[Evidence(quote="800,7 triệu cổ phiếu")],
        relevance_reason="Trực tiếp vì Novaland là chủ thể đợt chào bán (R-TT-1).",
        priority_reason="Trung bình: đợt chào bán 800,7 triệu cổ phiếu tương đương 33,3% CP lưu hành, "
                        "nhưng bài chỉ gia hạn lịch đã công bố (P-TH-02, P-MOD-1).",
        impact_reason="Trung lập: pha loãng nhưng tiền 8.007 tỷ đồng dùng trả nợ (I-TL-a).",
    )
    base.update(kw)
    return TickerResult(**base)


def test_clean_result_passes():
    assert check(result(), CONTENT) == []


def test_invented_number_is_caught():
    errs = check(result(priority_reason="Trung bình vì quy mô 9.999 tỷ đồng (P-TH-02)."), CONTENT)
    assert any("9999" in e for e in errs)


def test_missing_rule_and_label_and_advice():
    errs = check(result(impact_reason="Nhà đầu tư nên mua vào lúc này."), CONTENT)
    assert any("nhãn" in e for e in errs)
    assert any("trích ít nhất" in e for e in errs)
    assert any("khuyến nghị" in e for e in errs)


def test_cao_requires_direct():
    errs = check(result(relevance=Relevance.GT, priority=Priority.CAO,
                        relevance_reason="Gián tiếp (R-TT-1).", priority_reason="Cao (P-TH-02)."), CONTENT)
    assert any("Cao" in e for e in errs)
