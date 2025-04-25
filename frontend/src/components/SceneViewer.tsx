// src/components/SceneViewer.tsx
import React, { useState, useEffect } from 'react'

// 定義 Props 接口
interface SceneViewerProps {
    viewType: 'original' | 'rt' // 接收來自 App 的視圖類型
}

const SceneViewer: React.FC<SceneViewerProps> = ({ viewType }) => {
    // <--- 接收 viewType prop
    console.log('--- SceneViewer Component Rendered ---')
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [prevImageUrl, setPrevImageUrl] = useState<string | null>(null) // State to hold previous URL for cleanup

    useEffect(() => {
        console.log(
            `--- SceneViewer useEffect triggered, viewType: ${viewType} ---`
        )

        const originalEndpoint = '/api/v1/sionna/scene-image-original' // <--- 確認路徑正確
        const rtEndpoint = '/api/v1/sionna/scene-image-rt' // <--- 確認路徑正確

        const endpoint = viewType === 'original' ? originalEndpoint : rtEndpoint

        // ***** 將 fetchImage 宣告為 async 函數 *****
        const fetchImage = async () => {
            setIsLoading(true)
            setError(null)

            // 清理上一個 createObjectURL (如果存在)
            // 將清理邏輯移到這裡，確保在設定新 URL 前清理
            if (prevImageUrl) {
                URL.revokeObjectURL(prevImageUrl)
                setPrevImageUrl(null) // 清理 state
                console.log('Revoked previous object URL:', prevImageUrl)
            }
            // 清除當前顯示的圖像，避免切換時閃爍舊圖
            setImageUrl(null)

            const endpointWithCacheBuster = `${endpoint}?t=${new Date().getTime()}`
            console.log(`Fetching image from: ${endpointWithCacheBuster}`)

            try {
                // 使用 fetch API 進行請求
                const response = await fetch(endpointWithCacheBuster) // <--- await 現在合法了

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
                const imageBlob = await response.blob() // <--- await 現在合法了

                // 檢查 blob 是否有效 (例如，大小 > 0)
                if (imageBlob.size === 0) {
                    throw new Error('Received empty image blob.')
                }

                const newImageUrl = URL.createObjectURL(imageBlob)
                console.log('Created new object URL:', newImageUrl)
                setImageUrl(newImageUrl) // 設定新的圖片 URL
                setPrevImageUrl(newImageUrl) // 儲存這次的 URL 以便下次清理

                // 注意: setIsLoading(false) 會在圖片的 onLoad 事件中處理
                // 但如果圖片載入極快或有快取，onLoad 可能不會觸發，
                // 或者在錯誤處理後也需要設為 false。
                // 考慮是否在成功獲取 blob 後就設定 isLoading 為 false
                // setIsLoading(false); // <--- 可以在這裡或 onLoad 中設定
            } catch (error) {
                console.error(`Failed to fetch image from ${endpoint}:`, error)
                setError(
                    `無法載入 ${
                        viewType === 'original' ? '原始場景' : '帶路徑場景'
                    } (${error instanceof Error ? error.message : '未知錯誤'})`
                )
                setIsLoading(false) // 載入失敗，結束 loading
                setImageUrl(null) // 清除圖像
                // 如果有上一個 URL 且尚未清理，也清理掉
                if (prevImageUrl) {
                    URL.revokeObjectURL(prevImageUrl)
                    setPrevImageUrl(null)
                }
            }
        }

        fetchImage() // 呼叫 async 函數

        // *** 將清理函數移到 useEffect 的 return 中 ***
        // 這個清理函數會在元件卸載或 useEffect 重新執行前被呼叫
        return () => {
            // 使用 prevImageUrl 來清理，因為 imageUrl 可能已經改變
            if (prevImageUrl) {
                URL.revokeObjectURL(prevImageUrl)
                console.log(
                    'Cleaned up object URL on unmount/re-effect:',
                    prevImageUrl
                )
            }
        }
        // 依賴保持不變
    }, [viewType])

    const handleImageLoad = () => {
        console.log(`Image element loaded successfully: ${imageUrl}`)
        setIsLoading(false) // 圖片成功顯示後，確認 loading 結束
        setError(null) // 清除之前的錯誤
    }

    const handleImageError = (
        e: React.SyntheticEvent<HTMLImageElement, Event>
    ) => {
        // 這個錯誤通常表示圖片 URL 有問題或圖片本身損壞
        console.error(`Image element failed to load src: ${imageUrl}`, e)
        setError(`圖片載入失敗 (URL: ${imageUrl})`)
        setIsLoading(false) // 確保 loading 結束
        setImageUrl(null) // 清除無效的 URL
    }

    // ... (title 和 return 部分保持不變) ...
    const title =
        viewType === 'original' ? '原始場景 (Etoile)' : '場景與路徑 (Etoile)'

    return (
        <div>
            <h2>{title}</h2> {/* 使用動態標題 */}
            {isLoading && <p>正在載入圖片...</p>}
            {error && <p style={{ color: 'red' }}>錯誤: {error}</p>}
            {/* 只有在 imageUrl 存在且 loading 完成後才顯示 img，或在 loading 時顯示佔位符 */}
            {imageUrl && (
                <img
                    key={imageUrl} // 使用 key 確保 URL 變化時 img 元素刷新
                    src={imageUrl}
                    alt={title} // 使用動態 alt
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
            {/* 可以選擇在 loading 時顯示不同的佔位符 */}
            {/* {isLoading && !error && <p>圖像處理中...</p>} */}
        </div>
    )
}

export default SceneViewer
