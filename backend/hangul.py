"""
한글 자모 분해 및 획수 계산 모듈.

설계 원칙
---------
1. 획수표는 이 파일에서 단 한 번만 정의하고, 모든 계산에 동일하게 적용한다.
2. 동일한 입력은 항상 동일한 출력을 낸다 (랜덤 요소 없음).
3. 계산의 모든 중간 단계를 함께 반환하여 프론트엔드에서 "どんな仕組み？"로 노출한다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List

# ---------------------------------------------------------------------------
# 유니코드 한글 음절 분해 상수
#   음절코드 = 0xAC00 + (초성index * 21 + 중성index) * 28 + 종성index
# ---------------------------------------------------------------------------
HANGUL_BASE = 0xAC00
HANGUL_LAST = 0xD7A3

CHOSUNG = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]

JUNGSUNG = [
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ",
    "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ",
]

JONGSUNG = [
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ",
    "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]

# ---------------------------------------------------------------------------
# 획수표 (STROKE TABLE) — 본 프로젝트의 확정 규칙
#
# 한글 획수 계산법은 여러 유파가 존재하므로, 아래 표를 유일한 기준으로 삼는다.
# 겹자음/겹받침은 구성 자음의 획수 합으로 정의한다. (예: ㄲ = ㄱ2 + ㄱ2 = 4)
# ---------------------------------------------------------------------------
CONSONANT_STROKES = {
    "ㄱ": 2, "ㄴ": 2, "ㄷ": 3, "ㄹ": 5, "ㅁ": 4,
    "ㅂ": 4, "ㅅ": 2, "ㅇ": 1, "ㅈ": 3, "ㅊ": 4,
    "ㅋ": 3, "ㅌ": 4, "ㅍ": 4, "ㅎ": 3,
}

# 겹자음 (초성으로 쓰이는 것)
DOUBLE_CONSONANT_STROKES = {
    "ㄲ": 4,   # ㄱ + ㄱ
    "ㄸ": 6,   # ㄷ + ㄷ
    "ㅃ": 8,   # ㅂ + ㅂ
    "ㅆ": 4,   # ㅅ + ㅅ
    "ㅉ": 6,   # ㅈ + ㅈ
}

# 겹받침 (종성 전용)
CLUSTER_JONGSUNG_STROKES = {
    "ㄳ": 4,   # ㄱ2 + ㅅ2
    "ㄵ": 5,   # ㄴ2 + ㅈ3
    "ㄶ": 5,   # ㄴ2 + ㅎ3
    "ㄺ": 7,   # ㄹ5 + ㄱ2
    "ㄻ": 9,   # ㄹ5 + ㅁ4
    "ㄼ": 9,   # ㄹ5 + ㅂ4
    "ㄽ": 7,   # ㄹ5 + ㅅ2
    "ㄾ": 9,   # ㄹ5 + ㅌ4
    "ㄿ": 9,   # ㄹ5 + ㅍ4
    "ㅀ": 8,   # ㄹ5 + ㅎ3
    "ㅄ": 6,   # ㅂ4 + ㅅ2
}

VOWEL_STROKES = {
    "ㅏ": 2, "ㅐ": 3, "ㅑ": 3, "ㅒ": 4, "ㅓ": 2,
    "ㅔ": 3, "ㅕ": 3, "ㅖ": 4, "ㅗ": 2, "ㅘ": 4,
    "ㅙ": 5, "ㅚ": 3, "ㅛ": 3, "ㅜ": 2, "ㅝ": 4,
    "ㅞ": 5, "ㅟ": 3, "ㅠ": 3, "ㅡ": 1, "ㅢ": 2,
    "ㅣ": 1,
}

# 전체 획수표 (조회용 단일 딕셔너리)
STROKE_TABLE = {
    **CONSONANT_STROKES,
    **DOUBLE_CONSONANT_STROKES,
    **CLUSTER_JONGSUNG_STROKES,
    **VOWEL_STROKES,
}

# 자모 종류 라벨 (프론트엔드 표시용, 일본어)
JAMO_ROLE_LABEL_JA = {
    "chosung": "初声(子音)",
    "jungsung": "中声(母音)",
    "jongsung": "終声(パッチム)",
}


class HangulError(ValueError):
    """한글 입력 검증 실패."""


@dataclass
class Jamo:
    """분해된 자모 하나."""

    char: str          # 자모 문자 (예: "ㅅ")
    role: str          # chosung / jungsung / jongsung
    role_label: str    # 일본어 라벨
    strokes: int       # 획수

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Syllable:
    """음절 하나의 분해 결과."""

    char: str              # 음절 문자 (예: "심")
    jamos: List[Jamo]      # 구성 자모
    strokes: int           # 음절 총 획수

    def to_dict(self) -> dict:
        return {
            "char": self.char,
            "jamos": [j.to_dict() for j in self.jamos],
            "strokes": self.strokes,
        }


def is_hangul_syllable(ch: str) -> bool:
    """완성형 한글 음절인지 확인."""
    return HANGUL_BASE <= ord(ch) <= HANGUL_LAST


def validate_name(name: str, *, min_len: int = 2, max_len: int = 8) -> str:
    """
    이름 입력 검증.

    - 앞뒤 공백 제거
    - 완성형 한글 음절만 허용 (자모 단독, 한자, 알파벳, 숫자, 공백 모두 거부)
    - 길이 제한
    """
    if name is None:
        raise HangulError("EMPTY")

    cleaned = name.strip()
    if not cleaned:
        raise HangulError("EMPTY")

    if not all(is_hangul_syllable(ch) for ch in cleaned):
        raise HangulError("NOT_HANGUL")

    if not (min_len <= len(cleaned) <= max_len):
        raise HangulError("LENGTH")

    return cleaned


def decompose_syllable(ch: str) -> List[Jamo]:
    """
    완성형 한글 음절 하나를 초성/중성/종성으로 분해하고 각 획수를 붙인다.
    """
    if not is_hangul_syllable(ch):
        raise HangulError("NOT_HANGUL")

    code = ord(ch) - HANGUL_BASE
    cho_idx = code // (21 * 28)
    jung_idx = (code % (21 * 28)) // 28
    jong_idx = code % 28

    jamos: List[Jamo] = []

    cho = CHOSUNG[cho_idx]
    jamos.append(
        Jamo(cho, "chosung", JAMO_ROLE_LABEL_JA["chosung"], STROKE_TABLE[cho])
    )

    jung = JUNGSUNG[jung_idx]
    jamos.append(
        Jamo(jung, "jungsung", JAMO_ROLE_LABEL_JA["jungsung"], STROKE_TABLE[jung])
    )

    if jong_idx != 0:
        jong = JONGSUNG[jong_idx]
        jamos.append(
            Jamo(jong, "jongsung", JAMO_ROLE_LABEL_JA["jongsung"], STROKE_TABLE[jong])
        )

    return jamos


def decompose_name(name: str) -> List[Syllable]:
    """이름 전체를 음절 단위로 분해하고 음절별 획수를 계산한다."""
    result: List[Syllable] = []
    for ch in name:
        jamos = decompose_syllable(ch)
        result.append(Syllable(char=ch, jamos=jamos, strokes=sum(j.strokes for j in jamos)))
    return result


def stroke_counts(name: str) -> List[int]:
    """이름의 음절별 획수 배열만 반환. 예: '심효진' -> [7, 6, 6]"""
    return [s.strokes for s in decompose_name(name)]
