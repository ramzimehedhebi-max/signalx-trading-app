import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
  Platform,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useTranslation } from "react-i18next";
import { LinearGradient } from "expo-linear-gradient";
import * as Speech from "expo-speech";
import AsyncStorage from "@react-native-async-storage/async-storage";
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  withRepeat,
  withSequence,
  Easing,
  interpolate,
  Extrapolation,
  runOnJS,
} from "react-native-reanimated";
import {
  GestureDetector,
  Gesture,
} from "react-native-gesture-handler";
import { theme } from "../src/theme";

const { width: SCREEN_W } = Dimensions.get("window");

type Slide = {
  emoji: string;
  titleKey: string;
  textKey: string;
  gradient: [string, string];
  accent: string;
  badges?: string[];
  badgeKeys?: string[];
};

const SLIDES: Slide[] = [
  {
    emoji: "🚀",
    titleKey: "tutorial.s1.title",
    textKey: "tutorial.s1.text",
    gradient: ["#1A2A6C", "#B21F1F"],
    accent: "#FFD700",
  },
  {
    emoji: "🔐",
    titleKey: "tutorial.s2.title",
    textKey: "tutorial.s2.text",
    gradient: ["#0F2027", "#2C5364"],
    accent: "#00E396",
    badgeKeys: ["tutorial.s2.badge1", "tutorial.s2.badge2"],
  },
  {
    emoji: "💰",
    titleKey: "tutorial.s3.title",
    textKey: "tutorial.s3.text",
    gradient: ["#F2994A", "#F2C94C"],
    accent: "#FFFFFF",
    badgeKeys: ["tutorial.s3.badge1", "tutorial.s3.badge2", "tutorial.s3.badge3"],
  },
  {
    emoji: "🔗",
    titleKey: "tutorial.s4.title",
    textKey: "tutorial.s4.text",
    gradient: ["#360033", "#0B8793"],
    accent: "#FF4560",
    badgeKeys: ["tutorial.s4.badge1", "tutorial.s4.badge2"],
  },
  {
    emoji: "🤖",
    titleKey: "tutorial.s5.title",
    textKey: "tutorial.s5.text",
    gradient: ["#0F2027", "#203A43"],
    accent: theme.colors.primary,
    badgeKeys: ["tutorial.s5.badge1", "tutorial.s5.badge2", "tutorial.s5.badge3"],
  },
  {
    emoji: "⚡",
    titleKey: "tutorial.s6.title",
    textKey: "tutorial.s6.text",
    gradient: ["#16222A", "#3A6073"],
    accent: "#FF4560",
    badgeKeys: ["tutorial.s6.badge1"],
  },
  {
    emoji: "💸",
    titleKey: "tutorial.s7.title",
    textKey: "tutorial.s7.text",
    gradient: ["#134E5E", "#71B280"],
    accent: "#FFD700",
    badgeKeys: ["tutorial.s7.badge1", "tutorial.s7.badge2", "tutorial.s7.badge3", "tutorial.s7.badge4"],
  },
  {
    emoji: "🎯",
    titleKey: "tutorial.s8.title",
    textKey: "tutorial.s8.text",
    gradient: ["#1A2A6C", "#B21F1F"],
    accent: "#00E396",
    badgeKeys: ["tutorial.s8.badge1"],
  },
];

const STORAGE_KEY = "@signalx_tutorial_seen_v1";

