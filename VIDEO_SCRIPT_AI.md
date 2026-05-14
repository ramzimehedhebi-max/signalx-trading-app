# 🤖 Script Vidéo IA — SignalX Tutorial (Production-Ready)

**Durée cible** : 5 min 30 (idéal pour la rétention YouTube/Shorts long)
**Format final** : MP4 1080p 16:9 — sous-titres burned-in
**Méthode de production** : 100 % IA — aucun tournage caméra requis
**Coût estimé** : 0 à 30 € selon les outils (versions gratuites possibles)

---

## 🛠️ STACK D'OUTILS IA RECOMMANDÉE

| Tâche | Outil recommandé | Alternative gratuite |
|-------|------------------|----------------------|
| **Avatar parlant (présentateur)** | HeyGen (avatar + lip-sync FR) | D-ID (1 min gratuite) |
| **Voix off française** | ElevenLabs (voix "Charlotte" ou "Henri") | Edge TTS / Tortoise TTS |
| **B-roll abstrait / 3D** | Runway Gen-3 ou Kling 1.6 | Pika Labs gratuit (limité) |
| **Captures animées de l'app** | Screen Studio (Mac) / OBS + Motion | Loom + Canva animations |
| **Montage final** | CapCut Desktop (gratuit) | DaVinci Resolve (gratuit) |
| **Sous-titres auto FR** | CapCut (intégré) | Whisper + Subtitle Edit |
| **Musique IA** | Suno v4 / Udio | YouTube Audio Library |
| **Thumbnails** | Ideogram / Midjourney | Canva + Bing Image Creator |

---

## 🎬 PROMPT GLOBAL POUR L'AVATAR (HeyGen / Synthesia)

```
Avatar profile: Male or Female, 25-35 years old, business casual
(white t-shirt or light hoodie), warm but professional look,
confident smile. Background: modern minimalist office with
soft blue-purple ambient light. Camera angle: medium shot,
slight 3/4 turn. Lip-sync language: French. Gestures: natural,
not over-animated. Eye contact: direct to camera.
```

**Voix ElevenLabs recommandée** :
- Voice ID : `Charlotte` (féminin clair, accent FR standard) ou `Henri` (masculin chaleureux)
- Stability : 45 %
- Similarity Boost : 75 %
- Style Exaggeration : 20 %
- Speaker Boost : ON

---

## 🎞️ SCÈNE PAR SCÈNE (Storyboard IA)

> **Légende** :
> 🗣️ = voix-off (à coller telle quelle dans ElevenLabs)
> 🎨 = prompt visuel (à coller dans Runway / Kling / Sora)
> 📱 = capture écran de l'app SignalX (à enregistrer avec Screen Studio)
> 📝 = sous-titre à afficher (texte burned-in)

---

### SCÈNE 1 — HOOK (0:00 → 0:15) — 15 s

**🎨 Prompt B-roll (Runway Gen-3, 5 s)** :
```
Cinematic shot of a glowing crypto trading dashboard floating
in dark space, green upward candlestick chart animating in 3D,
particles of blue light, futuristic and clean, motion blur,
4K, no text on screen
```

📱 **Capture app** : Dashboard P&L SignalX, courbe verte animée 10 s

🗣️ **Voix-off** :
> « Et si je te disais qu'un robot intelligent pouvait faire travailler ton argent sur Binance, vingt-quatre heures sur vingt-quatre, sans que tu ne touches à rien ? Dans cinq minutes, tu sauras exactement comment lancer le tien. »

