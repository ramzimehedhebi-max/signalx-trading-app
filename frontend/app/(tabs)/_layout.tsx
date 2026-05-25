import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Platform, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import { theme } from "../../src/theme";

export default function TabsLayout() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  // Reserve enough space at the bottom for both the Android gesture / nav bar
  // (insets.bottom) and a comfortable tap target. iOS keeps its classic 84/28.
  const bottomInset = insets.bottom || 0;
  const tabBarPaddingBottom = Platform.OS === "ios" ? 28 : Math.max(8, bottomInset + 6);
  const tabBarHeight = Platform.OS === "ios" ? 84 : 56 + tabBarPaddingBottom;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.textMuted,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: tabBarHeight,
          paddingBottom: tabBarPaddingBottom,
          paddingTop: 8,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: "700", letterSpacing: 0.5 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t("tabs.home"),
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="markets"
        options={{
          title: t("tabs.markets"),
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="signals"
        options={{
          title: t("tabs.signals"),
          tabBarIcon: ({ color, size, focused }) => (
            <View>
              <Ionicons name="sparkles" size={size} color={color} />
              {focused && (
                <View
                  style={{
                    position: "absolute",
                    top: -2,
                    right: -2,
                    width: 6,
                    height: 6,
                    borderRadius: 3,
                    backgroundColor: theme.colors.primary,
                  }}
                />
              )}
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="bot"
        options={{
          title: t("tabs.bot"),
          tabBarIcon: ({ color, size, focused }) => (
            <View>
              <Ionicons name="rocket" size={size} color={color} />
              {focused && (
                <View
                  style={{
                    position: "absolute",
                    top: -2,
                    right: -2,
                    width: 6,
                    height: 6,
                    borderRadius: 3,
                    backgroundColor: theme.colors.buy,
                  }}
                />
              )}
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{
          href: null,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: t("tabs.profile"),
          tabBarIcon: ({ color, size }) => <Ionicons name="person-circle" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
