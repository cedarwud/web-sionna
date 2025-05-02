import { useState, useEffect } from 'react'
import '../styles/Navbar.css'

interface NavbarProps {
    onMenuClick: (component: string) => void
    activeComponent: string
}

const Navbar: React.FC<NavbarProps> = ({ onMenuClick, activeComponent }) => {
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const [showConstellationModal, setShowConstellationModal] = useState(false)

    const toggleMenu = () => {
        setIsMenuOpen(!isMenuOpen)
    }

    const handleConstellationClick = (e: React.MouseEvent) => {
        e.preventDefault()
        setShowConstellationModal(true)
    }

    const closeConstellationModal = () => {
        setShowConstellationModal(false)
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
                        <li
                            className={`navbar-item ${
                                showConstellationModal ? 'active' : ''
                            }`}
                            onClick={handleConstellationClick}
                        >
                            星座圖
                        </li>
                    </ul>
                </div>
            </nav>

            {/* 星座圖彈窗 */}
            {showConstellationModal && (
                <div
                    className="modal-backdrop"
                    onClick={closeConstellationModal}
                >
                    <div
                        className="constellation-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header">
                            <h3>星座圖</h3>
                            <button
                                className="close-button"
                                onClick={closeConstellationModal}
                            >
                                ×
                            </button>
                        </div>
                        <div className="modal-content">
                            <ConstellationViewer />
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}

// 內嵌的 ConstellationViewer 組件
const ConstellationViewer = () => {
    const [isLoading, setIsLoading] = useState(true)
    const [imageUrl, setImageUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    // 使用靜態圖片路徑作為示例
    // 實際應用中可能需要從API獲取最新的星座圖
    const FALLBACK_IMAGE_PATH = '/rendered_images/constellation_diagram.png'

    useEffect(() => {
        setIsLoading(true)

        // 模擬加載過程
        fetch(FALLBACK_IMAGE_PATH)
            .then((response) => {
                if (!response.ok) {
                    throw new Error('無法載入星座圖')
                }
                return response.blob()
            })
            .then((blob) => {
                const url = URL.createObjectURL(blob)
                setImageUrl(url)
                setIsLoading(false)
            })
            .catch((err) => {
                console.error('載入星座圖失敗:', err)
                setError('無法載入星座圖: ' + err.message)
                setIsLoading(false)
            })

        // 清理函數，當組件卸載時釋放Blob URL
        return () => {
            if (imageUrl) {
                URL.revokeObjectURL(imageUrl)
            }
        }
    }, [])

    return (
        <div className="constellation-viewer">
            {isLoading && <div className="loading">正在載入星座圖...</div>}
            {error && <div className="error">{error}</div>}
            {imageUrl && (
                <img
                    src={imageUrl}
                    alt="星座圖"
                    className="constellation-image"
                />
            )}
        </div>
    )
}

export default Navbar
