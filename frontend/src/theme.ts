export const theme = {
  colors: {
    bg: "#090C15",
    surface: "#131826",
    surfaceAlt: "#1A2030",
    glass: "rgba(255,255,255,0.04)",
    primary: "#F3BA2F",
    primaryHover: "#F5C953",
    primaryDark: "#A37C13",
    text: "#FFFFFF",
    textSecondary: "#8F9CAE",
    textMuted: "#5A6478",
    border: "rgba(255,255,255,0.08)",
    borderStrong: "rgba(255,255,255,0.14)",
    buy: "#00E396",
    sell: "#FF4560",
    hold: "#3D85C6",
    danger: "#FF4560",
    success: "#00E396",
    overlay: "rgba(0,0,0,0.6)",
  },
  radius: {
    sm: 8,
    md: 16,
    lg: 24,
    full: 9999,
  },
  spacing: (n: number) => n * 4,
};

export const fmtPrice = (n: number) => {
  if (n >= 1000) return n.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(3);
  if (n >= 0.01) return n.toFixed(4);
  return n.toFixed(6);
};

export const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

export const fmtUsd = (n: number) =>
  n.toLocaleString("fr-FR", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export const symbolToBase = (s: string) => s.replace(/USDT$|BUSD$|USD$/, "");
