"""HoldemLog 솔버 워커 — solver_jobs 큐를 폴링해 TexasSolver로 계산한다.

스캐폴드 상태: 폴링 루프·CAS 선점·서브프로세스 실행 골격까지.
hand_to_input()/parse_output()은 콘솔 입력 포맷 실측(README 체크리스트)
후 채운다.
"""

import hashlib
import json
import os
import subprocess
import tempfile
import time

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
# service_role 키 — RLS를 우회해 잡 상태 갱신·결과 기록. 워커 서버에만 둔다.
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SOLVER_BIN = os.environ.get("SOLVER_BIN", "/opt/texassolver/console_solver")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
SOLVE_TIMEOUT = int(os.environ.get("SOLVE_TIMEOUT", "300"))  # 잡당 5분 상한

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
    """동일 스팟 캐시 키 — 보드·유효스택·히어로 포지션·벳사이즈 설정.

    레인지는 포지션별 기본 레인지를 쓰므로 포지션이 곧 레인지 키가 된다.
    """
    key = json.dumps(
        {
            "board": [hand.get("board_flop"), hand.get("board_turn"), hand.get("board_river")],
            "stack": hand.get("effective_stack_bb"),
            "hero": hand.get("hero_position"),
            "sizes": [0.33, 0.75, "allin"],  # 트리 단순화 설정과 함께 갱신
        },
        sort_keys=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()


def hand_to_input(hand: dict, out_dir: str) -> str:
    """핸드 JSON → TexasSolver 콘솔 입력 파일 경로.

    TODO(E2E): 콘솔 브랜치 문서로 입력 포맷 실측 후 구현 —
    보드, 히어로/빌런 레인지(포지션별 기본 레인지 JSON), 유효스택,
    벳 사이즈 33/75/올인, accuracy·max_iteration 설정.
    """
    raise NotImplementedError("콘솔 입력 포맷 실측 후 구현")


def parse_output(output_path: str, hand: dict) -> list[dict]:
    """전략 JSON 덤프 → solver_results 행들.

    TODO(E2E): 히어로가 실제로 한 액션 노드를 찾아 스트리트별
    빈도(strategy_json)·EV(ev_json)·EV Loss(최선 EV - 실제 액션 EV)를
    추출한다 (§8 표시 항목과 1:1).
    """
    raise NotImplementedError("전략 덤프 구조 실측 후 구현")


def process(client: httpx.Client, job: dict) -> None:
    hand_rows = client.get(
        rest("hands"),
        headers=HEADERS,
        params={"id": f"eq.{job['hand_id']}", "select": "*"},
    ).json()
    if not hand_rows:
        raise RuntimeError("핸드가 삭제됨")
    hand = hand_rows[0]

    # 캐시 적중 시 재계산 생략
    cached = client.get(
        rest("solver_results"),
        headers=HEADERS,
        params={"spot_hash": f"eq.{spot_hash(hand)}", "limit": "1", "select": "id"},
    ).json()
    if cached:
        link_results = {"job_id": job["id"], "cached_from": cached[0]["id"]}
        print(f"캐시 적중: {link_results}")
        # TODO: 캐시 행 복제 또는 결과 참조 방식 확정 (0006 설계와 함께)
        return

    with tempfile.TemporaryDirectory() as tmp:
        input_path = hand_to_input(hand, tmp)
        output_path = os.path.join(tmp, "strategy.json")
        subprocess.run(
            [SOLVER_BIN, "-i", input_path, "-o", output_path],
            check=True,
            timeout=SOLVE_TIMEOUT,
        )
        results = parse_output(output_path, hand)

    for row in results:
        row.update(job_id=job["id"], hand_id=job["hand_id"], spot_hash=spot_hash(hand))
    client.post(rest("solver_results"), headers=HEADERS, json=results)


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
