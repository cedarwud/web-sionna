// src/SceneView.tsx
import {
    Suspense,
    useLayoutEffect,
    useMemo,
    useEffect,
    useState,
    useRef,
} from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { ContactShadows } from '@react-three/drei'
import { Bounds, OrbitControls, useGLTF, Clone } from '@react-three/drei'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
// @ts-ignore
import { GLTF } from 'three/examples/jsm/loaders/GLTFLoader'
import * as THREE from 'three'
import { TextureLoader, RepeatWrapping, SRGBColorSpace } from 'three'
import { Device } from '../App' // 從 App 引入前端 Device 介面

// 修改: 直接使用靜態檔案路徑而非 API 端點，避免後端處理錯誤
const SCENE_URL = '/static/models/XIN.glb'
const UAV_MODEL_URL = '/api/v1/sionna/models/uav' // 新增 UAV 模型 URL

// 定義設備類型材質和尺寸
const TX_MATERIAL = new THREE.MeshStandardMaterial({
    color: 0x0000ff, // 藍色
    emissive: 0x000066,
    emissiveIntensity: 0.5,
})
// RX_MATERIAL 不再需要，因為我們會用 UAV 模型
// const RX_MATERIAL = new THREE.MeshStandardMaterial({
//     color: 0xff0000, // 紅色
//     emissive: 0x660000,
//     emissiveIntensity: 0.5,
// })
const INT_MATERIAL = new THREE.MeshStandardMaterial({
    color: 0x000000, // 黑色
    emissive: 0x000000,
    emissiveIntensity: 0.5,
})
const DEVICE_SIZE = 5 // TX 和 INT 的尺寸
const UAV_SCALE = 1 // <-- 暫時放大 Scale 方便觀察
const UAV_Y_OFFSET = 10 // <-- 稍微調整偏移

// 定義射線材質 - 線寬度增加
const RAY_MATERIAL = new THREE.LineBasicMaterial({
    color: 0xffaa00, // 改為橙黃色
    linewidth: 5, // 增加線寬 - 注意: Three.js的linewidth在大多數WebGL實現中最大為1
})
const LOS_MATERIAL = new THREE.LineBasicMaterial({
    color: 0x00ffaa, // 改為青綠色
    linewidth: 5, // 增加線寬
})

// 新增: 箭頭輔助物材質
const ARROW_MATERIAL = new THREE.MeshBasicMaterial({
    color: 0xffff00,
})

// 新增: 全向天線輻射材質
const RADIATION_MATERIAL = new THREE.MeshBasicMaterial({
    color: 0x00aaff,
    transparent: true,
    opacity: 0.2,
})

interface EtoileProps {
    devices: Device[]
}

// 新增: 定義 API 回應數據類型
interface Point {
    x: number
    y: number
    z: number
}

interface RayPath {
    points: Point[]
    is_los?: boolean
    width?: number
}

interface RayPathData {
    paths: RayPath[]
}

