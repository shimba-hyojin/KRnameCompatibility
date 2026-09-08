"""
이름 궁합 계산 알고리즘.

확정 규칙 (동일 입력 -> 항상 동일 출력)
--------------------------------------
STEP 1. 두 이름을 각각 음절 단위로 분해하고 음절별 획수를 구한다.
        심효진 -> [7, 6, 6]   (심=ㅅ2+ㅣ1+ㅁ4, 효=ㅎ3+ㅛ3, 진=ㅈ3+ㅣ1+ㄴ2)
STEP 2. 두 배열을 교차(interleave)하여 하나의 숫자열을 만든다.
        A=[a1,a2,a3], B=[b1,b2,b3] -> [a1,b1,a2,b2,a3,b3]
        길이가 다르면 짧은 쪽이 끝난 뒤 남은 값을 순서대로 뒤에 붙인다.
STEP 3. 인접한 두 수를 더하고 10 이상이면 일의 자리만 남긴다 ((x+y) % 10).
        길이가 N이면 결과 길이는 N-1. 길이가 2가 될 때까지 반복한다.
STEP 4. 남은 두 자리 숫자를 십의 자리/일의 자리로 읽어 궁합도(%)로 삼는다.

주의: 항상 A(=심효진)를 교차의 첫 요소로 놓기 때문에 A와 B의 순서가 고정되며,
      따라서 결과도 고정된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from hangul import Syllable, decompose_name, validate_name

# 본인 이름은 항상 고정
OWNER_NAME = "심효진"
OWNER_NAME_JA = "シム・ヒョジン"


# ---------------------------------------------------------------------------
# 점수 구간별 코멘트 (일본어) — 순수 함수, 랜덤 없음
# ---------------------------------------------------------------------------
TIERS = [
    (90, "運命級", "これはもう運命。ランチは毎日一緒でいいレベルです。"),
    (80, "大吉", "かなりの好相性。仕事もプライベートも話が合いそう。"),
    (70, "吉", "いいバランス。安心して隣の席に座れる相性です。"),
    (60, "中吉", "そこそこ good。会話のきっかけがあれば一気に伸びます。"),
    (50, "小吉", "普通が一番。長く付き合えるタイプの相性です。"),
    (40, "末吉", "少し努力が必要。まずはコーヒーでも一杯どうぞ。"),
    (20, "がんばれ", "相性は数字だけじゃない…と韓国では言います。"),
    (0, "ドンマイ", "画数の神様は気分屋なので、明日もう一度どうぞ。"),
]


def grade_of(score: int) -> Dict[str, str]:
    """점수에 대응하는 등급/코멘트를 반환."""
    for threshold, label, comment in TIERS:
        if score >= threshold:
            return {"label": label, "comment": comment}
    return {"label": "ドンマイ", "comment": "もう一度どうぞ。"}


@dataclass
class CompatibilityResult:
    """궁합 계산 결과 전체 (계산 과정 포함)."""

    owner_name: str
    partner_name: str
    score: int
    grade_label: str
    grade_comment: str
    owner_syllables: List[Syllable] = field(default_factory=list)
    partner_syllables: List[Syllable] = field(default_factory=list)
    owner_strokes: List[int] = field(default_factory=list)
    partner_strokes: List[int] = field(default_factory=list)
    interleaved: List[int] = field(default_factory=list)
    reduction_rows: List[List[int]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner_name": self.owner_name,
            "partner_name": self.partner_name,
            "score": self.score,
            "grade": {"label": self.grade_label, "comment": self.grade_comment},
            "steps": {
                "step1_decompose": {
                    "owner": [s.to_dict() for s in self.owner_syllables],
                    "partner": [s.to_dict() for s in self.partner_syllables],
                },
                "step2_strokes": {
                    "owner": self.owner_strokes,
                    "partner": self.partner_strokes,
                },
                "step3_interleaved": self.interleaved,
                "step4_reduction": self.reduction_rows,
                "step5_score": self.score,
            },
        }


def interleave(a: List[int], b: List[int]) -> List[int]:
    """
    두 배열을 교차 병합한다. 길이가 다르면 남은 요소를 뒤에 이어 붙인다.

    >>> interleave([7, 6, 6], [4, 9, 5])
    [7, 4, 6, 9, 6, 5]
    >>> interleave([7, 6, 6], [4, 9])
    [7, 4, 6, 9, 6]
    """
    merged: List[int] = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            merged.append(a[i])
        if i < len(b):
            merged.append(b[i])
    return merged


def reduce_to_two_digits(numbers: List[int]) -> List[List[int]]:
    """
    인접합 + 일의 자리 남기기를 길이 2가 될 때까지 반복한다.
    각 단계의 배열을 순서대로 담은 리스트를 반환한다 (첫 요소 = 입력 배열).

    >>> reduce_to_two_digits([7, 4, 8, 9])
    [[7, 4, 8, 9], [1, 2, 7], [3, 9]]
    """
    if len(numbers) < 2:
        raise ValueError("최소 2개의 숫자가 필요합니다.")

    rows: List[List[int]] = [list(numbers)]
    current = list(numbers)
    while len(current) > 2:
        current = [(current[i] + current[i + 1]) % 10 for i in range(len(current) - 1)]
        rows.append(current)
    return rows


def calculate(partner_name_raw: str, owner_name: str = OWNER_NAME) -> CompatibilityResult:
    """
    상대 이름을 받아 궁합 결과를 계산한다.
    검증 실패 시 hangul.HangulError 를 발생시킨다.
    """
    partner_name = validate_name(partner_name_raw)

    owner_syllables = decompose_name(owner_name)
    partner_syllables = decompose_name(partner_name)

    owner_strokes = [s.strokes for s in owner_syllables]
    partner_strokes = [s.strokes for s in partner_syllables]

    merged = interleave(owner_strokes, partner_strokes)
    rows = reduce_to_two_digits(merged)
    tens, ones = rows[-1]
    score = tens * 10 + ones

    grade = grade_of(score)

    return CompatibilityResult(
        owner_name=owner_name,
        partner_name=partner_name,
        score=score,
        grade_label=grade["label"],
        grade_comment=grade["comment"],
        owner_syllables=owner_syllables,
        partner_syllables=partner_syllables,
        owner_strokes=owner_strokes,
        partner_strokes=partner_strokes,
        interleaved=merged,
        reduction_rows=rows,
    )
