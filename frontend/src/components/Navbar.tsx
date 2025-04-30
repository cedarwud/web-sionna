import { useState } from 'react'
import '../styles/Navbar.css'

interface NavbarProps {
    onMenuClick: (component: string) => void
    activeComponent: string
}

const Navbar: React.FC<NavbarProps> = ({ onMenuClick, activeComponent }) => {
    const [isMenuOpen, setIsMenuOpen] = useState(false)

    const toggleMenu = () => {
        setIsMenuOpen(!isMenuOpen)
    }

    return (
        <nav className="navbar">
            <div className="navbar-container">
                <div className="navbar-logo">Web Sionna</div>

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
                        2D電波傳播圖
                    </li>
                    <li
                        className={`navbar-item ${
                            activeComponent === '3DRT' ? 'active' : ''
                        }`}
                        onClick={() => onMenuClick('3DRT')}
                    >
                        3D電波傳播圖
                    </li>
                    <li
                        className={`navbar-item ${
                            activeComponent === 'constellation' ? 'active' : ''
                        }`}
                        onClick={() => onMenuClick('constellation')}
                    >
                        星座圖
                    </li>
                </ul>
            </div>
        </nav>
    )
}

export default Navbar
