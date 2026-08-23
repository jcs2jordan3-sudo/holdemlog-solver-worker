"""TexasSolver 전략 덤프 → 히어로 결정 리뷰 (빈도 + 리버 EV/EV Loss).

덤프 구조 (실측):
  action_node: {actions: [라벨], childrens: {라벨: node}, player: 0(IP)|1(OOP),
                strategy: {actions: [라벨], strategy: {콤보: [빈도]}}}
  터미널(폴드/쇼다운)은 덤프에서 생략된다 — 라벨 의미로 복원한다.
  chance_node: 다음 스트리트 (dump_rounds=1이면 자식 없음).

EV는 리버 솔브에서만 계산한다 — 리버 트리는 라운드 1 덤프에 전체 액션
노드가 담기고 카드 딜이 없어, 양측 전략·레인지·쇼다운 에퀴티로 히어로
콤보의 액션별 EV를 정확히 걷어낼 수 있다. 플랍·턴 EV는 솔버 바이너리에
EV 덤프를 추가(패치)한 뒤 제공한다 (solver-worker-plan §4).
"""

from __future__ import annotations

from dataclasses import dataclass

from converter import StreetSpec
from holdem import RANKS, SUITS, card_index, combo_key_variants, parse_cards, rank7
from ranges import RANK_ORDER


def parse_label(label: str) -> tuple[str, float | None]:
    """'BET 2.000000' → ('BET', 2.0), 'CHECK' → ('CHECK', None)."""
    word, _, amt = label.partition(" ")
    return word, (float(amt) if amt else None)


def map_action_to_label(
    action: dict, labels: list[str], effective: float, actor_commit: float = 0.0
) -> str:
    """실제 액션을 트리 액션 라벨로 사상 (가장 가까운 금액).

    실측 의미론: 라벨의 금액은 Raise-To가 아니라 **현재 커밋 위에 얹는
    추가 금액**이다. 앱 기록(amount_bb = 스트리트 총액 Raise-To)과
    비교하려면 액터의 현재 스트리트 커밋을 빼서 목표 금액을 만든다.
    """
    act = action["action"]
    amt = action.get("amount_bb")
    if act == "fold":
        return "FOLD" if "FOLD" in labels else labels[0]
    if act == "check":
        return "CHECK" if "CHECK" in labels else labels[0]
    if act == "call":
        return "CALL" if "CALL" in labels else labels[0]

    kind = "RAISE" if act == "raise" else "BET"
    if act == "all_in":
        # 올인은 해당 종류 최대 금액 라벨 (BET/RAISE 불문)
        cands = [(parse_label(l)[1], l) for l in labels if parse_label(l)[1] is not None]
        if not cands:
            return labels[0]
        return max(cands)[1]
    cands = [(parse_label(l)[1], l) for l in labels if l.startswith(kind + " ")]
    if not cands:  # 같은 종류가 없으면 금액 있는 아무 라벨
        cands = [(parse_label(l)[1], l) for l in labels if parse_label(l)[1] is not None]
    if not cands:
        return labels[0]
    target = (float(amt) if amt is not None else effective) - actor_commit
    return min(cands, key=lambda c: abs(c[0] - target))[1]


@dataclass
class HeroSpot:
    """스트리트 안에서 히어로가 결정한 지점 하나."""

    street: str
    node_key: str  # 루트→노드 라벨 경로 ('CHECK/BET 5.75')
    actions: list[str]  # 트리 선택지 라벨
    freqs: list[float]  # 히어로 콤보의 액션별 GTO 빈도
    hero_label: str  # 실제 액션이 사상된 트리 라벨
    actual: str  # 실제 액션 원문 ('bet 17.3bb')
    evs: list[float] | None = None  # 액션별 EV (BB, 리버만)
    ev_loss_bb: float | None = None
    path_nodes: list | None = None  # EV 계산용 내부 상태 (직렬화 제외)


def hero_combo_freqs(node: dict, hero_cards: list[str]) -> tuple[list[str], list[float]]:
    strat = node.get("strategy") or {}
    table = strat.get("strategy") or {}
    for key in combo_key_variants(*hero_cards):
        if key in table:
            return list(strat.get("actions") or node["actions"]), [float(x) for x in table[key]]
    return list(strat.get("actions") or node.get("actions") or []), []


