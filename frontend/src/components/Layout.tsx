import { useState, ReactNode, useEffect } from 'react'
import '../styles/Layout.css'

interface LayoutProps {
    children?: ReactNode
    sidebar: ReactNode
    content?: ReactNode
    activeComponent: string
}

const Layout: React.FC<LayoutProps> = ({
    children,
    sidebar,
    content,
    activeComponent,
}) => {
    const [collapsed, setCollapsed] = useState<boolean>(
        activeComponent !== '2DRT'
    )

    useEffect(() => {
        setCollapsed(activeComponent !== '2DRT')
    }, [activeComponent])

    const toggleSidebar = () => {
        setCollapsed(!collapsed)
    }

    return (
        <div
            className={`layout ${
                collapsed ? 'sidebar-collapsed' : 'sidebar-expanded'
            }`}
        >
            <div className="sidebar-toggle" onClick={toggleSidebar}>
                ☰
            </div>
            <div className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
                <div className="sidebar-content">{sidebar}</div>
            </div>
            <main className="main-content">{content || children}</main>
        </div>
    )
}

export default Layout
