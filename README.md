# Sionna RT 模擬平台專案

## 專案概觀

本專案旨在建立一個基於 NVIDIA Sionna RT 函式庫的無線通道模擬平台。後端使用 FastAPI (Python) 框架，搭配 SQLModel、非同步 SQLAlchemy 2.0 及 PostgreSQL/PostGIS 資料庫來儲存與管理模擬中的發射器 (Tx)、接收器 (Rx) 及干擾源節點參數。前端使用 React (TypeScript) 和 Vite 構建，提供使用者互動介面（目前主要用於顯示模擬結果，未來規劃加入節點管理功能）。整個應用程式透過 Docker 和 Docker Compose 進行容器化部署與管理。

## 主要功能

* **Sionna RT 模擬:**
    * 渲染包含路徑追蹤結果的 3D 場景圖像 (基於 'etoile' 場景)。
    * 產生基於模擬路徑的訊號星座圖，可包含干擾源影響。
* **後端 API:**
    * 提供 RESTful API 端點以觸發模擬並取得結果圖像。
    * 使用 FastAPI 建立非同步 API 服務。
* **資料庫整合:**
    * 使用 PostgreSQL 資料庫搭配 PostGIS 擴充套件儲存節點資訊 (名稱、類型、位置、啟用狀態)。
    * 使用 SQLModel 和非同步 SQLAlchemy 2.0 進行 ORM 操作。
    * 應用程式啟動時自動建立資料庫表格並填入初始種子資料。
* **前端顯示:**
    * 使用 React 框架顯示後端產生的模擬場景圖與星座圖。
    * 透過 Vite 進行前端開發與構建 [cite: 3, 4]。
* **容器化部署:**
    * 使用 Docker 和 Docker Compose 簡化開發與部署流程 [cite: 1]。
    * 分離後端、前端與資料庫服務。
* **硬體加速:**
    * 支援使用 NVIDIA GPU 進行 Sionna RT 計算加速（可透過環境變數 `CUDA_VISIBLE_DEVICES` 控制）[cite: 1, 2]。
    * 若無可用 GPU 或強制設定，則自動使用 CPU。

## 技術棧

* **後端:**
    * Python 3.11+
    * FastAPI
    * Uvicorn (ASGI Server)
    * Sionna & Sionna RT
    * SQLModel & SQLAlchemy 2.0 (Async)
    * GeoAlchemy2 (PostGIS Support)
    * Psycopg (Binary, Pool) & Asyncpg (PostgreSQL Drivers)
    * Matplotlib (圖像生成)
    * TensorFlow (Sionna 依賴)
* **前端:**
    * React 19+ [cite: 3]
    * TypeScript [cite: 3]
    * Vite [cite: 3, 4]
* **資料庫:**
    * PostgreSQL (建議版本 14+)
    * PostGIS 擴充套件 (建議版本 3+)
* **容器化:**
    * Docker
    * Docker Compose

## 專案結構
.
├── backend/                # 後端 FastAPI 應用程式
│   ├── app/                # 主要應用程式套件
│   │   ├── core/           # 核心設定 (config.py)
│   │   ├── db/             # 資料庫 (base.py, lifespan.py, models.py)
│   │   ├── api/            # API (deps.py, v1/)
│   │   ├── services/       # 服務邏輯 (sionna_simulation.py)
│   │   └── main.py         # FastAPI App 入口
│   ├── Dockerfile          # 後端 Dockerfile
│   ├── requirements.txt    # Python 依賴
│   └── .env                # 環境變數檔案 (需自行建立)
├── frontend/               # 前端 React 應用程式
│   ├── public/
│   ├── src/                # React 原始碼
│   ├── Dockerfile          # 前端 Dockerfile
│   ├── index.html
│   ├── package.json        # Node.js 依賴 
│   ├── tsconfig.json
│   └── vite.config.ts      # Vite 設定 
├── docker-compose.yml      # Docker Compose 設定檔 
└── README.md               # 本文件   

## 環境準備

