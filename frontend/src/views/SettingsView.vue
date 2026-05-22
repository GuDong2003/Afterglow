<script setup lang="ts">
// 设置面板
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import { useMemoryStore } from '@/stores/memory'
import {
  fetchInfo,
  fetchMemoryStats,
  pauseWriteback,
  resumeWriteback,
} from '@/api/memory'
import type { AppInfo } from '@/types/api'
import { ChevronLeft, Sticker as StickerIcon } from 'lucide-vue-next'
import DiagnosticsPanel from '@/components/common/DiagnosticsPanel.vue'

const settings = useSettingsStore()
const memory = useMemoryStore()
const router = useRouter()
const info = ref<AppInfo | null>(null)
const backendError = ref<string | null>(null)
const busy = ref(false)

onMounted(async () => {
  try {
    info.value = await fetchInfo()
  } catch (e) {
    backendError.value = `无法连接后端：${(e as Error).message}`
  }
  try {
    memory.setStats(await fetchMemoryStats())
  } catch {
    /* ignore */
  }
})

async function togglePause() {
  busy.value = true
  try {
    if (memory.stats?.writeback_paused) await resumeWriteback()
    else await pauseWriteback()
    memory.setStats(await fetchMemoryStats())
  } catch (e) {
    backendError.value = `操作失败：${(e as Error).message}`
  } finally {
    busy.value = false
  }
}

