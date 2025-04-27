// src/components/SceneViewer.tsx
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { debounce } from 'lodash' // 需要安裝 lodash 依賴
import CoordinateDisplay from './CoordinateDisplay' // 引入子組件
// 引入 API 函數和類型
import {
    createDevice,
    DeviceCreate,
    DeviceType as BackendDeviceType, // 重命名以避免衝突
    TransmitterType,
} from '../services/api' // <--- 修正路徑

// 定義 Props 接口
interface SceneViewerProps {
    refreshDeviceData: () => void // 添加回調函數 prop
}

// 定義設備類型枚舉
type DeviceType = 'tx' | 'rx' | 'int'

// 定義新設備的介面
interface NewDevice {
    name: string
    x: number
    y: number
    z: number
    active: boolean
    type: DeviceType
}

// API裝置數據介面
interface DeviceData {
    id: number
    name: string
    type: DeviceType
}

// 定義靜態路徑指向後端存儲的最後一次成功渲染的圖像
const FALLBACK_IMAGE_PATH = '/rendered_images/scene_with_paths.png'
const EMPTY_SCENE_IMAGE_PATH = '/rendered_images/empty_scene.png'

// 使用 React.memo 包裝組件以避免不必要的重新渲染
const SceneViewer: React.FC<SceneViewerProps> = React.memo((props) => {
    // console.log('--- SceneViewer Component Rendered ---') // 移除或註釋掉這個 log
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const prevImageUrlRef = useRef<string | null>(null) // 使用 ref 存儲上一個 URL
    const [usingFallback, setUsingFallback] = useState<boolean>(false)
    const [loadingPlaceholder, setLoadingPlaceholder] = useState<string | null>(
        null
    )
    const [retryCount, setRetryCount] = useState<number>(0)
    const [manualRetryMode, setManualRetryMode] = useState<boolean>(false)

    // 新增滑鼠座標狀態 - 移除 mousePositionRef
    const [mousePositionForDisplay, setMousePositionForDisplay] = useState<{
        x: number
        y: number
        clientX: number
        clientY: number
    } | null>(null) // 專門用於傳遞給 CoordinateDisplay 的狀態

    const imageRef = useRef<HTMLImageElement>(null)
    const existingDevicesRef = useRef<DeviceData[]>([])

    // 新增彈出視窗相關狀態
    const [showPopover, setShowPopover] = useState<boolean>(false)
    const [popoverPosition, setPopoverPosition] = useState<{
        x: number
        y: number
        clientX: number
        clientY: number
        sceneX: number
        sceneY: number
    } | null>(null)
    const [newDevice, setNewDevice] = useState<NewDevice>({
        name: '',
        x: 0,
        y: 0,
        z: 0,
        active: true,
        type: 'tx',
    })

    // 獲取現有設備列表的函數 - 將結果存儲在 ref 中而不是狀態
    const fetchExistingDevices = useCallback(async () => {
        try {
            const response = await fetch('/api/v1/devices/')
            if (response.ok) {
                const devices = await response.json()
                existingDevicesRef.current = devices
                return devices
            } else {
                console.error('Failed to fetch devices:', response.statusText)
                return existingDevicesRef.current // 返回當前 ref 中的值
            }
        } catch (error) {
            console.error('Error fetching devices:', error)
            return existingDevicesRef.current // 返回當前 ref 中的值
        }
    }, [])

    // 生成新設備名稱的函數
    const generateDeviceName = useCallback(
        (type: DeviceType, devices: DeviceData[]) => {
            // 修改前綴以使用 dash
            const prefix =
                type === 'tx' ? 'tx-' : type === 'rx' ? 'rx-' : 'int-'

            // 過濾出該類型的設備
            const typeDevices = devices.filter((d) => d.name.startsWith(prefix))

            // 尋找最大的數字編號
            let maxNum = 0
            typeDevices.forEach((device) => {
                // 修改替換邏輯以匹配 dash
                const numPart = device.name.replace(prefix, '')
                const num = parseInt(numPart, 10)
                if (!isNaN(num) && num > maxNum) {
                    maxNum = num
                }
            })

            // 返回新的名稱，編號加1
            return `${prefix}${maxNum + 1}`
        },
        []
    )

    // 封裝 fetchImage 函數，避免不必要的重複渲染
    const fetchImage = useCallback(async () => {
        const rtEndpoint = '/api/v1/sionna/scene-image-rt'

        setIsLoading(true)
        setError(null)
        setUsingFallback(false)

        // 清理上一個 createObjectURL (從 ref 中讀取)
        if (prevImageUrlRef.current) {
            URL.revokeObjectURL(prevImageUrlRef.current)
            prevImageUrlRef.current = null // 清理 ref
            console.log('Revoked previous object URL from ref')
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
            const timeoutId = setTimeout(() => controller.abort(), 15000) // 增加超時到15秒

            const response = await fetch(endpointWithCacheBuster, {
                signal: controller.signal,
                // 添加額外的請求選項，避免快取問題
                cache: 'no-cache',
                headers: {
                    Pragma: 'no-cache',
                    'Cache-Control': 'no-cache',
                },
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

            // 使用嘗試-捕獲塊來處理響應內容
            try {
                // 假設後端直接返回圖片 blob
                const imageBlob = await response.blob()

                // 檢查 blob 是否有效 (例如，大小 > 0)
                if (imageBlob.size === 0) {
                    throw new Error('Received empty image blob.')
                }

                const newImageUrl = URL.createObjectURL(imageBlob)
                console.log('Created new object URL:', newImageUrl)
                setImageUrl(newImageUrl) // 設定新的圖片 URL
                prevImageUrlRef.current = newImageUrl // 儲存這次的 URL 到 ref
                setRetryCount(0) // 重置重試計數
                setManualRetryMode(false) // 重置手動重試模式
            } catch (blobError) {
                console.error('Error processing image blob:', blobError)
                throw new Error(
                    `處理圖像時出錯: ${
                        blobError instanceof Error
                            ? blobError.message
                            : String(blobError)
                    }`
                )
            }
        } catch (error) {
            console.error(`Failed to fetch image from ${rtEndpoint}:`, error)

            // 嘗試使用備用圖像 - 但改為通過 fetch API 載入，而不是直接使用路徑
            try {
                console.log('Trying to fetch fallback image as blob...')
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
                        prevImageUrlRef.current = fallbackUrl // 更新 ref
                        setUsingFallback(true)
                        setError(
                            `使用備用圖像: ${
                                error instanceof Error
                                    ? error.message
                                    : '未知錯誤'
                            }`
                        )
                        console.log(
                            'Successfully loaded fallback image as blob'
                        )
                    } else {
                        throw new Error('備用圖像 blob 為空')
                    }
                } else {
                    throw new Error(
                        `備用圖像請求失敗: ${fallbackResponse.status}`
                    )
                }
            } catch (fallbackError) {
                console.error('Fallback image loading failed:', fallbackError)
                // 最後的備用：使用直接 URL (可能會導致 404 或內容長度問題，但至少我們嘗試了)
                setImageUrl(FALLBACK_IMAGE_PATH)
                setUsingFallback(true)
                setError(
                    `圖像載入失敗: ${
                        error instanceof Error ? error.message : '未知錯誤'
                    }`
                )
            }

            // 增加重試計數
            const currentRetryCount = retryCount + 1
            setRetryCount(currentRetryCount)

            // 如果重試超過3次，進入手動重試模式
            if (currentRetryCount >= 3) {
                // 這裡直接使用計算後的值
                setManualRetryMode(true)
            } else {
                // 否則自動重試一次，但延長間隔
                console.log(`自動重試 (${currentRetryCount}/3)...`)
                // 設定較長的重試間隔
                setTimeout(() => {
                    fetchImage() // 在 setTimeout 內部調用 fetchImage
                }, 5000) // 增加到5秒
            }
        } finally {
            setIsLoading(false)
        }
    }, [loadingPlaceholder])

    // 主效果 - 初始載入 - 僅執行一次
    useEffect(() => {
        console.log('--- SceneViewer useEffect triggered for mount ---')

        fetchImage()
        fetchExistingDevices()

        // 清理函數
        return () => {
            if (prevImageUrlRef.current) {
                URL.revokeObjectURL(prevImageUrlRef.current)
                console.log(
                    'Cleaned up object URL on unmount:',
                    prevImageUrlRef.current
                )
                prevImageUrlRef.current = null
            }
        }
        // 依賴項應包含 fetchImage 和 fetchExistingDevices，確保它們穩定
    }, [fetchImage, fetchExistingDevices])

    // 處理手動重試
    const handleRetry = useCallback(() => {
        console.log('手動重試載入圖片...')
        // 重置重試計數器以允許 fetchImage 正常工作
        setRetryCount(0)
        setManualRetryMode(false)
        fetchImage()
    }, [fetchImage])

    const handleImageLoad = useCallback(() => {
        console.log(`Image element loaded successfully: ${imageUrl}`)
        setIsLoading(false) // 圖片成功顯示後，確認 loading 結束
        if (!usingFallback) {
            setError(null) // 只有非備用圖像時才清除錯誤
        }
    }, [imageUrl, usingFallback])

    const handleImageError = useCallback(
        (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
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
        },
        [imageUrl, usingFallback]
    )

    // 處理滑鼠移動事件 - 使用防抖動更新顯示狀態
    const updateMousePositionForDisplay = useMemo(
        () =>
            debounce(
                (
                    newPosition: {
                        x: number
                        y: number
                        clientX: number
                        clientY: number
                    } | null
                ) => {
                    setMousePositionForDisplay(newPosition)
                },
                50
            ),
        []
    )

    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLImageElement>) => {
            if (imageRef.current) {
                const rect = imageRef.current.getBoundingClientRect()
                const x = Math.round(e.clientX - rect.left)
                const y = Math.round(e.clientY - rect.top)

                // 計算相對於圖片容器的座標
                const containerX = e.clientX
                const containerY = e.clientY

                const newPosition = {
                    x,
                    y,
                    clientX: containerX,
                    clientY: containerY,
                }

                // 使用防抖動更新顯示用的狀態
                updateMousePositionForDisplay(newPosition)
            }
        },
        [updateMousePositionForDisplay]
    )

    // 處理滑鼠離開事件
    const handleMouseLeave = useCallback(() => {
        updateMousePositionForDisplay(null)
    }, [updateMousePositionForDisplay])

    // 處理圖片點擊事件
    const handleImageClick = useCallback(
        async (e: React.MouseEvent<HTMLImageElement>) => {
            if (imageRef.current) {
                // 如果彈出視窗已經開啟，則關閉它
                if (showPopover) {
                    setShowPopover(false)
                    setPopoverPosition(null)
                    return
                }

                const rect = imageRef.current.getBoundingClientRect()
                const x = Math.round(e.clientX - rect.left)
                const y = Math.round(e.clientY - rect.top)

                // 計算場景座標
                const sceneX = Math.round((x - 492) / 1.2)
                const sceneY = Math.round((370 - y) / 1.2)

                // 設置彈出視窗位置
                const newPosition = {
                    x,
                    y,
                    clientX: e.clientX,
                    clientY: e.clientY,
                    sceneX,
                    sceneY,
                }

                setPopoverPosition(newPosition)

                // 直接獲取設備並生成名稱
                const devices = await fetchExistingDevices()

                // 批量更新狀態，避免多次渲染
                const initialDevice = {
                    // 保留 z, active, type 的默認值或上次的值
                    z: newDevice.z,
                    active: newDevice.active,
                    type: newDevice.type,
                    x: sceneX,
                    y: sceneY,
                    name: generateDeviceName(newDevice.type, devices), // 使用當前選中的 type
                }

                setNewDevice(initialDevice)
                setShowPopover(true)
            }
        },
        [
            fetchExistingDevices,
            generateDeviceName,
            newDevice.z,
            newDevice.active,
            newDevice.type,
            showPopover,
        ]
    ) // 添加依賴項

    // 關閉彈出視窗
    const handleClosePopover = useCallback(() => {
        setShowPopover(false)
        setPopoverPosition(null)
    }, [])

    // 處理新設備屬性變更
    const handleDeviceChange = useCallback(
        async (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
            const { name, value } = e.target

            const devices = await fetchExistingDevices() // 預先獲取設備列表

            setNewDevice((prev) => {
                let updatedDevice = { ...prev }

                if (name === 'type') {
                    const newType = value as DeviceType
                    const newName = generateDeviceName(newType, devices)
                    updatedDevice = {
                        ...updatedDevice,
                        type: newType,
                        name: newName,
                    }
                } else if (name === 'active') {
                    updatedDevice = {
                        ...updatedDevice,
                        active: (e.target as HTMLInputElement).checked,
                    }
                } else {
                    const newValue =
                        name === 'x' || name === 'y' || name === 'z'
                            ? parseFloat(value) || 0
                            : value
                    updatedDevice = { ...updatedDevice, [name]: newValue }
                }
                return updatedDevice
            })
        },
        [fetchExistingDevices, generateDeviceName]
    )

    // 處理添加設備 - 重構為使用 api.ts
    const handleAddDevice = useCallback(async () => {
        try {
            // 1. 準備符合 DeviceCreate 介面的 payload
            let devicePayload: DeviceCreate
            const frontendType = newDevice.type

            if (frontendType === 'tx') {
                devicePayload = {
                    name: newDevice.name,
                    x: newDevice.x,
                    y: newDevice.y,
                    z: newDevice.z,
                    active: newDevice.active,
                    device_type: BackendDeviceType.TRANSMITTER,
                    // transmitter_type 默認為 SIGNAL，api.ts 的 createDevice 會處理
                }
            } else if (frontendType === 'rx') {
                devicePayload = {
                    name: newDevice.name,
                    x: newDevice.x,
                    y: newDevice.y,
                    z: newDevice.z,
                    active: newDevice.active,
                    device_type: BackendDeviceType.RECEIVER,
                }
            } else {
                // 'int'
                devicePayload = {
                    name: newDevice.name,
                    x: newDevice.x,
                    y: newDevice.y,
                    z: newDevice.z,
                    active: newDevice.active,
                    device_type: BackendDeviceType.TRANSMITTER,
                    transmitter_type: TransmitterType.INTERFERER, // 明確指定干擾器類型
                }
            }

            console.log('Calling createDevice with payload:', devicePayload)

            // 2. 調用集中的 API 函數
            const createdDevice = await createDevice(devicePayload)
            console.log(
                'Device created successfully via api.ts:',
                createdDevice
            )

            // 3. 後續操作 (與之前相同)
            handleClosePopover()
            fetchImage() // 更新場景圖
            props.refreshDeviceData() // 更新 App 狀態 (包括星座圖)

            // 重置新設備表單
            setNewDevice({
                name: '',
                x: 0,
                y: 0,
                z: 0,
                active: true,
                type: 'tx',
            })

            // 顯示成功通知 (使用 payload 中的 name)
            alert(`成功新增設備: ${devicePayload.name}`)
        } catch (error: any) {
            console.error('Failed to add device via api.ts:', error)
            // 嘗試提取後端返回的詳細錯誤訊息
            let errorMessage = '新增設備失敗'
            if (error.response?.data?.detail) {
                if (Array.isArray(error.response.data.detail)) {
                    errorMessage +=
                        ': ' +
                        error.response.data.detail
                            .map(
                                (item: any) => item.msg || JSON.stringify(item)
                            )
                            .join('; ')
                } else {
                    errorMessage += ': ' + error.response.data.detail
                }
            } else if (error.message) {
                errorMessage += ': ' + error.message
            }
            alert(errorMessage)
        }
    }, [newDevice, fetchImage, props.refreshDeviceData, handleClosePopover]) // 移除 fetchExistingDevices

    // 使用固定標題
    const title = '場景與路徑 (Etoile)'

    return (
        <div style={{ position: 'relative' }}>
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
            <div style={{ position: 'relative' }}>
                {imageUrl && (
                    <img
                        ref={imageRef}
                        key={imageUrl} // 使用 key 確保 URL 變化時 img 元素刷新
                        src={imageUrl}
                        alt={title}
                        onLoad={handleImageLoad}
                        onError={handleImageError}
                        onMouseMove={handleMouseMove}
                        onMouseLeave={handleMouseLeave}
                        onClick={handleImageClick} // 新增點擊事件
                        style={{
                            maxWidth: '100%',
                            height: 'auto',
                            border: '1px solid #ccc',
                            display: isLoading ? 'none' : 'block', // 可以在 loading 時隱藏
                            cursor: 'crosshair', // 十字標指針
                        }}
                    />
                )}

                {/* 座標顯示 - 使用獨立組件，並且只在 popover 不顯示時渲染 */}
                {!showPopover && (
                    <CoordinateDisplay position={mousePositionForDisplay} />
                )}

                {/* 新增設備彈出視窗 */}
                {showPopover && popoverPosition && (
                    <div
                        style={{
                            position: 'fixed',
                            backgroundColor: 'var(--dark-accent)',
                            color: 'var(--dark-text)',
                            boxShadow: '0 2px 10px rgba(0, 0, 0, 0.4)',
                            borderRadius: '5px',
                            border: '1px solid var(--dark-border)',
                            padding: '15px',
                            zIndex: 1000,
                            left: `${popoverPosition.clientX}px`,
                            top: `${popoverPosition.clientY - 35}px`,
                            transform: 'translateX(-50%)',
                            width: '330px',
                        }}
                    >
                        {/* 設備名稱與關閉按鈕 */}
                        <div
                            style={{
                                position: 'relative',
                                marginBottom: '15px',
                            }}
                        >
                            <input
                                type="text"
                                name="name"
                                value={newDevice.name}
                                onChange={handleDeviceChange}
                                placeholder="設備名稱"
                                style={{
                                    width: '100%',
                                    padding: '8px 10px',
                                    backgroundColor: 'var(--dark-component)',
                                    color: 'var(--dark-text)',
                                    border: 'none',
                                    borderRadius: '3px',
                                    fontSize: '16px',
                                    textAlign: 'center',
                                    boxSizing: 'border-box',
                                }}
                            />
                            <button
                                onClick={handleClosePopover}
                                style={{
                                    position: 'absolute',
                                    right: '5px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    background: 'transparent',
                                    border: 'none',
                                    color: 'var(--dark-text-secondary)',
                                    cursor: 'pointer',
                                    fontSize: '20px',
                                    padding: '0 5px',
                                    opacity: '0.6',
                                    transition: 'all 0.2s ease',
                                    lineHeight: '1',
                                }}
                            >
                                ✕
                            </button>
                        </div>

                        {/* 設備屬性表格 */}
                        <div
                            style={{
                                borderTop: '1px solid var(--dark-border)',
                                paddingTop: '10px',
                            }}
                        >
                            <table
                                style={{
                                    width: '100%',
                                    borderCollapse: 'collapse',
                                    tableLayout: 'fixed',
                                }}
                            >
                                <thead>
                                    <tr>
                                        <th
                                            style={{
                                                color: 'var(--dark-text-secondary)',
                                                fontSize: '0.9rem',
                                                fontWeight: 'normal',
                                                textAlign: 'center',
                                                paddingBottom: '5px',
                                                width: '8%',
                                            }}
                                        ></th>
                                        <th
                                            style={{
                                                color: 'var(--dark-text-secondary)',
                                                fontSize: '0.9rem',
                                                fontWeight: 'normal',
                                                textAlign: 'center',
                                                paddingBottom: '5px',
                                                width: '25%',
                                            }}
                                        >
                                            Type
                                        </th>
                                        <th
                                            style={{
                                                color: 'var(--dark-text-secondary)',
                                                fontSize: '0.9rem',
                                                fontWeight: 'normal',
                                                textAlign: 'center',
                                                paddingBottom: '5px',
                                                width: '22%',
                                            }}
                                        >
                                            X
                                        </th>
                                        <th
                                            style={{
                                                color: 'var(--dark-text-secondary)',
                                                fontSize: '0.9rem',
                                                fontWeight: 'normal',
                                                textAlign: 'center',
                                                paddingBottom: '5px',
                                                width: '22%',
                                            }}
                                        >
                                            Y
                                        </th>
                                        <th
                                            style={{
                                                color: 'var(--dark-text-secondary)',
                                                fontSize: '0.9rem',
                                                fontWeight: 'normal',
                                                textAlign: 'center',
                                                paddingBottom: '5px',
                                                width: '22%',
                                            }}
                                        >
                                            Z
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td
                                            style={{
                                                padding: '2px',
                                                textAlign: 'center',
                                                verticalAlign: 'middle',
                                            }}
                                        >
                                            <input
                                                type="checkbox"
                                                name="active"
                                                checked={newDevice.active}
                                                onChange={handleDeviceChange}
                                                style={{
                                                    width: '16px',
                                                    height: '16px',
                                                    accentColor:
                                                        'var(--dark-button-primary)',
                                                }}
                                            />
                                        </td>
                                        <td
                                            style={{
                                                padding: '2px',
                                                textAlign: 'center',
                                                verticalAlign: 'middle',
                                            }}
                                        >
                                            <select
                                                name="type"
                                                value={newDevice.type}
                                                onChange={handleDeviceChange}
                                                style={{
                                                    width: '100%',
                                                    padding: '4px',
                                                    backgroundColor:
                                                        'var(--dark-input-bg)',
                                                    border: '1px solid var(--dark-border)',
                                                    borderRadius: '3px',
                                                    color: 'var(--dark-text)',
                                                    boxSizing: 'border-box',
                                                }}
                                            >
                                                <option value="tx">Tx</option>
                                                <option value="rx">Rx</option>
                                                <option value="int">Int</option>
                                            </select>
                                        </td>
                                        <td
                                            style={{
                                                padding: '2px',
                                                textAlign: 'center',
                                                verticalAlign: 'middle',
                                            }}
                                        >
                                            <input
                                                type="number"
                                                name="x"
                                                value={newDevice.x}
                                                onChange={handleDeviceChange}
                                                style={{
                                                    width: '100%',
                                                    padding: '4px',
                                                    backgroundColor:
                                                        'var(--dark-input-bg)',
                                                    border: '1px solid var(--dark-border)',
                                                    borderRadius: '3px',
                                                    color: 'var(--dark-text)',
                                                    boxSizing: 'border-box',
                                                    textAlign: 'right',
                                                }}
                                            />
                                        </td>
                                        <td
                                            style={{
                                                padding: '2px',
                                                textAlign: 'center',
                                                verticalAlign: 'middle',
                                            }}
                                        >
                                            <input
                                                type="number"
                                                name="y"
                                                value={newDevice.y}
                                                onChange={handleDeviceChange}
                                                style={{
                                                    width: '100%',
                                                    padding: '4px',
                                                    backgroundColor:
                                                        'var(--dark-input-bg)',
                                                    border: '1px solid var(--dark-border)',
                                                    borderRadius: '3px',
                                                    color: 'var(--dark-text)',
                                                    boxSizing: 'border-box',
                                                    textAlign: 'right',
                                                }}
                                            />
                                        </td>
                                        <td
                                            style={{
                                                padding: '2px',
                                                textAlign: 'center',
                                                verticalAlign: 'middle',
                                            }}
                                        >
                                            <input
                                                type="number"
                                                name="z"
                                                value={newDevice.z}
                                                onChange={handleDeviceChange}
                                                style={{
                                                    width: '100%',
                                                    padding: '4px',
                                                    backgroundColor:
                                                        'var(--dark-input-bg)',
                                                    border: '1px solid var(--dark-border)',
                                                    borderRadius: '3px',
                                                    color: 'var(--dark-text)',
                                                    boxSizing: 'border-box',
                                                    textAlign: 'right',
                                                }}
                                                step="0.1"
                                            />
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        {/* 底部按鈕 */}
                        <div
                            style={{
                                marginTop: '15px',
                                display: 'flex',
                                justifyContent: 'space-evenly',
                            }}
                        >
                            <button
                                onClick={handleAddDevice}
                                style={{
                                    padding: '6px 14px',
                                    backgroundColor:
                                        'var(--dark-button-primary)',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '3px',
                                    cursor: newDevice.name
                                        ? 'pointer'
                                        : 'not-allowed',
                                    opacity: newDevice.name ? '1' : '0.6',
                                    fontSize: '0.85rem',
                                }}
                                disabled={!newDevice.name} // 名稱為空時禁用
                            >
                                Apply
                            </button>
                            <button
                                onClick={handleClosePopover}
                                style={{
                                    padding: '6px 14px',
                                    backgroundColor:
                                        'var(--dark-button-secondary)',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '3px',
                                    cursor: 'pointer',
                                    fontSize: '0.85rem',
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
})

export default SceneViewer
