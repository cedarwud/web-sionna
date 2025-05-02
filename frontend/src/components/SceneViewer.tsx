// src/components/SceneViewer.tsx
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { debounce } from 'lodash' // 需要安裝 lodash 依賴
import CoordinateDisplay from './CoordinateDisplay' // 引入子組件
// 引入 API 函數和類型
import {
    createDevice,
    updateDevice,
    deleteDevice,
    DeviceCreate,
    DeviceUpdate,
    Device as BackendDevice,
    DeviceType as BackendDeviceType, // 重命名以避免衝突
    TransmitterType,
    getDeviceById,
} from '../services/api' // <--- 修正路徑
import { Device } from '../App' // <--- 從 App 引入前端 Device 介面

// 定義 Props 接口
interface SceneViewerProps {
    devices: Device[]
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

// 定義靜態路徑指向後端存儲的最後一次成功渲染的圖像
const FALLBACK_IMAGE_PATH = '/rendered_images/scene_with_paths.png'

// 添加座標轉換常量 - 統一管理座標轉換參數
const COORDINATE_TRANSFORM = {
    offsetX: 419, // X轴偏移量
    offsetY: 382, // Y轴偏移量
    scale: 1.4, // 比例因子
}

// 使用 React.memo 包裝組件以避免不必要的重新渲染
const SceneViewer: React.FC<SceneViewerProps> = React.memo(
    ({ devices: propDevices, refreshDeviceData }) => {
        // console.log('--- SceneViewer Component Rendered ---')

        // --- Start: Move helper functions inside component scope ---
        // 轉換前端設備類型到後端
        const mapToBackendType = useCallback(
            (
                frontendType: DeviceType
            ): {
                deviceType: BackendDeviceType
                transmitterType?: TransmitterType
            } => {
                if (frontendType === 'tx') {
                    return { deviceType: BackendDeviceType.TRANSMITTER }
                } else if (frontendType === 'int') {
                    return {
                        deviceType: BackendDeviceType.TRANSMITTER,
                        transmitterType: TransmitterType.INTERFERER,
                    }
                }
                return { deviceType: BackendDeviceType.RECEIVER }
            },
            []
        )

        // 轉換後端設備到前端 NewDevice (用於 Popover)
        const convertBackendToNewDevice = useCallback(
            (backendDevice: BackendDevice): NewDevice => {
                const txType = backendDevice.transmitter?.transmitter_type
                const frontendType: DeviceType =
                    backendDevice.device_type === BackendDeviceType.RECEIVER
                        ? 'rx'
                        : txType === TransmitterType.INTERFERER
                        ? 'int'
                        : 'tx'
                return {
                    name: backendDevice.name,
                    x: backendDevice.x,
                    y: backendDevice.y,
                    z: backendDevice.z,
                    active: backendDevice.active,
                    type: frontendType,
                }
            },
            []
        )
        // --- End: Move helper functions inside component scope ---

        const [imageUrl, setImageUrl] = useState<string | null>(null)
        const [isLoading, setIsLoading] = useState<boolean>(true)
        const [error, setError] = useState<string | null>(null)
        const prevImageUrlRef = useRef<string | null>(null) // 使用 ref 存儲上一個 URL
        const [usingFallback, setUsingFallback] = useState<boolean>(false)
        const [retryCount, setRetryCount] = useState<number>(0)
        const [manualRetryMode, setManualRetryMode] = useState<boolean>(false)

        // 新增滑鼠座標狀態 - 移除 mousePositionRef
        const [mousePositionForDisplay, setMousePositionForDisplay] = useState<{
            x: number
            y: number
            clientX: number
            clientY: number
            sceneX?: number
            sceneY?: number
        } | null>(null) // 專門用於傳遞給 CoordinateDisplay 的狀態

        const imageRef = useRef<HTMLImageElement>(null)

        // 新增彈出視窗相關狀態
        const [showPopover, setShowPopover] = useState<boolean>(false)
        const [popoverPosition, setPopoverPosition] = useState<{
            x: number
            y: number
            clientX: number
            clientY: number
            sceneX?: number
            sceneY?: number
        } | null>(null)
        const [popoverDevice, setPopoverDevice] = useState<NewDevice>({
            name: '',
            x: 0,
            y: 0,
            z: 0,
            active: true,
            type: 'tx',
        })
        const [isEditing, setIsEditing] = useState<boolean>(false)
        const [editingDeviceId, setEditingDeviceId] = useState<number | null>(
            null
        )
        const [hoveredDeviceId, setHoveredDeviceId] = useState<number | null>(
            null
        )
        const [cursorStyle, setCursorStyle] = useState<string>('crosshair')

        // 輔助函數：將圖像座標轉換為場景座標
        const imageToSceneCoords = useCallback(
            (imageX: number, imageY: number): { x: number; y: number } => {
                // 修改Y軸方向，使向下為正
                // sceneX = (imageX - offsetX) / scale
                // sceneY = (imageY - offsetY) / scale  <-- 修改這行，移除負號
                const x = Math.round(
                    (imageX - COORDINATE_TRANSFORM.offsetX) /
                        COORDINATE_TRANSFORM.scale
                )
                const y = Math.round(
                    (imageY - COORDINATE_TRANSFORM.offsetY) /
                        COORDINATE_TRANSFORM.scale
                )
                return { x, y }
            },
            []
        )

        // 輔助函數：將場景座標轉換為圖像座標
        const sceneToImageCoords = useCallback(
            (
                sceneX: number,
                sceneY: number
            ): { x: number; y: number } | null => {
                if (!imageRef.current) return null
                // 修改Y軸方向，使向下為正
                // x = sceneX * scale + offsetX
                // y = sceneY * scale + offsetY  <-- 修改這行，移除減法
                const x = Math.round(
                    sceneX * COORDINATE_TRANSFORM.scale +
                        COORDINATE_TRANSFORM.offsetX
                )
                const y = Math.round(
                    sceneY * COORDINATE_TRANSFORM.scale +
                        COORDINATE_TRANSFORM.offsetY
                )
                return { x, y }
            },
            []
        )

        // 獲取現有設備列表的函數 - 現在直接使用 props
        // const fetchExistingDevices = ... (移除)

        // 生成新設備名稱的函數 - 需要調整以使用 props 中的 devices
        const generateDeviceName = useCallback(
            (type: DeviceType, currentDevices: Device[]) => {
                const prefix =
                    type === 'tx' ? 'tx-' : type === 'rx' ? 'rx-' : 'int-'
                const typeDevices = currentDevices.filter((d) =>
                    d.name.startsWith(prefix)
                )
                let maxNum = 0
                typeDevices.forEach((device) => {
                    const numPart = device.name.replace(prefix, '')
                    const num = parseInt(numPart, 10)
                    if (!isNaN(num) && num > maxNum) {
                        maxNum = num
                    }
                })
                return `${prefix}${maxNum + 1}`
            },
            []
        )

        // 主效果 - 初始載入 - 僅執行一次
        useEffect(() => {
            console.log('--- SceneViewer useEffect triggered for mount ---')

            // 將 AbortController 移入 useEffect
            const controller = new AbortController()
            // 將 fetchImage 的調用也放入 useEffect，並傳遞 controller
            const fetchData = async () => {
                await fetchImage(controller.signal)
            }

            fetchData()

            // 清理函數
            return () => {
                console.log('--- SceneViewer useEffect cleanup ---')
                controller.abort() // 中斷與此 useEffect 實例相關的請求
                if (prevImageUrlRef.current) {
                    URL.revokeObjectURL(prevImageUrlRef.current)
                    console.log(
                        'Cleaned up object URL on unmount:',
                        prevImageUrlRef.current
                    )
                    prevImageUrlRef.current = null
                }
            }
        }, [])

        // 封裝 fetchImage 函數，接收 AbortSignal
        const fetchImage = useCallback(
            async (signal: AbortSignal) => {
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

                const endpointWithCacheBuster = `${rtEndpoint}?t=${new Date().getTime()}`
                console.log(`Fetching image from: ${endpointWithCacheBuster}`)

                let timeoutId: number | null = null

                try {
                    // 設置超時計時器
                    timeoutId = window.setTimeout(() => {
                        console.warn(
                            `Fetch image request timed out after 15s for ${endpointWithCacheBuster}`
                        )
                    }, 15000)

                    const response = await fetch(endpointWithCacheBuster, {
                        signal, // 使用傳入的 signal
                        cache: 'no-cache',
                        headers: {
                            Pragma: 'no-cache',
                            'Cache-Control': 'no-cache',
                        },
                    })

                    // 如果請求成功或失敗（非超時中止），清除超時計時器
                    if (timeoutId !== null) window.clearTimeout(timeoutId)

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
                    // 如果請求被中止，也清除超時
                    if (timeoutId !== null) window.clearTimeout(timeoutId)

                    // 只在錯誤不是 AbortError 時才記錄為失敗 (AbortError 在 StrictMode 下是預期行為)
                    if ((error as Error).name !== 'AbortError') {
                        console.error(
                            `Failed to fetch image from ${rtEndpoint}:`,
                            error
                        )
                        // 嘗試使用備用圖像 - 但改為通過 fetch API 載入，而不是直接使用路徑
                        try {
                            console.log(
                                'Trying to fetch fallback image as blob...'
                            )
                            const fallbackResponse = await fetch(
                                FALLBACK_IMAGE_PATH,
                                {
                                    cache: 'no-cache',
                                    headers: {
                                        Pragma: 'no-cache',
                                        'Cache-Control': 'no-cache',
                                    },
                                }
                            )

                            if (fallbackResponse.ok) {
                                const fallbackBlob =
                                    await fallbackResponse.blob()
                                if (fallbackBlob.size > 0) {
                                    const fallbackUrl =
                                        URL.createObjectURL(fallbackBlob)
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
                            console.error(
                                'Fallback image loading failed:',
                                fallbackError
                            )
                            // 最後的備用：使用直接 URL (可能會導致 404 或內容長度問題，但至少我們嘗試了)
                            setImageUrl(FALLBACK_IMAGE_PATH)
                            setUsingFallback(true)
                            setError(
                                `圖像載入失敗: ${
                                    error instanceof Error
                                        ? error.message
                                        : '未知錯誤'
                                }`
                            )
                        }
                    } else {
                        console.log(
                            'Fetch aborted (likely due to StrictMode or component unmount), ignoring error.'
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
                            fetchImage(new AbortController().signal) // 在 setTimeout 內部調用 fetchImage
                        }, 5000) // 增加到5秒
                    }
                } finally {
                    // 確保 timeoutId 被清除
                    if (timeoutId !== null) window.clearTimeout(timeoutId)
                    setIsLoading(false)
                }
            },
            [retryCount]
        )

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
                console.error(
                    `Image element failed to load src: ${imageUrl}`,
                    e
                )

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
                    const mouseX = Math.round(e.clientX - rect.left)
                    const mouseY = Math.round(e.clientY - rect.top)

                    // 計算場景座標
                    const sceneCoords = imageToSceneCoords(mouseX, mouseY)

                    // 更新顯示座標
                    const newDisplayPosition = {
                        x: mouseX,
                        y: mouseY,
                        clientX: e.clientX,
                        clientY: e.clientY,
                        sceneX: sceneCoords.x,
                        sceneY: sceneCoords.y,
                    }
                    updateMousePositionForDisplay(newDisplayPosition)

                    // 檢查是否有設備在懸停範圍內
                    let foundHoveredDeviceId: number | null = null
                    for (const device of propDevices) {
                        const deviceImageCoords = sceneToImageCoords(
                            device.x,
                            device.y
                        )
                        if (deviceImageCoords) {
                            const distanceX = Math.abs(
                                mouseX - deviceImageCoords.x
                            )
                            const distanceY = Math.abs(
                                mouseY - deviceImageCoords.y
                            )
                            if (distanceX <= 5 && distanceY <= 5) {
                                foundHoveredDeviceId = device.id
                                break // 找到第一個就停止
                            }
                        }
                    }

                    // 更新懸停狀態和游標樣式
                    setHoveredDeviceId(foundHoveredDeviceId)
                    setCursorStyle(
                        foundHoveredDeviceId !== null ? 'pointer' : 'crosshair'
                    )
                }
            },
            [
                propDevices,
                updateMousePositionForDisplay,
                sceneToImageCoords,
                imageToSceneCoords,
            ]
        )

