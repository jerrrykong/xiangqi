<template>
  <!--
    音效集成示例 - ChessBoard.vue 接入方式

    在现有 ChessBoard.vue 中的 mounted / onPiecePick / onPieceDrop 等位置
    加入 soundManager.play(...) 调用即可。
  -->
</template>

<script setup lang="ts">
import { getSoundManager } from '@/utils/sound'

const sound = getSoundManager()

// 初始化（在 App.vue 的 onMounted 中调用一次即可）
// await sound.init()

// ========== 示例：棋子交互 ==========

function onPiecePick() {
  // 拿起棋子时
  sound.play('pickup')
}

function onPieceDrop(isCapture: boolean) {
  // 放下棋子时
  sound.play('putdown')

  // 如果是吃子
  if (isCapture) {
    sound.play('capture')
  }
}

function onCheck() {
  // 将军时
  sound.play('check')
  // 同时播放"将军"语音
  sound.play('check_voice')
}

function onGameOver(result: 'win' | 'lose' | 'draw') {
  if (result === 'win')  sound.play('win')
  if (result === 'lose') sound.play('lose')
  if (result === 'draw') sound.play('draw')
}

// ========== 示例：播放棋步语音 ==========
// 方式一：传入棋子字符（适合从 board 直接拿到的棋子符号）
function onMoveMade(pieceChar: string) {
  sound.playMoveVoice(pieceChar)
}

// 方式二：传入棋子英文 ID（适合从 game store 拿到的 piece id）
function onMoveMadeById(pieceId: string) {
  sound.playMoveVoiceById(pieceId)  // 如 "red_chariot"
}

// ========== 示例：按钮点击 ==========
function onClickButton() {
  sound.play('button_click')
}
</script>
