<template>
  <div class="product-card">
    <!-- 缩略图 -->
    <div class="card-thumb">
      <img
        v-if="firstImage"
        :src="firstImage"
        :alt="card.variant"
        loading="lazy"
        @error="onImgError"
      />
      <div v-else class="thumb-placeholder"></div>
    </div>

    <!-- 信息区 -->
    <div class="card-info">
      <div class="info-top">
        <h3 class="card-name">{{ card.variant }}</h3>
        <span class="condition-tag" :class="card.is_used ? 'used' : 'new'">
          {{ card.is_used ? '二手' : '全新' }}
        </span>
      </div>
      <div class="info-meta">
        <span class="card-price">¥{{ formatPrice(card.price) }}</span>
        <span class="card-platform">{{ card.platform }}{{ card.shop_name ? ' · ' + card.shop_name : '' }}</span>
      </div>
      <div class="info-reason" v-if="card.reason">{{ card.reason }}</div>
      <a :href="buyUrl" target="_blank" rel="noopener" class="card-link">{{ linkText }}</a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  card: {
    variant: string;
    platform: string;
    shop_name?: string;
    price: number;
    is_used?: boolean;
    image?: string;
    all_images?: string[];
    buy_url?: string;
    buyUrl?: string;
    reason: string;
  };
}>();

const firstImage = computed(() => {
  const imgs = props.card.all_images || [];
  if (imgs.length > 0) return imgs[0];
  if (props.card.image?.startsWith("http")) return props.card.image;
  return "";
});

function onImgError(e: Event) {
  (e.target as HTMLElement).style.display = "none";
}

const buyUrl = computed(() => props.card.buy_url || props.card.buyUrl || "#");

const DIRECT_STORE_PATTERNS = [
  /taobao\.com\/chanpin\//i, /item\.jd\.com/i, /detail\.tmall\.com/i,
  /item\.taobao\.com/i, /yangkeduo\.com\/goods/i, /pinduoduo\.com\/goods/i,
];
const isDirectStore = computed(() => DIRECT_STORE_PATTERNS.some(p => p.test(buyUrl.value)));
const platformLabel = computed(() => props.card.platform || "平台");
const linkText = computed(() =>
  isDirectStore.value ? `去 ${platformLabel.value} 购买 →` : `去 ${platformLabel.value} 搜索 →`
);

function formatPrice(price: number): string {
  return price >= 1000 ? (price / 1000).toFixed(price % 1000 === 0 ? 0 : 1) + "k" : String(price);
}
</script>

<style scoped>
.product-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  transition: box-shadow 0.15s;
}
.product-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card-thumb {
  flex-shrink: 0;
  width: 72px;
  height: 72px;
  border-radius: 6px;
  overflow: hidden;
  background: #f5f5f5;
}
.card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-placeholder {
  width: 100%;
  height: 100%;
  background: #f5f5f5;
}

.card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.info-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.condition-tag {
  flex-shrink: 0;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
}
.condition-tag.new { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
.condition-tag.used { background: #fff7e6; color: #fa8c16; border: 1px solid #ffd591; }

.info-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.card-price {
  font-size: 18px;
  font-weight: 700;
  color: #cf1322;
}

.card-platform {
  font-size: 12px;
  color: #888;
}

.info-reason {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
}

.card-link {
  display: inline-block;
  margin-top: 2px;
  font-size: 12px;
  color: #fa8c16;
  text-decoration: none;
  font-weight: 600;
}
.card-link:hover { color: #d46b08; }
</style>