/* ---------------- 1) 讀 glTF → 加材質 / Normals ---------------- */
function Etoile({ devices = [] }: EtoileProps) {
    const { scene: mainScene } = useGLTF(SCENE_URL) as GLTF
    const { scene: uavModelScene } = useGLTF(UAV_MODEL_URL) as GLTF

    // --- 新增: 打印加載的 UAV 模型信息 ---
    useEffect(() => {
        if (uavModelScene) {
            console.log('UAV Model Loaded:', uavModelScene)
            // 可以進一步檢查模型的結構，例如 children
            console.log('UAV Model Children:', uavModelScene.children)
        } else {
            console.log('UAV Model not loaded yet or failed.')
        }
    }, [uavModelScene])
    // --- 結束新增 ---

    const { controls } = useThree()
    const [rays, setRays] = useState<THREE.Object3D[]>([])

    // 將useLayoutEffect從useMemo中移出，放在組件頂層
    useLayoutEffect(() => {
        ;(controls as OrbitControlsImpl)?.target?.set(0, 0, 0)
    }, [controls])

    /** 只在 glTF 載完後跑一次 → 回傳處理後的 clone */
    const prepared = useMemo(() => {
        const root = mainScene.clone(true) // ❗ 不要直接改原始 glTF，clone 一份

        // ─── 2.1 載入並設定地板貼圖 ────────────────────────────────
        const loader = new TextureLoader()
        const groundTex = loader.load('/textures/groundTex.png')
        const normalTex = loader.load('/textures/normalTex.png')
        const roughnessTex = loader.load('/textures/roughnessTex.png')
        const displacementTex = loader.load('/textures/displacementTex.png')
        // 移除 aoTex 載入，因為地板沒有 UV，無法使用 aoMap

        // 把它們放進一個陣列，並明確標注為 Texture[]
        const textures: THREE.Texture[] = [
            groundTex,
            normalTex,
            roughnessTex,
            displacementTex,
        ]

        groundTex.repeat.set(60, 60) // ↑更多重複，顆粒看起來更細
        roughnessTex.repeat.set(60, 60)

        textures.forEach((tex: THREE.Texture) => {
            // 單獨設定 wrapS、wrapT
            tex.wrapS = RepeatWrapping
            tex.wrapT = RepeatWrapping

            // 調整 tile 次數
            tex.repeat.set(40, 40)

            // 指定色彩空間
            tex.colorSpace = SRGBColorSpace
        })

        // 尋找最大面積（可能是地面）的網格
        let maxArea = 0
        let groundMesh: THREE.Mesh | null = null
        root.traverse((o: THREE.Object3D) => {
            if ((o as THREE.Mesh).isMesh) {
                const m = o as THREE.Mesh
                // 開啟所有物件的陰影投射與接收 (稍後再針對地面調整)
                m.castShadow = true
                m.receiveShadow = true

                if (m.geometry && m.geometry.boundingBox) {
                    m.geometry.computeBoundingBox()
                    const bb = m.geometry.boundingBox
                    const size = new THREE.Vector3()
                    bb.getSize(size)
                    const area = size.x * size.z // 使用 XZ 平面面積判斷地面

                    // 檢查是否為最大面積的 mesh
                    if (area > maxArea) {
                        // 如果之前有 groundMesh，將其 castShadow 設回 true
                        if (groundMesh) {
                            groundMesh.castShadow = true
                        }

                        maxArea = area
                        groundMesh = m // 更新 groundMesh

                        // 地面材質設定 (與之前相同)
                        const loader = new TextureLoader()
                        const groundTex = loader.load('/textures/groundTex.png')
                        const normalTex = loader.load('/textures/normalTex.png')
                        const roughnessTex = loader.load(
                            '/textures/roughnessTex.png'
                        )
                        const displacementTex = loader.load(
                            '/textures/displacementTex.png'
                        )
                        const textures: THREE.Texture[] = [
                            groundTex,
                            normalTex,
                            roughnessTex,
                            displacementTex,
                        ]
                        groundTex.repeat.set(60, 60)
                        roughnessTex.repeat.set(60, 60)
                        textures.forEach((tex: THREE.Texture) => {
                            tex.wrapS = RepeatWrapping
                            tex.wrapT = RepeatWrapping
                            tex.repeat.set(40, 40)
                            tex.colorSpace = SRGBColorSpace
                        })
                        groundMesh.material = new THREE.MeshStandardMaterial({
                            map: groundTex,
                            normalMap: normalTex,
                            roughnessMap: roughnessTex,
                            displacementMap: displacementTex,
                            displacementScale: 5,
                            displacementBias: -2,
                            color: 0xffffff,
                            roughness: 0.8,
                            metalness: 0.1,
                            emissive: 0x555555,
                            emissiveIntensity: 0.4,
                            vertexColors: false,
                            normalScale: new THREE.Vector2(0.5, 0.5),
                        })
                        groundMesh.receiveShadow = true // 地板接收陰影
                        groundMesh.castShadow = false // 地板不投射陰影
                    }
                    // else { // 非地面物件已在開頭設定 castShadow = true, receiveShadow = true
                    //     m.castShadow = true
                    //     m.receiveShadow = true // 讓建築物也能接收陰影
                    // }
                } else if (m.geometry) {
                    // ... (計算 boundingBox 的備用邏輯，確保 cast/receiveShadow)
                    m.geometry.computeBoundingBox()
                    if (m.geometry.boundingBox) {
                        const bb = m.geometry.boundingBox
                        const size = new THREE.Vector3()
                        bb.getSize(size)
                        const area = size.x * size.z
                        if (area > maxArea) {
                            if (groundMesh) {
                                groundMesh.castShadow = true
                            }
                            maxArea = area
                            groundMesh = m
                            const loader = new TextureLoader()
                            const groundTex = loader.load(
                                '/textures/groundTex.png'
                            )
                            const normalTex = loader.load(
                                '/textures/normalTex.png'
                            )
                            const roughnessTex = loader.load(
                                '/textures/roughnessTex.png'
                            )
                            const displacementTex = loader.load(
                                '/textures/displacementTex.png'
                            )
                            const textures: THREE.Texture[] = [
                                groundTex,
                                normalTex,
                                roughnessTex,
                                displacementTex,
                            ]
                            groundTex.repeat.set(60, 60)
                            roughnessTex.repeat.set(60, 60)
                            textures.forEach((tex: THREE.Texture) => {
                                tex.wrapS = RepeatWrapping
                                tex.wrapT = RepeatWrapping
                                tex.repeat.set(40, 40)
                                tex.colorSpace = SRGBColorSpace
                            })
                            groundMesh.material =
                                new THREE.MeshStandardMaterial({
                                    map: groundTex,
                                    normalMap: normalTex,
                                    roughnessMap: roughnessTex,
                                    displacementMap: displacementTex,
                                    displacementScale: 5,
                                    displacementBias: -2,
                                    color: 0xffffff,
                                    roughness: 0.8,
                                    metalness: 0.1,
                                    emissive: 0x555555,
                                    emissiveIntensity: 0.4,
                                    vertexColors: false,
                                    normalScale: new THREE.Vector2(0.5, 0.5),
                                })
                            groundMesh.receiveShadow = true
                            groundMesh.castShadow = false
                        } else {
                            m.castShadow = true
                            m.receiveShadow = true
                        }
                    } else {
                        m.castShadow = true
                        m.receiveShadow = true
                    }
                } else {
                    // 沒有 geometry，跳過
                }
            }
        })

        // 2.2 部分的邏輯已移至 traverse 內部，移除此區塊
        // if (groundMesh) { ... }

        // 移除 UV 相關代碼和警告，直接完成
        return root
    }, [mainScene])

    // 載入射線數據
    useEffect(() => {
        // 清除之前的射線
        rays.forEach((ray) => ray.removeFromParent())

        // 如果沒有設備，不需要獲取射線數據
        if (devices.length === 0) {
            setRays([])
            return
        }

        // 獲取射線路徑數據
        const fetchRayData = async () => {
            try {
                console.log('正在獲取射線路徑數據...')
                const response = await fetch('/api/v1/sionna/ray-paths')
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`)
                }
                const data = (await response.json()) as RayPathData
                console.log('獲取到射線路徑數據:', data)

                // 創建射線物件
                const newRays: THREE.Object3D[] = []

                if (data && Array.isArray(data.paths)) {
                    console.log(`將創建 ${data.paths.length} 條射線路徑`)

                    data.paths.forEach((path: RayPath, index: number) => {
                        if (
                            path.points &&
                            Array.isArray(path.points) &&
                            path.points.length >= 2
                        ) {
                            // 使用自定義寬度 (如果有提供)
                            const lineWidth =
                                path.width || (path.is_los ? 3 : 1.5)

                            // 創建自定義材質，使用不同顏色
                            const color = path.is_los ? 0x00ffaa : 0xffaa00
                            const material = new THREE.LineBasicMaterial({
                                color: color,
                                linewidth: 1, // WebGL限制
                            })

                            // 從後端獲取的點座標
                            const points = path.points.map(
                                (point: Point) =>
                                    new THREE.Vector3(point.x, point.z, point.y)
                            )

                            // 創建主射線
                            const geometry =
                                new THREE.BufferGeometry().setFromPoints(points)
                            const line = new THREE.Line(geometry, material)

                            // 採用管道方式來創建有粗細的線
                            const curve = new THREE.CatmullRomCurve3(points)
                            const tubeGeometry = new THREE.TubeGeometry(
                                curve, // 路徑曲線
                                20, // 路徑分段數
                                lineWidth * 0.3, // 管道半徑，用於控制粗細
                                8, // 管道截面分段數
                                false // 是否閉合
                            )
                            const tubeMaterial = new THREE.MeshBasicMaterial({
                                color: color,
                                transparent: true,
                                opacity: 0.6,
                            })
                            const tube = new THREE.Mesh(
                                tubeGeometry,
                                tubeMaterial
                            )

                            // 創建方向箭頭 (在每個線段中間)
                            for (let i = 0; i < points.length - 1; i++) {
                                const start = points[i]
                                const end = points[i + 1]
                                const direction =
                                    new THREE.Vector3().subVectors(end, start)
                                const length = direction.length()
                                direction.normalize()

                                // 箭頭位置 (線段中點)
                                const arrowPos = new THREE.Vector3().addVectors(
                                    start,
                                    direction
                                        .clone()
                                        .multiplyScalar(length * 0.5)
                                )

                                // 創建箭頭
                                const arrowHelper = new THREE.ArrowHelper(
                                    direction,
                                    arrowPos,
                                    length * 0.2, // 箭頭長度
                                    color,
                                    length * 0.1, // 頭部長度
                                    length * 0.05 // 頭部寬度
                                )

                                newRays.push(arrowHelper)
                            }

                            // 如果是發射器相關的射線，添加全向輻射球
                            if (path.points.length > 0 && index % 3 === 0) {
                                // 每三條路徑添加一個球
                                const startPoint = points[0] // 發射器位置

                                // 創建輻射球
                                const radiationGeometry =
                                    new THREE.SphereGeometry(10, 16, 16)
                                const radiationMaterial =
                                    new THREE.MeshBasicMaterial({
                                        color: color,
                                        transparent: true,
                                        opacity: 0.1,
                                        wireframe: true,
                                    })
                                const radiationSphere = new THREE.Mesh(
                                    radiationGeometry,
                                    radiationMaterial
                                )
                                radiationSphere.position.copy(startPoint)
                                newRays.push(radiationSphere)
                            }

                            // 所有物件添加到陣列
                            newRays.push(line)
                            newRays.push(tube)
                        }
                    })

                    console.log(`成功創建 ${newRays.length} 個射線相關物件`)
                }

                setRays(newRays)
            } catch (error) {
                console.error('Error fetching ray data:', error)
            }
        }

        // fetchRayData() // <--- 暫時禁用射線獲取
    }, [devices])

    // 渲染設備
    const deviceMeshes = useMemo(() => {
        return devices.map((device) => {
            if (device.name.startsWith('rx-')) {
                // --- 渲染 UAV 模型 ---
                if (!uavModelScene) {
                    console.log(
                        `RX device ${device.id}: UAV model not ready, skipping.`
                    )
                    return null // 如果模型尚未加載，則不渲染
                }
                console.log(
                    `RX device ${device.id}: Rendering UAV model. Position: ${[
                        device.x,
                        device.z + UAV_Y_OFFSET,
                        device.y,
                    ]}, Scale: ${UAV_SCALE}`
                )
                return (
                    <primitive
                        key={device.id}
                        object={uavModelScene.clone(true)} // 克隆模型以供每個接收器使用
                        position={[
                            device.x,
                            device.z + UAV_Y_OFFSET, // Y 軸是場景的 Z 軸，加上偏移量
                            device.y, // Z 軸是場景的 Y 軸
                        ]}
                        scale={[UAV_SCALE, UAV_SCALE, UAV_SCALE]}
                        // rotation={[0, Math.random() * Math.PI * 2, 0]} // <-- 暫時移除隨機旋轉
                        // 暫時移除 onUpdate 以簡化調試
                        // onUpdate={(self: THREE.Object3D) => self.traverse((child: THREE.Object3D) => {
                        //     if ((child as THREE.Mesh).isMesh) {
                        //         child.castShadow = true;
                        //         child.receiveShadow = true;
                        //     }
                        // })}
                    />
                )
            } else {
                // --- 渲染 TX 和 INT 球體 ---
                let material
                if (device.name.startsWith('tx-')) {
                    material = TX_MATERIAL
                } else if (device.name.startsWith('int-')) {
                    material = INT_MATERIAL
                } else {
                    material = TX_MATERIAL // 默認為發射器材質
                }

                return (
                    <mesh
                        key={device.id}
                        position={[
                            device.x,
                            device.z + 5, // Y 軸是場景的 Z 軸，加上偏移量
                            device.y, // Z 軸是場景的 Y 軸
                        ]}
                        material={material}
                        castShadow
                        receiveShadow
                    >
                        <sphereGeometry args={[DEVICE_SIZE, 16, 16]} />
                    </mesh>
                )
            }
        })
    }, [devices, uavModelScene]) // 加入 uavModelScene 作為依賴

    return (
        <Bounds>
            <primitive object={prepared} castShadow receiveShadow />
            {deviceMeshes}
            {/* {rays.map((ray, index) => (
                <primitive key={`ray-${index}`} object={ray} />
            ))} */}
        </Bounds>
    )
}

interface SceneViewProps {
    devices: Device[]
}

export default function SceneView({ devices = [] }: SceneViewProps) {
    return (
        <div
            className="scene-container"
            style={{ width: '100%', height: '100%' }}
        >
            <Canvas
                shadows
                camera={{ position: [0, 400, 0], near: 0.1, far: 1e4 }}
                gl={{
                    toneMapping: THREE.ACESFilmicToneMapping,
                    toneMappingExposure: 0.8, // <-- 降低曝光
                }}
            >
                <color attach="background" args={['#7f7f7f']} />
                {/* 降低光照強度 */}
                <hemisphereLight args={[0xffffff, 0x444444, 0.5]} />{' '}
                {/* 強度從 0.8 -> 0.5 */}
                <ambientLight intensity={0.05} /> {/* 強度從 0.1 -> 0.05 */}
                <directionalLight
                    castShadow
                    position={[15, 30, 10]}
                    intensity={1.5} // <-- 強度從 4 -> 1.5
                    shadow-mapSize-width={4096}
                    shadow-mapSize-height={4096}
                    shadow-camera-near={1}
                    shadow-camera-far={1000}
                    shadow-camera-top={500}
                    shadow-camera-bottom={-500}
                    shadow-camera-left={500}
                    shadow-camera-right={-500}
                    shadow-bias={-0.0004}
                    shadow-radius={8}
                />
                <Suspense fallback={null}>
                    <Etoile devices={devices} />
                    <ContactShadows
                        position={[0, 0.1, 0]} // 稍微抬高，避免 z-fighting
                        opacity={0.4} // 增加一點不透明度
                        scale={400} // 增加範圍以匹配可能更大的場景
                        blur={1.5} // 減少模糊，使陰影更清晰
                        far={50} // 增加距離
                    />
                </Suspense>
                <OrbitControls makeDefault />
            </Canvas>
        </div>
    )
}
