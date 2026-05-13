import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import * as Localization from 'expo-localization';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { I18nManager } from 'react-native';

import fr from './locales/fr.json';
import en from './locales/en.json';
import ar from './locales/ar.json';
import es from './locales/es.json';
import de from './locales/de.json';
import it from './locales/it.json';
import pt from './locales/pt.json';
import zh from './locales/zh.json';

export const SUPPORTED_LANGS = ['fr', 'en', 'ar', 'es', 'de', 'it', 'pt', 'zh'] as const;
export type LangCode = (typeof SUPPORTED_LANGS)[number];
export const RTL_LANGS: LangCode[] = ['ar'];
const LANG_STORAGE_KEY = '@signalx.lang';

const resources = {
  fr: { translation: fr },
  en: { translation: en },
  ar: { translation: ar },
  es: { translation: es },
  de: { translation: de },
  it: { translation: it },
  pt: { translation: pt },
  zh: { translation: zh },
};

async function detectInitialLanguage(): Promise<LangCode> {
  try {
    const stored = await AsyncStorage.getItem(LANG_STORAGE_KEY);
    if (stored && SUPPORTED_LANGS.includes(stored as LangCode)) return stored as LangCode;
  } catch {}
  try {
    const locales = Localization.getLocales?.() ?? [];
    for (const l of locales) {
      const c = (l.languageCode || '').toLowerCase() as LangCode;
      if (SUPPORTED_LANGS.includes(c)) return c;
    }
  } catch {}
  return 'fr';
}

let ready = false;
export async function initI18n() {
  if (ready) return;
  const lng = await detectInitialLanguage();
  await i18n.use(initReactI18next).init({
    resources,
    lng,
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    compatibilityJSON: 'v4',
  });
  // Apply RTL if needed (no auto-reload — Expo Go can't restart natively)
  try {
    const isRTL = RTL_LANGS.includes(lng);
    if (I18nManager.isRTL !== isRTL && I18nManager.allowRTL) {
      I18nManager.allowRTL(isRTL);
      I18nManager.forceRTL(isRTL);
    }
  } catch {}
  ready = true;
}

export async function changeLanguage(lng: LangCode) {
  await i18n.changeLanguage(lng);
  try {
    await AsyncStorage.setItem(LANG_STORAGE_KEY, lng);
  } catch {}
  try {
    const isRTL = RTL_LANGS.includes(lng);
    if (I18nManager.isRTL !== isRTL && I18nManager.allowRTL) {
      I18nManager.allowRTL(isRTL);
      I18nManager.forceRTL(isRTL);
    }
  } catch {}
}

export default i18n;
