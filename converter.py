"""핸드 JSON → TexasSolver 콘솔 입력 (스트리트별 솔브 스펙).

실측 확정 사항 (2026-08-23, v0.2.0 릴리즈 바이너리):
- 입력은 명령 텍스트 파일 (set_pot / set_effective_stack / set_board /
  set_range_ip / set_range_oop / set_bet_sizes / build_tree / start_solve /
  set_dump_rounds / dump_result)
- 보드는 'Qs,Jh,2h' 콤마 구분, 레인지는 'AA,KK:0.75' 가중 라벨
- 덤프 트리 액션 라벨은 'CHECK' 'CALL' 'FOLD' 'BET x' 'RAISE x'(Raise-To,
  입력 단위 그대로) — 올인은 별도 라벨 없이 금액이 스택에 도달한 BET/RAISE
- 금액 단위는 입력 단위를 따른다 → 우리는 전부 BB 단위로 넣는다
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import ranges as rg
from holdem import (
    STREETS,
    StreetState,
    parse_cards,
    postflop_order,
    state_entering,
)

# 트리 단순화 설정 (solver-worker-plan §2 — 벳 2개 + 레이즈 1개 + 올인)
BET_SIZES = [33, 75]
RAISE_SIZES = [60]
DONK_SIZES = [33]
# 올인 임계 — 실측 판정식: "추가 금액 + 현재 커밋(팟 절반 포함) > 유효스택 × 임계".
# 0.67이면 리버 75% 벳까지 올인으로 흡수되고(사상 정확도 훼손), 1.0을 플랍
# 솔브에 쓰면 트리가 13GB+로 폭증한다(실측). 절충: 각 솔브의 루트 스트리트
# 사상 정확도는 지키고 깊은 층만 단순화하는 스트리트별 사다리.
ALLIN_THRESHOLD_BY_STREET = {"flop": 0.67, "turn": 0.85, "river": 1.0}

ACCURACY = float(os.environ.get("SOLVER_ACCURACY", "0.5"))
MAX_ITERATION = int(os.environ.get("SOLVER_MAX_ITERATION", "150"))
THREAD_NUM = int(os.environ.get("SOLVER_THREADS", "4"))


class UnsupportedHand(Exception):
    """MVP 범위 밖 핸드 — 잡을 failed 처리하고 사유를 남긴다."""


@dataclass
class StreetSpec:
    """한 스트리트 솔브의 입력 + 추출 컨텍스트."""

    street: str
    board: list[str]  # 이 스트리트까지의 보드
    pot: float
    effective: float
    hero_is_ip: bool
    hero_range: dict[str, float]
    villain_range: dict[str, float]
    street_actions: list[dict]  # 이 스트리트의 실제 액션 (순서대로)
    input_text: str = field(default="", repr=False)


def _postflop_players(hand: dict) -> list[str]:
    seen: list[str] = []
    for a in hand["actions"]:
        if a["street"] != "preflop" and a["position"] not in seen:
            seen.append(a["position"])
    return seen


def _preflop_line(hand: dict) -> tuple[str | None, list[str]]:
    """(첫 레이저 포지션, 레이즈 순서 포지션 목록). BB 포스트(1BB) 초과 기준."""
    raisers: list[str] = []
    for a in hand["actions"]:
        if a["street"] != "preflop":
            continue
        if a["action"] in ("bet", "raise", "all_in") and (a.get("amount_bb") or 0) > 1:
            raisers.append(a["position"])
    return (raisers[0] if raisers else None, raisers)


def assign_ranges(
    hand: dict, hero: str, villain: str, depth: int
) -> tuple[dict[str, float], dict[str, float]]:
    """MVP 레인지 배정 (ranges.py 모듈 docstring의 규칙)."""
    table = hand["table_size"]
    opener, raisers = _preflop_line(hand)

    def range_of(pos: str, other: str) -> dict[str, float]:
        if opener is not None and pos in raisers and pos != opener:
            return rg.three_bet_range_for(table, hero=pos, opener=opener, stack_bb=depth)
        return rg.open_range_for(table, pos, depth)

    hero_range = dict(range_of(hero, villain))
    villain_range = dict(range_of(villain, hero))

    # 히어로 실제 콤보가 레인지에 없으면 라벨을 추가해 빈도 조회를 보장
    hero_cards = parse_cards(hand["hero_cards"])
    label = rg.hand_label(*hero_cards)
    hero_range.setdefault(label, 1.0)
    return hero_range, villain_range


def build_street_specs(hand: dict) -> tuple[list[StreetSpec], dict]:
    """핸드에서 (히어로가 액션한 스트리트별 솔브 스펙, 컨텍스트)를 만든다.

    MVP 제약: 포스트플랍 헤즈업만. 멀티웨이·보드 미완성은 UnsupportedHand.
    """
    hero = hand["hero_position"]
    players = _postflop_players(hand)
    if len(players) < 2:
        raise UnsupportedHand("포스트플랍 액션이 2인 미만입니다 — 리뷰할 스팟이 없습니다")
    if len(players) > 2:
        raise UnsupportedHand("멀티웨이 팟은 아직 지원하지 않습니다 (헤즈업만)")
    if hero not in players:
        raise UnsupportedHand("히어로가 포스트플랍에 참여하지 않았습니다")
    villain = players[0] if players[1] == hero else players[1]

    order = postflop_order(hand["table_size"])
    hero_is_ip = order.index(hero) > order.index(villain)

    depth = rg.nearest_stack_depth(
        hand.get("hero_stack_bb") or hand.get("effective_stack_bb")
    )
    hero_range, villain_range = assign_ranges(hand, hero, villain, depth)

    flop = parse_cards(hand["board_flop"]) if hand.get("board_flop") else None
    turn = hand.get("board_turn")
    river = hand.get("board_river")

    specs: list[StreetSpec] = []
    for street in ("flop", "turn", "river"):
        street_actions = [a for a in hand["actions"] if a["street"] == street]
        if not any(a["position"] == hero for a in street_actions):
            continue
        if flop is None or len(flop) != 3:
            raise UnsupportedHand("플랍 카드 3장이 필요합니다")
        board = list(flop)
        if street in ("turn", "river"):
            if not turn:
                raise UnsupportedHand("턴 카드가 필요합니다")
            board.append(turn)
        if street == "river":
            if not river:
                raise UnsupportedHand("리버 카드가 필요합니다")
            board.append(river)

        st: StreetState = state_entering(hand, street, hero, villain)
        if st.effective_left <= 0:
            continue  # 이미 올인 — 결정 없음
        spec = StreetSpec(
            street=street,
            board=board,
            pot=st.pot,
            effective=st.effective_left,
            hero_is_ip=hero_is_ip,
            hero_range=hero_range,
            villain_range=villain_range,
            street_actions=street_actions,
        )
        spec.input_text = render_input(spec)
        specs.append(spec)

    if not specs:
        raise UnsupportedHand("솔빙 가능한 포스트플랍 스팟이 없습니다")
    return specs, {"hero": hero, "villain": villain, "hero_is_ip": hero_is_ip, "depth": depth}


def render_input(spec: StreetSpec, output_file: str = "result.json") -> str:
    """스트리트 솔브 스펙 → 콘솔 입력 텍스트."""
    ip_range = spec.hero_range if spec.hero_is_ip else spec.villain_range
    oop_range = spec.villain_range if spec.hero_is_ip else spec.hero_range

    lines = [
        f"set_pot {spec.pot}",
        f"set_effective_stack {spec.effective}",
        f"set_board {','.join(spec.board)}",
        f"set_range_ip {rg.to_solver_range(ip_range)}",
        f"set_range_oop {rg.to_solver_range(oop_range)}",
    ]
    # 주의: set_bet_sizes는 (player, street, kind)별 "덮어쓰기"다 — 여러
    # 사이즈는 한 줄에 콤마로 넣는다 ('bet,33,75'). 실측: CommandLineTool.cpp
    # 가 sizes->clear() 후 4번째 인자부터 전부 push_back 한다.
    remaining = STREETS[STREETS.index(spec.street):]
    bets = ",".join(str(b) for b in BET_SIZES)
    raises = ",".join(str(r) for r in RAISE_SIZES)
    donks = ",".join(str(d) for d in DONK_SIZES)
    for street in remaining:
        for who in ("oop", "ip"):
            lines.append(f"set_bet_sizes {who},{street},bet,{bets}")
            lines.append(f"set_bet_sizes {who},{street},raise,{raises}")
            if who == "oop" and street != spec.street:
                lines.append(f"set_bet_sizes {who},{street},donk,{donks}")
            lines.append(f"set_bet_sizes {who},{street},allin")
    lines += [
        f"set_allin_threshold {ALLIN_THRESHOLD_BY_STREET[spec.street]}",
        "build_tree",
        f"set_thread_num {THREAD_NUM}",
        f"set_accuracy {ACCURACY}",
        f"set_max_iteration {MAX_ITERATION}",
        "set_print_interval 10",
        "set_use_isomorphism 1",
        "start_solve",
        "set_dump_rounds 1",
        f"dump_result {output_file}",
    ]
    return "\n".join(lines) + "\n"
