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
                            Channel Response Plots
                        </li>
                        <li
                            className={`navbar-item ${
                                activeComponent === '2DRT' ? 'active' : ''
                            }`}
                            onClick={() => onMenuClick('2DRT')}
                        >
                            Floor Plan
                        </li>
                        <li
                            className={`navbar-item ${
                                activeComponent === '3DRT' ? 'active' : ''
                            }`}
                            onClick={() => onMenuClick('3DRT')}
                        >
                            Stereogram
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

            {/* Constellation & CFR 彈窗 */}
            {showCFRModal && (
                <div className="modal-backdrop" onClick={closeCFRModal}>
                    <div
                        className="constellation-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h3>Constellation & CFR</h3>
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
                            <h3>Delay–Doppler</h3>
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

            {/* Time-Frequency 彈窗 - 更新為 Channel Response Plots */}
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
                            <h3>Channel Response Plots</h3>
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
            {/* 控制面板 */}
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
                <div className="loading">正在即時運算並生成 SINR Map...</div>
            )}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img src={imageUrl} alt="SINR Map" className="view-image" />
            )}
        </div>
    )
}

// Constellation & CFR 顯示組件
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
                console.error('載入 Constellation & CFR 失敗:', err)
                setError('無法載入 Constellation & CFR: ' + err.message)
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
                <div className="loading">
                    正在即時運算並生成 Constellation & CFR...
                </div>
            )}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img
                    src={imageUrl}
                    alt="Constellation & CFR"
                    className="view-image"
                />
            )}
        </div>
    )
}

// Delay-Doppler 顯示組件
const DelayDopplerViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [lastUpdate, setLastUpdate] = useState<string>('')

    // 使用 ref 來跟踪當前的 imageUrl，避免在 useCallback 中產生依賴
    const imageUrlRef = useRef<string | null>(null)

    // 後端API路徑 - 使用新的統一端點
    const API_PATH = '/api/v1/sionna/doppler-plots'

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

    // 請求並加載延遲多普勒圖
    const loadDopplerImage = useCallback(() => {
        setIsLoading(true)
        setError(null)

        // 從 API 獲取新的多普勒圖資訊
        fetch(API_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(
                        `API 請求失敗: ${response.status} ${response.statusText}`
                    )
                }
                return response.json()
            })
            .then((data) => {
                // 用獲得的 URL 載入圖片
                return fetch('/api/v1/sionna/unscaled-doppler-image') // 使用舊的端點，但它現在會返回新的統一圖像
                    .then((imgResponse) => {
                        if (!imgResponse.ok) {
                            throw new Error(
                                `圖片請求失敗: ${imgResponse.status} ${imgResponse.statusText}`
                            )
                        }
                        return imgResponse.blob()
                    })
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
                console.error('載入延遲多普勒圖失敗:', err)
                setError('無法載入延遲多普勒圖: ' + err.message)
                setIsLoading(false)
            })
    }, [])

    // 首次加載時獲取圖像
    useEffect(() => {
        loadDopplerImage()

        // 清理函數
        return () => {
            if (imageUrlRef.current) {
                URL.revokeObjectURL(imageUrlRef.current)
            }
        }
    }, [loadDopplerImage])

    // 刷新按鈕處理函數
    const handleRefresh = () => {
        loadDopplerImage()
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
                <div className="loading">
                    正在即時運算並生成 Delay-Doppler...
                </div>
            )}
            {error && <div className="error">{error}</div>}
            <div className="delay-doppler-container">
                {imageUrl && (
                    <div className="image-item doppler-image-v2">
                        <img
                            src={imageUrl}
                            alt="Delay-Doppler Plot"
                            className="view-image doppler-image-v2"
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
    const [lastUpdate, setLastUpdate] = useState<string>('')

    // 使用 ref 來跟踪當前的 imageUrl，避免在 useCallback 中產生依賴
    const imageUrlRef = useRef<string | null>(null)

    // 後端API路徑
    const API_PATH = '/api/v1/sionna/channel-response-plots'

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

    // 請求並加載通道響應圖
    const loadChannelResponseImage = useCallback(() => {
        setIsLoading(true)
        setError(null)

        // 向後端API發送請求以生成即時圖片
        fetch(API_PATH)
            .then((response) => {
                if (!response.ok) {
                    if (response.status === 400) {
                        return response.json().then((data) => {
                            throw new Error(
                                data.detail ||
                                    '需要至少一個活動的發射器和接收器'
                            )
                        })
                    }
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
                console.error('載入通道響應圖失敗:', err)
                setError('無法載入通道響應圖: ' + err.message)
                setIsLoading(false)
            })
    }, [])

    // 首次加載時獲取圖像
    useEffect(() => {
        loadChannelResponseImage()

        // 清理函數
        return () => {
            if (imageUrlRef.current) {
                URL.revokeObjectURL(imageUrlRef.current)
            }
        }
    }, [loadChannelResponseImage])

    // 刷新按鈕處理函數
    const handleRefresh = () => {
        loadChannelResponseImage()
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
                <div className="loading">
                    正在即時運算並生成 Channel Response Plots...
                </div>
            )}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img
                    src={imageUrl}
                    alt="Channel Response Plots"
                    className="view-image"
                />
            )}
        </div>
    )
}

export default Navbar
