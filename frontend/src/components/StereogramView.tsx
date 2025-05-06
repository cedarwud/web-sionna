import {
    Suspense,
    useLayoutEffect,
    useMemo,
    useEffect,
    useState,
    useRef,
} from 'react'
import { Canvas, useThree, useFrame } from '@react-three/fiber'
import {
    ContactShadows,
    Bounds,
    OrbitControls,
    useGLTF,
    useAnimations,
} from '@react-three/drei'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import * as THREE from 'three'
import { TextureLoader, RepeatWrapping, SRGBColorSpace } from 'three'
import { Device } from '../App'

// 靜態檔案路徑
const SCENE_URL = '/static/models/NYCU.glb'
const UAV_MODEL_URL = '/api/v1/sionna/models/uav' // 替換為帶動畫的 GLB 模型路徑
const BS_MODEL_URL = '/api/v1/sionna/models/tower' // BS 模型路徑
const JAMMER_MODEL_URL = '/api/v1/sionna/models/jam' // Jammer 模型路徑
const SATELLITE_TEXTURE_URL = '/static/NYCU/textures/EXPORT_GOOGLE_SAT_WM.png' // 衛星圖路徑

// 材質和尺寸定義
const DEVICE_SIZE = 5
const UAV_SCALE = 10
const UAV_Y_OFFSET = 1

const RAY_MATERIAL = new THREE.LineBasicMaterial({
    color: 0xffaa00,
    linewidth: 5,
})
const LOS_MATERIAL = new THREE.LineBasicMaterial({
    color: 0x00ffaa,
    linewidth: 5,
})
const ARROW_MATERIAL = new THREE.MeshBasicMaterial({ color: 0xffff00 })
const RADIATION_MATERIAL = new THREE.MeshBasicMaterial({
    color: 0x00aaff,
    transparent: true,
    opacity: 0.2,
})

interface EtoileProps {
    devices: Device[]
    auto: boolean
    manualControl?: (
        direction:
            | 'up'
            | 'down'
            | 'left'
            | 'right'
            | 'ascend'
            | 'descend'
            | 'left-up'
            | 'right-up'
            | 'left-down'
            | 'right-down'
            | 'rotate-left'
            | 'rotate-right'
            | null
    ) => void
    manualDirection?:
        | 'up'
        | 'down'
        | 'left'
        | 'right'
        | 'ascend'
        | 'descend'
        | 'left-up'
        | 'right-up'
        | 'left-down'
        | 'right-down'
        | 'rotate-left'
        | 'rotate-right'
        | null
    onUAVPositionUpdate?: (position: [number, number, number]) => void
}

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