📝 **Texte à l'écran** : `Gagne de l'argent sur Binance avec un bot IA`

🎵 **Musique** : entrée énergique, sub-bass + synth lo-fi (genre Suno : « cinematic crypto intro, 90 BPM, electronic »)

---

### SCÈNE 2 — TITRE ANIMÉ (0:15 → 0:20) — 5 s

**🎨 Prompt visuel (animation)** :
```
Animated title card: "SignalX — Le Guide A à Z" appears with
glow effect, gradient blue to purple, modern sans-serif font,
slight zoom-in, particles flowing behind, dark background
```

🎵 **Sound design** : whoosh + sub drop

---

### SCÈNE 3 — SÉCURITÉ EN PREMIER (0:20 → 1:00) — 40 s

**Avatar plein écran** (HeyGen)

🗣️ **Voix-off** :
> « Avant tout : la règle d'or. SignalX ne stocke jamais ton argent. Tes euros, tes cryptos, ils restent à cent pour cent sur ton compte Binance. SignalX, c'est juste un cerveau qui passe des ordres sur ton compte. Comme un trader pro qui regarderait par-dessus ton épaule, mais en automatique. Et le plus important : on va configurer les clés A.P.I sans permission de retrait. Ça veut dire que même si quelqu'un piratait l'application, il ne pourrait pas sortir un seul euro. »

**🎨 Overlay graphique (à insérer 0:35 → 0:55)** :
```
Animated infographic: two glowing boxes side by side.
Left box labeled "BINANCE — Tes fonds" with euro and bitcoin
icons. Right box labeled "SIGNALX — Cerveau" with brain icon.
Animated arrows showing orders flowing from right to left,
NO money flowing back. Style: flat 2D, neon outline, dark
background
```

📝 **Sous-titres clés** :
- `Tes fonds restent chez TOI`
- `Clés API : JAMAIS de permission de retrait`

---

### SCÈNE 4 — DÉPÔT SUR BINANCE (1:00 → 2:15) — 1 min 15

**📱 Captures écran à enregistrer (Screen Studio)** :
1. Page d'inscription binance.com (10 s)
2. Menu « Dépôt » → « Acheter avec carte » (10 s)
3. Menu « Dépôt » → « SEPA » (10 s)
4. Outil « Convertir » EUR → USDT (8 s)

🗣️ **Voix-off** :
> « Étape une : si t'as pas de compte Binance, va sur binance.com, inscription gratuite, vérification d'identité avec ta carte et un selfie, ça prend cinq minutes. Ensuite, pour déposer de l'argent t'as trois options. La plus simple : carte bancaire. Tu cliques sur Dépôt, Acheter avec carte, tu achètes directement des U.S.D.T. — la monnaie qu'on va utiliser pour trader. C'est instantané, environ deux pour cent de frais. Deuxième option, la moins chère : virement S.E.P.A. Tu vas dans Dépôt, E.U.R, Virement S.E.P.A., tu copies l'I.B.A.N. affiché, tu fais un virement depuis ta banque, et un à deux jours plus tard l'argent est là. Zéro frais. Tu convertis ensuite en U.S.D.T. avec l'outil Convertir. Mon conseil pour commencer : cent à trois cents euros. Pas plus. T'apprends, et tu ajouteras après. »

**🎨 B-roll alternatif (Runway, 5 s)** :
```
Close-up of a phone screen showing a SEPA bank transfer
animation, euro symbol morphing into USDT tether logo,
smooth transition, fintech aesthetic, blue and green accents
```

📝 **Cards animées** :
- `Option 1 : Carte bancaire — instantané, 2% frais`
- `Option 2 : SEPA — 1-2 jours, 0% frais ✅`
- `Option 3 : Crypto depuis autre wallet`
- `💡 Commence avec 100-300€ MAX`

---

### SCÈNE 5 — CONNECTER BINANCE À SIGNALX (2:15 → 3:30) — 1 min 15

**📱 Captures écran** :
1. Binance → Profil → API Management → Create API (15 s)
2. Zoom sur les checkboxes de permissions (10 s)
3. SignalX → Profil → Binance Connect → coller les clés (10 s)

🗣️ **Voix-off** :
> « Maintenant le côté technique, mais c'est rapide. Dans SignalX, tu vas dans Profil, Connecter mon Binance. L'app t'affiche un tutoriel pas à pas. Sur Binance, tu vas dans Profil, A.P.I. Management, Create A.P.I., tu choisis System Generated. Et là, attention. Tu actives uniquement Enable Spot et Margin Trading. C'est tout. Tu désactives absolument Enable Withdrawals et Enable Universal Transfer. Pourquoi ? Parce que sans Withdrawals, personne ne peut sortir d'argent, même avec tes clés. C'est mathématiquement impossible. Tu copies ta clé A.P.I et ta clé Secret, tu les colles dans SignalX, et hop, c'est connecté. Tes clés sont chiffrées en A.E.S. cent vingt-huit. Personne, même pas notre support, ne peut les lire en clair. »

**🎨 Overlay critique (à insérer 2:50 → 3:05)** :
```
Animated warning graphic: a red X mark crossing out the word
"Withdrawals" with shake animation, then a green checkmark
next to "Spot & Margin Trading". Pulsing red glow, urgency
feel, dark background
```

📝 **Sous-titres clés en gros texte rouge** :
- `❌ JAMAIS : Enable Withdrawals`
- `✅ SEULEMENT : Spot & Margin Trading`
- `🔐 Clés chiffrées AES-128`

---

### SCÈNE 6 — CONFIGURER LE BOT (3:30 → 4:45) — 1 min 15

**📱 Captures écran** :
1. Onglet Bot SignalX — badge « Mode Paper » (10 s)
2. Settings du bot — scroll des paramètres (15 s)
3. Toggles features avancées (10 s)
4. Dashboard P&L animé (15 s)

🗣️ **Voix-off** :
> « Maintenant le cœur du système : le bot I.A. Avant de risquer un euro, on teste en mode Paper. C'est du trading en simulation. Le bot utilise les vrais prix Binance, mais avec un capital virtuel de mille U.S.D.T. Aucun argent réel n'est touché. Tu actives, et tu observes pendant une à deux semaines. Pour commencer, je te recommande : stop-loss à trois pour cent, take-profit à huit à dix pour cent, taille de position dix à vingt pour cent du capital, maximum trois à cinq positions ouvertes, et les paires Bitcoin, Ethereum, Solana. Pour aller plus loin, active les trois features avancées : la diversification automatique évite de trader plein de cryptos corrélées en même temps, le trailing take-profit laisse courir les gros gains, et les prises partielles verrouillent cinquante pour cent du profit à plus trois pour cent. Pendant que le bot tourne, tu suis tes perfs dans le Dashboard P&L : courbe du capital, win-rate, drawdown, top cryptos. Et quand t'es vraiment prêt, et seulement quand t'es prêt, tu passes en mode Live. Le bot exécute alors des vrais ordres, avec une limite de cinquante dollars max par trade par défaut. »

**🎨 B-roll (Kling, 5 s)** :
```
Futuristic AI brain pulsing with neon blue and green lights,
data streams flowing in and out, holographic candlestick
charts orbiting around it, dark cyberpunk aesthetic, 4K
```

📝 **Cards animées (à enchaîner)** :
- `Stop-loss : 3%`
- `Take-profit : 8-10%`
- `Position : 10-20% capital`
- `Max 3-5 positions`
- `Paires : BTC, ETH, SOL`

---

### SCÈNE 7 — RETIRER TES GAINS (4:45 → 5:15) — 30 s

**📱 Captures écran** :
1. Binance Spot Wallet avec solde mis à jour (5 s)
2. Convertir USDT → EUR (5 s)
3. Retrait → SEPA → IBAN (10 s)
4. Toggle bot OFF dans SignalX (5 s)

🗣️ **Voix-off** :
> « Comment tu récupères tes gains ? Directement sur Binance. SignalX ne gère pas tes retraits, tu restes propriétaire. Tu vas sur Binance, Spot Wallet, tu vois ton solde. Tu cliques Convertir, U.S.D.T. vers E.U.R. Tu vas dans Retrait, Virement S.E.P.A., tu colles ton I.B.A.N., et un à deux jours plus tard l'argent est sur ton compte en banque. Gratuit. Et si tu veux stopper le bot à tout moment ? Onglet Bot, toggle Off. Ou Kill-switch pour une pause immédiate. »

📝 **Cards numérotées 1-2-3-4** animées en séquence

---

### SCÈNE 8 — OUTRO + DISCLAIMER (5:15 → 5:30) — 15 s

**Avatar plein écran** (HeyGen)

🗣️ **Voix-off** :
> « Récap rapide : tu déposes sur Binance, tu connectes des clés A.P.I. sans permission de retrait, tu testes en mode Paper, puis tu passes en Live quand t'es à l'aise. Le trading crypto comporte des risques, le bot peut perdre comme gagner. Trade uniquement avec de l'argent que tu peux te permettre de perdre. Toutes les questions, tout est dans Profil, Aide et Support. Bon trading, et à bientôt. »

**🎨 Overlay final** :
```
End card with SignalX logo glowing, four icons in row labeled
"DÉPOSE — CONNECTE — CONFIGURE — SURVEILLE", subscribe button
animation in bottom right, gradient background blue to purple
```

📝 **Disclaimer** : `⚠️ Le trading comporte des risques. Capital à risque.`

---

## 📋 CHECKLIST DE PRODUCTION (ordre recommandé)

- [ ] **Étape 1 — Voix off (1 h)** : Copie-colle chaque bloc 🗣️ dans ElevenLabs. Génère les 8 segments audio. Renomme `s1.mp3`, `s2.mp3`, etc.
- [ ] **Étape 2 — Avatar (1 h)** : Sur HeyGen, importe les audios. Choisis ton avatar. Génère les segments où l'avatar est plein écran (scènes 3 et 8).
- [ ] **Étape 3 — Captures app (45 min)** : Avec Screen Studio (Mac) ou OBS, enregistre les flux dans l'app SignalX selon les indications 📱 de chaque scène.
- [ ] **Étape 4 — B-rolls IA (1 h)** : Copie-colle chaque prompt 🎨 dans Runway Gen-3 ou Kling. Génère les clips de 5 s.
- [ ] **Étape 5 — Montage (2 h)** : Dans CapCut, importe tout. Assemble selon le storyboard. Synchronise voix + visuels.
- [ ] **Étape 6 — Sous-titres (15 min)** : Active la transcription auto en français dans CapCut. Vérifie et corrige.
- [ ] **Étape 7 — Musique (10 min)** : Suno : prompt = `"lo-fi electronic background music, 90 BPM, calm crypto vibe, no vocals, 6 minutes"`. Volume à -20 dB par rapport à la voix.
- [ ] **Étape 8 — Export final** : 1080p, H.264, 25 fps, audio 192 kbps.
- [ ] **Étape 9 — Thumbnail (15 min)** : Ideogram prompt = `"YouTube thumbnail, dark blue background, glowing green crypto chart going up, large bold French text 'Gagne sur Binance avec l'IA', face icon, modern bold design"`.
- [ ] **Étape 10 — Upload YouTube** : titre, description, tags, mode non-répertorié pour test puis public.

---

## 🎯 PROMPTS COPY-PASTE PRÊTS (toutes scènes)

### ElevenLabs — paramètres voix française
```
Voice: Charlotte (FR) ou Henri (FR)
Stability: 45
Similarity Boost: 75
Style: 20
Use speaker boost: ON
Output format: MP3 44.1 kHz 192 kbps
```

### Suno v4 — musique de fond
```
Prompt: lo-fi electronic ambient, 90 BPM, calm fintech crypto
mood, soft synth pads, subtle sub-bass, no vocals, instrumental,
6 minutes
Style: instrumental, lo-fi, ambient electronic
```

### Ideogram / Midjourney — thumbnail YouTube
```
A high-converting YouTube thumbnail, dark navy background with
green and blue gradient lights, a large 3D rising candlestick
chart on the right side glowing green, bold French headline
on the left "GAGNE SUR BINANCE AVEC L'IA" in white sans-serif
font with red accent, small SignalX logo bottom left, cinematic,
4K, ultra-realistic, eye-catching
--ar 16:9 --style raw
```

---

## 🚀 UNE FOIS LA VIDÉO PRÊTE

1. Upload sur YouTube (commence en **non répertorié** pour test interne).
2. Copie l'ID de la vidéo dans l'URL (`https://youtube.com/watch?v=XXXXXXXXXXX`).
3. Donne-moi l'ID — je l'intègre automatiquement dans `/app/frontend/app/help.tsx`.
4. Le lecteur YouTube apparaîtra dans l'onglet **Aide & Support** de SignalX.

