import React, { useEffect, useState } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { Redirect } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useAuth } from "../src/contexts/AuthContext";
import { theme } from "../src/theme";

const TUTORIAL_SEEN_KEY = "@signalx_tutorial_seen_v1";

export default function Index() {
  const { user, loading } = useAuth();
  const [tutorialSeen, setTutorialSeen] = useState<boolean | null>(null);

  // Read tutorial flag on mount (only matters if user is logged in)
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const v = await AsyncStorage.getItem(TUTORIAL_SEEN_KEY);
        if (mounted) setTutorialSeen(v === "1");
      } catch {
        if (mounted) setTutorialSeen(true); // fail-safe → don't trap users
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading || tutorialSeen === null) {
    return (
      <View style={styles.center} testID="splash-screen">
        <ActivityIndicator color={theme.colors.primary} size="large" />
      </View>
    );
  }
  if (!user) return <Redirect href="/(auth)/welcome" />;
  // First time after sign-up / login → launch interactive tutorial (auto-onboarding)
  if (!tutorialSeen) return <Redirect href="/tutorial?onboarding=1" />;
  return <Redirect href="/(tabs)" />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg },
});
