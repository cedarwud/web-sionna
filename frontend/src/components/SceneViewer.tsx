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

    useEffect(() => {
        console.log(
            `--- SceneViewer useEffect triggered, viewType: ${viewType} ---`
        )
        // 根據 viewType 決定請求哪個 API 端點
        const endpoint =
            viewType === 'original'
                ? '/api/scene-image-original' // 請求原始場景
                : '/api/scene-image-rt' // 請求帶路徑的場景

        const fetchImage = () => {
            setIsLoading(true)
            setError(null)
            console.log(
                `正在從 ${endpoint} (viewType: ${viewType}) 獲取場景圖...`
            ) // 修改日誌

            // 確保是正確的模板字符串語法
            const imageUrlWithCacheBuster = `${endpoint}?t=${new Date().getTime()}`
            console.log('Setting imageUrl to:', imageUrlWithCacheBuster)
            setImageUrl(imageUrlWithCacheBuster)
        }
        fetchImage()

        // viewType 改變時，useEffect 會重新執行
    }, [viewType]) // <--- 將 viewType 加入依賴數組

    const handleImageLoad = () => {
        console.log(`場景圖 (${viewType}) 載入成功`) // 修改日誌
        setIsLoading(false)
        setError(null)
    }

    const handleImageError = (
        e: React.SyntheticEvent<HTMLImageElement, Event>
    ) => {
        console.error(`場景圖 (${viewType}) 載入失敗`) // 修改日誌
        console.error('Error event:', e)
        setIsLoading(false)
        setError(
            `無法載入 ${
                viewType === 'original' ? '原始場景' : '帶路徑場景'
            }，請檢查後端服務。`
        ) // 修改錯誤訊息
        setImageUrl(null)
    }

    // 可以動態修改標題
    const title =
        viewType === 'original' ? '原始場景 (Etoile)' : '場景與路徑 (Etoile)'

    return (
        <div>
            <h2>{title}</h2> {/* 使用動態標題 */}
            {isLoading && <p>正在載入圖片...</p>}
            {error && <p style={{ color: 'red' }}>錯誤: {error}</p>}
            {imageUrl && (
                <img
                    // key={imageUrl} // 添加 key 可以強制 img 元素在 src 變化時重新創建，有時有助於避免緩存問題
                    src={imageUrl}
                    alt={title} // 使用動態 alt
                    onLoad={handleImageLoad}
                    onError={handleImageError}
                    style={{
                        maxWidth: '100%',
                        height: 'auto',
                        border: '1px solid #ccc',
                    }}
                />
            )}
        </div>
    )
}

export default SceneViewer
