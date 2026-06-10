import { ref } from "vue";

export function useAnalysis() {
  const phase = ref<"idle" | "loading" | "searching" | "analyzing" | "result" | "error">("idle");
  const progress = ref<string[]>([]);
  const currentStep = ref(0);   // 0=未开始, 1=解析中, 2=搜索中, 3=分析中
  const currentAction = ref(""); // 当前正在做什么
  const priceTable = ref<any>(null);
  const trendData = ref<any>(null);
  const report = ref("");
  const recommendation = ref("");
  const recommendCards = ref<any[]>([]);
  const analysisErrors = ref<string[]>([]);
  const error = ref("");

  let eventSource: EventSource | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let hasReceivedEvent = false;
  const SSE_TIMEOUT = 300_000; // 5 分钟（多商品搜索耗时较长）

  function startAnalysis(query: string) {
    phase.value = "loading";
    progress.value = [];
    error.value = "";
    analysisErrors.value = [];
    currentStep.value = 0;
    currentAction.value = "";
    priceTable.value = null;
    trendData.value = null;
    report.value = "";
    recommendation.value = "";
    recommendCards.value = [];

    if (timeoutId) clearTimeout(timeoutId);
    hasReceivedEvent = false;

    eventSource?.close();
    eventSource = new EventSource(`/api/analyze/stream?query=${encodeURIComponent(query)}`);

    function resetTimeout() {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        error.value = "分析超时，请重试";
        phase.value = "error";
        eventSource?.close();
      }, SSE_TIMEOUT);
    }
    resetTimeout();

    eventSource.addEventListener("connected", (e) => {
      hasReceivedEvent = true;
      resetTimeout();
      const data = JSON.parse(e.data);
      progress.value.push(`任务已创建: ${data.task_id}`);
    });

    eventSource.addEventListener("node_start", (e) => {
      resetTimeout();
      const data = JSON.parse(e.data);
      if (data.node === "parse_product") {
        currentStep.value = 1;
        currentAction.value = "正在解析商品型号…";
      } else if (data.node === "research_price") {
        phase.value = "searching";
        currentStep.value = 2;
        currentAction.value = "正在搜索多平台价格…";
      } else if (data.node === "compare_advise") {
        phase.value = "analyzing";
        currentStep.value = 3;
        currentAction.value = "正在生成对比报告…";
      }
    });

    eventSource.addEventListener("progress", (e) => {
      resetTimeout();
      const data = JSON.parse(e.data);
      progress.value.push(data.message || "");
      if (data.node === "research_price") {
        currentStep.value = 2;
      } else if (data.node === "compare_advise") {
        currentStep.value = 3;
      }
      currentAction.value = data.message || currentAction.value;
    });

    eventSource.addEventListener("node_complete", (e) => {
      resetTimeout();
      const data = JSON.parse(e.data);
      progress.value.push(`${data.node} 完成`);
    });

    eventSource.addEventListener("complete", (e) => {
      if (timeoutId) clearTimeout(timeoutId);
      const data = JSON.parse(e.data);
      priceTable.value = data.price_table || {};
      trendData.value = data.trend_data || null;
      report.value = data.comparison_report || "";
      recommendation.value = data.recommendation || "";
      recommendCards.value = data.recommend_cards || [];
      analysisErrors.value = data.errors || [];
      phase.value = "result";
      eventSource?.close();
    });

    eventSource.addEventListener("error", (e) => {
      if (timeoutId) clearTimeout(timeoutId);
      try {
        const data = JSON.parse((e as any).data);
        error.value = data.message || "未知错误";
      } catch {
        if (hasReceivedEvent) {
          error.value = "连接中断，请重新搜索";
        } else {
          error.value = "连接不上后端服务，请确认服务已启动（localhost:8000）";
        }
      }
      phase.value = "error";
      eventSource?.close();
    });
  }

  return {
    phase,
    progress,
    currentStep,
    currentAction,
    priceTable,
    trendData,
    report,
    recommendation,
    recommendCards,
    analysisErrors,
    error,
    startAnalysis,
  };
}
