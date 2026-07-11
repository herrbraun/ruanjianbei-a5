<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils, type VRM } from '@pixiv/three-vrm'
import {
  VRMAnimationLoaderPlugin,
  createVRMAnimationClip,
  type VRMAnimation,
} from '@pixiv/three-vrm-animation'

const IDLE_ANIMATION_URL = '/animations/chatvrm-idle-loop.vrma'

const props = defineProps<{
  assetUrl: string | null
  state: 'idle' | 'listening' | 'thinking' | 'speaking'
  audioLevel: number
}>()

const emit = defineEmits<{ error: [message: string] }>()

const mountElement = ref<HTMLDivElement>()
const unsupported = ref(false)
const renderFailed = ref(false)
let renderer: THREE.WebGLRenderer | undefined
let scene: THREE.Scene | undefined
let camera: THREE.PerspectiveCamera | undefined
let currentVrm: VRM | undefined
let headNode: THREE.Object3D | undefined
let headRestQuaternion: THREE.Quaternion | undefined
let idleMixer: THREE.AnimationMixer | undefined
let idleAction: THREE.AnimationAction | undefined
let animationFrame: number | undefined
let resizeObserver: ResizeObserver | undefined
let activeLoadController: AbortController | undefined
let idleLoadController: AbortController | undefined
let loadVersion = 0
let previousTime = 0
let blinkUntil = 0
let nextBlinkAt = 0
const headOffsetEuler = new THREE.Euler()
const headOffsetQuaternion = new THREE.Quaternion()

function disposeIdleAnimation() {
  idleLoadController?.abort()
  idleLoadController = undefined
  idleMixer?.stopAllAction()
  if (currentVrm) idleMixer?.uncacheRoot(currentVrm.scene)
  idleMixer = undefined
  idleAction = undefined
}

function disposeVrm() {
  disposeIdleAnimation()
  if (!currentVrm || !scene) return
  scene.remove(currentVrm.scene)
  VRMUtils.deepDispose(currentVrm.scene)
  currentVrm = undefined
  headNode = undefined
  headRestQuaternion = undefined
}

function cancelPendingLoad() {
  activeLoadController?.abort()
  activeLoadController = undefined
}

function disposeParsedGltf(gltf: GLTF) {
  VRMUtils.deepDispose(gltf.scene)
}

function prepareGuidePose(vrm: VRM) {
  // VRoid exports a neutral T-pose. Keep a calm arms-at-sides fallback while
  // the optional VRMA file loads and in non-idle interaction states.
  vrm.humanoid?.getNormalizedBoneNode('leftUpperArm')?.rotateZ(-1.2)
  vrm.humanoid?.getNormalizedBoneNode('rightUpperArm')?.rotateZ(1.2)
  headNode = vrm.humanoid?.getNormalizedBoneNode('head') ?? undefined
  headRestQuaternion = headNode?.quaternion.clone()
}

async function loadIdleAnimation(vrm: VRM, version: number) {
  const controller = new AbortController()
  idleLoadController = controller
  try {
    const response = await fetch(IDLE_ANIMATION_URL, { signal: controller.signal })
    if (!response.ok) throw new Error(`待机动作读取失败（${response.status}）`)
    const buffer = await response.arrayBuffer()
    const loader = new GLTFLoader()
    loader.register((parser) => new VRMAnimationLoaderPlugin(parser))
    const gltf = await new Promise<GLTF>((resolve, reject) => loader.parse(buffer, '', resolve, reject))
    const animations = gltf.userData.vrmAnimations as VRMAnimation[] | undefined
    const animation = animations?.[0]
    if (!animation) throw new Error('待机动作文件中没有可用的 VRMA 动画')
    if (controller.signal.aborted || version !== loadVersion || currentVrm !== vrm) return

    // The lockfile currently resolves three-vrm one patch release ahead of
    // three-vrm-animation. Their runtime VRM animation API is compatible,
    // while TypeScript keeps their private core types nominally separate.
    const clip = createVRMAnimationClip(
      animation,
      vrm as unknown as Parameters<typeof createVRMAnimationClip>[1],
    )
    idleMixer = new THREE.AnimationMixer(vrm.scene)
    idleAction = idleMixer.clipAction(clip)
    idleAction.setLoop(THREE.LoopRepeat, Infinity)
    idleAction.play()
  } catch (error) {
    if (!controller.signal.aborted && version === loadVersion) {
      // The viewer remains usable with its lightweight fallback motion when an
      // optional action asset cannot be loaded.
      console.warn('自然待机动作未加载，已使用基础待机：', error)
    }
  } finally {
    if (idleLoadController === controller) idleLoadController = undefined
  }
}

