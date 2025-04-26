// src/App.tsx
import { useState, useEffect } from 'react'
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
type DeviceType = 'tx' | 'rx' | 'int'

// 前端設備介面
interface Device {
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

function App() {
    const [devices, setDevices] = useState<Device[]>([])
    const [tempDevices, setTempDevices] = useState<Device[]>([])
    const [originalDevices, setOriginalDevices] = useState<Device[]>([])
    const [loading, setLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [apiStatus, setApiStatus] = useState<
        'disconnected' | 'connected' | 'error'
    >('disconnected')
    const [selectedScene, setSelectedScene] = useState<string>('Etoile')
    const [hasTempDevices, setHasTempDevices] = useState<boolean>(false)

    // 從API獲取設備數據
    useEffect(() => {
        const fetchDevices = async () => {
            try {
                setLoading(true)
                setApiStatus('disconnected')
                console.log('嘗試從API獲取設備數據...')
                const backendDevices = await getDevices() // backendDevices 現在有嵌套結構
                console.log('成功獲取設備數據:', backendDevices) // 保留這個基礎的，用於確認數據獲取

                // map 操作會使用更新後的 convertBackendToFrontend
                const frontendDevices = backendDevices.map(
                    convertBackendToFrontend
                )

                setDevices(frontendDevices)
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
                setDevices(defaultDevices)
                setTempDevices(defaultDevices)
                setOriginalDevices(defaultDevices)
            } finally {
                setLoading(false)
            }
        }

        fetchDevices()
    }, [])

    // 處理應用更改 - 將修改保存到後端
    const handleApply = async () => {
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
                await createDevice(backendData)
                console.log('新設備創建成功')
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
                    // 確保傳遞 transmitter_type，即使是 undefined
                    transmitter_type: transmitterType,
                }

                console.log(`正在更新設備 ID: ${device.id}，數據:`, backendData)
                await updateDevice(device.id, backendData) // 調用後端修改 API
                console.log(`設備 ID: ${device.id} 更新成功`)
            }

            // 所有更改完成後，重新獲取設備列表
            console.log('所有更新完成，正在重新獲取設備列表...')
            const updatedBackendDevices = await getDevices()
            const updatedFrontendDevices = updatedBackendDevices.map(
                convertBackendToFrontend
            )
            setDevices(updatedFrontendDevices)
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

    // 處理場景選擇
    const handleSceneChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedScene(e.target.value)
    }

    // 處理單個設備屬性更改
    const handleDeviceChange = (
        id: number,
        field: keyof Device,
        value: any
    ) => {
        setTempDevices((prev) =>
            prev.map((device) =>
                device.id === id ? { ...device, [field]: value } : device
            )
        )

        // 如果修改了現有設備，標記有臨時變更
        if (id > 0) {
            // 找到對應的原始設備
            const originalDevice = originalDevices.find((dev) => dev.id === id)
            // 檢查當前值與原始值是否不同
            if (originalDevice && originalDevice[field] !== value) {
                setHasTempDevices(true)
            }
        }
    }