def walk_street(
    spec: StreetSpec, dump_root: dict, hero_seat: int, hero_cards: list[str]
) -> list[HeroSpot]:
    """실제 액션 순서로 덤프 트리를 걸으며 히어로 결정 지점을 수집한다."""
    spots: list[HeroSpot] = []
    node: dict | None = dump_root
    path: list[tuple[dict, str]] = []  # (노드, 선택된 라벨)
    commits = {0: 0.0, 1: 0.0}  # 시트별 스트리트 커밋 (라벨 사상용)

    for a in spec.street_actions:
        if node is None or node.get("node_type") != "action_node":
            break
        seat = node.get("player")
        labels = list(node.get("actions") or [])
        label = map_action_to_label(a, labels, spec.effective, commits.get(seat, 0.0))
        kind, amt = parse_label(label)
        actor_is_hero = seat == hero_seat
        if actor_is_hero:
            actions, freqs = hero_combo_freqs(node, hero_cards)
            amt = a.get("amount_bb")
            actual = a["action"] + (f" {amt}bb" if amt is not None else "")
            spots.append(
                HeroSpot(
                    street=spec.street,
                    node_key="/".join(l for _, l in path) or "(root)",
                    actions=actions,
                    freqs=freqs,
                    hero_label=label,
                    actual=actual,
                    # 마지막 항목이 결정 노드 자신 — EV 계산이 이 관례를 쓴다
                    path_nodes=list(path) + [(node, label)],
                )
            )
        if kind in ("BET", "RAISE"):
            commits[seat] = commits.get(seat, 0.0) + (amt or 0.0)
        elif kind == "CALL":
            commits[seat] = commits.get(1 - seat, 0.0)
        path.append((node, label))
        node = (node.get("childrens") or {}).get(label)

    return spots


# ── 리버 EV 계산 ─────────────────────────────────────────────────


def _expand_label(label: str) -> list[tuple[str, str]]:
    """169 라벨 → 콤보 목록. 'AJs' → [('Ah','Jh'), ...]"""
    combos = []
    if len(label) == 2:  # 페어
        r = label[0]
        for i in range(4):
            for j in range(i + 1, 4):
                combos.append((r + SUITS[i], r + SUITS[j]))
    elif label[2] == "s":
        for s in SUITS:
            combos.append((label[0] + s, label[1] + s))
    else:
        for s1 in SUITS:
            for s2 in SUITS:
                if s1 != s2:
                    combos.append((label[0] + s1, label[1] + s2))
    return combos


def villain_combos(
    villain_range: dict[str, float], board: list[str], hero_cards: list[str]
) -> tuple[list[tuple[str, str]], list[float]]:
    """빌런 레인지 → (콤보, 초기 가중치) — 보드·히어로 카드 제거 적용."""
    dead = {card_index(c) for c in board} | {card_index(c) for c in hero_cards}
    combos: list[tuple[str, str]] = []
    weights: list[float] = []
    for label, w in villain_range.items():
        for c1, c2 in _expand_label(label):
            if card_index(c1) in dead or card_index(c2) in dead:
                continue
            combos.append((c1, c2))
            weights.append(w)
    return combos, weights


def _combo_freq_row(node: dict, combo: tuple[str, str], n_actions: int) -> list[float]:
    table = (node.get("strategy") or {}).get("strategy") or {}
    for key in combo_key_variants(*combo):
        if key in table:
            return [float(x) for x in table[key]]
    return [0.0] * n_actions