function frameAvatar(vrm: VRM) {
  if (!camera || !renderer) return
  vrm.scene.updateMatrixWorld(true)
  const bounds = new THREE.Box3().setFromObject(vrm.scene)
  const size = bounds.getSize(new THREE.Vector3())
  const center = bounds.getCenter(new THREE.Vector3())
  const targetY = center.y + size.y * 0.08
  const verticalHalfAngle = THREE.MathUtils.degToRad(camera.fov / 2)
  const horizontalHalfAngle = Math.atan(Math.tan(verticalHalfAngle) * camera.aspect)
  const distanceForHeight = size.y / (2 * Math.tan(verticalHalfAngle))
  const distanceForWidth = size.x / (2 * Math.tan(horizontalHalfAngle))
  const distance = Math.max(distanceForHeight, distanceForWidth) * 1.18

  camera.position.set(center.x, targetY, bounds.max.z + distance)
  camera.lookAt(center.x, targetY, center.z)
  camera.updateProjectionMatrix()
}

function rendererSize() {
  if (!renderer || !camera || !mountElement.value) return
  const { width, height } = mountElement.value.getBoundingClientRect()
  if (!width || !height) return
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  if (currentVrm) frameAvatar(currentVrm)
}

async function loadVrm() {
  const version = ++loadVersion
  cancelPendingLoad()
  disposeVrm()
  renderFailed.value = false
  if (!props.assetUrl || !scene) return
  const controller = new AbortController()
  activeLoadController = controller
  try {
    const token = localStorage.getItem('auth_token')
    const response = await fetch(props.assetUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: controller.signal,
    })
    if (!response.ok) throw new Error(`模型读取失败（${response.status}）`)
    const buffer = await response.arrayBuffer()
    const loader = new GLTFLoader()
    loader.register((parser) => new VRMLoaderPlugin(parser))
    const gltf = await new Promise<GLTF>((resolve, reject) => loader.parse(buffer, '', resolve, reject))
    if (version !== loadVersion || !scene) {
      disposeParsedGltf(gltf)
      return
    }
    const vrm = gltf.userData.vrm as VRM | undefined
    if (!vrm) {
      disposeParsedGltf(gltf)
      throw new Error('该文件未包含可用的 VRM 数据')
    }
    currentVrm = vrm
    // VRM models face +Z by convention; the previous 180° correction made
    // every guide face away from the visitor.
    currentVrm.scene.rotation.y = 0
    currentVrm.scene.position.set(0, 0, 0)
    prepareGuidePose(currentVrm)
    scene.add(currentVrm.scene)
    frameAvatar(currentVrm)
    void loadIdleAnimation(currentVrm, version)
  } catch (error) {
    if (controller.signal.aborted || version !== loadVersion) return
    renderFailed.value = true
    emit('error', error instanceof Error ? error.message : '数字人模型加载失败')
  } finally {
    if (activeLoadController === controller) activeLoadController = undefined
  }
}

