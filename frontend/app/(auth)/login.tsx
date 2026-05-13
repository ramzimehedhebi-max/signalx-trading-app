import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { Link, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import { theme } from "../../src/theme";
import { useAuth } from "../../src/contexts/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setErr(null);
    if (!email.trim() || !password) {
      setErr(t("auth.errors.email_required"));
      return;
    }
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      router.replace("/(tabs)");
    } catch (e: any) {
      setErr(e.message || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity onPress={() => router.back()} style={styles.back} testID="login-back-btn">
            <Ionicons name="chevron-back" size={24} color="#fff" />
          </TouchableOpacity>

          <Text style={styles.title}>{t("auth.welcome")} 👋</Text>
          <Text style={styles.subtitle}>{t("auth.tagline")}</Text>

          <View style={styles.field}>
            <Text style={styles.label}>{t("auth.email").toUpperCase()}</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder={t("auth.email_placeholder")}
              placeholderTextColor={theme.colors.textMuted}
              autoCapitalize="none"
              keyboardType="email-address"
              style={styles.input}
              testID="login-email-input"
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>{t("auth.password").toUpperCase()}</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor={theme.colors.textMuted}
              secureTextEntry
              style={styles.input}
              testID="login-password-input"
            />
          </View>

          {err && <Text style={styles.error} testID="login-error">{err}</Text>}

          <TouchableOpacity
            onPress={() => router.push("/(auth)/forgot-password")}
            style={styles.forgotBtn}
            hitSlop={10}
          >
            <Text style={styles.forgotText}>{t("auth.forgot_password")}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.primary, loading && { opacity: 0.7 }]}
            disabled={loading}
            onPress={onSubmit}
            testID="login-submit-btn"
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color="#000" />
            ) : (
              <Text style={styles.primaryText}>{t("auth.login")}</Text>
            )}
          </TouchableOpacity>

          <View style={styles.footer}>
            <Text style={styles.footerText}>{t("auth.no_account")} </Text>
            <Link href="/(auth)/register" testID="login-goto-register" replace>
              <Text style={styles.link}>{t("auth.register")}</Text>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { padding: 24, gap: 4, paddingBottom: 60 },
  back: { width: 40, height: 40, alignItems: "center", justifyContent: "center", marginLeft: -8, marginBottom: 8 },
  title: { color: "#fff", fontSize: 32, fontWeight: "900", letterSpacing: -1 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 15, marginTop: 8, marginBottom: 28 },
  field: { marginBottom: 16 },
  label: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "700", letterSpacing: 1.5, marginBottom: 8 },
  input: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    color: "#fff",
    fontSize: 15,
  },
  error: { color: theme.colors.danger, fontSize: 13, marginTop: 4, marginBottom: 8 },
  primary: {
    marginTop: 18,
    backgroundColor: theme.colors.primary,
    borderRadius: 999,
    padding: 16,
    alignItems: "center",
  },
  primaryText: { color: "#000", fontSize: 16, fontWeight: "800" },
  footer: { flexDirection: "row", justifyContent: "center", marginTop: 24 },
  footerText: { color: theme.colors.textSecondary, fontSize: 14 },
  link: { color: theme.colors.primary, fontWeight: "800", fontSize: 14 },
  forgotBtn: { alignSelf: "flex-end", marginTop: 4, marginBottom: 4, padding: 8 },
  forgotText: { color: theme.colors.primary, fontSize: 13, fontWeight: "700" },
});
