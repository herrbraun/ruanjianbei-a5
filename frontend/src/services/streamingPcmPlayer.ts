export type FirstAudioMetrics = {
  firstChunkMs: number
  provider: 'volcengine' | 'dashscope' | null
}

type PlayerCallbacks = {
  onFirstAudio?: (metrics: FirstAudioMetrics) => void
  onLevel?: (level: number) => void
  onEnded?: () => void
}

const SAMPLE_RATE = 24_000

export class StreamingPcmPlayer {
  private context?: AudioContext
  private analyser?: AnalyserNode
  private animationFrame?: number
  private abortController?: AbortController
  private sources = new Set<AudioBufferSourceNode>()
  private nextStartTime = 0
  private playing = false
  private paused = false

  constructor(private readonly callbacks: PlayerCallbacks = {}) {}

  get isPaused() {
    return this.paused
  }

  async prepare() {
    const AudioContextConstructor = window.AudioContext || (window as Window & {
      webkitAudioContext?: typeof AudioContext
    }).webkitAudioContext
    if (!AudioContextConstructor) throw new Error('当前浏览器不支持实时语音播放')
    if (!this.context) {
      try {
        this.context = new AudioContextConstructor({ sampleRate: SAMPLE_RATE })
      } catch {
        this.context = new AudioContextConstructor()
      }
    }
    this.analyser ||= this.context.createAnalyser()
    this.analyser.fftSize = 512
    this.analyser.connect(this.context.destination)
    if (this.context.state === 'suspended') await this.context.resume()
    this.paused = false
  }

  async play(url: string, token: string, recoverToken: () => Promise<string>, body?: unknown) {
    await this.prepare()
    this.stopSources()
    this.abortController = new AbortController()
    const requestStartedAt = performance.now()
    let response = await this.request(url, token, body)
    if (response.status === 401) response = await this.request(url, await recoverToken(), body)
    if (!response.ok) {
      const payload = await response.json().catch(() => null) as { detail?: string } | null
      throw new Error(payload?.detail || `语音合成失败（HTTP ${response.status}）`)
    }
    if (!response.body) throw new Error('浏览器无法读取实时语音流')
    const responseProvider = response.headers.get('X-TTS-Provider')
    const provider = responseProvider === 'volcengine' || responseProvider === 'dashscope'
      ? responseProvider
      : null
    this.nextStartTime = this.context!.currentTime + 0.04
    this.playing = true
    this.startLevelSampling()

    const reader = response.body.getReader()
    let carry: number | undefined
    let firstAudio = true
    while (this.playing) {
      const { done, value } = await reader.read()
      if (done) break
      if (!value?.length) continue
      let bytes = value
      if (carry !== undefined) {
        const joined = new Uint8Array(value.length + 1)
        joined[0] = carry
        joined.set(value, 1)
        bytes = joined
        carry = undefined
      }
      if (bytes.length % 2) {
        carry = bytes[bytes.length - 1]
        bytes = bytes.subarray(0, bytes.length - 1)
      }
      if (!bytes.length) continue
      while (this.playing && (this.paused || this.nextStartTime - this.context!.currentTime > 8)) {
        await new Promise((resolve) => window.setTimeout(resolve, 50))
      }
      if (!this.playing) return
      this.schedule(bytes)
      if (firstAudio) {
        firstAudio = false
        this.callbacks.onFirstAudio?.({
          firstChunkMs: Math.round(performance.now() - requestStartedAt),
          provider,
        })
      }
    }
    if (!this.playing) return
    while (this.playing && (this.paused || this.context!.currentTime < this.nextStartTime)) {
      await new Promise((resolve) => window.setTimeout(resolve, 50))
    }
    if (this.playing) {
      this.playing = false
      this.stopLevelSampling()
      this.callbacks.onEnded?.()
    }
  }

  async pause() {
    if (!this.context || !this.playing || this.paused) return
    await this.context.suspend()
    this.paused = true
    this.stopLevelSampling()
  }

  async resume() {
    if (!this.context || !this.playing || !this.paused) return
    await this.context.resume()
    this.paused = false
    this.startLevelSampling()
  }

  stop() {
    this.playing = false
    this.paused = false
    this.abortController?.abort()
    this.abortController = undefined
    this.stopSources()
    this.stopLevelSampling()
  }

  async destroy() {
    this.stop()
    await this.context?.close()
    this.context = undefined
    this.analyser = undefined
  }

  private request(url: string, token: string, body?: unknown) {
    return fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: this.abortController?.signal,
      cache: 'no-store',
    })
  }

  private schedule(bytes: Uint8Array) {
    const samples = new Float32Array(bytes.length / 2)
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    for (let index = 0; index < samples.length; index += 1) {
      samples[index] = view.getInt16(index * 2, true) / 32768
    }
    const buffer = this.context!.createBuffer(1, samples.length, SAMPLE_RATE)
    buffer.copyToChannel(samples, 0)
    const source = this.context!.createBufferSource()
    source.buffer = buffer
    source.connect(this.analyser!)
    const startAt = Math.max(this.nextStartTime, this.context!.currentTime + 0.025)
    source.start(startAt)
    this.nextStartTime = startAt + buffer.duration
    this.sources.add(source)
    source.onended = () => this.sources.delete(source)
  }

  private startLevelSampling() {
    this.stopLevelSampling()
    if (!this.analyser) return
    const samples = new Uint8Array(this.analyser.fftSize)
    const sample = () => {
      if (!this.analyser || !this.playing || this.paused) return
      this.analyser.getByteTimeDomainData(samples)
      let energy = 0
      for (const value of samples) {
        const normalized = (value - 128) / 128
        energy += normalized * normalized
      }
      this.callbacks.onLevel?.(Math.min(1, Math.sqrt(energy / samples.length) * 6))
      this.animationFrame = requestAnimationFrame(sample)
    }
    sample()
  }

  private stopSources() {
    for (const source of this.sources) {
      try { source.stop() } catch { /* already stopped */ }
      source.disconnect()
    }
    this.sources.clear()
  }

  private stopLevelSampling() {
    if (this.animationFrame) cancelAnimationFrame(this.animationFrame)
    this.animationFrame = undefined
    this.callbacks.onLevel?.(0)
  }
}
