// src/components/ConstellationViewer.tsx
import React, { useState, useEffect, useCallback, useRef } from 'react'

// 指向新的後端 API 端點
const CONSTELLATION_ENDPOINT = '/api/v1/sionna/constellation-diagram' // 使用相對路徑，透過 Vite 代理
// 定義靜態路徑指向後端存儲的最後一次成功渲染的圖像
const FALLBACK_IMAGE_PATH = '/rendered_images/constellation_diagram.png'
// 增加請求間隔時間
const RETRY_INTERVAL = 10000 // 10秒
// 防止重複請求標誌
const MAX_RETRIES = 2 // 降低最大重試次數
// 增加初始延遲
const INITIAL_LOAD_DELAY = 2000 // 2秒，讓其他請求先完成

// 新增：嘗試直接使用備用圖像選項，避免不必要的API請求
const USE_DIRECT_FALLBACK = true

const ConstellationViewer: React.FC = () => {
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [usingFallback, setUsingFallback] = useState<boolean>(false)
    // 新增重試機制相關狀態
    const [retryCount, setRetryCount] = useState<number>(0)
    const [manualRetryMode, setManualRetryMode] = useState<boolean>(false)
    // 使用 useRef 替代 useState 來存儲對象 URL
    const prevImageUrlRef = useRef<string | null>(null)
    // 增加一個標誌來防止重複請求
    const isFetchingRef = useRef<boolean>(false)

    // 存儲請求的控制器引用
    const controllerRef = useRef<AbortController | null>(null)

    // 直接使用備用圖像，避免API請求
    const loadFallbackDirectly = useCallback(async (): Promise<boolean> => {
        console.log('直接載入備用圖像...')
        setIsLoading(true)

        try {
            // 清理現有的URL對象
            if (prevImageUrlRef.current) {
                URL.revokeObjectURL(prevImageUrlRef.current)
                prevImageUrlRef.current = null
            }

            const fallbackResponse = await fetch(FALLBACK_IMAGE_PATH, {
                cache: 'no-cache',
                headers: {
                    Pragma: 'no-cache',
                    'Cache-Control': 'no-cache',
                },
            })

            if (!fallbackResponse.ok) {
                throw new Error(`備用圖像請求失敗: ${fallbackResponse.status}`)
            }

            const fallbackBlob = await fallbackResponse.blob()
            if (fallbackBlob.size === 0) {
                throw new Error('備用圖像為空')
            }

            const fallbackUrl = URL.createObjectURL(fallbackBlob)
            setImageUrl(fallbackUrl)
            prevImageUrlRef.current = fallbackUrl
            setUsingFallback(true)
            setIsLoading(false)
            return true
        } catch (error) {
            console.error('載入備用圖像失敗:', error)
            setIsLoading(false)
            return false
        }
    }, [])

    // 封裝 fetchImage 函數，接收 AbortSignal
    const fetchImage = useCallback(
        async (signal: AbortSignal) => {
            // 防止重複請求
            if (isFetchingRef.current) {
                console.log('已有請求進行中，忽略此次請求')
                return
            }

            if (USE_DIRECT_FALLBACK && retryCount === 0) {
                console.log('嘗試直接載入備用圖像...')
                const fallbackLoaded = await loadFallbackDirectly()
                if (fallbackLoaded) {
                    console.log('備用圖像載入成功，跳過API請求')
                    isFetchingRef.current = false
                    return
                } else {
                    console.log('備用圖像載入失敗，繼續嘗試 API...')
                    setError(null)
                }
            }

            isFetchingRef.current = true
            setIsLoading(true)
            setError(null)
            setUsingFallback(false)
            console.log(`正在從 ${CONSTELLATION_ENDPOINT} 獲取星座圖...`)

            // 清理上一個對象 URL（如果存在）
            if (prevImageUrlRef.current) {
                URL.revokeObjectURL(prevImageUrlRef.current)
                console.log(
                    'Revoked previous object URL:',
                    prevImageUrlRef.current
                )
                prevImageUrlRef.current = null
            }

            let timeoutId: number | null = null

            try {
                // 設置超時計時器
                timeoutId = window.setTimeout(() => {
                    console.warn(
                        `Fetch constellation request timed out after 15s for ${CONSTELLATION_ENDPOINT}`
                    )
                    // 超時時中止請求
                    if (controllerRef.current) {
                        controllerRef.current.abort()
                    }
                }, 15000)

                const endpointWithCacheBuster = `${CONSTELLATION_ENDPOINT}?t=${new Date().getTime()}`
                const response = await fetch(endpointWithCacheBuster, {
                    signal,
                    // 添加額外請求選項，避免快取問題
                    cache: 'no-cache',
                    headers: {
                        Pragma: 'no-cache',
                        'Cache-Control': 'no-cache',
                    },
                })

                // Clear timeout if fetch completes or fails (not aborted)
                if (timeoutId !== null) window.clearTimeout(timeoutId)

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
                    console.log(
                        'Created constellation diagram URL:',
                        newImageUrl
                    )
                    setImageUrl(newImageUrl)
                    prevImageUrlRef.current = newImageUrl

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
                // Clear timeout if aborted
                if (timeoutId !== null) window.clearTimeout(timeoutId)

                // Only handle error if it's not an AbortError
                if ((error as Error).name !== 'AbortError') {
                    console.error('星座圖載入失敗:', error)

                    // 如果設置為直接使用備用圖像，則跳過API請求
                    if (USE_DIRECT_FALLBACK && retryCount === 0) {
                        console.log('API 請求失敗，嘗試最後載入靜態備用圖...')
                        const fallbackSuccess = await loadFallbackDirectly()
                        if (fallbackSuccess) {
                            setError(
                                `API 請求失敗，已載入備用星座圖: ${
                                    error instanceof Error
                                        ? error.message
                                        : '未知錯誤'
                                }`
                            )
                        } else {
                            // 如果連備用圖都載入失敗
                            setError(
                                `API 和備用星座圖均載入失敗: ${
                                    error instanceof Error
                                        ? error.message
                                        : '未知錯誤'
                                }`
                            )
                            // 最後手段，嘗試設置靜態路徑，儘管它可能也會失敗
                            setImageUrl(FALLBACK_IMAGE_PATH)
                            setUsingFallback(true)
                        }
                    } else {
                        // 直接使用備用圖像 - 改为调用 loadFallbackDirectly，如果失敗，則設置錯誤狀態
                        console.log('API 請求失敗，嘗試最後載入靜態備用圖...')
                        const fallbackSuccess = await loadFallbackDirectly()
                        if (fallbackSuccess) {
                            setError(
                                `API 請求失敗，已載入備用星座圖: ${
                                    error instanceof Error
                                        ? error.message
                                        : '未知錯誤'
                                }`
                            )
                        } else {
                            // 如果連備用圖都載入失敗
                            setError(
                                `API 和備用星座圖均載入失敗: ${
                                    error instanceof Error
                                        ? error.message
                                        : '未知錯誤'
                                }`
                            )
                            // 最後手段，嘗試設置靜態路徑，儘管它可能也會失敗
                            setImageUrl(FALLBACK_IMAGE_PATH)
                            setUsingFallback(true)
                        }
                    }

                    // Retry logic only for non-AbortErrors
                    const currentRetryCount = retryCount + 1
                    setRetryCount(currentRetryCount)
                    if (currentRetryCount >= MAX_RETRIES) {
                        setManualRetryMode(true)
                    } else {
                        console.log(
                            `自動重試 (${currentRetryCount}/${MAX_RETRIES})... 將在 ${
                                RETRY_INTERVAL / 1000
                            } 秒後重試`
                        )
                        const retryTimeoutId = setTimeout(() => {
                            // 確保這次請求完成後再發起新請求
                            isFetchingRef.current = false
                            // Create a new controller for retry
                            controllerRef.current = new AbortController()
                            fetchImage(controllerRef.current.signal)
                        }, RETRY_INTERVAL)

                        // 清理函數
                        return () => {
                            clearTimeout(retryTimeoutId)
                        }
                    }
                } else {
                    console.log(
                        'Constellation fetch aborted (likely due to StrictMode or component unmount), ignoring error.'
                    )
                }
            } finally {
                // Ensure timeout is cleared
                if (timeoutId !== null) window.clearTimeout(timeoutId)
                setIsLoading(false)
                // 重置請求標誌
                isFetchingRef.current = false
            }
        },
        [retryCount, loadFallbackDirectly] // 加入 loadFallbackDirectly 依賴
    )

    // 主效果 - 初始載入
    useEffect(() => {
        console.log('--- ConstellationViewer useEffect triggered for mount ---')
        controllerRef.current = new AbortController()

        // 組件掛載後的延遲，避免與其他請求同時發送
        const loadTimeoutId = setTimeout(() => {
            fetchImage(controllerRef.current!.signal)
        }, INITIAL_LOAD_DELAY) // 增加初始載入延遲

        // 清理工作
        return () => {
            console.log('--- ConstellationViewer useEffect cleanup ---')
            clearTimeout(loadTimeoutId)

            // 中止進行中的請求
            if (controllerRef.current) {
                controllerRef.current.abort()
                controllerRef.current = null
            }

            // 清理 prevImageUrlRef 中存儲的 URL
            if (prevImageUrlRef.current) {
                URL.revokeObjectURL(prevImageUrlRef.current)
                console.log(
                    'Cleaned up constellation object URL on unmount:',
                    prevImageUrlRef.current
                )
                prevImageUrlRef.current = null
            }
            // 確保在卸載時重置 fetching 標誌
            isFetchingRef.current = false
        }
    }, [fetchImage])

    // 處理手動重試
    const handleRetry = useCallback(() => {
        if (isFetchingRef.current) {
            console.log('已有請求進行中，忽略此次手動重試')
            return
        }

        console.log('手動重試載入星座圖...')
        setRetryCount(0)
        setManualRetryMode(false)

        // 重新創建控制器
        if (controllerRef.current) {
            controllerRef.current.abort()
        }
        controllerRef.current = new AbortController()
        fetchImage(controllerRef.current.signal)
    }, [fetchImage])

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
        <div className="constellation-container" style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
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
            <div style={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', minHeight: '50vh' }}>
                {imageUrl && (
                    <img
                        key={imageUrl} // 使用 key 確保 URL 變化時 img 元素刷新
                        src={imageUrl}
                        alt="Constellation Diagram"
                        onLoad={handleImageLoad}
                        onError={handleImageError}
                        style={{
                            maxWidth: '100%',
                            maxHeight: '100%',
                            objectFit: 'contain',
                            border: '1px solid #ccc',
                            display: isLoading || !imageUrl ? 'none' : 'block',
                        }}
                    />
                )}
                {isLoading && !imageUrl && <p>正在載入星座圖...</p>}
            </div>
        </div>
    )
}

export default ConstellationViewer
