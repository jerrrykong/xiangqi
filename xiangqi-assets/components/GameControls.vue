<!--
  GameControls.vue — 对局操作按钮组
  与 Demo 中 game-actions-inline 一致
-->
<template>
  <div class="game-actions-inline">
    <button class="btn btn-secondary" @click="$emit('draw')">求和</button>
    <button class="btn btn-secondary" @click="$emit('resign')">认输</button>
    <button class="btn btn-secondary" @click="$emit('undo')">悔棋</button>
    <button class="btn btn-text" @click="$emit('exit')">退出</button>
  </div>
</template>

<script setup>
defineEmits(['draw', 'resign', 'undo', 'exit'])
</script>
