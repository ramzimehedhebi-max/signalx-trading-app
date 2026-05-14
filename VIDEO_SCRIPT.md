# 🎬 Script Vidéo Tutoriel SignalX

**Durée cible** : 5–6 minutes
**Format** : screencast + caméra (PIP en bas à droite optionnel)
**Ton** : direct, rassurant, pédagogue. Tu parles à un débutant complet.
**Plan** : Hook (15 s) → Sécurité (45 s) → Dépôt (1 min 30) → Connexion (1 min 15) → Bot (1 min 30) → Retrait (45 s) → Outro (30 s)

---

## 🎯 HOOK — 0:00 → 0:15

**[À l'écran : app SignalX ouverte sur Dashboard P&L avec courbe verte qui monte]**

> "Salut, dans cette vidéo je vais te montrer **comment faire travailler ton argent sur Binance grâce à un bot IA, sans rien y connaître**. En moins de 6 minutes tu sauras où mettre tes premiers euros, comment les laisser trader en automatique, et surtout — comment les récupérer quand tu veux."

**[Cut → titre animé "SignalX — Guide A à Z"]**

---

## 🔒 SÉCURITÉ EN PREMIER — 0:15 → 1:00

**[À l'écran : zoom sur la bannière "Tes fonds restent chez toi" dans l'app]**

> "Avant tout, **la règle d'or** : SignalX **ne stocke jamais ton argent**. Tes euros, tes cryptos, ils restent à 100 % sur **ton** compte Binance. SignalX, c'est juste un cerveau qui envoie des ordres d'achat et de vente sur ton compte — comme un trader pro qui regarderait par-dessus ton épaule, mais en mode automatique 24h/24."

**[À l'écran : illustration avec deux carrés "Binance : tes fonds" → flèche → "SignalX : juste des ordres"]**

> "Et la cerise sur le gâteau : on va configurer les clés API **sans permission de retrait**. Ça veut dire que même si demain quelqu'un piratait SignalX, il ne pourrait **pas** sortir un euro de ton compte. C'est mathématiquement impossible."

---

## 💰 DÉPÔT SUR BINANCE — 1:00 → 2:30

**[Cut → navigateur sur binance.com/register]**

> "OK donc première étape : on va **créer un compte Binance** si tu n'en as pas déjà un. C'est gratuit, prend 5 minutes. Email, mot de passe, et la vérification d'identité — carte d'identité plus selfie. Une fois validé, t'es prêt."

**[À l'écran : app Binance mobile, page d'accueil]**

> "Ensuite, **comment mettre de l'argent sur Binance ?** T'as trois options :"

**[Texte à l'écran : "1. Carte bancaire — rapide, ~2 % de frais"]**

> "**Option 1, la plus simple** : carte bancaire. Tu vas sur l'app Binance, tu cliques sur 'Dépôt', puis 'Acheter avec carte'. Tu achètes directement de l'**USDT** — c'est la monnaie qu'on va utiliser pour trader. Frais autour de 2 %, mais c'est instantané."

**[Texte à l'écran : "2. Virement SEPA — gratuit, 1-2 jours"]**

> "**Option 2, la moins chère** : virement SEPA. Dans Binance tu vas dans 'Dépôt' → 'EUR' → 'Virement SEPA'. Tu récupères l'IBAN affiché, tu fais un virement depuis ta banque, et 1 à 2 jours plus tard, l'argent arrive. **Zéro frais.** Une fois reçu, tu convertis tes euros en USDT via l'outil 'Convertir'. Taux instantané, frais quasi nuls."

**[Texte à l'écran : "3. Crypto depuis un autre wallet"]**

> "**Option 3** : si t'as déjà du Bitcoin ou de l'Ethereum quelque part — Coinbase, Kraken, ou un hardware wallet — tu peux le transférer sur Binance et le convertir en USDT."

**[À l'écran : zoom sur le solde USDT sur Binance]**

> "**Conseil important** : pour commencer, mets **100 à 300 €**. Pas plus. Apprends d'abord, ajoute plus tard si ça te plaît."

---

## 🔗 CONNECTER BINANCE À SIGNALX — 2:30 → 3:45

**[Cut → app SignalX, écran Profil]**

> "Maintenant la partie technique, mais je te promets que c'est rapide. Dans SignalX tu vas dans 'Profil' → 'Connecter mon Binance'. L'app t'affiche un tutoriel pas à pas, mais je te le résume."

**[À l'écran : split screen — Binance API Management à gauche, SignalX à droite]**

> "Sur Binance, tu vas dans **Profil** → **API Management** → **Create API** → tu choisis 'System generated'."

**[À l'écran : zoom sur les permissions]**

> "**Et là, attention.** Tu actives **uniquement** : ✅ **Enable Spot & Margin Trading**. C'est tout. Tu **désactives** absolument : ❌ Enable Withdrawals et ❌ Enable Universal Transfer."

**[Texte à l'écran en rouge : "JAMAIS Enable Withdrawals"]**

> "Pourquoi ? Parce que si tu laisses Withdrawals activé, en théorie quelqu'un avec tes clés pourrait sortir l'argent. En le désactivant : impossible. Les clés ne servent qu'à passer des ordres d'achat/vente."

**[À l'écran : copier-coller des clés dans SignalX]**

> "Tu copies l'API Key et l'API Secret. Tu les colles dans SignalX. **Hop, c'est connecté.** Tes clés sont chiffrées en AES-128 dans notre base — personne, même pas notre support, ne peut les lire en clair."

---

## ⚙️ CONFIGURER LE BOT — 3:45 → 5:15

**[Cut → onglet Bot dans SignalX]**

> "Maintenant le **cœur du système** : le bot IA. Avant de risquer un euro, on va le tester en **mode PAPER**."

**[À l'écran : badge "MODE PAPER — SIMULATION"]**

> "Le mode Paper, c'est du trading en simulation. Le bot utilise les **vrais prix Binance en temps réel**, mais avec **un capital virtuel** de 1000 USDT. Aucun argent réel n'est touché. Tu actives le bot, et tu observes pendant **1 à 2 semaines** comment il performe."

**[À l'écran : Settings du bot, on scroll jusqu'à "Features avancées"]**

> "Dans les paramètres, je te recommande pour commencer :
> - Stop-loss à **3 %** — la perte max par trade
> - Take-profit à **8–10 %**
> - Position size **10–20 %** du capital
> - Maximum **3 à 5 positions** ouvertes en même temps
> - Paires : **BTC, ETH, SOL** pour commencer. Volatilité maîtrisée."

**[À l'écran : section Features avancées avec les 3 toggles]**

> "On a aussi 3 features avancées que tu peux activer :
> - **Diversification auto** : le bot évite de trader plein de cryptos corrélées en même temps
> - **Trailing Take-Profit** : quand un trade gagne fort, on laisse courir au lieu de fermer trop tôt
> - **Prises partielles** : on verrouille 50 % du gain à +3 %, puis 30 % à +6 %, et on garde 20 % pour la suite."

**[Cut → Dashboard P&L]**

> "Pendant que le bot tourne, tu peux **suivre tes perfs** dans le Dashboard P&L : capital qui évolue, win-rate, drawdown maximal, top cryptos rentables. Bref, t'as tout sous les yeux."

**[À l'écran : badge "MODE LIVE — ARGENT RÉEL"]**

> "Et quand t'es **vraiment prêt** — et seulement quand t'es prêt — tu bascules en **mode LIVE**. Là, le bot exécute des **vrais ordres** sur ton compte Binance. Avec une limite de sécurité par défaut à **50 $ max par trade**, modifiable."

---

## 💸 RETIRER TES GAINS — 5:15 → 6:00

**[Cut → Binance Spot Wallet]**

> "Comment tu récupères tes gains ? **Directement sur Binance.** SignalX ne gère pas tes retraits — c'est toi qui restes propriétaire."

**[À l'écran : étapes 1-2-3-4 numérotées]**

> "1. Tu vas sur Binance, **Spot Wallet** — tu vois ton solde mis à jour en temps réel.
> 2. Tu cliques **Convertir** → USDT vers EUR
> 3. Tu vas dans **Retrait** → **Virement SEPA**
> 4. Tu colles ton IBAN, et **1 à 2 jours plus tard**, l'argent est sur ton compte en banque. **Gratuit.**"

**[À l'écran : toggle "BOT ACTIVE" passant à OFF]**

> "Et si tu veux **stopper le bot** à tout moment ? Onglet Bot, toggle OFF. Ou Kill-switch pour une pause immédiate sans clôturer les positions ouvertes."

---

## 🎯 OUTRO — 6:00 → 6:30

**[À l'écran : récap des 4 étapes "Dépose → Connecte → Configure → Surveille"]**

> "Récap : tu **déposes** sur Binance, tu **connectes** les clés API sans permission de retrait, tu **configures** le bot en mode Paper d'abord, et tu **surveilles** depuis le Dashboard. Quand t'es à l'aise, tu passes en Live."

**[À l'écran : logo SignalX + lien profil → Aide & Support]**

> "**Dernier mot** : le trading crypto comporte des risques. Le bot peut perdre comme gagner. Le stop-loss limite la casse, mais aucune garantie. Trade **uniquement** avec de l'argent que tu peux te permettre de perdre."

> "Si t'as une question, tout est détaillé dans **Profil → Aide & Support**, ou écris-nous à **support@signall.app**. Bon trading, et à bientôt 👋"

**[Fin → écran de fin avec QR code App Store / Play Store optionnel]**

---

## 📝 Notes de production

- **Voix** : Ton naturel, comme si tu parlais à un pote. Ne sois pas formel.
- **Rythme** : Tiens-toi à 130-150 mots/min (lent pour audience débutante).
- **B-rolls** :
  - 0:15 — capture écran bannière sécurité (5 s)
  - 1:00 — capture binance.com (3 s)
  - 1:30 — capture dépôt SEPA (5 s)
  - 2:45 — split screen Binance/SignalX (10 s)
  - 3:30 — zoom sur permissions API (5 s)
  - 4:00 — paramètres bot (10 s)
  - 4:45 — Dashboard P&L (5 s)
  - 5:30 — retrait SEPA Binance (5 s)
- **Musique** : Sub-tle background, calme, pas distractive. Un truc lo-fi ou ambient downtempo. Suggestions : YouTube Audio Library (recherche "calm tech").
- **Sous-titres** : OBLIGATOIRES. 70 % des gens regardent sans le son.
- **Thumbnail** : Capture du Dashboard P&L avec courbe verte qui monte, + texte "Bot IA Binance — Guide complet". Couleur de fond : noir/bleu nuit pour matcher la marque.
- **Export** : 1080p minimum, format 16:9.

## 🚀 Une fois la vidéo prête

1. Upload sur YouTube (mode non répertorié ou public)
2. Copie l'URL (format `https://www.youtube.com/watch?v=XXXXXXXX`)
3. Dans SignalX → utilise l'URL dans `app.json` ou directement dans le code (`/app/frontend/app/help.tsx` — section vidéo en haut)
4. Le lecteur YouTube est intégré et responsive

Tu peux aussi commencer par une version **2 minutes** très condensée pour tes premiers utilisateurs, puis ajouter une version longue plus tard.
