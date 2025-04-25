// src/components/ConstellationViewer.tsx
import React, { useState, useEffect } from 'react'

// 指向新的後端 API 端點
const CONSTELLATION_ENDPOINT = '/api/constellation-diagram' // 使用相對路徑，透過 Vite 代理

const ConstellationViewer: React.FC = () => {
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchImage = () => {
            setIsLoading(true)
            setError(null)
            console.log(`正在從 ${CONSTELLATION_ENDPOINT} 獲取星座圖...`)

            const imageUrlWithCacheBuster = `${CONSTELLATION_ENDPOINT}?t=${new Date().getTime()}`
            setImageUrl(imageUrlWithCacheBuster)
        }
        fetchImage()
    }, [])

    const handleImageLoad = () => {
        console.log('星座圖載入成功')
        setIsLoading(false)
        setError(null)
    }

    const handleImageError = (
        e: React.SyntheticEvent<HTMLImageElement, Event>
    ) => {
        console.error('星座圖載入失敗')
        console.error('Error event:', e)
        setIsLoading(false)
        setError('無法載入星座圖，請檢查後端服務。')
        setImageUrl(null)
    }

    return (
        <div>
            <h2>Constellation Diagram</h2>
            {isLoading && <p>正在載入星座圖...</p>}
            {error && <p style={{ color: 'red' }}>錯誤: {error}</p>}
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
