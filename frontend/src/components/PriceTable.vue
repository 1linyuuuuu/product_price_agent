<template>
  <div class="price-table-card" v-if="data && Object.keys(data).length > 0">
    <h2>比价汇总</h2>

    <div v-for="(prices, spec) in data" :key="spec" class="variant-section">
      <h3 class="variant-header" @click="toggleVariant(spec)">
        <span class="variant-arrow" :class="{ open: !collapsedVariants.has(spec) }">▸</span>
        {{ spec }}
        <span class="variant-count">{{ variantRowCount(prices) }} 条</span>
      </h3>

      <div v-show="!collapsedVariants.has(spec)" class="sub-tables-grid">
        <!-- 全新 -->
        <div v-if="filterByCondition(prices, false).length > 0" class="sub-table-box">
          <h4 class="sub-table-label new-label">全新</h4>
          <div class="table-scroll">
            <table>
              <colgroup>
                <col style="width:14%">
                <col style="width:22%">
                <col style="width:14%">
                <col style="width:14%">
                <col style="width:36%">
              </colgroup>
              <thead>
                <tr>
                  <th>平台</th>
                  <th>店铺</th>
                  <th>价格</th>
                  <th>原价</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(p, i) in visibleRows(filterByCondition(prices, false), spec, false)"
                  :key="i"
                  :class="{ 'best-price': p.price === minPrice(filterByCondition(prices, false)) }"
                >
                  <td>{{ p.platform }}</td>
                  <td>{{ p.shop_name || '-' }}</td>
                  <td class="price">¥{{ formatPrice(p.price) }}</td>
                  <td class="original">{{ p.original_price ? '¥' + formatPrice(p.original_price) : '-' }}</td>
                  <td class="note">{{ p.promotion || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <button
              v-if="filterByCondition(prices, false).length > COLLAPSE_THRESHOLD"
              class="toggle-btn"
              @click="toggleTable(spec, false)"
            >
              {{ expandedTables.has(key(spec, false)) ? '收起 ▴' : `展开全部 ${filterByCondition(prices, false).length} 条 ▾` }}
            </button>
          </div>
        </div>

        <!-- 二手 -->
        <div v-if="filterByCondition(prices, true).length > 0" class="sub-table-box">
          <h4 class="sub-table-label used-label">二手</h4>
          <div class="table-scroll">
            <table>
              <colgroup>
                <col style="width:14%">
                <col style="width:22%">
                <col style="width:14%">
                <col style="width:14%">
                <col style="width:36%">
              </colgroup>
              <thead>
                <tr>
                  <th>平台</th>
                  <th>店铺</th>
                  <th>价格</th>
                  <th>原价</th>
                  <th>成色/备注</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(p, i) in visibleRows(filterByCondition(prices, true), spec, true)"
                  :key="i"
                  :class="{ 'best-price': p.price === minPrice(filterByCondition(prices, true)) }"
                >
                  <td>{{ p.platform }}</td>
                  <td>{{ p.shop_name || '-' }}</td>
                  <td class="price">¥{{ formatPrice(p.price) }}</td>
                  <td class="original">{{ p.original_price ? '¥' + formatPrice(p.original_price) : '-' }}</td>
                  <td class="note">{{ p.condition ? p.condition + (p.promotion ? ' | ' + p.promotion : '') : (p.promotion || '-') }}</td>
                </tr>
              </tbody>
            </table>
            <button
              v-if="filterByCondition(prices, true).length > COLLAPSE_THRESHOLD"
              class="toggle-btn"
              @click="toggleTable(spec, true)"
            >
              {{ expandedTables.has(key(spec, true)) ? '收起 ▴' : `展开全部 ${filterByCondition(prices, true).length} 条 ▾` }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="price-table-card empty-state" v-else>
    <h2>比价汇总</h2>
    <div class="empty-content">
      <p class="empty-icon">&#128230;</p>
      <p>暂时没有搜到价格数据</p>
      <p class="empty-hint">换个关键词试试，或者检查一下网络连接</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

defineProps<{ data: Record<string, any[]> }>();

// 超过此数量的行默认折叠
const COLLAPSE_THRESHOLD = 5;

// 各表格折叠状态：key = "spec|isSecondhand"
const expandedTables = ref(new Set<string>());
// 各 variant 区块折叠状态
const collapsedVariants = ref(new Set<string>());

function key(spec: string, isSecondhand: boolean): string {
  return `${spec}||${isSecondhand}`;
}

function toggleTable(spec: string, isSecondhand: boolean) {
  const k = key(spec, isSecondhand);
  if (expandedTables.value.has(k)) {
    expandedTables.value.delete(k);
  } else {
    expandedTables.value.add(k);
  }
  // 触发响应式更新
  expandedTables.value = new Set(expandedTables.value);
}

function toggleVariant(spec: string) {
  if (collapsedVariants.value.has(spec)) {
    collapsedVariants.value.delete(spec);
  } else {
    collapsedVariants.value.add(spec);
  }
  collapsedVariants.value = new Set(collapsedVariants.value);
}

function visibleRows(prices: any[], spec: string, isSecondhand: boolean): any[] {
  if (expandedTables.value.has(key(spec, isSecondhand))) {
    return prices; // 已展开
  }
  // 首次加载：如果超过阈值就折叠，否则展开
  return prices.length > COLLAPSE_THRESHOLD ? prices.slice(0, COLLAPSE_THRESHOLD) : prices;
}

function variantRowCount(prices: any[]): number {
  return prices.filter(p => p.price > 0).length;
}

function filterByCondition(prices: any[], isSecondhand: boolean): any[] {
  return prices.filter(p => p.is_secondhand === isSecondhand && p.price > 0);
}

function minPrice(prices: any[]): number {
  if (prices.length === 0) return 0;
  return Math.min(...prices.map(p => p.price));
}

function formatPrice(price: number): string {
  return price % 1 === 0 ? price.toFixed(0) : price.toFixed(2);
}
</script>

<style scoped>
.price-table-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-left: 4px solid #52c41a;
}

.price-table-card h2 {
  margin-bottom: 20px;
  color: #389e0d;
}

.variant-section {
  margin-bottom: 20px;
}

.variant-section:last-child {
  margin-bottom: 0;
}

.variant-header {
  font-size: 16px;
  color: #4a90d9;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e6f0fa;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.variant-header:hover {
  color: #2b6cb0;
}

.variant-arrow {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 12px;
  color: #999;
}

.variant-arrow.open {
  transform: rotate(90deg);
}

.variant-count {
  font-size: 13px;
  color: #999;
  font-weight: 400;
  margin-left: 4px;
}

.sub-tables-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sub-table-box {
  width: 100%;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  background: #fafafa;
}

.sub-table-label {
  margin: 0;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.new-label { background: #52c41a; }
.used-label { background: #fa8c16; }

.table-scroll {
  overflow-x: auto;
  padding: 12px 14px 4px;
}

.sub-table-box table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 14px;
  background: #fff;
  border-radius: 4px;
  overflow: hidden;
}

.sub-table-box th {
  background: #f0f4f8;
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  color: #555;
  border-bottom: 2px solid #dde4ed;
  white-space: nowrap;
}

.sub-table-box td {
  padding: 7px 10px;
  border-bottom: 1px solid #f0f0f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub-table-box tbody tr:hover { background: #fafbfc; }

.sub-table-box .price { font-weight: 600; color: #333; }
.sub-table-box .original { color: #aaa; text-decoration: line-through; }

.sub-table-box .note {
  color: #888;
  font-size: 13px;
  white-space: normal;
  word-break: break-all;
}

.sub-table-box .best-price { background: #f6ffed; }
.sub-table-box .best-price .price { color: #52c41a; font-size: 15px; }

.toggle-btn {
  display: block;
  width: 100%;
  padding: 6px 0 10px;
  border: none;
  background: transparent;
  color: #4a90d9;
  font-size: 13px;
  cursor: pointer;
  text-align: center;
}

.toggle-btn:hover {
  color: #2b6cb0;
  background: #f0f5fa;
}

.empty-content { text-align: center; padding: 40px 20px; color: #999; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-hint { font-size: 13px; color: #bbb; margin-top: 8px; }
</style>
