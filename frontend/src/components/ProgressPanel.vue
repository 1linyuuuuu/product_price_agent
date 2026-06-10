<template>
  <div class="progress-panel">
    <!-- 步骤指示器 -->
    <div class="steps">
      <div class="step" :class="{ active: currentStep >= 1, done: currentStep > 1 }">
        <span class="dot"></span>
        <span>解析商品信息</span>
      </div>
      <div class="step-connector" :class="{ filled: currentStep > 1 }"></div>
      <div class="step" :class="{ active: currentStep >= 2, done: currentStep > 2 }">
        <span class="dot"></span>
        <span>搜索多平台价格</span>
      </div>
      <div class="step-connector" :class="{ filled: currentStep > 2 }"></div>
      <div class="step" :class="{ active: currentStep >= 3 }">
        <span class="dot"></span>
        <span>生成对比报告</span>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="progress-bar-track">
      <div class="progress-bar-fill" :style="{ width: barWidth }"></div>
    </div>
    <p class="current-action">{{ currentAction || '准备中…' }}</p>

    <!-- 详情日志（折叠） -->
    <details v-if="progress.length > 0" class="progress-detail">
      <summary class="detail-toggle">查看详细日志 ({{ progress.length }} 条)</summary>
      <p v-for="(p, i) in progress" :key="i" class="detail-item">{{ p }}</p>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  phase: string;
  progress: string[];
  currentStep: number;
  currentAction: string;
}>();

// 直接用 currentStep 映射目标值，靠 CSS transition 做平滑过渡
const TARGETS = [5, 35, 65, 90];
const barWidth = computed(() => `${TARGETS[props.currentStep] ?? 5}%`);
</script>

<style scoped>
.progress-panel {
  background: #fff;
  border-radius: 12px;
  padding: 28px 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #bbb;
  white-space: nowrap;
}

.step.active { color: #4a90d9; font-weight: 600; }
.step.done { color: #52c41a; }

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ddd;
  flex-shrink: 0;
  transition: background 0.3s;
}
.step.active .dot { background: #4a90d9; box-shadow: 0 0 0 3px rgba(74, 144, 217, 0.2); }
.step.done .dot { background: #52c41a; }

.step-connector {
  width: 40px;
  height: 2px;
  background: #e8e8e8;
  margin: 0 12px;
  transition: background 0.5s;
}
.step-connector.filled { background: #52c41a; }

/* 进度条 */
.progress-bar-track {
  margin-top: 24px;
  height: 6px;
  background: #eee;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4a90d9, #52c41a);
  border-radius: 3px;
  transition: width 1.2s cubic-bezier(0.22, 0.61, 0.36, 1);
  min-width: 3%;
}

.current-action {
  text-align: center;
  color: #4a90d9;
  font-size: 15px;
  margin-top: 14px;
  font-weight: 500;
  min-height: 22px;
}

/* 详情日志 */
.progress-detail {
  margin-top: 16px;
}

.detail-toggle {
  font-size: 13px;
  color: #999;
  cursor: pointer;
  user-select: none;
}

.detail-toggle:hover { color: #4a90d9; }

.detail-item {
  font-size: 12px;
  color: #999;
  margin: 3px 0 3px 12px;
  line-height: 1.6;
}
</style>