// 定義 AnimatedUAV 組件來處理動畫無人機
function AnimatedUAV({
    position,
    scale,
    auto,
    manualDirection,
    onManualMoveDone,
    onPositionUpdate,
}: {
    position: [number, number, number]
    scale: [number, number, number]
    auto: boolean
    manualDirection?:
        | 'up'
        | 'down'
        | 'left'
        | 'right'
        | 'ascend'
        | 'descend'
        | 'left-up'
        | 'right-up'
        | 'left-down'
        | 'right-down'
        | 'rotate-left'
        | 'rotate-right'
        | null
    onManualMoveDone?: () => void
    onPositionUpdate?: (position: [number, number, number]) => void
}) {
    const group = useRef<THREE.Group>(null)
    const lightRef = useRef<THREE.PointLight>(null)
    const { scene, animations } = useGLTF(UAV_MODEL_URL) as any
    const { actions } = useAnimations(animations, group)
    const lastUpdateTimeRef = useRef<number>(0)
    const throttleInterval = 100

    // Use state for current position, initialized from prop
    const [currentPosition, setCurrentPosition] = useState<THREE.Vector3>(
        new THREE.Vector3(...position)
    )

    // Storing initial position from props might still be useful for auto flight logic
    const initialPosition = useRef<THREE.Vector3>(
        new THREE.Vector3(...position)
    )
    // Update initialPosition ref if the position prop fundamentally changes
    useEffect(() => {
        initialPosition.current.set(...position)
    }, [position])

    const [targetPosition, setTargetPosition] = useState<THREE.Vector3>(
        new THREE.Vector3(...position) // Initialize target with initial prop position
    )
    const moveSpeed = useRef(0.5) // 移動速度控制
    const lastDirection = useRef(new THREE.Vector3(0, 0, 0)) // 保存上一幀的方向向量
    const turbulence = useRef({ x: 0, y: 0, z: 0 }) // 模擬風的影響
    const velocity = useRef(new THREE.Vector3(0, 0, 0)) // 物理速度向量
    const acceleration = useRef(0.5) // 加速度
    const deceleration = useRef(0.3) // 減速度
    const maxSpeed = useRef(1.5) // 最大速度

    // 飛行模式控制
    const flightModes = ['cruise', 'hover', 'agile', 'explore'] as const
    type FlightMode = (typeof flightModes)[number]
    const [flightMode, setFlightMode] = useState<FlightMode>('cruise')
    const flightModeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
    const flightModeParams = useRef({
        cruise: {
            pathCurvature: 0.2,
            speedFactor: 1.0,
            turbulenceEffect: 0.2,
            heightVariation: 5,
            smoothingFactor: 0.85,
        },
        hover: {
            pathCurvature: 0.4,
            speedFactor: 0.6,
            turbulenceEffect: 0.4,
            heightVariation: 2,
            smoothingFactor: 0.7,
        },
        agile: {
            pathCurvature: 0.5,
            speedFactor: 1.5,
            turbulenceEffect: 0.1,
            heightVariation: 15,
            smoothingFactor: 0.6,
        },
        explore: {
            pathCurvature: 0.3,
            speedFactor: 0.8,
            turbulenceEffect: 0.3,
            heightVariation: 10,
            smoothingFactor: 0.8,
        },
    })

    // 添加路徑點系統，使飛行軌跡更自然
    const [waypoints, setWaypoints] = useState<THREE.Vector3[]>([])
    const currentWaypoint = useRef(0)
    const pathCurvature = useRef(0.3 + Math.random() * 0.4) // 路徑曲率控制

    // 每隔一段時間更新自然的擾動
    useEffect(() => {
        const updateTurbulence = () => {
            const strength =
                flightModeParams.current[flightMode].turbulenceEffect
            turbulence.current = {
                x: (Math.random() - 0.5) * 0.4 * strength,
                y: (Math.random() - 0.5) * 0.2 * strength,
                z: (Math.random() - 0.5) * 0.4 * strength,
            }
        }

        updateTurbulence()
        const interval = setInterval(updateTurbulence, 2000) // 每2秒更新一次擾動

        // 隨機切換飛行模式
        const switchFlightMode = () => {
            const nextMode =
                flightModes[Math.floor(Math.random() * flightModes.length)]
            setFlightMode(nextMode)
            console.log(`UAV 切換到${nextMode}飛行模式`)

            // 根據飛行模式調整物理參數
            const modeParams = flightModeParams.current[nextMode]
            pathCurvature.current = modeParams.pathCurvature
            maxSpeed.current = 1.0 * modeParams.speedFactor
            acceleration.current = 0.5 * modeParams.speedFactor

            // 動態調整模式持續時間
            const duration = 10000 + Math.random() * 15000
            if (flightModeTimer.current) clearTimeout(flightModeTimer.current)
            flightModeTimer.current = setTimeout(switchFlightMode, duration)
        }

        // 初始啟動飛行模式切換
        flightModeTimer.current = setTimeout(switchFlightMode, 10000)

        return () => {
            clearInterval(interval)
            if (flightModeTimer.current) clearTimeout(flightModeTimer.current)
        }
    }, [flightMode])

    // 使用貝塞爾曲線生成平滑路徑
    const generateBezierPath = (
        start: THREE.Vector3,
        end: THREE.Vector3,
        points: number = 10
    ) => {
        const path: THREE.Vector3[] = []

        // 計算起點到終點的方向向量
        const direction = new THREE.Vector3().subVectors(end, start).normalize()

        // 計算垂直於方向的軸
        const up = new THREE.Vector3(0, 1, 0)
        const perpendicular = new THREE.Vector3()
            .crossVectors(direction, up)
            .normalize()

        // 如果結果為零向量（原始向量與參考向量平行），選擇另一個參考向量
        if (perpendicular.lengthSq() < 0.001) {
            perpendicular
                .crossVectors(direction, new THREE.Vector3(1, 0, 0))
                .normalize()
        }

        // 計算曲線的控制點
        const distance = start.distanceTo(end)
        const curveOffset = distance * pathCurvature.current

        // 產生兩個控制點以創建三次貝塞爾曲線
        const offset1 = perpendicular
            .clone()
            .multiplyScalar(curveOffset * (Math.random() > 0.5 ? 1 : -1))
        const offset2 = perpendicular
            .clone()
            .multiplyScalar(curveOffset * (Math.random() > 0.5 ? 1 : -1))

        // 控制點高度變化
        const heightVariation =
            flightModeParams.current[flightMode].heightVariation

        // 第一控制點：沿方向前進1/3距離 + 偏移 + 隨機高度
        const control1 = start
            .clone()
            .add(direction.clone().multiplyScalar(distance / 3))
            .add(offset1)
            .add(
                new THREE.Vector3(0, (Math.random() - 0.3) * heightVariation, 0)
            )

        // 第二控制點：沿方向前進2/3距離 + 偏移 + 隨機高度
        const control2 = start
            .clone()
            .add(direction.clone().multiplyScalar((distance * 2) / 3))
            .add(offset2)
            .add(
                new THREE.Vector3(0, (Math.random() - 0.3) * heightVariation, 0)
            )

        // 使用三次貝塞爾曲線生成平滑路徑
        for (let i = 0; i < points; i++) {
            const t = i / (points - 1)

            // 三次貝塞爾曲線公式: B(t) = (1-t)^3 * P0 + 3(1-t)^2 * t * P1 + 3(1-t) * t^2 * P2 + t^3 * P3
            const b0 = Math.pow(1 - t, 3)
            const b1 = 3 * Math.pow(1 - t, 2) * t
            const b2 = 3 * (1 - t) * Math.pow(t, 2)
            const b3 = Math.pow(t, 3)

            const point = new THREE.Vector3(
                b0 * start.x + b1 * control1.x + b2 * control2.x + b3 * end.x,
                b0 * start.y + b1 * control1.y + b2 * control2.y + b3 * end.y,
                b0 * start.z + b1 * control1.z + b2 * control2.z + b3 * end.z
            )

            // 加入細微的水平擾動，使路徑更加自然
            if (i > 0 && i < points - 1) {
                const smallNoise = new THREE.Vector3(
                    (Math.random() - 0.5) * 2,
                    (Math.random() - 0.5) * 1,
                    (Math.random() - 0.5) * 2
                )
                point.add(smallNoise)
            }

            path.push(point)
        }

        return path
    }

    // 生成新的隨機目標位置，考慮飛行模式
    const generateNewTarget = () => {
        const modeParams = flightModeParams.current[flightMode]

        // 基於飛行模式調整隨機範圍
        let distance
        let heightRange

        switch (flightMode) {
            case 'hover':
                // 徘徊模式：較小範圍，較低高度
                distance = 80 + Math.random() * 120
                heightRange = [40, 80]
                break
            case 'agile':
                // 敏捷模式：中等範圍，較大高度變化
                distance = 100 + Math.random() * 150
                heightRange = [30, 120]
                break
            case 'explore':
                // 探索模式：大範圍，較大高度
                distance = 150 + Math.random() * 200
                heightRange = [60, 150]
                break
            case 'cruise':
            default:
                // 巡航模式：標準範圍，適中高度
                distance = 120 + Math.random() * 150
                heightRange = [50, 100]
        }

        // 創建隨機方向向量
        const randomDirection = new THREE.Vector3(
            Math.random() * 2 - 1,
            0,
            Math.random() * 2 - 1
        ).normalize()

        // 計算新坐標
        const newX = initialPosition.current.x + randomDirection.x * distance
        const newZ = initialPosition.current.z + randomDirection.z * distance
        const newY =
            heightRange[0] + Math.random() * (heightRange[1] - heightRange[0])

        return new THREE.Vector3(newX, newY, newZ)
    }

    // 檢查是否到達目標位置
    const hasReachedTarget = (
        current: THREE.Vector3,
        target: THREE.Vector3,
        threshold: number = 5
    ) => {
        return current.distanceTo(target) < threshold
    }

    // 生成飛行路徑
    const generatePath = () => {
        const start = currentPosition
        const end = generateNewTarget()

        // 路徑點數量與距離成比例，確保轉彎平滑
        const distance = start.distanceTo(end)
        const points = Math.max(8, Math.min(20, Math.floor(distance / 15)))

        // 使用貝塞爾曲線生成平滑路徑
        const newWaypoints = generateBezierPath(start, end, points)
        setWaypoints(newWaypoints)
        currentWaypoint.current = 0

        // 設置最終目標點
        setTargetPosition(end)

        return newWaypoints
    }

    useEffect(() => {
        // 播放第一個動畫（假設動畫名稱未知時使用索引）
        const action = actions[Object.keys(actions)[0]]
        if (action) {
            action.setLoop(THREE.LoopRepeat, Infinity) // 設置循環播放
            action.play()
        }

        // 生成初始路徑
        generatePath()

        // 確保模型及其所有子物體設置正確的陰影屬性
        if (scene) {
            scene.traverse((child: THREE.Object3D) => {
                if ((child as THREE.Mesh).isMesh) {
                    child.castShadow = true
                    child.receiveShadow = true
                }
            })
        }
    }, [actions, scene])

    // 處理UAV的移動
    useFrame((state, delta) => {
        // Always update visual position based on state, regardless of auto mode
        if (group.current) {
            group.current.position.copy(currentPosition)
        }
        // Update light position relative to UAV
        if (lightRef.current) {
            lightRef.current.position.set(0, 5, 0) // 相對於UAV的位置
        }

        // Only run auto-flight logic if auto is true
        if (!auto) return
        if (!group.current || !lightRef.current || waypoints.length === 0)
            return

        const current = currentPosition.clone() // Use state as the source of truth
        const modeParams = flightModeParams.current[flightMode]

        // 確定當前目標路徑點
        const currentTargetIndex = currentWaypoint.current

        // 如果已經到達最後一個路徑點
        if (currentTargetIndex >= waypoints.length - 1) {
            // 生成新路徑
            const newPath = generatePath()
            if (newPath.length > 0) {
                // 重設速度
                velocity.current.set(0, 0, 0)
                return // 等待下一幀開始新路徑
            }
        }

        // 獲取當前目標路徑點
        const currentTarget = waypoints[currentTargetIndex]

        // 檢查是否到達當前路徑點
        if (hasReachedTarget(current, currentTarget, 10)) {
            // 移動到下一個路徑點
            currentWaypoint.current = Math.min(
                currentWaypoint.current + 1,
                waypoints.length - 1
            )
            return
        }

        // 計算朝向目標的方向
        const rawDirection = new THREE.Vector3()
            .subVectors(currentTarget, current)
            .normalize()

        // 平滑方向轉變，保留前一幀方向的一部分影響，使轉向更漸進
        const smoothingFactor = modeParams.smoothingFactor // 飛行模式決定平滑程度
        const smoothDirection = new THREE.Vector3(
            smoothingFactor * rawDirection.x +
                (1 - smoothingFactor) * lastDirection.current.x,
            smoothingFactor * rawDirection.y +
                (1 - smoothingFactor) * lastDirection.current.y,
            smoothingFactor * rawDirection.z +
                (1 - smoothingFactor) * lastDirection.current.z
        ).normalize()

        lastDirection.current = smoothDirection.clone()

        // 添加風的自然擾動，根據飛行模式調整強度
        const turbulenceEffect = modeParams.turbulenceEffect
        const movementWithTurbulence = new THREE.Vector3(
            smoothDirection.x + turbulence.current.x * turbulenceEffect,
            smoothDirection.y + turbulence.current.y * turbulenceEffect,
            smoothDirection.z + turbulence.current.z * turbulenceEffect
        ).normalize()

        // 計算速度 - 使用物理加速度和減速度
        const distanceToTarget = current.distanceTo(currentTarget)
        const targetSpeed =
            Math.min(maxSpeed.current, distanceToTarget / 10) *
            modeParams.speedFactor

        // 如果當前速度小於目標速度，加速；否則減速
        const currentSpeed = velocity.current.length()

        // 加速度隨距離變化
        let accelerationFactor =
            Math.min(1, distanceToTarget / 50) *
            (currentSpeed < targetSpeed
                ? acceleration.current
                : -deceleration.current)

        // 根據飛行模式調整加速度
        const speedChange = accelerationFactor * delta * 10

        // 更新速度向量 - 向目標方向逐漸調整
        velocity.current.lerp(
            movementWithTurbulence.clone().multiplyScalar(targetSpeed),
            delta * 2
        )

        // 調整速度大小
        if (velocity.current.length() > 0) {
            if (currentSpeed + speedChange > 0) {
                velocity.current
                    .normalize()
                    .multiplyScalar(currentSpeed + speedChange)
            } else {
                velocity.current.set(0, 0, 0)
            }
        }

        // 限制最大速度
        if (
            velocity.current.length() >
            maxSpeed.current * modeParams.speedFactor
        ) {
            velocity.current
                .normalize()
                .multiplyScalar(maxSpeed.current * modeParams.speedFactor)
        }

        // 計算新位置
        const newPosition = current
            .clone()
            .add(velocity.current.clone().multiplyScalar(delta * 30))

        // 更新組件位置
        group.current.position.set(newPosition.x, newPosition.y, newPosition.z)

        // 更新當前位置
        setCurrentPosition(newPosition)

        // Throttled update for parent component
        const now = performance.now()
        if (now - lastUpdateTimeRef.current > throttleInterval) {
            onPositionUpdate?.([newPosition.x, newPosition.y, newPosition.z])
            lastUpdateTimeRef.current = now
        }
    })

    // 新增 effect 處理手動移動
    useEffect(() => {
        if (!auto && manualDirection) {
            let finalPosition: [number, number, number] | null = null
            setCurrentPosition((prev) => {
                const next = prev.clone()
                switch (manualDirection) {
                    case 'up':
                        next.y += 1
                        break
                    case 'down':
                        next.y -= 1
                        break
                    case 'left':
                        next.x -= 1
                        break
                    case 'right':
                        next.x += 1
                        break
                    case 'ascend':
                        next.z += 1
                        break
                    case 'descend':
                        next.z -= 1
                        break
                    case 'left-up':
                        next.x -= 1
                        next.z -= 1
                        break
                    case 'right-up':
                        next.x += 1
                        next.z -= 1
                        break
                    case 'left-down':
                        next.x -= 1
                        next.z += 1
                        break
                    case 'right-down':
                        next.x += 1
                        next.z += 1
                        break
                    case 'rotate-left':
                        if (group.current) {
                            group.current.rotation.y += 0.087 // 約 5 度
                        }
                        break
                    case 'rotate-right':
                        if (group.current) {
                            group.current.rotation.y -= 0.087 // 約 5 度
                        }
                        break
                }
                finalPosition = [next.x, next.y, next.z]
                return next
            })
            if (onManualMoveDone) onManualMoveDone()
            if (finalPosition) {
                // Throttled update for parent component (manual mode)
                const now = performance.now()
                if (now - lastUpdateTimeRef.current > throttleInterval) {
                    onPositionUpdate?.(finalPosition)
                    lastUpdateTimeRef.current = now
                }
            }
        }
    }, [
        manualDirection,
        auto,
        onManualMoveDone,
        onPositionUpdate,
        throttleInterval,
    ])

    // 調試：輸出模型載入信息
    useEffect(() => {
        console.log('UAV 模型載入成功:', scene)
        console.log('光源已添加到組件中')
    }, [scene])

    return (
        <group ref={group} position={position} scale={scale}>
            <primitive
                object={scene}
                onUpdate={(self: THREE.Object3D) =>
                    self.traverse((child: THREE.Object3D) => {
                        if ((child as THREE.Mesh).isMesh) {
                            const mesh = child as THREE.Mesh
                            // 確保材質支援光照
                            if (
                                mesh.material instanceof THREE.MeshBasicMaterial
                            ) {
                                console.warn(
                                    'UAV 模型使用 MeshBasicMaterial，不支援光照'
                                )
                                // 替換為 MeshStandardMaterial
                                mesh.material = new THREE.MeshStandardMaterial({
                                    color: 0xffffff,
                                })
                            }
                            mesh.castShadow = true
                            mesh.receiveShadow = true
                        }
                    })
                }
            />
            {/* 添加點光源，增強光照效果，且設置為投射陰影 */}
            <pointLight
                ref={lightRef}
                position={[0, 5, 0]} // 調整位置以適應 UAV 模型
                intensity={2000} // 增加強度
                distance={100} // 擴大照射範圍
                decay={2}
                color={0xffffff}
                castShadow // 開啟陰影投射
                shadow-mapSize-width={512} // 設置陰影貼圖大小
                shadow-mapSize-height={512}
                shadow-bias={-0.001} // 減少陰影偏差
            />
        </group>
    )
}