* **Docker:** 請先安裝 Docker Engine。 ([安裝說明](https://docs.docker.com/engine/install/))
* **Docker Compose:** 請確保已安裝 Docker Compose (通常隨 Docker Desktop 一起安裝，或可單獨安裝)。([安裝說明](https://docs.docker.com/compose/install/))
* **(GPU 支援 - 可選)** 若要使用 GPU 加速：
    * 安裝 NVIDIA 顯示卡驅動程式。
    * 安裝 NVIDIA Container Toolkit ([安裝說明](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)) 以便 Docker 能使用 GPU。

## 安裝與執行

1.  **複製 (Clone) 專案:**
    ```bash
    git clone <您的專案 Git Repo URL>
    cd <專案目錄>
    ```

2.  **設定環境變數:**
    * 在 `backend/` 目錄下，根據 `backend/.env.example` (如果有的話) 或以下說明，建立一個 `.env` 檔案。
    * **必要設定:**
        ```dotenv
        # backend/.env

        # PostgreSQL 資料庫設定 (需與 docker-compose.yml 中的設定一致)
        DATABASE_URL=postgresql+asyncpg://myuser:mypassword@db:5432/myappdb
        POSTGRES_USER=myuser
        POSTGRES_PASSWORD=mypassword
        POSTGRES_DB=myappdb

        # GPU 控制 (可選，依需求設定)
        # CUDA_VISIBLE_DEVICES=0    # 指定使用 GPU 0
        # CUDA_VISIBLE_DEVICES=-1   # 強制使用 CPU
        # CUDA_VISIBLE_DEVICES=     # (預設) 自動偵測可用 GPU
        ```
    * 請將 `myuser`, `mypassword`, `myappdb` 替換為您想使用的實際值。

3.  **建立資料夾與空檔案 (若尚未建立):**
    如果您是從頭開始，可以使用以下指令快速建立後端 `app` 目錄結構：
    ```bash
    # 在專案根目錄執行
    mkdir -p backend/app/core backend/app/db backend/app/api/v1/endpoints backend/app/services && touch backend/app/__init__.py backend/app/main.py backend/app/core/__init__.py backend/app/core/config.py backend/app/db/__init__.py backend/app/db/base.py backend/app/db/lifespan.py backend/app/db/models.py backend/app/api/__init__.py backend/app/api/deps.py backend/app/api/v1/__init__.py backend/app/api/v1/endpoints/__init__.py backend/app/api/v1/endpoints/sionna.py backend/app/api/v1/router.py backend/app/services/__init__.py backend/app/services/sionna_simulation.py
    ```

4.  **啟動服務:**
    在專案根目錄（包含 `docker-compose.yml` 的地方）執行：
    ```bash
    # 首次啟動或 Dockerfile/依賴變更時，建議加上 --build
    docker-compose up --build -d
    ```
    * `--build`: 強制重新建構 Docker image。
    * `-d`: 在背景分離模式執行。

5.  **存取應用程式:**
    * **前端:** 打開瀏覽器，訪問 `http://localhost:5173` (根據 `docker-compose.yml` 中的前端端口設定 [cite: 1])。
    * **後端 API 文件:** 訪問 `http://localhost:8000/docs` (根據 `docker-compose.yml` 中的後端端口設定 [cite: 1]) 可查看 Swagger UI 自動產生的 API 文件。
    * **後端根目錄:** 訪問 `http://localhost:8000/`。

## 環境變數說明

* `DATABASE_URL`: 後端 FastAPI 應用程式連接資料庫的完整 URL [cite: 1]。
* `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: 用於初始化 PostgreSQL 資料庫容器，並供 `DATABASE_URL` 使用 [cite: 1]。
* `CUDA_VISIBLE_DEVICES`: 控制後端容器內 TensorFlow/Sionna 可見的 GPU 裝置。`-1` 表示強制 CPU，空字串或指定 ID (如 `0`) 表示使用 GPU [cite: 1, 2]。
* `TF_CPP_MIN_LOG_LEVEL`: 控制 TensorFlow 的日誌級別，`3` 表示只顯示錯誤訊息 [cite: 1]。

## API 端點 (v1)

目前提供的 API 端點皆位於 `/api/v1` 前綴下：

* **`GET /api/v1/sionna/scene-image-original`**: 取得原始的 Sionna 場景 ('etoile') 渲染圖。
* **`GET /api/v1/sionna/scene-image-rt`**: 根據資料庫中 `active=true` 的節點，產生包含路徑追蹤的場景渲染圖。
* **`GET /api/v1/sionna/constellation-diagram`**: 根據資料庫中 `active=true` 的節點，產生 QPSK 星座圖（包含干擾）。

## 資料庫結構

主要的資料庫表格包括 `device`, `transmitter`, `receiver`，用來儲存節點的基本資訊、位置 (PostGIS PointZ)、啟用狀態以及特定類型（發射器/接收器/干擾源）的屬性。詳細結構請參考之前提供的資料庫結構 Markdown 文件或 `backend/app/db/models.py` [cite: 2]。

## 未來規劃

* 在前端實作完整的節點管理介面 (CRUD - Create, Read, Update, Delete)。
* 提供 API 端點讓前端可以新增、修改、刪除及啟用/停用資料庫中的節點。
* 允許使用者透過前端調整模擬參數 (例如 JNR, Eb/N0 等)。
* 加入 API 安全性機制 (認證/授權)。