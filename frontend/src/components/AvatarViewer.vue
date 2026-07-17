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

type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'welcome' | 'guiding'
type AnimatedState = Exclude<AvatarState, 'listening'>

const ANIMATION_ASSETS: Record<AnimatedState, { url: string; loop: boolean }> = {
  idle: { url: '/animations/chatvrm-idle-loop.vrma', loop: true },
  welcome: { url: '/animations/mixamo/welcome-wave.vrma', loop: false },
  guiding: { url: '/animations/mixamo/guide-point.vrma', loop: false },
  thinking: { url: '/animations/mixamo/thinking.vrma', loop: true },
  speaking: { url: '/animations/mixamo/speaking.vrma', loop: true },
}

const props = defineProps<{
  assetUrl: string | null
  state: AvatarState
  audioLevel: number
  welcomeRequest: number
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
let animationMixer: THREE.AnimationMixer | undefined
let animationActions: Partial<Record<AnimatedState, THREE.AnimationAction>> = {}
let activeAnimatedState: AnimatedState | undefined
let animationFrame: number | undefined
let resizeObserver: ResizeObserver | undefined
let activeLoadController: AbortController | undefined
let animationLoadController: AbortController | undefined
let welcomeTimer: ReturnType<typeof setTimeout> | undefined
let transientAnimatedState: 'welcome' | undefined
let lastWelcomeRequest = 0
let loadVersion = 0
let previousTime = 0
let blinkUntil = 0
let nextBlinkAt = 0
const headOffsetEuler = new THREE.Euler()
const headOffsetQuaternion = new THREE.Quaternion()

function improveTextureQuality(vrm: VRM) {
  if (!renderer) return
  const anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8)
  vrm.scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    for (const material of materials) {
      for (const value of Object.values(material)) {
        if (!(value instanceof THREE.Texture)) continue
        value.anisotropy = anisotropy
        value.magFilter = THREE.LinearFilter
        value.needsUpdate = true
      }
    }
  })
}

function disposeAnimations() {
  animationLoadController?.abort()
  animationLoadController = undefined
  if (welcomeTimer) clearTimeout(welcomeTimer)
  welcomeTimer = undefined
  transientAnimatedState = undefined
  lastWelcomeRequest = 0
  animationMixer?.stopAllAction()
  if (currentVrm) animationMixer?.uncacheRoot(currentVrm.scene)
  animationMixer = undefined
  animationActions = {}
  activeAnimatedState = undefined
}

function disposeVrm() {
  disposeAnimations()
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
  // A VRoid export starts in a T-pose. This remains the fallback only while
  // animation resources are loading or a device cannot play VRMA files.
  vrm.humanoid?.getNormalizedBoneNode('leftUpperArm')?.rotateZ(-1.2)
  vrm.humanoid?.getNormalizedBoneNode('rightUpperArm')?.rotateZ(1.2)
  headNode = vrm.humanoid?.getNormalizedBoneNode('head') ?? undefined
  headRestQuaternion = headNode?.quaternion.clone()
}

async function loadAnimation(
  vrm: VRM,
  version: number,
  controller: AbortController,
  state: AnimatedState,
) {
  const asset = ANIMATION_ASSETS[state]
  const response = await fetch(asset.url, { signal: controller.signal })
  if (!response.ok) throw new Error(`${state} 动作读取失败（${response.status}）`)
  const buffer = await response.arrayBuffer()
  const loader = new GLTFLoader()
  loader.register((parser) => new VRMAnimationLoaderPlugin(parser))
  const gltf = await new Promise<GLTF>((resolve, reject) => loader.parse(buffer, '', resolve, reject))
  const animations = gltf.userData.vrmAnimations as VRMAnimation[] | undefined
  const animation = animations?.[0]
  if (!animation) throw new Error(`${state} 动作文件中没有可用的 VRMA 动画`)
  if (controller.signal.aborted || version !== loadVersion || currentVrm !== vrm) return

  // three-vrm and three-vrm-animation use nominal private types across
  // separately resolved patch versions, while their runtime API is compatible.
  const clip = createVRMAnimationClip(
    animation,
    vrm as unknown as Parameters<typeof createVRMAnimationClip>[1],
  )
  const action = animationMixer?.clipAction(clip)
  if (!action) return
  action.setLoop(asset.loop ? THREE.LoopRepeat : THREE.LoopOnce, asset.loop ? Infinity : 1)
  action.clampWhenFinished = !asset.loop
  action.enabled = true
  action.paused = true
  action.setEffectiveWeight(0)
  action.play()
  animationActions[state] = action
}

function applyAnimationState(state: AvatarState) {
  const nextState = state === 'listening' ? undefined : state
  if (activeAnimatedState === nextState) return
  const previous = activeAnimatedState ? animationActions[activeAnimatedState] : undefined
  const next = nextState ? animationActions[nextState] : undefined

  if (next) {
    next.reset()
    next.paused = false
    next.enabled = true
    next.setEffectiveWeight(1)
    if (previous && previous !== next) next.crossFadeFrom(previous, 0.2, false)
    next.play()
  } else if (previous) {
    previous.fadeOut(0.16)
  }
  activeAnimatedState = next ? nextState : undefined
}

function activeAnimationState() {
  return transientAnimatedState ?? props.state
}

