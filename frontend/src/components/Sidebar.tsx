import React, { useState, useEffect } from 'react'
import { Device } from '../App'
import '../styles/Sidebar.css'

interface SidebarProps {
    devices: Device[]
    loading: boolean
    apiStatus: 'disconnected' | 'connected' | 'error'
    onDeviceChange: (id: number, field: keyof Device, value: any) => void
    onDeleteDevice: (id: number) => void
    onAddDevice: () => void
    onRefresh: () => void
    onApply: () => void
    onCancel: () => void
    hasTempDevices: boolean
}

const Sidebar: React.FC<SidebarProps> = ({
    devices,
    loading,
    apiStatus,
    onDeviceChange,
    onDeleteDevice,
    onAddDevice,
    onRefresh,
    onApply,
    onCancel,
    hasTempDevices,
}) => {
    // 為每個設備的方向值創建本地狀態
    const [orientationInputs, setOrientationInputs] = useState<{
        [key: string]: { x: string; y: string; z: string }
    }>({})

    // 當 devices 更新時，初始化或更新本地輸入狀態
    useEffect(() => {
        const newInputs: {
            [key: string]: { x: string; y: string; z: string }
        } = {}
        devices.forEach((device) => {
            // 如果該設備已有本地輸入狀態，保留它；否則，從設備初始化
            if (!orientationInputs[device.id]) {
                newInputs[device.id] = {
                    x: device.orientation_x?.toString() || '0',
                    y: device.orientation_y?.toString() || '0',
                    z: device.orientation_z?.toString() || '0',
                }
            } else {
                newInputs[device.id] = orientationInputs[device.id]
            }
        })
        setOrientationInputs(newInputs)
    }, [devices])

    // 處理方向輸入的變化
    const handleOrientationInput = (
        deviceId: number,
        axis: 'x' | 'y' | 'z',
        value: string
    ) => {
        // 更新本地狀態
        setOrientationInputs((prev) => ({
            ...prev,
            [deviceId]: {
                ...prev[deviceId],
                [axis]: value,
            },
        }))

        // 檢查輸入是否包含分數格式
        if (value.includes('/')) {
            const parts = value.split('/')
            if (parts.length === 2) {
                const numerator = parseFloat(parts[0])
                const denominator = parseFloat(parts[1])
                if (
                    !isNaN(numerator) &&
                    !isNaN(denominator) &&
                    denominator !== 0
                ) {
                    // 計算分數值並乘以 π
                    const calculatedValue = (numerator / denominator) * Math.PI
                    // 更新設備狀態
                    const orientationKey = `orientation_${axis}` as keyof Device
                    onDeviceChange(deviceId, orientationKey, calculatedValue)
                }
            }
        } else {
            // 嘗試將值解析為數字
            const numValue = parseFloat(value)
            if (!isNaN(numValue)) {
                // 更新設備狀態
                const orientationKey = `orientation_${axis}` as keyof Device
                onDeviceChange(deviceId, orientationKey, numValue)
            }
        }
    }

    return (
        <div className="sidebar-container">
            <div className="sidebar-header">
                <h2>網路設備</h2>
                <div className="button-group">
                    <button onClick={onRefresh} disabled={loading}>
                        重新整理
                    </button>
                </div>
            </div>
            <div className="api-status">
                API 狀態:{' '}
                {apiStatus === 'connected' ? (
                    <span className="status-connected">已連接</span>
                ) : apiStatus === 'error' ? (
                    <span className="status-error">錯誤</span>
                ) : (
                    <span className="status-disconnected">未連接</span>
                )}
            </div>

            <div className="action-buttons">
                <button
                    onClick={onApply}
                    disabled={
                        loading || apiStatus !== 'connected' || !hasTempDevices
                    }
                    className="apply-button"
                >
                    套用
                </button>
                <button
                    onClick={onCancel}
                    disabled={loading}
                    className="cancel-button"
                >
                    取消
                </button>
            </div>

            <div className="devices-list">
                {[...devices].map((device) => (
                    <div key={device.id} className="device-item">
                        <div className="device-header">
                            <input
                                type="text"
                                value={device.name}
                                onChange={(e) =>
                                    onDeviceChange(
                                        device.id,
                                        'name',
                                        e.target.value
                                    )
                                }
                                className="device-name-input"
                            />
                            <button
                                className="delete-btn"
                                onClick={() => onDeleteDevice(device.id)}
                            >
                                &#10006;
                            </button>
                        </div>
                        <div className="device-content">
                            <table className="device-table">
                                <thead>
                                    <tr>
                                        <th>類型</th>
                                        <th>X 位置</th>
                                        <th>Y 位置</th>
                                        <th>Z 位置</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>
                                            <select
                                                value={device.role}
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'role',
                                                        e.target.value
                                                    )
                                                }
                                                className="device-type-select"
                                            >
                                                <option value="desired">
                                                    發射器
                                                </option>
                                                <option value="jammer">
                                                    干擾源
                                                </option>
                                                <option value="receiver">
                                                    接收器
                                                </option>
                                            </select>
                                        </td>
                                        <td>
                                            <input
                                                type="number"
                                                value={device.position_x}
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'position_x',
                                                        parseFloat(
                                                            e.target.value
                                                        ) || 0
                                                    )
                                                }
                                            />
                                        </td>
                                        <td>
                                            <input
                                                type="number"
                                                value={device.position_y}
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'position_y',
                                                        parseFloat(
                                                            e.target.value
                                                        ) || 0
                                                    )
                                                }
                                            />
                                        </td>
                                        <td>
                                            <input
                                                type="number"
                                                value={device.position_z}
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'position_z',
                                                        parseInt(
                                                            e.target.value,
                                                            10
                                                        ) || 0
                                                    )
                                                }
                                            />
                                        </td>
                                    </tr>
                                </tbody>
                            </table>

                            {device.role !== 'receiver' && (
                                <table className="device-table orientation-table">
                                    <thead>
                                        <tr>
                                            <th>功率 (dBm)</th>
                                            <th>X 方向</th>
                                            <th>Y 方向</th>
                                            <th>Z 方向</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td>
                                                <input
                                                    type="number"
                                                    value={
                                                        device.power_dbm || 0
                                                    }
                                                    onChange={(e) =>
                                                        onDeviceChange(
                                                            device.id,
                                                            'power_dbm',
                                                            parseInt(
                                                                e.target.value,
                                                                10
                                                            ) || 0
                                                        )
                                                    }
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="text"
                                                    value={
                                                        orientationInputs[
                                                            device.id
                                                        ]?.x || '0'
                                                    }
                                                    onChange={(e) =>
                                                        handleOrientationInput(
                                                            device.id,
                                                            'x',
                                                            e.target.value
                                                        )
                                                    }
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="text"
                                                    value={
                                                        orientationInputs[
                                                            device.id
                                                        ]?.y || '0'
                                                    }
                                                    onChange={(e) =>
                                                        handleOrientationInput(
                                                            device.id,
                                                            'y',
                                                            e.target.value
                                                        )
                                                    }
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="text"
                                                    value={
                                                        orientationInputs[
                                                            device.id
                                                        ]?.z || '0'
                                                    }
                                                    onChange={(e) =>
                                                        handleOrientationInput(
                                                            device.id,
                                                            'z',
                                                            e.target.value
                                                        )
                                                    }
                                                />
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                ))}
            </div>
            <div className="add-device-container">
                <button onClick={onAddDevice} className="add-device-btn">
                    添加設備
                </button>
            </div>
        </div>
    )
}

export default Sidebar
