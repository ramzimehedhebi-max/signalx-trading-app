import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { theme, fmtPrice, fmtPct, symbolToBase } from "../../src/theme";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/contexts/AuthContext";
import MiniChart from "../../src/components/MiniChart";

type Ticker = {
  symbol: string;
  lastPrice: number;
  priceChangePercent: number;
  priceChange: number;
  volume: number;
  quoteVolume: number;
};

function NotifBell() {
  const router = useRouter();
  const [count, setCount] = useState(0);
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const r = await api.unreadCount();
        if (mounted) setCount(r.unread || 0);
      } catch {}
    };
    load();
    const id = setInterval(load, 20000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);
  return (
    <TouchableOpacity
      style={styles.bell}
      onPress={() => router.push("/notifications")}
      testID="notif-bell-btn"
    >
      <Ionicons name="notifications-outline" size={20} color="#fff" />
      {count > 0 && (
        <View style={styles.bellBadge}>
          <Text style={styles.bellBadgeText}>{count > 9 ? "9+" : String(count)}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const router = useRouter();
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [watch, setWatch] = useState<any[]>([]);
  const [sparks, setSparks] = useState<Record<string, number[]>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {    try {
      const [t, w] = await Promise.all([api.tickers(), api.watchlist().catch(() => [])]);
      setTickers(t);
      setWatch(w);
      // load sparks for top 4
      const top = t.slice(0, 4);
      const spark: Record<string, number[]> = {};
      await Promise.all(
        top.map(async (item: Ticker) => {
          try {
            const k = await api.klines(item.symbol, "1h", 24);
            spark[item.symbol] = k.map((x: any) => x.close);
          } catch {}
        })
      );
      setSparks(spark);
    } catch (e) {
      console.warn("Dashboard load error", e);
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

  const topMovers = [...tickers].sort(
    (a, b) => Math.abs(b.priceChangePercent) - Math.abs(a.priceChangePercent)
  );

  const watchSymbols = new Set(watch.map((w) => w.symbol));
  const watchTickers = tickers.filter((t) => watchSymbols.has(t.symbol));

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="dashboard-screen">
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
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>{t("home.greeting", { name: user?.name?.split(" ")[0] || "trader" })}</Text>
            <Text style={styles.headerSub}>Voici ton cockpit du jour</Text>
          </View>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <NotifBell />
            <TouchableOpacity
              style={styles.aiBadge}
              onPress={() => router.push("/(tabs)/signals")}
              testID="header-ai-btn"
            >
              <Ionicons name="sparkles" size={14} color={theme.colors.primary} />
              <Text style={styles.aiBadgeText}>IA</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* AI Hero */}
        <TouchableOpacity
          style={styles.aiHero}
          onPress={() => router.push("/(tabs)/signals")}
          activeOpacity={0.9}
          testID="ai-hero-btn"
        >
          <View style={styles.aiHeroGlow} />
          <View style={styles.aiHeroLeft}>
            <View style={styles.aiPill}>
              <View style={styles.dot} />
              <Text style={styles.aiPillText}>CLAUDE SONNET 4.5</Text>
            </View>
            <Text style={styles.aiTitle}>{t("home.ai_pick_buy")}</Text>
            <Text style={styles.aiSubtitle}>
              Génère un signal d&apos;achat / vente sur n&apos;importe quelle paire en quelques secondes.
            </Text>
            <View style={styles.aiCta}>
              <Text style={styles.aiCtaText}>Lancer l&apos;analyse</Text>
              <Ionicons name="arrow-forward" size={14} color={theme.colors.primary} />
            </View>
          </View>
        </TouchableOpacity>

        {/* Prediction CTA */}
        <TouchableOpacity
          style={styles.predictCard}
          onPress={() => router.push("/predict")}
          activeOpacity={0.85}
          testID="predict-cta-btn"
        >
          <View style={styles.predictLeft}>
            <View style={styles.predictIcon}>
              <Ionicons name="telescope" size={20} color={theme.colors.primary} />
            </View>
            <View>
              <Text style={styles.predictTitle}>🔮 Prédictions IA</Text>
              <Text style={styles.predictSub}>Top opportunités 24h / 3J / 7J</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" color={theme.colors.textMuted} size={20} />
        </TouchableOpacity>

        {/* Watchlist */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>{t("home.watchlist")}</Text>
          <TouchableOpacity onPress={() => router.push("/(tabs)/markets")} testID="watchlist-add-btn">
            <Text style={styles.linkText}>Ajouter +</Text>
          </TouchableOpacity>
        </View>

        {watchTickers.length === 0 ? (
          <View style={styles.emptyCard}>
            <Ionicons name="star-outline" color={theme.colors.textMuted} size={28} />
            <Text style={styles.emptyText}>Aucune crypto en favoris</Text>
            <Text style={styles.emptySub}>
              Ajoute des paires depuis l&apos;onglet Marchés pour les suivre ici.
            </Text>
          </View>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingRight: 24, gap: 12 }}
          >
            {watchTickers.map((t) => (
              <TouchableOpacity
                key={t.symbol}
                style={styles.watchCard}
                onPress={() => router.push({ pathname: "/coin/[symbol]", params: { symbol: t.symbol } })}
                activeOpacity={0.85}
                testID={`watch-card-${t.symbol}`}
              >
                <View style={styles.watchRow}>
                  <Text style={styles.watchSym}>{symbolToBase(t.symbol)}</Text>
                  <View
                    style={[
                      styles.changePill,
                      { backgroundColor: t.priceChangePercent >= 0 ? "rgba(0,227,150,0.12)" : "rgba(255,69,96,0.12)" },
                    ]}
                  >
                    <Text
                      style={[
                        styles.changePillText,
                        { color: t.priceChangePercent >= 0 ? theme.colors.buy : theme.colors.sell },
                      ]}
                    >
                      {fmtPct(t.priceChangePercent)}
                    </Text>
                  </View>
                </View>
                <Text style={styles.watchPrice}>${fmtPrice(t.lastPrice)}</Text>
                <Text style={styles.watchPair}>{t.symbol}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}

        {/* Top movers (with sparkline for top 4) */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>{t("home.movers")}</Text>
          <Text style={styles.labelMuted}>24H</Text>
        </View>
        <View style={styles.bento}>
          {topMovers.slice(0, 4).map((t) => (
            <TouchableOpacity
              key={t.symbol}
              style={styles.bentoCard}
              onPress={() => router.push({ pathname: "/coin/[symbol]", params: { symbol: t.symbol } })}
              activeOpacity={0.85}
              testID={`mover-card-${t.symbol}`}
            >
              <View style={styles.bentoTop}>
                <View>
                  <Text style={styles.watchSym}>{symbolToBase(t.symbol)}</Text>
                  <Text style={styles.watchPair}>{t.symbol}</Text>
                </View>
                <View
                  style={[
                    styles.changePill,
                    { backgroundColor: t.priceChangePercent >= 0 ? "rgba(0,227,150,0.12)" : "rgba(255,69,96,0.12)" },
                  ]}
                >
                  <Text
                    style={[
                      styles.changePillText,
                      { color: t.priceChangePercent >= 0 ? theme.colors.buy : theme.colors.sell },
                    ]}
                  >
                    {fmtPct(t.priceChangePercent)}
                  </Text>
                </View>
              </View>
              <Text style={styles.bentoPrice}>${fmtPrice(t.lastPrice)}</Text>
              <View style={{ marginTop: 8 }}>
                <MiniChart data={sparks[t.symbol] || [t.lastPrice]} width={140} height={36} />
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Top by volume - list */}
        <View style={styles.sectionHead}>
          <Text style={styles.sectionTitle}>Top volume</Text>
          <Text style={styles.labelMuted}>USDT</Text>
        </View>
        <View style={styles.list}>
          {tickers.slice(0, 8).map((t, idx) => (
            <TouchableOpacity
              key={t.symbol}
              style={[styles.listRow, idx !== 0 && styles.listRowBorder]}
              onPress={() => router.push({ pathname: "/coin/[symbol]", params: { symbol: t.symbol } })}
              activeOpacity={0.7}
              testID={`vol-row-${t.symbol}`}
            >
              <View style={styles.iconCircle}>
                <Text style={styles.iconText}>{symbolToBase(t.symbol).slice(0, 2)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowSym}>{symbolToBase(t.symbol)}</Text>
                <Text style={styles.rowPair}>Vol ${(t.quoteVolume / 1e6).toFixed(1)}M</Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={styles.rowPrice}>${fmtPrice(t.lastPrice)}</Text>
                <Text
                  style={[
                    styles.rowChange,
                    { color: t.priceChangePercent >= 0 ? theme.colors.buy : theme.colors.sell },
                  ]}
                >
                  {fmtPct(t.priceChangePercent)}
                </Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        <View style={{ height: 30 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  scroll: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 32 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 18 },
  greeting: { color: "#fff", fontSize: 22, fontWeight: "900", letterSpacing: -0.5 },
  headerSub: { color: theme.colors.textSecondary, fontSize: 13, marginTop: 4 },
  aiBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: "rgba(243,186,47,0.12)",
    borderColor: "rgba(243,186,47,0.4)",
    borderWidth: 1,
  },
  aiBadgeText: { color: theme.colors.primary, fontSize: 11, fontWeight: "800" },
  aiHero: {
    backgroundColor: theme.colors.surface,
    borderRadius: 24,
    padding: 20,
    borderColor: theme.colors.border,
    borderWidth: 1,
    overflow: "hidden",
    position: "relative",
  },
  aiHeroGlow: {
    position: "absolute",
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: theme.colors.primary,
    opacity: 0.08,
    top: -80,
    right: -60,
  },
  aiHeroLeft: { },
  aiPill: {
    flexDirection: "row", alignItems: "center", gap: 6,
    alignSelf: "flex-start",
    paddingHorizontal: 10, paddingVertical: 5,
    backgroundColor: "rgba(243,186,47,0.12)",
    borderColor: "rgba(243,186,47,0.4)",
    borderWidth: 1,
    borderRadius: 999,
    marginBottom: 12,
  },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: theme.colors.primary },
  aiPillText: { color: theme.colors.primary, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  aiTitle: { color: "#fff", fontSize: 26, fontWeight: "900", letterSpacing: -0.6 },
  aiSubtitle: { color: theme.colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 6 },
  aiCta: {
    flexDirection: "row", alignItems: "center", gap: 6,
    marginTop: 14,
  },
  aiCtaText: { color: theme.colors.primary, fontWeight: "800", fontSize: 13 },

  predictCard: {
    marginTop: 12, padding: 16,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    backgroundColor: theme.colors.surface, borderRadius: 18,
    borderColor: theme.colors.border, borderWidth: 1,
  },
  predictLeft: { flexDirection: "row", alignItems: "center", gap: 12 },
  predictIcon: {
    width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(243,186,47,0.10)",
  },
  predictTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  predictSub: { color: theme.colors.textSecondary, fontSize: 11, marginTop: 2 },

  sectionHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 28, marginBottom: 12 },
  sectionTitle: { color: "#fff", fontSize: 17, fontWeight: "800", letterSpacing: -0.3 },
  linkText: { color: theme.colors.primary, fontSize: 13, fontWeight: "700" },
  labelMuted: { color: theme.colors.textMuted, fontSize: 11, fontWeight: "700", letterSpacing: 1.5 },

  emptyCard: {
    backgroundColor: theme.colors.surface,
    borderRadius: 20,
    padding: 22,
    borderColor: theme.colors.border,
    borderWidth: 1,
    alignItems: "center",
    gap: 8,
  },
  emptyText: { color: "#fff", fontWeight: "700", fontSize: 15, marginTop: 6 },
  emptySub: { color: theme.colors.textSecondary, fontSize: 12, textAlign: "center" },

  watchCard: {
    width: 160,
    padding: 14,
    backgroundColor: theme.colors.surface,
    borderRadius: 18,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  watchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  watchSym: { color: "#fff", fontWeight: "800", fontSize: 14 },
  watchPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  changePill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  changePillText: { fontSize: 11, fontWeight: "800" },
  watchPrice: { color: "#fff", fontSize: 18, fontWeight: "800", marginTop: 12 },

  bento: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  bentoCard: {
    flexBasis: "48%",
    flexGrow: 1,
    padding: 14,
    backgroundColor: theme.colors.surface,
    borderRadius: 18,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  bentoTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  bentoPrice: { color: "#fff", fontSize: 17, fontWeight: "800", marginTop: 12 },

  list: {
    backgroundColor: theme.colors.surface,
    borderRadius: 20,
    borderColor: theme.colors.border,
    borderWidth: 1,
    overflow: "hidden",
  },
  listRow: { flexDirection: "row", alignItems: "center", padding: 14, gap: 12 },
  listRowBorder: { borderTopColor: theme.colors.border, borderTopWidth: 1 },
  iconCircle: {
    width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surfaceAlt, borderColor: theme.colors.border, borderWidth: 1,
  },
  iconText: { color: theme.colors.primary, fontWeight: "800", fontSize: 11 },
  rowSym: { color: "#fff", fontWeight: "700", fontSize: 14 },
  rowPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  rowPrice: { color: "#fff", fontWeight: "700", fontSize: 14 },
  rowChange: { fontSize: 12, fontWeight: "700", marginTop: 2 },
});
