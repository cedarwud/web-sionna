import { useState, useEffect, useCallback, useRef } from 'react'
import '../styles/Navbar.css'

interface NavbarProps {
    onMenuClick: (component: string) => void
    activeComponent: string
}

const Navbar: React.FC<NavbarProps> = ({ onMenuClick, activeComponent }) => {
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const [showCFRModal, setShowCFRModal] = useState(false)
    const [showDelayDopplerModal, setShowDelayDopplerModal] = useState(false)
    const [showTimeFrequencyModal, setShowTimeFrequencyModal] = useState(false)
    const [showSINRModal, setShowSINRModal] = useState(false)

    const toggleMenu = () => {
        setIsMenuOpen(!isMenuOpen)
    }

    const handleCFRClick = (e: React.MouseEvent) => {
        e.preventDefault()
        setShowCFRModal(true)
    }

    const closeCFRModal = () => {
        setShowCFRModal(false)
    }

    const handleDelayDopplerClick = (e: React.MouseEvent) => {
        e.preventDefault()
        setShowDelayDopplerModal(true)
    }

    const closeDelayDopplerModal = () => {
        setShowDelayDopplerModal(false)
    }

    const handleTimeFrequencyClick = (e: React.MouseEvent) => {
        e.preventDefault()
        setShowTimeFrequencyModal(true)
    }

    const closeTimeFrequencyModal = () => {
        setShowTimeFrequencyModal(false)
    }

    const handleSINRClick = (e: React.MouseEvent) => {
        e.preventDefault()
        setShowSINRModal(true)
    }

    const closeSINRModal = () => {
        setShowSINRModal(false)
    }

    return (
        <>
            <nav className="navbar">
                <div className="navbar-container">
                    <div className="navbar-logo">Sionna</div>

                    <div className="navbar-menu-toggle" onClick={toggleMenu}>
                        <span
                            className={`menu-icon ${isMenuOpen ? 'open' : ''}`}
                        ></span>
                    </div>

                    <ul className={`navbar-menu ${isMenuOpen ? 'open' : ''}`}>
                        <li
                            className={`navbar-item ${
                                showSINRModal ? 'active' : ''
                            }`}
                            onClick={handleSINRClick}
                        >
                            SINR MAP
                        </li>
                        <li
                            className={`navbar-item ${
                                showCFRModal ? 'active' : ''
                            }`}
                            onClick={handleCFRClick}
                        >
                            Constellation & CFR
                        </li>
                        <li
                            className={`navbar-item ${
                                showDelayDopplerModal ? 'active' : ''
                            }`}
                            onClick={handleDelayDopplerClick}
                        >
                            Delay–Doppler
                        </li>
                        <li
                            className={`navbar-item ${
                                showTimeFrequencyModal ? 'active' : ''
                            }`}
                            onClick={handleTimeFrequencyClick}
                        >
                            Time-Frequency Surface Plot
                        </li>
                        <li
                            className={`navbar-item ${
                                activeComponent === '2DRT' ? 'active' : ''
                            }`}
                            onClick={() => onMenuClick('2DRT')}
                        >
                            2D RT
                        </li>
                        <li
                            className={`navbar-item ${
                                activeComponent === '3DRT' ? 'active' : ''
                            }`}
                            onClick={() => onMenuClick('3DRT')}
                        >
                            3D RT
                        </li>
                    </ul>
                </div>
            </nav>

            {/* SINR Map 彈窗 */}
            {showSINRModal && (
                <div className="modal-backdrop" onClick={closeSINRModal}>
                    <div
                        className="constellation-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h3>SINR Map</h3>
                            <button
                                className="close-button"
                                onClick={closeSINRModal}
                            >
                                ×
                            </button>
                        </div>
                        <div className="modal-content">
                            <SINRViewer />
                        </div>
                    </div>
                </div>
            )}

            {/* CFR Magnitude 彈窗 */}
            {showCFRModal && (
                <div className="modal-backdrop" onClick={closeCFRModal}>
                    <div
                        className="constellation-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h3>CFR Magnitude</h3>
                            <button
                                className="close-button"
                                onClick={closeCFRModal}
                            >
                                ×
                            </button>
                        </div>
                        <div className="modal-content">
                            <CFRViewer />
                        </div>
                    </div>
                </div>
            )}

            {/* Delay–Doppler 彈窗 */}
            {showDelayDopplerModal && (
                <div
                    className="modal-backdrop"
                    onClick={closeDelayDopplerModal}
                >
                    <div
                        className="constellation-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h3>Delay–Doppler 圖</h3>
                            <button
                                className="close-button"
                                onClick={closeDelayDopplerModal}
                            >
                                ×
                            </button>
                        </div>
                        <div className="modal-content">
                            <DelayDopplerViewer />
                        </div>
                    </div>
                </div>
            )}

            {/* Time-Frequency 彈窗 */}
            {showTimeFrequencyModal && (
                <div
                    className="modal-backdrop"
                    onClick={closeTimeFrequencyModal}
                >
                    <div
                        className="constellation-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h3>Time-Frequency Surface Plot</h3>
                            <button
                                className="close-button"
                                onClick={closeTimeFrequencyModal}
                            >
                                ×
                            </button>
                        </div>
                        <div className="modal-content">
                            <TimeFrequencyViewer />
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}

// SINR Map 顯示組件
const SINRViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string>('')
    const [sinrVmin, setSinrVmin] = useState<number>(-40)
    const [sinrVmax, setSinrVmax] = useState<number>(0)
    const [cellSize, setCellSize] = useState<number>(1.0)
    const [samplesPerTx, setSamplesPerTx] = useState<number>(10 ** 7)

    // 使用 ref 來跟踪當前的 imageUrl，避免在 useCallback 中產生依賴
    const imageUrlRef = useRef<string | null>(null)

    // 後端API路徑
    const API_PATH = '/api/v1/sionna/sinr-map'

    // 記錄請求時間戳，用於顯示最後更新時間
    const updateTimestamp = () => {
        const now = new Date()
        const timeString = now.toLocaleTimeString()
        setLastUpdate(timeString)
    }

    // 同步 imageUrl 到 ref
    useEffect(() => {
        imageUrlRef.current = imageUrl
    }, [imageUrl])

    // 請求並加載 SINR Map 圖
    const loadSINRMapImage = useCallback(() => {
        setIsLoading(true)
        setError(null)

        // 構建 API URL 包含參數
        const apiUrl = `${API_PATH}?sinr_vmin=${sinrVmin}&sinr_vmax=${sinrVmax}&cell_size=${cellSize}&samples_per_tx=${samplesPerTx}`

        // 向後端API發送請求以生成即時圖片
        fetch(apiUrl)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(
                        `API 請求失敗: ${response.status} ${response.statusText}`
                    )
                }
                return response.blob()
            })
            .then((blob) => {
                // 清理舊的 URL
                if (imageUrlRef.current) {
                    URL.revokeObjectURL(imageUrlRef.current)
                }

                const url = URL.createObjectURL(blob)
                setImageUrl(url)
                setIsLoading(false)
                updateTimestamp()
            })
            .catch((err) => {
                console.error('載入 SINR Map 失敗:', err)
                setError('無法載入 SINR Map: ' + err.message)
                setIsLoading(false)
            })
    }, [sinrVmin, sinrVmax, cellSize, samplesPerTx])

    // 首次加載時獲取圖像
    useEffect(() => {
        loadSINRMapImage()

        // 清理函數
        return () => {
            if (imageUrlRef.current) {
                URL.revokeObjectURL(imageUrlRef.current)
            }
        }
    }, [loadSINRMapImage])

    // 處理 SINR 參數變更
    const handleSinrVminChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSinrVmin(Number(e.target.value))
    }

    const handleSinrVmaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSinrVmax(Number(e.target.value))
    }

    const handleCellSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setCellSize(Number(e.target.value))
    }

    const handleSamplesChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSamplesPerTx(Number(e.target.value))
    }

    // 刷新按鈕處理函數
    const handleRefresh = () => {
        loadSINRMapImage()
    }

    return (
        <div className="image-viewer">
            {/* 暫時隱藏控制面板 */}
            {/* 
            <div className="image-controls">
                <div className="control-group">
                    <label>
                        SINR Min (dB):
                        <input 
                            type="number" 
                            value={sinrVmin} 
                            onChange={handleSinrVminChange} 
                            min="-100" 
                            max="0" 
                            step="5"
                        />
                    </label>
                    <label>
                        SINR Max (dB):
                        <input 
                            type="number" 
                            value={sinrVmax} 
                            onChange={handleSinrVmaxChange} 
                            min="-50" 
                            max="50" 
                            step="5"
                        />
                    </label>
                </div>
                <div className="control-group">
                    <label>
                        網格大小 (m):
                        <input 
                            type="number" 
                            value={cellSize} 
                            onChange={handleCellSizeChange} 
                            min="0.1" 
                            max="10" 
                            step="0.1"
                        />
                    </label>
                    <label>
                        採樣數量:
                        <select value={samplesPerTx} onChange={handleSamplesChange}>
                            <option value={10**5}>10^5 (快速)</option>
                            <option value={10**6}>10^6 (一般)</option>
                            <option value={10**7}>10^7 (精確)</option>
                        </select>
                    </label>
                </div>
                <button
                    className="refresh-button"
                    onClick={handleRefresh}
                    disabled={isLoading}
                >
                    {isLoading ? '正在生成...' : '生成 SINR 地圖'}
                </button>
                {lastUpdate && (
                    <span className="last-update">最後更新: {lastUpdate}</span>
                )}
            </div>
            */}

            {isLoading && (
                <div className="loading">正在即時生成 SINR 地圖...</div>
            )}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img src={imageUrl} alt="SINR Map" className="view-image" />
            )}
        </div>
    )
}