function playWelcomeWhenReady() {
  if (props.welcomeRequest <= lastWelcomeRequest || !animationActions.welcome) return
  lastWelcomeRequest = props.welcomeRequest
  if (welcomeTimer) clearTimeout(welcomeTimer)
  transientAnimatedState = 'welcome'
  applyAnimationState('welcome')
  welcomeTimer = setTimeout(() => {
    transientAnimatedState = undefined
    welcomeTimer = undefined
    applyAnimationState(props.state)
  }, 1_500)
}

async function loadAnimations(vrm: VRM, version: number) {
  const controller = new AbortController()
  animationLoadController = controller
  animationMixer = new THREE.AnimationMixer(vrm.scene)
  try {
    await Promise.all(
      (Object.keys(ANIMATION_ASSETS) as AnimatedState[]).map(async (state) => {
        try {
          await loadAnimation(vrm, version, controller, state)
        } catch (error) {
          if (!controller.signal.aborted) console.warn(`数字人 ${state} 动作未加载，已使用基础动作`, error)
        }
      }),
    )
    if (!controller.signal.aborted && version === loadVersion && currentVrm === vrm) {
      playWelcomeWhenReady()
      applyAnimationState(activeAnimationState())
    }
  } catch (error) {
    if (!controller.signal.aborted && version === loadVersion) {
      console.warn('数字人动作未加载，已使用基础待机', error)
    }
  } finally {
    if (animationLoadController === controller) animationLoadController = undefined
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
  const distance = Math.max(distanceForHeight, distanceForWidth) * 1.08

  camera.position.set(center.x, targetY, bounds.max.z + distance)
  camera.lookAt(center.x, targetY, center.z)
  camera.updateProjectionMatrix()
}

function rendererSize() {
  if (!renderer || !camera || !mountElement.value) return
  const { width, height } = mountElement.value.getBoundingClientRect()
  if (!width || !height) return
  // Guard against a cyclic percentage-height layout turning the canvas into
  // an enormous WebGL buffer before responsive styles have settled.
  const safeWidth = Math.min(Math.round(width), 4096)
  const safeHeight = Math.min(Math.round(height), 4096)
  renderer.setSize(safeWidth, safeHeight, false)
  camera.aspect = safeWidth / safeHeight
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
    if (!response.ok) throw new Error(`讲解员形象读取失败（${response.status}）`)
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
      throw new Error('该文件未包含可用的 3D 讲解员形象')
    }
    currentVrm = vrm
    // VRM models face +Z by convention; the previous 180° correction made
    // every guide face away from the visitor.
    currentVrm.scene.rotation.y = 0
    currentVrm.scene.position.set(0, 0, 0)
    improveTextureQuality(currentVrm)
    prepareGuidePose(currentVrm)
    scene.add(currentVrm.scene)
    frameAvatar(currentVrm)
    void loadAnimations(currentVrm, version)
  } catch (error) {
    if (controller.signal.aborted || version !== loadVersion) return
    renderFailed.value = true
    emit('error', error instanceof Error ? error.message : '讲解员形象加载失败')
  } finally {
    if (activeLoadController === controller) activeLoadController = undefined
  }
}

function updateAvatar(time: number) {
  if (!renderer || !scene || !camera) return
  const elapsed = time / 1000
  const delta = previousTime ? Math.min((time - previousTime) / 1000, 0.1) : 0
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

    applyAnimationState(activeAnimationState())
    animationMixer?.update(delta)
    const hasNaturalMotion = Boolean(activeAnimatedState && animationActions[activeAnimatedState])
    const motion = props.state === 'listening'
      ? { breath: 0.009, sway: 0.009, bodyTurn: 0.012, headTurn: 0.035, headTilt: 0.018 }
      : { breath: 0.008, sway: 0.013, bodyTurn: 0.02, headTurn: 0.055, headTilt: 0.025 }
    const slowLook = Math.sin(elapsed * 0.43) + Math.sin(elapsed * 0.19) * 0.42
    const breath = Math.sin(elapsed * (isSpeaking ? 3.2 : 2.05)) * motion.breath

    if (hasNaturalMotion) {
      currentVrm.scene.rotation.set(0, 0, 0)
      currentVrm.scene.position.set(0, 0, 0)
    } else {
      currentVrm.scene.rotation.y = slowLook * motion.bodyTurn
      currentVrm.scene.rotation.z = Math.sin(elapsed * 0.86) * motion.sway
      currentVrm.scene.position.y = breath + (isSpeaking ? Math.sin(elapsed * 5.4) * 0.004 : 0)
    }
    if (!hasNaturalMotion && headNode && headRestQuaternion) {
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
    // The stage is intentionally compact on mobile. A minimum 2x backing
    // buffer keeps faces, hair and clothing edges sharp even on 1x displays.
    renderer.setPixelRatio(THREE.MathUtils.clamp(window.devicePixelRatio || 1, 2, 2.5))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.08
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
    emit('error', '当前设备暂不支持 3D 讲解员形象')
  }
})

watch(() => props.assetUrl, () => void loadVrm())
watch(() => props.state, () => applyAnimationState(activeAnimationState()))
watch(() => props.welcomeRequest, () => playWelcomeWhenReady())

onBeforeUnmount(() => {
  loadVersion += 1
  cancelPendingLoad()
  disposeAnimations()
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
  min-height: 0;
  overflow: hidden;
}

.avatar-viewer :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.avatar-viewer :slotted(.guide-avatar-fallback) {
  width: 100%;
  height: 100%;
}
</style>
