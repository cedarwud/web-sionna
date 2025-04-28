import React from 'react'
import { Device } from '../App'
import { TransmitterType } from '../services/api'
import '../styles/Sidebar.css'

// 前端設備類型（簡化版）
type DeviceType = 'tx' | 'rx' | 'int'

interface SidebarProps {
    tempDevices: Device[]
    apiStatus: 'disconnected' | 'connected' | 'error'
    error: string | null
    selectedScene: string
    hasTempDevices: boolean
    handleApply: () => void
    handleCancel: () => void
    handleSceneChange: (e: React.ChangeEvent<HTMLSelectElement>) => void
    handleDeviceChange: (id: number, field: keyof Device, value: any) => void
    handleDeleteDevice: (id: number) => void
    handleAddDevice: () => void
}

const Sidebar: React.FC<SidebarProps> = ({
    tempDevices,
    apiStatus,
    error,
    selectedScene,
    hasTempDevices,
    handleApply,
    handleCancel,
    handleSceneChange,
    handleDeviceChange,
    handleDeleteDevice,
    handleAddDevice,
}) => {
    return (
        <div className="sidebar-container">
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
                    <select value={selectedScene} onChange={handleSceneChange}>
                        <option value="Etoile">Etoile</option>
                        <option value="國立陽明交通大學">
                            國立陽明交通大學
                        </option>
                        <option value="國立臺北大學">國立臺北大學</option>
                    </select>
                </div>
            </div>
            {error && <div className="error-message">{error}</div>}
            <div className="devices-list">
                {[...tempDevices].map((device) => (
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
                                onClick={() => handleDeleteDevice(device.id)}
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
                                                    handleDeviceChange(
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
                                                    handleDeviceChange(
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
                                                    handleDeviceChange(
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
                <button onClick={handleAddDevice} className="add-device-btn">
                    Add
                </button>
            </div>
        </div>
    )
}

export default Sidebar
