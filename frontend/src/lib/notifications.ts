/**
 * Safe wrapper around expo-notifications.
 *
 * Starting with Expo SDK 53, remote (push) notifications were removed from
 * Expo Go on Android. Importing/using expo-notifications at module load time
 * crashes the app on Expo Go Android. To keep Expo Go usable during dev, we:
 *  - delay the import until needed
 *  - swallow any errors silently
 *  - return null tokens (push won't work in Expo Go but the app still runs)
 *
 * In a real development/production build this code path still works normally.
 */
import { Platform } from "react-native";
import Constants from "expo-constants";
import { api } from "./api";

// Detect Expo Go runtime (cannot do real push). Constants.appOwnership === 'expo' in Expo Go.
const isExpoGo = Constants.appOwnership === "expo";

export async function registerForPushNotifications(): Promise<string | null> {
  // Skip entirely on web and inside Expo Go on Android (SDK 53 removed it).
  if (Platform.OS === "web") return null;
  if (isExpoGo && Platform.OS === "android") {
    console.log("[push] Expo Go Android — push notifications disabled (use a dev build).");
    return null;
  }

  try {
    // Lazy import to prevent module-load crash in Expo Go.
    const Notifications = await import("expo-notifications");
    const Device = await import("expo-device");

    // Configure handler (must be set after import, idempotent).
    try {
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowAlert: true,
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: true,
          shouldSetBadge: true,
        } as any),
      });
    } catch {}

    if (!Device.isDevice) return null;

    const { status: existing } = await Notifications.getPermissionsAsync();
    let final = existing;
    if (existing !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      final = status;
    }
    if (final !== "granted") {
      console.log("[push] permission denied");
      return null;
    }

    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "SignalX",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#F3BA2F",
      });
    }

    const token = (await Notifications.getExpoPushTokenAsync()).data;
    if (token) {
      try {
        await api.saveExpoPushToken(token);
      } catch (e) {
        console.warn("[push] token save failed:", e);
      }
    }
    return token;
  } catch (e: any) {
    // Most likely: expo-notifications removed from Expo Go (Android, SDK 53+).
    console.warn("[push] registerForPushNotifications skipped:", e?.message || e);
    return null;
  }
}
