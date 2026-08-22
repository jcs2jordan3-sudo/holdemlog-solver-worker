# holdemlog-solver-worker

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
  → 핸드 JSON → 트리 단순화(벳 33/75/올인) → TexasSolver 입력 파일
  → 콘솔 솔버 실행 (타임아웃·메모리 제한)
  → 전략 JSON 파싱 → 히어로 액션 노드의 빈도/EV/EV Loss
  → solver_results INSERT → status=done
```

- 동일 스팟 캐시: `spot_hash`(보드+레인지+스택+벳사이즈) 적중 시 재계산 생략
- 실패 잡은 `status=failed` + error 기록 — 앱은 재시도 버튼 노출

## 실행

```bash
cp .env.example .env   # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 기입
docker compose up --build
```

## 상태

- [x] 스캐폴드 (폴링 루프·CAS·서브프로세스 골격)
- [ ] TexasSolver 콘솔 입력 포맷 실측 → `hand_to_input()` 구현
- [ ] 전략 JSON → EV Loss 추출 `parse_output()` 구현
- [ ] 0006 마이그레이션 (solver_jobs / solver_results) 적용
- [ ] 로컬 Docker E2E (데모 핸드) → VPS 배포