        // 處理滑鼠離開事件
        const handleMouseLeave = useCallback(() => {
            updateMousePositionForDisplay(null)
            setHoveredDeviceId(null)
            setCursorStyle('crosshair')
        }, [updateMousePositionForDisplay])

        // 處理圖片點擊事件 - 修改以處理編輯和新增
        const handleImageClick = useCallback(
            async (e: React.MouseEvent<HTMLImageElement>) => {
                if (imageRef.current) {
                    // 如果點擊時 popover 已開啟，則關閉
                    if (showPopover) {
                        setShowPopover(false)
                        setPopoverPosition(null)
                        setIsEditing(false)
                        setEditingDeviceId(null)
                        return
                    }

                    const rect = imageRef.current.getBoundingClientRect()
                    const clickX = Math.round(e.clientX - rect.left)
                    const clickY = Math.round(e.clientY - rect.top)

                    // 使用統一函數計算場景座標
                    const sceneCoords = imageToSceneCoords(clickX, clickY)

                    // 檢查是否點擊在懸停的設備上
                    if (hoveredDeviceId !== null) {
                        // --- 編輯模式 ---
                        setIsEditing(true)
                        setEditingDeviceId(hoveredDeviceId)

                        try {
                            // 從 API 獲取最新的設備數據
                            const deviceToEdit = await getDeviceById(
                                hoveredDeviceId
                            )
                            const initialPopoverData =
                                convertBackendToNewDevice(deviceToEdit)
                            setPopoverDevice(initialPopoverData)

                            // 設置 popover 位置靠近設備圖標
                            const deviceCoords = sceneToImageCoords(
                                deviceToEdit.x,
                                deviceToEdit.y
                            )
                            const popoverX = deviceCoords
                                ? rect.left + deviceCoords.x
                                : e.clientX
                            const popoverY = deviceCoords
                                ? rect.top + deviceCoords.y
                                : e.clientY

                            setPopoverPosition({
                                x: clickX,
                                y: clickY,
                                clientX: popoverX,
                                clientY: popoverY,
                                sceneX: deviceToEdit.x,
                                sceneY: deviceToEdit.y,
                            })
                            setShowPopover(true)
                        } catch (error) {
                            console.error(
                                `獲取設備 ${hoveredDeviceId} 數據失敗:`,
                                error
                            )
                            alert(
                                `無法加載設備數據: ${
                                    error instanceof Error
                                        ? error.message
                                        : '未知錯誤'
                                }`
                            )
                            setIsEditing(false)
                            setEditingDeviceId(null)
                        }
                    } else {
                        // --- 新增模式 ---
                        setIsEditing(false)
                        setEditingDeviceId(null)

                        setPopoverPosition({
                            x: clickX,
                            y: clickY,
                            clientX: e.clientX,
                            clientY: e.clientY,
                            sceneX: sceneCoords.x,
                            sceneY: sceneCoords.y,
                        })

                        // 生成名稱並設置初始 popover 數據
                        const initialDevice = {
                            z: popoverDevice.z,
                            active: popoverDevice.active,
                            type: popoverDevice.type,
                            x: sceneCoords.x,
                            y: sceneCoords.y,
                            name: generateDeviceName(
                                popoverDevice.type,
                                propDevices
                            ),
                        }
                        setPopoverDevice(initialDevice)
                        setShowPopover(true)
                    }
                }
            },
            [
                showPopover,
                hoveredDeviceId,
                propDevices,
                generateDeviceName,
                popoverDevice.z,
                popoverDevice.active,
                popoverDevice.type,
                sceneToImageCoords,
                imageToSceneCoords,
            ]
        )

