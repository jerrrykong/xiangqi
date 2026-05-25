/**
 * 中国象棋音效管理器
 * 用法:
 *   import { SoundManager } from '@/utils/sound'
 *   const sound = new SoundManager()
 *   await sound.init()          // 预加载所有音效
 *   sound.play('pickup')       // 播放拿起棋子音效
 *   sound.playVoice('chariot') // 播放"出车"语音
 */

type SoundCategory = 'sfx' | 'voice'

interface SoundConfig {
  [key: string]: {
    file: string
    category: SoundCategory
    volume?: number   // 0-1，默认 1.0
  }
}

const SOUND_BASE = '/sounds'

const SOUND_MAP: SoundConfig = {
  // === 音效 ===
  pickup:        { file: 'pickup.wav',        category: 'sfx', volume: 0.6 },
  putdown:       { file: 'putdown.wav',       category: 'sfx', volume: 0.6 },
  capture:       { file: 'capture.wav',        category: 'sfx', volume: 0.8 },
  check:         { file: 'check.wav',          category: 'sfx', volume: 0.7 },
  win:           { file: 'win.wav',            category: 'sfx', volume: 0.8 },
  lose:          { file: 'lose.wav',           category: 'sfx', volume: 0.8 },
  draw:          { file: 'draw.wav',           category: 'sfx', volume: 0.6 },
  button_click:  { file: 'button_click.wav',   category: 'sfx', volume: 0.4 },

  // === 棋步语音 ===
  chariot:    { file: 'voice_move_chariot.wav',  category: 'voice', volume: 0.9 },  // 出车
  pawn:       { file: 'voice_move_pawn.wav',     category: 'voice', volume: 0.9 },  // 拱卒
  horse:      { file: 'voice_move_horse.wav',    category: 'voice', volume: 0.9 },  // 跳马
  advisor:    { file: 'voice_move_advisor.wav',  category: 'voice', volume: 0.9 },  // 上士
  elephant:   { file: 'voice_move_elephant.wav', category: 'voice', volume: 0.9 },  // 飞象
  cannon:     { file: 'voice_move_cannon.wav',   category: 'voice', volume: 0.9 },  // 当头炮
  check_voice:{ file: 'voice_check.wav',          category: 'voice', volume: 0.9 },  // 将军

  // === 落子/平炮语音 ===
  drop_advisor:  { file: 'voice_luo_advisor.wav',  category: 'voice', volume: 0.9 },  // 落士
  drop_elephant: { file: 'voice_luo_elephant.wav', category: 'voice', volume: 0.9 },  // 落象
  level_cannon:  { file: 'voice_ping_cannon.wav',  category: 'voice', volume: 0.9 },  // 平炮

  // === 吃子语音 ===
  eat_advisor:  { file: 'voice_eat_advisor.wav',  category: 'voice', volume: 0.9 },  // 吃士
  eat_elephant: { file: 'voice_eat_elephant.wav', category: 'voice', volume: 0.9 },  // 吃象
  eat_cannon:   { file: 'voice_eat_cannon.wav',   category: 'voice', volume: 0.9 },  // 吃炮
  eat_pawn:     { file: 'voice_eat_pawn.wav',     category: 'voice', volume: 0.9 },  // 吃卒
  eat_chariot:  { file: 'voice_eat_chariot.wav',  category: 'voice', volume: 0.9 },  // 吃车
  eat_horse:    { file: 'voice_eat_horse.wav',    category: 'voice', volume: 0.9 },  // 吃马

  // === 游戏语音 ===
  start:      { file: 'voice_start.wav',      category: 'voice', volume: 0.9 },  // 请开始游戏
  your_turn:  { file: 'voice_your_turn.wav',  category: 'voice', volume: 0.9 },  // 轮到你走棋
  red_win:    { file: 'voice_red_win.wav',     category: 'voice', volume: 0.9 },  // 红方胜
  black_win:  { file: 'voice_black_win.wav',   category: 'voice', volume: 0.9 },  // 黑方胜
  draw_voice: { file: 'voice_draw.wav',        category: 'voice', volume: 0.9 },  // 和棋
}

export type SoundKey = keyof typeof SOUND_MAP

type SoundCacheKey = SoundKey

export class SoundManager {
  private audioCache: Map<SoundCacheKey, HTMLAudioElement> = new Map()
  private enabled: boolean = true
  private sfxVolume: number = 0.7
  private voiceVolume: number = 0.8
  private voiceEnabled: boolean = true
  private initialized: boolean = false

  /** 预加载所有音效（建议在 App 启动时调用）*/
  async init(): Promise<void> {
    if (this.initialized) return
    const promises = Object.entries(SOUND_MAP).map(([key, cfg]) =>
      this.preload(key as SoundKey, cfg.file)
    )
    await Promise.allSettled(promises)
    this.initialized = true
    console.log('[SoundManager] All sounds preloaded')
  }

