"""프리플랍 기본 레인지 — 앱 STRATEGY 탭과 동일 데이터.

원본: holdemlog 앱 lib/features/strategy/data/preflop_ranges.dart
(8맥스 100bb GTO 근사 + 40/25bb 변형, 버튼 거리 기반 포지션 매핑).
앱 데이터가 바뀌면 이 파일도 함께 갱신한다.

MVP 레인지 배정 규칙 (solver-worker-plan §2):
- 오프너(첫 레이저): 자기 포지션 오픈 레인지
- 3벳터: 3벳 테이블 레인지
- 콜러: 자기 포지션 오픈 레인지를 대용 (콜링 레인지 차트가 없어 근사)
- BB(오픈 차트 없음)는 BTN 오픈 레인지를 수비 대용으로 사용
히어로 실제 콤보의 라벨이 레인지에 없으면 가중치 1.0으로 추가한다
(빈도 조회가 가능해야 하므로 — 왜곡은 라벨 1개 수준).
"""

from __future__ import annotations

RANK_ORDER = "AKQJT98765432"  # 그리드 순서 (A=0)

OPEN_100 = {
    "utg": "66+, A9s+, A5s, A4s, KTs+, QTs+, JTs, T9s, 98s, AJo+, KQo",
    "utg1": "55+, A8s+, A5s, A4s, K9s+, QTs+, JTs, T9s, 98s, 87s, ATo+, KQo",
    "mp": "44+, A7s+, A5s, A4s, A3s, A2s, K9s+, Q9s+, J9s+, T9s, 98s, 87s, 76s, ATo+, KJo+, QJo",
    "hj": "33+, A2s+, K9s+, Q9s+, J9s+, T8s+, 97s+, 87s, 76s, 65s, ATo+, KJo+, QJo, JTo",
    "co": "22+, A2s+, K7s+, Q8s+, J8s+, T8s+, 97s+, 86s+, 76s, 65s, 54s, A9o+, KTo+, QTo+, JTo",
    "btn": "22+, A2s+, K2s+, Q4s+, J6s+, T6s+, 96s+, 85s+, 75s+, 64s+, 54s, 43s, A2o+, K8o+, Q9o+, J9o+, T9o, 98o",
    "sb": "22+, A2s+, K4s+, Q6s+, J7s+, T7s+, 96s+, 86s+, 75s+, 65s, 54s, A4o+, K9o+, Q9o+, J9o+, T9o",
}

OPEN_40 = {
    "utg": "66+, A9s+, A5s, KTs+, QTs+, JTs, T9s, AJo+, KQo",
    "utg1": "55+, A8s+, A5s, A4s, KTs+, QTs+, JTs, T9s, 98s, ATo+, KQo",
    "mp": "44+, A7s+, A5s, A4s, A3s, K9s+, Q9s+, J9s+, T9s, 98s, 87s, ATo+, KJo+, QJo",
    "hj": "33+, A2s+, K9s+, Q9s+, J9s+, T8s+, 98s, 87s, 76s, ATo+, KJo+, QJo, JTo",
    "co": "22+, A2s+, K8s+, Q9s+, J8s+, T8s+, 97s+, 87s, 76s, 65s, A8o+, KTo+, QTo+, JTo",
    "btn": "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 86s+, 75s+, 65s, 54s, A2o+, K9o+, Q9o+, J9o+, T9o",
    "sb": "22+, A2s+, K5s+, Q7s+, J8s+, T7s+, 97s+, 86s+, 76s, 65s, A5o+, K9o+, QTo+, JTo",
}

OPEN_25 = {
    "utg": "66+, ATs+, A5s, KTs+, QJs, JTs, AJo+, KQo",
    "utg1": "66+, A9s+, A5s, KTs+, QTs+, JTs, ATo+, KQo",
    "mp": "55+, A8s+, A5s, A4s, K9s+, QTs+, JTs, T9s, ATo+, KJo+",
    "hj": "44+, A7s+, A5s, A4s, K9s+, Q9s+, JTs, T9s, 98s, ATo+, KJo+, QJo",
    "co": "33+, A2s+, K8s+, Q9s+, J9s+, T8s+, 98s, 87s, A9o+, KTo+, QTo+, JTo",
    "btn": "22+, A2s+, K4s+, Q6s+, J7s+, T7s+, 96s+, 86s+, 75s+, 65s, 54s, A3o+, K9o+, Q9o+, J9o+, T9o",
    "sb": "22+, A2s+, K6s+, Q8s+, J8s+, T8s+, 97s+, 87s, 76s, A7o+, KTo+, QTo+, JTo",
}

OPEN_BY_STACK = {100: OPEN_100, 40: OPEN_40, 25: OPEN_25}

