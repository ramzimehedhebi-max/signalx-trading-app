import AsyncStorage from "@react-native-async-storage/async-storage";

const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const TOKEN_KEY = "auth_token";

async function getToken() {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function setToken(t: string) {
  await AsyncStorage.setItem(TOKEN_KEY, t);
}

export async function clearToken() {
  await AsyncStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (auth) {
    const t = await getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const url = `${BASE_URL}/api${path}`;
  const res = await fetch(url, { ...options, headers });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg = (data && data.detail) || `Erreur ${res.status}`;
    const err: any = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    err.requiresPremium = res.status === 402;
    throw err;
  }
  return data as T;
}

export const api = {
  // Auth
  register: (email: string, password: string, name: string) =>
    request<{ token: string; user: any }>(
      "/auth/register",
      { method: "POST", body: JSON.stringify({ email, password, name }) },
      false
    ),
  login: (email: string, password: string) =>
    request<{ token: string; user: any }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false
    ),
  me: () => request<any>("/auth/me"),

  // Market
  tickers: (symbols?: string) =>
    request<any[]>(`/market/tickers${symbols ? `?symbols=${symbols}` : ""}`, {}, false),
  ticker: (symbol: string) => request<any>(`/market/ticker/${symbol}`, {}, false),
  klines: (symbol: string, interval = "1h", limit = 100) =>
    request<any[]>(
      `/market/klines/${symbol}?interval=${interval}&limit=${limit}`,
      {},
      false
    ),

  // AI
  signal: (symbol: string, interval = "1h") =>
    request<any>("/ai/signal", {
      method: "POST",
      body: JSON.stringify({ symbol, interval }),
    }),
  recentSignals: () => request<any[]>("/ai/signals/recent"),

  // Watchlist
  watchlist: () => request<any[]>("/watchlist"),
  addWatch: (symbol: string) =>
    request<any>("/watchlist", { method: "POST", body: JSON.stringify({ symbol }) }),
  removeWatch: (symbol: string) =>
    request<any>(`/watchlist/${symbol}`, { method: "DELETE" }),

  // Alerts
  alerts: () => request<any[]>("/alerts"),
  createAlert: (symbol: string, target_price: number, direction: "above" | "below") =>
    request<any>("/alerts", {
      method: "POST",
      body: JSON.stringify({ symbol, target_price, direction }),
    }),
  deleteAlert: (id: string) =>
    request<any>(`/alerts/${id}`, { method: "DELETE" }),

  // Portfolio
  portfolio: () => request<any>("/portfolio"),
  addPosition: (symbol: string, quantity: number, entry_price: number, side = "long") =>
    request<any>("/portfolio", {
      method: "POST",
      body: JSON.stringify({ symbol, quantity, entry_price, side }),
    }),
  deletePosition: (id: string) =>
    request<any>(`/portfolio/${id}`, { method: "DELETE" }),

  // Bot
  botConfig: () => request<any>("/bot/config"),
  botUpdateConfig: (cfg: any) =>
    request<any>("/bot/config", { method: "PUT", body: JSON.stringify(cfg) }),
  botPositions: () => request<any[]>("/bot/positions"),
  botTrades: () => request<any[]>("/bot/trades"),
  botStats: () => request<any>("/bot/stats"),
  botReset: () => request<any>("/bot/reset", { method: "POST" }),
  botRunNow: () => request<any>("/bot/run-now", { method: "POST" }),
  botBacktest: (params: any) =>
    request<any>("/bot/backtest", { method: "POST", body: JSON.stringify(params) }),

  // Predictions
  predict: (symbol: string, horizon = "24h") =>
    request<any>("/ai/predict", { method: "POST", body: JSON.stringify({ symbol, horizon }) }),
  predictTop: (horizon = "24h") =>
    request<any[]>(`/ai/predict/top?horizon=${horizon}`),

  // Notifications
  saveExpoPushToken: (token: string) =>
    request<any>("/user/push-token", { method: "POST", body: JSON.stringify({ token }) }),
  notifications: () => request<any>("/notifications"),
  unreadCount: () => request<any>("/notifications/unread-count"),
  markRead: (id: string) => request<any>(`/notifications/${id}/read`, { method: "POST" }),
  markAllRead: () => request<any>("/notifications/read-all", { method: "POST" }),

  // Binance Live
  binanceStatus: () => request<any>("/binance/status"),
  binanceConnect: (api_key: string, api_secret: string) =>
    request<any>("/binance/connect", {
      method: "POST",
      body: JSON.stringify({ api_key, api_secret }),
    }),
  binanceDisconnect: () =>
    request<any>("/binance/disconnect", { method: "DELETE" }),
  binanceAccount: () => request<any>("/binance/account"),

  // Premium
  premiumStatus: () => request<any>("/premium/status"),
  premiumCheckout: () => request<any>("/premium/checkout", { method: "POST" }),
  premiumCancel: () => request<any>("/premium/cancel", { method: "POST" }),
};
