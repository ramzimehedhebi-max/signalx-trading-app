import React, { useCallback, useEffect, useState } from "react";
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
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { theme, fmtPrice, fmtPct, symbolToBase } from "../../src/theme";
import { api } from "../../src/lib/api";
import CandleChart from "../../src/components/CandleChart";

const INTERVALS = [
  { v: "15m", l: "15m" },
  { v: "1h", l: "1h" },
  { v: "4h", l: "4h" },
  { v: "1d", l: "1J" },
  { v: "1w", l: "1S" },
];

export default function CoinDetail() {
  const { symbol: rawSym } = useLocalSearchParams<{ symbol: string }>();
  const symbol = (rawSym || "BTCUSDT").toUpperCase();
  const router = useRouter();

  const [ticker, setTicker] = useState<any | null>(null);
  const [klines, setKlines] = useState<any[]>([]);
  const [interval, setInterval] = useState("1h");
  const [signal, setSignal] = useState<any | null>(null);
  const [loadingSig, setLoadingSig] = useState(false);
  const [inWatch, setInWatch] = useState(false);
  const [loading, setLoading] = useState(true);

  const w = Dimensions.get("window").width - 48;

  const load = useCallback(
    async (currentInterval: string) => {
      try {
        const [t, k, wl] = await Promise.all([
          api.ticker(symbol),
          api.klines(symbol, currentInterval, 60),
          api.watchlist().catch(() => []),
        ]);
        setTicker(t);
        setKlines(k);
        setInWatch(wl.some((x: any) => x.symbol === symbol));
      } catch (e) {
        console.warn(e);
      }
    },
    [symbol]
  );

  useEffect(() => {
    (async () => {
      await load(interval);
      setLoading(false);
    })();
  }, [load, interval]);

  const toggleWatch = async () => {
    try {
      if (inWatch) {
        await api.removeWatch(symbol);
        setInWatch(false);
      } else {
        await api.addWatch(symbol);
        setInWatch(true);
      }
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    }
  };

  const generate = async () => {
    setLoadingSig(true);
    setSignal(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const s = await api.signal(symbol, interval);
      setSignal(s);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    } finally {
      setLoadingSig(false);
    }
  };

  if (loading || !ticker) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

  const isUp = ticker.priceChangePercent >= 0;
  const colorFor = (a: string) => (a === "BUY" ? theme.colors.buy : a === "SELL" ? theme.colors.sell : theme.colors.hold);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="coin-screen">
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.head}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="coin-back-btn">
            <Ionicons name="chevron-back" size={22} color="#fff" />
          </TouchableOpacity>
          <View style={{ alignItems: "center" }}>
            <Text style={styles.headSym}>{symbolToBase(symbol)}</Text>
            <Text style={styles.headPair}>{symbol}</Text>
          </View>
          <TouchableOpacity onPress={toggleWatch} style={styles.iconBtn} testID="coin-watch-toggle">
            <Ionicons
              name={inWatch ? "star" : "star-outline"}
              size={22}
              color={inWatch ? theme.colors.primary : "#fff"}
            />
          </TouchableOpacity>
        </View>

        <View style={styles.priceBlock}>
          <Text style={styles.price}>${fmtPrice(ticker.lastPrice)}</Text>
          <View style={[styles.pnlPill, { backgroundColor: isUp ? "rgba(0,227,150,0.15)" : "rgba(255,69,96,0.15)" }]}>
            <Ionicons name={isUp ? "trending-up" : "trending-down"} size={14} color={isUp ? theme.colors.buy : theme.colors.sell} />
            <Text style={[styles.pnlText, { color: isUp ? theme.colors.buy : theme.colors.sell }]}>
              {fmtPct(ticker.priceChangePercent)}  ·  ${fmtPrice(Math.abs(ticker.priceChange))}
            </Text>
          </View>
        </View>

        {/* Stats row */}
        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statL}>HAUT 24H</Text>
            <Text style={styles.statV}>${fmtPrice(ticker.highPrice)}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statL}>BAS 24H</Text>
            <Text style={styles.statV}>${fmtPrice(ticker.lowPrice)}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statL}>VOLUME</Text>
            <Text style={styles.statV}>${(ticker.quoteVolume / 1e6).toFixed(1)}M</Text>
          </View>
        </View>

        {/* Chart */}
        <View style={styles.chartCard}>
          <View style={styles.intervals}>
            {INTERVALS.map((i) => (
              <TouchableOpacity
                key={i.v}
                onPress={() => setInterval(i.v)}
                style={[styles.intChip, interval === i.v && styles.intChipActive]}
                testID={`coin-interval-${i.v}`}
              >
                <Text style={[styles.intChipText, interval === i.v && styles.intChipTextActive]}>{i.l}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={{ alignItems: "center", marginTop: 4 }}>
            <CandleChart klines={klines} width={w - 32} height={220} />
          </View>
        </View>

        {/* AI Signal CTA */}
        <View style={styles.aiBox}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Ionicons name="sparkles" color={theme.colors.primary} size={18} />
            <Text style={styles.aiTitle}>Signal IA — Claude Sonnet 4.5</Text>
          </View>
          <Text style={styles.aiSub}>
            Demande à l&apos;IA si c&apos;est le bon moment pour acheter ou vendre {symbolToBase(symbol)}.
          </Text>
          <TouchableOpacity
            style={[styles.aiCta, loadingSig && { opacity: 0.7 }]}
            onPress={generate}
            disabled={loadingSig}
            testID="coin-generate-signal"
          >
            {loadingSig ? <ActivityIndicator color="#000" /> : (
              <>
                <Ionicons name="flash" size={16} color="#000" />
                <Text style={styles.aiCtaText}>Analyser maintenant</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {signal && (
          <View
            testID="coin-signal-result"
            style={[styles.signalCard, { borderColor: colorFor(signal.action), shadowColor: colorFor(signal.action) }]}
          >
            <View style={styles.signalHead}>
              <Text style={styles.signalSym}>Recommandation</Text>
              <View style={[styles.actionBig, { backgroundColor: colorFor(signal.action) }]}>
                <Text style={styles.actionBigText}>{signal.action}</Text>
              </View>
            </View>
            <View style={styles.confRow}>
              <Text style={styles.confLabel}>Confiance</Text>
              <Text style={[styles.confValue, { color: colorFor(signal.action) }]}>{signal.confidence}%</Text>
            </View>
            <View style={styles.barTrack}>
              <View style={[styles.barFill, { width: `${signal.confidence}%`, backgroundColor: colorFor(signal.action) }]} />
            </View>
            <View style={styles.gridRow}>
              <View style={styles.metric}>
                <Text style={styles.metricLabel}>ENTRÉE</Text>
                <Text style={styles.metricValue}>{signal.entry ? `$${fmtPrice(signal.entry)}` : "—"}</Text>
              </View>
              <View style={styles.metric}>
                <Text style={styles.metricLabel}>OBJECTIF</Text>
                <Text style={[styles.metricValue, { color: theme.colors.buy }]}>
                  {signal.target ? `$${fmtPrice(signal.target)}` : "—"}
                </Text>
              </View>
              <View style={styles.metric}>
                <Text style={styles.metricLabel}>STOP-LOSS</Text>
                <Text style={[styles.metricValue, { color: theme.colors.sell }]}>
                  {signal.stop_loss ? `$${fmtPrice(signal.stop_loss)}` : "—"}
                </Text>
              </View>
            </View>
            <Text style={styles.reasonLabel}>POURQUOI</Text>
            <Text style={styles.reason}>{signal.reasoning}</Text>
          </View>
        )}

        <View style={{ height: 30 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  iconBtn: {
    width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  headSym: { color: "#fff", fontWeight: "900", fontSize: 18 },
  headPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },

  priceBlock: { alignItems: "center", marginTop: 22 },
  price: { color: "#fff", fontSize: 38, fontWeight: "900", letterSpacing: -1 },
  pnlPill: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, marginTop: 8 },
  pnlText: { fontWeight: "800", fontSize: 13 },

  statsRow: { flexDirection: "row", gap: 8, marginTop: 22 },
  statBox: {
    flex: 1, padding: 12, borderRadius: 14,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  statL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  statV: { color: "#fff", fontSize: 13, fontWeight: "800", marginTop: 4 },

  chartCard: {
    marginTop: 22, padding: 16, borderRadius: 22,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  intervals: { flexDirection: "row", gap: 6, justifyContent: "center", flexWrap: "wrap" },
  intChip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 999, backgroundColor: theme.colors.surfaceAlt },
  intChipActive: { backgroundColor: theme.colors.primary },
  intChipText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 12 },
  intChipTextActive: { color: "#000" },

  aiBox: {
    marginTop: 18, padding: 18, borderRadius: 22,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  aiTitle: { color: "#fff", fontWeight: "900", fontSize: 15 },
  aiSub: { color: theme.colors.textSecondary, fontSize: 13, marginTop: 8, lineHeight: 19 },
  aiCta: {
    marginTop: 14, paddingVertical: 14, borderRadius: 999, alignItems: "center", flexDirection: "row", justifyContent: "center", gap: 8,
    backgroundColor: theme.colors.primary,
    shadowColor: theme.colors.primary, shadowOpacity: 0.4, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
  },
  aiCtaText: { color: "#000", fontWeight: "900", fontSize: 14 },

  signalCard: {
    marginTop: 18, padding: 20, borderRadius: 22,
    backgroundColor: theme.colors.surface, borderWidth: 1.5,
    shadowOpacity: 0.18, shadowRadius: 20, shadowOffset: { width: 0, height: 0 },
  },
  signalHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  signalSym: { color: "#fff", fontWeight: "800", fontSize: 14 },
  actionBig: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12 },
  actionBigText: { color: "#000", fontWeight: "900", fontSize: 14, letterSpacing: 1 },
  confRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 16 },
  confLabel: { color: theme.colors.textSecondary, fontSize: 12, fontWeight: "700" },
  confValue: { fontSize: 22, fontWeight: "900" },
  barTrack: { height: 6, backgroundColor: theme.colors.surfaceAlt, borderRadius: 999, overflow: "hidden", marginTop: 6 },
  barFill: { height: 6, borderRadius: 999 },
  gridRow: { flexDirection: "row", gap: 8, marginTop: 18 },
  metric: { flex: 1, padding: 12, borderRadius: 14, backgroundColor: theme.colors.surfaceAlt },
  metricLabel: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  metricValue: { color: "#fff", fontWeight: "800", fontSize: 13, marginTop: 4 },
  reasonLabel: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginTop: 16 },
  reason: { color: "#fff", fontSize: 14, lineHeight: 21, marginTop: 6 },
});
