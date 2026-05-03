import React, { useCallback, useEffect, useState } from "react";
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
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { theme, fmtPrice, fmtUsd, symbolToBase } from "../../src/theme";
import { api } from "../../src/lib/api";

export default function Portfolio() {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState("");
  const [entry, setEntry] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const p = await api.portfolio();
      setData(p);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const submit = async () => {
    if (!symbol.trim() || !qty || !entry) {
      Alert.alert("Erreur", "Renseigne tous les champs");
      return;
    }
    const q = parseFloat(qty);
    const e = parseFloat(entry);
    if (isNaN(q) || isNaN(e) || q <= 0 || e <= 0) {
      Alert.alert("Erreur", "Valeurs numériques invalides");
      return;
    }
    setSubmitting(true);
    try {
      await api.addPosition(symbol.trim().toUpperCase(), q, e);
      await load();
      setOpen(false);
      setSymbol("");
      setQty("");
      setEntry("");
    } catch (err: any) {
      Alert.alert("Erreur", err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id: string) => {
    Alert.alert("Supprimer", "Retirer cette position ?", [
      { text: "Annuler" },
      {
        text: "Supprimer",
        style: "destructive",
        onPress: async () => {
          await api.deletePosition(id);
          await load();
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

  const positions = data?.positions || [];
  const total = data?.total_value || 0;
  const pnl = data?.total_pnl || 0;
  const pnlPct = data?.total_pnl_pct || 0;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="portfolio-screen">
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />}
      >
        <View style={styles.head}>
          <Text style={styles.title}>Portefeuille</Text>
          <Text style={styles.subtitle}>Suivi P&amp;L en temps réel</Text>
        </View>

        {/* Balance Card */}
        <View style={styles.balanceCard}>
          <Text style={styles.balLabel}>VALEUR TOTALE</Text>
          <Text style={styles.balValue}>{fmtUsd(total)}</Text>
          <View style={styles.pnlRow}>
            <View
              style={[
                styles.pnlPill,
                { backgroundColor: pnl >= 0 ? "rgba(0,227,150,0.15)" : "rgba(255,69,96,0.15)" },
              ]}
            >
              <Ionicons
                name={pnl >= 0 ? "arrow-up" : "arrow-down"}
                size={12}
                color={pnl >= 0 ? theme.colors.buy : theme.colors.sell}
              />
              <Text style={[styles.pnlText, { color: pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                {fmtUsd(Math.abs(pnl))} ({pnlPct.toFixed(2)}%)
              </Text>
            </View>
          </View>
          <View style={styles.investedRow}>
            <View>
              <Text style={styles.investLabel}>Investi</Text>
              <Text style={styles.investValue}>{fmtUsd(data?.total_invested || 0)}</Text>
            </View>
            <View>
              <Text style={styles.investLabel}>Positions</Text>
              <Text style={styles.investValue}>{positions.length}</Text>
            </View>
          </View>
        </View>

        <TouchableOpacity style={styles.addBtn} onPress={() => setOpen(true)} testID="position-add-btn">
          <Ionicons name="add-circle" size={20} color="#000" />
          <Text style={styles.addText}>Ajouter une position</Text>
        </TouchableOpacity>

        {positions.length === 0 ? (
          <View style={styles.emptyCard}>
            <Ionicons name="briefcase-outline" size={32} color={theme.colors.textMuted} />
            <Text style={styles.emptyT}>Aucune position</Text>
            <Text style={styles.emptyS}>
              Enregistre tes achats pour voir ton P&amp;L mis à jour en direct.
            </Text>
          </View>
        ) : (
          <View style={{ marginTop: 18, gap: 10 }}>
            {positions.map((p: any) => (
              <TouchableOpacity
                key={p.id}
                style={styles.posCard}
                onLongPress={() => remove(p.id)}
                activeOpacity={0.85}
                testID={`position-${p.symbol}`}
              >
                <View style={styles.posHead}>
                  <View style={styles.iconCircle}>
                    <Text style={styles.iconText}>{symbolToBase(p.symbol).slice(0, 2)}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.posSym}>{symbolToBase(p.symbol)}</Text>
                    <Text style={styles.posPair}>{p.symbol} · {p.quantity}</Text>
                  </View>
                  <TouchableOpacity onPress={() => remove(p.id)} testID={`delete-${p.id}`}>
                    <Ionicons name="trash-outline" size={18} color={theme.colors.textMuted} />
                  </TouchableOpacity>
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
                    <Text style={styles.metricL}>P&amp;L</Text>
                    <Text style={[styles.metricV, { color: p.pnl >= 0 ? theme.colors.buy : theme.colors.sell }]}>
                      {p.pnl >= 0 ? "+" : ""}
                      {fmtUsd(p.pnl)} ({p.pnl_pct.toFixed(2)}%)
                    </Text>
                  </View>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>

      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          style={styles.modalRoot}
        >
          <TouchableOpacity style={styles.backdrop} onPress={() => setOpen(false)} activeOpacity={1} />
          <View style={styles.sheet}>
            <View style={styles.handle} />
            <Text style={styles.sheetTitle}>Nouvelle position</Text>

            <Text style={styles.lbl}>SYMBOLE BINANCE</Text>
            <TextInput
              value={symbol}
              onChangeText={setSymbol}
              placeholder="BTCUSDT"
              placeholderTextColor={theme.colors.textMuted}
              autoCapitalize="characters"
              style={styles.input}
              testID="position-symbol-input"
            />

            <Text style={styles.lbl}>QUANTITÉ</Text>
            <TextInput
              value={qty}
              onChangeText={setQty}
              placeholder="0.5"
              placeholderTextColor={theme.colors.textMuted}
              keyboardType="decimal-pad"
              style={styles.input}
              testID="position-qty-input"
            />

            <Text style={styles.lbl}>PRIX D&apos;ENTRÉE (USD)</Text>
            <TextInput
              value={entry}
              onChangeText={setEntry}
              placeholder="65000"
              placeholderTextColor={theme.colors.textMuted}
              keyboardType="decimal-pad"
              style={styles.input}
              testID="position-entry-input"
            />

            <TouchableOpacity
              style={[styles.cta, submitting && { opacity: 0.7 }]}
              onPress={submit}
              disabled={submitting}
              testID="position-submit-btn"
            >
              {submitting ? <ActivityIndicator color="#000" /> : <Text style={styles.ctaText}>Ajouter</Text>}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  head: {},
  title: { color: "#fff", fontSize: 28, fontWeight: "900", letterSpacing: -0.8 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 13, marginTop: 4, marginBottom: 22 },

  balanceCard: {
    padding: 22,
    backgroundColor: theme.colors.surface,
    borderRadius: 24,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  balLabel: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5 },
  balValue: { color: "#fff", fontSize: 36, fontWeight: "900", marginTop: 6, letterSpacing: -1 },
  pnlRow: { flexDirection: "row", marginTop: 8 },
  pnlPill: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999 },
  pnlText: { fontWeight: "800", fontSize: 12 },
  investedRow: {
    flexDirection: "row", justifyContent: "space-between",
    marginTop: 18, paddingTop: 14, borderTopColor: theme.colors.border, borderTopWidth: 1,
  },
  investLabel: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "700", letterSpacing: 1 },
  investValue: { color: "#fff", fontSize: 14, fontWeight: "700", marginTop: 4 },

  addBtn: {
    marginTop: 18,
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    paddingVertical: 14, borderRadius: 999, backgroundColor: theme.colors.primary,
    shadowColor: theme.colors.primary, shadowOpacity: 0.3, shadowRadius: 12, shadowOffset: { width: 0, height: 6 },
  },
  addText: { color: "#000", fontWeight: "900", fontSize: 14 },

  emptyCard: {
    marginTop: 24, padding: 28, alignItems: "center",
    backgroundColor: theme.colors.surface, borderRadius: 20, borderColor: theme.colors.border, borderWidth: 1, gap: 6,
  },
  emptyT: { color: "#fff", fontWeight: "800", fontSize: 15, marginTop: 6 },
  emptyS: { color: theme.colors.textSecondary, fontSize: 12, textAlign: "center" },

  posCard: {
    padding: 16,
    backgroundColor: theme.colors.surface,
    borderRadius: 18,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  posHead: { flexDirection: "row", alignItems: "center", gap: 12 },
  iconCircle: {
    width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surfaceAlt, borderColor: theme.colors.border, borderWidth: 1,
  },
  iconText: { color: theme.colors.primary, fontWeight: "800", fontSize: 11 },
  posSym: { color: "#fff", fontWeight: "800", fontSize: 14 },
  posPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  posGrid: { flexDirection: "row", marginTop: 12, gap: 10 },
  posMetric: { flex: 1, padding: 10, borderRadius: 12, backgroundColor: theme.colors.surfaceAlt },
  metricL: { color: theme.colors.textMuted, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  metricV: { color: "#fff", fontSize: 13, fontWeight: "800", marginTop: 4 },

  modalRoot: { flex: 1, justifyContent: "flex-end" },
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: {
    backgroundColor: theme.colors.surface,
    borderTopLeftRadius: 28, borderTopRightRadius: 28,
    padding: 22, paddingBottom: 40,
    borderTopColor: theme.colors.border, borderLeftColor: theme.colors.border, borderRightColor: theme.colors.border, borderWidth: 1,
  },
  handle: { width: 42, height: 4, backgroundColor: theme.colors.borderStrong, alignSelf: "center", borderRadius: 2, marginBottom: 18 },
  sheetTitle: { color: "#fff", fontSize: 20, fontWeight: "900", marginBottom: 18 },
  lbl: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5, marginBottom: 8, marginTop: 8 },
  input: {
    backgroundColor: theme.colors.surfaceAlt,
    borderColor: theme.colors.border, borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    color: "#fff",
    fontSize: 15,
  },
  cta: {
    marginTop: 22, backgroundColor: theme.colors.primary, paddingVertical: 16, borderRadius: 999, alignItems: "center",
  },
  ctaText: { color: "#000", fontWeight: "900", fontSize: 15 },
});
