// src/App.tsx
import { useState, useEffect, useCallback } from 'react'
import SceneView from './components/SceneView'
import Layout from './components/Layout'
import Sidebar from './components/Sidebar'
import Navbar from './components/Navbar'
import SceneViewer from './components/SceneViewer'
import ConstellationViewer from './components/ConstellationViewer'
import './App.css'
import {
    Device as BackendDevice,
    DeviceType as BackendDeviceType,
    TransmitterType,
    getDevices,
    createDevice,
    updateDevice,
    deleteDevice,
} from './services/api'

// 前端設備類型（簡化版）
export type DeviceType = 'tx' | 'rx' | 'int'

// 前端設備介面
export interface Device {
    id: number
    name: string // 添加名稱字段
    x: number
    y: number
    z: number
    active: boolean
    type: DeviceType
    transmitterType?: TransmitterType // 新增可選欄位
}

// 轉換後端設備類型到前端設備類型
const mapDeviceType = (
    backendType: BackendDeviceType,
    transmitterType?: TransmitterType
): DeviceType => {
    if (backendType === BackendDeviceType.TRANSMITTER) {
        if (transmitterType === TransmitterType.INTERFERER) {
            return 'int'
        }
        return 'tx'
    }
    return 'rx'
}

// 轉換前端設備類型到後端設備類型
const mapToBackendType = (
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
}

// 轉換後端設備資料到前端設備格式
const convertBackendToFrontend = (backendDevice: BackendDevice): Device => {
    // 從嵌套結構中獲取 transmitter_type
    const txType = backendDevice.transmitter?.transmitter_type
    return {
        id: backendDevice.id,
        name: backendDevice.name,
        x: backendDevice.x,
        y: backendDevice.y,
        z: backendDevice.z,
        active: backendDevice.active,
        type: mapDeviceType(
            backendDevice.device_type,
            txType // 使用從嵌套結構獲取的值
        ),
        transmitterType: txType, // 將獲取的值存儲到前端介面
    }
}

// 輔助函數：計算啟用設備的數量
const countActiveDevices = (
    deviceList: Device[]
): { activeTx: number; activeRx: number } => {
    let activeTx = 0
    let activeRx = 0
    deviceList.forEach((d) => {
        if (d.active) {
            if (d.type === 'tx') {
                activeTx++
            } else if (d.type === 'rx') {
                activeRx++
            }
            // 'int' 類型雖然是 transmitter，但規則是針對 'tx' 和 'rx'
        }
    })
    return { activeTx, activeRx }
}

