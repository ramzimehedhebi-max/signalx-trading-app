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
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Stack, useRouter } from "expo-router";
import { theme } from "../../src/theme";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/contexts/AuthContext";

export default function ForgotPassword() {
  const router = useRouter();
  const { applyTokenAndUser } = useAuth() as any;
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [emailSent, setEmailSent] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const requestCode = async () => {
    setErr(null);
    if (!email.trim()) {
      setErr("Email requis");
      return;
    }
    setLoading(true);
    try {
      const res = await api.forgotPassword(email.trim().toLowerCase());
      setEmailSent(!!res?.email_sent);
      setStep("reset");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const doReset = async () => {
    setErr(null);
    if (!code.trim() || code.length !== 6) {
      setErr("Entre le code à 6 chiffres");
      return;
    }
    if (newPassword.length < 6) {
      setErr("Mot de passe trop court (min 6 caractères)");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErr("Les mots de passe ne correspondent pas");
      return;
    }
    setLoading(true);
    try {
      const res = await api.resetPassword(
        email.trim().toLowerCase(),
        code.trim(),
        newPassword
      );
      // Auto-login: store token and route to home
      if (res?.token && applyTokenAndUser) {
        await applyTokenAndUser(res.token, res.user);
      }
      Alert.alert("✅ Mot de passe changé", "Te voilà connecté !");
      router.replace("/(tabs)");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <Stack.Screen options={{ headerShown: false }} />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity style={styles.back} onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={26} color="#fff" />
          </TouchableOpacity>

          <Text style={styles.title}>
            {step === "email" ? "Mot de passe oublié ?" : "Nouveau mot de passe"}
          </Text>
          <Text style={styles.subtitle}>
            {step === "email"
              ? "Entre ton email, on t'envoie un code à 6 chiffres."
              : "Entre le code reçu puis ton nouveau mot de passe."}
          </Text>

          {step === "email" ? (
            <>
              <View style={styles.field}>
                <Text style={styles.label}>EMAIL</Text>
                <TextInput
                  value={email}
                  onChangeText={setEmail}
                  placeholder="email@exemple.com"
                  placeholderTextColor={theme.colors.textMuted}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  style={styles.input}
                />
              </View>

              {err && <Text style={styles.error}>{err}</Text>}

              <TouchableOpacity
                style={[styles.primary, loading && { opacity: 0.7 }]}
                onPress={requestCode}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <Text style={styles.primaryText}>Envoyer le code</Text>
                )}
              </TouchableOpacity>
            </>
          ) : (
            <>
              {/* Email sent confirmation */}
              {emailSent ? (
                <View style={styles.devBox}>
                  <Ionicons name="mail" size={22} color={theme.colors.primary} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.devLabel}>📧 Email envoyé !</Text>
                    <Text style={styles.devHint}>
                      Un code à 6 chiffres a été envoyé à{"\n"}<Text style={{color:'#fff',fontWeight:'700'}}>{email}</Text>{"\n\n"}
                      Vérifie ta boîte de réception (et le dossier <Text style={{color:theme.colors.primary,fontWeight:'700'}}>spam</Text>). Le code expire dans 30 min.
                    </Text>
                  </View>
                </View>
              ) : (
                <View style={[styles.devBox, {borderColor:'rgba(255,69,96,0.3)',backgroundColor:'rgba(255,69,96,0.08)'}]}>
                  <Ionicons name="warning" size={22} color={theme.colors.danger} />
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.devLabel,{color:theme.colors.danger}]}>Email non envoyé</Text>
                    <Text style={styles.devHint}>
                      L'email n'a pas pu être envoyé. Contacte le support pour récupérer ton code manuellement.
                    </Text>
                  </View>
                </View>
              )}

              <View style={styles.field}>
                <Text style={styles.label}>CODE À 6 CHIFFRES</Text>
                <TextInput
                  value={code}
                  onChangeText={(t) => setCode(t.replace(/[^0-9]/g, "").slice(0, 6))}
                  placeholder="••••••"
                  placeholderTextColor={theme.colors.textMuted}
                  keyboardType="number-pad"
                  maxLength={6}
                  style={[styles.input, styles.codeInput]}
                />
              </View>
              <View style={styles.field}>
                <Text style={styles.label}>NOUVEAU MOT DE PASSE</Text>
                <TextInput
                  value={newPassword}
                  onChangeText={setNewPassword}
                  placeholder="Min 6 caractères"
                  placeholderTextColor={theme.colors.textMuted}
                  secureTextEntry
                  autoCapitalize="none"
                  style={styles.input}
                />
              </View>
              <View style={styles.field}>
                <Text style={styles.label}>CONFIRMER</Text>
                <TextInput
                  value={confirmPassword}
                  onChangeText={setConfirmPassword}
                  placeholder="Retape le mot de passe"
                  placeholderTextColor={theme.colors.textMuted}
                  secureTextEntry
                  autoCapitalize="none"
                  style={styles.input}
                />
              </View>

              {err && <Text style={styles.error}>{err}</Text>}

              <TouchableOpacity
                style={[styles.primary, loading && { opacity: 0.7 }]}
                onPress={doReset}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <Text style={styles.primaryText}>Changer mon mot de passe</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.secondary}
                onPress={() => {
                  setStep("email");
                  setCode("");
                  setErr(null);
                }}
              >
                <Text style={styles.secondaryText}>Changer d'email</Text>
              </TouchableOpacity>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { padding: 24, gap: 4, paddingBottom: 60 },
  back: { width: 40, height: 40, alignItems: "center", justifyContent: "center", marginLeft: -8, marginBottom: 8 },
  title: { color: "#fff", fontSize: 28, fontWeight: "900", letterSpacing: -0.5 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 14, marginTop: 8, marginBottom: 24, lineHeight: 20 },
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
  codeInput: {
    textAlign: "center",
    letterSpacing: 12,
    fontSize: 22,
    fontWeight: "800",
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
  secondary: { marginTop: 12, alignItems: "center", padding: 12 },
  secondaryText: { color: theme.colors.textSecondary, fontSize: 13 },
  devBox: {
    flexDirection: "row",
    gap: 10,
    backgroundColor: "rgba(243,186,47,0.08)",
    borderColor: "rgba(243,186,47,0.3)",
    borderWidth: 1,
    padding: 14,
    borderRadius: 14,
    marginBottom: 16,
  },
  devLabel: { color: theme.colors.primary, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  devCode: {
    color: "#fff",
    fontSize: 26,
    fontWeight: "900",
    letterSpacing: 6,
    marginTop: 4,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  devHint: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 6, lineHeight: 16 },
});
