// src/App.tsx
import React, { useState } from 'react'
import SceneViewer from './components/SceneViewer'
import ConstellationViewer from './components/ConstellationViewer'
import './App.css'

type SceneView = 'original' | 'rt' // 'rt' 表示帶路徑

function App() {
    const [sceneViewType, setSceneViewType] = useState<SceneView>('original')

    // 按鈕點擊處理函數：切換視圖類型
    const handleToggleSceneView = () => {
        setSceneViewType((prevType) =>
            prevType === 'original' ? 'rt' : 'original'
        )
    }

    // 根據當前視圖類型決定按鈕文字
    const buttonText =
        sceneViewType === 'original' ? '顯示路徑 (RT)' : '顯示原始場景'

    return (
        <div className="App">
            <header className="App-header">
                <h1>FastAPI + React + Sionna RT 範例</h1>
                {/* 單一的切換按鈕 */}
                <div style={{ margin: '10px 0' }}>
                    <button onClick={handleToggleSceneView}>
                        {buttonText}
                    </button>
                </div>
            </header>
            <main
                style={{
                    display: 'flex',
                    flexDirection: 'row',
                    gap: '20px',
                    flexWrap: 'wrap',
                }}
            >
                <div style={{ flex: 1, minWidth: '400px' }}>
                    {/* SceneViewer 接收 viewType prop 保持不變 */}
                    <SceneViewer viewType={sceneViewType} />
                </div>
                <div style={{ flex: 1, minWidth: '400px' }}>
                    <ConstellationViewer />
                </div>
            </main>
        </div>
    )
}

export default App