THREEBET_100 = {
    "EP-ip": "QQ+, JJ:0.5, TT:0.25, AKs, AQs:0.75, AJs:0.25, A5s:0.5, A4s:0.5, KQs:0.25, AKo, AQo:0.25, 76s:0.25, 65s:0.25",
    "EP-sb": "QQ+, JJ:0.75, TT:0.25, AKs, AQs, AJs:0.5, A5s:0.75, A4s:0.5, KQs:0.5, KJs:0.25, AKo, AQo:0.5, 76s:0.25, 65s:0.25",
    "EP-bb": "JJ+, TT:0.5, 99:0.25, AKs, AQs, AJs:0.5, ATs:0.25, A5s, A4s:0.75, A3s:0.5, KQs:0.5, KJs:0.25, JTs:0.25, T9s:0.25, 98s:0.25, AKo, AQo:0.5, 87s:0.25, 76s:0.25",
    "HJ-ip": "TT+, 99:0.5, 88:0.25, AJs+, ATs:0.5, A5s, A4s:0.75, A3s:0.5, KQs:0.75, KJs:0.5, KTs:0.25, QJs:0.25, JTs:0.25, AQo+, AJo:0.25, KQo:0.25, 76s:0.25, 65s:0.25",
    "HJ-sb": "TT+, 99:0.5, AJs+, ATs:0.5, A5s, A4s, KQs:0.75, KJs:0.5, QJs:0.25, JTs:0.25, T9s:0.25, AQo+, AJo:0.25, KQo:0.5",
    "HJ-bb": "99+, 88:0.5, 77:0.25, ATs+, A9s:0.5, A5s, A4s, A3s:0.5, A2s:0.25, KJs+, KTs:0.5, QJs:0.5, QTs:0.25, JTs:0.5, T9s:0.5, 98s:0.25, 87s:0.25, 76s:0.25, 65s:0.25, AJo+, ATo:0.25, KQo:0.75, KJo:0.25",
    "CO-ip": "99+, 88:0.5, 77:0.25, ATs+, A9s:0.5, A8s:0.25, A5s, A4s, A3s:0.5, KJs+, KTs:0.5, QJs:0.5, QTs:0.25, JTs:0.5, T9s:0.25, AJo+, ATo:0.25, KQo:0.5, 65s:0.25, 54s:0.25",
    "CO-sb": "99+, 88:0.5, ATs+, A9s:0.5, A5s, A4s, A3s:0.5, KJs+, KTs:0.5, QJs:0.5, JTs:0.5, T9s:0.25, AJo+, ATo:0.25, KQo:0.75, 76s:0.25, 65s:0.25",
    "CO-bb": "88+, 77:0.5, 66:0.25, A9s+, A8s:0.5, A5s, A4s, A3s:0.75, A2s:0.5, KTs+, K9s:0.5, QTs+, Q9s:0.25, JTs, J9s:0.5, T9s:0.75, T8s:0.25, 98s:0.5, 87s:0.5, 76s:0.5, 65s:0.5, 54s:0.25, ATo+, A9o:0.25, KJo+, KTo:0.25, QJo:0.5, JTo:0.25",
    "BTN-sb": "88+, 77:0.75, 66:0.5, 55:0.25, A9s+, A8s:0.5, A5s, A4s, A3s:0.75, A2s:0.5, KTs+, K9s:0.5, QTs+, JTs, T9s:0.75, 98s:0.5, 87s:0.5, 76s:0.5, 65s:0.25, ATo+, A9o:0.5, KJo+, KTo:0.5, QJo:0.75, JTo:0.25",
    "BTN-bb": "77+, 66:0.75, 55:0.5, 44:0.25, A8s+, A7s:0.5, A6s:0.5, A5s, A4s, A3s:0.75, A2s:0.75, K9s+, K8s:0.5, Q9s+, Q8s:0.25, J9s+, T8s+, 97s:0.5, 98s:0.75, 87s:0.75, 76s:0.75, 65s:0.5, 54s:0.5, ATo+, A9o:0.5, A8o:0.25, KTo+, K9o:0.25, QTo+:0.75, JTo:0.5, T9o:0.25",
    "SB-bb": "66+, 55:0.75, 44:0.5, 33:0.25, 22:0.25, A2s+, K9s+, K8s:0.5, Q9s+, J9s+, T8s+, 97s:0.5, 87s:0.75, 76s:0.75, 65s:0.5, 54s:0.5, A9o+, A8o:0.5, A5o:0.25, KTo+, K9o:0.5, QTo+, JTo:0.5",
}

