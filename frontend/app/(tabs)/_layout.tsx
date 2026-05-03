import React from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Platform, View } from "react-native";
import { theme } from "../../src/theme";

export default function TabsLayout() {
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
          height: Platform.OS === "ios" ? 84 : 64,
          paddingBottom: Platform.OS === "ios" ? 28 : 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: "700", letterSpacing: 0.5 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Accueil",
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="markets"
        options={{
          title: "Marchés",
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="signals"
        options={{
          title: "Signaux IA",
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
          title: "Bot IA",
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
          title: "Profil",
          tabBarIcon: ({ color, size }) => <Ionicons name="person-circle" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