export default function TutorialScreen() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const [index, setIndex] = useState(0);
  const [voiceEnabled, setVoiceEnabled] = useState(false);

  const translateX = useSharedValue(0);
  const emojiScale = useSharedValue(0);
  const emojiBounce = useSharedValue(0);
  const contentOpacity = useSharedValue(0);
  const progressVal = useSharedValue(0);

  const total = SLIDES.length;
  const slide = SLIDES[index];

  const speakCurrent = useCallback(() => {
    if (!voiceEnabled) return;
    const text = `${t(slide.titleKey)}. ${t(slide.textKey)}`;
    Speech.stop();
    Speech.speak(text, {
      language: i18n.language === "ar" ? "ar-SA" : `${i18n.language}-${i18n.language.toUpperCase()}`,
      rate: 0.95,
      pitch: 1.0,
    });
  }, [voiceEnabled, slide, t, i18n.language]);

  const animateIn = useCallback(() => {
    emojiScale.value = 0;
    contentOpacity.value = 0;
    emojiScale.value = withSpring(1, { damping: 8, stiffness: 80 });
    contentOpacity.value = withTiming(1, { duration: 500, easing: Easing.out(Easing.cubic) });
    // gentle floating animation
    emojiBounce.value = withRepeat(
      withSequence(
        withTiming(-10, { duration: 1200, easing: Easing.inOut(Easing.sin) }),
        withTiming(10, { duration: 1200, easing: Easing.inOut(Easing.sin) })
      ),
      -1,
      true
    );
  }, [emojiScale, contentOpacity, emojiBounce]);

  // Animate progress bar
  useEffect(() => {
    progressVal.value = withTiming((index + 1) / total, { duration: 400 });
  }, [index, progressVal, total]);

  useEffect(() => {
    animateIn();
    speakCurrent();
    return () => {
      Speech.stop();
    };
  }, [index, animateIn, speakCurrent]);

  const goNext = useCallback(async () => {
    Speech.stop();
    if (index < total - 1) {
      setIndex(index + 1);
    } else {
      // mark seen and exit
      try {
        await AsyncStorage.setItem(STORAGE_KEY, "1");
      } catch {}
      router.back();
    }
  }, [index, router, total]);

  const goPrev = useCallback(() => {
    Speech.stop();
    if (index > 0) setIndex(index - 1);
  }, [index]);

  const skip = useCallback(async () => {
    Speech.stop();
    try {
      await AsyncStorage.setItem(STORAGE_KEY, "1");
    } catch {}
    router.back();
  }, [router]);

  const toggleVoice = useCallback(() => {
    setVoiceEnabled((v) => {
      const newVal = !v;
      if (!newVal) Speech.stop();
      return newVal;
    });
  }, []);

  // Swipe gesture
  const pan = Gesture.Pan()
    .onUpdate((e) => {
      translateX.value = e.translationX;
    })
    .onEnd((e) => {
      const threshold = 80;
      if (e.translationX < -threshold) {
        translateX.value = withTiming(-SCREEN_W, { duration: 200 }, () => {
          translateX.value = 0;
          runOnJS(goNext)();
        });
      } else if (e.translationX > threshold && index > 0) {
        translateX.value = withTiming(SCREEN_W, { duration: 200 }, () => {
          translateX.value = 0;
          runOnJS(goPrev)();
        });
      } else {
        translateX.value = withSpring(0);
      }
    });

  const slideStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
    opacity: interpolate(
      Math.abs(translateX.value),
      [0, SCREEN_W * 0.5],
      [1, 0.4],
      Extrapolation.CLAMP
    ),
  }));

  const emojiStyle = useAnimatedStyle(() => ({
    transform: [{ scale: emojiScale.value }, { translateY: emojiBounce.value }],
  }));

  const contentStyle = useAnimatedStyle(() => ({
    opacity: contentOpacity.value,
    transform: [
      {
        translateY: interpolate(contentOpacity.value, [0, 1], [30, 0], Extrapolation.CLAMP),
      },
    ],
  }));

  const progressStyle = useAnimatedStyle(() => ({
    width: `${progressVal.value * 100}%`,
  }));

  return (
    <LinearGradient colors={slide.gradient} style={styles.gradient}>
      <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
          {/* Top Bar: progress + close + voice */}
          <View style={styles.topBar}>
            <TouchableOpacity
              onPress={skip}
              style={styles.iconBtn}
              testID="tutorial-close-btn"
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Ionicons name="close" size={22} color="#fff" />
            </TouchableOpacity>

            <View style={styles.progressTrack}>
              <Animated.View style={[styles.progressFill, progressStyle, { backgroundColor: slide.accent }]} />
            </View>

            <TouchableOpacity
              onPress={toggleVoice}
              style={[styles.iconBtn, voiceEnabled && { backgroundColor: "rgba(255,255,255,0.18)" }]}
              testID="tutorial-voice-btn"
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Ionicons
                name={voiceEnabled ? "volume-high" : "volume-mute"}
                size={20}
                color="#fff"
              />
            </TouchableOpacity>
          </View>

          {/* Slide step indicator */}
          <View style={styles.stepIndicator}>
            <Text style={styles.stepText}>
              {index + 1} / {total}
            </Text>
          </View>

          {/* Main content (swipeable) */}
          <GestureDetector gesture={pan}>
            <Animated.View style={[styles.slideContainer, slideStyle]}>
              <Animated.View style={[styles.emojiWrap, emojiStyle]}>
                <Text style={styles.emoji}>{slide.emoji}</Text>
                <View style={[styles.emojiGlow, { backgroundColor: slide.accent + "40" }]} />
              </Animated.View>

              <Animated.View style={[styles.textBlock, contentStyle]}>
                <Text style={styles.title}>{t(slide.titleKey)}</Text>
                <Text style={styles.text}>{t(slide.textKey)}</Text>

                {slide.badgeKeys && slide.badgeKeys.length > 0 && (
                  <ScrollView
                    style={{ maxHeight: 200, marginTop: 16 }}
                    showsVerticalScrollIndicator={false}
                  >
                    {slide.badgeKeys.map((bk, i) => (
                      <BadgeRow
                        key={bk}
                        text={t(bk)}
                        accent={slide.accent}
                        delay={i * 100}
                      />
                    ))}
                  </ScrollView>
                )}
              </Animated.View>
            </Animated.View>
          </GestureDetector>

          {/* Dots indicator */}
          <View style={styles.dots}>
            {SLIDES.map((_, i) => (
              <View
                key={i}
                style={[
                  styles.dot,
                  i === index && { backgroundColor: slide.accent, width: 24 },
                ]}
              />
            ))}
          </View>

          {/* Bottom buttons */}
          <View style={styles.bottomBar}>
            <TouchableOpacity
              onPress={goPrev}
              style={[styles.navBtn, styles.navBtnSecondary, index === 0 && styles.navBtnDisabled]}
              disabled={index === 0}
              testID="tutorial-prev-btn"
            >
              <Ionicons name="chevron-back" size={20} color={index === 0 ? "rgba(255,255,255,0.3)" : "#fff"} />
              <Text style={[styles.navBtnText, index === 0 && { color: "rgba(255,255,255,0.3)" }]}>
                {t("tutorial.prev")}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={goNext}
              style={[styles.navBtn, styles.navBtnPrimary, { backgroundColor: slide.accent }]}
              testID="tutorial-next-btn"
            >
              <Text style={styles.navBtnTextPrimary}>
                {index === total - 1 ? t("tutorial.finish") : t("tutorial.next")}
              </Text>
              <Ionicons
                name={index === total - 1 ? "checkmark" : "chevron-forward"}
                size={20}
                color="#0A0E27"
              />
            </TouchableOpacity>
          </View>

          {/* Swipe hint */}
          {index === 0 && (
            <View style={styles.swipeHint}>
              <Ionicons name="swap-horizontal" size={14} color="rgba(255,255,255,0.5)" />
              <Text style={styles.swipeHintText}>{t("tutorial.swipe_hint")}</Text>
            </View>
          )}
        </SafeAreaView>
      </LinearGradient>
  );
}