THREEBET_40 = {
    "EP-ip": "QQ+, JJ:0.75, TT:0.25, AKs, AQs:0.5, A5s:0.25, AKo, AQo:0.25",
    "EP-sb": "QQ+, JJ:0.75, TT:0.5, AKs, AQs:0.75, A5s:0.5, AKo, AQo:0.5",
    "EP-bb": "JJ+, TT:0.5, AKs, AQs, AJs:0.25, A5s:0.75, A4s:0.5, KQs:0.25, AKo, AQo:0.5",
    "HJ-ip": "TT+, 99:0.5, AJs+, ATs:0.25, A5s:0.75, A4s:0.5, KQs:0.5, AQo+, AJo:0.25",
    "HJ-sb": "TT+, 99:0.5, AJs+, A5s, A4s:0.5, KQs:0.5, AQo+, KQo:0.25",
    "HJ-bb": "99+, 88:0.5, ATs+, A9s:0.25, A5s, A4s:0.75, KJs+, QJs:0.5, JTs:0.25, AJo+, KQo:0.5",
    "CO-ip": "99+, 88:0.5, ATs+, A9s:0.25, A5s, A4s:0.75, KJs+, KTs:0.25, QJs:0.5, JTs:0.25, AJo+, KQo:0.5, ATo:0.25",
    "CO-sb": "99+, 88:0.5, ATs+, A5s, A4s:0.75, KJs+, QJs:0.5, JTs:0.25, AJo+, KQo:0.75",
    "CO-bb": "88+, 77:0.5, A9s+, A8s:0.25, A5s, A4s, A3s:0.5, KTs+, QTs+, JTs:0.75, T9s:0.5, 98s:0.25, ATo+, KJo+, QJo:0.25",
    "BTN-sb": "88+, 77:0.5, 66:0.25, A9s+, A5s, A4s, A3s:0.5, KTs+, K9s:0.25, QTs+, JTs, T9s:0.5, 98s:0.25, ATo+, A9o:0.25, KJo+, KTo:0.25, QJo:0.5",
    "BTN-bb": "77+, 66:0.5, 55:0.25, A8s+, A7s:0.25, A5s, A4s, A3s:0.5, A2s:0.5, K9s+, Q9s+, J9s+, T8s+, 98s:0.5, 87s:0.5, 76s:0.5, ATo+, A9o:0.25, KTo+, QTo+:0.5, JTo:0.25",
    "SB-bb": "66+, 55:0.5, 44:0.25, A2s+, K9s+, Q9s+, J9s+, T8s+, 98s:0.5, 87s:0.5, 76s:0.5, 65s:0.25, A9o+, A8o:0.25, KTo+, K9o:0.25, QTo+, JTo:0.5",
}

THREEBET_25 = {
    "EP-ip": "QQ+, JJ:0.75, AKs, AQs:0.25, AKo",
    "EP-sb": "QQ+, JJ, TT:0.5, AKs, AQs:0.5, AKo, AQo:0.25",
    "EP-bb": "JJ+, TT:0.75, 99:0.25, AKs, AQs, A5s:0.5, AKo, AQo:0.5",
    "HJ-ip": "TT+, 99:0.5, AQs+, AJs:0.5, A5s:0.5, AQo+, AJo:0.25",
    "HJ-sb": "TT+, 99:0.75, AJs+, A5s:0.5, KQs:0.25, AQo+",
    "HJ-bb": "99+, 88:0.5, ATs+, A5s:0.75, A4s:0.5, KQs:0.5, KJs:0.25, AJo+, KQo:0.25",
    "CO-ip": "99+, 88:0.5, ATs+, A5s:0.75, A4s:0.5, KQs:0.75, KJs:0.25, AJo+, KQo:0.25, ATo:0.25",
    "CO-sb": "99+, 88:0.5, 77:0.25, ATs+, A5s:0.75, A4s:0.5, KJs+, AJo+, KQo:0.5",
    "CO-bb": "88+, 77:0.5, 66:0.25, ATs+, A9s:0.5, A5s, A4s:0.75, KTs+, QJs:0.5, JTs:0.25, ATo+, KQo:0.75, KJo:0.25",
    "BTN-sb": "77+, 66:0.5, 55:0.25, A9s+, A8s:0.25, A5s, A4s:0.75, KTs+, K9s:0.25, QTs+, JTs:0.5, ATo+, A9o:0.25, KJo+, QJo:0.25",
    "BTN-bb": "66+, 55:0.5, 44:0.25, A8s+, A7s:0.5, A5s, A4s, A3s:0.5, A2s:0.25, K9s+, QTs+, Q9s:0.5, J9s+, T9s:0.75, 98s:0.5, 87s:0.25, ATo+, A9o:0.5, KTo+, K9o:0.25, QTo+, JTo:0.5",
    "SB-bb": "55+, 44:0.5, 33:0.25, A2s+, K9s+, K8s:0.25, Q9s+, J9s+, T8s+, 98s:0.5, 87s:0.5, 76s:0.25, A8o+, A7o:0.25, KTo+, K9o:0.5, QTo+, JTo:0.75",
}

