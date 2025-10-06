# Progiciel Dalot - Guide des Nouvelles Fonctionnalités v2.0

## Vue d'ensemble

Cette mise à jour majeure du progiciel de dimensionnement des dalots ajoute des fonctionnalités avancées tout en préservant l'interface existante et la compatibilité avec les projets actuels.

## Nouvelles Fonctionnalités

### 1. Murs en Aile Paramétriques

#### Interface Utilisateur
Dans l'onglet **📐 Géométrie**, une nouvelle section "Murs en aile" permet de configurer :

**Aile Gauche / Aile Droite :**
- ✅ **Activer** : Case à cocher pour activer/désactiver l'aile
- 📐 **Angle (°)** : Angle en plan par rapport à la perpendiculaire (0-180°)
- 📏 **Longueur (m)** : Longueur de l'aile depuis le dalot
- 📐 **Épaisseur (m)** : Épaisseur constante du mur
- 🔽 **Fruit V/H** : Décalage horizontal au sommet (batter)
- ↕️ **Décalage tête (m)** : Décalage longitudinal en tête de dalot

#### Visualisation 3D
- Rendu automatique des ailes activées avec géométrie paramétrique
- Couleurs distinctives : rose clair (gauche), prune clair (droite)
- Ajustement automatique des limites d'affichage
- Sélection interactive des faces avec inspection des paramètres

### 2. Matériaux Personnalisables

#### Béton (Section "Surcharges manuelles")
- **fck (MPa)** : Résistance caractéristique (remplace la classe si renseigné)
- **γc** : Coefficient de sécurité sur le béton (défaut: 1.5)
- **αcc** : Coefficient d'efficacité à long terme (défaut: 1.0)  
- **Enrobage (mm)** : Enrobage des armatures (remplace la classe d'exposition)

#### Acier (Section "Surcharges manuelles")
- **fyk (MPa)** : Limite d'élasticité caractéristique
- **γs** : Coefficient de sécurité sur l'acier (défaut: 1.15)
- **Es (MPa)** : Module d'élasticité (défaut selon classe)
- **wk (mm)** : Ouverture de fissure admissible (optionnel)

### 3. Paramètres Sol et Charges Avancés

#### Propriétés du Sol
- **γsol (kN/m³)** : Poids volumique du sol de remblai
- **φ (°)** : Angle de frottement interne  
- **c (kPa)** : Cohésion du sol
- **Ka manuel** : Surcharge du coefficient de poussée active (optionnel)
- **K0 manuel** : Surcharge du coefficient de poussée au repos (optionnel)

#### Charges et Combinaisons
- **Surcharge trafic q (kN/m²)** : Charge de trafic personnalisée
- **Surcharge perm. supp. (kN/m²)** : Charges permanentes additionnelles
- **γG** : Facteur de sécurité sur charges permanentes (défaut: 1.35)
- **γQ** : Facteur de sécurité sur charges variables (défaut: 1.5)  
- **ψ0** : Facteur de combinaison (défaut: 0.7)

### 4. Calculs Enrichis

#### Poussée des Terres
- **Formule de Rankine** : Ka = tan²(π/4 - φ/2) pour poussée active
- **Formule de Jaky** : K0 = 1 - sin φ pour poussée au repos
- **Profil de pression latérale** : σh(z) = Ka·γsol·z + Ka·q
- Prise en compte des surcharges de surface dans la poussée

#### Combinaisons de Charges  
- **ELS** : qELS = q_pp + q_perm_supp + q_trafic
- **ELU** : qELU = γG·(q_pp + q_perm_supp) + γQ·q_trafic
- Facteurs personnalisables par l'utilisateur

#### Dimensionnement BA
- Calcul avec fcd = αcc·fck/γc et fyd = fyk/γs personnalisables
- Prise en compte de l'enrobage utilisateur dans la hauteur utile d
- Formules EC2 pour le calcul des armatures

### 5. Rapport Enrichi

Le rapport de dimensionnement inclut désormais :

#### Section Paramètres de Calcul
- Caractéristiques détaillées des matériaux utilisés
- Propriétés du sol et coefficients de poussée avec formules appliquées  
- Facteurs de combinaison et charges considérées

#### Section Murs en Aile  
- Configuration géométrique de chaque aile activée
- Paramètres de fruit et décalages

#### Section Méthodologie
- Références aux normes et formules utilisées
- Traçabilité des coefficients appliqués

### 6. Inspection Interactive 3D

#### Faces de Murs en Aile
Lors du clic sur une face d'aile, affichage de :
- 📐 Paramètres géométriques (angle, longueur, épaisseur)
- 🔽 Configuration du fruit et décalages  
- 💨 Forces de poussée associées
- 📍 Point d'application des efforts

## Guide d'Utilisation

### Configuration d'un Projet avec Murs en Aile

1. **Géométrie de Base**
   - Définir les dimensions principales du dalot (L×l×H)
   - Spécifier les épaisseurs des dalles et voiles

2. **Configuration des Ailes**
   - Activer les ailes souhaitées (gauche/droite)
   - Définir angle, longueur et épaisseur
   - Ajuster le fruit si nécessaire pour la stabilité

3. **Matériaux Personnalisés**
   - Laisser vide pour utiliser les classes standards
   - Renseigner les valeurs manuelles pour surcharger

4. **Paramètres Sol**
   - Entrer γsol, φ, c selon l'étude géotechnique
   - Laisser Ka/K0 vides pour calcul automatique (recommandé)

5. **Validation 3D**
   - Vérifier la géométrie dans la vue 3D
   - Cliquer sur les faces pour inspection détaillée

### Bonnes Pratiques

#### Murs en Aile
- **Angles typiques** : 90° (perpendiculaire), 135° (oblique)
- **Longueurs** : 1.5 à 3.0 fois la hauteur du dalot
- **Fruit** : 0 à 0.2 V/H pour la stabilité structurelle

#### Paramètres Sol
- Utiliser les valeurs de l'étude géotechnique
- Vérifier la cohérence φ/c selon la nature du sol
- Les surcharges Ka/K0 manuelles sont réservées aux cas exceptionnels

#### Matériaux
- Privilégier les classes normalisées pour les projets courants
- Les surcharges manuelles permettent l'adaptation à des contextes spécifiques
- Vérifier la cohérence fck/classe d'exposition/enrobage

## Compatibilité

### Projets Existants
- **✅ Totalement compatible** : Tous les projets existants continuent de fonctionner
- Les nouvelles fonctionnalités sont optionnelles et n'affectent pas les calculs existants
- Les valeurs par défaut correspondent au comportement antérieur

### Migration
- Aucune migration requise pour les fichiers existants
- Les nouveaux paramètres prennent automatiquement des valeurs par défaut sensées

## Support et Validation

### Tests de Validation
- ✅ Formules de Rankine et Jaky validées (φ=28° → Ka=0.361, K0=0.531)
- ✅ Géométrie des murs en aile conforme aux spécifications
- ✅ Calculs EC2 avec matériaux personnalisés

### Limites Actuelles
- La vérification à la fissuration (wk) est préparée mais non implémentée
- Les murs en aile sont représentés mais leurs calculs spécifiques restent à développer
- Les combinaisons accidentelles ne sont pas encore intégrées

---

**Note** : Cette version enrichit considérablement les possibilités du progiciel tout en préservant sa simplicité d'usage. Pour toute question ou demande de fonctionnalité, se référer au dépôt GitHub du projet.