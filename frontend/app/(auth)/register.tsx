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
import { theme } from "../../src/theme";
import { useAuth } from "../../src/contexts/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setErr(null);
    if (!name.trim() || !email.trim() || password.length < 6) {
      setErr("Nom, email et mot de passe (6+ caractères) requis");
      return;
    }
    setLoading(true);
    try {
      await register(email.trim().toLowerCase(), password, name.trim());
      router.replace("/(tabs)");
    } catch (e: any) {
      setErr(e.message || "Erreur d'inscription");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity onPress={() => router.back()} style={styles.back} testID="register-back-btn">
            <Ionicons name="chevron-back" size={24} color="#fff" />
          </TouchableOpacity>

          <Text style={styles.title}>Crée ton compte</Text>
          <Text style={styles.subtitle}>30 secondes pour débloquer les signaux IA.</Text>

          <View style={styles.field}>
            <Text style={styles.label}>NOM</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Ton nom"
              placeholderTextColor={theme.colors.textMuted}
              style={styles.input}
              testID="register-name-input"
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.label}>EMAIL</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="toi@email.com"
              placeholderTextColor={theme.colors.textMuted}
              autoCapitalize="none"
              keyboardType="email-address"
              style={styles.input}
              testID="register-email-input"
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.label}>MOT DE PASSE</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="6 caractères minimum"
              placeholderTextColor={theme.colors.textMuted}
              secureTextEntry
              style={styles.input}
              testID="register-password-input"
            />
          </View>

          {err && <Text style={styles.error} testID="register-error">{err}</Text>}

          <TouchableOpacity
            style={[styles.primary, loading && { opacity: 0.7 }]}
            disabled={loading}
            onPress={onSubmit}
            testID="register-submit-btn"
            activeOpacity={0.85}
          >
            {loading ? <ActivityIndicator color="#000" /> : <Text style={styles.primaryText}>Créer mon compte</Text>}
          </TouchableOpacity>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Déjà inscrit ? </Text>
            <Link href="/(auth)/login" testID="register-goto-login" replace>
              <Text style={styles.link}>Se connecter</Text>
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
});
