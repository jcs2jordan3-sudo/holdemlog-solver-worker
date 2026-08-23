"""HoldemLog 솔버 워커 — solver_jobs 큐를 폴링해 TexasSolver로 계산한다.

파이프라인 (스트리트별 솔브, solver-worker-plan §2·§4):
  잡 선점 → 핸드 로드 → 스트리트별 솔브 스펙 생성(converter)
  → 콘솔 솔버 실행 → 덤프 워크로 히어로 결정 추출(parser)
  → 빈도(전 스트리트) + EV/EV Loss(리버) → solver_results INSERT
"""

import hashlib
import json
import os
import subprocess
import tempfile
import time

import httpx

from converter import (
    ACCURACY,
    ALLIN_THRESHOLD_BY_STREET,
    BET_SIZES,
    MAX_ITERATION,
    RAISE_SIZES,
    UnsupportedHand,
    build_street_specs,
    render_input,
)
from holdem import parse_cards
from parser import finalize_spots, walk_street

SUPABASE_URL = os.environ["SUPABASE_URL"]
# service_role 키 — RLS를 우회해 잡 상태 갱신·결과 기록. 워커 서버에만 둔다.
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SOLVER_BIN = os.environ.get("SOLVER_BIN", "/opt/texassolver/console_solver")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
SOLVE_TIMEOUT = int(os.environ.get("SOLVE_TIMEOUT", "300"))  # 스트리트당 상한

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}


def rest(path: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{path}"


def claim_job(client: httpx.Client) -> dict | None:
    """queued 잡 하나를 CAS로 선점한다 (status=queued 조건 update).

    동시에 여러 워커가 떠도 update의 eq(status=queued) 조건이 한 쪽만
    성공시킨다 — 반환 행이 비면 선점 실패로 보고 다음 폴링을 기다린다.
    """
    rows = client.get(
        rest("solver_jobs"),
        headers=HEADERS,
        params={
            "status": "eq.queued",
            "order": "requested_at.asc",
            "limit": "1",
            "select": "id,hand_id,user_id",
        },
    ).json()
    if not rows:
        return None
    job = rows[0]
    claimed = client.patch(
        rest("solver_jobs"),
        headers={**HEADERS, "Prefer": "return=representation"},
        params={"id": f"eq.{job['id']}", "status": "eq.queued"},
        json={"status": "running", "started_at": "now()"},
    ).json()
    return job if claimed else None


def spot_hash(hand: dict) -> str:
    """동일 스팟 캐시 키.

    보드·유효스택·히어로 카드/포지션·액션 라인·트리 설정이 모두 같아야
    결과를 재사용할 수 있다 (결과 행이 히어로 콤보 기준이므로).
    """
    key = json.dumps(
        {
            "board": [hand.get("board_flop"), hand.get("board_turn"), hand.get("board_river")],
            "stack": hand.get("effective_stack_bb") or hand.get("hero_stack_bb"),
            "hero": hand.get("hero_position"),
            "cards": hand.get("hero_cards"),
            "table": hand.get("table_size"),
            "line": [
                [a.get("street"), a.get("position"), a.get("action"), a.get("amount_bb")]
                for a in hand.get("actions", [])
            ],
            "tree": [BET_SIZES, RAISE_SIZES, ACCURACY, MAX_ITERATION, sorted(ALLIN_THRESHOLD_BY_STREET.items())],
        },
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()


def solve_hand(hand: dict) -> list[dict]:
    """핸드 하나를 스트리트별로 솔빙해 solver_results 행 목록을 만든다.

    (job_id/hand_id/spot_hash는 호출자가 채운다)
    """
    specs, ctx = build_street_specs(hand)
    hero_cards = parse_cards(hand["hero_cards"])
    solver_dir = os.path.dirname(SOLVER_BIN) or "."
    rows: list[dict] = []

    with tempfile.TemporaryDirectory() as tmp:
        for spec in specs:
            out_path = os.path.join(tmp, f"{spec.street}.json").replace("\\", "/")
            in_path = os.path.join(tmp, f"{spec.street}.txt")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write(render_input(spec, output_file=out_path))
            subprocess.run(
                [SOLVER_BIN, "-i", in_path],
                check=True,
                timeout=SOLVE_TIMEOUT,
                cwd=solver_dir,
                stdout=subprocess.DEVNULL,
            )
            with open(out_path, encoding="utf-8") as f:
                dump = json.load(f)

            hero_seat = 0 if spec.hero_is_ip else 1
            spots = walk_street(spec, dump, hero_seat, hero_cards)
            finalize_spots(spec, spots, hand["hero_cards"])
            for s in spots:
                rows.append(
                    {
                        "street": s.street,
                        "node_key": s.node_key,
                        "strategy_json": {
                            "actions": s.actions,
                            "freqs": s.freqs,
                            "actual": s.actual,
                            "pot_bb": spec.pot,
                            "effective_bb": spec.effective,
                        },
                        "ev_json": None if s.evs is None else {"actions": s.actions, "evs": s.evs},
                        "hero_action": s.hero_label,
                        "ev_loss_bb": s.ev_loss_bb,
                    }
                )
    return rows


def process(client: httpx.Client, job: dict) -> None:
    hand_rows = client.get(
        rest("hands"),
        headers=HEADERS,
        params={"id": f"eq.{job['hand_id']}", "select": "*"},
    ).json()
    if not hand_rows:
        raise RuntimeError("핸드가 삭제됨")
    hand = hand_rows[0]
    h = spot_hash(hand)

    # 캐시 적중 시 재계산 없이 기존 결과 행을 새 잡으로 복제
    cached = client.get(
        rest("solver_results"),
        headers=HEADERS,
        params={"spot_hash": f"eq.{h}", "select": "*", "order": "created_at.asc"},
    ).json()
    if cached:
        rows = [
            {
                k: r[k]
                for k in ("street", "node_key", "strategy_json", "ev_json", "hero_action", "ev_loss_bb")
            }
            for r in cached
            if r["job_id"] != job["id"]
        ]
        print(f"캐시 적중: {len(rows)}행 복제")
    else:
        rows = solve_hand(hand)

    for row in rows:
        row.update(job_id=job["id"], hand_id=job["hand_id"], spot_hash=h)
    if rows:
        client.post(rest("solver_results"), headers=HEADERS, json=rows)


def main() -> None:
    print(f"솔버 워커 시작 — {SUPABASE_URL}, 폴링 {POLL_SECONDS}s")
    with httpx.Client(timeout=30) as client:
        while True:
            try:
                job = claim_job(client)
                if job is None:
                    time.sleep(POLL_SECONDS)
                    continue
                print(f"잡 처리: {job['id']}")
                try:
                    process(client, job)
                    status = {"status": "done", "finished_at": "now()"}
                except UnsupportedHand as e:
                    print(f"미지원 핸드: {e}")
                    status = {"status": "failed", "error": str(e), "finished_at": "now()"}
                except Exception as e:  # noqa: BLE001 — 잡 단위 격리
                    print(f"잡 실패: {e}")
                    status = {"status": "failed", "error": str(e)[:500], "finished_at": "now()"}
                client.patch(
                    rest("solver_jobs"),
                    headers=HEADERS,
                    params={"id": f"eq.{job['id']}"},
                    json=status,
                )
            except Exception as e:  # noqa: BLE001 — 네트워크 등, 루프는 살아남는다
                print(f"폴링 오류(재시도): {e}")
                time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
