import { useState, useEffect } from 'react'
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

// CFR Magnitude 顯示組件
const CFRViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    const IMAGE_PATH = '/static/images/cfr.png'

    useEffect(() => {
        setIsLoading(true)

        fetch(IMAGE_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error('無法載入 CFR Magnitude 圖')
                }
                return response.blob()
            })
            .then((blob) => {
                const url = URL.createObjectURL(blob)
                setImageUrl(url)
                setIsLoading(false)
            })
            .catch((err) => {
                console.error('載入 CFR Magnitude 圖失敗:', err)
                setError('無法載入 CFR Magnitude 圖: ' + err.message)
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
                <div className="loading">正在載入 CFR Magnitude 圖...</div>
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
