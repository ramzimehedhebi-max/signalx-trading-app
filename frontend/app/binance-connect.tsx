import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { api } from "../src/lib/api";
import { theme } from "../src/theme";

export default function BinanceConnectScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const [status, setStatus] = useState<any>(null);
  const [balances, setBalances] = useState<any[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [showSecret, setShowSecret] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      const s = await api.binanceStatus();
      setStatus(s);
      if (s.connected) {
        try {
          const acc = await api.binanceAccount();
          setBalances(acc.balances || []);
        } catch {}
      }
    } catch (e: any) {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const doConnect = async (force: boolean) => {
    setBusy(true);
    try {
      const res = await api.binanceConnect(apiKey.trim(), apiSecret.trim(), force);
      setApiKey("");
      setApiSecret("");
      if (res.unverified) {
        Alert.alert(
          "✅ Clés sauvegardées (non vérifiées)",
          "Tes clés Binance sont stockées en sécurité (chiffrement AES). Le bot tentera de les valider à sa prochaine exécution. Si Binance n'est pas joignable, tu seras prévenu via les notifications."
        );
      } else {
        Alert.alert(
          t("binance.success_title"),
          t("binance.success_msg", { type: res.account_type || "SPOT", trade: res.can_trade ? t("common.yes") : t("common.no") })
        );
      }
      await loadStatus();
    } catch (e: any) {
      const msg = e?.message || "";
      // Backend signals geo-block with prefix "GEO_BLOCKED|"
      if (msg.includes("GEO_BLOCKED") || msg.includes("503")) {
        Alert.alert(
          "⚠️ Binance non joignable depuis le serveur",
          "Notre serveur cloud est temporairement bloqué par Binance (restriction géographique). Tu peux sauvegarder tes clés quand même — elles seront chiffrées en AES-128 et le bot les utilisera dès que la connexion sera rétablie.",
          [
            { text: "Annuler", style: "cancel" },
            {
              text: "Sauvegarder quand même",
              onPress: () => doConnect(true),
            },
          ]
        );
      } else {
        Alert.alert(t("binance.fail_title"), msg || t("binance.unknown_error"));
      }
    } finally {
      setBusy(false);
    }
  };

  const onConnect = async () => {
    if (apiKey.trim().length < 20 || apiSecret.trim().length < 20) {
      Alert.alert(t("binance.invalid_keys_title"), t("binance.invalid_keys_msg"));
      return;
    }
    await doConnect(false);
  };

  const onDisconnect = () => {
    Alert.alert(
      t("binance.disconnect_confirm"),
      t("binance.disconnect_msg"),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("binance.disconnect_btn"),
          style: "destructive",
          onPress: async () => {
            setBusy(true);
            try {
              await api.binanceDisconnect();
              setBalances([]);
              await loadStatus();
            } catch (e: any) {
              Alert.alert(t("common.error"), e?.message);
            } finally {
              setBusy(false);
            }
          },
        },
      ]
    );
  };

  const usdtBal = balances.find((b: any) => b.asset === "USDT");

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
          <Ionicons name="chevron-back" size={22} color={theme.colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("binance.title")}</Text>
        <View style={{ width: 36 }} />
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          {/* HERO STATUS */}
          <LinearGradient
            colors={
              status?.connected
                ? ["rgba(0,227,150,0.18)", "rgba(0,227,150,0.04)"]
                : ["rgba(243,186,47,0.18)", "rgba(243,186,47,0.04)"]
            }
            style={styles.hero}
          >
            <View style={styles.heroRow}>
              <View style={styles.iconWrap}>
                <Ionicons
                  name={status?.connected ? "shield-checkmark" : "shield-outline"}
                  size={28}
                  color={status?.connected ? theme.colors.success : theme.colors.primary}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.heroLabel}>{status?.connected ? t("binance.status_connected") : t("binance.status_disconnected")}</Text>
                <Text style={styles.heroTitle}>{status?.connected ? t("binance.trading_active") : t("binance.paper_only")}</Text>
              </View>
            </View>
            {status?.connected && usdtBal && (
              <View style={styles.balanceCard}>
                <Text style={styles.balanceLabel}>{t("binance.balance")}</Text>
                <Text style={styles.balanceValue}>${parseFloat(usdtBal.free).toFixed(2)}</Text>
              </View>
            )}
          </LinearGradient>

          {!status?.connected ? (
            <>
              {/* INSTRUCTIONS */}
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>{t("binance.how_to_title")}</Text>
                <View style={styles.step}>
                  <Text style={styles.stepNum}>1</Text>
                  <Text style={styles.stepText}>
                    {t("binance.step_1_part1")}<Text style={styles.bold}>{t("binance.step_1_brand")}</Text>{t("binance.step_1_part2")}
                  </Text>
                </View>
                <View style={styles.step}>
                  <Text style={styles.stepNum}>2</Text>
                  <Text style={styles.stepText}>
                    {t("binance.step_2_part1")}<Text style={styles.bold}>{t("binance.step_2_strong1")}</Text>{t("binance.step_2_part2")}<Text style={styles.bold}>{t("binance.step_2_strong2")}</Text>
                  </Text>
                </View>
                <View style={styles.step}>
                  <Text style={styles.stepNum}>3</Text>
                  <Text style={styles.stepText}>
                    {t("binance.step_3_part1")}<Text style={styles.bold}>{t("binance.step_3_strong")}</Text>{t("binance.step_3_part2")}
                  </Text>
                </View>
                <View style={styles.step}>
                  <Text style={styles.stepNum}>4</Text>
                  <Text style={styles.stepText}>
                    <Text style={styles.bold}>{t("binance.step_4_strong")}</Text>{t("binance.step_4_part")}
                  </Text>
                </View>
                <View style={styles.warn}>
                  <Ionicons name="warning" size={16} color={theme.colors.danger} />
                  <Text style={styles.warnText}>{t("binance.warn_withdrawals")}</Text>
                </View>
              </View>

              {/* FORM */}
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>{t("binance.form_title")}</Text>
                <Text style={styles.label}>API Key</Text>
                <TextInput
                  value={apiKey}
                  onChangeText={setApiKey}
                  placeholder={t("binance.placeholder")}
                  placeholderTextColor={theme.colors.textMuted}
                  style={styles.input}
                  autoCapitalize="none"
                  autoCorrect={false}
                />
                <Text style={styles.label}>{t("binance.api_secret")}</Text>
                <View style={styles.secretRow}>
                  <TextInput
                    value={apiSecret}
                    onChangeText={setApiSecret}
                    placeholder={t("binance.placeholder")}
                    placeholderTextColor={theme.colors.textMuted}
                    style={[styles.input, { flex: 1, marginBottom: 0 }]}
                    autoCapitalize="none"
                    autoCorrect={false}
                    secureTextEntry={!showSecret}
                  />
                  <TouchableOpacity
                    onPress={() => setShowSecret((v) => !v)}
                    style={styles.eyeBtn}
                  >
                    <Ionicons
                      name={showSecret ? "eye-off" : "eye"}
                      size={20}
                      color={theme.colors.textSecondary}
                    />
                  </TouchableOpacity>
                </View>

                <TouchableOpacity
                  style={[styles.primaryBtn, busy && { opacity: 0.6 }]}
                  onPress={onConnect}
                  disabled={busy}
                >
                  {busy ? (
                    <ActivityIndicator color="#000" />
                  ) : (
                    <>
                      <Ionicons name="link" size={18} color="#000" />
                      <Text style={styles.primaryBtnText}>{t("binance.connect_btn")}</Text>
                    </>
                  )}
                </TouchableOpacity>

                <Text style={styles.tinyNote}>{t("binance.encryption_note")}</Text>
              </View>
            </>
          ) : (
            <>
              {/* BALANCES */}
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Text style={styles.sectionTitle}>{t("binance.balances")}</Text>
                  <TouchableOpacity onPress={loadStatus}>
                    <Ionicons name="refresh" size={20} color={theme.colors.textSecondary} />
                  </TouchableOpacity>
                </View>
                {balances.length === 0 ? (
                  <Text style={styles.empty}>{t("binance.no_balance")}</Text>
                ) : (
                  balances.slice(0, 10).map((b: any) => (
                    <View key={b.asset} style={styles.balanceRow}>
                      <View style={styles.assetDot} />
                      <Text style={styles.assetSym}>{b.asset}</Text>
                      <View style={{ flex: 1 }} />
                      <Text style={styles.assetQty}>{parseFloat(b.free).toFixed(6)}</Text>
                    </View>
                  ))
                )}
              </View>

              {/* INFO LIVE MODE */}
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>{t("binance.next_step_title")}</Text>
                <Text style={styles.bodyText}>
                  {t("binance.next_step_desc_part1")}<Text style={styles.bold}>{t("binance.next_step_desc_bot")}</Text>{t("binance.next_step_desc_part2")}<Text style={[styles.bold, { color: theme.colors.danger }]}>{t("binance.next_step_desc_live")}</Text>{t("binance.next_step_desc_part3")}
                </Text>
                <Text style={[styles.bodyText, { marginTop: 8, color: theme.colors.textSecondary }]}>
                  {t("binance.limit_default_part1")}<Text style={styles.bold}>{t("binance.limit_default_amount")}</Text>{t("binance.limit_default_part2")}
                </Text>
              </View>

              <TouchableOpacity
                style={styles.dangerBtn}
                onPress={onDisconnect}
                disabled={busy}
              >
                {busy ? (
                  <ActivityIndicator color={theme.colors.danger} />
                ) : (
                  <>
                    <Ionicons name="unlink" size={18} color={theme.colors.danger} />
                    <Text style={styles.dangerBtnText}>{t("binance.disconnect_btn")}</Text>
                  </>
                )}
              </TouchableOpacity>
            </>
          )}
          <View style={{ height: 24 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomColor: theme.colors.border,
    borderBottomWidth: 1,
  },
  headerBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: { color: theme.colors.text, fontWeight: "700", fontSize: 17 },
  scroll: { padding: 16, gap: 16 },
  hero: {
    borderRadius: 20,
    padding: 18,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  heroRow: { flexDirection: "row", alignItems: "center", gap: 14 },
  iconWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  heroLabel: {
    color: theme.colors.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.2,
  },
  heroTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "800", marginTop: 2 },
  balanceCard: {
    marginTop: 14,
    padding: 12,
    borderRadius: 12,
    backgroundColor: "rgba(0,0,0,0.25)",
  },
  balanceLabel: {
    color: theme.colors.textSecondary,
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.8,
  },
  balanceValue: {
    color: theme.colors.text,
    fontSize: 26,
    fontWeight: "800",
    marginTop: 2,
  },
  card: {
    backgroundColor: theme.colors.surface,
    borderRadius: 16,
    padding: 16,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  sectionTitle: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 12,
  },
  step: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 8,
    alignItems: "flex-start",
  },
  stepNum: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: theme.colors.primary,
    color: "#000",
    textAlign: "center",
    lineHeight: 24,
    fontSize: 12,
    fontWeight: "800",
  },
  stepText: {
    color: theme.colors.text,
    fontSize: 13.5,
    flex: 1,
    lineHeight: 20,
  },
  bold: { fontWeight: "800" },
  warn: {
    marginTop: 8,
    flexDirection: "row",
    gap: 8,
    backgroundColor: "rgba(255,69,96,0.1)",
    padding: 10,
    borderRadius: 10,
    borderColor: "rgba(255,69,96,0.25)",
    borderWidth: 1,
  },
  warnText: { color: theme.colors.text, fontSize: 12, lineHeight: 17, flex: 1 },
  label: {
    color: theme.colors.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1,
    marginBottom: 6,
  },
  input: {
    backgroundColor: theme.colors.bg,
    color: theme.colors.text,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 14,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    fontSize: 13,
  },
  secretRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 14 },
  eyeBtn: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: theme.colors.bg,
    alignItems: "center",
    justifyContent: "center",
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  primaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: theme.colors.primary,
    paddingVertical: 15,
    borderRadius: 14,
    marginTop: 4,
  },
  primaryBtnText: { color: "#000", fontWeight: "800", fontSize: 15 },
  tinyNote: {
    marginTop: 12,
    color: theme.colors.textMuted,
    fontSize: 11,
    lineHeight: 16,
    textAlign: "center",
  },
  bodyText: { color: theme.colors.text, fontSize: 14, lineHeight: 20 },
  balanceRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomColor: theme.colors.border,
    borderBottomWidth: 1,
    gap: 10,
  },
  assetDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.primary,
  },
  assetSym: { color: theme.colors.text, fontWeight: "700" },
  assetQty: { color: theme.colors.textSecondary, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  empty: { color: theme.colors.textMuted, textAlign: "center", padding: 14, fontSize: 13 },
  dangerBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: "rgba(255,69,96,0.1)",
    borderColor: "rgba(255,69,96,0.3)",
    borderWidth: 1,
    paddingVertical: 14,
    borderRadius: 14,
  },
  dangerBtnText: { color: theme.colors.danger, fontWeight: "800", fontSize: 14 },
});
