import { onBeforeUnmount, ref } from 'vue'

/**
 * 自动滚到底部 + 用户上滑时暂停。
 *
 * 调用 attach(el) 把容器接入，调用 schedule() 在新消息到来时尝试滚动。
 */
export function useAutoScroll() {
  const scrollerRef = ref<HTMLElement | null>(null)
  // 用户是否主动向上滚（暂停 auto-scroll）
  const userPaused = ref(false)
  // 距离底部多少像素以内视为"在底部"
  const STICK_THRESHOLD = 64

  let detachListeners: (() => void) | null = null

  function attach(el: HTMLElement) {
    if (detachListeners) detachListeners()
    scrollerRef.value = el
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight
      if (distance > STICK_THRESHOLD) {
        userPaused.value = true
      } else {
        userPaused.value = false
      }
    }
    const onWheelOrTouch = () => {
      // 用户主动操作：进入"由滚动事件决定"的状态
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    el.addEventListener('wheel', onWheelOrTouch, { passive: true })
    el.addEventListener('touchmove', onWheelOrTouch, { passive: true })
    detachListeners = () => {
      el.removeEventListener('scroll', onScroll)
      el.removeEventListener('wheel', onWheelOrTouch)
      el.removeEventListener('touchmove', onWheelOrTouch)
    }
  }

  function schedule(opts: { force?: boolean } = {}) {
    const el = scrollerRef.value
    if (!el) return
    if (userPaused.value && !opts.force) return
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    })
  }

  function jumpToBottom() {
    const el = scrollerRef.value
    if (!el) return
    userPaused.value = false
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
    })
  }

  onBeforeUnmount(() => detachListeners?.())

  return {
    scrollerRef,
    userPaused,
    attach,
    schedule,
    jumpToBottom,
  }
}
