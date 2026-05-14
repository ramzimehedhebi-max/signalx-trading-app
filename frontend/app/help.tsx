import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { theme } from "../src/theme";

export default function HelpScreen() {
  const router = useRouter();
  const { t } = useTranslation();

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="help-screen">
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="help-back-btn">
          <Ionicons name="chevron-back" color="#fff" size={20} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t("help.title")}</Text>
        <View style={{ width: 42 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* HERO */}
        <View style={styles.hero}>
          <Text style={styles.heroEmoji}>📘</Text>
          <Text style={styles.heroTitle}>{t("help.hero_title")}</Text>
          <Text style={styles.heroSub}>{t("help.hero_sub")}</Text>
        </View>

        {/* SAFETY BANNER */}
        <View style={styles.safetyBanner}>
          <Ionicons name="shield-checkmark" size={20} color={theme.colors.buy} />
          <View style={{ flex: 1 }}>
            <Text style={styles.safetyTitle}>{t("help.safety_title")}</Text>
            <Text style={styles.safetyText}>{t("help.safety_text")}</Text>
          </View>
        </View>

        {/* SECTION 1: ACCOUNT */}
        <Section emoji="📝" title={t("help.s1.title")}>
          <Step n="1" title={t("help.s1.step1_t")} text={t("help.s1.step1_d")} />
          <Step n="2" title={t("help.s1.step2_t")} text={t("help.s1.step2_d")} />
          <Step n="3" title={t("help.s1.step3_t")} text={t("help.s1.step3_d")} />
        </Section>

        {/* SECTION 2: DEPOSIT MONEY ON BINANCE */}
        <Section emoji="💰" title={t("help.s2.title")}>
          <Text style={styles.intro}>{t("help.s2.intro")}</Text>

          <SubSection icon="card" color="#F0B90B" title={t("help.s2.opt1_t")} desc={t("help.s2.opt1_d")} />
          <SubSection icon="business" color={theme.colors.buy} title={t("help.s2.opt2_t")} desc={t("help.s2.opt2_d")} />
          <SubSection icon="logo-bitcoin" color={theme.colors.primary} title={t("help.s2.opt3_t")} desc={t("help.s2.opt3_d")} />

          <View style={styles.tipBox}>
            <Ionicons name="bulb" size={16} color={theme.colors.primary} />
            <Text style={styles.tipText}>{t("help.s2.tip")}</Text>
          </View>

          <TouchableOpacity
            onPress={() => Linking.openURL("https://accounts.binance.com/register")}
            style={styles.linkBtn}
            testID="help-open-binance"
          >
            <Ionicons name="open-outline" size={16} color={theme.colors.primary} />
            <Text style={styles.linkBtnText}>{t("help.s2.open_binance")}</Text>
          </TouchableOpacity>
        </Section>

        {/* SECTION 3: CONVERT TO USDT */}
        <Section emoji="🔄" title={t("help.s3.title")}>
          <Text style={styles.intro}>{t("help.s3.intro")}</Text>
          <Step n="1" title={t("help.s3.step1_t")} text={t("help.s3.step1_d")} />
          <Step n="2" title={t("help.s3.step2_t")} text={t("help.s3.step2_d")} />
          <Step n="3" title={t("help.s3.step3_t")} text={t("help.s3.step3_d")} />
        </Section>

        {/* SECTION 4: CONNECT API */}
        <Section emoji="🔗" title={t("help.s4.title")}>
          <Text style={styles.intro}>{t("help.s4.intro")}</Text>
          <Step n="1" title={t("help.s4.step1_t")} text={t("help.s4.step1_d")} />
          <Step n="2" title={t("help.s4.step2_t")} text={t("help.s4.step2_d")} />
          <Step n="3" title={t("help.s4.step3_t")} text={t("help.s4.step3_d")} />

          <View style={styles.dangerBox}>
            <Ionicons name="warning" size={18} color={theme.colors.danger} />
            <Text style={styles.dangerText}>{t("help.s4.warning")}</Text>
          </View>

          <TouchableOpacity
            onPress={() => router.push("/binance-connect")}
            style={styles.primaryBtn}
            testID="help-open-binance-connect"
          >
            <Ionicons name="key" size={16} color="#000" />
            <Text style={styles.primaryBtnText}>{t("help.s4.cta")}</Text>
          </TouchableOpacity>
        </Section>

        {/* SECTION 5: CONFIGURE BOT */}
        <Section emoji="⚙️" title={t("help.s5.title")}>
          <Text style={styles.intro}>{t("help.s5.intro")}</Text>

          <View style={styles.modeBlock}>
            <View style={[styles.modePill, { backgroundColor: theme.colors.primary + "22", borderColor: theme.colors.primary + "60" }]}>
              <Text style={[styles.modePillText, { color: theme.colors.primary }]}>{t("help.s5.paper_label")}</Text>
            </View>
            <Text style={styles.modeText}>{t("help.s5.paper_desc")}</Text>
          </View>

          <View style={styles.modeBlock}>
            <View style={[styles.modePill, { backgroundColor: theme.colors.danger + "22", borderColor: theme.colors.danger + "60" }]}>
              <Text style={[styles.modePillText, { color: theme.colors.danger }]}>{t("help.s5.live_label")}</Text>
            </View>
            <Text style={styles.modeText}>{t("help.s5.live_desc")}</Text>
          </View>

          <Text style={styles.subTitle}>{t("help.s5.recommended")}</Text>
          <Bullet text={t("help.s5.rec1")} />
          <Bullet text={t("help.s5.rec2")} />
          <Bullet text={t("help.s5.rec3")} />
          <Bullet text={t("help.s5.rec4")} />
          <Bullet text={t("help.s5.rec5")} />
        </Section>

        {/* SECTION 6: MONITOR */}
        <Section emoji="📊" title={t("help.s6.title")}>
          <Bullet text={t("help.s6.b1")} />
          <Bullet text={t("help.s6.b2")} />
          <Bullet text={t("help.s6.b3")} />
        </Section>

        {/* SECTION 7: WITHDRAW */}
        <Section emoji="💸" title={t("help.s7.title")}>
          <View style={styles.tipBox}>
            <Ionicons name="information-circle" size={18} color={theme.colors.primary} />
            <Text style={styles.tipText}>{t("help.s7.reminder")}</Text>
          </View>
          <Step n="1" title={t("help.s7.step1_t")} text={t("help.s7.step1_d")} />
          <Step n="2" title={t("help.s7.step2_t")} text={t("help.s7.step2_d")} />
          <Step n="3" title={t("help.s7.step3_t")} text={t("help.s7.step3_d")} />
          <Step n="4" title={t("help.s7.step4_t")} text={t("help.s7.step4_d")} />

          <Text style={styles.subTitle}>{t("help.s7.stop_title")}</Text>
          <Text style={styles.body}>{t("help.s7.stop_desc")}</Text>
        </Section>

        {/* SECTION 8: SECURITY */}
        <Section emoji="🛡️" title={t("help.s8.title")}>
          <Bullet text={t("help.s8.b1")} danger />
          <Bullet text={t("help.s8.b2")} />
          <Bullet text={t("help.s8.b3")} danger />
          <Bullet text={t("help.s8.b4")} />
          <Bullet text={t("help.s8.b5")} />
        </Section>

        {/* FAQ */}
        <Section emoji="❓" title={t("help.faq.title")}>
          <Faq q={t("help.faq.q1")} a={t("help.faq.a1")} />
          <Faq q={t("help.faq.q2")} a={t("help.faq.a2")} />
          <Faq q={t("help.faq.q3")} a={t("help.faq.a3")} />
          <Faq q={t("help.faq.q4")} a={t("help.faq.a4")} />
          <Faq q={t("help.faq.q5")} a={t("help.faq.a5")} />
        </Section>

        {/* SUPPORT */}
        <Section emoji="📞" title={t("help.contact.title")}>
          <Text style={styles.body}>{t("help.contact.text")}</Text>
          <TouchableOpacity
            onPress={() => Linking.openURL("mailto:support@signall.app")}
            style={styles.linkBtn}
            testID="help-email-support"
          >
            <Ionicons name="mail" size={16} color={theme.colors.primary} />
            <Text style={styles.linkBtnText}>support@signall.app</Text>
          </TouchableOpacity>
        </Section>

        <Text style={styles.footer}>{t("help.footer")}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ emoji, title, children }: { emoji: string; title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>
        <Text style={{ fontSize: 18 }}>{emoji}</Text>  {title}
      </Text>
      <View style={styles.sectionBody}>{children}</View>
    </View>
  );
}

