import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { theme, fmtPrice, symbolToBase } from "../src/theme";
import { api } from "../src/lib/api";

const HORIZONS = [
  { v: "24h", l: "24h" },
  { v: "3d", l: "3 jours" },
  { v: "7d", l: "7 jours" },
];

const QUICK_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"];

export default function Predict() {
  const router = useRouter();
  const [horizon, setHorizon] = useState("24h");
  const [tab, setTab] = useState<"top" | "single">("top");
  const [topData, setTopData] = useState<any[]>([]);
  const [loadingTop, setLoadingTop] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const [single, setSingle] = useState<any | null>(null);
  const [loadingSingle, setLoadingSingle] = useState(false);

  const loadTop = useCallback(async () => {
    setLoadingTop(true);
    try {
      const r = await api.predictTop(horizon);
      setTopData(r);
    } catch (e: any) {
      Alert.alert("Erreur", e.message || "Impossible de charger les prédictions");
    } finally {
      setLoadingTop(false);
    }
  }, [horizon]);

  useEffect(() => {
    if (tab === "top") loadTop();
  }, [tab, horizon, loadTop]);

  const generateSingle = async () => {
    setLoadingSingle(true);
    setSingle(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const r = await api.predict(selectedSymbol, horizon);
      setSingle(r);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    } finally {
      setLoadingSingle(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="predict-screen">
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          tab === "top" ? (
            <RefreshControl refreshing={loadingTop} onRefresh={loadTop} tintColor={theme.colors.primary} />
          ) : undefined
        }
      >
        <View style={styles.head}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="predict-back-btn">
            <Ionicons name="chevron-back" size={22} color="#fff" />
          </TouchableOpacity>
          <Text style={styles.headTitle}>Prédictions IA</Text>
          <View style={styles.iconBtn} />
        </View>

        <View style={styles.aiPill}>
          <Ionicons name="sparkles" size={12} color={theme.colors.primary} />
          <Text style={styles.aiPillText}>CLAUDE SONNET 4.5</Text>
        </View>

        <Text style={styles.subtitle}>
          L&apos;IA analyse RSI, volume, volatilité et tendance pour prédire les prix futurs avec niveau de confiance.
        </Text>

        {/* Horizon */}
        <Text style={styles.label}>HORIZON</Text>
        <View style={styles.chips}>
          {HORIZONS.map((h) => (
            <TouchableOpacity
              key={h.v}
              onPress={() => setHorizon(h.v)}
              style={[styles.chip, horizon === h.v && styles.chipActive]}
              testID={`predict-horizon-${h.v}`}
            >
              <Text style={[styles.chipText, horizon === h.v && styles.chipTextActive]}>{h.l}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Tabs */}
        <View style={styles.tabs}>
          <TouchableOpacity
            style={[styles.tab, tab === "top" && styles.tabActive]}
            onPress={() => setTab("top")}
            testID="predict-tab-top"
          >
            <Ionicons name="trophy" size={14} color={tab === "top" ? "#000" : theme.colors.textSecondary} />
            <Text style={[styles.tabText, tab === "top" && styles.tabTextActive]}>Top opportunités</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, tab === "single" && styles.tabActive]}
            onPress={() => setTab("single")}
            testID="predict-tab-single"
          >
            <Ionicons name="search" size={14} color={tab === "single" ? "#000" : theme.colors.textSecondary} />
            <Text style={[styles.tabText, tab === "single" && styles.tabTextActive]}>Analyse ciblée</Text>
          </TouchableOpacity>
        </View>

        {tab === "top" ? (
          <TopPredictionsView data={topData} loading={loadingTop} />
        ) : (
          <SinglePredictionView
            selectedSymbol={selectedSymbol}
            setSelectedSymbol={setSelectedSymbol}
            single={single}
            loading={loadingSingle}
            onGenerate={generateSingle}
          />
        )}

        <Text style={styles.disclaimer}>
          🛈 Les prédictions IA ne sont pas des conseils financiers. Crois en ce que tu comprends, pas en ce qu&apos;on te promet.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function TopPredictionsView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading && data.length === 0) {
    return (
      <View style={{ padding: 40, alignItems: "center" }}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
        <Text style={{ color: theme.colors.textSecondary, marginTop: 12 }}>
          Claude analyse 10 cryptos...
        </Text>
        <Text style={{ color: theme.colors.textMuted, marginTop: 4, fontSize: 11 }}>
          (peut prendre 20-30 secondes)
        </Text>
      </View>
    );
  }
  if (data.length === 0) {
    return (
      <View style={{ padding: 24, alignItems: "center" }}>
        <Text style={{ color: theme.colors.textSecondary }}>Aucune prédiction disponible</Text>
      </View>
    );
  }
  return (
    <View style={{ gap: 12 }}>
      {data.map((p, i) => (
        <PredictionCard key={p.symbol} data={p} rank={i + 1} compact />
      ))}
    </View>
  );
}

function SinglePredictionView({ selectedSymbol, setSelectedSymbol, single, loading, onGenerate }: any) {
  return (
    <View>
      <Text style={styles.label}>PAIRE</Text>
      <View style={styles.chips}>
        {QUICK_SYMBOLS.map((s) => (
          <TouchableOpacity
            key={s}
            onPress={() => setSelectedSymbol(s)}
            style={[styles.chip, selectedSymbol === s && styles.chipActive]}
            testID={`predict-sym-${s}`}
          >
            <Text style={[styles.chipText, selectedSymbol === s && styles.chipTextActive]}>
              {symbolToBase(s)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.cta, loading && { opacity: 0.7 }]}
        onPress={onGenerate}
        disabled={loading}
        testID="predict-generate-btn"
      >
        {loading ? (
          <ActivityIndicator color="#000" />
        ) : (
          <>
            <Ionicons name="rocket" size={16} color="#000" />
            <Text style={styles.ctaText}>Prédire {symbolToBase(selectedSymbol)}</Text>
          </>
        )}
      </TouchableOpacity>

      {single && <PredictionCard data={single} />}
    </View>
  );
}

function PredictionCard({ data, rank, compact }: { data: any; rank?: number; compact?: boolean }) {
  const dirColor =
    data.direction === "HAUSSE" ? theme.colors.buy : data.direction === "BAISSE" ? theme.colors.sell : theme.colors.hold;
  const dirIcon =
    data.direction === "HAUSSE" ? "trending-up" : data.direction === "BAISSE" ? "trending-down" : "remove";
  const medianChange = ((data.target_median - data.current_price) / data.current_price) * 100;
  const upPct = ((data.target_high - data.current_price) / data.current_price) * 100;
  const downPct = ((data.target_low - data.current_price) / data.current_price) * 100;
  const actionColor =
    data.action === "BUY" ? theme.colors.buy : data.action === "SELL" ? theme.colors.sell : theme.colors.primary;

  return (
    <View
      style={[
        styles.predCard,
        { borderColor: dirColor + "55", shadowColor: dirColor },
        rank === 1 && { borderColor: theme.colors.primary, shadowColor: theme.colors.primary },
      ]}
      testID={`prediction-${data.symbol}`}
    >
      <View style={styles.predHead}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flex: 1 }}>
          {rank !== undefined && (
            <View style={[styles.rankPill, rank === 1 && { backgroundColor: theme.colors.primary }]}>
              <Text style={[styles.rankText, rank === 1 && { color: "#000" }]}>#{rank}</Text>
            </View>
          )}
          <View>
            <Text style={styles.predSym}>{symbolToBase(data.symbol)}</Text>
            <Text style={styles.predPair}>${fmtPrice(data.current_price)} · {data.horizon}</Text>
          </View>
        </View>
        <View style={[styles.dirBadge, { backgroundColor: dirColor }]}>
          <Ionicons name={dirIcon as any} size={14} color="#000" />
          <Text style={styles.dirText}>{data.direction}</Text>
        </View>
      </View>

      {/* Confidence bar */}
      <View style={{ marginTop: 14 }}>
        <View style={styles.confRow}>
          <Text style={styles.smallLabel}>Confiance IA</Text>
          <Text style={[styles.confVal, { color: dirColor }]}>{data.confidence}%</Text>
        </View>
        <View style={styles.bar}>
          <View style={[styles.barFill, { width: `${data.confidence}%`, backgroundColor: dirColor }]} />
        </View>
      </View>

      {/* Price targets visual */}
      <View style={styles.targets}>
        <View style={styles.targetCell}>
          <Text style={[styles.targetL, { color: theme.colors.sell }]}>BAS</Text>
          <Text style={styles.targetV}>${fmtPrice(data.target_low)}</Text>
          <Text style={[styles.targetPct, { color: theme.colors.sell }]}>{downPct.toFixed(1)}%</Text>
        </View>
        <View style={[styles.targetCell, { backgroundColor: theme.colors.surfaceAlt }]}>
          <Text style={[styles.targetL, { color: theme.colors.primary }]}>MÉDIAN</Text>
          <Text style={[styles.targetV, { fontSize: 16 }]}>${fmtPrice(data.target_median)}</Text>
          <Text style={[styles.targetPct, { color: medianChange >= 0 ? theme.colors.buy : theme.colors.sell }]}>
            {medianChange >= 0 ? "+" : ""}
            {medianChange.toFixed(1)}%
          </Text>
        </View>
        <View style={styles.targetCell}>
          <Text style={[styles.targetL, { color: theme.colors.buy }]}>HAUT</Text>
          <Text style={styles.targetV}>${fmtPrice(data.target_high)}</Text>
          <Text style={[styles.targetPct, { color: theme.colors.buy }]}>+{upPct.toFixed(1)}%</Text>
        </View>
      </View>

      {/* Action */}
      <View style={[styles.actionBox, { backgroundColor: actionColor + "22", borderColor: actionColor }]}>
        <Ionicons
          name={data.action === "BUY" ? "arrow-up-circle" : data.action === "SELL" ? "arrow-down-circle" : "pause-circle"}
          size={18}
          color={actionColor}
        />
        <Text style={[styles.actionText, { color: actionColor }]}>
          Action recommandée : {data.action === "BUY" ? "ACHETER" : data.action === "SELL" ? "VENDRE" : "ATTENDRE"}
        </Text>
      </View>

      {/* Key factors */}
      {data.key_factors?.length > 0 && (
        <View style={{ marginTop: 14 }}>
          <Text style={styles.smallLabel}>FACTEURS CLÉS</Text>
          <View style={{ gap: 6, marginTop: 8 }}>
            {data.key_factors.map((f: string, i: number) => (
              <View key={i} style={styles.factor}>
                <View style={[styles.factorDot, { backgroundColor: dirColor }]} />
                <Text style={styles.factorText}>{f}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Reasoning */}
      {!compact && data.reasoning && (
        <>
          <Text style={[styles.smallLabel, { marginTop: 14 }]}>ANALYSE</Text>
          <Text style={styles.reasoning}>{data.reasoning}</Text>
        </>
      )}

      {/* Indicators footer */}
      <View style={styles.indFooter}>
        <Text style={styles.indMuted}>
          RSI {data.indicators?.rsi14?.toFixed(0) ?? "—"} ·{" "}
          Vol {data.indicators?.volatility_pct?.toFixed(2) ?? "—"}% ·{" "}
          24h {data.indicators?.change_24h_pct >= 0 ? "+" : ""}
          {data.indicators?.change_24h_pct?.toFixed(1) ?? "—"}%
        </Text>
        {data.cached && (
          <Text style={styles.cacheTag}>📦 caché ({data.cached_age_min}min)</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  iconBtn: {
    width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  headTitle: { color: "#fff", fontSize: 20, fontWeight: "900" },
  aiPill: {
    flexDirection: "row", alignItems: "center", gap: 5, alignSelf: "flex-start",
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999,
    backgroundColor: "rgba(243,186,47,0.12)", borderColor: "rgba(243,186,47,0.4)", borderWidth: 1,
    marginTop: 16,
  },
  aiPillText: { color: theme.colors.primary, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 12, marginBottom: 18 },

  label: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginBottom: 10, marginTop: 8 },
  chips: { flexDirection: "row", gap: 8, flexWrap: "wrap", marginBottom: 16 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 999,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  chipActive: { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
  chipText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 13 },
  chipTextActive: { color: "#000" },

  tabs: { flexDirection: "row", gap: 8, marginBottom: 18 },
  tab: {
    flex: 1, paddingVertical: 12, borderRadius: 14,
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  tabActive: { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
  tabText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 13 },
  tabTextActive: { color: "#000" },

  cta: {
    backgroundColor: theme.colors.primary, borderRadius: 999, paddingVertical: 14,
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    marginBottom: 18,
  },
  ctaText: { color: "#000", fontWeight: "900", fontSize: 14 },

  predCard: {
    padding: 18, borderRadius: 22,
    backgroundColor: theme.colors.surface, borderWidth: 1.5,
    shadowOpacity: 0.15, shadowRadius: 14, shadowOffset: { width: 0, height: 0 },
  },
  predHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  rankPill: {
    width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surfaceAlt,
  },
  rankText: { color: "#fff", fontWeight: "900", fontSize: 11 },
  predSym: { color: "#fff", fontWeight: "900", fontSize: 16 },
  predPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  dirBadge: { flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  dirText: { color: "#000", fontWeight: "900", fontSize: 11, letterSpacing: 0.8 },

  confRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  smallLabel: { color: theme.colors.textSecondary, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  confVal: { fontSize: 18, fontWeight: "900" },
  bar: { height: 5, backgroundColor: theme.colors.surfaceAlt, borderRadius: 999, marginTop: 4, overflow: "hidden" },
  barFill: { height: 5, borderRadius: 999 },

  targets: { flexDirection: "row", gap: 6, marginTop: 16 },
  targetCell: {
    flex: 1, padding: 10, borderRadius: 12, alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.03)",
  },
  targetL: { fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  targetV: { color: "#fff", fontSize: 13, fontWeight: "800", marginTop: 4 },
  targetPct: { fontSize: 10, fontWeight: "700", marginTop: 2 },

  actionBox: {
    marginTop: 14, paddingVertical: 10, paddingHorizontal: 14, borderRadius: 12,
    flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1,
  },
  actionText: { fontWeight: "900", fontSize: 13 },

  factor: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  factorDot: { width: 6, height: 6, borderRadius: 3, marginTop: 6 },
  factorText: { color: theme.colors.textSecondary, fontSize: 12, lineHeight: 18, flex: 1 },

  reasoning: { color: "#fff", fontSize: 13, lineHeight: 20, marginTop: 6 },

  indFooter: {
    marginTop: 14, paddingTop: 10,
    borderTopColor: theme.colors.border, borderTopWidth: 1,
    flexDirection: "row", justifyContent: "space-between",
  },
  indMuted: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "600" },
  cacheTag: { color: theme.colors.textMuted, fontSize: 10 },

  disclaimer: { color: theme.colors.textMuted, fontSize: 11, textAlign: "center", marginTop: 22, lineHeight: 16 },
});