function App() {
    const [tempDevices, setTempDevices] = useState<Device[]>([])
    const [originalDevices, setOriginalDevices] = useState<Device[]>([])
    const [loading, setLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [apiStatus, setApiStatus] = useState<
        'disconnected' | 'connected' | 'error'
    >('disconnected')
    const [hasTempDevices, setHasTempDevices] = useState<boolean>(false)
    const [activeComponent, setActiveComponent] = useState<string>('3DRT')

    // 從API獲取設備數據
    const fetchDevices = useCallback(async () => {
        try {
            setLoading(true)
            setApiStatus('disconnected')
            console.log('嘗試從API獲取設備數據...')
            const backendDevices = await getDevices() // backendDevices 現在有嵌套結構
            console.log('成功獲取設備數據:', backendDevices)

            const frontendDevices = backendDevices.map(convertBackendToFrontend)

            setTempDevices(frontendDevices)
            setOriginalDevices(frontendDevices)
            setError(null)
            setApiStatus('connected')
        } catch (err: any) {
            console.error('獲取設備失敗:', err)
            const errorMessage = err.message || '未知錯誤'
            setError(`獲取設備數據時發生錯誤: ${errorMessage}`)
            setApiStatus('error')

            // 如果API連接失敗，使用一些默認設備數據進行開發測試
            const defaultDevices: Device[] = Array.from(
                { length: 3 },
                (_, i) => ({
                    id: -(i + 1), // 負數ID表示臨時數據
                    name: `測試設備 ${i + 1}`,
                    x: i * 10,
                    y: i * 10,
                    z: 0.0,
                    active: true,
                    type: ['tx', 'rx', 'int'][i % 3] as DeviceType,
                })
            )
            setTempDevices(defaultDevices)
            setOriginalDevices(defaultDevices)
        } finally {
            setLoading(false)
        }
    }, [])

    // Effect to fetch devices on mount
    useEffect(() => {
        fetchDevices()
    }, [fetchDevices])

    // Define the refresh function based on the stable fetchDevices
    const refreshDeviceData = useCallback(() => {
        fetchDevices()
    }, [fetchDevices])

    // 處理應用更改 - 將修改保存到後端
    const handleApply = async () => {
        // --- 開始：加入檢查邏輯 ---
        const { activeTx: currentActiveTx, activeRx: currentActiveRx } =
            countActiveDevices(tempDevices)

        if (currentActiveTx < 1 || currentActiveRx < 1) {
            alert(
                '套用失敗：操作後必須至少保留一個啟用的發射器 (tx) 和一個啟用的接收器 (rx)。請檢查設備的啟用狀態。'
            )
            // 可以選擇是否恢復更改，例如：
            // handleCancel();
            return // 阻止執行 API 呼叫
        }
        // --- 結束：加入檢查邏輯 ---

        if (apiStatus !== 'connected') {
            setError('無法保存更改：API連接未建立')
            return
        }

        try {
            setLoading(true)
            setError(null)

            // 1. 處理需要創建的新設備（ID 為負數的臨時設備）
            const newDevices = tempDevices.filter((device) => device.id < 0)

            // 2. 找出需要更新的已存在設備
            const devicesToUpdate = tempDevices.filter((tempDevice) => {
                // 只處理已存在於後端的設備（ID > 0）
                if (tempDevice.id <= 0) return false

                // 找到對應的原始設備
                const originalDevice = originalDevices.find(
                    (org) => org.id === tempDevice.id
                )

                // 如果找不到原始設備，或者設備內容與原始狀態不同，則標記為需要更新
                return (
                    !originalDevice ||
                    JSON.stringify(tempDevice) !==
                        JSON.stringify(originalDevice)
                )
            })

            if (newDevices.length === 0 && devicesToUpdate.length === 0) {
                console.log('沒有檢測到需要保存的更改。')
                setLoading(false)
                return // 沒有更改，提前退出
            }

            // 首先創建新設備
            for (const device of newDevices) {
                console.log('準備創建新設備:', device)

                const { deviceType, transmitterType } = mapToBackendType(
                    device.type
                )

                const backendData = {
                    name: device.name,
                    x: device.x,
                    y: device.y,
                    z: device.z,
                    active: device.active,
                    device_type: deviceType,
                    transmitter_type: transmitterType,
                }

                console.log('調用 API 創建設備，數據:', backendData)
                try {
                    await createDevice(backendData)
                    console.log('新設備創建成功')
                } catch (error: any) {
                    // 詳細記錄錯誤
                    console.error(
                        '創建設備錯誤詳情:',
                        error.response?.data || error.message
                    )

                    // 處理422錯誤的詳細信息
                    let errorDetail = '未知錯誤'
                    if (error.response?.data?.detail) {
                        if (Array.isArray(error.response.data.detail)) {
                            // 422錯誤通常會返回一個詳細信息數組
                            errorDetail = error.response.data.detail
                                .map((item: any) => {
                                    if (item.msg && item.loc) {
                                        return `${item.msg} at ${item.loc.join(
                                            '.'
                                        )}`
                                    }
                                    return JSON.stringify(item)
                                })
                                .join('; ')
                        } else {
                            errorDetail = error.response.data.detail
                        }
                    } else {
                        errorDetail = error.message || '未知錯誤'
                    }

                    throw new Error(
                        `創建設備 "${device.name}" 失敗: ${errorDetail}`
                    )
                }
            }

            // 然後更新已有設備
            for (const device of devicesToUpdate) {
                const { deviceType, transmitterType } = mapToBackendType(
                    device.type
                )

                const backendData = {
                    name: device.name,
                    x: device.x,
                    y: device.y,
                    z: device.z,
                    active: device.active,
                    device_type: deviceType,
                    transmitter_type: transmitterType,
                }

                console.log(`正在更新設備 ID: ${device.id}，數據:`, backendData)
                try {
                    await updateDevice(device.id, backendData) // 調用後端修改 API
                    console.log(`設備 ID: ${device.id} 更新成功`)
                } catch (error: any) {
                    // 詳細記錄錯誤
                    console.error(
                        `更新設備錯誤詳情:`,
                        error.response?.data || error.message
                    )

                    // 處理422錯誤的詳細信息
                    let errorDetail = '未知錯誤'
                    if (error.response?.data?.detail) {
                        if (Array.isArray(error.response.data.detail)) {
                            // 422錯誤通常會返回一個詳細信息數組
                            errorDetail = error.response.data.detail
                                .map((item: any) => {
                                    if (item.msg && item.loc) {
                                        return `${item.msg} at ${item.loc.join(
                                            '.'
                                        )}`
                                    }
                                    return JSON.stringify(item)
                                })
                                .join('; ')
                        } else {
                            errorDetail = error.response.data.detail
                        }
                    } else {
                        errorDetail = error.message || '未知錯誤'
                    }

                    throw new Error(
                        `更新設備 ID: ${device.id} 失敗: ${errorDetail}`
                    )
                }
            }

            // 所有更改完成後，重新獲取設備列表
            console.log('所有更新完成，正在重新獲取設備列表...')
            const updatedBackendDevices = await getDevices()
            const updatedFrontendDevices = updatedBackendDevices.map(
                convertBackendToFrontend
            )
            setTempDevices(updatedFrontendDevices)
            setOriginalDevices(updatedFrontendDevices) // 更新原始狀態為最新已保存狀態
            // 重置臨時設備標記
            setHasTempDevices(false)
            console.log('設備列表已更新，前端應已觸發重新渲染')
        } catch (err: any) {
            console.error('保存設備更新失敗:', err)
            const errorMessage = err.message || '未知錯誤'
            setError(`保存設備更新時發生錯誤: ${errorMessage}`)
        } finally {
            setLoading(false)
        }
    }

    // 處理取消更改
    const handleCancel = () => {
        setTempDevices([...originalDevices])
        setHasTempDevices(false)
        setError(null)
    }

    // 處理刪除設備
    const handleDeleteDevice = async (id: number) => {
        // 如果是新添加的、未保存的設備 (ID 為負數)
        if (id < 0) {
            setTempDevices((prev) => prev.filter((device) => device.id !== id))
            // 標記有臨時更改，因為我們移除了列表中的一項
            setHasTempDevices(true)
            console.log(`已從前端移除臨時設備 ID: ${id}`)
            return // 直接返回，不執行後續 API 調用
        }

        // --- 開始：現有設備的檢查邏輯 ---
        // 模擬刪除後的裝置列表
        const devicesAfterDelete = tempDevices.filter(
            (device) => device.id !== id
        )
        const { activeTx: futureActiveTx, activeRx: futureActiveRx } =
            countActiveDevices(devicesAfterDelete)

        if (futureActiveTx < 1 || futureActiveRx < 1) {
            alert(
                '刪除失敗：操作後必須至少保留一個啟用的發射器 (tx) 和一個啟用的接收器 (rx)。'
            )
            return // 阻止執行 API 呼叫
        }
        // --- 結束：現有設備的檢查邏輯 ---

        if (apiStatus !== 'connected') {
            setError('無法刪除設備：API連接未建立')
            return
        }

        // 添加確認對話框
        if (!window.confirm('確定要刪除這個設備嗎？此操作將立即生效。')) {
            return
        }

        try {
            setLoading(true)
            setError(null)
            console.log(`調用 API 刪除設備 ID: ${id}`)
            await deleteDevice(id) // 調用後端刪除 API
            console.log(`設備 ID: ${id} 刪除成功`)

            // 從前端狀態中移除已刪除的設備
            setTempDevices((prev) => prev.filter((device) => device.id !== id))
            setOriginalDevices((prev) =>
                prev.filter((device) => device.id !== id)
            )
            // 刪除後，重新檢查是否有未保存的更改
            setHasTempDevices(
                JSON.stringify(tempDevices) !== JSON.stringify(originalDevices)
            )
        } catch (err: any) {
            console.error(`刪除設備ID ${id} 失敗:`, err)
            setError(
                `刪除設備 ID: ${id} 失敗: ${
                    err.response?.data?.detail || err.message || '未知錯誤'
                }`
            )
        } finally {
            setLoading(false)
        }
    }

    // 處理添加新設備
    const handleAddDevice = () => {
        // 產生一個負數 ID，用於標識臨時設備
        const tempId = -Math.floor(Math.random() * 1000000) - 1

        // 根據選定的設備類型生成不同的名稱前綴
        const getPrefix = (type: DeviceType = 'tx') => {
            switch (type) {
                case 'tx':
                    return 'tx-'
                case 'rx':
                    return 'rx-'
                case 'int':
                    return 'int-'
                default:
                    return 'device-'
            }
        }

        // 獲取已存在的設備名稱列表，以確保不會重複
        const existingNames = tempDevices.map((device) => device.name)

        // 默認設備類型
        const defaultType: DeviceType = 'tx'
        const prefix = getPrefix(defaultType)

        // 尋找一個可用的名稱（不在現有名稱列表中）
        let index = 1
        let newName = `${prefix}${index}`
        while (existingNames.includes(newName)) {
            index++
            newName = `${prefix}${index}`
        }

        // 創建一個新的臨時設備
        const newDevice: Device = {
            id: tempId,
            name: newName,
            x: 0,
            y: 0,
            z: 0,
            active: true,
            type: defaultType,
        }

        // 更新 tempDevices 狀態，添加新的臨時設備
        setTempDevices((prev) => [...prev, newDevice])
        // 標記有臨時設備
        setHasTempDevices(true)

        // 注意：此時並不調用 API 創建設備
        console.log('已在前端創建臨時設備:', newDevice)
    }

    // 處理單個設備屬性更改
    const handleDeviceChange = (
        id: number,
        field: keyof Device,
        value: any
    ) => {
        setTempDevices((prev) => {
            if (field === 'type') {
                const deviceToUpdate = prev.find((d) => d.id === id)
                if (deviceToUpdate) {
                    const currentName = deviceToUpdate.name
                    const isDefaultNamingFormat = /^(tx|rx|int)-\d+$/.test(
                        currentName
                    )
                    const newType = value as DeviceType

                    // Only auto-update name if it was default or it's a new device
                    if (isDefaultNamingFormat || deviceToUpdate.id < 0) {
                        const getPrefix = (type: DeviceType): string => {
                            switch (type) {
                                case 'tx':
                                    return 'tx-'
                                case 'rx':
                                    return 'rx-'
                                case 'int':
                                    return 'int-'
                                default:
                                    return 'device-'
                            }
                        }
                        const newPrefix = getPrefix(newType)

                        // Find the max number among existing devices of the NEW type (excluding the current one)
                        let maxNum = 0
                        prev.forEach((device) => {
                            // Skip the device being edited
                            if (device.id === id) return

                            if (device.name.startsWith(newPrefix)) {
                                const match = device.name.match(/-(\d+)$/)
                                if (match) {
                                    const num = parseInt(match[1], 10)
                                    if (!isNaN(num) && num > maxNum) {
                                        maxNum = num
                                    }
                                }
                            }
                        })

                        const newNumber = maxNum + 1
                        const newName = `${newPrefix}${newNumber}`

                        // Note: Uniqueness check might be redundant now but kept for safety
                        let uniqueName = newName
                        let suffix = newNumber
                        const otherNames = prev
                            .filter((d) => d.id !== id)
                            .map((d) => d.name)
                        while (otherNames.includes(uniqueName)) {
                            suffix++
                            uniqueName = `${newPrefix}${suffix}`
                        }

                        // Update type and the newly generated name
                        return prev.map((device) =>
                            device.id === id
                                ? { ...device, type: newType, name: uniqueName }
                                : device
                        )
                    }
                    // If name wasn't default and it's not a new device, just update type
                    else {
                        return prev.map((device) =>
                            device.id === id
                                ? { ...device, type: newType } // Only update type
                                : device
                        )
                    }
                }
            }

            // Handle other field changes (non-type)
            return prev.map((device) =>
                device.id === id ? { ...device, [field]: value } : device
            )
        })

        // Mark changes if a persistent device (id > 0) was modified
        if (id > 0) {
            const originalDevice = originalDevices.find((dev) => dev.id === id)
            const currentDevice = tempDevices.find((d) => d.id === id)
            // Check against original state or if the value actually changed compared to current temp state
            if (
                originalDevice &&
                JSON.stringify(currentDevice) !== JSON.stringify(originalDevice)
            ) {
                setHasTempDevices(true)
            }
        }
    }

    // 處理導航菜單點擊
    const handleMenuClick = (component: string) => {
        setActiveComponent(component)
    }

    // 渲染當前選中的組件
    const renderActiveComponent = () => {
        switch (activeComponent) {
            case '2DRT':
                return (
                    <SceneViewer
                        devices={tempDevices}
                        refreshDeviceData={refreshDeviceData}
                    />
                )
            case '3DRT':
                return <SceneView devices={tempDevices} />
            case 'constellation':
                return <ConstellationViewer />
            default:
                return (
                    <SceneViewer
                        devices={tempDevices}
                        refreshDeviceData={refreshDeviceData}
                    />
                )
        }
    }

    if (loading) {
        return <div className="loading">載入中...</div>
    }

    return (
        <div className="app-container">
            <Navbar
                onMenuClick={handleMenuClick}
                activeComponent={activeComponent}
            />
            <div className="content-wrapper">
                <Layout
                    sidebar={
                        <Sidebar
                            devices={tempDevices}
                            onDeviceChange={handleDeviceChange}
                            onDeleteDevice={handleDeleteDevice}
                            onAddDevice={handleAddDevice}
                            onApply={handleApply}
                            onCancel={handleCancel}
                            loading={loading}
                            apiStatus={apiStatus}
                            onRefresh={refreshDeviceData}
                            hasTempDevices={hasTempDevices}
                        />
                    }
                    content={renderActiveComponent()}
                />
            </div>
        </div>
    )
}

export default App
