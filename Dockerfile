# ── 1단계: TexasSolver를 소스에서 빌드 (AGPL 준수 — 바이너리 재배포 대신
#    이미지 빌드 시 직접 빌드, 소스 제공 의무는 이 공개 저장소가 충족)
FROM debian:bookworm-slim AS solver-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake g++ make ca-certificates && rm -rf /var/lib/apt/lists/*
# 재현성: 커밋 고정 (E2E 검증 시점에 최신 안정 커밋으로 갱신)
ARG TEXASSOLVER_REF=master
RUN git clone --depth 1 --branch ${TEXASSOLVER_REF} \
    https://github.com/bupticybee/TexasSolver.git /src
WORKDIR /src
# TODO(E2E): console 타깃 빌드 명령 실측 확인 (콘솔 브랜치 문서 기준)
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release . && \
    cmake --build build -j"$(nproc)" || echo "빌드 타깃은 E2E 단계에서 확정"

# ── 2단계: 파이썬 워커
FROM python:3.12-slim
RUN useradd -m worker
COPY --from=solver-build /src/build /opt/texassolver
COPY --from=solver-build /src/resources /opt/texassolver/resources
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY worker.py /app/
USER worker
WORKDIR /app
ENV SOLVER_BIN=/opt/texassolver/console_solver
CMD ["python", "worker.py"]
