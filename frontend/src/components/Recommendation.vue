<template>
  <!-- 比价分析报告 -->
  <div class="report-card" v-if="report">
    <h2>比价分析报告</h2>
    <div class="report" v-html="renderedReport"></div>
  </div>

  <!-- 购买建议 -->
  <div class="buy-advice-card" v-if="hasContent">
    <h2>购买建议</h2>

    <!-- 总结/风险提示文字 -->
    <div v-if="summaryText" class="recommendation-content" v-html="renderedSummary"></div>

    <!-- 理由 + 卡片 交错 -->
    <div class="cards-sequence">
      <div v-for="(card, idx) in cards" :key="idx" class="card-block">
        <div v-if="card.text" class="card-reason" v-html="renderedCardText(card.text)"></div>
        <ProductCard :card="card" />
      </div>
    </div>
  </div>

  <div class="buy-advice-card empty-state" v-else-if="!report">
    <h2>购买建议</h2>
    <div class="empty-content">
      <p class="empty-icon">&#128161;</p>
      <p>还没有购买建议</p>
      <p class="empty-hint">输入具体的商品型号，可以帮你找到更精准的推荐哦</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { marked } from "marked";
import ProductCard from "./ProductCard.vue";

const props = defineProps<{
  report: string;
  recommendation: string;
  priceTable?: Record<string, any[]>;
  recommendCards?: any[];
}>();

interface Card {
  variant: string;
  platform: string;
  shop_name?: string;
  price: number;
  is_used?: boolean;
  image?: string;
  buy_url?: string;
  reason: string;
  text?: string;
  type?: string;
}

function normalizeCard(c: any): Card {
  return {
    variant: c.variant || "",
    platform: c.platform || "",
    shop_name: c.shop_name || "",
    price: c.price || 0,
    is_used: c.is_used !== undefined ? c.is_used : (c.isUsed || false),
    image: c.image || "",
    buy_url: c.buy_url || c.buyUrl || "",
    reason: c.reason || "",
    text: c.text || "",
    type: c.type || "",
  };
}

const llmCards = computed<Card[]>(() =>
  (props.recommendCards || []).map(normalizeCard).filter(c => c.variant && c.price > 0)
);

// 优先 LLM 卡片，否则自动生成
const allCards = computed<Card[]>(() => {
  if (llmCards.value.length > 0) return llmCards.value;

  // fallback：从 priceTable 自动生成
  const result: Card[] = [];
  const pt = props.priceTable || {};

  for (const [variant, prices] of Object.entries(pt)) {
    if (!Array.isArray(prices) || !prices.length) continue;
    const valid = prices.filter((p: any) => p.price > 0);
    if (!valid.length) continue;

    const bestNew = valid.filter((p: any) => !p.is_secondhand).sort((a: any, b: any) => a.price - b.price)[0];
    const bestUsed = valid.filter((p: any) => p.is_secondhand).sort((a: any, b: any) => a.price - b.price)[0];

    if (bestNew) {
      result.push({
        variant, platform: bestNew.platform || "", price: Math.round(bestNew.price),
        is_used: false, shop_name: bestNew.shop_name || "",
        buy_url: bestNew.source_url || buildSearchUrl(bestNew.platform || "", variant),
        reason: bestNew.is_official ? "官方渠道" : (bestNew.promotion || "全新好价"),
      });
    }
    if (bestUsed) {
      result.push({
        variant, platform: bestUsed.platform || "", price: Math.round(bestUsed.price),
        is_used: true, shop_name: bestUsed.shop_name || "",
        buy_url: bestUsed.source_url || buildSearchUrl(bestUsed.platform || "", variant),
        reason: bestUsed.condition ? `${bestUsed.condition}成色` : "二手性价比之选",
      });
    }
  }
  return result.slice(0, 4);
});

const cards = computed<Card[]>(() => {
  const primary = allCards.value.filter(c => c.type !== "alternative");
  const alt = allCards.value.filter(c => c.type === "alternative");
  return [...primary, ...alt].slice(0, 4);
});

const summaryText = computed(() => {
  // LLM 的 recommendation 字段现在只含入手时机和风险提示等总结
  if (llmCards.value.length > 0) return props.recommendation || "";
  // fallback 模式：显示 recommendation 全文
  if (!llmCards.value.length && props.recommendation) return props.recommendation;
  return "";
});

// --- 报告区块着色：每个 h2/h3 小标题区块换不同背景色 ---
const SECTION_COLORS = [
  { bg: "#f0f6ff", border: "#4a90d9" },
  { bg: "#f3faf7", border: "#52c41a" },
  { bg: "#fef7f0", border: "#fa8c16" },
  { bg: "#faf4ff", border: "#a34dbe" },
  { bg: "#f0fafc", border: "#13c2c2" },
];

