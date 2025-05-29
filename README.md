# Sionna RT 無線電模擬系統

一個基於 [Sionna](https://nvlabs.github.io/sionna/) 的無線電傳播模擬系統，支援多場景 RT (Ray Tracing) 模擬、設備管理和視覺化分析。

## 📋 目錄

-   [功能特色](#功能特色)
-   [系統架構](#系統架構)
-   [技術堆疊](#技術堆疊)
-   [環境需求](#環境需求)
-   [快速開始](#快速開始)
-   [開發指南](#開發指南)
-   [API 文檔](#api-文檔)
-   [場景管理](#場景管理)
-   [故障排除](#故障排除)
-   [貢獻指南](#貢獻指南)

## 🚀 功能特色

### 核心功能

-   **多場景支援**: 支援 NYCU（陽明交通大學）、Lotus（荷花池）、NTPU（臺北大學）、Nanliao（南寮漁港）
-   **設備管理**: 支援基站 (Desired)、接收器 (Receiver)、干擾器 (Jammer) 三種設備類型
-   **即時模擬**: 基於 Sionna RT 的無線電傳播模擬
-   **2D/3D 視覺化**: 提供平面和立體場景視圖

### 模擬功能

-   **SINR 地圖**: 信噪干擾比分布視覺化
-   **CFR 圖**: 通道頻率響應分析
-   **延遲多普勒圖**: 時延-多普勒頻移分析
-   **通道響應圖**: 3D 通道響應可視化

### 使用者介面

-   **拖拽式設備配置**: 直觀的設備位置調整
-   **即時預覽**: 設備變更即時反映在模擬中
-   **響應式設計**: 支援多種螢幕尺寸

## 🏗️ 系統架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Database      │
│   (React)       │◄──►│   (FastAPI)     │◄──►│  (PostgreSQL)   │
│   Port: 5174    │    │   Port: 8889    │    │   Port: 5433    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Vite Dev      │    │ Sionna RT       │    │   PostGIS       │
│   Hot Reload    │    │ 模擬引擎        │    │   地理擴展      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 💻 技術堆疊

### 前端

-   **框架**: React 19 + TypeScript
-   **建構工具**: Vite 6
-   **3D 渲染**: Three.js + React Three Fiber
-   **樣式**: SASS/SCSS
-   **路由**: React Router DOM 6
-   **HTTP 客戶端**: Axios

### 後端

-   **框架**: FastAPI (Python)
-   **ORM**: SQLAlchemy + SQLModel
-   **資料庫驅動**: asyncpg
-   **模擬引擎**: Sionna + Sionna-RT
-   **3D 渲染**: PyRender + Trimesh
-   **圖像處理**: Matplotlib + Pillow

### 資料庫

-   **主資料庫**: PostgreSQL 16
-   **地理擴展**: PostGIS 3.4

### 部署

-   **容器化**: Docker + Docker Compose
-   **反向代理**: Vite 開發代理
-   **網路**: Docker 自定義網路

## 📋 環境需求

### 系統需求

-   **作業系統**: Linux (推薦 Ubuntu 20.04+)
-   **記憶體**: 最少 8GB RAM (推薦 16GB+)
-   **硬碟**: 最少 10GB 可用空間
-   **顯示卡**: 支援 OpenGL 3.3+ (推薦 NVIDIA GPU)

### 軟體需求

-   **Docker**: 20.10+
-   **Docker Compose**: 2.0+
-   **Make**: GNU Make 4.0+ (可選)

## 🚀 快速開始

### 1. 克隆專案

```bash
git clone <repository-url>
cd web-sionna
```

### 2. 環境配置

創建 `.env` 文件：

```bash
# 資料庫配置
POSTGRES_USER=sionna_user
POSTGRES_PASSWORD=sionna_password
POSTGRES_DB=sionna_db
POSTGRES_PORT=5433

# 應用配置
BACKEND_PORT=8889
FRONTEND_PORT=5174
```

### 3. 快速啟動

```bash
# 使用 Make（推薦）
make up

# 或使用 Docker Compose
docker compose up -d
```

### 4. 訪問應用

-   **前端**: http://localhost:5174
-   **後端 API**: http://localhost:8889
-   **API 文檔**: http://localhost:8889/docs

### 5. 驗證安裝

```bash
# 檢查服務狀態
make status

# 查看日誌
make logs
```

## 🛠️ 開發指南

### 開發環境啟動

```bash
# 啟動所有服務
make dev

# 單獨重啟後端
make restart-backend

# 單獨重啟前端
make restart-frontend
```

### 程式碼開發

```bash
# 進入後端容器
make shell-backend

# 進入前端容器
make shell-frontend

# 進入資料庫
make shell-db
```

### 測試與品質檢查

```bash
# 執行前端 linting
make lint-frontend

# 執行後端測試
make test-backend

# 建構生產版本
make build-prod
```

### 資料庫管理

```bash
# 重置資料庫
make db-reset

# 備份資料庫
make db-backup

# 還原資料庫
make db-restore
```

## 📚 API 文檔

### 核心端點

#### 設備管理

-   `GET /api/v1/devices/` - 獲取所有設備
-   `POST /api/v1/devices/` - 創建新設備
-   `PUT /api/v1/devices/{id}` - 更新設備
-   `DELETE /api/v1/devices/{id}` - 刪除設備

#### 模擬功能

-   `GET /api/v1/simulations/scene-image` - 獲取場景圖像
-   `GET /api/v1/simulations/sinr-map` - 生成 SINR 地圖
-   `GET /api/v1/simulations/cfr-plot` - 生成 CFR 圖
-   `GET /api/v1/simulations/doppler-plots` - 生成延遲多普勒圖
-   `GET /api/v1/simulations/channel-response` - 生成通道響應圖

#### 場景管理

-   `GET /api/v1/simulations/scenes` - 獲取可用場景列表
-   `GET /api/v1/simulations/scene/{name}` - 獲取場景資訊
-   `GET /api/v1/sionna/models/{model}` - 獲取 3D 模型

### API 測試

```bash
# 獲取設備列表
curl http://localhost:8889/api/v1/devices/

# 生成 SINR 地圖
curl "http://localhost:8889/api/v1/simulations/sinr-map?scene=nycu"

# 檢查 API 健康狀態
curl http://localhost:8889/ping
```

## 🏢 場景管理

### 支援場景

| 場景代碼  | 顯示名稱     | 描述         |
| --------- | ------------ | ------------ |
| `nycu`    | 陽明交通大學 | 大學校園環境 |
| `lotus`   | 荷花池       | 自然環境場景 |
| `ntpu`    | 臺北大學     | 都市校園環境 |
| `nanliao` | 南寮漁港     | 海岸環境場景 |

### 場景檔案結構

```
backend/app/static/scene/{SCENE_NAME}/
├── {SCENE_NAME}.glb          # 3D 模型檔案
├── {SCENE_NAME}.xml          # Sionna 場景配置
├── textures/                 # 紋理檔案目錄
│   └── EXPORT_GOOGLE_SAT_WM.png
└── meshes/                   # 網格檔案目錄
```

### 新增場景

1. 在 `backend/app/static/scene/` 目錄下創建場景資料夾
2. 添加對應的 GLB 模型和 XML 配置檔案
3. 更新 `frontend/src/utils/sceneUtils.ts` 中的場景映射
4. 重新啟動服務

## 🛠️ 故障排除

### 常見問題

#### 1. 服務啟動失敗

```bash
# 檢查 Docker 狀態
docker --version
docker compose --version

# 檢查端口占用
sudo netstat -tlpn | grep -E "(5174|8889|5433)"

# 清理並重新啟動
make clean
make up
```

#### 2. 資料庫連接問題

```bash
# 檢查資料庫狀態
make db-status

# 重置資料庫
make db-reset

# 查看資料庫日誌
docker compose logs postgis
```

#### 3. 前端熱重載問題

```bash
# 重啟前端服務
make restart-frontend

# 檢查 Vite 配置
docker compose logs frontend
```

#### 4. GPU 渲染問題

```bash
# 檢查 OpenGL 支援
docker compose exec backend python -c "import pyrender; print('PyRender OK')"

# 檢查 CUDA 可用性
docker compose exec backend python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

### 日誌檢查

```bash
# 查看所有服務日誌
make logs

# 查看特定服務日誌
make logs-backend
make logs-frontend
make logs-db

# 跟蹤即時日誌
make logs-follow
```

### 效能優化

```bash
# 清理未使用的 Docker 資源
make docker-clean

# 重建容器映像
make rebuild

# 檢查系統資源使用
make system-info
```

## 🔧 Make 指令參考

查看所有可用指令：

```bash
make help
```

主要指令：

-   `make up` - 啟動所有服務
-   `make down` - 停止所有服務
-   `make restart` - 重啟所有服務
-   `make clean` - 清理所有資源
-   `make logs` - 查看服務日誌
-   `make shell-backend` - 進入後端容器
-   `make db-reset` - 重置資料庫

更多詳細指令請參考 [Makefile](Makefile)。
