# 🛠️ Sionna RT 開發者指南

本指南提供給想要為 Sionna RT 無線電模擬系統做出貢獻或進行深度開發的開發者。

## 📋 目錄

-   [開發環境設定](#開發環境設定)
-   [專案結構](#專案結構)
-   [技術架構詳解](#技術架構詳解)
-   [開發工作流程](#開發工作流程)
-   [代碼規範](#代碼規範)
-   [測試指南](#測試指南)
-   [調試技巧](#調試技巧)
-   [效能優化](#效能優化)
-   [部署指南](#部署指南)
-   [常見問題](#常見問題)

## 🔧 開發環境設定

### 前置需求

1. **系統要求**

    - Linux Ubuntu 20.04+ 或 macOS 10.15+
    - Docker 20.10+ 和 Docker Compose 2.0+
    - Python 3.9+ (如果需要本地開發)
    - Node.js 18+ (如果需要本地開發)
    - Git 2.30+

2. **推薦工具**
    - VS Code 或 PyCharm
    - Postman 或 Insomnia (API 測試)
    - DB Browser for SQLite (資料庫查看)
    - Chrome DevTools

### 快速開始

```bash
# 1. 克隆專案
git clone <repository-url>
cd web-sionna

# 2. 複製環境配置
cp env.example .env

# 3. 使用自動化設置腳本
./setup.sh

# 4. 驗證安裝
make health
```

### 本地開發設定

如果您想在本地運行部分服務進行開發：

```bash
# 僅啟動資料庫
docker compose up -d postgis

# 設定後端本地開發環境
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# 設定前端本地開發環境
cd frontend
npm install
npm run dev
```

## 📂 專案結構

```
web-sionna/
├── 📁 backend/                    # FastAPI 後端應用
│   ├── 📁 app/                    # 主應用目錄
│   │   ├── 📁 api/                # API 路由
│   │   │   ├── 📁 v1/             # API v1 版本
│   │   │   │   ├── devices.py     # 設備管理 API
│   │   │   │   ├── simulations.py # 模擬 API
│   │   │   │   └── sionna.py      # Sionna 特定 API
│   │   │   └── deps.py            # 依賴注入
│   │   ├── 📁 core/               # 核心配置
│   │   │   ├── config.py          # 應用配置
│   │   │   ├── database.py        # 資料庫配置
│   │   │   └── lifespan.py        # 應用生命週期
│   │   ├── 📁 models/             # 資料模型
│   │   │   ├── device.py          # 設備模型
│   │   │   └── simulation.py      # 模擬模型
│   │   ├── 📁 services/           # 業務邏輯服務
│   │   │   ├── device_service.py  # 設備服務
│   │   │   ├── simulation_service.py # 模擬服務
│   │   │   └── sionna_service.py  # Sionna 服務
│   │   ├── 📁 static/             # 靜態檔案
│   │   │   ├── 📁 scene/          # 場景檔案
│   │   │   └── 📁 rendered_images/ # 渲染結果
│   │   └── main.py                # 應用入口點
│   ├── requirements.txt           # Python 依賴
│   └── Dockerfile                 # Docker 建構檔
├── 📁 frontend/                   # React 前端應用
│   ├── 📁 src/                    # 前端源碼
│   │   ├── 📁 components/         # React 元件
│   │   │   ├── 📁 device/         # 設備相關元件
│   │   │   ├── 📁 simulation/     # 模擬相關元件
│   │   │   └── 📁 scene/          # 場景相關元件
│   │   ├── 📁 hooks/              # 自定義 React Hooks
│   │   ├── 📁 services/           # API 服務
│   │   ├── 📁 types/              # TypeScript 類型定義
│   │   ├── 📁 utils/              # 工具函數
│   │   └── 📁 config/             # 前端配置
│   ├── package.json               # Node.js 依賴
│   ├── vite.config.ts             # Vite 配置
│   └── Dockerfile                 # Docker 建構檔
├── docker-compose.yml             # Docker Compose 配置
├── Makefile                       # 開發指令
├── setup.sh                       # 自動化設置腳本
├── env.example                    # 環境變數範例
└── README.md                      # 專案說明
```

## 🏗️ 技術架構詳解

### 後端架構 (FastAPI)

```
FastAPI 應用
├── 路由層 (API Routes)
│   ├── 驗證和授權
│   ├── 請求驗證
│   └── 響應序列化
├── 服務層 (Services)
│   ├── 業務邏輯處理
│   ├── 數據轉換
│   └── 外部服務整合
├── 模型層 (Models)
│   ├── SQLModel 定義
│   ├── Pydantic 驗證
│   └── 資料庫映射
└── 基礎設施層
    ├── 資料庫連接
    ├── 日誌系統
    └── 配置管理
```

### 前端架構 (React + TypeScript)

```
React 應用
├── 元件層 (Components)
│   ├── 頁面元件 (Pages)
│   ├── 功能元件 (Features)
│   └── 基礎元件 (Base)
├── 狀態管理
│   ├── React Hooks
│   ├── Context API
│   └── 本地狀態
├── 服務層 (Services)
│   ├── API 呼叫
│   ├── 資料轉換
│   └── 錯誤處理
└── 工具層 (Utils)
    ├── 類型定義
    ├── 常數定義
    └── 輔助函數
```

### Sionna 模擬引擎整合

```
Sionna RT 整合
├── 場景管理
│   ├── 3D 模型載入 (.glb)
│   ├── 場景配置 (.xml)
│   └── 材質定義
├── 設備配置
│   ├── 發射器設定
│   ├── 接收器設定
│   └── 通道參數
├── 模擬執行
│   ├── 射線追蹤計算
│   ├── 通道建模
│   └── 結果生成
└── 結果視覺化
    ├── SINR 地圖
    ├── CFR 圖表
    └── 3D 渲染
```

## 🔄 開發工作流程

### 1. 功能開發流程

```bash
# 1. 創建功能分支
git checkout -b feature/new-awesome-feature

# 2. 啟動開發環境
make dev

# 3. 開發和測試
make shell-backend  # 進入後端容器
make shell-frontend # 進入前端容器

# 4. 運行測試
make test-backend
make test-frontend

# 5. 代碼品質檢查
make lint-frontend
# 後端 linting (如果配置)

# 6. 提交和推送
git add .
git commit -m "feat: add awesome new feature"
git push origin feature/new-awesome-feature
```

### 2. 調試工作流程

```bash
# 查看即時日誌
make logs-follow

# 檢查特定服務
make logs-backend
make logs-frontend
make logs-db

# 進入容器調試
make shell-backend
# 然後在容器內：
python -c "import your_module; your_module.debug_function()"

# 檢查資料庫狀態
make psql
# 在 PostgreSQL 中執行查詢
```

### 3. 測試工作流程

```bash
# 後端測試
make shell-backend
pytest tests/ -v

# 前端測試
make shell-frontend
npm test

# API 整合測試
make api-test

# 端到端測試 (如果配置)
npm run e2e
```

## 📝 代碼規範

### Python 代碼規範 (後端)

1. **風格指南**

    - 遵循 PEP 8
    - 使用 Black 格式化器
    - 行長度限制：88 字符

2. **命名約定**

    ```python
    # 變數和函數：snake_case
    device_count = 10
    def calculate_sinr_map():
        pass

    # 類名：PascalCase
    class DeviceModel:
        pass

    # 常數：UPPER_SNAKE_CASE
    MAX_DEVICE_COUNT = 100
    ```

3. **文檔字串**
    ```python
    def simulate_channel_response(
        scene_name: str,
        devices: List[Device]
    ) -> ChannelResponse:
        """
        模擬給定場景和設備配置的通道響應。

        Args:
            scene_name: 場景名稱 (如 'nycu', 'lotus')
            devices: 設備列表

        Returns:
            通道響應結果

        Raises:
            SimulationError: 當模擬參數無效時
        """
        pass
    ```

### TypeScript 代碼規範 (前端)

1. **風格指南**

    - 遵循 ESLint 規則
    - 使用 Prettier 格式化器
    - 優先使用函數元件和 Hooks

2. **命名約定**

    ```typescript
    // 變數和函數：camelCase
    const deviceCount = 10
    const calculateSinrMap = () => {}

    // 元件和類型：PascalCase
    interface DeviceProps {
        id: string
    }

    const DeviceComponent: React.FC<DeviceProps> = ({ id }) => {
        return <div>{id}</div>
    }

    // 常數：UPPER_SNAKE_CASE
    const MAX_DEVICE_COUNT = 100
    ```

3. **類型定義**

    ```typescript
    // 詳細的介面定義
    interface Device {
        id: string
        type: 'desired' | 'receiver' | 'jammer'
        position: {
            x: number
            y: number
            z: number
        }
        parameters: DeviceParameters
    }

    // 使用聯合類型
    type SimulationStatus = 'idle' | 'running' | 'completed' | 'error'
    ```

## 🧪 測試指南

### 後端測試

1. **單元測試**

    ```python
    # tests/test_device_service.py
    import pytest
    from app.services.device_service import DeviceService

    @pytest.fixture
    def device_service():
        return DeviceService()

    def test_create_device(device_service):
        device_data = {
            "type": "desired",
            "position": {"x": 0, "y": 0, "z": 1.5}
        }
        device = device_service.create_device(device_data)
        assert device.type == "desired"
    ```

2. **整合測試**

    ```python
    # tests/test_api.py
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    def test_get_devices():
        response = client.get("/api/v1/devices/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    ```

### 前端測試

1. **元件測試**

    ```typescript
    // src/components/__tests__/DeviceList.test.tsx
    import { render, screen } from '@testing-library/react'
    import DeviceList from '../DeviceList'

    test('renders device list', () => {
        const devices = [
            { id: '1', type: 'desired', position: { x: 0, y: 0, z: 1.5 } },
        ]
        render(<DeviceList devices={devices} />)
        expect(screen.getByText('desired')).toBeInTheDocument()
    })
    ```

2. **Hook 測試**

    ```typescript
    // src/hooks/__tests__/useDevices.test.ts
    import { renderHook, waitFor } from '@testing-library/react'
    import { useDevices } from '../useDevices'

    test('fetches devices', async () => {
        const { result } = renderHook(() => useDevices())

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.devices).toBeDefined()
    })
    ```

## 🐛 調試技巧

### 後端調試

1. **日誌調試**

    ```python
    import logging

    logger = logging.getLogger(__name__)

    def complex_calculation():
        logger.debug("開始複雜計算")
        result = do_calculation()
        logger.info(f"計算結果: {result}")
        return result
    ```

2. **pdb 調試**

    ```python
    import pdb

    def problematic_function():
        data = get_data()
        pdb.set_trace()  # 設置斷點
        processed_data = process(data)
        return processed_data
    ```

### 前端調試

1. **瀏覽器 DevTools**

    ```typescript
    const debugData = {
        devices,
        selectedDevice,
        simulationStatus,
    }

    console.log('Debug info:', debugData)
    console.table(devices) // 表格形式顯示陣列
    ```

2. **React DevTools**
    - 安裝 React Developer Tools 瀏覽器擴展
    - 使用 Profiler 分析效能
    - 檢查元件狀態和 props

### 資料庫調試

```sql
-- 檢查設備數據
SELECT * FROM devices ORDER BY created_at DESC LIMIT 10;

-- 分析查詢效能
EXPLAIN ANALYZE SELECT * FROM devices WHERE type = 'desired';

-- 檢查資料庫連接
SELECT count(*) FROM pg_stat_activity;
```

## ⚡ 效能優化

### 後端優化

1. **資料庫查詢優化**

    ```python
    # 使用適當的索引
    from sqlalchemy import Index

    Index('idx_device_type', Device.type)
    Index('idx_device_position', Device.position_x, Device.position_y)

    # 避免 N+1 查詢
    devices = session.query(Device).options(
        joinedload(Device.simulations)
    ).all()
    ```

2. **快取策略**

    ```python
    from functools import lru_cache

    @lru_cache(maxsize=128)
    def expensive_calculation(scene_name: str, device_count: int):
        # 昂貴的計算
        return result
    ```

### 前端優化

1. **React 優化**

    ```typescript
    // 使用 memo 防止不必要的重渲染
    const DeviceComponent = React.memo(({ device }) => {
        return <div>{device.id}</div>
    })

    // 使用 useMemo 緩存昂貴計算
    const expensiveValue = useMemo(() => {
        return devices.filter((d) => d.type === 'desired').length
    }, [devices])

    // 使用 useCallback 穩定函數引用
    const handleDeviceClick = useCallback((id: string) => {
        setSelectedDevice(id)
    }, [])
    ```

2. **程式碼分割**

    ```typescript
    // 動態導入重型元件
    const HeavyComponent = lazy(() => import('./HeavyComponent'))

    function App() {
        return (
            <Suspense fallback={<Loading />}>
                <HeavyComponent />
            </Suspense>
        )
    }
    ```

## 🚀 部署指南

### 開發部署

```bash
# 標準開發部署
make up

# 帶日誌監控的部署
make up && make logs-follow
```

### 生產部署

```bash
# 建構生產映像
make build-prod

# 部署前檢查
make deploy-check

# 生產環境變數配置
cp env.example .env.production
# 編輯 .env.production 配置生產設定

# 使用生產配置部署
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 監控和維護

```bash
# 檢查系統資源
make system-info

# 備份資料庫
make db-backup

# 清理舊資源
make docker-clean
```

## ❓ 常見問題

### Q: 容器啟動失敗怎麼辦？

```bash
# 1. 檢查日誌
make logs

# 2. 檢查端口占用
make ports

# 3. 清理並重啟
make clean
make up
```

### Q: 前端無法連接後端？

1. 檢查後端是否正常運行：`make health`
2. 檢查 CORS 設定
3. 確認前端 API 端點配置正確

### Q: Sionna 模擬報錯？

1. 檢查場景檔案是否存在
2. 驗證設備參數配置
3. 檢查 GPU/OpenGL 支援

### Q: 資料庫連接問題？

```bash
# 檢查資料庫狀態
make db-status

# 重置資料庫
make db-reset

# 手動連接測試
make psql
```

## 📖 相關資源

-   [Sionna 官方文檔](https://nvlabs.github.io/sionna/)
-   [FastAPI 文檔](https://fastapi.tiangolo.com/)
-   [React 文檔](https://react.dev/)
-   [Three.js 文檔](https://threejs.org/docs/)
-   [Docker 文檔](https://docs.docker.com/)

---

**開發愉快！** 🎉

如有問題，請參考 [README.md](README.md) 或建立 GitHub Issue。