function BadgeRow({ text, accent, delay }: { text: string; accent: string; delay: number }) {
  const opacity = useSharedValue(0);
  const tx = useSharedValue(-30);

  useEffect(() => {
    opacity.value = withTiming(1, { duration: 500 });
    tx.value = withSpring(0, { damping: 12 });
  }, [opacity, tx]);

  const style = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateX: tx.value }],
  }));

  return (
    <Animated.View style={[styles.badge, style, { borderLeftColor: accent }]}>
      <Text style={styles.badgeText}>{text}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1, paddingHorizontal: 24 },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
  },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.08)",
    alignItems: "center",
    justifyContent: "center",
  },
  progressTrack: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    backgroundColor: "rgba(255,255,255,0.15)",
    overflow: "hidden",
  },
  progressFill: { height: "100%", borderRadius: 2 },
  stepIndicator: { alignItems: "center", marginTop: 8 },
  stepText: {
    color: "rgba(255,255,255,0.65)",
    fontSize: 13,
    fontWeight: "600",
    letterSpacing: 1,
  },
  slideContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 8,
  },
  emojiWrap: {
    width: 180,
    height: 180,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 32,
  },
  emoji: {
    fontSize: Platform.select({ ios: 120, android: 110, default: 120 }),
    zIndex: 2,
  },
  emojiGlow: {
    position: "absolute",
    width: 200,
    height: 200,
    borderRadius: 100,
    opacity: 0.45,
    zIndex: 1,
  },
  textBlock: { alignItems: "center", paddingHorizontal: 8 },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: "#fff",
    textAlign: "center",
    lineHeight: 34,
    marginBottom: 12,
  },
  text: {
    fontSize: 15,
    color: "rgba(255,255,255,0.85)",
    textAlign: "center",
    lineHeight: 22,
    paddingHorizontal: 8,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.12)",
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 12,
    marginBottom: 8,
    borderLeftWidth: 3,
  },
  badgeText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "600",
    flex: 1,
  },
  dots: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 6,
    marginBottom: 20,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "rgba(255,255,255,0.25)",
  },
  bottomBar: {
    flexDirection: "row",
    gap: 12,
    paddingBottom: 12,
  },
  navBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 14,
  },
  navBtnSecondary: {
    backgroundColor: "rgba(255,255,255,0.1)",
    flex: 1,
  },
  navBtnPrimary: {
    flex: 2,
  },
  navBtnDisabled: { opacity: 0.5 },
  navBtnText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  navBtnTextPrimary: { color: "#0A0E27", fontWeight: "800", fontSize: 15 },
  swipeHint: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    position: "absolute",
    bottom: 88,
    alignSelf: "center",
    left: 0,
    right: 0,
  },
  swipeHintText: { color: "rgba(255,255,255,0.5)", fontSize: 12 },
});
