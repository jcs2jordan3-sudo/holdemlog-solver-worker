"""홀덤 기본 도구 — 카드, 포지션, 베팅 리플레이(팟/유효스택), 7장 핸드 평가.

앱(lib/domain/hand/*)과 규칙을 1:1로 맞춘다:
- 금액은 BB 단위, raise는 Raise-To(해당 스트리트 총액)
- 앤티는 BB 앤티 관례로 팟에 1회 반영 (betting_engine.dart §32)
- 액션 없는 SB/BB는 블라인드만 데드로 남는다
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

RANKS = "23456789TJQKA"  # 값 오름차순 (2=0 … A=12)
SUITS = "cdhs"

STREETS = ["preflop", "flop", "turn", "river"]

# 프리플랍 액션 순서 (테이블 인원수별) — position.dart와 동일
POSITIONS_BY_SIZE = {
    2: ["sb", "bb"],
    3: ["btn", "sb", "bb"],
    4: ["co", "btn", "sb", "bb"],
    5: ["hj", "co", "btn", "sb", "bb"],
    6: ["utg", "hj", "co", "btn", "sb", "bb"],
    7: ["utg", "mp", "hj", "co", "btn", "sb", "bb"],
    8: ["utg", "utg1", "mp", "hj", "co", "btn", "sb", "bb"],
    9: ["utg", "utg1", "mp", "lj", "hj", "co", "btn", "sb", "bb"],
}


def postflop_order(table_size: int) -> list[str]:
    """포스트플랍 액션 순서 — SB부터 시계방향, BTN이 마지막."""
    pre = POSITIONS_BY_SIZE[table_size]
    blinds = [p for p in pre if p in ("sb", "bb")]
    rest = [p for p in pre if p not in ("sb", "bb")]
    return blinds + rest


def card_index(code: str) -> int:
    """'As' → 0~51 정수. 잘못된 코드는 ValueError."""
    if len(code) != 2 or code[0] not in RANKS or code[1] not in SUITS:
        raise ValueError(f"잘못된 카드 코드: {code}")
    return RANKS.index(code[0]) * 4 + SUITS.index(code[1])


def parse_cards(codes: str) -> list[str]:
    """'AsJs' / 'Jh8s4c' → ['As','Js'] — 앱 cardsToCode 역변환."""
    if len(codes) % 2 != 0:
        raise ValueError(f"잘못된 카드 문자열: {codes}")
    cards = [codes[i : i + 2] for i in range(0, len(codes), 2)]
    for c in cards:
        card_index(c)  # 검증
    return cards


def combo_key(c1: str, c2: str) -> str:
    """TexasSolver 덤프의 콤보 키 — 높은 랭크 먼저 (예: 'AsJs', 'Tc9c')."""
    if RANKS.index(c1[0]) < RANKS.index(c2[0]):
        c1, c2 = c2, c1
    return c1 + c2


def combo_key_variants(c1: str, c2: str) -> list[str]:
    """페어는 수트 순서가 덤프 구현에 따라 다를 수 있어 양쪽을 시도한다."""
    return [c1 + c2, c2 + c1]


# ── 베팅 리플레이 ────────────────────────────────────────────────


@dataclass
class StreetState:
    """스트리트 진입 시점 상태 (BB 단위)."""

    pot: float  # 스트리트 시작 팟 (양측 매치 완료분 + 데드)
    effective_left: float  # 남은 유효스택 (양 플레이어 중 작은 쪽)


def street_contributions(
    actions: list[dict], street: str, sb_bb: float
) -> dict[str, float]:
    """해당 스트리트의 포지션별 최종 투입액.

    bet/raise/all_in의 amount_bb는 Raise-To(스트리트 총액), call은 현재
    최고액 매치. 프리플랍은 SB/BB 포스트가 기본 투입액이다.
    """
    contrib: dict[str, float] = {}
    if street == "preflop":
        contrib = {"sb": sb_bb, "bb": 1.0}
    highest = max(contrib.values(), default=0.0)
    for a in actions:
        if a["street"] != street:
            continue
        pos, act = a["position"], a["action"]
        amt = a.get("amount_bb")
        prev = contrib.get(pos, 0.0)
        if act in ("bet", "raise", "all_in"):
            if amt is not None:
                contrib[pos] = max(prev, float(amt))
                highest = max(highest, contrib[pos])
        elif act == "call":
            # 금액이 기록돼 있으면 그대로(앱이 매치액을 기록), 없으면 최고액 매치
            contrib[pos] = max(prev, float(amt) if amt is not None else highest)
            highest = max(highest, contrib[pos])
        # fold/check는 투입 없음 (이미 넣은 것은 데드로 남는다)
    return contrib


def state_entering(
    hand: dict, street: str, hero: str, villain: str
) -> StreetState:
    """[street] 진입 시점의 팟과 남은 유효스택.

    팟 = 앤티(1회) + 이전 스트리트 투입 총합.
    유효스택 = effective_stack_bb − 히어로/빌런 각자 투입액 중 큰 쪽 차감.
    """
    bb_chips = float(hand["bb"])
    ante_bb = float(hand.get("ante") or 0) / bb_chips
    sb_bb = float(hand["sb"]) / bb_chips
    actions = hand["actions"]

    pot = ante_bb if ante_bb > 0 else 0.0
    spent = {hero: 0.0, villain: 0.0}
    for s in STREETS:
        if s == street:
            break
        contrib = street_contributions(actions, s, sb_bb)
        pot += sum(contrib.values())
        for p in (hero, villain):
            spent[p] += contrib.get(p, 0.0)

    eff0 = float(hand.get("effective_stack_bb") or hand.get("hero_stack_bb") or 100)
    left = eff0 - max(spent[hero], spent[villain])
    return StreetState(pot=round(pot, 2), effective_left=round(max(left, 0.0), 2))


# ── 7장 핸드 평가 ────────────────────────────────────────────────
#
# 반환값은 클수록 강한 정수. (카테고리, 타이브레이커) 튜플을 정수로 인코딩.
# 카테고리: 8=스트레이트플러시 7=포카드 6=풀하우스 5=플러시 4=스트레이트
#           3=트립스 2=투페어 1=원페어 0=하이카드


def _rank5(cards: list[str]) -> int:
    ranks = sorted((RANKS.index(c[0]) for c in cards), reverse=True)
    suits = {c[1] for c in cards}
    flush = len(suits) == 1

    # 스트레이트 (휠 A2345 포함)
    uniq = sorted(set(ranks), reverse=True)
    straight_high = -1
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_high = uniq[0]
        elif uniq == [12, 3, 2, 1, 0]:  # A5432
            straight_high = 3

    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    # (개수, 랭크) 내림차순 — 타이브레이커 순서
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = sorted(counts.values(), reverse=True)

    if flush and straight_high >= 0:
        cat, tie = 8, [straight_high]
    elif shape == [4, 1]:
        cat, tie = 7, [groups[0][0], groups[1][0]]
    elif shape == [3, 2]:
        cat, tie = 6, [groups[0][0], groups[1][0]]
    elif flush:
        cat, tie = 5, ranks
    elif straight_high >= 0:
        cat, tie = 4, [straight_high]
    elif shape == [3, 1, 1]:
        cat, tie = 3, [groups[0][0], groups[1][0], groups[2][0]]
    elif shape == [2, 2, 1]:
        cat, tie = 2, [groups[0][0], groups[1][0], groups[2][0]]
    elif shape == [2, 1, 1, 1]:
        cat, tie = 1, [groups[0][0]] + [g[0] for g in groups[1:]]
    else:
        cat, tie = 0, ranks
    value = cat
    for t in (tie + [0] * 5)[:5]:
        value = value * 16 + t
    return value


def rank7(cards: list[str]) -> int:
    """7장(홀 2 + 보드 5) 중 최선 5장 랭크."""
    return max(_rank5(list(five)) for five in combinations(cards, 5))
