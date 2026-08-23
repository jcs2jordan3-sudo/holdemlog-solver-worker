"""로컬 E2E — 데모 핸드를 실제 TexasSolver 바이너리로 솔빙한다.

Supabase 없이 solve_hand()만 검증한다 (잡 큐·INSERT 경로는 단위 테스트와
서버 배포 시점 통합 테스트가 담당).

실행 (Windows, 릴리즈 바이너리):
  set SOLVER_BIN=C:/dev/texassolver/TexasSolver-v0.2.0-Windows/console_solver.exe
  python run_local_e2e.py
"""

import json
import os
import sys
import time

os.environ.setdefault(
    "SOLVER_BIN",
    "C:/dev/texassolver/TexasSolver-v0.2.0-Windows/console_solver.exe",
)
# Windows v0.2.0 릴리즈는 스레드 8에서 segfault가 실측됨 — 낮춰서 실행
os.environ.setdefault("SOLVER_THREADS", "2")
os.environ.setdefault("SUPABASE_URL", "http://local-e2e")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "local-e2e")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_worker import demo_hand  # noqa: E402
from worker import solve_hand  # noqa: E402


def main() -> None:
    hand = demo_hand()
    t0 = time.time()
    rows = solve_hand(hand)
    elapsed = time.time() - t0

    print(f"\n=== E2E 완료: {elapsed:.1f}s, 결과 {len(rows)}행 ===")
    for r in rows:
        s = r["strategy_json"]
        print(f"\n[{r['street']}] node={r['node_key']}")
        print(f"  실제: {s['actual']} → 트리 사상: {r['hero_action']}")
        print(f"  팟 {s['pot_bb']}bb / 유효 {s['effective_bb']}bb")
        for i, a in enumerate(s["actions"]):
            freq = s["freqs"][i] if i < len(s["freqs"]) else None
            ev = (r["ev_json"] or {}).get("evs", [None] * 9)[i] if r["ev_json"] else None
            line = f"    {a:<14} 빈도 {freq:.3f}" if freq is not None else f"    {a}"
            if ev is not None:
                line += f"  EV {ev:+.2f}bb"
            print(line)
        if r["ev_loss_bb"] is not None:
            print(f"  ▶ EV Loss: {r['ev_loss_bb']}bb")

    # 정확도 자기검증 (리버): 혼합 액션(빈도>5%)들의 EV는 서로 근접해야 한다
    for r in rows:
        if r["street"] != "river" or not r["ev_json"]:
            continue
        s = r["strategy_json"]
        evs = r["ev_json"]["evs"]
        mixed = [evs[i] for i, f in enumerate(s["freqs"]) if f > 0.05]
        if len(mixed) >= 2:
            spread = max(mixed) - min(mixed)
            print(f"\n[검증] 리버 혼합 액션 EV 편차: {spread:.3f}bb (수렴 정확도 지표)")

    with open("e2e_result.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\n결과 저장: e2e_result.json")


if __name__ == "__main__":
    main()
