export interface ProductVariant {
  id: number;
  spec: string;
  search_query: string;
  status: "pending" | "searching" | "done";
}

export interface PriceInfo {
  platform: string;
  shop_name: string;
  price: number;
  original_price: number;
  is_official: boolean;
  is_secondhand: boolean;
  in_stock: boolean;
  promotion: string;
  source_url: string;
  fetched_at: string;
  condition?: string;
  repairs?: string;
  has_invoice?: boolean;
  warranty_left?: string;
  seller_rating?: string;
  original_purchase_date?: string;
  extra_attrs: Record<string, string>;
}

export interface AnalysisPhase {
  type: "idle" | "loading" | "searching" | "analyzing" | "result" | "error";
}

export interface SSEEvent {
  event: string;
  data: Record<string, any>;
}
