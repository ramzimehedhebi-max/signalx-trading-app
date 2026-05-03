import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { theme, fmtPrice, fmtPct, symbolToBase } from "../../src/theme";
import { api } from "../../src/lib/api";

export default function Markets() {
  const router = useRouter();
  const [tickers, setTickers] = useState<any[]>([]);
  const [watch, setWatch] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<"all" | "gainers" | "losers" | "watch">("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, w] = await Promise.all([api.tickers(), api.watchlist().catch(() => [])]);
      setTickers(t);
      setWatch(new Set(w.map((x: any) => x.symbol)));
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

  const toggleWatch = async (symbol: string) => {
    try {
      if (watch.has(symbol)) {
        await api.removeWatch(symbol);
        const n = new Set(watch);
        n.delete(symbol);
        setWatch(n);
      } else {
        await api.addWatch(symbol);
        const n = new Set(watch);
        n.add(symbol);
        setWatch(n);
      }
    } catch (e) {
      console.warn(e);
    }
  };

  const filtered = useMemo(() => {
    let list = [...tickers];
    if (tab === "gainers") list = list.filter((x) => x.priceChangePercent > 0).sort((a, b) => b.priceChangePercent - a.priceChangePercent);
    if (tab === "losers") list = list.filter((x) => x.priceChangePercent < 0).sort((a, b) => a.priceChangePercent - b.priceChangePercent);
    if (tab === "watch") list = list.filter((x) => watch.has(x.symbol));
    if (q.trim()) {
      const k = q.trim().toUpperCase();
      list = list.filter((x) => x.symbol.includes(k));
    }
    return list;
  }, [tickers, tab, q, watch]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }

  const tabs: { key: any; label: string }[] = [
    { key: "all", label: "Tous" },
    { key: "gainers", label: "Hausses" },
    { key: "losers", label: "Baisses" },
    { key: "watch", label: "Favoris" },
  ];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]} testID="markets-screen">
      <View style={styles.header}>
        <Text style={styles.title}>Marchés</Text>
        <Text style={styles.subtitle}>Top 20 paires Binance USDT</Text>
      </View>

      <View style={styles.searchWrap}>
        <Ionicons name="search" color={theme.colors.textMuted} size={18} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Rechercher BTC, ETH, SOL..."
          placeholderTextColor={theme.colors.textMuted}
          autoCapitalize="characters"
          style={styles.search}
          testID="markets-search"
        />
      </View>

      <View style={styles.tabs}>
        {tabs.map((t) => (
          <TouchableOpacity
            key={t.key}
            onPress={() => setTab(t.key)}
            style={[styles.tab, tab === t.key && styles.tabActive]}
            testID={`markets-tab-${t.key}`}
          >
            <Text style={[styles.tabText, tab === t.key && styles.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(it) => it.symbol}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40 }}
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />}
        ListEmptyComponent={
          <View style={{ alignItems: "center", paddingVertical: 60 }}>
            <Ionicons name="search-outline" size={32} color={theme.colors.textMuted} />
            <Text style={{ color: theme.colors.textSecondary, marginTop: 8 }}>Aucune paire trouvée</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => router.push({ pathname: "/coin/[symbol]", params: { symbol: item.symbol } })}
            activeOpacity={0.85}
            testID={`market-row-${item.symbol}`}
          >
            <View style={styles.iconCircle}>
              <Text style={styles.iconText}>{symbolToBase(item.symbol).slice(0, 2)}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowSym}>{symbolToBase(item.symbol)}</Text>
              <Text style={styles.rowPair}>{item.symbol}</Text>
            </View>
            <View style={{ alignItems: "flex-end", marginRight: 6 }}>
              <Text style={styles.rowPrice}>${fmtPrice(item.lastPrice)}</Text>
              <Text
                style={[
                  styles.rowChange,
                  { color: item.priceChangePercent >= 0 ? theme.colors.buy : theme.colors.sell },
                ]}
              >
                {fmtPct(item.priceChangePercent)}
              </Text>
            </View>
            <TouchableOpacity
              onPress={() => toggleWatch(item.symbol)}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              testID={`watch-toggle-${item.symbol}`}
            >
              <Ionicons
                name={watch.has(item.symbol) ? "star" : "star-outline"}
                size={20}
                color={watch.has(item.symbol) ? theme.colors.primary : theme.colors.textMuted}
              />
            </TouchableOpacity>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
  header: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 8 },
  title: { color: "#fff", fontSize: 28, fontWeight: "900", letterSpacing: -0.8 },
  subtitle: { color: theme.colors.textSecondary, fontSize: 13, marginTop: 4 },
  searchWrap: {
    marginHorizontal: 24,
    marginTop: 16,
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  search: { flex: 1, color: "#fff", fontSize: 15 },
  tabs: { flexDirection: "row", gap: 8, paddingHorizontal: 24, paddingVertical: 14 },
  tab: { paddingVertical: 8, paddingHorizontal: 14, borderRadius: 999, backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1 },
  tabActive: { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
  tabText: { color: theme.colors.textSecondary, fontWeight: "700", fontSize: 12 },
  tabTextActive: { color: "#000" },

  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    backgroundColor: theme.colors.surface,
    borderRadius: 16,
    borderColor: theme.colors.border,
    borderWidth: 1,
  },
  iconCircle: {
    width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.colors.surfaceAlt, borderColor: theme.colors.border, borderWidth: 1,
  },
  iconText: { color: theme.colors.primary, fontWeight: "800", fontSize: 11 },
  rowSym: { color: "#fff", fontWeight: "800", fontSize: 14 },
  rowPair: { color: theme.colors.textMuted, fontSize: 11, marginTop: 2 },
  rowPrice: { color: "#fff", fontWeight: "700", fontSize: 14 },
  rowChange: { fontSize: 12, fontWeight: "700", marginTop: 2 },
});
