"""DecisionModel: typed choice with probabilities. Jev when available, Claude otherwise."""

import os
from typing import Protocol

from pydantic import BaseModel

from . import config, llm


class DecisionModel(Protocol):
    def choice(self, state: str, question: str, options: list[str]) -> tuple[str, dict[str, float]]: ...


class _OptionProb(BaseModel):
    option: str
    probability: float


class _Choice(BaseModel):
    answer: str
    probabilities: list[_OptionProb]


DECISION_SYSTEM = """Bạn trả lời một câu hỏi lựa chọn về một bài báo chứng khoán, dựa trên dữ kiện được cung cấp và tiêu chí đánh giá kèm theo.
- `answer` phải là đúng một trong các lựa chọn được liệt kê, viết y nguyên.
- `probabilities` gán xác suất cho MỌI lựa chọn, tổng bằng 1, phản ánh trung thực mức chắc chắn.
- Không có bằng chứng trong bài thì không kết luận theo hướng đó."""


class ClaudeBackend:
    def __init__(self, criteria: str):
        self._system = [DECISION_SYSTEM, "# Tiêu chí\n\n" + criteria]

    def choice(self, state: str, question: str, options: list[str]) -> tuple[str, dict[str, float]]:
        user = f"{state}\n\nCâu hỏi: {question}\nCác lựa chọn: {' | '.join(options)}"
        out = llm.parse(self._system, user, _Choice, effort=config.EFFORT["decision"], max_tokens=4000,
                        stage="decision")
        probs = {o: 0.0 for o in options}
        for p in out.probabilities:
            if p.option in probs:
                probs[p.option] = max(0.0, p.probability)
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()} if total > 0 else {k: 1 / len(options) for k in options}
        answer = out.answer if out.answer in probs else max(probs, key=probs.get)
        return answer, probs


class JevBackend:
    """Adapter for TypeSafe Jev (Choice questions).

    Not wired yet: the request/response shape must come from TypeSafe's API docs.
    """

    def __init__(self):
        self.api_key = os.environ["TYPESAFE_API_KEY"]

    def choice(self, state: str, question: str, options: list[str]) -> tuple[str, dict[str, float]]:
        raise NotImplementedError("JevBackend chưa được nối API: cần tài liệu API của TypeSafe Jev.")


def make_decision_model(criteria: str) -> DecisionModel:
    return JevBackend() if config.DECISION_BACKEND == "jev" else ClaudeBackend(criteria)