// 定義 StaticModel 組件來處理靜態模型
function StaticModel({
    url,
    position,
    scale,
}: {
    url: string
    position: [number, number, number]
    scale: [number, number, number]
}) {
    const { scene } = useGLTF(url) as any

    // 創建一個深度克隆的新實例，避免共享同一個模型實例
    const clonedScene = useMemo(() => {
        // 深度克隆場景，確保每個設備有自己獨立的模型實例
        const clone = scene.clone(true)

        // 確保所有材質也被複製，避免材質共享
        clone.traverse((node: THREE.Object3D) => {
            if ((node as THREE.Mesh).isMesh) {
                const mesh = node as THREE.Mesh
                if (mesh.material) {
                    // 如果是材質數組
                    if (Array.isArray(mesh.material)) {
                        mesh.material = mesh.material.map((mat) => mat.clone())
                    } else {
                        // 單個材質
                        mesh.material = mesh.material.clone()
                    }
                }
            }
        })

        return clone
    }, [scene])

    return (
        <primitive
            object={clonedScene}
            position={position}
            scale={scale}
            onUpdate={(self: THREE.Object3D) =>
                self.traverse((child: THREE.Object3D) => {
                    if ((child as THREE.Mesh).isMesh) {
                        child.castShadow = true
                        child.receiveShadow = true
                    }
                })
            }
        />
    )
}