  private preload(key: SoundKey, file: string): Promise<void> {
    return new Promise((resolve) => {
      const audio = new Audio(`${SOUND_BASE}/${file}`)
      audio.preload = 'auto'
      audio.addEventListener('canplaythrough', () => resolve(), { once: true })
      audio.addEventListener('error', () => {
        console.warn(`[SoundManager] Failed to preload: ${file}`)
        resolve()
      }, { once: true })
      audio.load()
      this.audioCache.set(key as SoundCacheKey, audio)
    })
  }

  /** 播放音效 */
  play(key: SoundKey): void {
    if (!this.enabled) return
    const cfg = SOUND_MAP[key]
    if (!cfg) {
      console.warn(`[SoundManager] Unknown sound: ${key}`)
      return
    }

    // 语音类型且语音被禁用，跳过
    if (cfg.category === 'voice' && !this.voiceEnabled) return

    // 克隆节点播放（支持重叠播放）
    const base = this.audioCache.get(key)
    let audio: HTMLAudioElement
    if (base) {
      audio = base.cloneNode() as HTMLAudioElement
    } else {
      audio = new Audio(`${SOUND_BASE}/${cfg.file}`)
    }

    const vol = cfg.category === 'voice' ? this.voiceVolume : this.sfxVolume
    audio.volume = Math.min(1, Math.max(0, (cfg.volume ?? 1) * vol))
    audio.play().catch(() => {
      // 浏览器策略限制时静默失败
    })
  }

  /** 播放棋步语音（根据棋子类型）*/
  playMoveVoice(pieceType: string): void {
    const voiceMap: Record<string, SoundKey> = {
      '车': 'chariot',
      '俥': 'chariot',
      '马': 'horse',
      '傌': 'horse',
      '象': 'elephant',
      '相': 'elephant',
      '士': 'advisor',
      '仕': 'advisor',
      '将': 'check_voice',
      '帅': 'check_voice',
      '炮': 'cannon',
      '砲': 'cannon',
      '兵': 'pawn',
      '卒': 'pawn',
    }
    const key = voiceMap[pieceType]
    if (key) this.play(key)
  }

  /** 根据棋子英文 ID 播放语音 */
  playMoveVoiceById(pieceId: string): void {
    // pieceId 格式如 "red_chariot", "black_horse"
    const idMap: Record<string, SoundKey> = {
      'chariot': 'chariot',
      'horse':   'horse',
      'elephant':'elephant',
      'advisor': 'advisor',
      'general': 'check_voice',
      'cannon':  'cannon',
      'pawn':    'pawn',
    }
    const key = idMap[pieceId.split('_')[1]]
    if (key) this.play(key)
  }

  /** 播放移动语音（更智能的版本，根据走子方向选择语音）*/
  playMoveVoiceSmart(pieceChar: string, isCapture: boolean, isRetreat: boolean): void {
    const eatMap: Record<string, SoundKey> = {
      '车': 'eat_chariot', '俥': 'eat_chariot',
      '马': 'eat_horse',   '傌': 'eat_horse',
      '象': 'eat_elephant','相': 'eat_elephant',
      '士': 'eat_advisor', '仕': 'eat_advisor',
      '炮': 'eat_cannon',  '砲': 'eat_cannon',
      '兵': 'eat_pawn',    '卒': 'eat_pawn',
    }

    if (isCapture) {
      const capKey = eatMap[pieceChar]
      if (capKey) { this.play(capKey); return }
    }

    // 后退走法（落士、落象）
    if (isRetreat) {
      const dropMap: Record<string, SoundKey> = {
        '士': 'drop_advisor', '仕': 'drop_advisor',
        '象': 'drop_elephant','相': 'drop_elephant',
      }
      const key = dropMap[pieceChar]
      if (key) { this.play(key); return }
    }

    // 默认走法
    this.playMoveVoice(pieceChar)
  }

  /** 播放吃子语音（根据被吃棋子类型）*/
  playCaptureVoice(capturedPieceChar: string): void {
    const eatMap: Record<string, SoundKey> = {
      '车': 'eat_chariot', '俥': 'eat_chariot',
      '马': 'eat_horse',   '傌': 'eat_horse',
      '象': 'eat_elephant','相': 'eat_elephant',
      '士': 'eat_advisor', '仕': 'eat_advisor',
      '炮': 'eat_cannon',  '砲': 'eat_cannon',
      '兵': 'eat_pawn',    '卒': 'eat_pawn',
      '将': 'check_voice', '帅': 'check_voice',
    }
    const key = eatMap[capturedPieceChar]
    if (key) this.play(key)
  }

  // --- 设置 ---
  setEnabled(v: boolean): void { this.enabled = v }
  setSfxVolume(v: number): void { this.sfxVolume = v }
  setVoiceEnabled(v: boolean): void { this.voiceEnabled = v }
  setVoiceVolume(v: number): void { this.voiceVolume = v }

  get isEnabled(): boolean { return this.enabled }
  get isVoiceEnabled(): boolean { return this.voiceEnabled }
}

// 全局单例
let globalSoundManager: SoundManager | null = null

export function getSoundManager(): SoundManager {
  if (!globalSoundManager) {
    globalSoundManager = new SoundManager()
  }
  return globalSoundManager
}