---

## 💡 BONUS : Version SHORT 60 secondes (pour TikTok / YouTube Shorts / Reels)

Si tu veux aussi capter du trafic sur les réseaux courts, garde uniquement :
- **0–5 s** : Hook (« Et si un robot faisait travailler ton argent sur Binance ? »)
- **5–25 s** : Démo écran rapide (bot qui trade, P&L qui monte)
- **25–50 s** : 3 étapes clés (Dépose → Connecte → Bot Paper d'abord)
- **50–60 s** : CTA (« Lien dans la bio, tutoriel complet sur YouTube »)

Format vertical 9:16, sous-titres énormes, musique punchy (BPM 110+).

---

## 📞 BUDGET TYPE (tout-en-un)

| Outil | Plan gratuit | Plan payant utile |
|-------|--------------|-------------------|
| ElevenLabs | 10 000 caractères/mois (suffit) | Starter 5 $/mois |
| HeyGen | 1 vidéo gratuite/mois | Creator 24 $/mois |
| Runway Gen-3 | 125 crédits gratuits | Standard 12 $/mois |
| Suno | 10 chansons/jour | Pro 8 $/mois |
| CapCut | 100 % gratuit | — |
| **Total** | **0 €** (avec contraintes) | **~30 €** (premium) |

Tu peux tout faire en gratuit en répartissant la prod sur 2-3 jours. 🎬

---

**Prêt à enregistrer ?** Dis-moi sur quel outil tu pars (ElevenLabs + HeyGen ? Synthesia ? autre ?) et je peux t'aider à débugger les prompts si certains rendus ne te plaisent pas. 🚀
