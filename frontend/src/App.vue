<template>
  <div class="app-container">
    <header class="app-header">
      <h1>商品价格智能分析助手</h1>
      <p class="subtitle">多平台比价 · 型号对比 · 趋势分析 · 购买建议</p>
    </header>

    <main class="app-main">
      <SearchInput @analyze="startAnalysis" :loading="phase === 'loading' || phase === 'searching'" />

      <ProgressPanel v-if="phase !== 'idle' && phase !== 'result'" :phase="phase" :progress="progress" :current-step="currentStep" :current-action="currentAction" />

      <div v-if="phase === 'result'" class="results">
        <div v-if="isResultEmpty" class="result-empty-card">
          <p class="result-empty-icon">&#128270;</p>
          <h2>未获取到有效数据</h2>
          <p>当前搜索暂时没有找到比价结果，换个关键词试试？</p>
          <p class="result-empty-hint">建议尝试更通用的商品名称（如"平板""手机"），或更换关键词重试</p>
        </div>
        <div v-if="analysisErrors.length > 0" class="result-warnings">
          <p v-for="(e, i) in analysisErrors" :key="i">&#9888; {{ e }}</p>
        </div>
        <template v-if="!isResultEmpty">
          <PriceTable :data="priceTable" />
          <TrendChart :data="trendData" />
          <Recommendation :report="report" :recommendation="recommendation" :price-table="priceTable" :recommend-cards="recommendCards" />
        </template>
      </div>

      <div v-if="phase === 'error'" class="error-state">
        <p>分析出错：{{ error }}</p>
        <button @click="phase = 'idle'">重新搜索</button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import SearchInput from "./components/SearchInput.vue";
import ProgressPanel from "./components/ProgressPanel.vue";
import PriceTable from "./components/PriceTable.vue";
import TrendChart from "./components/TrendChart.vue";
import Recommendation from "./components/Recommendation.vue";
import { useAnalysis } from "./composables/useAnalysis";

const { phase, progress, currentStep, currentAction, priceTable, trendData, report, recommendation, recommendCards, analysisErrors, error, startAnalysis } = useAnalysis();

const isResultEmpty = computed(() => {
  const hasPrice = priceTable.value && Object.keys(priceTable.value).length > 0;
  const hasTrend = trendData.value && (trendData.value.platformComparison || trendData.value.priceHistory);
  const hasReport = !!report.value || !!recommendation.value || (recommendCards.value && recommendCards.value.length > 0);
  return !hasPrice && !hasTrend && !hasReport;
});
</script>

<style scoped>
.result-empty-card {
  background: #fff; border-radius: 12px; padding: 48px 24px;
  text-align: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-left: 4px solid #faad14;
}
.result-empty-card h2 { color: #d48806; margin: 16px 0 8px; }
.result-empty-card p { color: #888; font-size: 14px; }
.result-empty-icon { font-size: 56px; margin: 0 0 8px; }
.result-empty-hint { font-size: 13px; color: #bbb; margin-top: 12px; }

.result-warnings {
  background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px;
  padding: 12px 16px; margin-bottom: 16px;
}
.result-warnings p { font-size: 13px; color: #ad6800; margin: 4px 0; }
</style>
