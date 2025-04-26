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
    const [loading, setLoading] = useState<boolean>(true)
    const [error, setError] = useState<string | null>(null)
    const [apiStatus, setApiStatus] = useState<
        'disconnected' | 'connected' | 'error'
    >('disconnected')
    const [selectedScene, setSelectedScene] = useState<string>('Etoile')

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
            } finally {
                setLoading(false)
            }
        }

        fetchDevices()
    }, [])

    // 處理應用更改 - 將更改保存到後端
    const handleApply = async () => {
        if (apiStatus !== 'connected') {
            setError('無法保存更改：API連接未建立')
            return
        }

        try {
            setLoading(true)
            setError(null)

            // 獲取已刪除的設備 ID
            const deletedDeviceIds = devices
                .filter(
                    (device) =>
                        !tempDevices.some((temp) => temp.id === device.id)
                )
                .map((device) => device.id)
                .filter((id) => id > 0) // 只考慮真實的後端ID（正數）

            // 處理已刪除的設備
            for (const id of deletedDeviceIds) {
                await deleteDevice(id)
            }

            // 處理更新和新增的設備
            for (const device of tempDevices) {
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

                if (device.id > 0) {
                    // 更新現有設備
                    await updateDevice(device.id, backendData)
                } else {
                    // 創建新設備
                    await createDevice({
                        ...backendData,
                        device_type: deviceType,
                    })
                }
            }

            // 重新獲取設備列表以反映最新狀態
            const updatedBackendDevices = await getDevices()
            const updatedFrontendDevices = updatedBackendDevices.map(
                convertBackendToFrontend
            )
            setDevices(updatedFrontendDevices)
            setTempDevices(updatedFrontendDevices)
        } catch (err: any) {
            console.error('保存設備失敗:', err)
            const errorMessage = err.message || '未知錯誤'
            setError(`保存設備數據時發生錯誤: ${errorMessage}`)
        } finally {
            setLoading(false)
        }
    }

    // 處理取消更改
    const handleCancel = () => {
        setTempDevices([...devices])
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
    }

    // 處理刪除設備
    const handleDeleteDevice = (id: number) => {
        setTempDevices((prev) => prev.filter((device) => device.id !== id))
    }

    // 處理添加新設備
    const handleAddDevice = () => {
        // 創建新設備（前端暫存，尚未保存到後端）
        const newDeviceId = Math.min(0, ...tempDevices.map((d) => d.id)) - 1 // 用負數作為臨時ID
        const newDevice: Device = {
            id: newDeviceId,
            name: `設備 ${-newDeviceId}`, // 默認名稱
            x: 0,
            y: 0,
            z: 0,
            active: true,
            type: 'tx',
        }
        setTempDevices([...tempDevices, newDevice])
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
                                應用
                            </button>
                            <button onClick={handleCancel}>取消</button>
                            <button onClick={handleAddDevice}>添加設備</button>
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
                    <div className="api-status">
                        API 狀態:
                        <span className={`status-indicator ${apiStatus}`}>
                            {apiStatus === 'connected'
                                ? '已連接'
                                : apiStatus === 'error'
                                ? '連接錯誤'
                                : '未連接'}
                        </span>
                        {apiStatus !== 'connected' && (
                            <span className="status-warning">
                                （僅本地編輯模式，無法保存到後端）
                            </span>
                        )}
                    </div>
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
                </div>
                <div className="main-content">
                    <SceneViewer />
                    <ConstellationViewer />
                </div>
            </div>
        </div>
    )
}

export default App
