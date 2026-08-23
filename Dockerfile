# ── 1단계: TexasSolver를 소스에서 빌드 (AGPL 준수 — 바이너리 재배포 대신
#    이미지 빌드 시 직접 빌드, 소스 제공 의무는 이 공개 저장소가 충족)
FROM debian:bookworm-slim AS solver-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake g++ make ca-certificates && rm -rf /var/lib/apt/lists/*
# console 브랜치 = 콘솔 전용 CMake 타깃(console_solver) 제공, Qt 불필요.
# 재현성: E2E 검증을 마친 시점의 커밋으로 고정해 갱신한다.
ARG TEXASSOLVER_REF=console
RUN git clone --depth 1 --branch ${TEXASSOLVER_REF} \
    https://github.com/bupticybee/TexasSolver.git /src
WORKDIR /src
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release . && \
    cmake --build build --target console_solver -j"$(nproc)"

# ── 2단계: 파이썬 워커
FROM python:3.12-slim
RUN useradd -m worker
COPY --from=solver-build /src/build/console_solver /opt/texassolver/console_solver
# 카드 사전 등 런타임 리소스 — 바이너리는 CWD 기준 ./resources를 읽는다
COPY --from=solver-build /src/resources /opt/texassolver/resources
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY holdem.py ranges.py converter.py parser.py worker.py /app/
USER worker
WORKDIR /app
ENV SOLVER_BIN=/opt/texassolver/console_solver
ENV SOLVER_THREADS=4
CMD ["python", "worker.py"]
