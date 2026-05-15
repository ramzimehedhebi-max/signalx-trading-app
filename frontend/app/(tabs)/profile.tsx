import React, { useEffect, useState, useCallback } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, Platform } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { theme } from "../../src/theme";
import { useAuth } from "../../src/contexts/AuthContext";
import { api } from "../../src/lib/api";
import { LanguagePickerRow } from "../../src/components/LanguagePicker";

export default function Profile() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const { t } = useTranslation();
  const [binance, setBinance] = useState<any>(null);
  const [premium, setPremium] = useState<any>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);

  const loadBinance = useCallback(async () => {
    try {
      const s = await api.binanceStatus();
      setBinance(s);
    } catch {}
    try {
      const p = await api.premiumStatus();
      setPremium(p);
    } catch {}
    try {
      const u = await api.unreadCount();
      setUnreadCount(u?.count ?? u?.unread ?? 0);
    } catch {}
  }, []);

  useEffect(() => {
    loadBinance();
  }, [loadBinance]);

  useFocusEffect(
    useCallback(() => {
      loadBinance();
    }, [loadBinance])
  );

  const doLogout = async () => {
    await logout();
    router.replace("/(auth)/welcome");
  };

  const onLogout = () => {
    if (Platform.OS === "web") {
      // eslint-disable-next-line no-alert
      const ok = typeof window !== "undefined" && window.confirm("Te déconnecter de SignalX ?");
      if (ok) doLogout();
      return;
    }
    Alert.alert("Déconnexion", "Te déconnecter de SignalX ?", [
      { text: "Annuler" },
      { text: "Déconnecter", style: "destructive", onPress: doLogout },
    ]);
  };

  const items: { icon: any; label: string; sub: string; onPress?: () => void; badge?: number }[] = [
    {
      icon: "shield-checkmark",
      label: t("profile.security"),
      sub: t("profile.security_sub"),
      onPress: () => {
        if (Platform.OS === "web") {
          // eslint-disable-next-line no-alert
          typeof window !== "undefined" && window.alert("Bientôt disponible — Mot de passe & 2FA");
        } else {
          Alert.alert("Bientôt disponible", "La gestion du mot de passe et de la 2FA arrive très bientôt.");
        }
      },
    },
    {
      icon: "notifications",
      label: t("profile.notifications"),
      sub: t("profile.notifications_sub"),
      onPress: () => router.push("/notifications"),
      badge: unreadCount,
    },
    {
      icon: "help-circle",
      label: t("profile.support"),
      sub: t("profile.support_sub"),
      onPress: () => router.push("/help"),
    },
  ];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="profile-screen">
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>{t("profile.title")}</Text>

        <View style={styles.userCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{user?.name?.[0]?.toUpperCase() || "U"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>{user?.name}</Text>
            <Text style={styles.email}>{user?.email}</Text>
          </View>
          <View style={[styles.proPill, premium?.is_premium && styles.proPillActive]}>
            <Ionicons
              name={premium?.is_premium ? "diamond" : "sparkles"}
              size={12}
              color={premium?.is_premium ? theme.colors.success : theme.colors.primary}
            />
            <Text
              style={[
                styles.proText,
                premium?.is_premium && { color: theme.colors.success },
              ]}
            >
              {premium?.is_premium ? "Premium" : "Free"}
            </Text>
          </View>
        </View>

        {/* Premium card */}
        <TouchableOpacity
          activeOpacity={0.85}
          style={[styles.binanceCard, premium?.is_premium && styles.binanceCardConnected]}
          onPress={() => router.push("/premium")}
        >
          <View style={styles.binanceIconWrap}>
            <Ionicons
              name={premium?.is_premium ? "diamond" : "diamond-outline"}
              size={22}
              color={premium?.is_premium ? theme.colors.success : theme.colors.primary}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.binanceTitle}>
              {premium?.is_premium ? t("profile.premium_active") : t("profile.premium_upgrade")}
            </Text>
            <Text style={styles.binanceSub}>
              {premium?.is_premium ? t("profile.premium_manage") : t("profile.premium_pitch")}
            </Text>
          </View>
          <Ionicons name="chevron-forward" color={theme.colors.textMuted} size={18} />
        </TouchableOpacity>

        {/* Binance connection — call-to-action */}
        <TouchableOpacity
          activeOpacity={0.85}
          style={[
            styles.binanceCard,
            binance?.connected && styles.binanceCardConnected,
          ]}
          onPress={() => router.push("/binance-connect")}
        >
          <View style={styles.binanceIconWrap}>
            <Ionicons
              name={binance?.connected ? "shield-checkmark" : "wallet"}
              size={22}
              color={binance?.connected ? theme.colors.success : theme.colors.primary}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.binanceTitle}>
              {binance?.connected ? t("profile.binance_connected") : t("profile.binance_connect")}
            </Text>
            <Text style={styles.binanceSub}>
              {binance?.connected ? t("profile.binance_manage") : t("profile.binance_connect_desc")}
            </Text>
          </View>
          {binance?.connected ? (
            <View style={styles.greenDot} />
          ) : (
            <Ionicons name="chevron-forward" color={theme.colors.textMuted} size={18} />
          )}
        </TouchableOpacity>

        {/* Language picker */}
        <LanguagePickerRow />

        <View style={styles.list}>
          {items.map((it, idx) => (
            <TouchableOpacity
              key={it.label}
              style={[styles.row, idx !== 0 && styles.rowBorder]}
              testID={`profile-${it.label}`}
              onPress={it.onPress}
              activeOpacity={0.7}
            >
              <View style={styles.rowIconWrap}>
                <Ionicons name={it.icon} color={theme.colors.primary} size={18} />
                {!!it.badge && it.badge > 0 && (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{it.badge > 99 ? "99+" : it.badge}</Text>
                  </View>
                )}
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowLabel}>{it.label}</Text>
                <Text style={styles.rowSub}>{it.sub}</Text>
              </View>
              <Ionicons name="chevron-forward" color={theme.colors.textMuted} size={18} />
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.disclaimer}>
          <Ionicons name="warning-outline" color={theme.colors.primary} size={16} />
          <Text style={styles.disclaimerText}>
            SignalX fournit des analyses techniques basées sur l&apos;IA. Aucune garantie de gain. Le
            trading crypto comporte des risques élevés. Investis uniquement ce que tu peux perdre.
          </Text>
        </View>

        <TouchableOpacity style={styles.logout} onPress={onLogout} testID="profile-logout-btn">
          <Ionicons name="log-out-outline" color={theme.colors.danger} size={18} />
          <Text style={styles.logoutText}>{t("auth.logout")}</Text>
        </TouchableOpacity>

        <Text style={styles.version}>SignalX v1.0 · Powered by Claude Sonnet 4.5</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { padding: 24, paddingBottom: 40 },
  title: { color: "#fff", fontSize: 28, fontWeight: "900", letterSpacing: -0.8, marginBottom: 22 },
  userCard: {
    flexDirection: "row", alignItems: "center", gap: 14, padding: 18,
    backgroundColor: theme.colors.surface, borderRadius: 20, borderColor: theme.colors.border, borderWidth: 1,
  },
  avatar: {
    width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.primary,
  },
  avatarText: { color: "#000", fontWeight: "900", fontSize: 22 },
  name: { color: "#fff", fontWeight: "800", fontSize: 15 },
  email: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 2 },
  proPill: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999,
    backgroundColor: "rgba(243,186,47,0.12)", borderColor: "rgba(243,186,47,0.4)", borderWidth: 1,
  },
  proPillActive: {
    backgroundColor: "rgba(0,227,150,0.12)",
    borderColor: "rgba(0,227,150,0.45)",
  },
  proText: { color: theme.colors.primary, fontWeight: "800", fontSize: 11 },

  binanceCard: {
    marginTop: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: 16,
    backgroundColor: theme.colors.surface,
    borderRadius: 18,
    borderColor: "rgba(243,186,47,0.4)",
    borderWidth: 1,
  },
  binanceCardConnected: {
    borderColor: "rgba(0,227,150,0.4)",
    backgroundColor: "rgba(0,227,150,0.05)",
  },
  binanceIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.surfaceAlt,
  },
  binanceTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  binanceSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },
  greenDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: theme.colors.success,
  },

  list: {
    marginTop: 18,
    backgroundColor: theme.colors.surface,
    borderRadius: 20,
    borderColor: theme.colors.border, borderWidth: 1, overflow: "hidden",
  },
  row: { flexDirection: "row", alignItems: "center", padding: 16, gap: 12 },
  rowBorder: { borderTopColor: theme.colors.border, borderTopWidth: 1 },
  rowIconWrap: {
    width: 38, height: 38, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(243,186,47,0.08)",
    position: "relative",
  },
  badge: {
    position: "absolute",
    top: -4,
    right: -4,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: theme.colors.sell,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 5,
    borderWidth: 2,
    borderColor: theme.colors.surface,
  },
  badgeText: {
    color: "#fff",
    fontWeight: "900",
    fontSize: 10,
    lineHeight: 12,
  },
  rowLabel: { color: "#fff", fontWeight: "800", fontSize: 14 },
  rowSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },

  disclaimer: {
    marginTop: 18, padding: 14,
    flexDirection: "row", gap: 10,
    backgroundColor: "rgba(243,186,47,0.06)",
    borderColor: "rgba(243,186,47,0.25)", borderWidth: 1,
    borderRadius: 16,
  },
  disclaimerText: { color: theme.colors.textSecondary, fontSize: 11, lineHeight: 16, flex: 1 },

  logout: {
    marginTop: 18, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    paddingVertical: 16, borderRadius: 999,
    backgroundColor: "rgba(255,69,96,0.08)", borderColor: "rgba(255,69,96,0.3)", borderWidth: 1,
  },
  logoutText: { color: theme.colors.danger, fontWeight: "800", fontSize: 14 },

  version: { color: theme.colors.textMuted, fontSize: 11, textAlign: "center", marginTop: 24 },
});
