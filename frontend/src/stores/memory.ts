import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MemorySource, MemoryStats } from '@/types/api'

export const useMemoryStore = defineStore('memory', () => {
  const stats = ref<MemoryStats | null>(null)
  // 缓存随机的"记忆碎片"，侧栏滚动展示
  const fragments = ref<MemorySource[]>([])
  // 当前打开的溯源浮窗（null 表示关闭）
  const openSources = ref<MemorySource[] | null>(null)

  function setStats(s: MemoryStats) {
    stats.value = s
  }

  function setFragments(items: MemorySource[]) {
    fragments.value = items
  }

  function openMemoryModal(sources: MemorySource[]) {
    openSources.value = sources
  }

  function closeMemoryModal() {
    openSources.value = null
  }

  return {
    stats,
    fragments,
    openSources,
    setStats,
    setFragments,
    openMemoryModal,
    closeMemoryModal,
  }
})
