/**
 * 把 SSE 一次性塞进来的文字，按真人打字节奏逐字渲染。
 *
 * - 字符队列异步消费
 * - 普通字符：20-60ms 基础延迟
 * - 中英标点：额外停顿 120-220ms
 * - 句末（。！？）：停顿 280-420ms
 * - 当上游已经 finish 而队列还在排时，会自动加速以避免用户长时间等待
 */
import { onScopeDispose } from 'vue'

const PUNCT_LIGHT = new Set(['，', ',', '、', ';', '；', ':', '：'])
const PUNCT_HEAVY = new Set(['。', '！', '？', '.', '!', '?', '\n'])

export interface TypewriterOptions {
  baseMin?: number
  baseMax?: number
  /** 当 finish() 被调用后，剩余队列的总最大耗时（ms）。超过则一次性 flush */
  flushBudgetMs?: number
}

export function useTypewriter(
  onEmit: (text: string) => void,
  options: TypewriterOptions = {},
) {
  const baseMin = options.baseMin ?? 22
  const baseMax = options.baseMax ?? 60
  const flushBudgetMs = options.flushBudgetMs ?? 1200

  const queue: string[] = []
  let running = false
  let finished = false

  function pushText(text: string): void {
    if (!text) return
    // 拆分到字符级别（包含 emoji 用 Array.from）
    for (const ch of Array.from(text)) queue.push(ch)
    if (!running) {
      running = true
      void loop()
    }
  }

  function finish(): void {
    finished = true
  }

  function reset(): void {
    queue.length = 0
    running = false
    finished = false
  }

  function delayFor(ch: string): number {
    if (PUNCT_HEAVY.has(ch)) return 280 + Math.random() * 140
    if (PUNCT_LIGHT.has(ch)) return 120 + Math.random() * 100
    return baseMin + Math.random() * (baseMax - baseMin)
  }

  async function loop(): Promise<void> {
    while (queue.length > 0) {
      // 如果 finish 已被触发，且 budget 已满，则一次性 flush 剩余
      if (finished && queue.length * baseMax > flushBudgetMs) {
        const rest = queue.splice(0, queue.length).join('')
        onEmit(rest)
        break
      }
      const ch = queue.shift()!
      onEmit(ch)
      const ms = delayFor(ch)
      await new Promise((r) => setTimeout(r, ms))
    }
    running = false
  }

  onScopeDispose(() => {
    reset()
  })

  return { pushText, finish, reset }
}