THREEBET_BY_STACK = {100: THREEBET_100, 40: THREEBET_40, 25: THREEBET_25}

# 버튼 기준 거리 → 8맥스 베이스 포지션 (preflop_ranges.dart _byBtnDistance)
_BY_BTN_DISTANCE = ["btn", "co", "hj", "mp", "utg1", "utg"]

from holdem import POSITIONS_BY_SIZE  # noqa: E402 — 순환 없음


def base_equivalent(table_size: int, pos: str) -> str:
    if pos in ("sb", "bb"):
        return pos
    non_blind = [p for p in POSITIONS_BY_SIZE[table_size] if p not in ("sb", "bb")]
    dist = len(non_blind) - 1 - non_blind.index(pos)
    return _BY_BTN_DISTANCE[min(dist, len(_BY_BTN_DISTANCE) - 1)]


def nearest_stack_depth(stack_bb: float | None) -> int:
    """앱 solver_review.dart nearestStackDepth와 동일 매핑."""
    if stack_bb is None:
        return 100
    if stack_bb >= 70:
        return 100
    if stack_bb >= 32.5:
        return 40
    return 25


def parse_range(range_str: str) -> dict[str, float]:
    """'66+, A9s+:0.5, KQo' → {라벨: 가중치}. preflop_range.dart와 동일 문법."""
    weights: dict[str, float] = {}
    for raw in range_str.split(","):
        token = raw.strip()
        if not token:
            continue
        spec, _, w = token.partition(":")
        spec = spec.strip()
        weight = float(w) if w else 1.0
        if not (0 < weight <= 1):
            raise ValueError(f"잘못된 빈도: {token}")
        plus = spec.endswith("+")
        body = spec[:-1] if plus else spec

        if len(body) == 2 and body[0] == body[1]:  # 페어
            idx = RANK_ORDER.index(body[0])
            end = 0 if plus else idx
            for i in range(idx, end - 1, -1):
                weights[RANK_ORDER[i] * 2] = weight
        elif len(body) == 3 and body[2] in "so":
            hi, lo = RANK_ORDER.index(body[0]), RANK_ORDER.index(body[1])
            if hi > lo:
                hi, lo = lo, hi
            end = hi + 1 if plus else lo
            for k in range(lo, end - 1, -1):
                weights[f"{RANK_ORDER[hi]}{RANK_ORDER[k]}{body[2]}"] = weight
        else:
            raise ValueError(f"잘못된 레인지 토큰: {token}")
    return weights


def open_range_for(table_size: int, pos: str, stack_bb: int) -> dict[str, float]:
    table = OPEN_BY_STACK.get(stack_bb, OPEN_100)
    base = base_equivalent(table_size, pos)
    if base == "bb":  # BB는 오픈 차트가 없다 — BTN 레인지를 수비 대용
        base = "btn"
    return parse_range(table[base])


def three_bet_range_for(
    table_size: int, hero: str, opener: str, stack_bb: int
) -> dict[str, float]:
    base_opener = base_equivalent(table_size, opener)
    bucket = {
        "utg": "EP", "utg1": "EP", "mp": "EP", "hj": "HJ", "co": "CO", "btn": "BTN",
    }.get(base_opener, "SB")
    hero_type = "sb" if hero == "sb" else "bb" if hero == "bb" else "ip"
    tables = THREEBET_BY_STACK.get(stack_bb, THREEBET_100)
    return parse_range(
        tables.get(f"{bucket}-{hero_type}")
        or tables.get(f"{bucket}-bb")
        or tables["EP-bb"]
    )


def hand_label(c1: str, c2: str) -> str:
    """'As','Js' → 'AJs' (169 라벨, solver_review.dart heroHandLabel과 동일)."""
    i1, i2 = RANK_ORDER.index(c1[0]), RANK_ORDER.index(c2[0])
    if i1 == i2:
        return c1[0] * 2
    hi, lo = (i1, i2) if i1 < i2 else (i2, i1)
    suffix = "s" if c1[1] == c2[1] else "o"
    return f"{RANK_ORDER[hi]}{RANK_ORDER[lo]}{suffix}"


def to_solver_range(weights: dict[str, float]) -> str:
    """{라벨: 가중치} → TexasSolver 레인지 문자열 ('AA,KK:0.75,...')."""
    parts = []
    for label, w in weights.items():
        parts.append(label if w >= 0.999 else f"{label}:{round(w, 4)}")
    return ",".join(parts)
