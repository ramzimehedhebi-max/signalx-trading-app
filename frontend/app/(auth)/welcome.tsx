import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ImageBackground,
  TouchableOpacity,
  Dimensions,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { theme } from "../../src/theme";
import { SafeAreaView } from "react-native-safe-area-context";

const HERO =
  "https://static.prod-images.emergentagent.com/jobs/7c6a6fa1-aaf5-4739-b507-171c0af670d4/images/6e0eaa83f67e1677db7291837d87cd6f46cfe7427cadba8b116f8a87cc546ab0.png";

export default function Welcome() {
  const router = useRouter();
  const { t } = useTranslation();
  return (
    <ImageBackground
      source={{ uri: HERO }}
      style={styles.bg}
      resizeMode="cover"
      testID="welcome-screen"
    >
      <LinearGradient
        colors={["rgba(9,12,21,0.55)", "rgba(9,12,21,0.85)", theme.colors.bg]}
        locations={[0, 0.5, 1]}
        style={StyleSheet.absoluteFillObject}
      />
      <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
        <View style={styles.topRow}>
          <View style={styles.logoWrap}>
            <Ionicons name="trending-up" size={20} color={theme.colors.bg} />
          </View>
          <Text style={styles.brand}>SignalX</Text>
        </View>

        <View style={{ flex: 1 }} />

        <View style={styles.content}>
          <View style={styles.badge}>
            <View style={styles.dot} />
            <Text style={styles.badgeText}>IA · CLAUDE SONNET 4.5</Text>
          </View>
          <Text style={styles.title}>
            Sache <Text style={{ color: theme.colors.primary }}>quand acheter</Text>{"\n"}
            et quand vendre.
          </Text>
          <Text style={styles.subtitle}>
            Signaux d&apos;achat / vente alimentés par l&apos;IA, en temps réel sur les
            paires Binance. Décode le marché en quelques secondes.
          </Text>

          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => router.push("/(auth)/register")}
            testID="welcome-register-btn"
            activeOpacity={0.85}
          >
            <Text style={styles.primaryBtnText}>{t("auth.register")}</Text>
            <Ionicons name="arrow-forward" size={18} color="#000" />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.secondaryBtn}
            onPress={() => router.push("/(auth)/login")}
            testID="welcome-login-btn"
            activeOpacity={0.85}
          >
            <Text style={styles.secondaryBtnText}>{t("auth.have_account")}</Text>
          </TouchableOpacity>

          <Text style={styles.disclaimer}>
            Cet outil fournit des analyses, pas des conseils financiers. Le trading
            crypto comporte des risques.
          </Text>
        </View>
      </SafeAreaView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: theme.colors.bg },
  safe: { flex: 1, paddingHorizontal: 24 },
  topRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 8 },
  logoWrap: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: theme.colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brand: { color: "#fff", fontSize: 18, fontWeight: "800", letterSpacing: 0.5 },
  content: { paddingBottom: 12 },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 7,
    backgroundColor: "rgba(243,186,47,0.12)",
    borderColor: "rgba(243,186,47,0.45)",
    borderWidth: 1,
    borderRadius: 999,
    marginBottom: 16,
  },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: theme.colors.primary },
  badgeText: { color: theme.colors.primary, fontSize: 11, fontWeight: "800", letterSpacing: 1.5 },
  title: { color: "#fff", fontSize: 38, fontWeight: "900", lineHeight: 44, letterSpacing: -1 },
  subtitle: {
    color: theme.colors.textSecondary,
    fontSize: 15,
    lineHeight: 22,
    marginTop: 14,
    marginBottom: 28,
  },
  primaryBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: 999,
    paddingVertical: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    shadowColor: theme.colors.primary,
    shadowOpacity: 0.4,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
  },
  primaryBtnText: { color: "#000", fontSize: 16, fontWeight: "800" },
  secondaryBtn: {
    marginTop: 12,
    paddingVertical: 16,
    borderRadius: 999,
    borderColor: theme.colors.borderStrong,
    borderWidth: 1,
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.04)",
  },
  secondaryBtnText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  disclaimer: {
    color: theme.colors.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: 18,
    lineHeight: 16,
  },
});
