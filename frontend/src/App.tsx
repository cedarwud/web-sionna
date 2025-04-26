// src/App.tsx
import { useState } from 'react'
import SceneViewer from './components/SceneViewer'
import ConstellationViewer from './components/ConstellationViewer'
import './App.css'

type DeviceType = 'tx' | 'rx' | 'int'

interface Device {
    id: number
    x: number
    y: number
    z: number
    active: boolean
    type: DeviceType
}

function App() {
    // 創建10個設備的假數據
    const initialDevices: Device[] = Array.from({ length: 10 }, (_, i) => ({
        id: i + 1,
        x: 0,
        y: 0,
        z: 0.0,
        active: false,
        type: 'tx' as DeviceType,
    }))

    const [devices, setDevices] = useState<Device[]>(initialDevices)
    const [tempDevices, setTempDevices] = useState<Device[]>(initialDevices)
    const [selectedScene, setSelectedScene] = useState<string>('Etoile')

    // 處理應用更改
    const handleApply = () => {
        setDevices([...tempDevices])
    }

    // 處理取消更改
    const handleCancel = () => {
        setTempDevices([...devices])
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

    return (
        <div className="App">
            <div className="app-container">
                <div className="sidebar">
                    <div className="sidebar-header">
                        <div className="button-group">
                            <button onClick={handleApply}>Apply</button>
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
                    <div className="devices-list">
                        {tempDevices.map((device) => (
                            <div key={device.id} className="device-item">
                                <div className="device-header">
                                    Device {device.id}
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
                                                                parseInt(
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
                                                                parseInt(
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
