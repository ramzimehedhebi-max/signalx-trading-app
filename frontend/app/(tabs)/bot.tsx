import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  Switch,
  Alert,
  Platform,
  KeyboardAvoidingView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import { theme, fmtPrice, fmtUsd, symbolToBase } from "../../src/theme";
import { api } from "../../src/lib/api";

const ALL_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT"];

export default function Bot() {
  const router = useRouter();
  const { t } = useTranslation();
  const [cfg, setCfg] = useState<any | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [savingToggle, setSavingToggle] = useState(false);
  const [scanning, setScanning] = useState(false);
  const pollRef = useRef<any>(null);

  const load = useCallback(async () => {
    try {
      const [c, s, p, t] = await Promise.all([
        api.botConfig(),
        api.botStats(),
        api.botPositions(),
        api.botTrades(),
      ]);
      setCfg(c);
      setStats(s);
      setPositions(p);
      setTrades(t);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await load();
      setLoading(false);
    })();
    pollRef.current = setInterval(load, 15000);
    return () => clearInterval(pollRef.current);
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const toggleBot = async (val: boolean) => {
    setSavingToggle(true);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const updated = await api.botUpdateConfig({ enabled: val });
      setCfg(updated);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Erreur", e.message || "Impossible de modifier le bot");
    } finally {
      setSavingToggle(false);
    }
  };

  const confirmLive = async (turnOn: boolean) => {
    if (!turnOn) {
      // Quick disable
      try {
        const updated = await api.botUpdateConfig({ live_mode: false });
        setCfg(updated);
      } catch (e: any) {
        Alert.alert("Erreur", e.message);
      }
      return;
    }
    // Check Binance connection first
    let connected = false;
    try {
      const s = await api.binanceStatus();
      connected = !!s.connected;
    } catch {}
    if (!connected) {
      Alert.alert(
        "Binance non connecté",
        "Tu dois d'abord connecter ton compte Binance avant d'activer le mode Live.",
        [
          { text: "Plus tard", style: "cancel" },
          { text: "Connecter maintenant", onPress: () => router.push("/binance-connect") },
        ]
      );
      return;
    }
    const doEnable = async () => {
      try {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        const updated = await api.botUpdateConfig({ live_mode: true });
        setCfg(updated);
        Alert.alert(
          "⚡ Mode LIVE activé",
          `Le bot va maintenant exécuter de VRAIS ordres sur Binance.\n\nLimite par trade : $${updated.live_max_position_usdt || 50}.`
        );
      } catch (e: any) {
        Alert.alert("Erreur", e.message || "Impossible d'activer le mode Live");
      }
    };
    if (Platform.OS === "web") {
      const ok =
        typeof window !== "undefined" &&
        window.confirm(
          "⚠️ ATTENTION : Mode LIVE\n\nLe bot va passer en trading RÉEL avec de l'argent VRAI sur Binance.\n\nConfirmer l'activation ?"
        );
      if (ok) doEnable();
      return;
    }
    Alert.alert(
      "⚠️ Activer le mode LIVE ?",
      "Le bot va passer en trading RÉEL avec de l'argent VRAI sur Binance. Tu peux désactiver à tout moment.",
      [
        { text: "Annuler", style: "cancel" },
        { text: "Activer Live", style: "destructive", onPress: doEnable },
      ]
    );
  };

  const toggleKillSwitch = async (val: boolean) => {
    try {
      const updated = await api.botUpdateConfig({ live_killswitch: val });
      setCfg(updated);
      if (val) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    }
  };

  const doReset = async () => {
    try {
      await api.botReset();
      await load();
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    }
  };

  const onReset = () => {
    if (Platform.OS === "web") {
      const ok = typeof window !== "undefined" && window.confirm("Réinitialiser le bot ? Toutes les positions et l'historique seront supprimés.");
      if (ok) doReset();
      return;
    }
    Alert.alert("Réinitialiser le bot", "Toutes les positions et l'historique seront supprimés.", [
      { text: "Annuler" },
      { text: "Réinitialiser", style: "destructive", onPress: doReset },
    ]);
  };

  const forceScan = async () => {
    setScanning(true);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      await api.botRunNow();
      await new Promise((r) => setTimeout(r, 1500));
      await load();
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    } finally {
      setScanning(false);
    }
  };

  if (loading || !cfg || !stats) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

  const totalPnl = stats.total_pnl || 0;
  const totalPnlPct = stats.capital_usdt > 0 ? (totalPnl / stats.capital_usdt) * 100 : 0;
  const isProfit = totalPnl >= 0;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="bot-screen">
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />
        }
      >
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.title}>{t("bot.title")}</Text>
            <Text style={styles.subtitle}>{cfg.live_mode ? t("bot.mode.live") : t("bot.mode.paper")}</Text>
          </View>
          <TouchableOpacity onPress={() => setSettingsOpen(true)} style={styles.iconBtn} testID="bot-settings-btn">
            <Ionicons name="options-outline" size={20} color="#fff" />
          </TouchableOpacity>
        </View>

        {/* Status Card */}
        <View style={[styles.statusCard, cfg.enabled && styles.statusCardActive]}>
          <View style={styles.statusHead}>
            <View style={styles.statusLeft}>
              <View style={[styles.dotPulse, { backgroundColor: cfg.enabled ? theme.colors.buy : theme.colors.textMuted }]} />
              <Text style={styles.statusLabel}>{cfg.enabled ? t("bot.active") : t("bot.inactive")}</Text>
            </View>
            <Switch
              value={cfg.enabled}
              onValueChange={toggleBot}
              disabled={savingToggle}
              trackColor={{ false: theme.colors.surfaceAlt, true: theme.colors.primary }}
              thumbColor={cfg.enabled ? "#000" : "#888"}
              testID="bot-enable-switch"
            />
          </View>

          <Text style={styles.balanceLabel}>{t("bot.stats.capital")} (USDT)</Text>
          <Text style={styles.balance}>{fmtUsd(stats.paper_balance_usdt)}</Text>

          <View style={styles.pnlRow}>
            <View style={[styles.pnlPill, { backgroundColor: isProfit ? "rgba(0,227,150,0.15)" : "rgba(255,69,96,0.15)" }]}>
              <Ionicons name={isProfit ? "trending-up" : "trending-down"} size={14} color={isProfit ? theme.colors.buy : theme.colors.sell} />
              <Text style={[styles.pnlText, { color: isProfit ? theme.colors.buy : theme.colors.sell }]}>
                {isProfit ? "+" : ""}{fmtUsd(totalPnl)} ({totalPnlPct.toFixed(2)}%)
              </Text>
            </View>
          </View>

          <View style={styles.kpiRow}>
            <View style={styles.kpi}>
              <Text style={styles.kpiL}>{t("bot.stats.positions")}</Text>
              <Text style={styles.kpiV}>{stats.open_positions_count} / {cfg.max_positions}</Text>
            </View>
            <View style={styles.kpi}>
              <Text style={styles.kpiL}>{t("bot.stats.trades")}</Text>
              <Text style={styles.kpiV}>{stats.trades_count}</Text>
            </View>
            <View style={styles.kpi}>
              <Text style={styles.kpiL}>WIN RATE</Text>
              <Text style={[styles.kpiV, { color: stats.win_rate_pct >= 50 ? theme.colors.buy : theme.colors.sell }]}>
                {stats.win_rate_pct.toFixed(0)}%
              </Text>
            </View>
          </View>
        </View>

        {/* Mode Paper / Live */}
        <View style={[styles.modeCard, cfg.live_mode && styles.modeCardLive]}>
          <View style={styles.modeHead}>
            <View style={{ flex: 1 }}>
              <View style={styles.modeBadgeRow}>
                <View style={[styles.modeBadge, cfg.live_mode ? styles.modeBadgeLive : styles.modeBadgePaper]}>
                  <Ionicons
                    name={cfg.live_mode ? "flash" : "document-text-outline"}
                    size={12}
                    color={cfg.live_mode ? theme.colors.danger : theme.colors.primary}
                  />
                  <Text style={[styles.modeBadgeText, { color: cfg.live_mode ? theme.colors.danger : theme.colors.primary }]}>
                    {cfg.live_mode ? "MODE LIVE — ARGENT RÉEL" : "MODE PAPER — SIMULATION"}
                  </Text>
                </View>
              </View>
              <Text style={styles.modeDesc}>
                {cfg.live_mode
                  ? `Le bot exécute de vrais ordres sur Binance. Limite: $${cfg.live_max_position_usdt || 50}/trade.`
                  : "Aucun ordre réel. Les performances utilisent un capital fictif."}
              </Text>
            </View>
            <Switch
              value={!!cfg.live_mode}
              onValueChange={confirmLive}
              trackColor={{ false: theme.colors.surfaceAlt, true: theme.colors.danger }}
              thumbColor={cfg.live_mode ? "#fff" : "#888"}
            />
          </View>

          {cfg.live_mode && (
            <View style={styles.killRow}>
              <Ionicons name="warning" size={16} color={cfg.live_killswitch ? theme.colors.danger : theme.colors.textSecondary} />
              <View style={{ flex: 1 }}>
                <Text style={styles.killTitle}>Kill-switch (pause des achats)</Text>
                <Text style={styles.killSub}>
                  {cfg.live_killswitch
                    ? "Aucun nouvel achat. Le bot ne fait QUE clôturer les positions ouvertes."
                    : "Désactive instantanément les nouveaux achats si besoin."}
                </Text>
              </View>
              <Switch
                value={!!cfg.live_killswitch}
                onValueChange={toggleKillSwitch}
                trackColor={{ false: theme.colors.surfaceAlt, true: theme.colors.danger }}
                thumbColor={cfg.live_killswitch ? "#fff" : "#888"}
              />
            </View>
          )}
        </View>

        {/* Strategy summary */}
        <View style={styles.stratCard}>
          <View style={styles.stratHead}>
            <Ionicons name="sparkles" size={14} color={theme.colors.primary} />
            <Text style={styles.stratTitle}>Stratégie hybride</Text>
          </View>
          <Text style={styles.stratText}>
            Le bot scanne {cfg.pairs?.length || 5} paires toutes les {cfg.interval_minutes} min.
            Indicateurs RSI + EMA détectent les opportunités, Claude Sonnet 4.5 valide les trades incertains.
            Stop-loss {cfg.stop_loss_pct}% · Take-profit {cfg.take_profit_pct}% · {cfg.position_size_pct}% capital/trade.
          </Text>
          <View style={styles.boostsRow}>
            {cfg.trailing_enabled && (
              <View style={styles.boost}>
                <Ionicons name="shield-checkmark" size={11} color={theme.colors.buy} />
                <Text style={styles.boostText}>Trailing SL +{cfg.trailing_trigger_pct}%</Text>
              </View>
            )}
            {cfg.compounding_enabled && (
              <View style={styles.boost}>
                <Ionicons name="trending-up" size={11} color={theme.colors.buy} />
                <Text style={styles.boostText}>Compounding</Text>
              </View>
            )}
            {cfg.ai_predictions_enabled && (
              <View style={styles.boost}>
                <Ionicons name="telescope" size={11} color={theme.colors.buy} />
                <Text style={styles.boostText}>IA Prédictive</Text>
              </View>
            )}
          </View>
        </View>

        {/* Open positions */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>Positions ouvertes</Text>
          <Text style={styles.muted}>{positions.length}</Text>
        </View>
        {positions.length === 0 ? (
          <View style={styles.emptyCard}>
            <Ionicons name="hourglass-outline" size={28} color={theme.colors.textMuted} />
            <Text style={styles.emptyT}>{cfg.enabled ? "Le bot scrute le marché..." : "Active le bot pour qu'il commence à trader"}</Text>
            <Text style={styles.emptyS}>Les positions s&apos;ouvriront automatiquement dès qu&apos;un signal fort apparaît.</Text>
          </View>
        ) : (
          <View style={{ gap: 10 }}>
            {positions.map((p) => (
              <View key={p.id} style={styles.posCard} testID={`bot-position-${p.symbol}`}>
                <View style={styles.posHead}>
                  <View style={styles.iconCircle}>
                    <Text style={styles.iconText}>{symbolToBase(p.symbol).slice(0, 2)}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                      <Text style={styles.posSym}>{symbolToBase(p.symbol)}</Text>
                      {p.trail_active && (
                        <View style={styles.trailPill}>
                          <Ionicons name="shield-checkmark" size={9} color={theme.colors.buy} />
                          <Text style={styles.trailPillText}>TRAIL</Text>
                        </View>
                      )}
                    </View>
                    <Text style={styles.posPair}>{p.symbol} · {p.quantity.toFixed(6)}</Text>
                  </View>
                  <View style={[styles.pnlMini, { backgroundColor: p.pnl >= 0 ? "rgba(0,227,150,0.15)" : "rgba(255,69,96,0.15)" }]}>
                    <Text style={[styles.pnlMiniText, { color: p.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                      {p.pnl >= 0 ? "+" : ""}{p.pnl_pct.toFixed(2)}%
                    </Text>
                  </View>
                </View>
                <View style={styles.posGrid}>
                  <View style={styles.posMetric}>
                    <Text style={styles.metricL}>ENTRÉE</Text>
                    <Text style={styles.metricV}>${fmtPrice(p.entry_price)}</Text>
                  </View>
                  <View style={styles.posMetric}>
                    <Text style={styles.metricL}>ACTUEL</Text>
                    <Text style={styles.metricV}>${fmtPrice(p.current_price)}</Text>
                  </View>
                  <View style={styles.posMetric}>
                    <Text style={styles.metricL}>TP / SL</Text>
                    <Text style={styles.metricV}>
                      <Text style={{ color: theme.colors.buy }}>${fmtPrice(p.take_profit)}</Text>
                    </Text>
                    <Text style={[styles.metricV, { color: theme.colors.sell, fontSize: 11 }]}>${fmtPrice(p.stop_loss)}</Text>
                  </View>
                </View>
                {p.entry_reason ? (
                  <Text style={styles.posReason} numberOfLines={2}>💡 {p.entry_reason}</Text>
                ) : null}
              </View>
            ))}
          </View>
        )}

        {/* History */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>Historique des trades</Text>
          <Text style={styles.muted}>{trades.length}</Text>
        </View>
        {trades.length === 0 ? (
          <Text style={styles.emptyHist}>Aucun trade clôturé pour le moment.</Text>
        ) : (
          <View style={{ gap: 8 }}>
            {trades.slice(0, 20).map((t) => (
              <View key={t.id} style={styles.histRow}>
                <View style={[styles.histPill, { backgroundColor: t.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                  <Ionicons name={t.pnl >= 0 ? "checkmark" : "close"} size={11} color="#000" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.histSym}>
                    {symbolToBase(t.symbol)}{" "}
                    <Text style={styles.histReason}>· {t.exit_reason === "take_profit" ? "TP" : t.exit_reason === "stop_loss" ? "SL" : t.exit_reason}</Text>
                  </Text>
                  <Text style={styles.histTime}>
                    {new Date(t.exit_time).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  </Text>
                </View>
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={[styles.histPnl, { color: t.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                    {t.pnl >= 0 ? "+" : ""}{fmtUsd(t.pnl)}
                  </Text>
                  <Text style={[styles.histPnlPct, { color: t.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                    {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}

        <TouchableOpacity onPress={onReset} style={styles.resetBtn} testID="bot-reset-btn">
          <Ionicons name="refresh" size={16} color={theme.colors.danger} />
          <Text style={styles.resetText}>Réinitialiser le bot</Text>
        </TouchableOpacity>

        <Text style={styles.disclaimer}>
          🛈 Mode Paper Trading — aucune transaction réelle n&apos;est exécutée. Les prix utilisés sont
          ceux du marché Binance en temps réel.
        </Text>
      </ScrollView>

      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} cfg={cfg} onUpdated={(c) => setCfg(c)} />
    </SafeAreaView>
  );
}

function SettingsSheet({ open, onClose, cfg, onUpdated }: any) {
  const [capital, setCapital] = useState(String(cfg.capital_usdt));
  const [posSize, setPosSize] = useState(String(cfg.position_size_pct));
  const [maxPos, setMaxPos] = useState(String(cfg.max_positions));
  const [sl, setSl] = useState(String(cfg.stop_loss_pct));
  const [tp, setTp] = useState(String(cfg.take_profit_pct));
  const [interval, setIntervalV] = useState(String(cfg.interval_minutes));
  const [pairs, setPairs] = useState<string[]>(cfg.pairs || []);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setCapital(String(cfg.capital_usdt));
      setPosSize(String(cfg.position_size_pct));
      setMaxPos(String(cfg.max_positions));
      setSl(String(cfg.stop_loss_pct));
      setTp(String(cfg.take_profit_pct));
      setIntervalV(String(cfg.interval_minutes));
      setPairs(cfg.pairs || []);
    }
  }, [open, cfg]);

  const togglePair = (p: string) => {
    setPairs((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  };

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.botUpdateConfig({
        capital_usdt: parseFloat(capital),
        position_size_pct: parseFloat(posSize),
        max_positions: parseInt(maxPos, 10),
        stop_loss_pct: parseFloat(sl),
        take_profit_pct: parseFloat(tp),
        interval_minutes: parseInt(interval, 10),
        pairs,
      });
      onUpdated(updated);
      onClose();
    } catch (e: any) {
      Alert.alert("Erreur", e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
        <TouchableOpacity style={styles.backdrop} onPress={onClose} activeOpacity={1} />
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <ScrollView showsVerticalScrollIndicator={false}>
            <Text style={styles.sheetTitle}>Configuration du bot</Text>

            <Text style={styles.lbl}>CAPITAL VIRTUEL (USDT)</Text>
            <TextInput value={capital} onChangeText={setCapital} keyboardType="decimal-pad" style={styles.input} testID="bot-capital-input" />

            <View style={styles.grid2}>
              <View style={{ flex: 1 }}>
                <Text style={styles.lbl}>TAILLE POSITION %</Text>
                <TextInput value={posSize} onChangeText={setPosSize} keyboardType="decimal-pad" style={styles.input} testID="bot-possize-input" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.lbl}>MAX POSITIONS</Text>
                <TextInput value={maxPos} onChangeText={setMaxPos} keyboardType="number-pad" style={styles.input} testID="bot-maxpos-input" />
              </View>
            </View>

            <View style={styles.grid2}>
              <View style={{ flex: 1 }}>
                <Text style={styles.lbl}>STOP-LOSS %</Text>
                <TextInput value={sl} onChangeText={setSl} keyboardType="decimal-pad" style={styles.input} testID="bot-sl-input" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.lbl}>TAKE-PROFIT %</Text>
                <TextInput value={tp} onChangeText={setTp} keyboardType="decimal-pad" style={styles.input} testID="bot-tp-input" />
              </View>
            </View>

            <Text style={styles.lbl}>INTERVALLE D&apos;ANALYSE (MIN)</Text>
            <TextInput value={interval} onChangeText={setIntervalV} keyboardType="number-pad" style={styles.input} testID="bot-interval-input" />

            <Text style={styles.lbl}>PAIRES À TRADER</Text>
            <View style={styles.pairs}>
              {ALL_PAIRS.map((p) => (
                <TouchableOpacity
                  key={p}
                  onPress={() => togglePair(p)}
                  style={[styles.pairChip, pairs.includes(p) && styles.pairChipActive]}
                  testID={`bot-pair-${p}`}
                >
                  <Text style={[styles.pairText, pairs.includes(p) && styles.pairTextActive]}>{symbolToBase(p)}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity onPress={save} disabled={saving} style={[styles.cta, saving && { opacity: 0.7 }]} testID="bot-save-btn">
              {saving ? <ActivityIndicator color="#000" /> : <Text style={styles.ctaText}>Enregistrer</Text>}
            </TouchableOpacity>
            <View style={{ height: 30 }} />
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
  title: { color: "#fff", fontSize: 28, fontWeight: "900", letterSpacing: -0.8 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 13, marginTop: 4 },
  iconBtn: {
    width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },

  statusCard: {
    padding: 22, borderRadius: 24,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  statusCardActive: {
    borderColor: theme.colors.primary,
    shadowColor: theme.colors.primary,
    shadowOpacity: 0.2,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  statusHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statusLeft: { flexDirection: "row", alignItems: "center", gap: 8 },
  dotPulse: { width: 8, height: 8, borderRadius: 4 },
  statusLabel: { color: "#fff", fontWeight: "900", fontSize: 12, letterSpacing: 1.5 },

  balanceLabel: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginTop: 18 },
  balance: { color: "#fff", fontSize: 32, fontWeight: "900", marginTop: 4, letterSpacing: -1 },
  pnlRow: { flexDirection: "row", marginTop: 8 },
  pnlPill: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999 },
  pnlText: { fontWeight: "800", fontSize: 12 },

  kpiRow: { flexDirection: "row", marginTop: 18, paddingTop: 16, borderTopColor: theme.colors.border, borderTopWidth: 1 },
  kpi: { flex: 1 },
  kpiL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  kpiV: { color: "#fff", fontSize: 16, fontWeight: "800", marginTop: 4 },

  stratCard: {
    marginTop: 14, padding: 14,
    backgroundColor: "rgba(243,186,47,0.07)", borderColor: "rgba(243,186,47,0.25)", borderWidth: 1,
    borderRadius: 16,
  },
  stratHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  stratTitle: { color: theme.colors.primary, fontWeight: "800", fontSize: 12, letterSpacing: 0.8 },
  stratText: { color: theme.colors.textSecondary, fontSize: 12, lineHeight: 18, marginTop: 6 },
  boostsRow: { flexDirection: "row", gap: 6, marginTop: 10, flexWrap: "wrap" },
  boost: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999,
    backgroundColor: "rgba(0,227,150,0.10)",
    borderColor: "rgba(0,227,150,0.3)", borderWidth: 1,
  },
  boostText: { color: theme.colors.buy, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  trailPill: {
    flexDirection: "row", alignItems: "center", gap: 3,
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6,
    backgroundColor: "rgba(0,227,150,0.15)",
    borderColor: "rgba(0,227,150,0.4)", borderWidth: 1,
  },
  trailPillText: { color: theme.colors.buy, fontSize: 9, fontWeight: "900", letterSpacing: 0.5 },

  sectionHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 24, marginBottom: 12 },
  sectionTitle: { color: "#fff", fontSize: 17, fontWeight: "900" },
  muted: { color: theme.colors.textMuted, fontSize: 12, fontWeight: "700" },

  emptyCard: {
    padding: 24, alignItems: "center", gap: 6,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1, borderRadius: 18,
  },
  emptyT: { color: "#fff", fontWeight: "700", fontSize: 14, marginTop: 8, textAlign: "center" },
  emptyS: { color: theme.colors.textSecondary, fontSize: 12, textAlign: "center" },
  emptyHist: { color: theme.colors.textSecondary, textAlign: "center", paddingVertical: 16, fontSize: 13 },

  posCard: {
    padding: 14, borderRadius: 16,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  posHead: { flexDirection: "row", alignItems: "center", gap: 10 },
  iconCircle: {
    width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surfaceAlt, borderColor: theme.colors.border, borderWidth: 1,
  },
  iconText: { color: theme.colors.primary, fontWeight: "800", fontSize: 11 },
  posSym: { color: "#fff", fontWeight: "800", fontSize: 14 },
  posPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  pnlMini: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  pnlMiniText: { fontWeight: "800", fontSize: 12 },
  posGrid: { flexDirection: "row", marginTop: 12, gap: 8 },
  posMetric: { flex: 1, padding: 10, borderRadius: 12, backgroundColor: theme.colors.surfaceAlt },
  metricL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  metricV: { color: "#fff", fontSize: 12, fontWeight: "800", marginTop: 4 },
  posReason: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 10, lineHeight: 16 },

  histRow: {
    flexDirection: "row", alignItems: "center", gap: 10,
    padding: 12, borderRadius: 14,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  histPill: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  histSym: { color: "#fff", fontWeight: "800", fontSize: 13 },
  histReason: { color: theme.colors.textSecondary, fontWeight: "600", fontSize: 11 },
  histTime: { color: theme.colors.textMuted, fontSize: 10, marginTop: 2 },
  histPnl: { fontWeight: "800", fontSize: 13 },
  histPnlPct: { fontSize: 11, fontWeight: "700", marginTop: 2 },

  resetBtn: {
    marginTop: 24, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    paddingVertical: 12, borderRadius: 999,
    backgroundColor: "rgba(255,69,96,0.08)", borderColor: "rgba(255,69,96,0.3)", borderWidth: 1,
  },
  resetText: { color: theme.colors.danger, fontWeight: "800", fontSize: 13 },
  backtestCard: {
    marginTop: 14, padding: 16,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: theme.colors.surface, borderRadius: 18,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  backtestLeft: { flexDirection: "row", alignItems: "center", gap: 12 },
  backtestIcon: {
    width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(243,186,47,0.12)",
    borderColor: "rgba(243,186,47,0.25)", borderWidth: 1,
  },
  backtestTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  backtestSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },
  scanBtn: {
    marginTop: 12, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    paddingVertical: 14, borderRadius: 999,
    backgroundColor: theme.colors.primary,
  },
  scanText: { color: "#000", fontWeight: "900", fontSize: 14 },

  backtestCard: {
    marginTop: 14, padding: 16,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: theme.colors.surface, borderRadius: 18,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  backtestLeft: { flexDirection: "row", alignItems: "center", gap: 12 },
  backtestIcon: {
    width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(243,186,47,0.12)",
    borderColor: "rgba(243,186,47,0.25)", borderWidth: 1,
  },
  backtestTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  backtestSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },
  disclaimer: { color: theme.colors.textMuted, fontSize: 11, textAlign: "center", marginTop: 16, lineHeight: 16 },

  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: {
    backgroundColor: theme.colors.surface,
    borderTopLeftRadius: 28, borderTopRightRadius: 28,
    paddingHorizontal: 22, paddingTop: 18, paddingBottom: 30,
    maxHeight: "92%",
    borderTopColor: theme.colors.border, borderLeftColor: theme.colors.border, borderRightColor: theme.colors.border, borderWidth: 1,
  },
  handle: { width: 42, height: 4, backgroundColor: theme.colors.borderStrong, alignSelf: "center", borderRadius: 2, marginBottom: 14 },
  sheetTitle: { color: "#fff", fontSize: 20, fontWeight: "900", marginBottom: 14 },
  lbl: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginBottom: 8, marginTop: 12 },
  input: {
    backgroundColor: theme.colors.surfaceAlt,
    borderColor: theme.colors.border, borderWidth: 1,
    borderRadius: 14, padding: 14, color: "#fff", fontSize: 15,
  },
  grid2: { flexDirection: "row", gap: 10 },
  pairs: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  pairChip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999,
    backgroundColor: theme.colors.surfaceAlt, borderColor: theme.colors.border, borderWidth: 1,
  },
  pairChipActive: { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
  pairText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 12 },
  pairTextActive: { color: "#000" },

  cta: { marginTop: 22, backgroundColor: theme.colors.primary, paddingVertical: 16, borderRadius: 999, alignItems: "center" },
  ctaText: { color: "#000", fontWeight: "900", fontSize: 15 },

  modeCard: {
    marginTop: 14,
    backgroundColor: theme.colors.surface,
    borderRadius: 16,
    padding: 14,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  modeCardLive: {
    backgroundColor: "rgba(255,69,96,0.05)",
    borderColor: "rgba(255,69,96,0.35)",
  },
  modeHead: { flexDirection: "row", alignItems: "center", gap: 14 },
  modeBadgeRow: { flexDirection: "row" },
  modeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    alignSelf: "flex-start",
  },
  modeBadgePaper: {
    backgroundColor: "rgba(243,186,47,0.1)",
    borderColor: "rgba(243,186,47,0.35)",
  },
  modeBadgeLive: {
    backgroundColor: "rgba(255,69,96,0.12)",
    borderColor: "rgba(255,69,96,0.45)",
  },
  modeBadgeText: { fontSize: 11, fontWeight: "800", letterSpacing: 0.3 },
  modeDesc: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 6, lineHeight: 17 },
  killRow: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingTop: 12,
    borderTopColor: theme.colors.border,
    borderTopWidth: 1,
  },
  killTitle: { color: "#fff", fontWeight: "700", fontSize: 13 },
  killSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },
});
