// src/SceneView.tsx
import { Suspense, useLayoutEffect, useMemo } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { ContactShadows } from '@react-three/drei'
import { Bounds, OrbitControls, useGLTF } from '@react-three/drei'
import { GLTF } from 'three/examples/jsm/loaders/GLTFLoader'
import * as THREE from 'three'
import { TextureLoader, RepeatWrapping } from 'three'

// 修正 API 路徑，使用 GET 端點而非 POST 端點
// 前端路徑帶 /api 前綴，vite 會將其重寫並代理到後端
const SCENE_URL = '/api/v1/sionna/scene'

/* ---------------- 1) 讀 glTF → 加材質 / Normals ---------------- */
function Etoile() {
    const { scene } = useGLTF(SCENE_URL) as GLTF
    const { controls } = useThree()

    /** 只在 glTF 載完後跑一次 → 回傳處理後的 clone */
    const prepared = useMemo(() => {
        const root = scene.clone(true) // ❗ 不要直接改原始 glTF，clone 一份

        // ─── 2.1 載入並設定地板貼圖 ────────────────────────────────
        const loader = new TextureLoader()
        const groundTex = loader.load('/textures/groundTex.png')
        const normalTex = loader.load('/textures/normalTex.png')
        const roughnessTex = loader.load('/textures/roughnessTex.png')
        const displacementTex = loader.load('/textures/displacementTex.png')
        const aoTex = loader.load('/textures/aoTex.png')
        // 把它們放進一個陣列，並明確標注為 Texture[]
        const textures: THREE.Texture[] = [
            groundTex,
            normalTex,
            roughnessTex,
            displacementTex,
            aoTex,
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
            tex.encoding = THREE.SRGBColorSpace
        })

        // 尋找最大面積（可能是地面）的網格
        let maxArea = 0
        let groundMesh: THREE.Mesh | null = null
        root.traverse((o) => {
            if ((o as THREE.Mesh).isMesh) {
                const m = o as THREE.Mesh
                m.geometry.computeBoundingBox()
                m.castShadow = true
                m.receiveShadow = false
                const bb = m.geometry.boundingBox!
                const size = new THREE.Vector3()
                bb.getSize(size)
                const area = size.x * size.z
                if (area > maxArea) {
                    maxArea = area
                    groundMesh = m
                }
            }
        })

        // 2.2 覆寫地板為「貼圖 + 白色底」材質
        if (groundMesh) {
            groundMesh.material = new THREE.MeshStandardMaterial({
                map: groundTex,
                normalMap: normalTex,
                roughnessMap: roughnessTex,
                displacementMap: displacementTex,
                displacementScale: 5,
                aoMap: aoTex,
                aoMapIntensity: 1.5,
                displacementScale: 5, // ← 擠出高度量 (可從 1→20 微調)
                displacementBias: -2, // ← 讓整體往下移避免浮在空中
                color: 0xffffff,
                roughness: 1.0,
                metalness: 0.0,
                emissive: 0x555555,
                emissiveIntensity: 0.3,
                vertexColors: false,
                normalScale: new THREE.Vector2(0.5, 0.5),
            })
            groundMesh.receiveShadow = true // ← 地板接收陰影
            groundMesh.castShadow = false // ← 地板本身不投影到自己        }

            const geom = groundMesh.geometry as THREE.BufferGeometry
            const uvAttr = geom.attributes.uv as
                | THREE.BufferAttribute
                | undefined

            if (uvAttr) {
                // 如果確定有 uv，就設第二組 uv2
                geom.setAttribute(
                    'uv2',
                    new THREE.BufferAttribute(
                        uvAttr.array,
                        uvAttr.itemSize,
                        uvAttr.normalized
                    )
                )
            } else {
                console.warn('groundMesh 沒有 UV，跳過 aoMap 設定')
                // 如果一定要用 AO，可以改用全局 AO 或 ContactShadows，不用靠 aoMap
                groundMesh.material.aoMap = undefined
            }
        }

        useLayoutEffect(() => {
            controls?.target.set(0, 0, 0)
        }, [controls])

        return root
    }, [scene])
    // <Bounds fit clip observe margin={0.8}>

    return (
        <Bounds>
            <primitive object={prepared} />
        </Bounds>
    )
}

export default function SceneView() {
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
                    toneMappingExposure: 0.9,
                }}
            >
                <color attach="background" args={['#7f7f7f']} />
                <hemisphereLight
                    skyColor={0xffffff}
                    groundColor={0x333333}
                    intensity={0.3}
                />
                <ambientLight intensity={0.05} />
                <directionalLight
                    castShadow
                    position={[5, 10, 5]}
                    intensity={3}
                    shadow-mapSize-width={4096}
                    shadow-mapSize-height={4096}
                    shadow-camera-near={1}
                    shadow-camera-far={3000}
                    shadow-camera-top={1000}
                    shadow-camera-bottom={-1000}
                    shadow-camera-left={1000}
                    shadow-camera-right={-1000}
                    shadow-bias={-0.0002}
                    shadow-radius={10}
                />
                <directionalLight
                    castShadow
                    position={[20, 5, 20]} // 低角度，從側面掃射
                    intensity={0.8}
                    shadow-mapSize-width={2048}
                    shadow-mapSize-height={2048}
                    shadow-bias={-0.0002}
                />
                <directionalLight position={[-5, -10, -5]} intensity={0.8} />
                <Suspense fallback={null}>
                    <Etoile />
                    <ContactShadows
                        position={[0, 0, 0]} // z=0 地面
                        opacity={0.3} // 控制陰影深淺
                        width={200} // 覆蓋面積／寬度
                        height={200} // 覆蓋面積／深度
                        blur={2} // 模糊半徑
                        far={10} // 阻擋距離（算到物件底面）
                    />
                </Suspense>
                <OrbitControls makeDefault />
            </Canvas>
        </div>
    )
}
