"""重复抄写发现：在同一拼接稿中查找可能的重复抄写区间对。

复用 :func:`app.assembler.assemble` 的拼接文本与逐字来源（沿用段数/长度限制
与续接失败规则），在拼接文本中寻找两个**互不重叠**的等长连续区间：

- 逐位置**兼容**：对应字相同，或任一字为 ``?``（未辨认字）；
- 区间长度至少 :data:`MIN_REPEAT_LEN`（6）；
- 至少 :data:`MIN_SAME_KNOWN`（4）个位置是两侧相同的**已知字**（非 ``?``）。

候选区间对按（长度降序、已知相同位降序、两起点升序）取最优：先选长度最长
的区间对；同长度时选已知相同位更多者；仍并列时按两起点升序取首对。
无合格重复时 ``repeat`` 为 ``None``。

本模块只做发现与报告，绝不改写拼接文本。
"""

from __future__ import annotations

from .aligner import WILDCARD
from .assembler import assemble

MIN_REPEAT_LEN = 6   # 重复区间最小长度
MIN_SAME_KNOWN = 4   # 至少需要的两侧相同已知字位置数


def _compatible(a: str, b: str) -> bool:
    """两字兼容：相同，或任一字为 ``?``。"""
    return a == b or a == WILDCARD or b == WILDCARD


def _find_best_pair(text: str) -> tuple[int, int, int, int] | None:
    """在文本中找最优合格重复区间对。

    返回 ``(length, same_known, s1, s2)``：区间 ``[s1, s1+length)`` 与
    ``[s2, s2+length)``（``s1 < s2``，互不重叠即 ``length <= s2 - s1``），
    ``same_known`` 为两侧相同已知字的位置数；无合格区间对返回 ``None``。

    按起点间距 ``d = s2 - s1`` 逐条对角线扫描：同一 ``d`` 上兼容位置的最长
    连续段内，每个起点 ``s1`` 可取的最长窗口为 ``min(d, 段剩余长度)``（以
    ``d`` 截断保证两区间不重叠）。已知相同位数随窗口加长单调不减，故每个
    起点对只需考察其最长窗口：最长窗口不满足已知相同位下限时，更短窗口
    同样不满足。整体 O(n²)。
    """
    n = len(text)
    best: tuple[int, int, int, int] | None = None
    for d in range(1, n):
        span = n - d  # 本对角线上可比较的位置数：text[i] 对 text[i + d]
        if span < MIN_REPEAT_LEN:
            break  # 对角线剩余位置不足最小长度，更大的 d 亦然
        compat = [False] * span
        known = [0] * span
        for i in range(span):
            a, b = text[i], text[i + d]
            if _compatible(a, b):
                compat[i] = True
                if a != WILDCARD and a == b:
                    known[i] = 1
        # 已知相同位前缀和，供任意窗口 O(1) 查询
        pref = [0] * (span + 1)
        for i in range(span):
            pref[i + 1] = pref[i] + known[i]

        i = 0
        while i < span:
            if not compat[i]:
                i += 1
                continue
            run_end = i
            while run_end < span and compat[run_end]:
                run_end += 1
            # 兼容段 [i, run_end)：逐起点考察其最长窗口（不超过 d 保证不重叠）
            for s1 in range(i, run_end):
                length = min(d, run_end - s1)
                if length < MIN_REPEAT_LEN:
                    continue
                same_known = pref[s1 + length] - pref[s1]
                if same_known < MIN_SAME_KNOWN:
                    continue
                cand = (length, same_known, s1, s1 + d)
                if best is None or (
                    (cand[0], cand[1], -cand[2], -cand[3])
                    > (best[0], best[1], -best[2], -best[3])
                ):
                    best = cand
            i = run_end
    return best


def find_repetition(segments: list[str]) -> dict:
    """在 2～5 段转写的拼接文本中查找最优合格重复区间对。

    返回 ``{"text", "repeat"}``：``repeat`` 为 ``None``（无合格重复）或
    ``{"length", "same_known", "first", "second"}``，其中 ``first`` /
    ``second`` 各带左闭右开区间、原文片段与该区间逐字来源。拼接阶段失败
    原样抛出 :class:`~app.assembler.AssemblyError`。
    """
    result = assemble(segments)
    text, sources = result["text"], result["sources"]

    best = _find_best_pair(text)
    if best is None:
        return {"text": text, "repeat": None}

    length, same_known, s1, s2 = best

    def make_interval(start: int) -> dict:
        return {
            "start": start,
            "end": start + length,
            "fragment": text[start:start + length],
            "sources": [list(src) for src in sources[start:start + length]],
        }

    return {
        "text": text,
        "repeat": {
            "length": length,
            "same_known": same_known,
            "first": make_interval(s1),
            "second": make_interval(s2),
        },
    }
