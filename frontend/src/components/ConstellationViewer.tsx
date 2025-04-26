// src/components/ConstellationViewer.tsx
import React, { useState, useEffect } from 'react'

// 指向新的後端 API 端點
const CONSTELLATION_ENDPOINT = '/api/v1/sionna/constellation-diagram' // 使用相對路徑，透過 Vite 代理
// 定義靜態路徑指向後端存儲的最後一次成功渲染的圖像
const FALLBACK_IMAGE_PATH = '/rendered_images/constellation_diagram.png'

const ConstellationViewer: React.FC = () => {
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [usingFallback, setUsingFallback] = useState<boolean>(false)
    // 新增重試機制相關狀態
    const [retryCount, setRetryCount] = useState<number>(0)
    const [manualRetryMode, setManualRetryMode] = useState<boolean>(false)

    // 封裝 fetchImage 函數為可獨立調用的函數
    const fetchImage = async () => {
        setIsLoading(true)
        setError(null)
        setUsingFallback(false)
        console.log(`正在從 ${CONSTELLATION_ENDPOINT} 獲取星座圖...`)

        try {
            // 使用 fetch API 進行請求，添加超時處理
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 10000) // 10秒超時

            const endpointWithCacheBuster = `${CONSTELLATION_ENDPOINT}?t=${new Date().getTime()}`
            const response = await fetch(endpointWithCacheBuster, {
                signal: controller.signal,
            })
            clearTimeout(timeoutId)

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`)
            }

            // 直接設置圖像URL
            setImageUrl(endpointWithCacheBuster)
            // 重置重試計數和模式
            setRetryCount(0)
            setManualRetryMode(false)
        } catch (error) {
            console.error('星座圖載入失敗:', error)
            console.log('使用備用星座圖:', FALLBACK_IMAGE_PATH)

            // 使用備用圖像
            setImageUrl(FALLBACK_IMAGE_PATH)
            setUsingFallback(true)

            // 設置更有幫助的錯誤訊息
            setError(
                `星座圖載入失敗: ${
                    error instanceof Error ? error.message : '未知錯誤'
                }`
            )

            // 增加重試計數
            setRetryCount((prev) => prev + 1)

            // 如果重試超過3次，進入手動重試模式
            if (retryCount >= 2) {
                setManualRetryMode(true)
            } else {
                // 否則自動重試一次
                console.log(`自動重試 (${retryCount + 1}/3)...`)
                // 設定較短的重試間隔
                setTimeout(() => {
                    fetchImage()
                }, 3000)
            }
        } finally {
            setIsLoading(false)
        }
    }

    // 主效果 - 初始載入
    useEffect(() => {
        fetchImage()
        // 清理工作（如果需要）
        return () => {
            // 這裡可以添加需要的清理邏輯
        }
    }, []) // 空依賴陣列，僅在掛載時執行一次

    // 處理手動重試
    const handleRetry = () => {
        console.log('手動重試載入星座圖...')
        fetchImage()
    }

    const handleImageLoad = () => {
        console.log('星座圖載入成功')
        setIsLoading(false)
        if (!usingFallback) {
            setError(null) // 只有非備用圖像時才清除錯誤
        }
    }

    const handleImageError = (
        e: React.SyntheticEvent<HTMLImageElement, Event>
    ) => {
        console.error('星座圖載入失敗')
        console.error('Error event:', e)

        // 如果是備用圖像也載入失敗，那麼顯示錯誤訊息
        if (usingFallback || imageUrl === FALLBACK_IMAGE_PATH) {
            setError(`備用星座圖也無法載入，請檢查網絡連接`)
        } else {
            // 嘗試使用備用圖像
            console.log('常規星座圖失敗，嘗試備用圖:', FALLBACK_IMAGE_PATH)
            setImageUrl(FALLBACK_IMAGE_PATH)
            setUsingFallback(true)
            setError(`使用最後一次成功的星座圖 (無法連接後端服務)`)
        }

        setIsLoading(false) // 確保 loading 結束
    }

    return (
        <div>
            <h2>Constellation Diagram</h2>
            {isLoading && <p>正在載入星座圖...</p>}
            {error && (
                <div
                    style={{
                        color: usingFallback ? 'orange' : 'red',
                        marginBottom: '10px',
                    }}
                >
                    <p>狀態: {error}</p>
                    {manualRetryMode && (
                        <button
                            onClick={handleRetry}
                            style={{
                                padding: '5px 10px',
                                marginTop: '5px',
                                background: '#4CAF50',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                            }}
                        >
                            重試載入
                        </button>
                    )}
                </div>
            )}
            {imageUrl && (
                <img
                    src={imageUrl}
                    alt="Constellation Diagram"
                    onLoad={handleImageLoad}
                    onError={handleImageError}
                    style={{
                        width: '100%',
                        height: 'auto',
                        border: '1px solid #ccc',
                    }}
                />
            )}
        </div>
    )
}

export default ConstellationViewer
