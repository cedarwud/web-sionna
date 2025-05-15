// frontend/src/components/UAVDashboard.tsx  ← 新增
import { useState, useEffect } from 'react'
import axios from 'axios'

export default function UAVDashboard() {
    const [data, set] = useState<any>(null)
    useEffect(() => {
        const id = setInterval(async () => {
            const r = await axios.get('/api/v1/skybridge/status')
            set(r.data)
        }, 1000)
        return () => clearInterval(id)
    }, [])
    if (!data) return <div>Loading UAV link…</div>
    return (
        <div className="rounded-xl bg-slate-800 p-4 text-white">
            <h2 className="text-lg font-bold mb-2">UAV NTN Link</h2>
            <p>SNR (dB): {data.snr.toFixed(1)}</p>
            <p>Status: {data.link ? '📶 Connected' : '⚠️ Lost'}</p>
            <p>
                Sat lat/lon: {data.sat.lat.toFixed(2)},{' '}
                {data.sat.lon.toFixed(2)}
            </p>
        </div>
    )
}
