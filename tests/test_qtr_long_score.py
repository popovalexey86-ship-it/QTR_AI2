import pytest

from strategies.qtr_long.score import LongScore, LongScoreGrade


def make_score(total_band: str) -> LongScore:
    values = {
        "ignore": (10, 10, 10, 5, 5, 5),      # 45
        "watch": (15, 15, 15, 5, 5, 5),       # 60
        "possible": (20, 15, 15, 10, 5, 5),   # 70
        "long": (20, 20, 20, 10, 5, 5),       # 80
        "a_plus": (25, 20, 20, 15, 10, 10),   # 100
    }
    return LongScore(*values[total_band])


def test_total_is_sum_of_transparent_components():
    score = make_score("a_plus")
    assert score.total == 100


@pytest.mark.parametrize(
    ("band", "grade"),
    [
        ("ignore", LongScoreGrade.IGNORE),
        ("watch", LongScoreGrade.WATCH),
        ("possible", LongScoreGrade.POSSIBLE),
        ("long", LongScoreGrade.LONG),
        ("a_plus", LongScoreGrade.A_PLUS),
    ],
)
def test_grade_thresholds(band, grade):
    assert make_score(band).grade == grade


def test_component_cannot_exceed_its_weight():
    with pytest.raises(ValueError):
        LongScore(
            structure=26,
            liquidity=20,
            order_block=20,
            momentum=15,
            volume=10,
            location=9,
        )
