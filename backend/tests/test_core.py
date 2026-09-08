"""
코어 로직 단위 테스트.
실행:  cd backend && python -m pytest -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compatibility import calculate, interleave, reduce_to_two_digits  # noqa: E402
from hangul import (  # noqa: E402
    STROKE_TABLE,
    HangulError,
    decompose_name,
    stroke_counts,
    validate_name,
)


# --------------------------------------------------------------- 자모 분해
def test_decompose_sim():
    syls = decompose_name("심")
    assert [j.char for j in syls[0].jamos] == ["ㅅ", "ㅣ", "ㅁ"]
    # ㅅ2 + ㅣ1 + ㅁ4 = 7
    assert syls[0].strokes == 7


def test_decompose_no_jongsung():
    syls = decompose_name("효")
    assert [j.char for j in syls[0].jamos] == ["ㅎ", "ㅛ"]
    assert syls[0].strokes == 3 + 3


def test_owner_strokes_fixed():
    # 심(7) 효(6) 진(6)
    assert stroke_counts("심효진") == [7, 6, 6]


def test_cluster_jongsung():
    # 값 -> ㄱ2 + ㅏ2 + ㅄ6 = 10
    assert stroke_counts("값") == [10]


def test_double_chosung():
    # 까 -> ㄲ4 + ㅏ2 = 6
    assert stroke_counts("까") == [6]


def test_stroke_table_complete():
    """모든 자모가 획수표에 존재해야 한다."""
    from hangul import CHOSUNG, JONGSUNG, JUNGSUNG

    for jamo in CHOSUNG + JUNGSUNG + [j for j in JONGSUNG if j]:
        assert jamo in STROKE_TABLE, f"획수표에 {jamo} 없음"


# --------------------------------------------------------------- 검증
@pytest.mark.parametrize(
    "bad", ["", "   ", "야", "yamada", "山田", "야마다 타로", "가나다라마바사아자", "ㄱㄴ"]
)
def test_validate_rejects(bad):
    with pytest.raises(HangulError):
        validate_name(bad)


def test_validate_trims():
    assert validate_name("  야마다  ") == "야마다"


# --------------------------------------------------------------- 알고리즘
def test_interleave_equal_length():
    assert interleave([7, 6, 6], [4, 9, 5]) == [7, 4, 6, 9, 6, 5]


def test_interleave_unequal_length():
    assert interleave([7, 6, 6], [4, 9]) == [7, 4, 6, 9, 6]
    assert interleave([7, 6], [4, 9, 5, 2]) == [7, 4, 6, 9, 5, 2]


def test_reduce_steps():
    rows = reduce_to_two_digits([7, 4, 8, 9])
    assert rows == [[7, 4, 8, 9], [1, 2, 7], [3, 9]]


def test_reduce_mod10():
    # 9+8=17 -> 7
    assert reduce_to_two_digits([9, 8, 1])[1] == [7, 9]


def test_reduce_requires_two():
    with pytest.raises(ValueError):
        reduce_to_two_digits([5])


# --------------------------------------------------------------- 통합
def test_calculate_deterministic():
    a = calculate("야마다")
    b = calculate("야마다")
    assert a.score == b.score
    assert a.reduction_rows == b.reduction_rows


def test_calculate_score_range():
    for name in ["야마다", "사토", "스즈키", "타나카", "와타나베", "이토"]:
        result = calculate(name)
        assert 0 <= result.score <= 99


def test_calculate_trace_shape():
    result = calculate("타나카")
    d = result.to_dict()
    assert d["owner_name"] == "심효진"
    assert d["partner_name"] == "타나카"
    assert d["steps"]["step2_strokes"]["owner"] == [7, 6, 6]
    # 마지막 감축 행은 두 자리
    assert len(d["steps"]["step4_reduction"][-1]) == 2
    # 점수 = 십의자리*10 + 일의자리
    tens, ones = d["steps"]["step4_reduction"][-1]
    assert d["score"] == tens * 10 + ones


def test_calculate_invalid_raises():
    with pytest.raises(HangulError):
        calculate("Tanaka")