function updateAvatar(time: number) {
  if (!renderer || !scene || !camera) return
  const elapsed = time / 1000
  const delta = previousTime ? (time - previousTime) / 1000 : 0
  previousTime = time
  if (currentVrm) {
    const manager = currentVrm.expressionManager
    const isSpeaking = props.state === 'speaking'
    const mouth = isSpeaking ? Math.min(1, Math.max(0, props.audioLevel * 2.25)) : 0
    manager?.setValue('aa', mouth)
    if (time >= nextBlinkAt && !blinkUntil) {
      blinkUntil = time + 110
      nextBlinkAt = time + 2600 + Math.random() * 2500
    }
    const blinking = blinkUntil > time ? 1 : 0
    if (blinkUntil && blinkUntil <= time) blinkUntil = 0
    manager?.setValue('blink', blinking)

    const hasNaturalIdle = Boolean(idleMixer && idleAction)
    if (idleMixer && idleAction) {
      const isIdle = props.state === 'idle'
      idleAction.paused = !isIdle
      idleAction.setEffectiveWeight(isIdle ? 1 : 0)
      idleMixer.update(delta)
    }

    const motion = props.state === 'idle'
      ? { breath: 0.012, sway: 0.014, bodyTurn: 0.026, headTurn: 0.07, headTilt: 0.024 }
      : props.state === 'listening'
        ? { breath: 0.009, sway: 0.009, bodyTurn: 0.012, headTurn: 0.035, headTilt: 0.018 }
        : props.state === 'thinking'
          ? { breath: 0.007, sway: 0.018, bodyTurn: 0.016, headTurn: 0.05, headTilt: 0.032 }
          : { breath: 0.009, sway: 0.007, bodyTurn: 0.009, headTurn: 0.02, headTilt: 0.014 }
    const slowLook = Math.sin(elapsed * 0.43) + Math.sin(elapsed * 0.19) * 0.42
    const breath = Math.sin(elapsed * (isSpeaking ? 3.2 : 2.05)) * motion.breath

    if (props.state === 'idle' && hasNaturalIdle) {
      currentVrm.scene.rotation.set(0, 0, 0)
      currentVrm.scene.position.set(0, 0, 0)
    } else {
      currentVrm.scene.rotation.y = slowLook * motion.bodyTurn
      currentVrm.scene.rotation.z = Math.sin(elapsed * 0.86) * motion.sway
      currentVrm.scene.position.y = breath + (isSpeaking ? Math.sin(elapsed * 5.4) * 0.004 : 0)
    }
    if ((!hasNaturalIdle || props.state !== 'idle') && headNode && headRestQuaternion) {
      headOffsetEuler.set(
        Math.sin(elapsed * 0.91) * motion.headTilt * 0.35,
        slowLook * motion.headTurn,
        Math.sin(elapsed * 0.67) * motion.headTilt,
      )
      headOffsetQuaternion.setFromEuler(headOffsetEuler)
      headNode.quaternion.copy(headRestQuaternion).multiply(headOffsetQuaternion)
    }
    currentVrm.update(delta)
  }
  renderer.render(scene, camera)
  animationFrame = requestAnimationFrame(updateAvatar)
}

onMounted(() => {
  if (!mountElement.value) return
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mountElement.value.appendChild(renderer.domElement)
    scene = new THREE.Scene()
    camera = new THREE.PerspectiveCamera(24, 1, 0.1, 100)
    scene.add(new THREE.HemisphereLight(0xfff9e9, 0x235c56, 2.8))
    const keyLight = new THREE.DirectionalLight(0xffe2ae, 2.5)
    keyLight.position.set(-3, 4, 4)
    scene.add(keyLight)
    const rimLight = new THREE.DirectionalLight(0x68b2a6, 1.8)
    rimLight.position.set(3, 2, -2)
    scene.add(rimLight)
    nextBlinkAt = performance.now() + 900
    resizeObserver = new ResizeObserver(rendererSize)
    resizeObserver.observe(mountElement.value)
    rendererSize()
    void loadVrm()
    animationFrame = requestAnimationFrame(updateAvatar)
  } catch {
    unsupported.value = true
    emit('error', '当前设备不支持 WebGL 数字人展示')
  }
})

watch(() => props.assetUrl, () => void loadVrm())

onBeforeUnmount(() => {
  loadVersion += 1
  cancelPendingLoad()
  disposeIdleAnimation()
  if (animationFrame) cancelAnimationFrame(animationFrame)
  resizeObserver?.disconnect()
  disposeVrm()
  renderer?.dispose()
  renderer?.domElement.remove()
})
</script>

<template>
  <div ref="mountElement" class="avatar-viewer" :class="{ 'is-unsupported': unsupported }">
    <slot v-if="unsupported || renderFailed || !assetUrl" />
  </div>
</template>

<style scoped>
.avatar-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 360px;
}

.avatar-viewer :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.avatar-viewer :slotted(*) {
  position: absolute;
  z-index: 1;
  inset: 0;
}
</style>