function back() {
  router.push('/')
}
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="max-w-2xl mx-auto px-4 py-6 sm:py-10 space-y-6">
      <header class="flex items-center gap-2">
        <button
          class="p-2 -ml-2 rounded-full text-ink-soft hover:text-ink
                 dark:text-night-text-soft dark:hover:text-night-text"
          @click="back"
        >
          <ChevronLeft :size="20" />
        </button>
        <h1 class="text-xl font-medium">设置</h1>
      </header>

      <!-- 后端连接 -->
      <section class="space-y-3 rounded-2xl p-4 bg-paper-soft dark:bg-night-bg-soft
                      shadow-letter border border-ink/5 dark:border-night-text/10">
        <h2 class="text-base font-medium">后端连接</h2>
        <label class="block">
          <span class="text-sm text-ink-soft dark:text-night-text-soft">后端 API 地址</span>
          <input
            v-model="settings.backendBaseUrl"
            placeholder="留空使用 Vite 代理（dev）；生产填如 http://127.0.0.1:8000"
            class="mt-1 w-full px-3 py-2 rounded-lg bg-paper dark:bg-night-bg
                   border border-ink/10 dark:border-night-text/10 outline-none
                   focus:ring-2 focus:ring-accent-soft"
          />
        </label>
        <label class="block">
          <span class="text-sm text-ink-soft dark:text-night-text-soft">
            本地 API key（后端默认需要 XUWEN_API_KEY）
          </span>
          <input
            v-model="settings.localApiKey"
            type="password"
            class="mt-1 w-full px-3 py-2 rounded-lg bg-paper dark:bg-night-bg
                   border border-ink/10 dark:border-night-text/10 outline-none
                   focus:ring-2 focus:ring-accent-soft"
          />
        </label>
        <p v-if="backendError" class="text-sm text-warning">{{ backendError }}</p>
        <div v-if="info" class="text-xs text-ink-soft dark:text-night-text-soft space-y-1">
          <div>后端版本：{{ info.version }}</div>
          <div>对话模型：{{ info.chat_model }}</div>
          <div>向量模型：{{ info.embedding_model }}</div>
          <div>人格模板：{{ info.persona_template }} · {{ info.relationship_type }}</div>
          <div>persona 卡片：{{ info.has_persona_card ? '已生成' : '尚未生成（运行 analyze_persona.py）' }}</div>
        </div>
      </section>

      <!-- 身份与人格 -->
      <section class="space-y-3 rounded-2xl p-4 bg-paper-soft dark:bg-night-bg-soft
                      shadow-letter border border-ink/5 dark:border-night-text/10">
        <h2 class="text-base font-medium">身份</h2>
        <div class="grid grid-cols-2 gap-3">
          <label class="block">
            <span class="text-sm">你的名字</span>
            <input
              v-model="settings.selfName"
              class="mt-1 w-full px-3 py-2 rounded-lg bg-paper dark:bg-night-bg
                     border border-ink/10 dark:border-night-text/10 outline-none focus:ring-2 focus:ring-accent-soft"
            />
          </label>
          <label class="block">
            <span class="text-sm">ta 的名字</span>
            <input
              v-model="settings.friendName"
              class="mt-1 w-full px-3 py-2 rounded-lg bg-paper dark:bg-night-bg
                     border border-ink/10 dark:border-night-text/10 outline-none focus:ring-2 focus:ring-accent-soft"
            />
          </label>
        </div>
        <label class="block">
          <span class="text-sm">关系</span>
          <input
            v-model="settings.relationshipDescription"
            class="mt-1 w-full px-3 py-2 rounded-lg bg-paper dark:bg-night-bg
                   border border-ink/10 dark:border-night-text/10 outline-none focus:ring-2 focus:ring-accent-soft"
          />
        </label>
        <p class="text-xs text-ink-soft dark:text-night-text-soft">
          这些值仅控制前端文案。要真正切换 persona 模板请改 backend/.env 的 PERSONA_TEMPLATE。
        </p>
      </section>

      <!-- 外观 -->
      <section class="space-y-3 rounded-2xl p-4 bg-paper-soft dark:bg-night-bg-soft
                      shadow-letter border border-ink/5 dark:border-night-text/10">
        <h2 class="text-base font-medium">外观</h2>
        <div class="flex gap-2">
          <button
            v-for="t in (['light','dark','system'] as const)"
            :key="t"
            class="flex-1 py-2 rounded-lg border text-sm transition-colors"
            :class="
              settings.theme === t
                ? 'border-accent bg-accent/10 text-accent dark:border-night-accent dark:text-night-accent dark:bg-night-accent/10'
                : 'border-ink/10 dark:border-night-text/10 text-ink-soft dark:text-night-text-soft hover:text-ink dark:hover:text-night-text'
            "
            @click="settings.theme = t"
          >
            {{ t === 'light' ? '明色' : t === 'dark' ? '暗色' : '跟随系统' }}
          </button>
        </div>
        <label class="block">
          <span class="text-sm">字号缩放：{{ Math.round(settings.fontScale * 100) }}%</span>
          <input
            v-model.number="settings.fontScale"
            type="range"
            min="0.9"
            max="1.3"
            step="0.05"
            class="mt-1 w-full"
          />
        </label>
      </section>

      <!-- 记忆 -->
      <section v-if="memory.stats" class="space-y-3 rounded-2xl p-4 bg-paper-soft dark:bg-night-bg-soft
                                          shadow-letter border border-ink/5 dark:border-night-text/10">
        <h2 class="text-base font-medium">记忆</h2>
        <div class="grid grid-cols-3 gap-3 text-center">
          <div>
            <div class="text-2xl font-medium">{{ memory.stats.friend_messages }}</div>
            <div class="text-xs text-ink-soft dark:text-night-text-soft">朋友的话</div>
          </div>
          <div>
            <div class="text-2xl font-medium">{{ memory.stats.dialogue_windows }}</div>
            <div class="text-xs text-ink-soft dark:text-night-text-soft">对话片段</div>
          </div>
          <div>
            <div class="text-2xl font-medium">{{ memory.stats.live_messages }}</div>
            <div class="text-xs text-ink-soft dark:text-night-text-soft">新对话回写</div>
          </div>
        </div>
        <button
          :disabled="busy"
          class="w-full py-2 rounded-lg border border-ink/10 dark:border-night-text/10 text-sm
                 hover:bg-paper dark:hover:bg-night-bg disabled:opacity-50"
          @click="togglePause"
        >
          {{ memory.stats.writeback_paused ? '恢复回写' : '暂停回写（不再把新对话写入记忆）' }}
        </button>
      </section>
      <!-- 表情包入口 -->
      <section
        class="rounded-2xl p-4 bg-paper-soft dark:bg-night-bg-soft shadow-letter
               border border-ink/5 dark:border-night-text/10"
      >
        <button
          class="w-full flex items-center justify-between"
          @click="router.push('/stickers')"
        >
          <span class="flex items-center gap-2">
            <StickerIcon :size="18" />
            <span class="font-medium">表情包管理</span>
          </span>
          <span class="text-xs text-ink-soft dark:text-night-text-soft">→</span>
        </button>
      </section>

      <!-- 诊断 -->
      <DiagnosticsPanel />
    </div>
  </div>
</template>
