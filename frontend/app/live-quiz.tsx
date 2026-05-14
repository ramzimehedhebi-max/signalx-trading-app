import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import * as Haptics from "expo-haptics";
import { theme } from "../src/theme";
import { api } from "../src/lib/api";

type Choice = { key: "a" | "b" | "c"; isCorrect: boolean };
type Question = { id: number; choices: Choice[] };

// 5 questions with correct answer key embedded
const QUESTIONS: Question[] = [
  { id: 1, choices: [{ key: "a", isCorrect: false }, { key: "b", isCorrect: true }, { key: "c", isCorrect: false }] },
  { id: 2, choices: [{ key: "a", isCorrect: false }, { key: "b", isCorrect: false }, { key: "c", isCorrect: true }] },
  { id: 3, choices: [{ key: "a", isCorrect: true }, { key: "b", isCorrect: false }, { key: "c", isCorrect: false }] },
  { id: 4, choices: [{ key: "a", isCorrect: false }, { key: "b", isCorrect: true }, { key: "c", isCorrect: false }] },
  { id: 5, choices: [{ key: "a", isCorrect: false }, { key: "b", isCorrect: true }, { key: "c", isCorrect: false }] },
];

export default function LiveQuiz() {
  const router = useRouter();
  const { t } = useTranslation();
  const params = useLocalSearchParams<{ cap?: string }>();
  const [step, setStep] = useState(0); // 0..4 = question index ; 5 = result
  const [answers, setAnswers] = useState<("a" | "b" | "c" | null)[]>([null, null, null, null, null]);
  const [submitting, setSubmitting] = useState(false);

  const q = QUESTIONS[step];
  const current = answers[step];

  const choose = (key: "a" | "b" | "c") => {
    Haptics.selectionAsync();
    const next = [...answers];
    next[step] = key;
    setAnswers(next);
  };

  const nextQuestion = () => {
    if (step < 4) {
      setStep(step + 1);
    } else {
      setStep(5);
    }
  };

  const correctCount = answers.reduce<number>((acc, a, i) => {
    if (!a) return acc;
    const c = QUESTIONS[i].choices.find((x) => x.key === a);
    return acc + (c?.isCorrect ? 1 : 0);
  }, 0);

  const passed = correctCount === 5;

  const enableLive = async () => {
    setSubmitting(true);
    try {
      await api.botUpdateConfig({ live_mode: true });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Alert.alert(
        t("quiz.activated_title"),
        t("quiz.activated_msg", { cap: params.cap || "50" }),
        [{ text: "OK", onPress: () => router.replace("/(tabs)/bot") }]
      );
    } catch (e: any) {
      Alert.alert(t("common.error"), e?.message || "");
    } finally {
      setSubmitting(false);
    }
  };

  // ===== RESULT SCREEN =====
  if (step === 5) {
    return (
      <SafeAreaView style={styles.safe} edges={["top", "bottom"]} testID="quiz-result-screen">
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="quiz-close-btn">
            <Ionicons name="close" color="#fff" size={20} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>{t("quiz.result")}</Text>
          <View style={{ width: 42 }} />
        </View>

        <ScrollView contentContainerStyle={styles.resultScroll}>
          <View style={styles.scoreBig}>
            <Text style={[styles.scoreNum, { color: passed ? theme.colors.buy : theme.colors.danger }]}>
              {correctCount}/5
            </Text>
            <Text style={styles.scoreText}>
              {passed ? t("quiz.score_perfect") : t("quiz.score_retry")}
            </Text>
          </View>

          {/* Recap each question */}
          <View style={styles.recap}>
            {QUESTIONS.map((qq, i) => {
              const ans = answers[i];
              const c = qq.choices.find((x) => x.key === ans);
              const ok = c?.isCorrect;
              return (
                <View key={qq.id} style={styles.recapRow}>
                  <Ionicons
                    name={ok ? "checkmark-circle" : "close-circle"}
                    size={18}
                    color={ok ? theme.colors.buy : theme.colors.danger}
                  />
                  <Text style={styles.recapText}>
                    Q{i + 1}: {t(`quiz.q${qq.id}.title`)}
                  </Text>
                </View>
              );
            })}
          </View>

          {passed ? (
            <>
              <View style={styles.successBox}>
                <Ionicons name="trophy" size={20} color={theme.colors.buy} />
                <Text style={styles.successText}>{t("quiz.unlock_desc")}</Text>
              </View>
              <TouchableOpacity
                onPress={enableLive}
                disabled={submitting}
                style={[styles.cta, submitting && { opacity: 0.7 }]}
                testID="quiz-activate-live-btn"
                activeOpacity={0.85}
              >
                <Ionicons name="flash" size={18} color="#000" />
                <Text style={styles.ctaText}>{t("quiz.activate_live")}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.back()} style={styles.ghost} testID="quiz-cancel-btn">
                <Text style={styles.ghostText}>{t("common.cancel")}</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <View style={styles.warnBox}>
                <Ionicons name="book" size={20} color={theme.colors.primary} />
                <Text style={styles.warnText}>{t("quiz.retry_desc")}</Text>
              </View>
              <TouchableOpacity
                onPress={() => { setAnswers([null, null, null, null, null]); setStep(0); }}
                style={[styles.cta, { backgroundColor: theme.colors.primary }]}
                testID="quiz-retry-btn"
              >
                <Ionicons name="refresh" size={18} color="#000" />
                <Text style={styles.ctaText}>{t("quiz.retry")}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.replace("/help")} style={styles.ghost} testID="quiz-go-help-btn">
                <Ionicons name="book-outline" size={14} color={theme.colors.primary} />
                <Text style={styles.ghostText}>{t("quiz.read_help")}</Text>
              </TouchableOpacity>
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ===== QUESTION SCREEN =====
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]} testID="quiz-screen">
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="quiz-close-btn">
          <Ionicons name="close" color="#fff" size={20} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("quiz.title")}</Text>
        <Text style={styles.progress}>{step + 1}/5</Text>
      </View>

      <View style={styles.progressBar}>
        <View style={[styles.progressFill, { width: `${((step + 1) / 5) * 100}%` }]} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.questionLabel}>{t("quiz.question_n", { n: step + 1 })}</Text>
        <Text style={styles.questionText}>{t(`quiz.q${q.id}.title`)}</Text>

        <View style={styles.choices}>
          {q.choices.map((c) => {
            const selected = current === c.key;
            return (
              <TouchableOpacity
                key={c.key}
                onPress={() => choose(c.key)}
                style={[styles.choice, selected && styles.choiceActive]}
                testID={`quiz-choice-${c.key}`}
                activeOpacity={0.85}
              >
                <View style={[styles.choiceLetter, selected && { backgroundColor: theme.colors.primary }]}>
                  <Text style={[styles.choiceLetterText, selected && { color: "#000" }]}>{c.key.toUpperCase()}</Text>
                </View>
                <Text style={[styles.choiceText, selected && { color: "#fff", fontWeight: "800" }]}>
                  {t(`quiz.q${q.id}.${c.key}`)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <TouchableOpacity
          onPress={nextQuestion}
          disabled={!current}
          style={[styles.cta, !current && { opacity: 0.4 }]}
          testID="quiz-next-btn"
          activeOpacity={0.85}
        >
          <Text style={styles.ctaText}>{step < 4 ? t("quiz.next") : t("quiz.see_result")}</Text>
          <Ionicons name="arrow-forward" size={18} color="#000" />
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  header: { flexDirection: "row", alignItems: "center", padding: 24, paddingBottom: 8 },
  headerTitle: { flex: 1, textAlign: "center", color: "#fff", fontSize: 16, fontWeight: "800" },
  progress: { width: 42, color: theme.colors.primary, fontWeight: "800", textAlign: "right" },
  iconBtn: {
    width: 42, height: 42, borderRadius: 14,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
    alignItems: "center", justifyContent: "center",
  },
  progressBar: { height: 4, marginHorizontal: 24, backgroundColor: theme.colors.surface, borderRadius: 2, overflow: "hidden" },
  progressFill: { height: 4, backgroundColor: theme.colors.primary, borderRadius: 2 },
  scroll: { padding: 24, paddingTop: 24 },

  questionLabel: { color: theme.colors.primary, fontSize: 11, fontWeight: "900", letterSpacing: 1.5 },
  questionText: { color: "#fff", fontSize: 20, fontWeight: "900", marginTop: 10, lineHeight: 28, letterSpacing: -0.3 },

  choices: { gap: 12, marginTop: 28 },
  choice: {
    flexDirection: "row", alignItems: "center", gap: 14, padding: 16,
    borderRadius: 18, backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1.5,
  },
  choiceActive: { borderColor: theme.colors.primary, backgroundColor: theme.colors.primary + "12" },
  choiceLetter: {
    width: 34, height: 34, borderRadius: 12,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
    alignItems: "center", justifyContent: "center",
  },
  choiceLetterText: { color: "#fff", fontWeight: "900" },
  choiceText: { color: theme.colors.textSecondary, fontSize: 14, flex: 1, lineHeight: 19 },

  cta: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    paddingVertical: 16, borderRadius: 999,
    backgroundColor: theme.colors.buy, marginTop: 24,
  },
  ctaText: { color: "#000", fontSize: 15, fontWeight: "900" },

  resultScroll: { padding: 24 },
  scoreBig: { alignItems: "center", paddingVertical: 32 },
  scoreNum: { fontSize: 72, fontWeight: "900", letterSpacing: -2 },
  scoreText: { color: "#fff", fontSize: 17, fontWeight: "800", marginTop: 8, textAlign: "center" },

  recap: {
    padding: 18, borderRadius: 16,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
    gap: 10, marginBottom: 18,
  },
  recapRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  recapText: { color: "#fff", fontSize: 12, flex: 1, lineHeight: 17 },

  successBox: {
    flexDirection: "row", gap: 12, padding: 16, borderRadius: 16,
    backgroundColor: theme.colors.buy + "15", borderColor: theme.colors.buy + "40", borderWidth: 1,
    marginBottom: 14,
  },
  successText: { color: "#fff", fontSize: 13, flex: 1, lineHeight: 18 },
  warnBox: {
    flexDirection: "row", gap: 12, padding: 16, borderRadius: 16,
    backgroundColor: theme.colors.primary + "15", borderColor: theme.colors.primary + "40", borderWidth: 1,
    marginBottom: 14,
  },
  warnText: { color: "#fff", fontSize: 13, flex: 1, lineHeight: 18 },

  ghost: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 14, marginTop: 8 },
  ghostText: { color: theme.colors.primary, fontWeight: "800", fontSize: 13 },
});
