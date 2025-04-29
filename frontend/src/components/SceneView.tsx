// src/SceneView.tsx
import { Suspense, useLayoutEffect, useMemo } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { Bounds, OrbitControls, useGLTF } from '@react-three/drei'
import { GLTF } from 'three/examples/jsm/loaders/GLTFLoader'
import * as THREE from 'three'

// 修正 API 路徑，使其與 vite 代理配置相符
// 前端路徑帶 /api 前綴，vite 會將其重寫並代理到後端
const SCENE_URL = '/api/v1/sionna/scene'

/* ---------------- 1) 讀 glTF → 加材質 / Normals ---------------- */
function Etoile() {
    const { scene } = useGLTF(SCENE_URL) as GLTF
    const { controls } = useThree()

    /** 只在 glTF 載完後跑一次 → 回傳處理後的 clone */
    const prepared = useMemo(() => {
        const root = scene.clone(true) // ❗ 不要直接改原始 glTF，clone 一份
        root.traverse((obj) => {
            if ((obj as THREE.Mesh).isMesh) {
                const mesh = obj as THREE.Mesh

                // (a) 沒 Normals → 補一份
                const geo = mesh.geometry as THREE.BufferGeometry
                if (!geo.attributes.normal) geo.computeVertexNormals()

                // 2) DEBUG: 看看到底有哪些 attributes
                console.log('▶ attributes', Object.keys(geo.attributes))

                // 3) 如果 loader 把頂點色叫做 'COLOR_0'，手動複製到 'color'
                scene.traverse((o) => {
                    if (o.isMesh)
                        console.log(Object.keys(o.geometry.attributes))
                })

                // 1) 开启顶点色，用 smooth shading（flatShading=false）
                const mats = Array.isArray(mesh.material)
                    ? (mesh.material as THREE.Material[])
                    : [mesh.material as THREE.MeshStandardMaterial]
                mats.forEach((m) => {
                    const mat = m as THREE.MeshStandardMaterial
                    mat.vertexColors = true
                    mat.flatShading = false // ★ smooth shading
                    mat.side = THREE.DoubleSide // ★ 双面，和 Open3D 一样
                    mat.needsUpdate = true
                })

                mesh.castShadow = true
                mesh.receiveShadow = true
            }
        })

        root.traverse((o) => {
            if ((o as THREE.Mesh).isMesh) {
                const mat = (o as THREE.Mesh)
                    .material as THREE.MeshStandardMaterial
                console.log(mat.vertexColors) // 應該印 true 或 2（VertexColors 常數）
            }
        })

        return root
    }, [scene])

    /* 讓 OrbitControls 的焦點永遠在 (0,0,0) */
    useLayoutEffect(() => {
        controls?.target.set(0, 0, 0)
    }, [controls])

    return (
        <Bounds fit clip observe margin={1.2}>
            <primitive object={prepared} />
        </Bounds>
    )
}
useGLTF.preload(SCENE_URL)

/* ---------------- 2) 畫布 + 光源 ---------------- */
export default function SceneView() {
    return (
        <div
            className="scene-container"
            style={{ width: '100%', height: '100%' }}
        >
            <Canvas
                camera={{ position: [0, 0, 1500], near: 0.1, far: 1e4 }}
                gl={{
                    outputColorSpace: THREE.SRGBColorSpace,
                    toneMapping: THREE.ACESFilmicToneMapping,
                    toneMappingExposure: 2.5,
                    physicallyCorrectLights: true,
                }}
            >
                <color attach="background" args={['#ffffff']} />

                {/* 增強版光源 */}
                <hemisphereLight
                    skyColor={[1, 1, 1]}
                    groundColor={[0.2, 0.2, 0.6]}
                    intensity={1.2}
                />
                <directionalLight position={[500, 800, 1000]} intensity={3.0} />
                <directionalLight
                    position={[0, 0, 1500]}
                    intensity={1.0}
                    target-position={[0, 0, 0]}
                />
                <ambientLight intensity={0.4} />

                <Suspense fallback={null}>
                    <Etoile />
                    {/* 如果想要環境反射，也可以打開 */}
                    {/* <Environment preset="city" intensity={1.5} /> */}
                </Suspense>

                <OrbitControls makeDefault />
            </Canvas>
        </div>
    )
}
