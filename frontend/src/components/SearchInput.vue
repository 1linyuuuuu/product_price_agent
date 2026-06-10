<template>
  <div class="search-input-card">
    <div class="input-wrapper">
      <input
        v-model="query"
        type="text"
        placeholder="输入你想对比的商品..."
        :disabled="loading"
        @keyup.enter="handleSubmit"
        @input="errorMsg = ''"
      />
      <button :disabled="loading || !query.trim()" @click="handleSubmit">
        {{ loading ? "分析中..." : "开始分析" }}
      </button>
    </div>
    <p class="hint" v-if="!errorMsg">例：华为Mate 70 Pro 256G vs 512G / RTX 4080 显卡多少钱 / 戴森V15 全新还是二手划算</p>
    <p class="error-msg" v-else>{{ errorMsg }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

defineProps<{ loading: boolean }>();
const emit = defineEmits<{ analyze: [query: string] }>();

const query = ref("");
const errorMsg = ref("");

function handleSubmit() {
  const q = query.value.trim();
  if (!q) return;
  if (q.length < 2) {
    errorMsg.value = "请输入至少 2 个字符";
    return;
  }
  if (q.length > 200) {
    errorMsg.value = "输入内容过长，请精简到 200 字以内";
    return;
  }
  emit("analyze", q);
}
</script>

<style scoped>
.error-msg { color: #cf1322; font-size: 13px; margin-top: 8px; }
</style>
