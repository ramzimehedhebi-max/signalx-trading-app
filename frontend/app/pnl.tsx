import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import Svg, { Path, Line, Circle, Defs, LinearGradient as SvgLinearGradient, Stop } from "react-native-svg";
import { theme, fmtUsd, symbolToBase } from "../src/theme";
import { api } from "../src/lib/api";

const SCREEN_PAD = 24;

export default function PnLDashboard() {
  const router = useRouter();
  const { t } = useTranslation();
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api.botAnalytics();
      setData(d);
    } catch (e) {
      console.warn("analytics error", e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  if (!data) return null;

  const isProfit = data.total_pnl >= 0;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="pnl-screen">
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="pnl-back-btn">
          <Ionicons name="chevron-back" color="#fff" size={20} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("pnl.title")}</Text>
        <View style={{ width: 42 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />
        }
      >
        {/* HERO: Capital + P&L */}
        <View style={styles.hero}>
          <Text style={styles.heroLabel}>{t("pnl.current_capital")}</Text>
          <Text style={styles.heroCapital}>{fmtUsd(data.capital_current)}</Text>
          <View style={styles.heroRow}>
            <View style={[styles.pnlBadge, { backgroundColor: isProfit ? theme.colors.buy + "22" : theme.colors.sell + "22" }]}>
              <Ionicons
                name={isProfit ? "trending-up" : "trending-down"}
                size={14}
                color={isProfit ? theme.colors.buy : theme.colors.sell}
              />
              <Text style={[styles.pnlText, { color: isProfit ? theme.colors.buy : theme.colors.sell }]}>
                {data.total_pnl >= 0 ? "+" : ""}{fmtUsd(data.total_pnl)} ({data.total_pnl_pct >= 0 ? "+" : ""}{data.total_pnl_pct}%)
              </Text>
            </View>
          </View>
          <View style={styles.splitRow}>
            <View style={styles.splitCol}>
              <Text style={styles.splitLabel}>{t("pnl.realized")}</Text>
              <Text style={[styles.splitVal, { color: data.realized_pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                {data.realized_pnl >= 0 ? "+" : ""}{fmtUsd(data.realized_pnl)}
              </Text>
            </View>
            <View style={styles.splitDivider} />
            <View style={styles.splitCol}>
              <Text style={styles.splitLabel}>{t("pnl.unrealized")}</Text>
              <Text style={[styles.splitVal, { color: data.unrealized_pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                {data.unrealized_pnl >= 0 ? "+" : ""}{fmtUsd(data.unrealized_pnl)}
              </Text>
            </View>
          </View>
        </View>

        {/* EQUITY CURVE */}
        <View style={styles.card}>
          <View style={styles.cardHead}>
            <Text style={styles.cardTitle}>📈 {t("pnl.equity_curve")}</Text>
            <Text style={styles.cardSub}>{data.trades_count} {t("pnl.trades")}</Text>
          </View>
          <EquityChart points={data.equity_curve} positive={isProfit} />
          <View style={styles.curveFooter}>
            <Text style={styles.curveStart}>
              {t("pnl.from")} {fmtUsd(data.capital_start)}
            </Text>
            <Text style={[styles.curveEnd, { color: isProfit ? theme.colors.buy : theme.colors.sell }]}>
              {t("pnl.to")} {fmtUsd(data.capital_current)}
            </Text>
          </View>
        </View>

        {/* WIN RATE DONUT */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🎯 {t("pnl.win_rate_breakdown")}</Text>
          <View style={styles.donutRow}>
            <DonutChart winRate={data.win_rate_pct} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <DonutLegend color={theme.colors.buy} label={t("pnl.wins")} value={data.wins} pct={data.win_rate_pct} />
              <DonutLegend color={theme.colors.sell} label={t("pnl.losses")} value={data.losses} pct={100 - data.win_rate_pct - (data.breakevens / data.trades_count * 100 || 0)} />
              {data.breakevens > 0 && (
                <DonutLegend color={theme.colors.textMuted} label={t("pnl.breakeven")} value={data.breakevens} pct={data.breakevens / data.trades_count * 100} />
              )}
            </View>
          </View>
          <View style={styles.statGrid}>
            <StatBox label={t("pnl.avg_win")} value={`+${fmtUsd(data.avg_win)}`} color={theme.colors.buy} />
            <StatBox label={t("pnl.avg_loss")} value={fmtUsd(data.avg_loss)} color={theme.colors.sell} />
            <StatBox label={t("pnl.profit_factor")} value={data.profit_factor ? data.profit_factor.toFixed(2) : "—"} />
            <StatBox label={t("pnl.avg_duration")} value={`${data.avg_duration_hours}h`} />
          </View>
        </View>

        {/* BEST / WORST + DRAWDOWN */}
        <View style={styles.row2}>
          {data.best_trade && (
            <View style={[styles.miniCard, { borderColor: theme.colors.buy + "40" }]}>
              <Text style={styles.miniLabel}>🏆 {t("pnl.best_trade")}</Text>
              <Text style={styles.miniSym}>{symbolToBase(data.best_trade.symbol)}</Text>
              <Text style={[styles.miniPnl, { color: theme.colors.buy }]}>+{fmtUsd(data.best_trade.pnl)}</Text>
              <Text style={[styles.miniPct, { color: theme.colors.buy }]}>+{data.best_trade.pnl_pct}%</Text>
            </View>
          )}
          {data.worst_trade && (
            <View style={[styles.miniCard, { borderColor: theme.colors.sell + "40" }]}>
              <Text style={styles.miniLabel}>💀 {t("pnl.worst_trade")}</Text>
              <Text style={styles.miniSym}>{symbolToBase(data.worst_trade.symbol)}</Text>
              <Text style={[styles.miniPnl, { color: theme.colors.sell }]}>{fmtUsd(data.worst_trade.pnl)}</Text>
              <Text style={[styles.miniPct, { color: theme.colors.sell }]}>{data.worst_trade.pnl_pct}%</Text>
            </View>
          )}
        </View>

        {/* MAX DRAWDOWN */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📉 {t("pnl.max_drawdown")}</Text>
          <Text style={styles.drawdownVal}>-{fmtUsd(data.max_drawdown)} <Text style={styles.drawdownPct}>(-{data.max_drawdown_pct}%)</Text></Text>
          <Text style={styles.drawdownDesc}>{t("pnl.max_drawdown_desc")}</Text>
        </View>

        {/* TOP / WORST SYMBOLS */}
        {data.top_symbols.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>🥇 {t("pnl.top_symbols")}</Text>
            {data.top_symbols.map((s: any) => (
              <SymbolRow key={s.symbol} s={s} />
            ))}
          </View>
        )}

        {data.worst_symbols.length > 0 && data.worst_symbols[0].pnl < 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>📉 {t("pnl.worst_symbols")}</Text>
            {data.worst_symbols.filter((s: any) => s.pnl < 0).map((s: any) => (
              <SymbolRow key={s.symbol} s={s} />
            ))}
          </View>
        )}

        {/* OPEN POSITIONS LIVE */}
        {data.open_positions.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>🔓 {t("pnl.open_positions")} ({data.open_positions_count})</Text>
            {data.open_positions.map((p: any) => (
              <View key={p.symbol} style={styles.openRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.openSym}>{symbolToBase(p.symbol)}</Text>
                  <Text style={styles.openSub}>Entry {p.entry.toFixed(p.entry < 1 ? 6 : 2)} · Now {p.current.toFixed(p.current < 1 ? 6 : 2)}</Text>
                </View>
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={[styles.openPnl, { color: p.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                    {p.pnl >= 0 ? "+" : ""}{fmtUsd(p.pnl)}
                  </Text>
                  <Text style={[styles.openPct, { color: p.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                    {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct}%
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        <Text style={styles.disclaimer}>{t("pnl.disclaimer")}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function EquityChart({ points, positive }: { points: any[]; positive: boolean }) {
  const W = 320;
  const H = 140;
  if (!points || points.length < 2) {
    return (
      <View style={{ height: H, alignItems: "center", justifyContent: "center" }}>
        <Text style={{ color: theme.colors.textMuted, fontSize: 12 }}>Pas encore de trades</Text>
      </View>
    );
  }
  const ys = points.map((p) => p.equity);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const range = maxY - minY || 1;
  const stepX = W / (points.length - 1);
  const color = positive ? theme.colors.buy : theme.colors.sell;
  let pathD = "";
  let areaD = "";
  points.forEach((p, i) => {
    const x = i * stepX;
    const y = H - ((p.equity - minY) / range) * (H - 20) - 10;
    if (i === 0) {
      pathD = `M${x},${y}`;
      areaD = `M${x},${H} L${x},${y}`;
    } else {
      pathD += ` L${x},${y}`;
      areaD += ` L${x},${y}`;
    }
  });
  areaD += ` L${W},${H} Z`;

  return (
    <View style={{ alignItems: "center" }}>
      <Svg width={W} height={H}>
        <Defs>
          <SvgLinearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={color} stopOpacity={0.3} />
            <Stop offset="1" stopColor={color} stopOpacity={0} />
          </SvgLinearGradient>
        </Defs>
        <Line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke={theme.colors.border} strokeWidth={0.5} strokeDasharray="2,3" />
        <Path d={areaD} fill="url(#grad)" />
        <Path d={pathD} stroke={color} strokeWidth={2.5} fill="none" strokeLinejoin="round" />
        {points.map((p, i) => {
          if (i !== points.length - 1) return null;
          const x = i * stepX;
          const y = H - ((p.equity - minY) / range) * (H - 20) - 10;
          return <Circle key={i} cx={x} cy={y} r={4} fill={color} />;
        })}
      </Svg>
    </View>
  );
}

function DonutChart({ winRate }: { winRate: number }) {
  const SIZE = 110;
  const R = 45;
  const STROKE = 14;
  const C = 2 * Math.PI * R;
  const winLen = (winRate / 100) * C;
  return (
    <View style={{ width: SIZE, height: SIZE, alignItems: "center", justifyContent: "center" }}>
      <Svg width={SIZE} height={SIZE}>
        <Circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R}
          fill="none"
          stroke={theme.colors.sell + "33"}
          strokeWidth={STROKE}
        />
        <Circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={R}
          fill="none"
          stroke={theme.colors.buy}
          strokeWidth={STROKE}
          strokeDasharray={`${winLen}, ${C}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
        />
      </Svg>
      <View style={{ position: "absolute", alignItems: "center" }}>
        <Text style={{ color: "#fff", fontSize: 22, fontWeight: "900" }}>{winRate.toFixed(0)}%</Text>
        <Text style={{ color: theme.colors.textMuted, fontSize: 10, fontWeight: "700", letterSpacing: 1 }}>WINRATE</Text>
      </View>
    </View>
  );
}

function DonutLegend({ color, label, value, pct }: { color: string; label: string; value: number; pct: number }) {
  return (
    <View style={styles.legendRow}>
      <View style={[styles.legendDot, { backgroundColor: color }]} />
      <Text style={styles.legendLabel}>{label}</Text>
      <Text style={styles.legendVal}>
        {value} <Text style={styles.legendPct}>({(pct || 0).toFixed(0)}%)</Text>
      </Text>
    </View>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.statBox}>
      <Text style={styles.statL}>{label}</Text>
      <Text style={[styles.statV, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

function SymbolRow({ s }: { s: any }) {
  const positive = s.pnl >= 0;
  return (
    <View style={styles.symbolRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.symbolName}>{symbolToBase(s.symbol)}</Text>
        <Text style={styles.symbolSub}>{s.trades} trades · {s.win_rate}% winrate</Text>
      </View>
      <Text style={[styles.symbolPnl, { color: positive ? theme.colors.buy : theme.colors.sell }]}>
        {positive ? "+" : ""}{fmtUsd(s.pnl)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  headerRow: { flexDirection: "row", alignItems: "center", padding: SCREEN_PAD, paddingBottom: 8 },
  headerTitle: { flex: 1, textAlign: "center", color: "#fff", fontSize: 18, fontWeight: "800" },
  iconBtn: {
    width: 42, height: 42, borderRadius: 14,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
    alignItems: "center", justifyContent: "center",
  },
  scroll: { padding: SCREEN_PAD, paddingTop: 4, gap: 14 },

  hero: {
    padding: 22, borderRadius: 22,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  heroLabel: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "800", letterSpacing: 1.5 },
  heroCapital: { color: "#fff", fontSize: 38, fontWeight: "900", marginTop: 4, letterSpacing: -1.2 },
  heroRow: { flexDirection: "row", marginTop: 10 },
  pnlBadge: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999,
  },
  pnlText: { fontWeight: "800", fontSize: 13 },
  splitRow: {
    marginTop: 18, paddingTop: 16,
    borderTopColor: theme.colors.border, borderTopWidth: 1,
    flexDirection: "row", alignItems: "center",
  },
  splitCol: { flex: 1 },
  splitDivider: { width: 1, height: 36, backgroundColor: theme.colors.border, marginHorizontal: 14 },
  splitLabel: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  splitVal: { color: "#fff", fontSize: 18, fontWeight: "900", marginTop: 4 },

  card: {
    padding: 18, borderRadius: 20,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  cardHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  cardTitle: { color: "#fff", fontSize: 14, fontWeight: "800", marginBottom: 14 },
  cardSub: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "700" },
  curveFooter: { flexDirection: "row", justifyContent: "space-between", marginTop: 8 },
  curveStart: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "700" },
  curveEnd: { fontSize: 12, fontWeight: "800" },

  donutRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  legendRow: { flexDirection: "row", alignItems: "center", paddingVertical: 4 },
  legendDot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  legendLabel: { color: "#fff", fontSize: 12, fontWeight: "700", flex: 1 },
  legendVal: { color: "#fff", fontSize: 13, fontWeight: "800" },
  legendPct: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "700" },

  statGrid: { flexDirection: "row", flexWrap: "wrap", marginTop: 8, marginHorizontal: -4 },
  statBox: {
    width: "50%", paddingHorizontal: 4, paddingVertical: 6,
  },
  statL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  statV: { color: "#fff", fontSize: 14, fontWeight: "800", marginTop: 2 },

  row2: { flexDirection: "row", gap: 14 },
  miniCard: {
    flex: 1, padding: 16, borderRadius: 18,
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
  },
  miniLabel: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  miniSym: { color: "#fff", fontSize: 16, fontWeight: "800", marginTop: 8 },
  miniPnl: { fontSize: 16, fontWeight: "900", marginTop: 4 },
  miniPct: { fontSize: 12, fontWeight: "700", marginTop: 2 },

  drawdownVal: { color: theme.colors.danger, fontSize: 24, fontWeight: "900", marginTop: 4 },
  drawdownPct: { fontSize: 14, fontWeight: "700" },
  drawdownDesc: { color: theme.colors.textMuted, fontSize: 11, marginTop: 6, lineHeight: 16 },

  symbolRow: { flexDirection: "row", paddingVertical: 10, alignItems: "center", borderBottomColor: theme.colors.border, borderBottomWidth: 0.5 },
  symbolName: { color: "#fff", fontSize: 14, fontWeight: "800" },
  symbolSub: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  symbolPnl: { fontSize: 14, fontWeight: "900" },

  openRow: {
    flexDirection: "row", alignItems: "center", paddingVertical: 10,
    borderBottomColor: theme.colors.border, borderBottomWidth: 0.5,
  },
  openSym: { color: "#fff", fontSize: 13, fontWeight: "800" },
  openSub: { color: theme.colors.textMuted, fontSize: 10, marginTop: 2 },
  openPnl: { fontSize: 14, fontWeight: "900" },
  openPct: { fontSize: 11, fontWeight: "700" },

  disclaimer: { color: theme.colors.textMuted, fontSize: 11, textAlign: "center", marginTop: 16, marginBottom: 12, lineHeight: 16 },
});