// CFR Magnitude 顯示組件
const CFRViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string>('')

    // 使用 ref 來跟踪當前的 imageUrl，避免在 useCallback 中產生依賴
    const imageUrlRef = useRef<string | null>(null)

    // 後端API路徑
    const API_PATH = '/api/v1/sionna/cfr-plot'

    // 記錄請求時間戳，用於顯示最後更新時間
    const updateTimestamp = () => {
        const now = new Date()
        const timeString = now.toLocaleTimeString()
        setLastUpdate(timeString)
    }

    // 同步 imageUrl 到 ref
    useEffect(() => {
        imageUrlRef.current = imageUrl
    }, [imageUrl])

    // 請求並加載 CFR 圖
    const loadCFRImage = useCallback(() => {
        setIsLoading(true)
        setError(null)

        // 向後端API發送請求以生成即時圖片
        fetch(API_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(
                        `API 請求失敗: ${response.status} ${response.statusText}`
                    )
                }
                return response.blob()
            })
            .then((blob) => {
                // 清理舊的 URL
                if (imageUrlRef.current) {
                    URL.revokeObjectURL(imageUrlRef.current)
                }

                const url = URL.createObjectURL(blob)
                setImageUrl(url)
                setIsLoading(false)
                updateTimestamp()
            })
            .catch((err) => {
                console.error('載入 CFR Magnitude 圖失敗:', err)
                setError('無法載入 CFR Magnitude 圖: ' + err.message)
                setIsLoading(false)
            })
    }, [])

    // 首次加載時獲取圖像
    useEffect(() => {
        loadCFRImage()

        // 清理函數
        return () => {
            if (imageUrlRef.current) {
                URL.revokeObjectURL(imageUrlRef.current)
            }
        }
    }, [loadCFRImage])

    // 刷新按鈕處理函數
    const handleRefresh = () => {
        loadCFRImage()
    }

    return (
        <div className="image-viewer">
            <div className="image-controls">
                <button
                    className="refresh-button"
                    onClick={handleRefresh}
                    disabled={isLoading}
                >
                    {isLoading ? '正在生成...' : '重新生成圖表'}
                </button>
                {lastUpdate && (
                    <span className="last-update">最後更新: {lastUpdate}</span>
                )}
            </div>

            {isLoading && (
                <div className="loading">正在即時生成 CFR Magnitude 圖...</div>
            )}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img
                    src={imageUrl}
                    alt="CFR Magnitude"
                    className="view-image"
                />
            )}
        </div>
    )
}

