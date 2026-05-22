<script setup lang="ts">
// 整体外壳：背景 + 顶栏 + 主内容
import AmbientCanvas from './AmbientCanvas.vue'
import ChatHeader from '@/components/chat/ChatHeader.vue'
import MemoryModal from '@/components/memory/MemoryModal.vue'
</script>

<template>
  <div class="relative min-h-screen paper-bg text-ink dark:text-night-text flex flex-col">
    <AmbientCanvas />
    <ChatHeader />
    <main class="relative flex-1 overflow-hidden">
      <slot />
    </main>
    <MemoryModal />
  </div>
</template>
