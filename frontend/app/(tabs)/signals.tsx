import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { theme, fmtPrice, symbolToBase } from "../../src/theme";
import { api } from "../../src/lib/api";

const QUICK_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"];
const INTERVALS: { v: string; l: string }[] = [
  { v: "15m", l: "15m" },
  { v: "1h", l: "1h" },
  { v: "4h", l: "4h" },
  { v: "1d", l: "1J" },
];

export default function Signals() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("1h");
  const [loading, setLoading] = useState(false);
  const [signal, setSignal] = useState<any | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [customSymbol, setCustomSymbol] = useState("");

  const loadHistory = useCallback(async () => {
    try {
      const h = await api.recentSignals();
      setHistory(h);
    } catch {}
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const generate = async () => {
    setLoading(true);
    setSignal(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const s = await api.signal(symbol, interval);
      setSignal(s);
      setHistory([s, ...history].slice(0, 20));
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Erreur", e.message || "Impossible de générer le signal");
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadHistory();
    setRefreshing(false);
  };

  const colorFor = (action: string) => {
    if (action === "BUY") return theme.colors.buy;
    if (action === "SELL") return theme.colors.sell;
    return theme.colors.hold;
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="signals-screen">
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.title}>Signaux IA</Text>
          <Text style={styles.subtitle}>Acheter / vendre — analyse Claude Sonnet 4.5 en temps réel.</Text>

          {/* Symbol picker */}
          <Text style={styles.label}>PAIRE</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            {QUICK_SYMBOLS.map((s) => (
              <TouchableOpacity
                key={s}
                onPress={() => setSymbol(s)}
                style={[styles.chip, symbol === s && styles.chipActive]}
                testID={`signal-symbol-${s}`}
              >
                <Text style={[styles.chipText, symbol === s && styles.chipTextActive]}>{symbolToBase(s)}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <View style={styles.customWrap}>
            <TextInput
              value={customSymbol}
              onChangeText={setCustomSymbol}
              placeholder="Autre paire ex: ARBUSDT"
              placeholderTextColor={theme.colors.textMuted}
              autoCapitalize="characters"
              style={styles.input}
              testID="signal-custom-input"
            />
            <TouchableOpacity
              onPress={() => {
                if (customSymbol.trim()) setSymbol(customSymbol.trim().toUpperCase());
              }}
              style={styles.miniBtn}
              testID="signal-custom-set"
            >
              <Text style={styles.miniBtnText}>Choisir</Text>
            </TouchableOpacity>
          </View>

          {/* Interval */}
          <Text style={styles.label}>INTERVALLE</Text>
          <View style={styles.intervals}>
            {INTERVALS.map((i) => (
              <TouchableOpacity
                key={i.v}
                onPress={() => setInterval(i.v)}
                style={[styles.chip, interval === i.v && styles.chipActive]}
                testID={`signal-interval-${i.v}`}
              >
                <Text style={[styles.chipText, interval === i.v && styles.chipTextActive]}>{i.l}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Selected symbol display */}
          <View style={styles.selected}>
            <Text style={styles.selectedSym}>{symbol}</Text>
            <Text style={styles.selectedInt}>{interval}</Text>
          </View>

          <TouchableOpacity
            style={[styles.cta, loading && { opacity: 0.7 }]}
            disabled={loading}
            onPress={generate}
            testID="signal-generate-btn"
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color="#000" />
            ) : (
              <>
                <Ionicons name="sparkles" size={18} color="#000" />
                <Text style={styles.ctaText}>Lancer l&apos;analyse IA</Text>
              </>
            )}
          </TouchableOpacity>

          {/* Signal Result */}
          {signal && (
            <View
              testID="signal-result"
              style={[
                styles.signalCard,
                { borderColor: colorFor(signal.action), shadowColor: colorFor(signal.action) },
              ]}
            >
              <View style={styles.signalHead}>
                <View>
                  <Text style={styles.signalSym}>{signal.symbol} · {signal.interval}</Text>
                  <Text style={styles.signalTime}>
                    {new Date(signal.generated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                  </Text>
                </View>
                <View style={[styles.actionBig, { backgroundColor: colorFor(signal.action) }]}>
                  <Text style={styles.actionBigText}>{signal.action}</Text>
                </View>
              </View>

              <View style={styles.confRow}>
                <Text style={styles.confLabel}>Confiance</Text>
                <Text style={[styles.confValue, { color: colorFor(signal.action) }]}>{signal.confidence}%</Text>
              </View>
              <View style={styles.barTrack}>
                <View
                  style={[
                    styles.barFill,
                    { width: `${signal.confidence}%`, backgroundColor: colorFor(signal.action) },
                  ]}
                />
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

              <View style={styles.timeframe}>
                <Ionicons name="time-outline" color={theme.colors.textSecondary} size={14} />
                <Text style={styles.timeframeText}>Horizon: {signal.timeframe}</Text>
              </View>

              <Text style={styles.reasonLabel}>POURQUOI</Text>
              <Text style={styles.reason}>{signal.reasoning}</Text>

              <View style={styles.indicatorsBox}>
                <Text style={styles.indHead}>Indicateurs</Text>
                <View style={styles.indGrid}>
                  {signal.indicators?.rsi14 !== undefined && (
                    <Text style={styles.ind}>RSI(14): <Text style={styles.indV}>{signal.indicators.rsi14}</Text></Text>
                  )}
                  {signal.indicators?.sma20 !== undefined && (
                    <Text style={styles.ind}>SMA20: <Text style={styles.indV}>{fmtPrice(signal.indicators.sma20)}</Text></Text>
                  )}
                  {signal.indicators?.sma50 !== undefined && (
                    <Text style={styles.ind}>SMA50: <Text style={styles.indV}>{fmtPrice(signal.indicators.sma50)}</Text></Text>
                  )}
                  {signal.indicators?.ema12 !== undefined && (
                    <Text style={styles.ind}>EMA12: <Text style={styles.indV}>{fmtPrice(signal.indicators.ema12)}</Text></Text>
                  )}
                </View>
              </View>
            </View>
          )}

          {/* History */}
          {history.length > 0 && (
            <>
              <Text style={[styles.sectionTitle, { marginTop: 28 }]}>Historique</Text>
              {history.slice(0, 6).map((h: any, i: number) => (
                <View key={i} style={styles.histRow}>
                  <View style={[styles.histPill, { backgroundColor: colorFor(h.action) }]}>
                    <Text style={styles.histPillText}>{h.action}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.histSym}>{h.symbol} · {h.interval}</Text>
                    <Text style={styles.histReason} numberOfLines={2}>{h.reasoning}</Text>
                  </View>
                  <Text style={styles.histConf}>{h.confidence}%</Text>
                </View>
              ))}
            </>
          )}

          <View style={{ height: 30 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  title: { color: "#fff", fontSize: 28, fontWeight: "900", letterSpacing: -0.8 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 13, marginTop: 6, marginBottom: 22 },
  label: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginTop: 16, marginBottom: 10 },

  chip: {
    paddingHorizontal: 14, paddingVertical: 9,
    borderRadius: 999,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  chipActive: { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
  chipText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 13 },
  chipTextActive: { color: "#000" },

  customWrap: { flexDirection: "row", gap: 8, marginTop: 12 },
  input: {
    flex: 1, backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
    borderRadius: 14, paddingHorizontal: 14, paddingVertical: 11, color: "#fff", fontSize: 14,
  },
  miniBtn: { paddingHorizontal: 16, justifyContent: "center", borderRadius: 14, backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1 },
  miniBtnText: { color: "#fff", fontWeight: "700", fontSize: 13 },

  intervals: { flexDirection: "row", gap: 8 },

  selected: {
    marginTop: 22,
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 18, paddingVertical: 14,
    backgroundColor: theme.colors.surface,
    borderRadius: 16,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  selectedSym: { color: "#fff", fontSize: 18, fontWeight: "900" },
  selectedInt: { color: theme.colors.primary, fontWeight: "800", fontSize: 13 },

  cta: {
    marginTop: 14,
    backgroundColor: theme.colors.primary,
    borderRadius: 999,
    paddingVertical: 16,
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "center",
    gap: 8,
    shadowColor: theme.colors.primary,
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
  },
  ctaText: { color: "#000", fontWeight: "900", fontSize: 15 },

  signalCard: {
    marginTop: 22,
    padding: 20,
    backgroundColor: theme.colors.surface,
    borderRadius: 22,
    borderWidth: 1.5,
    shadowOpacity: 0.18,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 0 },
  },
  signalHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  signalSym: { color: "#fff", fontWeight: "800", fontSize: 16 },
  signalTime: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  actionBig: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 12 },
  actionBigText: { color: "#000", fontWeight: "900", fontSize: 14, letterSpacing: 1 },

  confRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", marginTop: 18 },
  confLabel: { color: theme.colors.textSecondary, fontSize: 12, fontWeight: "700", letterSpacing: 1 },
  confValue: { fontSize: 22, fontWeight: "900" },
  barTrack: { height: 6, backgroundColor: theme.colors.surfaceAlt, borderRadius: 999, overflow: "hidden", marginTop: 6 },
  barFill: { height: 6, borderRadius: 999 },

  gridRow: { flexDirection: "row", gap: 8, marginTop: 18 },
  metric: { flex: 1, padding: 12, borderRadius: 14, backgroundColor: theme.colors.surfaceAlt },
  metricLabel: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  metricValue: { color: "#fff", fontWeight: "800", fontSize: 14, marginTop: 4 },

  timeframe: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 14 },
  timeframeText: { color: theme.colors.textSecondary, fontSize: 12 },

  reasonLabel: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginTop: 16 },
  reason: { color: "#fff", fontSize: 14, lineHeight: 21, marginTop: 6 },

  indicatorsBox: { marginTop: 18, padding: 14, borderRadius: 14, backgroundColor: theme.colors.surfaceAlt },
  indHead: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.2 },
  indGrid: { flexDirection: "row", flexWrap: "wrap", gap: 14, marginTop: 8 },
  ind: { color: theme.colors.textSecondary, fontSize: 12 },
  indV: { color: "#fff", fontWeight: "800" },

  sectionTitle: { color: "#fff", fontSize: 17, fontWeight: "900", marginBottom: 12 },
  histRow: {
    flexDirection: "row", alignItems: "center", gap: 10,
    padding: 12, borderRadius: 14,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
    marginBottom: 8,
  },
  histPill: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  histPillText: { color: "#000", fontWeight: "900", fontSize: 11 },
  histSym: { color: "#fff", fontWeight: "800", fontSize: 13 },
  histReason: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },
  histConf: { color: "#fff", fontWeight: "800", fontSize: 13 },
});
