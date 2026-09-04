# holdemlog-solver-worker

> **상태 (2026-09-04)**: HoldemLog 앱의 Solver Review는 이 워커 대신
> Supabase Edge Function + Claude(LLM) 분석으로 운영 중이다. 이 저장소는
> TexasSolver 기반 정밀 경로가 다시 필요할 때를 위해 완성된 상태로 보관한다
> (로컬 E2E까지 검증됨, VPS 배포는 하지 않았음).

HoldemLog 앱의 Solver Review(§8)를 계산하는 **독립 워커 서비스**.
[TexasSolver](https://github.com/bupticybee/TexasSolver)(AGPL-3.0)를 Docker
이미지 안에서 소스 빌드해 서브프로세스로 실행하고, Supabase `solver_jobs`
큐를 폴링해 결과를 `solver_results`에 쓴다.

> **라이선스**: 이 저장소는 AGPL-3.0으로 공개된다 — TexasSolver를 번들하는
> Docker 이미지를 배포·운영하기 위한 조건이다. 본체 앱(HoldemLog)은 이
> 워커와 테이블 큐로만 통신하는 별개 프로그램이라 AGPL이 전파되지 않는다.
> 상세 근거: 앱 저장소 밖 `solver-worker-plan.md` §1.

## 아키텍처

```
solver_jobs (queued)
  → worker.py 폴링 → status CAS(queued→running)
  → 핸드 JSON → 스트리트별 솔브 스펙 (converter.py)
      - 포스트플랍 헤즈업만 (멀티웨이는 failed + 사유)
      - 레인지: 포지션·스택 깊이(100/40/25bb) 기본 차트 — 앱 STRATEGY 탭과
        동일 데이터 (ranges.py)
      - 트리 단순화: 벳 33/75% + 레이즈 60% + 올인. 올인 임계는 스트리트별
        사다리(플랍 0.67 / 턴 0.85 / 리버 1.0) — 판정식이 커밋 포함이라
        0.67 고정이면 리버 큰 벳이 올인으로 흡수되고, 1.0 고정이면 플랍
        트리가 13GB+로 폭증한다 (둘 다 실측)
  → 콘솔 솔버 실행 (스트리트당 타임아웃)
  → 전략 덤프 워크 (parser.py): 실제 액션 라인을 따라 히어로 결정 노드 추출
      - 빈도: 전 스트리트
      - EV/EV Loss: 리버 (양측 전략 + 레인지 + 쇼다운 에퀴티로 직접 계산)
        플랍·턴 EV는 솔버에 EV 덤프를 패치한 뒤 제공 (아래 '남은 작업')
  → solver_results INSERT → status=done
```

- 동일 스팟 캐시: `spot_hash`(보드+스택+히어로 카드+액션 라인+트리 설정)
  적중 시 재계산 없이 결과 행 복제
- 실패 잡은 `status=failed` + error 기록 — 앱은 재시도 버튼 노출

## 실행

```bash
cp .env.example .env   # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 기입
docker compose up --build
```

로컬 개발 (서버 없이):

```bash
python -m pytest tests -q          # 단위 테스트
python run_local_e2e.py            # 데모 핸드 E2E (콘솔 바이너리 필요)
```

Windows 릴리즈 바이너리(v0.2.0)는 스레드 8에서 segfault가 실측됐다 —
로컬 E2E는 `SOLVER_THREADS`를 2~4로 낮춰 실행한다 (Docker/Linux 빌드는
기본 4, VPS 코어 수에 맞춰 조정).

## 실측 기록 (2026-08-23)

- 콘솔 입력 포맷·덤프 구조 실측 완료 — converter.py/parser.py 모듈
  docstring에 기록
- 덤프에는 전략(빈도)만 있고 **EV가 없다** (console 브랜치는 EV 계산
  코드 자체가 없음, master는 있으나 Qt 의존) → 리버 EV는 워커가 직접
  계산하는 설계로 확정

## 상태

- [x] 스캐폴드 (폴링 루프·CAS·서브프로세스 골격)
- [x] TexasSolver 콘솔 입력 포맷 실측 → `hand_to_input` (converter.py)
- [x] 전략 덤프 파싱 + 빈도 추출 + 리버 EV/EV Loss (parser.py)
- [x] 0006 마이그레이션 SQL 작성 (앱 저장소 supabase/migrations)
- [x] 단위 테스트 12개 + 로컬 E2E 스크립트
- [ ] 0006 서버 적용 (Supabase 토큰 필요)
- [ ] VPS 배포 (docker compose) — 인프라 결정: 저가 VPS 1대, 직렬 큐
- [ ] 플랍·턴 EV: master 브랜치 EV 계산 백포트 패치 → 덤프에 evs 추가
- [ ] 레인지 고도화: 콜링 레인지 차트, 이전 스트리트 전략으로 레인지 내로잉
