import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, Stack, useFocusEffect, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import { useTranslation } from "react-i18next";
import { api } from "../src/lib/api";
import { theme } from "../src/theme";

const FEATURE_ICONS = ["infinite", "sparkles", "flash", "notifications", "stats-chart", "shield-checkmark"];
const FEATURE_KEYS = ["pairs", "predictions", "live_trading", "notifications", "backtest", "advanced"];

export default function PremiumScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const params = useLocalSearchParams<{ paid?: string }>();
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [postPayBanner, setPostPayBanner] = useState<"success" | "cancel" | null>(null);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      const s = await api.premiumStatus();
      setStatus(s);
    } catch (e: any) {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Handle return-from-Stripe (paid=1) or cancel (paid=0)
  useEffect(() => {
    if (params.paid === "1") {
      setPostPayBanner("success");
      // Poll status a few times in case the webhook is slightly delayed
      const interval = setInterval(loadStatus, 2000);
      const stop = setTimeout(() => clearInterval(interval), 20000);
      return () => {
        clearInterval(interval);
        clearTimeout(stop);
      };
    } else if (params.paid === "0") {
      setPostPayBanner("cancel");
    }
  }, [params.paid, loadStatus]);

  useFocusEffect(
    useCallback(() => {
      loadStatus();
    }, [loadStatus])
  );

  const onSubscribe = async () => {
    setBusy(true);
    try {
      const deepLink = Linking.createURL("premium");
      const backend = process.env.EXPO_PUBLIC_BACKEND_URL || "";
      const successUrl = `${backend}/api/stripe/return?paid=1&target=${encodeURIComponent(deepLink)}`;
      const cancelUrl = `${backend}/api/stripe/return?paid=0&target=${encodeURIComponent(deepLink)}`;
      const sess = await api.premiumCheckout(successUrl, cancelUrl);
      if (!sess?.url) throw new Error("URL Stripe manquante");
      if (Platform.OS === "web") {
        // Open in a NEW tab so Stripe Checkout works even when our preview is embedded in an iframe
        if (typeof window !== "undefined") {
          const popup = window.open(sess.url, "_blank", "noopener,noreferrer");
          if (!popup) {
            // Popup blocked → fall back to same-tab navigation
            window.location.href = sess.url;
          }
        }
        // Show pending banner regardless
        setPostPayBanner("success");
        // Start polling for activation
        const t = setInterval(loadStatus, 3000);
        setTimeout(() => clearInterval(t), 60000);
      } else {
        await WebBrowser.openBrowserAsync(sess.url, {
          dismissButtonStyle: "close",
          presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
          enableBarCollapsing: true,
        });
        setPostPayBanner("success");
        await loadStatus();
      }
    } catch (e: any) {
      Alert.alert(t("premium.checkout_unavailable"), e?.message || t("premium.checkout_unavailable_msg"));
    } finally {
      setBusy(false);
    }
  };

  const onCancel = () => {
    const doCancel = async () => {
      setBusy(true);
      try {
        await api.premiumCancel();
        Alert.alert(
          "Abonnement annulé",
          "Tu conserves l'accès Premium jusqu'à la fin de la période payée."
        );
        await loadStatus();
      } catch (e: any) {
        Alert.alert(t("common.error"), e?.message);
      } finally {
        setBusy(false);
      }
    };
    if (Platform.OS === "web") {
      const ok =
        typeof window !== "undefined" &&
        window.confirm(t("premium.cancel_confirm_title") + "\n\n" + t("premium.cancel_confirm_msg"));
      if (ok) doCancel();
      return;
    }
    Alert.alert(
      t("premium.cancel_confirm_title"),
      t("premium.cancel_confirm_msg"),
      [
        { text: t("premium.cancel_confirm_keep"), style: "cancel" },
        { text: t("common.cancel"), style: "destructive", onPress: doCancel },
      ]
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={theme.colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const isPremium = !!status?.is_premium;
  const periodEnd = status?.current_period_end
    ? new Date(status.current_period_end)
    : null;
  const willCancel = !!status?.cancel_at_period_end;

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
          <Ionicons name="chevron-back" size={22} color={theme.colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("premium.title")}</Text>
        <View style={{ width: 36 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Post-payment banner */}
        {postPayBanner === "success" && !isPremium && (
          <View style={[styles.banner, styles.bannerSuccess]}>
            <Ionicons name="hourglass-outline" size={22} color={theme.colors.success} />
            <View style={{ flex: 1 }}>
              <Text style={styles.bannerTitle}>{t("premium.paid_pending_title")}</Text>
              <Text style={styles.bannerSub}>{t("premium.paid_pending_msg")}</Text>
              <TouchableOpacity
                onPress={loadStatus}
                style={styles.refreshBtn}
                hitSlop={8}
              >
                <Ionicons name="refresh" size={14} color={theme.colors.success} />
                <Text style={styles.refreshText}>{t("premium.verify_now")}</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
        {postPayBanner === "success" && isPremium && (
          <View style={[styles.banner, styles.bannerSuccess]}>
            <Ionicons name="checkmark-circle" size={22} color={theme.colors.success} />
            <View style={{ flex: 1 }}>
              <Text style={styles.bannerTitle}>{t("premium.paid_success_title")}</Text>
              <Text style={styles.bannerSub}>{t("premium.paid_success_msg")}</Text>
            </View>
          </View>
        )}
        {postPayBanner === "cancel" && (
          <View style={[styles.banner, styles.bannerCancel]}>
            <Ionicons name="close-circle-outline" size={22} color={theme.colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={styles.bannerTitle}>{t("premium.cancelled_payment_title")}</Text>
              <Text style={styles.bannerSub}>{t("premium.cancelled_payment_msg")}</Text>
            </View>
          </View>
        )}

        {/* HERO */}
        <LinearGradient
          colors={
            isPremium
              ? ["rgba(0,227,150,0.22)", "rgba(0,227,150,0.04)"]
              : ["rgba(243,186,47,0.25)", "rgba(243,186,47,0.04)"]
          }
          style={styles.hero}
        >
          <View style={styles.crownWrap}>
            <Ionicons
              name={isPremium ? "shield-checkmark" : "diamond"}
              size={42}
              color={isPremium ? theme.colors.success : theme.colors.primary}
            />
          </View>
          <Text style={styles.heroLabel}>{isPremium ? t("premium.hero_label_active") : t("premium.hero_label_inactive")}</Text>
          <Text style={styles.heroTitle}>{isPremium ? (status?.lifetime ? t("premium.hero_title_lifetime") : t("premium.hero_title_active")) : t("premium.hero_title_inactive")}</Text>
          {!isPremium && (
            <View style={styles.priceRow}>
              <Text style={styles.priceVal}>{t("premium.price")}</Text>
              <Text style={styles.pricePer}>{t("premium.per_month")}</Text>
            </View>
          )}
          {isPremium && status?.lifetime && (
            <Text style={styles.heroSub}>{t("premium.lifetime_subtitle")}</Text>
          )}
          {isPremium && periodEnd && !status?.lifetime && (
            <Text style={styles.heroSub}>
              {willCancel
                ? t("premium.access_until", { date: periodEnd.toLocaleDateString() })
                : t("premium.renewal_on", { date: periodEnd.toLocaleDateString() })}
            </Text>
          )}
        </LinearGradient>

        {/* FEATURES */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t("premium.unlock_title")}</Text>
          {FEATURE_KEYS.map((key, idx) => (
            <View key={key} style={styles.featRow}>
              <View style={styles.featIcon}>
                <Ionicons name={FEATURE_ICONS[idx] as any} size={16} color={theme.colors.primary} />
              </View>
              <Text style={styles.featText}>{t(`premium.features.${key}`)}</Text>
            </View>
          ))}
        </View>

        {/* CTA */}
        {!isPremium ? (
          <>
            <TouchableOpacity
              style={[styles.ctaBtn, busy && { opacity: 0.6 }]}
              onPress={onSubscribe}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#000" />
              ) : (
                <>
                  <Ionicons name="diamond" size={18} color="#000" />
                  <Text style={styles.ctaText}>{t("premium.cta_subscribe")}</Text>
                </>
              )}
            </TouchableOpacity>
            <Text style={styles.tinyNote}>{t("premium.cta_note")}</Text>
            {status?.stripe_configured === false && (
              <View style={styles.warnBox}>
                <Ionicons name="information-circle" size={16} color={theme.colors.primary} />
                <Text style={styles.warnText}>{t("premium.stripe_not_ready")}</Text>
              </View>
            )}
          </>
        ) : (
          <>
            {!willCancel ? (
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={onCancel}
                disabled={busy}
              >
                {busy ? (
                  <ActivityIndicator color={theme.colors.danger} />
                ) : (
                  <Text style={styles.cancelText}>{t("premium.cancel_subscription")}</Text>
                )}
              </TouchableOpacity>
            ) : (
              <View style={styles.willCancel}>
                <Ionicons name="time-outline" size={18} color={theme.colors.primary} />
                <Text style={styles.willCancelText}>{t("premium.will_cancel")}</Text>
              </View>
            )}
          </>
        )}

        <View style={{ height: 28 }} />
        <Text style={styles.legal}>{t("premium.legal")}</Text>
        <View style={{ height: 16 }} />
      </ScrollView>
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

  banner: {
    flexDirection: "row",
    gap: 12,
    padding: 14,
    borderRadius: 14,
    alignItems: "center",
    borderWidth: 1,
  },
  bannerSuccess: {
    backgroundColor: "rgba(0,227,150,0.08)",
    borderColor: "rgba(0,227,150,0.35)",
  },
  bannerCancel: {
    backgroundColor: "rgba(255,255,255,0.04)",
    borderColor: theme.colors.border,
  },
  bannerTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  bannerSub: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 2 },
  refreshBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    backgroundColor: "rgba(0,227,150,0.12)",
    alignSelf: "flex-start",
  },
  refreshText: { color: theme.colors.success, fontSize: 12, fontWeight: "700" },

  hero: {
    borderRadius: 22,
    padding: 22,
    alignItems: "center",
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  crownWrap: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },
  heroLabel: {
    color: theme.colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.4,
  },
  heroTitle: {
    color: "#fff",
    fontWeight: "900",
    fontSize: 24,
    marginTop: 4,
    textAlign: "center",
  },
  heroSub: {
    marginTop: 8,
    color: theme.colors.textSecondary,
    fontSize: 13,
  },
  priceRow: { flexDirection: "row", alignItems: "baseline", marginTop: 12 },
  priceVal: { color: "#fff", fontSize: 38, fontWeight: "900" },
  pricePer: { color: theme.colors.textSecondary, fontSize: 16, marginLeft: 4 },

  card: {
    backgroundColor: theme.colors.surface,
    borderRadius: 18,
    padding: 18,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  cardTitle: { color: "#fff", fontWeight: "800", fontSize: 15, marginBottom: 12 },
  featRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8, gap: 12 },
  featIcon: {
    width: 30,
    height: 30,
    borderRadius: 8,
    backgroundColor: "rgba(243,186,47,0.12)",
    alignItems: "center",
    justifyContent: "center",
  },
  featText: { color: "#fff", fontSize: 13, flex: 1 },

  ctaBtn: {
    flexDirection: "row",
    gap: 8,
    backgroundColor: theme.colors.primary,
    paddingVertical: 16,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  ctaText: { color: "#000", fontWeight: "900", fontSize: 15 },
  tinyNote: {
    textAlign: "center",
    color: theme.colors.textMuted,
    fontSize: 11,
    marginTop: 8,
  },

  warnBox: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
    backgroundColor: "rgba(243,186,47,0.07)",
    borderRadius: 12,
    borderColor: "rgba(243,186,47,0.3)",
    borderWidth: 1,
    marginTop: 8,
  },
  warnText: { color: theme.colors.text, fontSize: 12, lineHeight: 17, flex: 1 },

  cancelBtn: {
    padding: 16,
    borderRadius: 14,
    backgroundColor: "rgba(255,69,96,0.1)",
    borderColor: "rgba(255,69,96,0.3)",
    borderWidth: 1,
    alignItems: "center",
  },
  cancelText: { color: theme.colors.danger, fontWeight: "800", fontSize: 14 },
  willCancel: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    padding: 14,
    borderRadius: 14,
    backgroundColor: "rgba(243,186,47,0.07)",
    borderColor: "rgba(243,186,47,0.3)",
    borderWidth: 1,
  },
  willCancelText: { color: theme.colors.text, flex: 1, fontSize: 13 },

  legal: {
    color: theme.colors.textMuted,
    fontSize: 11,
    lineHeight: 16,
    textAlign: "center",
    paddingHorizontal: 10,
  },
});
