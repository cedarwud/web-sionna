// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// 標記這是一個 Node.js 環境，所以 console 是有效的
/* eslint-disable */
// @ts-ignore
const nodeProcess = process;

export default defineConfig({
    plugins: [react()],
    server: {
        host: '0.0.0.0', // 👈 必填，表示聽所有網卡
        port: 5173, // 使用 5173 端口（容器內部端口）
        strictPort: false, // 設為 false 以允許自動尋找可用端口
        hmr: {
            port: 5174, // 👈 使用外部映射端口 5174 進行HMR
            host: '120.126.151.101', // 👈 外部可訪問的主機名
        },
        proxy: {
            // 將所有以 /api 開頭的請求都代理到後端
            '/api': {
                target: 'http://sionna_backend:8000', // 使用正確的容器名稱
                changeOrigin: true, // 修改請求頭中的 Host 字段為目標 URL
                secure: false, // 關閉安全檢查，允許自簽證書
                rewrite: (path: string) => path, // 保持路徑不變
                configure: (proxy: any, options: any) => {
                    // 代理事件處理
                    proxy.on('error', (err: any, req: any, res: any) => {
                        nodeProcess.stdout.write(`代理錯誤: ${err}\n`);
                    });
                    proxy.on('proxyReq', (proxyReq: any, req: any, res: any) => {
                        nodeProcess.stdout.write(`代理請求: ${req.url}\n`);
                    });
                    proxy.on('proxyRes', (proxyRes: any, req: any, res: any) => {
                        nodeProcess.stdout.write(`代理響應: ${proxyRes.statusCode} ${req.url}\n`);
                    });
                },
            },
            // 增加對靜態文件的代理
            '/rendered_images': {
                target: 'http://sionna_backend:8000',
                changeOrigin: true,
                secure: false,
            },
            // 其他靜態資源路徑
            '/static': {
                target: 'http://sionna_backend:8000',
                changeOrigin: true,
                secure: false,
            }
        },
    },
})
