"""重复抄写发现（find_repetition）测试。"""

import pytest

from app.assembler import AssemblyError, assemble
from app.repetition import (
    MIN_REPEAT_LEN,
    MIN_SAME_KNOWN,
    _find_best_pair,
    find_repetition,
)

# 拼接结果：甲乙丙丁戊己 / 庚辛 / 甲乙丙丁戊己（相同六字由无关两字隔开）
REPEAT_SEGMENTS = ["甲乙丙丁戊己", "丁戊己庚辛甲乙", "辛甲乙丙丁戊己"]
REPEAT_TEXT = "甲乙丙丁戊己庚辛甲乙丙丁戊己"


def test_constants():
    assert MIN_REPEAT_LEN == 6
    assert MIN_SAME_KNOWN == 4


def test_find_best_pair_basic():
    assert _find_best_pair(REPEAT_TEXT) == (6, 6, 0, 8)


def test_find_best_pair_wildcard_compatible_but_not_known():
    # "?" 与任意字兼容，但不计入已知相同位
    assert _find_best_pair("甲乙?丁戊己庚甲乙丙丁戊己") == (6, 5, 0, 7)


def test_find_best_pair_requires_four_known_same():
    # 兼容段只有 2 个已知相同位（其余位置含 ?），不合格
    assert _find_best_pair("甲乙?????庚甲乙丙丁戊己") is None


def test_find_best_pair_requires_min_length():
    # 五字重复不足 6 字，不合格
    assert _find_best_pair("甲乙丙丁戊庚甲乙丙丁戊") is None


def test_find_best_pair_mismatch_breaks_run():
    # 异字（两侧均已知且不同）不兼容，兼容段被截断后均不足 6 字
    assert _find_best_pair("甲乙丙丁戊己庚甲乙丙戌戊己") is None


def test_find_best_pair_non_overlap_caps_length():
    # 区间不得重叠：长度被起点间距截断
    assert _find_best_pair("甲" * 20) == (10, 10, 0, 10)
    assert _find_best_pair("甲" * 12) == (6, 6, 0, 6)
    assert _find_best_pair("甲" * 11) is None


def test_longest_wins_over_more_known_same():
    # 长度 7（已知相同位 5）胜过长度 6（已知相同位 6）
    text = (
        "甲乙丙丁戊己庚" + "辛" + "甲乙丙?戊?庚"
        + "子丑寅卯辰巳" + "午" + "子丑寅卯辰巳"
    )
    assert _find_best_pair(text) == (7, 5, 0, 8)


def test_more_known_same_wins_on_equal_length():
    # 同为长度 6：已知相同位 6 胜过 5
    text = (
        "甲乙丙丁戊己" + "庚" + "甲乙丙丁?己"
        + "子丑寅卯辰巳" + "午" + "子丑寅卯辰巳"
    )
    assert _find_best_pair(text) == (6, 6, 13, 20)


def test_smallest_starts_on_full_tie():
    # 长度与已知相同位均相同：按两起点升序取首对
    text = "甲乙丙丁戊己" + "庚" + "甲乙丙丁戊己" + "辛" + "甲乙丙丁戊己"
    assert _find_best_pair(text) == (6, 6, 0, 7)


def test_find_repetition_returns_intervals_with_sources():
    r = find_repetition(REPEAT_SEGMENTS)
    assert r["text"] == REPEAT_TEXT
    rep = r["repeat"]
    assert rep["length"] == 6
    assert rep["same_known"] == 6
    assert (rep["first"]["start"], rep["first"]["end"]) == (0, 6)
    assert (rep["second"]["start"], rep["second"]["end"]) == (8, 14)
    assert rep["first"]["fragment"] == "甲乙丙丁戊己"
    assert rep["second"]["fragment"] == "甲乙丙丁戊己"
    # 逐字 sources 与 /api/assemble 对应区间一致
    full = assemble(REPEAT_SEGMENTS)
    assert rep["first"]["sources"] == full["sources"][0:6]
    assert rep["second"]["sources"] == full["sources"][8:14]


def test_find_repetition_wildcard_positions():
    r = find_repetition(["甲乙?丁戊己", "丁戊己庚辛甲乙", "辛甲乙丙丁戊己"])
    assert r["text"] == "甲乙?丁戊己庚辛甲乙丙丁戊己"
    rep = r["repeat"]
    assert (rep["length"], rep["same_known"]) == (6, 5)
    assert (rep["first"]["start"], rep["first"]["end"]) == (0, 6)
    assert (rep["second"]["start"], rep["second"]["end"]) == (8, 14)
    assert rep["first"]["fragment"] == "甲乙?丁戊己"
    assert rep["second"]["fragment"] == "甲乙丙丁戊己"


def test_find_repetition_none_when_no_qualified_pair():
    r = find_repetition(["学而?习之", "时习之不", "之不亦乐乎"])
    assert r["text"] == "学而时习之不亦乐乎"
    assert r["repeat"] is None


def test_find_repetition_gate_failure_propagates():
    with pytest.raises(AssemblyError) as exc:
        find_repetition(["孔子曰未知", "未知生焉", "完全无关文本"])
    assert exc.value.failed_segment == 2