        // 關閉彈出視窗
        const handleClosePopover = useCallback(() => {
            setShowPopover(false)
            setPopoverPosition(null)
            setIsEditing(false)
            setEditingDeviceId(null)
        }, [])

        // 處理 Popover 內設備屬性變更
        const handleDeviceChange = useCallback(
            (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
                const { name, value, type } = e.target
                // Correctly get 'checked' for checkboxes
                const checked = (e.target as HTMLInputElement).checked

                setPopoverDevice((prev) => {
                    let updatedDevice = { ...prev }

                    if (name === 'type') {
                        const newType = value as DeviceType
                        const currentDevice = propDevices.find(
                            (d) => d.id === editingDeviceId
                        )
                        const isDefaultNameFormat =
                            currentDevice &&
                            /^(tx|rx|int)-[0-9]+$/.test(currentDevice.name)

                        if (!isEditing || isDefaultNameFormat) {
                            const newName = generateDeviceName(
                                newType,
                                propDevices
                            )
                            updatedDevice = {
                                ...updatedDevice,
                                type: newType,
                                name: newName,
                            }
                        } else {
                            updatedDevice = { ...updatedDevice, type: newType }
                        }
                    } else if (name === 'active') {
                        // Use the 'checked' variable obtained above
                        updatedDevice = { ...updatedDevice, active: checked }
                    } else if (name === 'name') {
                        updatedDevice = { ...updatedDevice, name: value }
                    } else {
                        // Use 'type' attribute from target for number check
                        const newValue =
                            type === 'number' ? parseFloat(value) || 0 : value
                        updatedDevice = { ...updatedDevice, [name]: newValue }
                    }
                    return updatedDevice
                })
            },
            [propDevices, generateDeviceName, isEditing, editingDeviceId]
        )

