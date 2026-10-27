"""DecisionModel: typed choice with probabilities. Jev when configured, Claude otherwise."""

import json
import time
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

from pydantic import BaseModel

from . import config, llm, tracing


@dataclass
class Decision:
    answer: str
    probabilities: dict[str, float]   # every option, sums to 1
    confidence: float                 # how sure the model is; < config.LOW_CONFIDENCE → flag low_confidence


class DecisionModel(Protocol):
    def choice(self, state: str, question: str, options: dict[str, str]) -> Decision:
        """`options` maps each label to a short description of when it applies (may be "")."""
        ...


def _normalize(raw: dict[str, float], labels: list[str]) -> dict[str, float]:
    probs = {o: max(0.0, float(raw.get(o, 0.0))) for o in labels}
    total = sum(probs.values())
    return {k: v / total for k, v in probs.items()} if total > 0 else {k: 1 / len(labels) for k in labels}


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

    def choice(self, state: str, question: str, options: dict[str, str]) -> Decision:
        listed = "\n".join(f"- {o}: {d}" if d else f"- {o}" for o, d in options.items())
        user = f"{state}\n\nCâu hỏi: {question}\nCác lựa chọn:\n{listed}"
        out = llm.parse(self._system, user, _Choice, effort=config.EFFORT["decision"], max_tokens=4000,
                        stage="decision")
        probs = _normalize({p.option: p.probability for p in out.probabilities}, list(options))
        answer = out.answer if out.answer in probs else max(probs, key=probs.get)
        return Decision(answer, probs, probs[answer])


class JevBackend:
    """TypeSafe Jev (System One) via `typesafe-sdk`: one Choice question per decision.

    Jev answers from `state` + the question + option descriptions only; it does not get the
    full criteria document (its input tokens are billed and it needs no long instructions).
    """

    def __init__(self, model: str = config.JEV_MODEL):
        self.model = model

    @cached_property
    def _client(self):
        from typesafe_sdk import TypeSafeClient  # reads TYPESAFE_API_KEY
        return TypeSafeClient(model=self.model, timeout=config.JEV_TIMEOUT)

    def choice(self, state: str, question: str, options: dict[str, str]) -> Decision:
        from typesafe_sdk import Choice
        criteria = {o: (d or None) for o, d in options.items()}
        started = time.perf_counter()
        with tracing.llm_span("jev.system_one", "typesafe", self.model,
                              json.dumps({"question": question, "options": criteria, "state": state},
                                         ensure_ascii=False)) as set_result:
            resp = self._client.system_one(state=state,
                                           questions={"q": Choice(instructions=question, criteria=criteria)})
            ans = resp.choices["q"]
            set_result(json.dumps({"choice": ans.choice, "confidence": ans.confidence,
                                   "probabilities": ans.probabilities}, ensure_ascii=False),
                       resp.usage.input_tokens or 0, resp.usage.output_tokens or 0, resp.model)
        llm.record("decision", time.perf_counter() - started, "jev",
                   input_tokens=resp.usage.input_tokens or 0, output_tokens=resp.usage.output_tokens or 0)
        probs = _normalize(ans.probabilities, list(options))
        answer = ans.choice if ans.choice in probs else max(probs, key=probs.get)
        return Decision(answer, probs, float(ans.confidence))


def make_decision_model(criteria: str) -> DecisionModel:
    return JevBackend() if config.DECISION_BACKEND == "jev" else ClaudeBackend(criteria)
