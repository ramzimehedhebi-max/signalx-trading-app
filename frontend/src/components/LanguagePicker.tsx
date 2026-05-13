import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGS, LangCode, changeLanguage } from "../i18n";
import { theme } from "../theme";

const FLAGS: Record<LangCode, string> = {
  fr: "🇫🇷",
  en: "🇬🇧",
  ar: "🇸🇦",
  es: "🇪🇸",
  de: "🇩🇪",
  it: "🇮🇹",
  pt: "🇧🇷",
  zh: "🇨🇳",
};

export function LanguagePickerRow() {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const current = (i18n.language || "fr") as LangCode;

  const onSelect = useCallback(async (lng: LangCode) => {
    await changeLanguage(lng);
    setOpen(false);
  }, []);

  return (
    <>
      <TouchableOpacity
        style={styles.row}
        onPress={() => setOpen(true)}
        activeOpacity={0.7}
      >
        <View style={styles.iconWrap}>
          <Ionicons name="language" size={20} color={theme.colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>{t("profile.language")}</Text>
          <Text style={styles.value}>
            {FLAGS[current]} {t(`languages.${current}` as any)}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={theme.colors.textMuted} />
      </TouchableOpacity>

      <Modal
        visible={open}
        animationType="slide"
        transparent
        onRequestClose={() => setOpen(false)}
      >
        <View style={styles.modalBackdrop}>
          <TouchableOpacity
            style={{ flex: 1 }}
            activeOpacity={1}
            onPress={() => setOpen(false)}
          />
          <View style={styles.sheet}>
            <View style={styles.handle} />
            <Text style={styles.sheetTitle}>{t("languages.title")}</Text>

            <ScrollView style={{ maxHeight: 480 }} showsVerticalScrollIndicator={false}>
              {SUPPORTED_LANGS.map((lng) => {
                const selected = lng === current;
                return (
                  <TouchableOpacity
                    key={lng}
                    style={[styles.langRow, selected && styles.langRowActive]}
                    onPress={() => onSelect(lng)}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.flag}>{FLAGS[lng]}</Text>
                    <Text style={[styles.langName, selected && styles.langNameActive]}>
                      {t(`languages.${lng}` as any)}
                    </Text>
                    {selected && (
                      <Ionicons
                        name="checkmark-circle"
                        size={22}
                        color={theme.colors.primary}
                      />
                    )}
                  </TouchableOpacity>
                );
              })}
              <View style={{ height: 16 }} />
            </ScrollView>

            <TouchableOpacity
              style={styles.closeBtn}
              onPress={() => setOpen(false)}
            >
              <Text style={styles.closeBtnText}>{t("common.close")}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    backgroundColor: theme.colors.surface,
    borderRadius: 14,
    borderColor: theme.colors.border,
    borderWidth: 1,
    marginVertical: 6,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: theme.colors.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  label: { color: theme.colors.textSecondary, fontSize: 11, fontWeight: "700", letterSpacing: 1 },
  value: { color: "#fff", fontSize: 14, fontWeight: "700", marginTop: 2 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: theme.colors.bg,
    borderTopLeftRadius: 26,
    borderTopRightRadius: 26,
    padding: 20,
    paddingBottom: Platform.OS === "ios" ? 36 : 20,
    borderTopWidth: 1,
    borderColor: theme.colors.border,
  },
  handle: {
    alignSelf: "center",
    width: 50,
    height: 4,
    borderRadius: 2,
    backgroundColor: theme.colors.border,
    marginBottom: 14,
  },
  sheetTitle: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "900",
    textAlign: "center",
    marginBottom: 16,
  },
  langRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderRadius: 14,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    marginBottom: 8,
  },
  langRowActive: {
    borderColor: theme.colors.primary,
    backgroundColor: "rgba(243,186,47,0.08)",
  },
  flag: { fontSize: 26 },
  langName: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "600",
    flex: 1,
  },
  langNameActive: { color: "#fff", fontWeight: "800" },
  closeBtn: {
    marginTop: 8,
    backgroundColor: theme.colors.surface,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  closeBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
});