function Step({ n, title, text }: { n: string; title: string; text: string }) {
  return (
    <View style={styles.step}>
      <View style={styles.stepNum}><Text style={styles.stepNumText}>{n}</Text></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.stepTitle}>{title}</Text>
        <Text style={styles.stepText}>{text}</Text>
      </View>
    </View>
  );
}

function SubSection({ icon, color, title, desc }: { icon: any; color: string; title: string; desc: string }) {
  return (
    <View style={styles.sub}>
      <View style={[styles.subIcon, { backgroundColor: color + "22" }]}>
        <Ionicons name={icon} size={18} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.subTitleInline}>{title}</Text>
        <Text style={styles.subDesc}>{desc}</Text>
      </View>
    </View>
  );
}

function Bullet({ text, danger }: { text: string; danger?: boolean }) {
  return (
    <View style={styles.bullet}>
      <Ionicons
        name={danger ? "close-circle" : "checkmark-circle"}
        size={16}
        color={danger ? theme.colors.danger : theme.colors.buy}
      />
      <Text style={styles.bulletText}>{text}</Text>
    </View>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <View style={styles.faq}>
      <Text style={styles.faqQ}>Q. {q}</Text>
      <Text style={styles.faqA}>{a}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  headerRow: { flexDirection: "row", alignItems: "center", padding: 24, paddingBottom: 8 },
  headerTitle: { flex: 1, textAlign: "center", color: "#fff", fontSize: 18, fontWeight: "800" },
  iconBtn: {
    width: 42, height: 42, borderRadius: 14,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
    alignItems: "center", justifyContent: "center",
  },
  scroll: { padding: 24, paddingTop: 4, gap: 18, paddingBottom: 60 },

  hero: { alignItems: "center", paddingVertical: 16 },
  heroEmoji: { fontSize: 48, marginBottom: 8 },
  heroTitle: { color: "#fff", fontSize: 22, fontWeight: "900", letterSpacing: -0.5, textAlign: "center" },
  heroSub: { color: theme.colors.textSecondary, fontSize: 14, marginTop: 8, textAlign: "center", lineHeight: 20 },

  safetyBanner: {
    flexDirection: "row", alignItems: "flex-start", gap: 10,
    padding: 14, borderRadius: 14,
    backgroundColor: theme.colors.buy + "12",
    borderColor: theme.colors.buy + "30", borderWidth: 1,
  },
  safetyTitle: { color: theme.colors.buy, fontWeight: "800", fontSize: 13 },
  safetyText: { color: "#fff", fontSize: 12, marginTop: 4, lineHeight: 17 },

  section: {
    padding: 18, borderRadius: 18,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  sectionTitle: { color: "#fff", fontSize: 16, fontWeight: "900", marginBottom: 14 },
  sectionBody: { gap: 10 },

  intro: { color: theme.colors.textSecondary, fontSize: 13, lineHeight: 19, marginBottom: 4 },
  body: { color: "#fff", fontSize: 13, lineHeight: 19 },

  step: { flexDirection: "row", gap: 12, alignItems: "flex-start", paddingVertical: 4 },
  stepNum: {
    width: 26, height: 26, borderRadius: 8,
    backgroundColor: theme.colors.primary + "22",
    alignItems: "center", justifyContent: "center",
  },
  stepNumText: { color: theme.colors.primary, fontSize: 12, fontWeight: "900" },
  stepTitle: { color: "#fff", fontSize: 13, fontWeight: "800" },
  stepText: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 3, lineHeight: 18 },

  sub: { flexDirection: "row", gap: 12, paddingVertical: 8 },
  subIcon: {
    width: 36, height: 36, borderRadius: 10,
    alignItems: "center", justifyContent: "center",
  },
  subTitleInline: { color: "#fff", fontSize: 13, fontWeight: "800" },
  subDesc: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 3, lineHeight: 17 },

  tipBox: {
    flexDirection: "row", gap: 10, alignItems: "flex-start",
    padding: 12, borderRadius: 12,
    backgroundColor: theme.colors.primary + "15",
    borderColor: theme.colors.primary + "30", borderWidth: 1,
    marginTop: 6,
  },
  tipText: { color: "#fff", fontSize: 12, flex: 1, lineHeight: 17 },

  dangerBox: {
    flexDirection: "row", gap: 10, alignItems: "flex-start",
    padding: 12, borderRadius: 12,
    backgroundColor: theme.colors.danger + "15",
    borderColor: theme.colors.danger + "40", borderWidth: 1,
    marginTop: 6,
  },
  dangerText: { color: "#fff", fontSize: 12, flex: 1, lineHeight: 17, fontWeight: "600" },

  linkBtn: {
    flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center",
    paddingVertical: 11, paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.primary + "40", borderWidth: 1,
    marginTop: 8,
  },
  linkBtnText: { color: theme.colors.primary, fontWeight: "800", fontSize: 12 },

  primaryBtn: {
    flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center",
    paddingVertical: 13,
    borderRadius: 999,
    backgroundColor: theme.colors.primary,
    marginTop: 10,
  },
  primaryBtnText: { color: "#000", fontWeight: "900", fontSize: 13 },

  modeBlock: { marginBottom: 14 },
  modePill: {
    alignSelf: "flex-start",
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999,
    borderWidth: 1, marginBottom: 6,
  },
  modePillText: { fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  modeText: { color: "#fff", fontSize: 12, lineHeight: 17 },

  subTitle: { color: "#fff", fontSize: 13, fontWeight: "900", marginTop: 8, marginBottom: 4 },

  bullet: { flexDirection: "row", gap: 10, alignItems: "flex-start", paddingVertical: 3 },
  bulletText: { color: "#fff", fontSize: 12, flex: 1, lineHeight: 17 },

  faq: { paddingVertical: 8, borderBottomColor: theme.colors.border, borderBottomWidth: 0.5 },
  faqQ: { color: "#fff", fontSize: 13, fontWeight: "800" },
  faqA: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 4, lineHeight: 17 },

  footer: { color: theme.colors.textMuted, fontSize: 11, textAlign: "center", marginTop: 12, marginBottom: 20, lineHeight: 16 },
});
