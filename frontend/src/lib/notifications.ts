import * as Notifications from "expo-notifications";
import * as Device from "expo-device";
import { Platform } from "react-native";
import { api } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications() {
  if (!Device.isDevice) return null;
  try {
    const { status: existing } = await Notifications.getPermissionsAsync();
    let final = existing;
    if (existing !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      final = status;
    }
    if (final !== "granted") {
      console.log("Push permission denied");
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
        console.warn("Push token save failed:", e);
      }
    }
    return token;
  } catch (e) {
    console.warn("registerForPushNotifications error:", e);
    return null;
  }
}