    // 處理刪除設備
    const handleDeleteDevice = async (id: number) => {
        // 判斷是否為臨時設備（ID < 0）
        if (id < 0) {
            // 如果是臨時設備，直接從前端狀態中移除
            setTempDevices((prev) => prev.filter((device) => device.id !== id))
            console.log(`已從前端移除臨時設備 ID: ${id}`)
            return
        }

        // 以下是處理實際存在於後端的設備
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
            console.log(`嘗試刪除設備 ID: ${id}`)
            await deleteDevice(id)
            console.log(`設備 ID: ${id} 刪除成功，正在重新獲取列表...`)

            // 重新獲取設備列表以反映刪除
            const updatedBackendDevices = await getDevices()
            const updatedFrontendDevices = updatedBackendDevices.map(
                convertBackendToFrontend
            )
            setDevices(updatedFrontendDevices)
            setTempDevices(updatedFrontendDevices)
            setOriginalDevices(updatedFrontendDevices)
            console.log('設備列表已更新')
        } catch (err: any) {
            console.error(`刪除設備 ID: ${id} 失敗:`, err)
            const errorMessage = err.message || '未知錯誤'
            setError(`刪除設備時發生錯誤: ${errorMessage}`)
        } finally {
            setLoading(false)
        }
    }

    // 處理添加新設備
    const handleAddDevice = () => {
        // 產生一個負數 ID，用於標識臨時設備
        const tempId = -Math.floor(Math.random() * 1000000) - 1

        // 計算現有的 tx 設備數量（只計算 type 為 'tx' 的設備，不包括 'int'）
        const existingTxCount = tempDevices.filter(
            (device) => device.type === 'tx'
        ).length

        // 創建一個新的臨時設備，名稱格式為 "tx_編號"
        const newDevice: Device = {
            id: tempId,
            name: `tx_${existingTxCount + 1}`,
            x: 0,
            y: 0,
            z: 0,
            active: true,
            type: 'tx', // 預設為 Tx
        }

        // 更新 tempDevices 狀態，添加新的臨時設備
        setTempDevices((prev) => [...prev, newDevice])
        // 標記有臨時設備
        setHasTempDevices(true)

        // 注意：此時並不調用 API 創建設備
        console.log('已在前端創建臨時設備:', newDevice)
    }

    if (loading) {
        return <div className="loading">載入中...</div>
    }

    return (
        <div className="App">
            <div className="app-container">
                <div className="sidebar">
                    <div className="sidebar-header">
                        <div className="button-group">
                            <button
                                onClick={handleApply}
                                disabled={apiStatus !== 'connected'}
                            >
                                Apply
                            </button>
                            <button onClick={handleCancel}>Cancel</button>
                        </div>
                        <div className="scene-selector">
                            <select
                                value={selectedScene}
                                onChange={handleSceneChange}
                            >
                                <option value="Etoile">Etoile</option>
                                <option value="國立陽明交通大學">
                                    國立陽明交通大學
                                </option>
                                <option value="國立臺北大學">
                                    國立臺北大學
                                </option>
                            </select>
                        </div>
                    </div>
                    {error && <div className="error-message">{error}</div>}
                    <div className="devices-list">
                        {tempDevices.map((device) => (
                            <div key={device.id} className="device-item">
                                <div className="device-header">
                                    <input
                                        type="text"
                                        value={device.name}
                                        onChange={(e) =>
                                            handleDeviceChange(
                                                device.id,
                                                'name',
                                                e.target.value
                                            )
                                        }
                                        className="device-name-input"
                                    />
                                    <button
                                        className="delete-btn"
                                        onClick={() =>
                                            handleDeleteDevice(device.id)
                                        }
                                    >
                                        &#10006;
                                    </button>
                                </div>
                                <div className="device-content">
                                    <table className="device-table">
                                        <thead>
                                            <tr>
                                                <th></th>
                                                <th>Type</th>
                                                <th>X</th>
                                                <th>Y</th>
                                                <th>Z</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td>
                                                    <input
                                                        type="checkbox"
                                                        checked={device.active}
                                                        onChange={(e) =>
                                                            handleDeviceChange(
                                                                device.id,
                                                                'active',
                                                                e.target.checked
                                                            )
                                                        }
                                                    />
                                                </td>
                                                <td>
                                                    <select
                                                        value={device.type}
                                                        onChange={(e) =>
                                                            handleDeviceChange(
                                                                device.id,
                                                                'type',
                                                                e.target
                                                                    .value as DeviceType
                                                            )
                                                        }
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
                                                <td>
                                                    <input
                                                        type="number"
                                                        value={device.x}
                                                        onChange={(e) =>
                                                            handleDeviceChange(
                                                                device.id,
                                                                'x',
                                                                parseFloat(
                                                                    e.target
                                                                        .value
                                                                ) || 0
                                                            )
                                                        }
                                                    />
                                                </td>
                                                <td>
                                                    <input
                                                        type="number"
                                                        value={device.y}
                                                        onChange={(e) =>
                                                            handleDeviceChange(
                                                                device.id,
                                                                'y',
                                                                parseFloat(
                                                                    e.target
                                                                        .value
                                                                ) || 0
                                                            )
                                                        }
                                                    />
                                                </td>
                                                <td>
                                                    <input
                                                        type="number"
                                                        value={device.z.toFixed(
                                                            1
                                                        )}
                                                        step="0.1"
                                                        onChange={(e) =>
                                                            handleDeviceChange(
                                                                device.id,
                                                                'z',
                                                                parseFloat(
                                                                    parseFloat(
                                                                        e.target
                                                                            .value
                                                                    ).toFixed(1)
                                                                ) || 0
                                                            )
                                                        }
                                                    />
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="add-device-container">
                        <button
                            onClick={handleAddDevice}
                            className="add-device-btn"
                        >
                            Add
                        </button>
                    </div>
                </div>
                <div className="main-content">
                    {/* 顯示警告訊息，如果有臨時設備 */}
                    {hasTempDevices && (
                        <div
                            className="warning-message"
                            style={{
                                color: 'orange',
                                padding: '10px',
                                textAlign: 'center',
                            }}
                        >
                            您有未保存的設備更改。請點擊 Apply
                            按鈕保存更改並更新圖像。
                        </div>
                    )}

                    {/* 渲染可視化組件 */}
                    <SceneViewer />
                    <ConstellationViewer />
                </div>
            </div>
        </div>
    )
}

export default App
