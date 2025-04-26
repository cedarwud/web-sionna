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
    // 存儲對象 URL 以便清理
    const [prevImageUrl, setPrevImageUrl] = useState<string | null>(null)

    // 封裝 fetchImage 函數為可獨立調用的函數
    const fetchImage = async () => {
        setIsLoading(true)
        setError(null)
        setUsingFallback(false)
        console.log(`正在從 ${CONSTELLATION_ENDPOINT} 獲取星座圖...`)

        // 清理上一個對象 URL（如果存在）
        if (prevImageUrl) {
            URL.revokeObjectURL(prevImageUrl)
            setPrevImageUrl(null)
            console.log('Revoked previous object URL:', prevImageUrl)
        }

        try {
            // 使用 fetch API 進行請求，添加超時處理
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 15000) // 增加到15秒超時

            const endpointWithCacheBuster = `${CONSTELLATION_ENDPOINT}?t=${new Date().getTime()}`
            const response = await fetch(endpointWithCacheBuster, {
                signal: controller.signal,
                // 添加額外請求選項，避免快取問題
                cache: 'no-cache',
                headers: {
                    Pragma: 'no-cache',
                    'Cache-Control': 'no-cache',
                },
            })
            clearTimeout(timeoutId)

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`)
            }

            // 使用嘗試-捕獲塊來處理響應內容
            try {
                // 獲取 blob 而不是使用直接 URL
                const imageBlob = await response.blob()

                // 檢查 blob 大小
                if (imageBlob.size === 0) {
                    throw new Error('接收到空的圖像 blob')
                }

                // 創建 blob URL
                const newImageUrl = URL.createObjectURL(imageBlob)
                console.log('Created constellation diagram URL:', newImageUrl)
                setImageUrl(newImageUrl)
                setPrevImageUrl(newImageUrl)

                // 重置重試計數和模式
                setRetryCount(0)
                setManualRetryMode(false)
            } catch (blobError) {
                console.error('Error processing image blob:', blobError)
                throw new Error(
                    `處理星座圖時出錯: ${
                        blobError instanceof Error
                            ? blobError.message
                            : String(blobError)
                    }`
                )
            }
        } catch (error) {
            console.error('星座圖載入失敗:', error)

            // 嘗試使用備用圖像 - 通過 fetch API 載入
            try {
                console.log(
                    'Trying to fetch fallback constellation image as blob...'
                )
                const fallbackResponse = await fetch(FALLBACK_IMAGE_PATH, {
                    cache: 'no-cache',
                    headers: {
                        Pragma: 'no-cache',
                        'Cache-Control': 'no-cache',
                    },
                })

                if (fallbackResponse.ok) {
                    const fallbackBlob = await fallbackResponse.blob()
                    if (fallbackBlob.size > 0) {
                        const fallbackUrl = URL.createObjectURL(fallbackBlob)
                        setImageUrl(fallbackUrl)
                        setPrevImageUrl(fallbackUrl)
                        setUsingFallback(true)
                        setError(
                            `使用備用星座圖: ${
                                error instanceof Error
                                    ? error.message
                                    : '未知錯誤'
                            }`
                        )
                        console.log(
                            'Successfully loaded fallback constellation image as blob'
                        )
                    } else {
                        throw new Error('備用星座圖 blob 為空')
                    }
                } else {
                    throw new Error(
                        `備用星座圖請求失敗: ${fallbackResponse.status}`
                    )
                }
            } catch (fallbackError) {
                console.error(
                    'Fallback constellation image loading failed:',
                    fallbackError
                )
                // 最後的備用：使用直接 URL
                setImageUrl(FALLBACK_IMAGE_PATH)
                setUsingFallback(true)
                setError(
                    `星座圖載入失敗: ${
                        error instanceof Error ? error.message : '未知錯誤'
                    }`
                )
            }

            // 增加重試計數
            setRetryCount((prev) => prev + 1)

            // 如果重試超過3次，進入手動重試模式
            if (retryCount >= 2) {
                setManualRetryMode(true)
            } else {
                // 否則自動重試一次，但延長間隔
                console.log(`自動重試 (${retryCount + 1}/3)...`)
                // 設定較長的重試間隔
                setTimeout(() => {
                    fetchImage()
                }, 5000) // 增加到5秒
            }
        } finally {
            setIsLoading(false)
        }
    }

    // 主效果 - 初始載入
    useEffect(() => {
        fetchImage()
        // 清理工作
        return () => {
            if (prevImageUrl) {
                URL.revokeObjectURL(prevImageUrl)
                console.log(
                    'Cleaned up constellation object URL on unmount:',
                    prevImageUrl
                )
            }
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
            // 嘗試使用備用圖像 (這是 img 元素的錯誤處理，可能是 blob URL 有問題)
            console.log('常規星座圖失敗，嘗試備用圖:', FALLBACK_IMAGE_PATH)
            setImageUrl(FALLBACK_IMAGE_PATH)
            setUsingFallback(true)
            setError(`使用最後一次成功的星座圖 (圖像渲染失敗)`)
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
                    key={imageUrl} // 使用 key 確保 URL 變化時 img 元素刷新
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
