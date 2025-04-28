// src/SceneView.tsx
import { Suspense, useLayoutEffect, useMemo } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { Bounds, Environment, OrbitControls, useGLTF } from '@react-three/drei'
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
    const root = scene.clone(true)          // ❗ 不要直接改原始 glTF，clone 一份
    root.traverse(obj => {
      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh

        // (a) 沒 Normals → 補一份
        const geo = mesh.geometry as THREE.BufferGeometry
        if (!geo.attributes.normal) geo.computeVertexNormals()

        // (b) 給一個灰色 PBR 材質
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0x8a8a8a,
          roughness: 0.9,
          metalness: 0,
        })

        mesh.castShadow = mesh.receiveShadow = true
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
    <div className="scene-container" style={{ width: '100%', height: '100%' }}>
      <Canvas camera={{ position: [0, 0, 1500], near: 0.1, far: 1e4 }} gl={{outputColorSpace: THREE.SRGBColorSpace}}>
        <color attach="background" args={['#dcdcdc']} />
        {/*💡→ 光打亮一點 ←💡*/}
        <ambientLight intensity={0.5} />
        <directionalLight
          position={[500, 800, 1000]}
          intensity={2.3}
        />

        <Suspense fallback={null}>
          <Etoile />
          {/* HDRI 只當反射背景用 */}
          <Environment preset="sunset" intensity={1} />
        </Suspense>

        <OrbitControls makeDefault />
      </Canvas>
    </div>
  )
}
