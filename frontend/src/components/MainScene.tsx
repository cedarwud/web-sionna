import React, { useLayoutEffect, useMemo } from 'react'
import { useGLTF } from '@react-three/drei'
import { useThree } from '@react-three/fiber'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import * as THREE from 'three'
import { TextureLoader, RepeatWrapping, SRGBColorSpace } from 'three'
import UAVFlight, { UAVManualDirection } from './UAVFlight'
import StaticModel from './StaticModel'

const SCENE_URL = '/static/models/NYCU.glb'
const BS_MODEL_URL = '/api/v1/sionna/models/tower'
const JAMMER_MODEL_URL = '/api/v1/sionna/models/jam'
const SATELLITE_TEXTURE_URL = '/static/NYCU/textures/EXPORT_GOOGLE_SAT_WM.png'
const UAV_SCALE = 10

// 預加載模型以提高性能
useGLTF.preload(SCENE_URL)
useGLTF.preload(BS_MODEL_URL)
useGLTF.preload(JAMMER_MODEL_URL)

export interface MainSceneProps {
    devices: any[]
    auto: boolean
    manualControl?: (direction: UAVManualDirection) => void
    manualDirection?: UAVManualDirection
    onUAVPositionUpdate?: (position: [number, number, number]) => void
    uavAnimation: boolean
}

const MainScene: React.FC<MainSceneProps> = ({
    devices = [],
    auto,
    manualDirection,
    manualControl,
    onUAVPositionUpdate,
    uavAnimation,
}) => {
    // 加載主場景模型，使用 useMemo 避免重複加載
    const { scene: mainScene } = useGLTF(SCENE_URL) as any
    const { controls } = useThree()

    useLayoutEffect(() => {
        ;(controls as OrbitControlsImpl)?.target?.set(0, 0, 0)
    }, [controls])

    const prepared = useMemo(() => {
        const root = mainScene.clone(true)
        let maxArea = 0
        let groundMesh: THREE.Mesh | null = null
        const loader = new TextureLoader()
        const satelliteTexture = loader.load(SATELLITE_TEXTURE_URL)
        satelliteTexture.wrapS = RepeatWrapping
        satelliteTexture.wrapT = RepeatWrapping
        satelliteTexture.colorSpace = SRGBColorSpace
        satelliteTexture.repeat.set(1, 1)
        satelliteTexture.anisotropy = 16

        // 處理場景中的所有網格
        root.traverse((o: THREE.Object3D) => {
            if ((o as THREE.Mesh).isMesh) {
                const m = o as THREE.Mesh
                m.castShadow = true
                m.receiveShadow = true

                // 處理可能的材質問題
                if (m.material) {
                    // 確保材質能正確接收光照
                    if (Array.isArray(m.material)) {
                        m.material.forEach((mat) => {
                            if (mat instanceof THREE.MeshBasicMaterial) {
                                const newMat = new THREE.MeshStandardMaterial({
                                    color: (mat as any).color,
                                    map: (mat as any).map,
                                })
                                mat = newMat
                            }
                        })
                    } else if (m.material instanceof THREE.MeshBasicMaterial) {
                        const basicMat = m.material
                        const newMat = new THREE.MeshStandardMaterial({
                            color: basicMat.color,
                            map: basicMat.map,
                        })
                        m.material = newMat
                    }
                }

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
        // 過濾出所有接收器設備，以便管理它們的索引
        const receivers = devices.filter(
            (device) => device.role === 'receiver' && device.active
        )

        // 為每個接收器設備創建地圖以便查詢索引
        const receiverIndices = new Map()
        receivers.forEach((device, index) => {
            receiverIndices.set(device.id, index)
        })

        console.log(`總共有 ${receivers.length} 台可用的無人機`)

        return devices.map((device: any) => {
            if (device.role === 'receiver' && device.active) {
                // 獲取該接收器在所有接收器中的索引
                const receiverIndex = receiverIndices.get(device.id) || 0

                // 使用真實高度，不添加人為偏移
                console.log(
                    `渲染無人機 ID=${device.id}, 真實位置=[${device.position_x}, ${device.position_z}, ${device.position_y}]`
                )

                return (
                    <UAVFlight
                        key={`uav-${device.id}`}
                        instanceId={device.id}
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
                        uavAnimation={uavAnimation}
                    />
                )
            } else if (device.role === 'desired' && device.active) {
                return (
                    <StaticModel
                        key={`bs-${device.id}`}
                        url={BS_MODEL_URL}
                        position={[
                            device.position_x,
                            device.position_z + 5,
                            device.position_y,
                        ]}
                        scale={[0.05, 0.05, 0.05]}
                        pivotOffset={[0, -900, 0]}
                    />
                )
            } else if (device.role === 'jammer' && device.active) {
                return (
                    <StaticModel
                        key={`jam-${device.id}`}
                        url={JAMMER_MODEL_URL}
                        position={[
                            device.position_x,
                            device.position_z + 5,
                            device.position_y,
                        ]}
                        scale={[0.005, 0.005, 0.005]}
                        pivotOffset={[0, -8970, 0]}
                    />
                )
            } else {
                return null
            }
        })
    }, [
        devices,
        auto,
        manualDirection,
        onUAVPositionUpdate,
        manualControl,
        uavAnimation,
    ])

    return (
        <>
            <primitive object={prepared} castShadow receiveShadow />
            {deviceMeshes}
        </>
    )
}

export default MainScene