def river_action_evs(
    spec: StreetSpec, hero_spot: HeroSpot, hero_cards: list[str]
) -> list[float]:
    """히어로 결정 노드에서 각 트리 액션의 EV(BB).

    기준점: 결정 시점 이후 히어로 추가 투입은 음수, 최종 팟 획득은 양수.
    (동일 노드의 액션 간 비교가 목적이므로 이미 넣은 칩은 상수로 제외)
    """
    combos, w0 = villain_combos(spec.villain_range, spec.board, hero_cards)
    hero_rank = rank7(hero_cards + spec.board)
    v_ranks = [rank7(list(c) + spec.board) for c in combos]

    # 결정 노드 "이전"까지 빌런 도달 확률 갱신 + 스트리트 커밋 재구성.
    # path_nodes 마지막 항목은 결정 노드 자신이므로 리플레이에서 제외한다.
    hero_seat_is_ip = spec.hero_is_ip
    reach = list(w0)
    c_ip = c_oop = 0.0
    for node, label in (hero_spot.path_nodes or [])[:-1]:
        player = node.get("player")
        kind, amt = parse_label(label)
        if player == (0 if hero_seat_is_ip else 1):  # 히어로 노드 — 도달 확률 불변
            pass
        else:
            actions = list((node.get("strategy") or {}).get("actions") or node["actions"])
            idx = actions.index(label) if label in actions else -1
            for i, combo in enumerate(combos):
                row = _combo_freq_row(node, combo, len(actions))
                reach[i] *= row[idx] if 0 <= idx < len(row) else 0.0
        # 라벨 금액 = 현재 커밋 위에 얹는 추가 금액 (실측 의미론)
        if kind in ("BET", "RAISE"):
            if player == 0:
                c_ip += amt or 0.0
            else:
                c_oop += amt or 0.0
        elif kind == "CALL":
            if player == 0:
                c_ip = c_oop
            else:
                c_oop = c_ip

    hero_c = c_ip if hero_seat_is_ip else c_oop
    villain_c = c_oop if hero_seat_is_ip else c_ip

    node = _node_at(hero_spot)

    evs = []
    total_mass = sum(reach) or 1.0
    for label in hero_spot.actions:
        ev_sum = _ev_after_hero(
            spec, node, label, hero_cards, hero_rank, combos, v_ranks, reach,
            hero_c, villain_c, hero_spent=0.0,
        )
        evs.append(ev_sum / total_mass)
    return evs


def _node_at(hero_spot: HeroSpot) -> dict:
    """path_nodes 마지막 엣지의 자식 = 결정 노드. 루트 결정이면 첫 노드."""
    path = hero_spot.path_nodes or []
    if not path:
        raise ValueError("경로가 비어 있습니다")
    # walk_street는 결정 노드 자신도 path에 (노드, 선택라벨)로 넣는다 —
    # 마지막 항목의 노드가 곧 결정 노드다.
    return path[-1][0]


def _ev_after_hero(
    spec, node, label, hero_cards, hero_rank, combos, v_ranks, reach,
    c_hero, c_villain, hero_spent,
):
    """히어로가 [label]을 택한 뒤의 EV 합 (reach 가중, 정규화 전)."""
    kind, amt = parse_label(label)
    if kind == "FOLD":
        return 0.0 - hero_spent * sum(reach)
    if kind == "CALL":
        cost = c_villain - c_hero
        pot = spec.pot + 2 * c_villain
        return _showdown_sum(hero_rank, v_ranks, reach, pot) - (hero_spent + cost) * sum(reach)
    if kind == "CHECK":
        new_c_hero = c_hero
        child = (node.get("childrens") or {}).get(label)
        if child is None:  # 체크로 스트리트 종료 → 쇼다운
            pot = spec.pot + c_hero + c_villain
            return _showdown_sum(hero_rank, v_ranks, reach, pot) - hero_spent * sum(reach)
        return _ev_villain_node(
            spec, child, hero_cards, hero_rank, combos, v_ranks, reach,
            new_c_hero, c_villain, hero_spent,
        )
    # BET/RAISE — 라벨 금액은 현재 커밋 위에 얹는 추가 금액
    cost = amt or 0.0
    new_c_hero = c_hero + cost
    child = (node.get("childrens") or {}).get(label)
    if child is None:
        # 응답 노드가 없는 벳은 비정상 — 보수적으로 콜 종료로 처리
        pot = spec.pot + 2 * new_c_hero
        return _showdown_sum(hero_rank, v_ranks, reach, pot) - (hero_spent + cost) * sum(reach)
    return _ev_villain_node(
        spec, child, hero_cards, hero_rank, combos, v_ranks, reach,
        new_c_hero, c_villain, hero_spent + cost,
    )


