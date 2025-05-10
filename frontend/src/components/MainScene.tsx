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
        return devices.map((device: any) => {
            if (device.role === 'receiver') {
                return (
                    <UAVFlight
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
                        uavAnimation={uavAnimation}
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
                        pivotOffset={[0, -900, 0]}
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
