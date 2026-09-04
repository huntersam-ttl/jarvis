// Shared TypeScript types mirroring the Jarvis backend DTOs.

export type HealthResponse = {
  status: string;
  version: string;
  environment: string;
};

export type ProviderModel = {
  id: string;
  owned_by?: string | null;
};

export type ProviderModelList = {
  provider: string;
  models: ProviderModel[];
  count: number;
};

export type ProviderInfo = {
  name: string;
  status: "connected" | "offline" | "not_configured";
  base_url?: string | null;
  default_model?: string | null;
  model_count?: number | null;
  api_key_configured: boolean;
};

export type ProviderList = {
  providers: ProviderInfo[];
};

export type ChatRequest = {
  message: string;
  model?: string | null;
};

export type ChatRunMeta = {
  requested_model: string | null;
  resolved_model: string;
  provider: string;
  duration_ms: number;
  success: boolean;
};

export type ChatResponse = {
  reply: string;
  model: string;
  provider: string;
  status: "completed" | "failed";
  run: ChatRunMeta;
};

export type SystemComponent = {
  name: string;
  status: "online" | "offline" | "not_installed" | "not_configured" | string;
  detail?: string | null;
};

export type SystemStatus = {
  overall: "online" | "degraded" | "offline";
  components: SystemComponent[];
};

// ---------------------------------------------------------------- trading
export type TradingPosition = {
  symbol: string;
  side: "long" | "short" | string;
  qty: number;
  entry_price: number;
  unrealized_pnl: number;
};

export type TradingActivityItem = {
  id: string;
  time: string;
  event: "started" | "paused" | "resumed" | "stopped" | "trade" | "error" | string;
  detail?: string | null;
};

export type TradingPerformance = {
  today_pnl: number;
  total_pnl: number;
  win_rate?: number | null;
  trades_today: number;
};

export type TradingStatus = {
  connected: boolean;
  mode: "paper" | "live" | string;
  state: "offline" | "running" | "paused" | "error" | string;
  open_positions: number;
  today_pnl: number;
  last_heartbeat?: string | null;
  adapter: "mock" | "http" | string;
};

export type TradingCommandResult = {
  success: boolean;
  state: string;
  detail?: string | null;
};
