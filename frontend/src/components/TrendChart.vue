<template>
  <div class="trend-chart-card" v-if="data">
    <h2>价格趋势</h2>

    <div v-if="data.platformComparison" class="chart-section">
      <h3 class="chart-label">各平台价格对比</h3>
      <div ref="barChartRef" class="chart-container"></div>
    </div>

    <div v-if="showPriceHistory" class="chart-section">
      <h3 class="chart-label">历史价格走势</h3>
      <div ref="lineChartRef" class="chart-container"></div>
    </div>

    <div v-else-if="data.platformComparison && !showPriceHistory" class="history-too-few">
      暂未收录该商品的历史价格走势，先看看各平台当前报价吧
    </div>

    <div v-if="!data.platformComparison && !data.priceHistory" class="chart-empty">
      暂时还没有趋势数据，多搜几次就能看到价格变化啦
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick, computed } from "vue";
import * as echarts from "echarts";

const props = defineProps<{ data: any }>();

const barChartRef = ref<HTMLElement | null>(null);
const lineChartRef = ref<HTMLElement | null>(null);

let barChart: echarts.ECharts | null = null;
let lineChart: echarts.ECharts | null = null;

// 历史数据点过少时隐藏折线图（点太少/跨度太短都没意义）
const showPriceHistory = computed(() => {
  const ph = props.data?.priceHistory;
  if (!ph) return false;
  const series = ph.series || [];
  const dates: string[] = ph.xAxis?.data || [];
  if (dates.length < 3) return false;
  // 日期跨度不足一个月也不显示
  if (dates.length >= 2) {
    const first = new Date(dates[0]);
    const last = new Date(dates[dates.length - 1]);
    if ((last.getTime() - first.getTime()) < 30 * 24 * 3600 * 1000) return false;
  }
  // 所有 series 的非 null 数据点累计 < 4
  let totalPoints = 0;
  for (const s of series) {
    totalPoints += (s.data || []).filter((v: any) => v != null).length;
  }
  return totalPoints >= 4;
});

function renderCharts() {
  if (!props.data) return;

  // Y 轴短格式：12899 → "12.9k"
  function shortPrice(v: number): string {
    if (v >= 10000) return (v / 10000).toFixed(1) + "万";
    if (v >= 1000) return (v / 1000).toFixed(1) + "k";
    return String(v);
  }

  if (props.data.platformComparison && barChartRef.value) {
    if (!barChart) {
      barChart = echarts.init(barChartRef.value);
    }
    const { title, ...rest } = props.data.platformComparison;
    const xData = rest.xAxis?.data || [];
    barChart.setOption({
      ...rest,
      grid: { top: 10, bottom: xData.length > 4 ? 70 : 30, left: 70, right: 20 },
      xAxis: {
        ...rest.xAxis,
        axisLabel: {
          rotate: xData.length > 4 ? 30 : 0,
          fontSize: 12,
        },
      },
      yAxis: {
        ...rest.yAxis,
        nameTextStyle: { fontSize: 11 },
        nameGap: 12,
        axisLabel: { fontSize: 11, formatter: shortPrice },
      },
    }, true);
  }

  if (props.data.priceHistory && lineChartRef.value) {
    if (!lineChart) {
      lineChart = echarts.init(lineChartRef.value);
    }
    const { title, ...rest } = props.data.priceHistory;
    const xData = rest.xAxis?.data || [];
    lineChart.setOption({
      ...rest,
      grid: { top: 10, bottom: xData.length > 8 ? 70 : 30, left: 70, right: 20 },
      xAxis: {
        ...rest.xAxis,
        axisLabel: {
          rotate: xData.length > 8 ? 30 : 0,
          fontSize: 12,
        },
      },
      yAxis: {
        ...rest.yAxis,
        nameTextStyle: { fontSize: 11 },
        nameGap: 12,
        axisLabel: { fontSize: 11, formatter: shortPrice },
      },
    }, true);
  }
}

function handleResize() {
  barChart?.resize();
  lineChart?.resize();
}

onMounted(async () => {
  await nextTick();
  renderCharts();
  window.addEventListener("resize", handleResize);
});

watch(() => props.data, async () => {
  await nextTick();
  renderCharts();
}, { deep: true });

// v-if 隐藏折线图时销毁实例，避免下次显示时引用已 disposed 的旧实例
watch(showPriceHistory, (visible) => {
  if (!visible) {
    lineChart?.dispose();
    lineChart = null;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  barChart?.dispose();
  lineChart?.dispose();
});
</script>

<style scoped>
.trend-chart-card {
  background: #fff; border-radius: 12px; padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); border-left: 4px solid #7c5ce7;
  margin-bottom: 20px;
}
.trend-chart-card h2 { margin-bottom: 16px; color: #5b3eb0; }

.chart-label {
  font-size: 15px; color: #555; margin: 8px 0 4px;
}

.chart-container { width: 100%; height: 320px; }

.chart-empty {
  text-align: center; color: #999; padding: 24px; font-size: 14px;
}

.history-too-few {
  text-align: center; color: #aaa; padding: 16px 8px; font-size: 13px;
  background: #fafafa; border-radius: 8px; margin-top: 8px;
}
</style>