function sectionColorize(html: string): string {
  if (!html) return html;

  // 在每个 h2/h3 之前注入分割标记
  const withMarkers = html.replace(/(<h[23])/g, "<!-- section-break -->$1");

  const chunks = withMarkers.split("<!-- section-break -->");
  if (chunks.length <= 1) return html;

  let result = "";
  let colorIdx = 0;

  for (const chunk of chunks) {
    const trimmed = chunk.trim();
    if (!trimmed) continue;

    // 找出这个块的标题级别
    const hMatch = trimmed.match(/^<h([23])/);
    const c = SECTION_COLORS[colorIdx % SECTION_COLORS.length];

    // h3 子标题用更浅的缩进样式
    if (hMatch && hMatch[1] === "3") {
      result += `<div style="margin-bottom:12px; margin-left:8px; padding:12px 16px; border-radius:6px; background:${c.bg}; border-left:3px solid ${c.border};">${trimmed}</div>`;
    } else if (hMatch && hMatch[1] === "2") {
      result += `<div style="margin-bottom:16px; padding:16px 20px; border-radius:8px; background:${c.bg}; border-left:4px solid ${c.border};">${trimmed}</div>`;
      colorIdx++; // h2 换色，h3 沿用当前色
    } else {
      // 未以标题开头的片段（报告开头的导语），不加包裹
      result += trimmed;
    }
  }

  return result;
}

const renderedReport = computed(() => {
  const raw = props.report ? (marked(props.report) as string) : "";
  return sectionColorize(raw);
});
const renderedSummary = computed(() => summaryText.value ? marked(summaryText.value) as string : "");

function renderedCardText(text: string): string {
  return text ? marked(text) as string : "";
}

const hasContent = computed(() => !!(props.recommendation || cards.value.length > 0));

const SEARCH_URLS: Record<string, string> = {
  "京东": "https://search.jd.com/Search?keyword=",
  "淘宝": "https://s.taobao.com/search?q=",
  "天猫": "https://list.tmall.com/search_product.htm?q=",
  "拼多多": "https://mobile.yangkeduo.com/search_result.html?search_key=",
  "闲鱼": "https://s.2.taobao.com/list/list.htm?q=",
  "转转": "https://m.zhuanzhuan.com/platform/search?keyword=",
};

function buildSearchUrl(platform: string, keyword: string): string {
  const base = SEARCH_URLS[platform] || "https://www.google.com/search?q=";
  return base + encodeURIComponent(keyword);
}
</script>

<style scoped>
.report-card {
  background: #fff; border-radius: 12px; padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); border-left: 4px solid #4a90d9;
}
.report-card h2 { margin-bottom: 16px; color: #2b6cb0; }
.report { line-height: 1.9; color: #444; }

.buy-advice-card {
  background: #fff7e6; border-radius: 12px; padding: 24px;
  box-shadow: 0 2px 12px rgba(250, 140, 22, 0.12); border-left: 4px solid #fa8c16;
}
.buy-advice-card h2 { margin-bottom: 20px; color: #d46b08; }

.recommendation-content { line-height: 1.9; color: #5a3e1b; font-size: 15px; margin-bottom: 20px; }

.cards-sequence { display: flex; flex-direction: column; gap: 0; }

.card-block { margin-bottom: 20px; }
.card-block:last-child { margin-bottom: 0; }

.card-reason {
  line-height: 1.9; color: #5a3e1b; font-size: 15px;
  padding: 0 4px 12px;
}

.card-reason :deep(strong) { color: #d46b08; }
.card-reason :deep(p) { margin: 4px 0; }

.report :deep(h2) { font-size: 18px; color: #2c3e50; margin: 0 0 10px; padding-bottom: 6px; border-bottom: 2px solid #e6f0fa; }
.report :deep(h3) { font-size: 15px; color: #3a6e9e; margin: 0 0 8px; }
/* 段落首尾去掉多余间距，让区块 padding 控制留白 */
.report :deep(p:first-child) { margin-top: 0; }
.report :deep(p:last-child) { margin-bottom: 0; }
.report :deep(table) { width: 100%; border-collapse: collapse; font-size: 14px; margin: 12px 0; }
.report :deep(th) { background: #f0f4f8; padding: 10px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #dde4ed; }
.report :deep(td) { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
.report :deep(blockquote) { border-left: 4px solid #89b4d4; background: #f8fafc; margin: 16px 0; padding: 12px 16px; border-radius: 0 6px 6px 0; }

.recommendation-content :deep(h2) { font-size: 17px; color: #d46b08; margin: 20px 0 8px; }
.recommendation-content :deep(strong) { color: #d46b08; }

.empty-content { text-align: center; padding: 40px 20px; color: #999; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-hint { font-size: 13px; color: #bbb; margin-top: 8px; }
</style>
