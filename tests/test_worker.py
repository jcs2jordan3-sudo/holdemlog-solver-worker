"""워커 단위 테스트 — 베팅 리플레이·레인지·변환기·덤프 워크·리버 EV.

실행: python -m pytest tests -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import ranges as rg
from converter import UnsupportedHand, build_street_specs, render_input
from holdem import (
    combo_key,
    parse_cards,
    postflop_order,
    rank7,
    state_entering,
    street_contributions,
)
from parser import HeroSpot, finalize_spots, map_action_to_label, walk_street


def demo_hand() -> dict:
    """앱 hands_provider.dart demoHand()와 동일한 픽스처."""
    return {
        "game_type": "tournament",
        "table_size": 8,
        "sb": 500,
        "bb": 1000,
        "ante": 1000,
        "effective_stack_bb": 42,
        "hero_position": "btn",
        "hero_stack_bb": 42,
        "hero_cards": "AsJs",
        "board_flop": "Jh8s4c",
        "board_turn": "2d",
        "board_river": "Kd",
        "actions": [
            {"street": "preflop", "seq": 0, "position": "hj", "action": "bet", "amount_bb": 2.2},
            {"street": "preflop", "seq": 1, "position": "btn", "action": "call", "amount_bb": 2.2},
            {"street": "flop", "seq": 2, "position": "hj", "action": "bet", "amount_bb": 2.3},
            {"street": "flop", "seq": 3, "position": "btn", "action": "call", "amount_bb": 2.3},
            {"street": "turn", "seq": 4, "position": "hj", "action": "check"},
            {"street": "turn", "seq": 5, "position": "btn", "action": "bet", "amount_bb": 5.8},
            {"street": "turn", "seq": 6, "position": "hj", "action": "call", "amount_bb": 5.8},
            {"street": "river", "seq": 7, "position": "hj", "action": "check"},
            {"street": "river", "seq": 8, "position": "btn", "action": "bet", "amount_bb": 17.3},
            {"street": "river", "seq": 9, "position": "hj", "action": "call", "amount_bb": 17.3},
        ],
    }


# ── holdem ───────────────────────────────────────────────────────


def test_postflop_order_btn_last():
    assert postflop_order(8)[-1] == "btn"
    assert postflop_order(8)[0] == "sb"


def test_street_contributions_preflop_includes_blinds():
    c = street_contributions(demo_hand()["actions"], "preflop", sb_bb=0.5)
    assert c == {"sb": 0.5, "bb": 1.0, "hj": 2.2, "btn": 2.2}


def test_state_entering_matches_app_pot_math():
    h = demo_hand()
    flop = state_entering(h, "flop", "btn", "hj")
    assert flop.pot == pytest.approx(6.9)  # 앤티1 + 블라인드1.5 + 2.2*2
    assert flop.effective_left == pytest.approx(39.8)
    turn = state_entering(h, "turn", "btn", "hj")
    assert turn.pot == pytest.approx(11.5)
    assert turn.effective_left == pytest.approx(37.5)
    river = state_entering(h, "river", "btn", "hj")
    assert river.pot == pytest.approx(23.1)
    assert river.effective_left == pytest.approx(31.7)


def test_rank7_orderings():
    board = parse_cards("Jh8s4c2dKd")
    top_pair = rank7(parse_cards("AsJs") + board)
    under_pair = rank7(parse_cards("TdTc") + board)
    king_pair = rank7(parse_cards("KsQs") + board)
    assert top_pair > under_pair  # 데모 핸드의 실제 결말
    assert king_pair > top_pair  # K 페어 > J 페어
    wheel = rank7(parse_cards("As2s") + parse_cards("3c4d5h9sJc"))
    pair_only = rank7(parse_cards("AsAd") + parse_cards("3c4d5h9sJc"))
    assert wheel > pair_only  # 휠 스트레이트 > 원페어


# ── ranges ───────────────────────────────────────────────────────


def test_parse_range_expansions():
    w = rg.parse_range("66+, A9s+:0.5, KQo")
    assert w["AA"] == 1.0 and w["66"] == 1.0 and "55" not in w
    assert w["AKs"] == 0.5 and w["A9s"] == 0.5 and "A8s" not in w
    assert w["KQo"] == 1.0


def test_demo_hero_hand_in_btn_open_range():
    w = rg.open_range_for(8, "btn", 40)
    assert w.get("AJs") == 1.0
    assert rg.hand_label("As", "Js") == "AJs"


def test_bb_uses_btn_proxy():
    assert rg.open_range_for(8, "bb", 100) == rg.parse_range(rg.OPEN_100["btn"])


# ── converter ────────────────────────────────────────────────────


def test_build_street_specs_demo():
    specs, ctx = build_street_specs(demo_hand())
    assert [s.street for s in specs] == ["flop", "turn", "river"]
    assert ctx["hero_is_ip"] is True  # BTN은 HJ보다 뒤
    assert ctx["depth"] == 40  # 42bb → 40bb 차트
    river = specs[-1]
    assert river.pot == pytest.approx(23.1)
    assert river.board == ["Jh", "8s", "4c", "2d", "Kd"]
    text = render_input(river, "out.json")
    assert "set_board Jh,8s,4c,2d,Kd" in text
    assert "set_pot 23.1" in text
    assert "dump_result out.json" in text
    # 리버 솔브에는 리버 사이즈만 있다
    assert "flop,bet" not in text and "river,bet" in text


def test_multiway_rejected():
    h = demo_hand()
    h["actions"].append(
        {"street": "flop", "seq": 10, "position": "sb", "action": "call", "amount_bb": 2.3}
    )
    with pytest.raises(UnsupportedHand):
        build_street_specs(h)


# ── parser ───────────────────────────────────────────────────────


def _river_spec():
    specs, _ = build_street_specs(demo_hand())
    return specs[-1]


def test_map_action_nearest_amount():
    labels = ["CHECK", "BET 7.62", "BET 17.32", "BET 31.70"]
    assert map_action_to_label({"action": "bet", "amount_bb": 17.3}, labels, 31.7) == "BET 17.32"
    assert map_action_to_label({"action": "check"}, labels, 31.7) == "CHECK"
    assert (
        map_action_to_label({"action": "all_in"}, labels, 31.7) == "BET 31.70"
    )


def make_toy_river_dump(pot: float, bet: float):
    """히어로(OOP=player1) 너츠 vs 100% 콜하는 빌런의 장난감 리버 트리."""
    def strat(combos, freqs):
        return {"actions": None, "strategy": {c: freqs for c in combos}}

    villain_combos = ["2d2h", "2d2s", "2h2s"]
    bet_label = f"BET {bet:.6f}"
    villain_after_bet = {
        "node_type": "action_node",
        "player": 0,
        "actions": ["CALL", "FOLD"],
        "childrens": {},
        "strategy": {"actions": ["CALL", "FOLD"], "strategy": {c: [1.0, 0.0] for c in villain_combos}},
    }
    villain_after_check = {
        "node_type": "action_node",
        "player": 0,
        "actions": ["CHECK", bet_label],
        "childrens": {},
        "strategy": {"actions": ["CHECK", bet_label], "strategy": {c: [1.0, 0.0] for c in villain_combos}},
    }
    hero_combo = "QdQh"
    root = {
        "node_type": "action_node",
        "player": 1,
        "actions": ["CHECK", bet_label],
        "childrens": {bet_label: villain_after_bet, "CHECK": villain_after_check},
        "strategy": {"actions": ["CHECK", bet_label], "strategy": {hero_combo: [0.0, 1.0]}},
    }
    return root, bet_label


def test_river_ev_toy_case():
    """너츠로 벳 = 팟 + 벳 획득, 체크 = 팟 획득 — EV Loss = 벳 크기."""
    from converter import StreetSpec

    pot, bet = 10.0, 5.0
    board = parse_cards("2c7d9hThQs")
    spec = StreetSpec(
        street="river",
        board=board,
        pot=pot,
        effective=30.0,
        hero_is_ip=False,  # 히어로 OOP (player 1)
        hero_range={"QQ": 1.0},
        villain_range={"22": 1.0},
        street_actions=[{"action": "check", "position": "x"}],
    )
    dump, bet_label = make_toy_river_dump(pot, bet)
    hero_cards = ["Qd", "Qh"]
    spots = walk_street(spec, dump, hero_seat=1, hero_cards=hero_cards)
    assert len(spots) == 1
    spot = spots[0]
    assert spot.actions == ["CHECK", bet_label]
    assert spot.freqs == [0.0, 1.0]

    finalize_spots(spec, spots, "QdQh")
    # 빌런(22 셋 아님 — 2c가 보드라 남은 콤보 3개, 전부 히어로 탑셋에 패배)
    assert spot.evs is not None
    ev_check, ev_bet = spot.evs
    assert ev_check == pytest.approx(pot, abs=0.01)
    assert ev_bet == pytest.approx(pot + bet, abs=0.01)
    # 실제 액션이 체크였으므로 EV Loss = 벳 EV와의 차
    assert spot.hero_label == "CHECK"
    assert spot.ev_loss_bb == pytest.approx(bet, abs=0.01)


def test_map_raise_uses_additive_semantics():
    """라벨 금액 = 추가 금액. Raise-To 20, 이미 2.3 커밋 → 목표 17.7."""
    labels = ["CALL", "RAISE 17.70", "RAISE 29.40", "FOLD"]
    assert (
        map_action_to_label(
            {"action": "raise", "amount_bb": 20}, labels, 31.7, actor_commit=2.3
        )
        == "RAISE 17.70"
    )


def test_combo_key_order():
    assert combo_key("Js", "As") == "AsJs"
    assert combo_key("Tc", "9c") == "Tc9c"
