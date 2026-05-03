import React from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, Platform } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { theme } from "../../src/theme";
import { useAuth } from "../../src/contexts/AuthContext";

export default function Profile() {
  const { user, logout } = useAuth();
  const router = useRouter();

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

  const items: { icon: any; label: string; sub: string; onPress?: () => void }[] = [
    { icon: "shield-checkmark", label: "Sécurité", sub: "Mot de passe & 2FA (bientôt)" },
    { icon: "notifications", label: "Notifications", sub: "Alertes prix push (bientôt)" },
    { icon: "language", label: "Langue", sub: "Français" },
    { icon: "help-circle", label: "Aide", sub: "FAQ et support" },
  ];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="profile-screen">
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>Profil</Text>

        <View style={styles.userCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{user?.name?.[0]?.toUpperCase() || "U"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>{user?.name}</Text>
            <Text style={styles.email}>{user?.email}</Text>
          </View>
          <View style={styles.proPill}>
            <Ionicons name="sparkles" size={12} color={theme.colors.primary} />
            <Text style={styles.proText}>IA Active</Text>
          </View>
        </View>

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
          <Text style={styles.logoutText}>Se déconnecter</Text>
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
  proText: { color: theme.colors.primary, fontWeight: "800", fontSize: 11 },

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
