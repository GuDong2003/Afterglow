<script setup lang="ts">
// 消息右下方的水波纹按钮，点开记忆溯源浮窗
import { Waves } from 'lucide-vue-next'
</script>

<template>
  <button
    class="group inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full
           text-accent/70 dark:text-night-accent/70
           hover:text-accent dark:hover:text-night-accent
           hover:bg-accent/5 dark:hover:bg-night-accent/10
           transition-colors no-select"
    aria-label="查看记忆出处"
  >
    <Waves :size="14" class="group-hover:animate-pulse-soft" />
    <span>来自这段记忆</span>
  </button>
</template>
