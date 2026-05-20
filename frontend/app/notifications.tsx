import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { theme } from "../src/theme";
import { api } from "../src/lib/api";

type NotifData = {
  symbol?: string;
  side?: string;
  qty?: number;
  price?: number;
  entry_price?: number;
  exit_price?: number;
  pnl?: number;
  pnl_pct?: number;
  reason?: string;
  is_live?: boolean;
};

type Notif = {
  id: string;
  type: string;
  title: string;
  body: string;
  data?: NotifData;
  read?: boolean;
  created_at: string;
};

export default function Notifications() {
  const router = useRouter();
  const { t } = useTranslation();
  const [items, setItems] = useState<Notif[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tgStatus, setTgStatus] = useState<{ configured: boolean } | null>(null);
  const [tgSending, setTgSending] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.notifications();
      setItems(r.items || []);
    } catch (e) {
      console.warn(e);
    }
  }, []);

  const loadTg = useCallback(async () => {
    try {
      const s = await api.telegramStatus();
      setTgStatus(s);
    } catch (e) {
      console.warn("tg status", e);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await Promise.all([load(), loadTg()]);
      setLoading(false);
    })();
  }, [load, loadTg]);

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([load(), loadTg()]);
    setRefreshing(false);
  };

  const sendTelegramTest = async () => {
    if (tgSending) return;
    setTgSending(true);
    try {
      await api.telegramTest();
      if (Platform.OS === "web") {
        window.alert("✅ Message Telegram envoyé ! Ouvre ton chat Telegram pour le voir.");
      } else {
        Alert.alert(
          "✅ Envoyé",
          "Message Telegram envoyé ! Ouvre ton chat Telegram pour le voir."
        );
      }
    } catch (e: any) {
      const msg = e?.message || "Échec d'envoi";
      if (Platform.OS === "web") {
        window.alert("❌ " + msg);
      } else {
        Alert.alert("Erreur", msg);
      }
    } finally {
      setTgSending(false);
    }
  };

  const markAll = async () => {
    try {
      await api.markAllRead();
      await load();
    } catch (e) {
      console.warn(e);
    }
  };

  const onTap = useCallback(
    async (notif: Notif) => {
      // Toggle expanded view
      setExpandedId((prev) => (prev === notif.id ? null : notif.id));
      // Mark as read silently if needed
      if (!notif.read) {
        try {
          await api.markRead(notif.id);
          // Optimistic update without full reload
          setItems((prev) => prev.map((n) => (n.id === notif.id ? { ...n, read: true } : n)));
        } catch (e) {
          console.warn(e);
        }
      }
    },
    []
  );

  const openRelated = useCallback(
    (notif: Notif) => {
      const sym = notif.data?.symbol;
      if (sym) {
        router.push(`/coin/${sym}`);
        return;
      }
      // Fallback by type
      if (notif.type?.startsWith("trade")) {
        router.push("/(tabs)/bot");
        return;
      }
      if (notif.type === "bot_status") {
        router.push("/(tabs)/bot");
        return;
      }
      if (notif.type === "premium") {
        router.push("/premium");
        return;
      }
    },
    [router]
  );

  const iconFor = (n: Notif) => {
    if (n.type === "trade_open") return { name: "rocket" as const, color: theme.colors.primary };
    if (n.type === "trade_close") {
      const pnl = n.data?.pnl ?? 0;
      if (pnl > 0) return { name: "trophy" as const, color: theme.colors.buy };
      return { name: "close-circle" as const, color: theme.colors.sell };
    }
    if (n.type === "bot_status") return { name: "construct" as const, color: theme.colors.primary };
    if (n.type === "premium") return { name: "star" as const, color: theme.colors.primary };
    return { name: "notifications" as const, color: theme.colors.textSecondary };
  };

  const fmtNum = (v: number | undefined, d = 2) =>
    v === undefined || v === null || isNaN(v) ? "—" : Number(v).toFixed(d);

  const hasOpenable = (n: Notif) => {
    if (n.data?.symbol) return true;
    return ["trade_open", "trade_close", "bot_status", "premium"].includes(n.type);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

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
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={theme.colors.primary}
          />
        }
      >
        {/* Telegram banner */}
        {tgStatus && (
          <View style={[styles.tgBanner, tgStatus.configured ? styles.tgBannerOk : styles.tgBannerWarn]}>
            <View style={styles.tgIconBox}>
              <Ionicons
                name="paper-plane"
                size={18}
                color={tgStatus.configured ? "#2AABEE" : theme.colors.textSecondary}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.tgTitle}>
                {tgStatus.configured ? "Telegram connecté" : "Telegram non configuré"}
              </Text>
              <Text style={styles.tgSub} numberOfLines={2}>
                {tgStatus.configured
                  ? "Tu recevras une alerte sur Telegram à chaque trade LIVE (achat, clôture, erreur)."
                  : "Ajoute TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans le .env du serveur pour activer."}
              </Text>
            </View>
            {tgStatus.configured && (
              <TouchableOpacity
                style={styles.tgTestBtn}
                onPress={sendTelegramTest}
                disabled={tgSending}
                testID="tg-test-btn"
                activeOpacity={0.7}
              >
                {tgSending ? (
                  <ActivityIndicator size="small" color="#0A0E27" />
                ) : (
                  <Text style={styles.tgTestBtnText}>Tester</Text>
                )}
              </TouchableOpacity>
            )}
          </View>
        )}

        {items.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="notifications-off-outline" size={36} color={theme.colors.textMuted} />
            <Text style={styles.emptyT}>{t("notifications.empty")}</Text>
            <Text style={styles.emptyS}>{t("notifications.empty_sub")}</Text>
          </View>
        ) : (
          items.map((n) => {
            const icon = iconFor(n);
            const isExpanded = expandedId === n.id;
            const canOpen = hasOpenable(n);
            const pnl = n.data?.pnl ?? 0;
            const pnlPct = n.data?.pnl_pct ?? 0;
            return (
              <View key={n.id} style={[styles.rowWrap, !n.read && styles.rowUnread]}>
                <TouchableOpacity
                  style={styles.row}
                  onPress={() => onTap(n)}
                  activeOpacity={0.85}
                  testID={`notif-${n.id}`}
                >
                  <View style={[styles.iconCircle, { backgroundColor: icon.color + "20" }]}>
                    <Ionicons name={icon.name as any} size={18} color={icon.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.notifTitle}>{n.title}</Text>
                    <Text
                      style={styles.notifBody}
                      numberOfLines={isExpanded ? undefined : 2}
                    >
                      {n.body}
                    </Text>
                    <Text style={styles.notifTime}>
                      {new Date(n.created_at).toLocaleString("fr-FR", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </Text>
                  </View>
                  <View style={styles.rightCol}>
                    {!n.read && <View style={styles.dot} />}
                    <Ionicons
                      name={isExpanded ? "chevron-up" : "chevron-down"}
                      size={16}
                      color={theme.colors.textMuted}
                      style={{ marginTop: 4 }}
                    />
                  </View>
                </TouchableOpacity>

                {isExpanded && (
                  <View style={styles.expandedBox}>
                    {/* Detail rows */}
                    {n.data?.symbol && (
                      <DetailRow label="Crypto" value={n.data.symbol} accent />
                    )}
                    {n.data?.side && (
                      <DetailRow
                        label="Type"
                        value={n.data.side === "BUY" ? "🟢 ACHAT" : "🔴 VENTE"}
                      />
                    )}
                    {n.data?.is_live !== undefined && (
                      <DetailRow
                        label="Mode"
                        value={n.data.is_live ? "🔴 LIVE (réel)" : "🧪 PAPER (simulation)"}
                      />
                    )}
                    {n.data?.entry_price !== undefined && (
                      <DetailRow label="Prix d'entrée" value={`$${fmtNum(n.data.entry_price, 4)}`} />
                    )}
                    {n.data?.exit_price !== undefined && (
                      <DetailRow label="Prix de sortie" value={`$${fmtNum(n.data.exit_price, 4)}`} />
                    )}
                    {n.data?.price !== undefined && n.data?.entry_price === undefined && (
                      <DetailRow label="Prix" value={`$${fmtNum(n.data.price, 4)}`} />
                    )}
                    {n.data?.qty !== undefined && (
                      <DetailRow label="Quantité" value={fmtNum(n.data.qty, 6)} />
                    )}
                    {n.data?.pnl !== undefined && (
                      <DetailRow
                        label="P&L"
                        value={`${pnl >= 0 ? "+" : ""}${fmtNum(pnl, 2)} USDT (${pnlPct >= 0 ? "+" : ""}${fmtNum(pnlPct, 2)}%)`}
                        valueColor={pnl >= 0 ? theme.colors.buy : theme.colors.sell}
                      />
                    )}
                    {n.data?.reason && <DetailRow label="Raison" value={n.data.reason} />}

                    {/* Action buttons */}
                    <View style={styles.actionsRow}>
                      {canOpen && (
                        <TouchableOpacity
                          onPress={() => openRelated(n)}
                          style={styles.openBtn}
                          testID={`notif-open-${n.id}`}
                        >
                          <Ionicons name="open-outline" size={16} color="#0A0E27" />
                          <Text style={styles.openBtnText}>
                            {n.data?.symbol
                              ? `Voir ${n.data.symbol}`
                              : n.type?.startsWith("trade") || n.type === "bot_status"
                              ? "Voir le Bot"
                              : "Ouvrir"}
                          </Text>
                        </TouchableOpacity>
                      )}
                      <TouchableOpacity
                        onPress={() => setExpandedId(null)}
                        style={styles.closeBtn}
                      >
                        <Text style={styles.closeBtnText}>Fermer</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                )}
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function DetailRow({
  label,
  value,
  accent,
  valueColor,
}: {
  label: string;
  value: string;
  accent?: boolean;
  valueColor?: string;
}) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text
        style={[
          styles.detailValue,
          accent && { color: theme.colors.primary, fontWeight: "900" },
          valueColor ? { color: valueColor, fontWeight: "900" } : null,
        ]}
        numberOfLines={2}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  head: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 8,
  },
  title: { color: "#fff", fontWeight: "900", fontSize: 20 },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  scroll: { padding: 20, gap: 10, paddingBottom: 40 },

  empty: { alignItems: "center", paddingVertical: 60, gap: 8 },
  emptyT: { color: "#fff", fontWeight: "800", fontSize: 16, marginTop: 8 },
  emptyS: { color: theme.colors.textSecondary, fontSize: 13, textAlign: "center", paddingHorizontal: 30 },

  rowWrap: {
    borderRadius: 16,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    overflow: "hidden",
  },
  rowUnread: { borderColor: theme.colors.primary + "55", backgroundColor: "rgba(243,186,47,0.06)" },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    padding: 14,
  },
  iconCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
  },
  notifTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  notifBody: { color: theme.colors.textSecondary, fontSize: 12, marginTop: 4, lineHeight: 17 },
  notifTime: { color: theme.colors.textMuted, fontSize: 10, marginTop: 6 },
  rightCol: { alignItems: "center" },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: theme.colors.primary },

  // Expanded box
  expandedBox: {
    padding: 14,
    paddingTop: 4,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    gap: 8,
  },
  detailRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.colors.border,
  },
  detailLabel: { color: theme.colors.textMuted, fontSize: 12, fontWeight: "600" },
  detailValue: { color: "#fff", fontSize: 13, fontWeight: "700", maxWidth: "60%", textAlign: "right" },

  actionsRow: { flexDirection: "row", gap: 10, marginTop: 12 },
  openBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    backgroundColor: theme.colors.primary,
    paddingVertical: 12,
    borderRadius: 12,
  },
  openBtnText: { color: "#0A0E27", fontWeight: "900", fontSize: 13 },
  closeBtn: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1,
    borderColor: theme.colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  closeBtnText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 13 },

  // Telegram banner
  tgBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
  },
  tgBannerOk: {
    backgroundColor: "rgba(42,171,238,0.08)",
    borderColor: "rgba(42,171,238,0.35)",
  },
  tgBannerWarn: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
  },
  tgIconBox: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(42,171,238,0.15)",
    alignItems: "center",
    justifyContent: "center",
  },
  tgTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  tgSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 3, lineHeight: 15 },
  tgTestBtn: {
    backgroundColor: theme.colors.primary,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 10,
    minWidth: 60,
    alignItems: "center",
    justifyContent: "center",
  },
  tgTestBtnText: { color: "#0A0E27", fontWeight: "900", fontSize: 12 },
});
