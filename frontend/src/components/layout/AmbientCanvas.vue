<script setup lang="ts">
// 信笺背景：用 Canvas 画几粒缓慢漂浮的暖光粒子。
// - 自动适配设备像素比
// - 暗色模式下颜色更冷更暗
// - 用户切到非 / 浏览器后台时自动停止动画

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)
let raf = 0
let particles: Particle[] = []
let ctx: CanvasRenderingContext2D | null = null
let dpr = 1

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  alpha: number
}

const palette = computed(() => {
  if (settings.isDark) {
    return { color: 'rgba(217, 181, 138, ', baseAlpha: 0.35 }
  }
  return { color: 'rgba(139, 90, 43, ', baseAlpha: 0.18 }
})

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  const w = window.innerWidth
  const h = window.innerHeight
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = `${w}px`
  canvas.style.height = `${h}px`
  ctx = canvas.getContext('2d')
  ctx?.scale(dpr, dpr)
}

function spawnParticles() {
  const canvas = canvasRef.value
  if (!canvas) return
  const count = Math.min(
    24,
    Math.max(10, Math.floor((canvas.width / dpr) * (canvas.height / dpr) / 60000)),
  )
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * (canvas.width / dpr),
    y: Math.random() * (canvas.height / dpr),
    vx: (Math.random() - 0.5) * 0.08,
    vy: -0.05 - Math.random() * 0.1,
    r: 30 + Math.random() * 60,
    alpha: 0.2 + Math.random() * 0.8,
  }))
}

function tick() {
  if (!ctx) return
  const canvas = canvasRef.value!
  const W = canvas.width / dpr
  const H = canvas.height / dpr
  ctx.clearRect(0, 0, W, H)

  const { color, baseAlpha } = palette.value

  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    // 漂出顶部就从底部重新进
    if (p.y + p.r < 0) {
      p.y = H + p.r
      p.x = Math.random() * W
    }
    if (p.x < -p.r) p.x = W + p.r
    if (p.x > W + p.r) p.x = -p.r

    const a = baseAlpha * p.alpha
    const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r)
    grad.addColorStop(0, color + a + ')')
    grad.addColorStop(1, color + '0)')
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fill()
  }
  raf = requestAnimationFrame(tick)
}

function start() {
  cancelAnimationFrame(raf)
  resize()
  spawnParticles()
  raf = requestAnimationFrame(tick)
}

function stop() {
  cancelAnimationFrame(raf)
  raf = 0
}

function onVisibility() {
  if (document.hidden) stop()
  else start()
}

onMounted(() => {
  start()
  window.addEventListener('resize', start)
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  stop()
  window.removeEventListener('resize', start)
  document.removeEventListener('visibilitychange', onVisibility)
})

watch(() => settings.isDark, () => {
  // 重启以应用新颜色
  start()
})
</script>

<template>
  <canvas
    ref="canvasRef"
    aria-hidden="true"
    class="pointer-events-none fixed inset-0 -z-10"
  />
</template>
