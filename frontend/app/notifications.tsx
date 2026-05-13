import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { theme } from "../src/theme";
import { api } from "../src/lib/api";

export default function Notifications() {
  const router = useRouter();
  const { t } = useTranslation();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.notifications();
      setItems(r.items || []);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await load();
      setLoading(false);
    })();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const markAll = async () => {
    await api.markAllRead();
    await load();
  };

  const onTap = async (notif: any) => {
    if (!notif.read) {
      await api.markRead(notif.id);
      load();
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

  const iconFor = (n: any) => {
    if (n.type === "trade_open") return { name: "rocket", color: theme.colors.primary };
    if (n.type === "trade_close") {
      const pnl = n.data?.pnl ?? 0;
      if (pnl > 0) return { name: "trophy", color: theme.colors.buy };
      return { name: "close-circle", color: theme.colors.sell };
    }
    return { name: "notifications", color: theme.colors.textSecondary };
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="notifications-screen">
      <View style={styles.head}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn} testID="notif-back-btn">
          <Ionicons name="chevron-back" size={22} color="#fff" />
        </TouchableOpacity>
        <Text style={styles.title}>{t("notifications.title")}</Text>
        <TouchableOpacity onPress={markAll} style={styles.iconBtn} testID="notif-mark-all">
          <Ionicons name="checkmark-done" size={18} color="#fff" />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />}
      >
        {items.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="notifications-off-outline" size={36} color={theme.colors.textMuted} />
            <Text style={styles.emptyT}>{t("notifications.empty")}</Text>
            <Text style={styles.emptyS}>{t("notifications.empty_sub")}</Text>
          </View>
        ) : (
          items.map((n) => {
            const icon = iconFor(n);
            return (
              <TouchableOpacity
                key={n.id}
                style={[styles.row, !n.read && styles.rowUnread]}
                onPress={() => onTap(n)}
                activeOpacity={0.85}
                testID={`notif-${n.id}`}
              >
                <View style={[styles.iconCircle, { backgroundColor: icon.color + "20" }]}>
                  <Ionicons name={icon.name as any} size={18} color={icon.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.notifTitle}>{n.title}</Text>
                  <Text style={styles.notifBody}>{n.body}</Text>
                  <Text style={styles.notifTime}>
                    {new Date(n.created_at).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </Text>
                </View>
                {!n.read && <View style={styles.dot} />}
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 20, paddingTop: 8 },
  title: { color: "#fff", fontWeight: "900", fontSize: 20 },
  iconBtn: {
    width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  scroll: { padding: 20, gap: 10, paddingBottom: 40 },

  empty: { alignItems: "center", paddingVertical: 60, gap: 8 },
  emptyT: { color: "#fff", fontWeight: "800", fontSize: 16, marginTop: 8 },
  emptyS: { color: theme.colors.textSecondary, fontSize: 13, textAlign: "center", paddingHorizontal: 30 },

  row: {
    flexDirection: "row", alignItems: "flex-start", gap: 12,
    padding: 14, borderRadius: 16,
    backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1,
  },
  rowUnread: { borderColor: theme.colors.primary + "55", backgroundColor: "rgba(243,186,47,0.04)" },
  iconCircle: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center" },
  notifTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  notifBody: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 4, lineHeight: 17 },
  notifTime: { color: theme.colors.textMuted, fontSize: 10, marginTop: 6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: theme.colors.primary, marginTop: 6 },
});
