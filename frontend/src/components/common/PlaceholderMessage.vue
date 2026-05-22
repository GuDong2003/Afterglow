<script setup lang="ts">
// 占位符消息（图片 / 语音 / 撤回...）的诗化渲染
import { computed } from 'vue'
import { Image as ImageIcon, Mic, Film, FileText, EyeOff, MessageSquare } from 'lucide-vue-next'

const props = defineProps<{
  kind: string
  isUser: boolean
}>()

const meta = computed(() => {
  switch (props.kind) {
    case '图片':
      return {
        icon: ImageIcon,
        primary: '一张照片',
        secondary: '这张图片已随时间斑驳',
      }
    case '语音':
      return {
        icon: Mic,
        primary: '一段语音',
        secondary: '声音变得有些听不清',
      }
    case '视频':
      return {
        icon: Film,
        primary: '一段视频',
        secondary: '画面在记忆里逐渐模糊',
      }
    case '文件':
      return {
        icon: FileText,
        primary: '一个文件',
        secondary: '已经找不到了',
      }
    case '撤回':
      return {
        icon: EyeOff,
        primary: '撤回了一条消息',
        secondary: '想说又抹去了',
      }
    case '系统消息':
      return {
        icon: MessageSquare,
        primary: '系统消息',
        secondary: '',
      }
    default:
      return {
        icon: MessageSquare,
        primary: `[${props.kind}]`,
        secondary: '',
      }
  }
})
</script>

<template>
  <div
    class="px-4 py-3 rounded-bubble border border-dashed flex items-center gap-3
           text-sm italic select-none"
    :class="
      isUser
        ? 'border-ink/15 dark:border-night-text/15 bg-paper/40 dark:bg-night-bubble-user/40 text-ink-soft dark:text-night-text-soft rounded-tr-md'
        : 'border-ink/10 dark:border-night-text/10 text-ink-soft dark:text-night-text-soft rounded-tl-md'
    "
  >
    <component :is="meta.icon" :size="18" class="opacity-70 shrink-0" />
    <div class="leading-tight">
      <div>{{ meta.primary }}</div>
      <div v-if="meta.secondary" class="text-xs opacity-70 mt-0.5">{{ meta.secondary }}</div>
    </div>
  </div>
</template>
