// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
    plugins: [react()],
    server: {
        host: '0.0.0.0', // 👈 必填，表示聽所有網卡
        port: 5173, // 保持跟瀏覽器網址一致
        strictPort: true, // 如果 5173 被佔用就直接報錯，不會自動跳號
        proxy: {
            // 將所有以 /api 開頭的請求都代理到後端
            '/api': {
                target: 'http://fastapi:8000', // 您的後端 API 伺服器地址
                changeOrigin: true, // 建議開啟，會修改請求頭中的 Host 字段為目標 URL，有助於處理某些後端的虛擬主機或安全配置
                // rewrite: (path) => path.replace(/^\/api/, '') // 只有當後端 API 路徑本身不包含 /api 前綴時才需要使用 rewrite
                // 在您的情況下，後端是 @app.get("/api/scene-image")，所以通常不需要 rewrite
            },
            // 增加對靜態文件的代理
            '/rendered_images': {
                target: 'http://fastapi:8000',
                changeOrigin: true,
            },
        },
    },
})