function Etoile({
    devices = [],
    auto,
    manualControl,
    manualDirection,
    onUAVPositionUpdate,
}: EtoileProps) {
    const { scene: mainScene } = useGLTF(SCENE_URL) as any
    const { controls } = useThree()
    const [rays, setRays] = useState<THREE.Object3D[]>([])
    const [pendingManual, setPendingManual] = useState<string | null>(null)

    useLayoutEffect(() => {
        ;(controls as OrbitControlsImpl)?.target?.set(0, 0, 0)
    }, [controls])

    const prepared = useMemo(() => {
        const root = mainScene.clone(true)
        let maxArea = 0
        let groundMesh: THREE.Mesh | null = null

        // 載入衛星圖貼圖
        const loader = new TextureLoader()
        const satelliteTexture = loader.load(SATELLITE_TEXTURE_URL)
        satelliteTexture.wrapS = RepeatWrapping
        satelliteTexture.wrapT = RepeatWrapping
        satelliteTexture.colorSpace = SRGBColorSpace
        satelliteTexture.repeat.set(1, 1) // 設置為1，顯示完整衛星圖
        satelliteTexture.anisotropy = 16 // 提高清晰度

        root.traverse((o: THREE.Object3D) => {
            if ((o as THREE.Mesh).isMesh) {
                const m = o as THREE.Mesh
                m.castShadow = true
                m.receiveShadow = true

                if (m.geometry) {
                    m.geometry.computeBoundingBox()
                    const bb = m.geometry.boundingBox
                    if (bb) {
                        const size = new THREE.Vector3()
                        bb.getSize(size)
                        const area = size.x * size.z

                        if (area > maxArea) {
                            if (groundMesh) groundMesh.castShadow = true
                            maxArea = area
                            groundMesh = m

                            // 將材質設為使用衛星圖的 MeshStandardMaterial
                            groundMesh.material =
                                new THREE.MeshStandardMaterial({
                                    map: satelliteTexture,
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
                        }
                    }
                }
            }
        })
        return root
    }, [mainScene])

    const deviceMeshes = useMemo(() => {
        return devices.map((device) => {
            if (device.role === 'receiver') {
                return (
                    <AnimatedUAV
                        key={device.id}
                        position={[
                            device.position_x,
                            device.position_z,
                            device.position_y,
                        ]}
                        scale={[UAV_SCALE, UAV_SCALE, UAV_SCALE]}
                        auto={auto}
                        manualDirection={manualDirection}
                        onManualMoveDone={() =>
                            manualControl && manualControl(null)
                        }
                        onPositionUpdate={onUAVPositionUpdate}
                    />
                )
            } else if (device.role === 'desired') {
                return (
                    <StaticModel
                        key={device.id}
                        url={BS_MODEL_URL}
                        position={[
                            device.position_x,
                            device.position_z + 5,
                            device.position_y,
                        ]}
                        scale={[0.05, 0.05, 0.05]}
                    />
                )
            } else if (device.role === 'jammer') {
                return (
                    <StaticModel
                        key={device.id}
                        url={JAMMER_MODEL_URL}
                        position={[
                            device.position_x,
                            device.position_z + 5,
                            device.position_y,
                        ]}
                        scale={[0.005, 0.005, 0.005]}
                    />
                )
            } else {
                return null
            }
        })
    }, [devices, auto, manualDirection, onUAVPositionUpdate])

    return (
        <Bounds>
            <primitive object={prepared} castShadow receiveShadow />
            {deviceMeshes}
            {/* {rays.map((ray, index) => <primitive key={`ray-${index}`} object={ray} />)} */}
        </Bounds>
    )
}

interface SceneViewProps {
    devices: Device[]
    auto: boolean
    manualDirection?:
        | 'up'
        | 'down'
        | 'left'
        | 'right'
        | 'ascend'
        | 'descend'
        | 'left-up'
        | 'right-up'
        | 'left-down'
        | 'right-down'
        | 'rotate-left'
        | 'rotate-right'
        | null
    onManualControl?: (
        direction:
            | 'up'
            | 'down'
            | 'left'
            | 'right'
            | 'ascend'
            | 'descend'
            | 'left-up'
            | 'right-up'
            | 'left-down'
            | 'right-down'
            | 'rotate-left'
            | 'rotate-right'
            | null
    ) => void
    onUAVPositionUpdate?: (position: [number, number, number]) => void
}

// 星空星點數量
const STAR_COUNT = 180

// 定義星點型別
interface Star {
    left: number
    top: number
    size: number
    baseOpacity: number
    phase: number
    speed: number
    animOpacity: number
}

// 產生星點初始資料（只在初始渲染時產生一次）
function createStars(): Star[] {
    return Array.from({ length: STAR_COUNT }, () => {
        const baseOpacity = Math.random() * 0.7 + 0.3
        return {
            left: Math.random() * 100,
            top: Math.random() * 100,
            size: Math.random() * 2 + 1,
            baseOpacity,
            phase: Math.random() * Math.PI * 2,
            speed: Math.random() * 1.0 + 1.0, // 閃爍速度 1.0~2.0
            animOpacity: baseOpacity,
        }
    })
}

export default function SceneView({
    devices = [],
    auto,
    manualDirection,
    onManualControl,
    onUAVPositionUpdate,
}: SceneViewProps) {
    // 星空動畫狀態
    const [starAnim, setStarAnim] = useState(() => createStars())

    // 輕微閃爍動畫：每 60ms 更新一次透明度
    useEffect(() => {
        let mounted = true
        let frame = 0
        const interval = setInterval(() => {
            if (!mounted) return
            setStarAnim((prev) =>
                prev.map((star, i) => {
                    // 用 baseOpacity 為中心，sin 波動幅度 0.5，速度不同
                    const t = frame / 30 // 時間參數
                    const flicker = Math.sin(t * star.speed + star.phase) * 0.5
                    let opacity = star.baseOpacity + flicker
                    // 限制在 0.15~1.0 之間
                    opacity = Math.max(0.15, Math.min(1, opacity))
                    return { ...star, animOpacity: opacity }
                })
            )
            frame++
        }, 60)
        return () => {
            mounted = false
            clearInterval(interval)
        }
    }, [])

    return (
        <div
            className="scene-container"
            style={{
                width: '100%',
                height: '100%',
                position: 'relative',
                background:
                    'radial-gradient(ellipse at bottom, #1b2735 0%, #090a0f 100%)',
                overflow: 'hidden',
            }}
        >
            {/* 星空星點層（在最底層，不影響互動） */}
            <div
                style={{
                    position: 'absolute',
                    inset: 0,
                    zIndex: 0,
                    pointerEvents: 'none',
                }}
            >
                {starAnim.map((star, i) => (
                    <div
                        key={i}
                        style={{
                            position: 'absolute',
                            left: `${star.left}%`,
                            top: `${star.top}%`,
                            width: `${star.size}px`,
                            height: `${star.size}px`,
                            borderRadius: '50%',
                            background: 'white',
                            opacity: star.animOpacity ?? star.baseOpacity,
                            filter: 'blur(0.5px)',
                            transition: 'opacity 0.2s linear',
                        }}
                    />
                ))}
            </div>
            {/* 3D Canvas內容照舊，會蓋在星空上 */}
            <Canvas
                shadows
                camera={{ position: [40, 80, 120], near: 0.1, far: 1e4 }}
                gl={{
                    toneMapping: THREE.ACESFilmicToneMapping,
                    toneMappingExposure: 1.2,
                    alpha: true,
                }}
            >
                <hemisphereLight args={[0xffffff, 0x444444, 1.0]} />
                <ambientLight intensity={0.2} />
                <directionalLight
                    castShadow
                    position={[15, 30, 10]}
                    intensity={1.5} // 降低方向光強度以突出點光源
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
                    <Etoile
                        devices={devices}
                        auto={auto}
                        manualDirection={manualDirection}
                        manualControl={onManualControl}
                        onUAVPositionUpdate={onUAVPositionUpdate}
                    />
                    <ContactShadows
                        position={[0, 0.1, 0]}
                        opacity={0.4}
                        scale={400}
                        blur={1.5}
                        far={50}
                    />
                </Suspense>
                <OrbitControls makeDefault />
            </Canvas>
        </div>
    )
}
