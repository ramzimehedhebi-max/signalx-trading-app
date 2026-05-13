import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Dimensions,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import Svg, { Path, Defs, LinearGradient, Stop, Line } from "react-native-svg";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import { theme, fmtUsd, symbolToBase } from "../src/theme";
import { api } from "../src/lib/api";

const PERIODS = [
  { v: 7, l: "7J" },
  { v: 14, l: "14J" },
  { v: 30, l: "30J" },
  { v: 60, l: "60J" },
];

export default function Backtest() {
  const router = useRouter();
  const { t } = useTranslation();
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const cfg = await api.botConfig();
      const r = await api.botBacktest({
        days,
        capital_usdt: cfg.capital_usdt,
        position_size_pct: cfg.position_size_pct,
        max_positions: cfg.max_positions,
        stop_loss_pct: cfg.stop_loss_pct,
        take_profit_pct: cfg.take_profit_pct,
        pairs: cfg.pairs,
        interval: "1h",
      });
      setResult(r);
      Haptics.notificationAsync(
        r.total_pnl >= 0 ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Warning
      );
    } catch (e: any) {
      Alert.alert(t("common.error"), e.message || t("backtest.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="backtest-screen">
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.head}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="backtest-back-btn">
            <Ionicons name="chevron-back" size={22} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.headTitle}>{t("backtest.title")}</Text>
          <View style={styles.iconBtn} />
        </View>

        <Text style={styles.subtitle}>{t("backtest.subtitle")}</Text>

        <Text style={styles.label}>{t("backtest.period")}</Text>
        <View style={styles.periods}>
          {PERIODS.map((p) => (
            <TouchableOpacity
              key={p.v}
              onPress={() => setDays(p.v)}
              style={[styles.chip, days === p.v && styles.chipActive]}
              testID={`bt-period-${p.v}`}
            >
              <Text style={[styles.chipText, days === p.v && styles.chipTextActive]}>{t(`backtest.period_${p.v}`)}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          onPress={run}
          disabled={loading}
          style={[styles.cta, loading && { opacity: 0.7 }]}
          testID="backtest-run-btn"
        >
          {loading ? (
            <ActivityIndicator color="#000" />
          ) : (
            <>
              <Ionicons name="rocket" size={18} color="#000" />
              <Text style={styles.ctaText}>{t("backtest.run_btn")}</Text>
            </>
          )}
        </TouchableOpacity>

        {result && <BacktestResult data={result} />}

        {!result && !loading && (
          <View style={styles.hint}>
            <Ionicons name="information-circle-outline" size={18} color={theme.colors.textMuted} />
            <Text style={styles.hintText}>{t("backtest.hint")}</Text>
          </View>
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function BacktestResult({ data }: { data: any }) {
  const { t } = useTranslation();
  const isProfit = data.total_pnl >= 0;
  const outperform = data.outperformance_pct >= 0;
  const width = Dimensions.get("window").width - 48;

  return (
    <View style={{ gap: 14, marginTop: 22 }}>
      {/* Headline Result */}
      <View style={[styles.resultCard, { borderColor: isProfit ? theme.colors.buy : theme.colors.sell }]}>
        <Text style={styles.resultL}>{t("backtest.headline", { days: data.period_days })}</Text>
        <Text style={[styles.resultValue, { color: isProfit ? theme.colors.buy : theme.colors.sell }]}>
          {isProfit ? "+" : ""}
          {fmtUsd(data.total_pnl)}
        </Text>
        <Text style={[styles.resultPct, { color: isProfit ? theme.colors.buy : theme.colors.sell }]}>
          {isProfit ? "+" : ""}
          {t("backtest.in_days", { pct: data.total_pnl_pct.toFixed(2), days: data.period_days })}
        </Text>
        <View style={styles.capitalRow}>
          <View style={styles.capBox}>
            <Text style={styles.capL}>{t("backtest.capital_start")}</Text>
            <Text style={styles.capV}>{fmtUsd(data.capital_start)}</Text>
          </View>
          <Ionicons name="arrow-forward" color={theme.colors.textMuted} size={18} />
          <View style={styles.capBox}>
            <Text style={styles.capL}>{t("backtest.capital_end")}</Text>
            <Text style={styles.capV}>{fmtUsd(data.capital_end)}</Text>
          </View>
        </View>
      </View>

      {/* Equity curve */}
      {data.equity_curve?.length > 1 && (
        <View style={styles.chartCard}>
          <Text style={styles.chartTitle}>{t("backtest.equity_curve")}</Text>
          <EquityCurve data={data.equity_curve} start={data.capital_start} width={width - 32} />
        </View>
      )}

      {/* Stats grid */}
      <View style={styles.stats}>
        <StatBox label={t("backtest.trades")} value={String(data.trades_count)} />
        <StatBox
          label={t("backtest.winrate")}
          value={`${data.win_rate_pct.toFixed(0)}%`}
          color={data.win_rate_pct >= 50 ? theme.colors.buy : theme.colors.sell}
        />
        <StatBox label={t("backtest.wins")} value={String(data.wins)} color={theme.colors.buy} />
        <StatBox label={t("backtest.losses")} value={String(data.losses)} color={theme.colors.sell} />
      </View>

      <View style={styles.stats}>
        <StatBox label={t("backtest.avg_win")} value={fmtUsd(data.avg_win)} color={theme.colors.buy} small />
        <StatBox label={t("backtest.avg_loss")} value={fmtUsd(data.avg_loss)} color={theme.colors.sell} small />
      </View>

      {/* Best/worst */}
      {data.best_trade && (
        <View style={styles.bwRow}>
          <View style={[styles.bwCard, { borderColor: "rgba(0,227,150,0.3)" }]}>
            <Text style={styles.bwL}>{t("backtest.best")}</Text>
            <Text style={styles.bwSym}>{symbolToBase(data.best_trade.symbol)}</Text>
            <Text style={[styles.bwV, { color: theme.colors.buy }]}>
              +{fmtUsd(data.best_trade.pnl)} ({data.best_trade.pnl_pct.toFixed(2)}%)
            </Text>
          </View>
          {data.worst_trade && (
            <View style={[styles.bwCard, { borderColor: "rgba(255,69,96,0.3)" }]}>
              <Text style={styles.bwL}>{t("backtest.worst")}</Text>
              <Text style={styles.bwSym}>{symbolToBase(data.worst_trade.symbol)}</Text>
              <Text style={[styles.bwV, { color: theme.colors.sell }]}>
                {fmtUsd(data.worst_trade.pnl)} ({data.worst_trade.pnl_pct.toFixed(2)}%)
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Buy & Hold comparison */}
      <View style={styles.compareCard}>
        <Text style={styles.compareTitle}>{t("backtest.vs_hodl")}</Text>
        <View style={styles.compareRow}>
          <Text style={styles.compareLabel}>{t("backtest.bot_ai")}</Text>
          <Text style={[styles.compareVal, { color: isProfit ? theme.colors.buy : theme.colors.sell }]}>
            {isProfit ? "+" : ""}
            {data.total_pnl_pct.toFixed(2)}%
          </Text>
        </View>
        <View style={styles.compareRow}>
          <Text style={styles.compareLabel}>{t("backtest.hodl")}</Text>
          <Text style={[styles.compareVal, { color: data.buy_hold_pct >= 0 ? theme.colors.buy : theme.colors.sell }]}>
            {data.buy_hold_pct >= 0 ? "+" : ""}
            {data.buy_hold_pct.toFixed(2)}%
          </Text>
        </View>
        <View style={[styles.compareRow, styles.compareRowBorder]}>
          <Text style={styles.compareLabel}>{t("backtest.outperf")}</Text>
          <Text style={[styles.compareVal, { color: outperform ? theme.colors.buy : theme.colors.sell }]}>
            {outperform ? "+" : ""}
            {data.outperformance_pct.toFixed(2)}%
          </Text>
        </View>
      </View>

      {/* Recent trades */}
      {data.trades?.length > 0 && (
        <>
          <Text style={styles.sectionT}>{t("backtest.recent_trades")}</Text>
          {data.trades.slice(-10).reverse().map((tr: any, i: number) => (
            <View key={i} style={styles.tradeRow}>
              <View
                style={[
                  styles.tradePill,
                  { backgroundColor: tr.pnl >= 0 ? theme.colors.buy : theme.colors.sell },
                ]}
              >
                <Ionicons name={tr.pnl >= 0 ? "checkmark" : "close"} size={11} color="#000" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.tradeSym}>
                  {symbolToBase(tr.symbol)}{" "}
                  <Text style={styles.tradeReason}>
                    · {tr.exit_reason === "take_profit" ? t("backtest.exit_reason.tp") : tr.exit_reason === "stop_loss" ? t("backtest.exit_reason.sl") : t("backtest.exit_reason.end")}
                  </Text>
                </Text>
                <Text style={styles.tradeTime}>
                  {new Date(tr.entry_time).toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" })} →{" "}
                  {new Date(tr.exit_time).toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" })}
                </Text>
              </View>
              <Text style={[styles.tradePnl, { color: tr.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                {tr.pnl >= 0 ? "+" : ""}
                {tr.pnl_pct.toFixed(2)}%
              </Text>
            </View>
          ))}
        </>
      )}

      <Text style={styles.disclaimer}>{t("backtest.disclaimer")}</Text>
    </View>
  );
}

function StatBox({ label, value, color, small }: any) {
  return (
    <View style={styles.statBox}>
      <Text style={styles.statL}>{label}</Text>
      <Text style={[styles.statV, color && { color }, small && { fontSize: 13 }]}>{value}</Text>
    </View>
  );
}

function EquityCurve({ data, start, width }: { data: any[]; start: number; width: number }) {
  const height = 140;
  if (data.length < 2) return null;
  const values = data.map((d) => d.equity);
  const min = Math.min(...values, start);
  const max = Math.max(...values, start);
  const range = max - min || 1;
  const stepX = width / (data.length - 1);
  const yFor = (v: number) => height - ((v - min) / range) * height;
  const startY = yFor(start);
  const points = data.map((d, i) => [i * stepX, yFor(d.equity)] as [number, number]);
  const lastEquity = values[values.length - 1];
  const isProfit = lastEquity >= start;
  const color = isProfit ? theme.colors.buy : theme.colors.sell;
  const gradId = `eq-${isProfit ? "p" : "n"}`;
  const path = "M " + points.map(([x, y], i) => (i === 0 ? `${x},${y}` : `L ${x},${y}`)).join(" ");
  const area = `${path} L ${width},${height} L 0,${height} Z`;
  return (
    <Svg width={width} height={height} style={{ marginTop: 10 }}>
      <Defs>
        <LinearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity="0.3" />
          <Stop offset="1" stopColor={color} stopOpacity="0" />
        </LinearGradient>
      </Defs>
      <Line
        x1={0}
        x2={width}
        y1={startY}
        y2={startY}
        stroke={theme.colors.textMuted}
        strokeWidth={1}
        strokeDasharray="4,4"
      />
      <Path d={area} fill={`url(#${gradId})`} />
      <Path d={path} stroke={color} strokeWidth={2} fill="none" />
    </Svg>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  iconBtn: {
    width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  headTitle: { color: "#fff", fontSize: 20, fontWeight: "900" },
  subtitle: { color: theme.colors.textSecondary, fontSize: 13, lineHeight: 19, marginBottom: 22 },
  label: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginBottom: 10 },
  periods: { flexDirection: "row", gap: 8, marginBottom: 18 },
  chip: {
    paddingHorizontal: 18, paddingVertical: 10, borderRadius: 999,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  chipActive: { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
  chipText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 13 },
  chipTextActive: { color: "#000" },

  cta: {
    backgroundColor: theme.colors.primary, borderRadius: 999, paddingVertical: 16,
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    shadowColor: theme.colors.primary, shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
  },
  ctaText: { color: "#000", fontWeight: "900", fontSize: 15 },

  hint: {
    marginTop: 20, flexDirection: "row", gap: 8, alignItems: "flex-start",
    padding: 14, backgroundColor: theme.colors.surface, borderRadius: 14, borderColor: theme.colors.border, borderWidth: 1,
  },
  hintText: { color: theme.colors.textSecondary, fontSize: 12, flex: 1, lineHeight: 18 },

  resultCard: {
    padding: 22, borderRadius: 24, alignItems: "center",
    backgroundColor: theme.colors.surface, borderWidth: 1.5,
  },
  resultL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 },
  resultValue: { fontSize: 38, fontWeight: "900", letterSpacing: -1, marginTop: 6 },
  resultPct: { fontSize: 14, fontWeight: "800", marginTop: 4 },
  capitalRow: { flexDirection: "row", alignItems: "center", gap: 14, marginTop: 18, width: "100%", justifyContent: "center" },
  capBox: { alignItems: "center" },
  capL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  capV: { color: "#fff", fontSize: 14, fontWeight: "800", marginTop: 4 },

  chartCard: {
    padding: 16, borderRadius: 22,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  chartTitle: { color: "#fff", fontWeight: "800", fontSize: 13 },

  stats: { flexDirection: "row", gap: 10 },
  statBox: {
    flex: 1, padding: 12, borderRadius: 14,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  statL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  statV: { color: "#fff", fontSize: 17, fontWeight: "900", marginTop: 4 },

  bwRow: { flexDirection: "row", gap: 10 },
  bwCard: { flex: 1, padding: 14, borderRadius: 14, backgroundColor: theme.colors.surface, borderWidth: 1 },
  bwL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  bwSym: { color: "#fff", fontWeight: "800", fontSize: 14, marginTop: 4 },
  bwV: { fontSize: 12, fontWeight: "800", marginTop: 4 },

  compareCard: {
    padding: 16, borderRadius: 18,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  compareTitle: { color: "#fff", fontWeight: "800", fontSize: 14, marginBottom: 12 },
  compareRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 6 },
  compareRowBorder: { borderTopColor: theme.colors.border, borderTopWidth: 1, marginTop: 4, paddingTop: 10 },
  compareLabel: { color: theme.colors.textSecondary, fontSize: 13 },
  compareVal: { fontWeight: "900", fontSize: 16 },

  sectionT: { color: "#fff", fontWeight: "900", fontSize: 15, marginTop: 8 },
  tradeRow: {
    flexDirection: "row", alignItems: "center", gap: 10,
    padding: 12, borderRadius: 14,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  tradePill: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  tradeSym: { color: "#fff", fontWeight: "800", fontSize: 13 },
  tradeReason: { color: theme.colors.textSecondary, fontWeight: "600", fontSize: 11 },
  tradeTime: { color: theme.colors.textMuted, fontSize: 10, marginTop: 2 },
  tradePnl: { fontWeight: "800", fontSize: 13 },

  disclaimer: { color: theme.colors.textMuted, fontSize: 11, textAlign: "center", marginTop: 8, lineHeight: 16 },
});