        // 處理應用 Popover 的更改 (新增或編輯)
        const handleApplyPopover = useCallback(async () => {
            try {
                const { deviceType, transmitterType: originalTransmitterType } =
                    mapToBackendType(popoverDevice.type)

                // Determine the final transmitterType for the payload
                const finalTransmitterType =
                    deviceType === BackendDeviceType.TRANSMITTER &&
                    !originalTransmitterType
                        ? TransmitterType.SIGNAL // Explicitly set SIGNAL for 'tx'
                        : originalTransmitterType // Use INTERFERER for 'int' or undefined for 'rx'

                if (isEditing && editingDeviceId !== null) {
                    // --- 更新設備 ---
                    console.log(
                        `準備更新設備 ID: ${editingDeviceId}`,
                        popoverDevice
                    )
                    const devicePayload: DeviceUpdate = {
                        name: popoverDevice.name,
                        x: popoverDevice.x,
                        y: popoverDevice.y,
                        z: popoverDevice.z,
                        active: popoverDevice.active,
                        device_type: deviceType,
                        transmitter_type: finalTransmitterType,
                    }
                    console.log(
                        'Calling updateDevice with payload:',
                        devicePayload
                    )
                    const updated = await updateDevice(
                        editingDeviceId,
                        devicePayload
                    )
                    console.log('Device updated successfully:', updated)
                    alert(`成功更新設備: ${updated.name}`)
                } else {
                    // --- 新增設備 ---
                    console.log('準備新增設備', popoverDevice)
                    const devicePayload: DeviceCreate = {
                        name: popoverDevice.name,
                        x: popoverDevice.x,
                        y: popoverDevice.y,
                        z: popoverDevice.z,
                        active: popoverDevice.active,
                        device_type: deviceType,
                        transmitter_type: finalTransmitterType,
                    }
                    console.log(
                        'Calling createDevice with payload:',
                        devicePayload
                    )
                    const created = await createDevice(devicePayload)
                    console.log('Device created successfully:', created)
                    alert(`成功新增設備: ${created.name}`)
                    // 重置 Popover 狀態為下次新增做準備
                    setPopoverDevice({
                        name: '',
                        x: 0,
                        y: 0,
                        z: 0,
                        active: true,
                        type: 'tx',
                    })
                }

                handleClosePopover()
                fetchImage(new AbortController().signal) // 更新場景圖
                refreshDeviceData() // 更新 App 狀態
            } catch (error: any) {
                console.error(
                    `Failed to ${isEditing ? 'update' : 'add'} device:`,
                    error
                )
                let errorMessage = `${isEditing ? '更新' : '新增'}設備失敗`
                if (error.response?.data?.detail) {
                    if (Array.isArray(error.response.data.detail)) {
                        errorMessage +=
                            ': ' +
                            error.response.data.detail
                                .map(
                                    (item: any) =>
                                        item.msg || JSON.stringify(item)
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
        }, [
            popoverDevice,
            isEditing,
            editingDeviceId,
            fetchImage,
            refreshDeviceData,
            handleClosePopover,
            mapToBackendType,
        ])

        // 新增：處理刪除設備
        const handleDeleteDevice = useCallback(async () => {
            if (!isEditing || editingDeviceId === null) {
                console.warn('Delete called without editing context')
                return
            }

            if (
                !window.confirm(`確定要刪除設備 "${popoverDevice.name}" 嗎？`)
            ) {
                return
            }

            try {
                console.log(`Calling deleteDevice for ID: ${editingDeviceId}`)
                await deleteDevice(editingDeviceId)
                console.log('Device deleted successfully')
                alert(`成功刪除設備: ${popoverDevice.name}`)

                handleClosePopover()
                fetchImage(new AbortController().signal) // 更新場景圖
                refreshDeviceData() // 更新 App 狀態
            } catch (error: any) {
                console.error(
                    `Failed to delete device ${editingDeviceId}:`,
                    error
                )
                let errorMessage = '刪除設備失敗'
                if (error.response?.data?.detail) {
                    errorMessage += ': ' + error.response.data.detail
                } else if (error.message) {
                    errorMessage += ': ' + error.message
                }
                alert(errorMessage)
            }
        }, [
            isEditing,
            editingDeviceId,
            popoverDevice.name,
            fetchImage,
            refreshDeviceData,
            handleClosePopover,
        ])

        // 使用固定標題
        const title = '場景與路徑 (Etoile)'

        const [maxImageHeight, setMaxImageHeight] = useState<string>('auto') // 新增狀態儲存最大高度

        // Effect to calculate and update max image height
        useEffect(() => {
            const calculateHeight = () => {
                const navbarHeight = 60 // Navbar height in pixels
                const availableHeight = window.innerHeight - navbarHeight
                setMaxImageHeight(`${availableHeight}px`)
            }

            calculateHeight() // Initial calculation
            window.addEventListener('resize', calculateHeight) // Update on resize

            // Cleanup listener on component unmount
            return () => window.removeEventListener('resize', calculateHeight)
        }, []) // Empty dependency array means this runs once on mount and cleans up on unmount

        return (
            <div
                style={{
                    position: 'relative',
                    backgroundColor: 'rgb(127, 127, 127)',
                }}
            >
                {isLoading && <p>正在載入路徑圖...</p>}
                {/* 只有在 imageUrl 存在且 loading 完成後才顯示 img，或在 loading 時顯示佔位符 */}
                <div style={{ position: 'relative' }}>
                    {imageUrl && (
                        <img
                            ref={imageRef}
                            key={imageUrl}
                            src={imageUrl}
                            alt={title}
                            onLoad={handleImageLoad}
                            onError={handleImageError}
                            onMouseMove={handleMouseMove}
                            onMouseLeave={handleMouseLeave}
                            onClick={handleImageClick}
                            style={{
                                maxWidth: '100%',
                                maxHeight: maxImageHeight, // 使用計算後的最大高度
                                display: isLoading ? 'none' : 'block',
                                cursor: cursorStyle,
                                objectFit: 'contain',
                                margin: '0 auto', // 水平置中
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
                                top: `${popoverPosition.clientY + 10}px`,
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
                                    value={popoverDevice.name}
                                    onChange={handleDeviceChange}
                                    placeholder="設備名稱"
                                    style={{
                                        width: '100%',
                                        padding: '8px 35px 8px 10px',
                                        backgroundColor:
                                            'var(--dark-component)',
                                        color: 'var(--dark-text)',
                                        border: 'none',
                                        borderRadius: '3px',
                                        fontSize: '16px',
                                        textAlign: 'center',
                                        boxSizing: 'border-box',
                                    }}
                                />
                                <button
                                    onClick={
                                        isEditing
                                            ? handleDeleteDevice
                                            : handleClosePopover
                                    }
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
                                    title={isEditing ? '刪除設備' : '關閉'}
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
                                                    checked={
                                                        popoverDevice.active
                                                    }
                                                    onChange={
                                                        handleDeviceChange
                                                    }
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
                                                    value={popoverDevice.type}
                                                    onChange={
                                                        handleDeviceChange
                                                    }
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
                                                    <option value="tx">
                                                        Tx
                                                    </option>
                                                    <option value="rx">
                                                        Rx
                                                    </option>
                                                    <option value="int">
                                                        Int
                                                    </option>
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
                                                    value={popoverDevice.x}
                                                    onChange={
                                                        handleDeviceChange
                                                    }
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
                                                    value={popoverDevice.y}
                                                    onChange={
                                                        handleDeviceChange
                                                    }
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
                                                    value={popoverDevice.z}
                                                    onChange={
                                                        handleDeviceChange
                                                    }
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

                            {/* 底部按鈕 - 移除編輯模式下的 Delete 按鈕 */}
                            <div
                                style={{
                                    marginTop: '15px',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                }}
                            >
                                {/* Apply Button (通用) */}
                                <button
                                    onClick={handleApplyPopover}
                                    style={{
                                        padding: '6px 14px',
                                        backgroundColor:
                                            'var(--dark-button-primary)',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: popoverDevice.name
                                            ? 'pointer'
                                            : 'not-allowed',
                                        opacity: popoverDevice.name ? 1 : 0.6,
                                        fontSize: '0.85rem',
                                        flexGrow: 1, // 讓按鈕均分空間
                                        margin: '0 5px',
                                    }}
                                    disabled={!popoverDevice.name}
                                >
                                    Apply
                                </button>
                                {/* Cancel Button (通用) */}
                                <button
                                    onClick={handleClosePopover} // 這個 Cancel 按鈕維持關閉功能
                                    style={{
                                        padding: '6px 14px',
                                        backgroundColor:
                                            'var(--dark-button-secondary)',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer',
                                        fontSize: '0.85rem',
                                        flexGrow: 1,
                                        margin: '0 5px',
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
    }
)

export default SceneViewer
