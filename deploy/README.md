# 🚀 Déploiement SignalX sur Hetzner Frankfurt

**Coût** : 4,50 €/mois
**Temps** : ~45 minutes (première fois)
**Résultat** : Live Trading réel sur Binance ✅

---

## 🎯 Étape 1 — Créer ton compte Hetzner (5 min)

1. Va sur **[hetzner.com/cloud](https://www.hetzner.com/cloud)**
2. Tape **"Sign up"** en haut à droite
3. Crée ton compte avec :
   - Email
   - Mot de passe
   - Vérification email
4. Ajoute un moyen de paiement :
   - **Carte bancaire** (recommandé) ou **PayPal**
   - Hetzner vérifie ta carte avec 1 € qui sera remboursé
5. Crée un projet nommé **"SignalX"**

---

## 🖥️ Étape 2 — Louer le VPS (3 min)

Dans Hetzner Cloud Console :

1. Tape **"Add Server"**
2. **Location** : choisis **Falkenstein** ou **Nuremberg** 🇩🇪 (Allemagne)
3. **Image** : **Ubuntu 24.04**
4. **Type** : 
   - ⭐ **CX22** (recommandé) — 2 vCPU, 4 Go RAM, 40 Go SSD — 4,50 €/mois
   - Alternative : CX21 (idem mais Intel ancienne gén) — 4,50 €/mois
5. **Networking** : laisse les options par défaut
6. **SSH Keys** : tape **"+ Add SSH Key"** → colle ta clé publique
   - Si tu n'as pas de clé SSH, on en crée une (voir étape 3 ci-dessous)
   - OU sélectionne **"Use password"** — un mot de passe te sera envoyé par email
7. **Name** : `signalx-prod`
8. Tape **"Create & Buy now"**

⏱️ Attends ~30 secondes. Tu reçois un email avec :
- L'IP publique du serveur (ex: `49.12.45.67`)
- Le mot de passe root (si pas de clé SSH)

---

## 🔑 Étape 3 — Créer une clé SSH (optionnel mais recommandé, 2 min)

Sur ton PC (Mac/Linux) ou Windows :

### Mac/Linux :
```bash
ssh-keygen -t ed25519 -C "signalx@hetzner"
# Appuie sur Entrée 3 fois (passphrase optionnelle)
cat ~/.ssh/id_ed25519.pub
# Copie la sortie (commence par ssh-ed25519...)
```

### Windows :
```powershell
ssh-keygen -t ed25519 -C "signalx@hetzner"
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

Colle le contenu dans Hetzner → "Add SSH Key".

---

## 🖥️ Étape 4 — Se connecter au VPS (1 min)

```bash
ssh root@TON_IP_HETZNER
# Exemple: ssh root@49.12.45.67
# Tape 'yes' pour accepter la fingerprint
```

Tu es maintenant sur ton VPS. Tu vois `root@signalx-prod:~#`.

---

## 📦 Étape 5 — Récupérer le code SignalX (3 min)

### Option A — Si tu as un compte GitHub (recommandé)

1. Dans Emergent, tape **"Save to GitHub"**
2. Crée un repo privé `signalx`
3. Sur ton VPS :

```bash
cd /opt
git clone https://TON_TOKEN_GITHUB@github.com/TON_USERNAME/signalx.git
cd signalx
```

### Option B — Sans GitHub (transfert direct)

Sur ton PC :
```bash
scp -r /chemin/vers/signalx root@TON_IP:/opt/signalx
```

Puis sur le VPS :
```bash
cd /opt/signalx
```

---

## ⚙️ Étape 6 — Configurer les secrets (5 min)

```bash
cd /opt/signalx
cp deploy/.env.example deploy/.env
nano deploy/.env
```

**Remplir les valeurs** :

```bash
# 1) PUBLIC_URL — si pas de domaine, utilise http://TON_IP
PUBLIC_URL=http://49.12.45.67
# OU avec un domaine
# PUBLIC_URL=https://signalx.ton-domaine.com

# 2) JWT_SECRET — génère-le :
#    openssl rand -hex 32
JWT_SECRET=...le_hex_généré...

# 3) ENCRYPTION_KEY — génère-le :
#    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# (installer cryptography d'abord: apt install -y python3-cryptography)
ENCRYPTION_KEY=...la_clé_fernet...

# 4) EMERGENT_LLM_KEY — copie depuis ton /app/backend/.env preview
EMERGENT_LLM_KEY=sk-emergent-XXX

# 5) Resend & Stripe — copie depuis ton /app/backend/.env preview
RESEND_API_KEY=re_XXX
EMAIL_FROM=noreply@signall.app
STRIPE_SECRET_KEY=sk_live_XXX
# etc.
```

Sauvegarde : `Ctrl+O` puis `Enter` puis `Ctrl+X`.

---

## 🚀 Étape 7 — Lancer le déploiement (15 min)

Une seule commande :
```bash
cd /opt/signalx
sudo bash deploy/scripts/deploy.sh
```

Le script va :
1. ✅ Installer Docker (1 min)
2. ✅ Builder les images backend + frontend (~5 min)
3. ✅ Démarrer MongoDB + backend + frontend + nginx
4. ✅ Vérifier le healthcheck
5. ✅ Te donner les URLs finales

⏱️ **Total : ~10-15 min** (selon vitesse du VPS et réseau)

---

## 🌐 Étape 8 — Tester le déploiement (2 min)

Dans Chrome sur ton téléphone ou PC :

1. **Healthcheck** : `http://TON_IP/api/health`
   - Doit afficher : `{"ok":true,"db":true,...}`
2. **App** : `http://TON_IP/`
   - Tu vois la page de login SignalX
3. **Inscription** : crée ton compte
4. **Test Binance** → Profil → Connecter mon Binance
5. Colle tes clés API → **"Connecter"**

✅ Si tu vois **"Connexion réussie"** → 🎉 **LIVE TRADING DISPONIBLE !**

---

## 🔒 Étape 9 — Activer HTTPS (avec domaine, 5 min)

### A. Pointer ton domaine vers le VPS

Sur ton registrar (Cloudflare, OVH, etc.) :
- Créer un enregistrement **A**
- Nom : `signalx` (ou `app` ou ce que tu veux)
- Valeur : `49.12.45.67` (l'IP de ton VPS)
- Attendre 5-15 min la propagation DNS

### B. Activer le SSL automatique

```bash
cd /opt/signalx
sudo bash deploy/scripts/enable_ssl.sh signalx.ton-domaine.com
```

Ça va :
1. Demander un certificat Let's Encrypt (gratuit)
2. Mettre à jour la config nginx pour HTTPS
3. Recharger nginx

✅ Après : `https://signalx.ton-domaine.com` fonctionne !

---

## 🔄 Commandes utiles

```bash
# Voir les logs du backend en temps réel
cd /opt/signalx/deploy && docker compose logs -f backend

# Voir les logs du bot
docker compose logs -f backend | grep BOT

# Redémarrer le backend
docker compose restart backend

# Tout arrêter
docker compose down

# Tout redémarrer
docker compose up -d

# Mettre à jour le code (après git pull)
docker compose build && docker compose up -d
```

---

## 🆘 Dépannage

### Le backend ne démarre pas
```bash
docker compose logs backend | tail -50
```

### MongoDB ne répond pas
```bash
docker compose logs mongo | tail -30
docker compose exec mongo mongosh --eval "db.runCommand({ping: 1})"
```

### Le frontend affiche une page vide
- Vérifie `PUBLIC_URL` dans `.env`
- Re-build : `docker compose build frontend && docker compose up -d frontend`

### Binance toujours géo-bloqué ? (improbable depuis l'Allemagne)
```bash
docker compose exec backend curl -I https://api.binance.com/api/v3/time
# Doit retourner HTTP 200, pas 451
```

---

## 💰 Récapitulatif coûts

| Item | Coût |
|------|------|
| VPS Hetzner CX22 | 4,50 €/mois |
| Domaine (optionnel) | ~10 €/an |
| SSL Let's Encrypt | **Gratuit** |
| **TOTAL** | **~5 €/mois** |

VS Emergent : **20 €/mois minimum**

→ 💸 **Économie : ~180 €/an** — ET ça marche réellement avec Binance !