// Delay-Doppler 顯示組件
const DelayDopplerViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [lowImageUrl, setLowImageUrl] = useState<string | null>(null)
    const [highImageUrl, setHighImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    const LOW_IMAGE_PATH = '/static/images/low.png'
    const HIGH_IMAGE_PATH = '/static/images/high.png'

    useEffect(() => {
        setIsLoading(true)
        let loadedCount = 0
        const totalImages = 2

        // 加載低功率圖像
        fetch(LOW_IMAGE_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error('無法載入低功率 Delay-Doppler 圖')
                }
                return response.blob()
            })
            .then((blob) => {
                const url = URL.createObjectURL(blob)
                setLowImageUrl(url)
                loadedCount++
                if (loadedCount === totalImages) setIsLoading(false)
            })
            .catch((err) => {
                console.error('載入低功率 Delay-Doppler 圖失敗:', err)
                setError('無法載入低功率 Delay-Doppler 圖: ' + err.message)
                setIsLoading(false)
            })

        // 加載高功率圖像
        fetch(HIGH_IMAGE_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error('無法載入高功率 Delay-Doppler 圖')
                }
                return response.blob()
            })
            .then((blob) => {
                const url = URL.createObjectURL(blob)
                setHighImageUrl(url)
                loadedCount++
                if (loadedCount === totalImages) setIsLoading(false)
            })
            .catch((err) => {
                console.error('載入高功率 Delay-Doppler 圖失敗:', err)
                setError('無法載入高功率 Delay-Doppler 圖: ' + err.message)
                setIsLoading(false)
            })

        return () => {
            if (lowImageUrl) URL.revokeObjectURL(lowImageUrl)
            if (highImageUrl) URL.revokeObjectURL(highImageUrl)
        }
    }, [])

    return (
        <div className="image-viewer">
            {isLoading && (
                <div className="loading">正在載入 Delay-Doppler 圖...</div>
            )}
            {error && <div className="error">{error}</div>}
            <div className="delay-doppler-container">
                {lowImageUrl && (
                    <div className="image-item">
                        <h4>Low Power</h4>
                        <img
                            src={lowImageUrl}
                            alt="Low Power Delay-Doppler"
                            className="view-image"
                        />
                    </div>
                )}
                {highImageUrl && (
                    <div className="image-item">
                        <h4>High Power</h4>
                        <img
                            src={highImageUrl}
                            alt="High Power Delay-Doppler"
                            className="view-image"
                        />
                    </div>
                )}
            </div>
        </div>
    )
}

// Time-Frequency 顯示組件
const TimeFrequencyViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    const IMAGE_PATH = '/static/images/tf.png'

    useEffect(() => {
        setIsLoading(true)

        fetch(IMAGE_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error('無法載入 Time-Frequency Surface Plot')
                }
                return response.blob()
            })
            .then((blob) => {
                const url = URL.createObjectURL(blob)
                setImageUrl(url)
                setIsLoading(false)
            })
            .catch((err) => {
                console.error('載入 Time-Frequency Surface Plot 失敗:', err)
                setError('無法載入 Time-Frequency Surface Plot: ' + err.message)
                setIsLoading(false)
            })

        return () => {
            if (imageUrl) {
                URL.revokeObjectURL(imageUrl)
            }
        }
    }, [])

    return (
        <div className="image-viewer">
            {isLoading && (
                <div className="loading">
                    正在載入 Time-Frequency Surface Plot...
                </div>
            )}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img
                    src={imageUrl}
                    alt="Time-Frequency Surface Plot"
                    className="view-image"
                />
            )}
        </div>
    )
}

export default Navbar
