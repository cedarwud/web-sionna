# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /workspace

# 1) 系統依賴：加 cmake、libsctp-dev、lksctp-tools、llvm、llvm-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git cmake \
      libsctp-dev lksctp-tools \
      llvm llvm-dev \
    && rm -rf /var/lib/apt/lists/*

# 2) Python 套件：原 requirements + Sionna/Skyfield/Docker SDK/FASTAPI
COPY backend/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt \
    && pip install --no-cache-dir \
         sionna==0.15 \
         skyfield==1.46 \
         docker==7.1.0 \
         fastapi uvicorn[standard] pydantic[email]

# 3) Clone & Build UERANSIM
RUN git clone --depth=1 https://github.com/aligungr/UERANSIM.git /tmp/ueransim \
 && cd /tmp/ueransim \
 && cmake -DCMAKE_BUILD_TYPE=Release -G "Unix Makefiles" -B build \
 && make -C build -j$(nproc) \
 && mkdir -p /workspace/ueransim \
 && cp build/nr-* /workspace/ueransim/ \
 && rm -rf /tmp/ueransim

# 4) 複製後端程式與 UERANSIM 配置
COPY backend /workspace/backend
COPY ueransim-config /workspace/config

# 5) 設定路徑與啟動
ENV PYTHONPATH=/workspace/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
