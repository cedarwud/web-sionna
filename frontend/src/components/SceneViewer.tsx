// src/components/SceneViewer.tsx
import React, { useState, useEffect } from 'react'

// 定義 Props 接口
interface SceneViewerProps {
    // viewType 屬性已移除
}

// 定義靜態路徑指向後端存儲的最後一次成功渲染的圖像
const FALLBACK_IMAGE_PATH = '/rendered_images/scene_with_paths.png'
const EMPTY_SCENE_IMAGE_PATH = '/rendered_images/empty_scene.png'

const SceneViewer: React.FC<SceneViewerProps> = () => {
    console.log('--- SceneViewer Component Rendered ---')
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [prevImageUrl, setPrevImageUrl] = useState<string | null>(null) // State to hold previous URL for cleanup
    const [usingFallback, setUsingFallback] = useState<boolean>(false)
    const [loadingPlaceholder, setLoadingPlaceholder] = useState<string | null>(
        null
    )
    // 新增重試機制相關狀態
    const [retryCount, setRetryCount] = useState<number>(0)
    const [manualRetryMode, setManualRetryMode] = useState<boolean>(false)

    // 檢查空場景圖片是否存在，如果不存在則生成
    useEffect(() => {
        const checkEmptyScene = async () => {
            try {
                console.log('檢查空場景圖片是否存在...')
                const response = await fetch('/api/v1/sionna/check-empty-scene')

                if (response.ok) {
                    const data = await response.json()
                    console.log('空場景檢查結果:', data)
                    setLoadingPlaceholder(data.path)
                } else {
                    console.error('檢查空場景圖片失敗:', response.statusText)
                    // 如果檢查失敗，使用默認的備用圖片
                    setLoadingPlaceholder(FALLBACK_IMAGE_PATH)
                }
            } catch (error) {
                console.error('檢查空場景圖片出錯:', error)
                setLoadingPlaceholder(FALLBACK_IMAGE_PATH)
            }
        }

        checkEmptyScene()
    }, [])

    // 包裝 fetchImage 函數為可獨立調用的函數
    const fetchImage = async () => {
        const rtEndpoint = '/api/v1/sionna/scene-image-rt'

        setIsLoading(true)
        setError(null)
        setUsingFallback(false)

        // 清理上一個 createObjectURL (如果存在)
        if (prevImageUrl) {
            URL.revokeObjectURL(prevImageUrl)
            setPrevImageUrl(null) // 清理 state
            console.log('Revoked previous object URL:', prevImageUrl)
        }

        // 如果存在空場景圖片，則在加載過程中顯示它
        if (loadingPlaceholder) {
            setImageUrl(loadingPlaceholder)
        } else {
            setImageUrl(null)
        }

        const endpointWithCacheBuster = `${rtEndpoint}?t=${new Date().getTime()}`
        console.log(`Fetching image from: ${endpointWithCacheBuster}`)

        try {
            // 使用 fetch API 進行請求，添加超時處理
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 10000) // 10秒超時

            const response = await fetch(endpointWithCacheBuster, {
                signal: controller.signal,
            })
            clearTimeout(timeoutId)

            if (!response.ok) {
                // 嘗試讀取錯誤訊息 (如果後端返回 JSON)
                let errorDetail = `HTTP error! status: ${response.status}`
                try {
                    const errorJson = await response.json()
                    errorDetail = errorJson.detail || errorDetail // 使用後端提供的 detail
                } catch (jsonError) {
                    // 如果回應不是 JSON 或解析失敗，保持原始 HTTP 錯誤
                }
                throw new Error(errorDetail)
            }

            // 假設後端直接返回圖片 blob
            const imageBlob = await response.blob()

            // 檢查 blob 是否有效 (例如，大小 > 0)
            if (imageBlob.size === 0) {
                throw new Error('Received empty image blob.')
            }

            const newImageUrl = URL.createObjectURL(imageBlob)
            console.log('Created new object URL:', newImageUrl)
            setImageUrl(newImageUrl) // 設定新的圖片 URL
            setPrevImageUrl(newImageUrl) // 儲存這次的 URL 以便下次清理
            setRetryCount(0) // 重置重試計數
            setManualRetryMode(false) // 重置手動重試模式
        } catch (error) {
            console.error(`Failed to fetch image from ${rtEndpoint}:`, error)

            // 使用備用圖像
            setImageUrl(FALLBACK_IMAGE_PATH)
            setUsingFallback(true)

            // 設置更有幫助的錯誤訊息
            setError(
                `圖像載入失敗: ${
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
        console.log('--- SceneViewer useEffect triggered ---')
        fetchImage() // 首次呼叫

        // 清理函數
        return () => {
            if (prevImageUrl) {
                URL.revokeObjectURL(prevImageUrl)
                console.log(
                    'Cleaned up object URL on unmount/re-effect:',
                    prevImageUrl
                )
            }
        }
    }, []) // 空依賴陣列，僅在掛載時執行一次

    // 處理手動重試
    const handleRetry = () => {
        console.log('手動重試載入圖片...')
        fetchImage()
    }

    const handleImageLoad = () => {
        console.log(`Image element loaded successfully: ${imageUrl}`)
        setIsLoading(false) // 圖片成功顯示後，確認 loading 結束
        if (!usingFallback) {
            setError(null) // 只有非備用圖像時才清除錯誤
        }
    }

    const handleImageError = (
        e: React.SyntheticEvent<HTMLImageElement, Event>
    ) => {
        // 這個錯誤通常表示圖片 URL 有問題或圖片本身損壞
        console.error(`Image element failed to load src: ${imageUrl}`, e)

        // 如果是備用圖像也載入失敗，那麼顯示錯誤訊息
        if (usingFallback || imageUrl === FALLBACK_IMAGE_PATH) {
            setError(`備用圖片也無法載入，請檢查網絡連接`)
        } else {
            // 嘗試使用備用圖像
            console.log(
                'Regular image failed, trying fallback:',
                FALLBACK_IMAGE_PATH
            )
            setImageUrl(FALLBACK_IMAGE_PATH)
            setUsingFallback(true)
            setError(`使用最後一次成功的圖像 (無法連接後端服務)`)
        }

        setIsLoading(false) // 確保 loading 結束
    }

    // 使用固定標題
    const title = '場景與路徑 (Etoile)'

    return (
        <div>
            {isLoading && <p>正在載入圖片...</p>}
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
            {/* 只有在 imageUrl 存在且 loading 完成後才顯示 img，或在 loading 時顯示佔位符 */}
            {imageUrl && (
                <img
                    key={imageUrl} // 使用 key 確保 URL 變化時 img 元素刷新
                    src={imageUrl}
                    alt={title}
                    onLoad={handleImageLoad}
                    onError={handleImageError}
                    style={{
                        maxWidth: '100%',
                        height: 'auto',
                        border: '1px solid #ccc',
                        display: isLoading ? 'none' : 'block', // 可以在 loading 時隱藏
                    }}
                />
            )}
        </div>
    )
}

export default SceneViewer