def _ev_villain_node(
    spec, node, hero_cards, hero_rank, combos, v_ranks, reach,
    c_hero, c_villain, hero_spent,
):
    """빌런 액션 노드 — 빌런 전략으로 reach를 나눠 각 갈래를 합산한다."""
    if node.get("node_type") != "action_node":
        # 리버에서는 chance_node가 없어야 한다 — 방어적으로 쇼다운 처리
        pot = spec.pot + c_hero + c_villain
        return _showdown_sum(hero_rank, v_ranks, reach, pot) - hero_spent * sum(reach)

    hero_seat = 0 if spec.hero_is_ip else 1
    if node.get("player") == hero_seat:
        # 히어로 재결정 노드 — 히어로 콤보의 덤프 전략을 따른다
        actions, freqs = hero_combo_freqs(node, hero_cards)
        if not freqs:
            freqs = [1.0 / len(actions)] * len(actions)
        total = 0.0
        for f, lab in zip(freqs, actions):
            if f <= 1e-9:
                continue
            total += f * _ev_after_hero(
                spec, node, lab, hero_cards, hero_rank, combos, v_ranks, reach,
                c_hero, c_villain, hero_spent,
            )
        return total

    actions = list((node.get("strategy") or {}).get("actions") or node["actions"])
    rows = [_combo_freq_row(node, c, len(actions)) for c in combos]
    total = 0.0
    for idx, label in enumerate(actions):
        branch_reach = [reach[i] * rows[i][idx] for i in range(len(combos))]
        if sum(branch_reach) <= 1e-12:
            continue
        kind, amt = parse_label(label)
        if kind == "FOLD":
            pot = spec.pot + c_hero + c_villain
            total += sum(branch_reach) * (pot - hero_spent)
            continue
        if kind == "CALL":
            pot = spec.pot + 2 * c_hero
            total += _showdown_sum(hero_rank, v_ranks, branch_reach, pot) - hero_spent * sum(branch_reach)
            continue
        if kind == "CHECK":
            child = (node.get("childrens") or {}).get(label)
            if child is None:  # 빌런 체크로 종료 → 쇼다운
                pot = spec.pot + c_hero + c_villain
                total += _showdown_sum(hero_rank, v_ranks, branch_reach, pot) - hero_spent * sum(branch_reach)
            else:
                total += _ev_hero_node(
                    spec, child, hero_cards, hero_rank, combos, v_ranks, branch_reach,
                    c_hero, c_villain, hero_spent,
                )
            continue
        # BET/RAISE — 빌런 커밋에 추가 금액을 얹고 히어로 응답 노드로
        child = (node.get("childrens") or {}).get(label)
        if child is None:
            continue  # 응답 없는 벳 — 도달 불가로 간주
        total += _ev_hero_node(
            spec, child, hero_cards, hero_rank, combos, v_ranks, branch_reach,
            c_hero, c_villain + (amt or 0.0), hero_spent,
        )
    return total


def _ev_hero_node(
    spec, node, hero_cards, hero_rank, combos, v_ranks, reach,
    c_hero, c_villain, hero_spent,
):
    """히어로 차례 노드 — 히어로는 덤프 전략(자기 콤보)을 따른다."""
    actions, freqs = hero_combo_freqs(node, hero_cards)
    if not freqs:
        freqs = [1.0 / len(actions)] * len(actions) if actions else []
    total = 0.0
    for f, lab in zip(freqs, actions):
        if f <= 1e-9:
            continue
        total += f * _ev_after_hero(
            spec, node, lab, hero_cards, hero_rank, combos, v_ranks, reach,
            c_hero, c_villain, hero_spent,
        )
    return total


def _showdown_sum(hero_rank, v_ranks, reach, pot):
    total = 0.0
    for r, vr in zip(reach, v_ranks):
        if r <= 0:
            continue
        if hero_rank > vr:
            total += r * pot
        elif hero_rank == vr:
            total += r * pot / 2
    return total


def finalize_spots(spec: StreetSpec, spots: list[HeroSpot], hero_cards_code: str) -> None:
    """리버 스팟에 EV/EV Loss를 채우고 직렬화용 내부 상태를 정리한다."""
    hero_cards = parse_cards(hero_cards_code)
    for s in spots:
        if spec.street == "river" and s.freqs:
            try:
                s.evs = [round(v, 3) for v in river_action_evs(spec, s, hero_cards)]
                if s.hero_label in s.actions:
                    actual_ev = s.evs[s.actions.index(s.hero_label)]
                    s.ev_loss_bb = round(max(s.evs) - actual_ev, 3)
            except Exception:  # EV는 부가 정보 — 실패해도 빈도 리뷰는 남긴다
                s.evs = None
        s.path_nodes = None
