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
    // Build a user-friendly error message.
    // 1) If backend returned a clean JSON {detail: "..."} → use that.
    // 2) If Cloudflare/proxy returned a 5xx HTML page → show a clear "server temporarily down" message.
    let msg: string;
    if (data && typeof data === "object" && data.detail) {
      msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } else if (res.status >= 520 && res.status <= 530) {
      // Cloudflare-specific gateway errors (520-530)
      msg =
        "Le serveur est temporairement indisponible (déploiement ou pic de charge). " +
        "Réessaie dans 30 secondes.";
    } else if (res.status === 502 || res.status === 503 || res.status === 504) {
      msg =
        "Le serveur ne répond pas (502/503/504). Réessaie dans quelques secondes.";
    } else if (res.status === 429) {
      msg = "Trop de tentatives. Attends 60 secondes avant de réessayer.";
    } else if (res.status === 401) {
      msg = "Session expirée. Reconnecte-toi.";
    } else if (res.status === 404) {
      msg = "Ressource introuvable.";
    } else {
      msg = `Erreur ${res.status}. Réessaie ou contacte le support.`;
    }
    const err: any = new Error(msg);
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
  botAnalytics: () => request<any>("/bot/analytics"),
  botLiveHistory: () => request<any>("/bot/live-history"),
  botTraderReadiness: () => request<any>("/bot/trader-readiness"),
  quizSubmit: (body: { score: number; answers: string[]; passed: boolean; time_spent_sec?: number }) =>
    request<any>("/quiz/submit", { method: "POST", body: JSON.stringify(body) }),
  adminQuizStats: () => request<any>("/admin/quiz-stats"),
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
  telegramStatus: () => request<any>("/notifications/telegram/status"),
  telegramTest: () => request<any>("/notifications/telegram/test", { method: "POST" }),

  // Binance Live
  binanceStatus: () => request<any>("/binance/status"),
  binanceConnect: (api_key: string, api_secret: string, force: boolean = false) =>
    request<any>(`/binance/connect${force ? "?force=true" : ""}`, {
      method: "POST",
      body: JSON.stringify({ api_key, api_secret }),
    }),
  binanceDisconnect: () =>
    request<any>("/binance/disconnect", { method: "DELETE" }),
  binanceAccount: () => request<any>("/binance/account"),

  // Premium
  premiumStatus: () => request<any>("/premium/status"),
  premiumCheckout: (success_url?: string, cancel_url?: string) =>
    request<any>("/premium/checkout", {
      method: "POST",
      body: JSON.stringify({ success_url, cancel_url }),
    }),
  premiumCancel: () => request<any>("/premium/cancel", { method: "POST" }),

  // Auth — password reset
  forgotPassword: (email: string) =>
    request<any>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  resetPassword: (email: string, code: string, new_password: string) =>
    request<any>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, code, new_password }),
    }),
};
