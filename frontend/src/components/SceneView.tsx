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
import { GLTF } from 'three/examples/jsm/loaders/GLTFLoader'
import * as THREE from 'three'
import { TextureLoader, RepeatWrapping, SRGBColorSpace } from 'three'
import { Device } from '../App'

// 靜態檔案路徑
const SCENE_URL = '/static/models/XIN.glb'
const UAV_MODEL_URL = '/api/v1/sionna/models/uav1' // 替換為帶動畫的 GLB 模型路徑
const BS_MODEL_URL = '/api/v1/sionna/models/tx' // BS 模型路徑
const JAMMER_MODEL_URL = '/api/v1/sionna/models/jammer' // Jammer 模型路徑

// 材質和尺寸定義
const DEVICE_SIZE = 5
const UAV_SCALE = 5
const UAV_Y_OFFSET = 10

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
}: {
    position: [number, number, number]
    scale: [number, number, number]
}) {
    const group = useRef<THREE.Group>(null)
    const { scene, animations } = useGLTF(UAV_MODEL_URL) as GLTF
    const { actions } = useAnimations(animations, group)

    useEffect(() => {
        // 播放第一個動畫（假設動畫名稱未知時使用索引）
        const action = actions[Object.keys(actions)[0]]
        if (action) {
            action.setLoop(THREE.LoopRepeat, Infinity) // 設置循環播放
            action.play()
        }
    }, [actions])

    useFrame((state, delta) => {
        // 可選：添加額外旋轉效果
        if (group.current) {
            group.current.rotation.y += delta * 0.5
        }
    })

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
            {/* 添加點光源，增強光照效果 */}
            <pointLight
                position={[0, 10, 0]} // 調整位置以適應 UAV 模型
                intensity={2000} // 增加強度
                distance={100} // 擴大照射範圍
                decay={2}
                color={0xffffff}
                castShadow // 開啟陰影投射
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
    const { scene } = useGLTF(url) as GLTF
    return (
        <primitive
            object={scene}
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

function Etoile({ devices = [] }: EtoileProps) {
    const { scene: mainScene } = useGLTF(SCENE_URL) as GLTF
    const { controls } = useThree()
    const [rays, setRays] = useState<THREE.Object3D[]>([])

    useLayoutEffect(() => {
        ;(controls as OrbitControlsImpl)?.target?.set(0, 0, 0)
    }, [controls])

    const prepared = useMemo(() => {
        const root = mainScene.clone(true)
        let maxArea = 0
        let groundMesh: THREE.Mesh | null = null

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
                            textures.forEach((tex) => {
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
                        }
                    }
                }
            }
        })
        return root
    }, [mainScene])

    useEffect(() => {
        // 射線數據加載邏輯保持不變（這裡省略具體實現）
    }, [devices])

    const deviceMeshes = useMemo(() => {
        return devices.map((device) => {
            if (device.name.startsWith('rx-')) {
                return (
                    <AnimatedUAV
                        key={device.id}
                        position={[device.x, device.z + UAV_Y_OFFSET, device.y]}
                        scale={[UAV_SCALE, UAV_SCALE, UAV_SCALE]}
                    />
                )
            } else if (device.name.startsWith('tx-')) {
                return (
                    <StaticModel
                        key={device.id}
                        url={BS_MODEL_URL}
                        position={[device.x, device.z + 5, device.y]}
                        scale={[1, 1, 1]}
                    />
                )
            } else if (device.name.startsWith('int-')) {
                return (
                    <StaticModel
                        key={device.id}
                        url={JAMMER_MODEL_URL}
                        position={[device.x, device.z + 5, device.y]}
                        scale={[10, 10, 10]}
                    />
                )
            } else {
                return null
            }
        })
    }, [devices])

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
                    toneMappingExposure: 1.2, // 增強整體光照效果 -> 調低整體亮度
                }}
            >
                <color attach="background" args={['#7f7f7f']} />
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
                    <Etoile devices={devices} />
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
