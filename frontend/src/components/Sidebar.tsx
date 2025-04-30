import React from 'react'
import { Device } from '../App'
import '../styles/Sidebar.css'

// 前端設備類型（簡化版）
type DeviceType = 'tx' | 'rx' | 'int'

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
                                        <th></th>
                                        <th>類型</th>
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
                                                    onDeviceChange(
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
                                                    onDeviceChange(
                                                        device.id,
                                                        'type',
                                                        e.target
                                                            .value as DeviceType
                                                    )
                                                }
                                            >
                                                <option value="tx">Tx</option>
                                                <option value="rx">Rx</option>
                                                <option value="int">Int</option>
                                            </select>
                                        </td>
                                        <td>
                                            <input
                                                type="number"
                                                value={device.x}
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'x',
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
                                                value={device.y}
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'y',
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
                                                value={device.z.toFixed(1)}
                                                step="0.1"
                                                onChange={(e) =>
                                                    onDeviceChange(
                                                        device.id,
                                                        'z',
                                                        parseFloat(
                                                            parseFloat(
                                                                e.target.value
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
                <button onClick={onAddDevice} className="add-device-btn">
                    添加設備
                </button>
            </div>
        </div>
    )
}

export default Sidebar
