#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kleinlogel - toutes les routines calculent en TONNES (t, t/m, t/m²)
Version affichant les paramètres internes et les charges utilisées pour les convois (Bc, Bt, Br).
Modifications :
 - stockage et affichage des pressions convois en t/m² et des charges linéiques utilisées (t/m, largeur tributaire = 1 m)
 - conservation des autres diagnostics (j1,j2,j3,k1,k2,F1,..., coef_MA)
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font
from dataclasses import dataclass
from typing import Dict, Any
import math
import csv
from datetime import datetime

# constantes de conversion
GN_PAR_T = 9810.0                     # 1 t ≈ 9810 N (utilisé uniquement pour conversion UI -> t)
KILO_NEWTON_EN_N = 1000.0             # 1 kN = 1000 N

# ----------------------------
# Classes de données (noms français)
# ----------------------------
@dataclass
class Materiau:
    gamma_b_kN_m3: float = 25.0   # entrée UI en kN/m³
    E: float = 22e9
    nu: float = 0.3

    @property
    def gamma_b_t_m3(self) -> float:
        # convertir kN/m3 -> t/m3 : 1 kN/m3 = 1000 N/m3 ; 1 t = 9810 N => factor = 1000/9810
        return self.gamma_b_kN_m3 * (KILO_NEWTON_EN_N / GN_PAR_T)

@dataclass
class Sol:
    gamma_sol_kN_m3: float = 20
    phi_deg: float = 30
    c_pa: float = 0.0  # en Pa

    @property
    def gamma_sol_t_m3(self) -> float:
        return self.gamma_sol_kN_m3 * (KILO_NEWTON_EN_N / GN_PAR_T)

@dataclass
class GeometrieDalot:
    Li_m: float
    Hi_m: float
    e_dalle_m: float
    e_voile_m: float
    e_radier_m: float

# ----------------------------
# Classe Kleinlogel (t-units)
# ----------------------------
SOL_KEYS = ["MA", "MD", "MB", "MC", "M_BC", "M_AD", "M_AB", "M_CD", "S1", "S2", "S2_prime", "S3"]

class Kleinlogel:
    def __init__(self, geom: GeometrieDalot, materiau: Materiau = None, sol: Sol = None,
                 F_br_tonnes: float = 10.0, bc_defaut: float = 1.1, bt_defaut: float = 1.0):
        self.geom = geom
        self.materiau = materiau or Materiau()
        self.sol = sol or Sol()
        self.bc_defaut = bc_defaut
        self.bt_defaut = bt_defaut
        # F_br en tonnes (utilisé uniquement pour convoi Br si besoin)
        self.F_br_t = F_br_tonnes
        self._calculer_parametres()

    def _calculer_parametres(self):
        g = self.geom
        # définitions géométriques utilisées par les formules
        self.h_eff = g.Hi_m + g.e_dalle_m / 2.0 + g.e_radier_m / 2.0
        self.l_eff = g.Li_m + g.e_voile_m
        self.j1 = (g.e_radier_m ** 3) / 12.0
        self.j2 = (g.e_voile_m ** 3) / 12.0
        self.j3 = (g.e_dalle_m ** 3) / 12.0
        self.k1 = (self.j3 / self.j1) if self.j1 != 0 else 0.0
        # k2 = (j3/j2) * (h_eff / l_eff)
        if self.j2 != 0 and self.l_eff != 0:
            self.k2 = (self.j3 / self.j2) * (self.h_eff / self.l_eff)
        else:
            self.k2 = 0.0
        self.K1 = 2.0 * self.k2 + 3.0
        self.K2 = 3.0 * self.k1 + 2.0 * self.k2
        self.K3 = 3.0 * self.k2 + 1.0 - self.k1 / 5.0
        self.K4 = (6.0 * self.k1) / 5.0 + 3.0 * self.k2
        self.F1 = self.K1 * self.K2 - self.k2 ** 2
        self.F2 = 1.0 + self.k1 + 6.0 * self.k2
        if abs(self.F1) < 1e-12:
            self.F1 = 1e-12

    def calculer_Ka(self, phi_deg: float = None) -> float:
        phi = math.radians(self.sol.phi_deg if phi_deg is None else phi_deg)
        return (math.tan(math.pi / 4.0 - phi / 2.0)) ** 2

    # ----------------------------
    # routines INTERNES : EN T (t/m², t, etc.)
    # Elles renvoient : moments en t·m et efforts en t.
    # ----------------------------
    def _moments_uniforme_t(self, q_t_par_m2: float) -> Dict[str, float]:
        q_t_par_m = q_t_par_m2 * 1.0
        l = self.l_eff; h = self.h_eff; F1 = self.F1; k1 = self.k1; k2 = self.k2; K1 = self.K1; K2 = self.K2
        MA = MD = (-q_t_par_m * l ** 2 / (4.0 * F1)) * (k1 * K1 - k2)
        MB = MC = (-q_t_par_m * l ** 2 / (4.0 * F1)) * (K2 - k2 * k1)
        M_BC = (MB + MC) / 2.0 + (q_t_par_m * l ** 2) / 8.0
        M_AD = (MA + MD) / 2.0 + (q_t_par_m * l ** 2) / 8.0
        M_AB = (MA + MB) / 2.0
        M_CD = (MC + MD) / 2.0
        S1 = (MB - MA) / h if h != 0 else 0.0
        S3 = -S1
        S2 = S2_prime = q_t_par_m * l / 2.0
        return {"MA": MA, "MB": MB, "MC": MC, "MD": MD,
                "M_BC": M_BC, "M_AD": M_AD, "M_AB": M_AB, "M_CD": M_CD,
                "S1": S1, "S2": S2, "S2_prime": S2_prime, "S3": S3}

    def _moments_symetrique_t(self, sigma1_t_par_m2: float, sigma2_t_par_m2: float) -> Dict[str, float]:
        sigma1 = sigma1_t_par_m2
        sigma2 = sigma2_t_par_m2
        delta = sigma2 - sigma1
        h = self.h_eff; F1 = self.F1; k1 = self.k1; k2 = self.k2
        MA = MD = -(k2 * (k2 + 3.0) * sigma1 * h ** 2) / (4.0 * F1) - (k2 * (3.0 * k2 + 8.0) * delta * h ** 2) / (20.0 * F1)
        MB = MC = -(k2 * (3.0 * k1 + k2) * sigma1 * h ** 2) / (4.0 * F1) - (k2 * (7.0 * k1 + 2.0 * k2) * delta * h ** 2) / (20.0 * F1)
        M_BC = (MB + MC) / 2.0; M_AD = (MA + MD) / 2.0
        M_AB = (MA + MB) / 2.0 + (delta * h ** 2) / 12.0 + (sigma1 * h ** 2) / 8.0
        M_CD = M_AB
        S1 = ((sigma1 + 2.0 * sigma2) * h) / 6.0 + (MB - MA) / h + (MD - MA) / self.l_eff
        S3 = ((2.0 * sigma1 + sigma2) * h) / 6.0 + (MA - MB) / h + (MC - MB) / self.l_eff
        S2 = S2_prime = 0.0
        return {"MA": MA, "MB": MB, "MC": MC, "MD": MD,
                "M_BC": M_BC, "M_AD": M_AD, "M_AB": M_AB, "M_CD": M_CD,
                "S1": S1, "S2": S2, "S2_prime": S2_prime, "S3": S3}

    def _moments_concentrees_t(self, P_t: float) -> Dict[str, float]:
        P = P_t
        l = self.l_eff; h = self.h_eff; F1 = self.F1; k1 = self.k1; K1 = self.K1; k2 = self.k2
        Rs = (2.0 * P) / l if l != 0 else 0.0
        MA = MD = -(P * l * k1 * K1) / (2.0 * F1)
        MB = MC = (P * l * k1 * k2) / (2.0 * F1)
        M_BC = (MB + MC) / 2.0
        M_AD = (MA + MD) / 2.0 + (Rs * l ** 2) / 8.0
        M_AB = (MA + MB) / 2.0
        M_CD = (MC + MD) / 2.0
        S1 = (3.0 * P * l * k1 * (1.0 + k2)) / (2.0 * h * F1) if h != 0 else 0.0
        S3 = -S1
        S2 = S2_prime = P
        return {"MA": MA, "MB": MB, "MC": MC, "MD": MD,
                "M_BC": M_BC, "M_AD": M_AD, "M_AB": M_AB, "M_CD": M_CD,
                "S1": S1, "S2": S2, "S2_prime": S2_prime, "S3": S3}
    
    def _moments_surcharge_t(self, sigma_t_par_m2: float) -> Dict[str, float]:
        # surcharge routière appliquée sur les piedroits (sigma en t/m²)
        sigma = sigma_t_par_m2
        h = self.h_eff; F1 = self.F1; k1 = self.k1; k2 = self.k2
        # ici l'expression suit la forme simplifiée : on applique une pression sigma sur les piedroits
        MA = -(k2 * (k2 + 3.0) * sigma * h ** 2) / (4.0 * F1)
        # on considère MD = MC = MB = MA (symétrie pour cette surcharge simplifiée)
        MD = MC = MB = MA

        M_AB = (MA + MB) / 2.0 + (sigma * h ** 2) / 8.0
        M_AD = (MA + MD) / 2.0
        M_BC = (MB + MC) / 2.0
        M_CD = M_AB

        S1 = (sigma * h) / 2.0
        S2 = S2_prime = 0.0
        S3 = S1

        return {"MA": MA, "MB": MB, "MC": MC, "MD": MD,
                "M_BC": M_BC, "M_AD": M_AD, "M_AB": M_AB, "M_CD": M_CD,
                "S1": S1, "S2": S2, "S2_prime": S2_prime, "S3": S3}




    # Convois renvoient maintenant des pressions en t/m² (tonnes par m²)
    def q_convoi_Bc_t(self, hr_m: float, bc: float = None) -> float:
        bc = self.bc_defaut if bc is None else bc
        numer_t = 2.0 * 6.0  # tonnes
        denom = (0.25 + 2.0 * hr_m) ** 2
        q_t_m2 = (numer_t / denom) if denom != 0 else 0.0
        delta = 1.0 + 0.64 / (1.0 + 0.2 * 1)
        return q_t_m2 * bc * delta

    def q_convoi_Bt_t(self, hr_m: float, bt: float = None) -> float:
        bt = self.bt_defaut if bt is None else bt
        numer_t = 2.0 * 8.0
        denom = (0.25 + 2.0 * hr_m) * (0.6 + 2.0 * hr_m)
        q_t_m2 = (numer_t / denom) if denom != 0 else 0.0
        return q_t_m2 * bt

    def q_convoi_Br_t(self, hr_m: float) -> float:
        numer_t = 10.0
        denom = (0.3 + 2.0 * hr_m) * (0.6 + 2.0 * hr_m)
        q_t_m2 = (numer_t / denom) if denom != 0 else 0.0
        return q_t_m2

# ----------------------------
# Fonctions utilitaires pour récapitulatif
# ----------------------------
def additionner_resultats(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    out = {}
    for k in SOL_KEYS:
        out[k] = a.get(k, 0.0) + b.get(k, 0.0)
    return out

def multiplier_resultat_par_scalaire(a: Dict[str, float], scalaire: float) -> Dict[str, float]:
    """
    Nom principal utilisé dans le code : multiplier_resultat_par_scalaire
    (forme française) — multiplie chaque composante du dictionnaire par un scalaire.
    """
    out = {}
    for k in SOL_KEYS:
        out[k] = a.get(k, 0.0) * scalaire
    return out

# Wrapper de compatibilité (corrige l'ancien nom avec faute de frappe)
def multiplier_result_par_scalaire(a: Dict[str, float], scalaire: float) -> Dict[str, float]:
    return multiplier_resultat_par_scalaire(a, scalaire)

def construire_tableau_recap(carte_resultats: Dict[str, Any], kle: Kleinlogel) -> Dict[str, Dict[str, float]]:
    """
    Prend carte_resultats contenant résultats (en t·m et t pour efforts) et renvoie le récap.
    """
    recap = {}
    recap["1 - Charges sur tablier"] = carte_resultats["service"]
    recap["2 - Poids propre voile"] = carte_resultats["voile"]
    recap["3 - Poussée latérale"] = carte_resultats["poussee"]
    recap["4 - Charge du convoi Bc"] = carte_resultats["bc"]
    recap["5 - Charge du convoi Bt"] = carte_resultats["bt"]
    recap["6 - Charge du convoi Br"] = carte_resultats["br"]
    recap["7 - convoi de type max(BC,Bt,Br)"] = carte_resultats["max_convoi"]
    recap["8 - Surcharge routière"] = carte_resultats["surcharge"]

    G = additionner_resultats(recap["1 - Charges sur tablier"], recap["2 - Poids propre voile"])
    G = additionner_resultats(G, recap["3 - Poussée latérale"])
    recap["G (1+2+3)"] = G

    Q = additionner_resultats(recap["7 - convoi de type max(BC,Bt,Br)"], recap["8 - Surcharge routière"])
    recap["Q (7+8)"] = Q

    # utilise le nom correct (multiplier_resultat_par_scalaire). Le wrapper garantit compatibilité.
    ELU = additionner_resultats(multiplier_resultat_par_scalaire(G, 1.35), multiplier_resultat_par_scalaire(Q, 1.5))
    recap["combinaison ELU (1.35G+1.5Q)"] = ELU

    ELS = additionner_resultats(G, Q)
    recap["combinaison ELS (G+Q)"] = ELS

    return recap

# ----------------------------
# Interface utilisateur
# ----------------------------
class InterfaceDalot:
    def __init__(self, master):
        self.master = master
        master.title("Kleinlogel - calculs en t / t/m² + charges convois affichées")

        # fenêtre
        try:
            sw = master.winfo_screenwidth(); sh = master.winfo_screenheight()
            w = min(1400, sw - 50); h = min(900, sh - 80)
            master.geometry(f"{w}x{h}")
        except:
            pass

        # variables UI
        self.Li_m = tk.DoubleVar(value=3.0)
        self.Hi_m = tk.DoubleVar(value=2.5)
        self.e_dalle_m = tk.DoubleVar(value=0.20)
        self.e_voile_m = tk.DoubleVar(value=0.20)
        self.e_radier_m = tk.DoubleVar(value=0.20)
        self.hr_m = tk.DoubleVar(value=1.0)
        self.bc = tk.DoubleVar(value=1.1)
        self.bt = tk.DoubleVar(value=1.0)
        self.gamma_b_kN_m3 = tk.DoubleVar(value=25.0)
        self.gamma_sol_kN_m3 = tk.DoubleVar(value=18.0)
        self.phi_deg = tk.DoubleVar(value=45.0)
        self.c_pa = tk.DoubleVar(value=20000.0)
        self.q_surcharge_kN_m2 = tk.DoubleVar(value=0.0)

        frm = ttk.Frame(master, padding=8); frm.pack(fill=tk.BOTH, expand=True)
        gauche = ttk.Frame(frm); gauche.pack(side=tk.LEFT, anchor=tk.NW, fill=tk.Y)
        droite = ttk.Frame(frm); droite.pack(side=tk.LEFT, anchor=tk.N, fill=tk.BOTH, expand=True)

        row = 0
        def ajouter_label_champ(parent, texte, var):
            nonlocal row
            ttk.Label(parent, text=texte).grid(row=row, column=0, sticky=tk.W, padx=2, pady=2)
            ttk.Entry(parent, textvariable=var, width=14).grid(row=row, column=1, sticky=tk.W, padx=2, pady=2)
            row += 1

        ajouter_label_champ(gauche, "Largeur intérieure Li (m):", self.Li_m)
        ajouter_label_champ(gauche, "Hauteur intérieure Hi (m):", self.Hi_m)
        ajouter_label_champ(gauche, "Épaisseur dalle e_dalle (m):", self.e_dalle_m)
        ajouter_label_champ(gauche, "Épaisseur voile e_voile (m):", self.e_voile_m)
        ajouter_label_champ(gauche, "Épaisseur radier e_radier (m):", self.e_radier_m)
        ajouter_label_champ(gauche, "Hauteur remblai hr (m):", self.hr_m)
        ajouter_label_champ(gauche, "gamma_b (béton) (kN/m³):", self.gamma_b_kN_m3)
        ajouter_label_champ(gauche, "gamma_sol (kN/m³):", self.gamma_sol_kN_m3)
        ajouter_label_champ(gauche, "phi (°):", self.phi_deg)
        ajouter_label_champ(gauche, "c (Pa):", self.c_pa)
        ajouter_label_champ(gauche, "q surcharge (kN/m²):", self.q_surcharge_kN_m2)
        ajouter_label_champ(gauche, "bc (par défaut 1.1):", self.bc)
        ajouter_label_champ(gauche, "bt (par défaut 1.0):", self.bt)

        ttk.Button(gauche, text="Calculer", command=self.calculer).grid(row=row, column=0, pady=6, sticky=tk.W)
        ttk.Button(gauche, text="Afficher récapitulatif", command=self.afficher_recap).grid(row=row, column=1, pady=6)
        ttk.Button(gauche, text="Exporter CSV récap", command=self.exporter_csv).grid(row=row, column=2, pady=6)
        row += 1

        self.font_mono = font.Font(family="Courier", size=10)
        self.resume = tk.Text(droite, width=100, height=22, font=self.font_mono)
        self.resume.pack(fill=tk.BOTH, expand=False, padx=6, pady=6)

        self.dernier_resultats: Dict[str, Any] = {}
        self.dernier_recap: Dict[str, Dict[str, float]] = {}

    def calculer(self):
        try:
            geom = GeometrieDalot(Li_m=self.Li_m.get(), Hi_m=self.Hi_m.get(),
                                  e_dalle_m=self.e_dalle_m.get(), e_voile_m=self.e_voile_m.get(), e_radier_m=self.e_radier_m.get())
            materiau = Materiau(gamma_b_kN_m3=self.gamma_b_kN_m3.get())
            sol = Sol(gamma_sol_kN_m3=self.gamma_sol_kN_m3.get(), phi_deg=self.phi_deg.get(), c_pa=self.c_pa.get())
            kle = Kleinlogel(geom, materiau=materiau, sol=sol, F_br_tonnes=10.0, bc_defaut=self.bc.get(), bt_defaut=self.bt.get())

            # Ka en coeff adimensionnel
            Ka = kle.calculer_Ka(phi_deg=self.phi_deg.get())
            hr_m = self.hr_m.get()

            # convertir gamma en t/m³ pour utiliser unités t
            gamma_b_t_m3 = materiau.gamma_b_t_m3
            gamma_sol_t_m3 = sol.gamma_sol_t_m3

            # sigma (poussee) en t/m²
            sigma1_t_m2 = Ka * gamma_sol_t_m3 * hr_m
            sigma2_t_m2 = Ka * gamma_sol_t_m3 * (hr_m + geom.Hi_m + geom.e_dalle_m + geom.e_radier_m/2.0)

            # poids propre dalle et remblai en t/m²
            p_tablier_t_m2 = gamma_b_t_m3 * geom.e_dalle_m
            p_remblai_t_m2 = gamma_sol_t_m3 * hr_m

            # q permanente totale en t/m² (somme des deux pressions surfaciques)
            q_permanente_t_m2 = p_tablier_t_m2 + p_remblai_t_m2

            # 1 - charges sur tablier (q en t/m²)
            res_service_t = kle._moments_uniforme_t(q_permanente_t_m2)

            # 2 - poids propre voile : P en tonnes (poids d'un piedroit par m courant)
            P_t = gamma_b_t_m3 * (geom.Hi_m + geom.e_dalle_m) * geom.e_voile_m
            res_voile_t = kle._moments_concentrees_t(P_t)

            # 3 - poussée latérale (sigma en t/m²)
            res_poussee_t = kle._moments_symetrique_t(sigma1_t_m2, sigma2_t_m2)

            # 4-6 convois : obtenir q en t/m² puis appeler la routine
            q_bc_t_m2 = kle.q_convoi_Bc_t(hr_m, bc=self.bc.get())
            q_bt_t_m2 = kle.q_convoi_Bt_t(hr_m, bt=self.bt.get())
            q_br_t_m2 = kle.q_convoi_Br_t(hr_m)
            # charges linéiques utilisées (largeur tributaire = 1 m)
            q_bc_t_par_m = q_bc_t_m2 * 1.0
            q_bt_t_par_m = q_bt_t_m2 * 1.0
            q_br_t_par_m = q_br_t_m2 * 1.0

            res_bc_t = kle._moments_uniforme_t(q_bc_t_m2)
            res_bt_t = kle._moments_uniforme_t(q_bt_t_m2)
            res_br_t = kle._moments_uniforme_t(q_br_t_m2)

            # 7 - convoi max
            qmax_t_m2 = max(q_bc_t_m2, q_bt_t_m2, q_br_t_m2)
            res_max_convoi_t = kle._moments_uniforme_t(qmax_t_m2)

            # 8 - surcharge routière : UI en kN/m² -> convertir en t/m²
            q_surcharge_N_m2 = self.q_surcharge_kN_m2.get() * KILO_NEWTON_EN_N
            q_surcharge_t_m2 = q_surcharge_N_m2 / GN_PAR_T
            # pression effective sur piedroits -> sigma_q_t_m2
            sigma_q_t_m2 = q_surcharge_t_m2 * Ka
            # passer la pression effective (sigma) à la routine surcharge
            res_surcharge_t = kle._moments_surcharge_t(sigma_q_t_m2)

            # stocker résultats (en t·m pour moments, t pour efforts) et charges utilisées
            self.dernier_resultats = {
                "service": res_service_t, "voile": res_voile_t, "poussee": res_poussee_t,
                "bc": res_bc_t, "bt": res_bt_t, "br": res_br_t, "max_convoi": res_max_convoi_t,
                "surcharge": res_surcharge_t,
                "q_bc_t_m2": q_bc_t_m2, "q_bt_t_m2": q_bt_t_m2, "q_br_t_m2": q_br_t_m2,
                "q_bc_t_par_m": q_bc_t_par_m, "q_bt_t_par_m": q_bt_t_par_m, "q_br_t_par_m": q_br_t_par_m,
                "q_permanente_t_m2": q_permanente_t_m2,
                "p_tablier_t_m2": p_tablier_t_m2, "p_remblai_t_m2": p_remblai_t_m2,
                "sigma1_t_m2": sigma1_t_m2, "sigma2_t_m2": sigma2_t_m2,
                "P_t": P_t, "Ka": Ka,
                "q_surcharge_t_m2": q_surcharge_t_m2, "sigma_q_t_m2": sigma_q_t_m2
            }

            # --- Paramètres Kleinlogel complets pour vérification ---
            coef_MA = 2.0 * kle.k2 * (kle.k1 - 1.0)
            params_k = {
                "j1": kle.j1,
                "j2": kle.j2,
                "j3": kle.j3,
                "k1": kle.k1,
                "k2": kle.k2,
                "K1": kle.K1,
                "K2": kle.K2,
                "K3": kle.K3,
                "K4": kle.K4,
                "F1": kle.F1,
                "F2": kle.F2,
                "h_eff": kle.h_eff,
                "l_eff": kle.l_eff,
                "gamma_b_t_m3": gamma_b_t_m3,
                "gamma_sol_t_m3": gamma_sol_t_m3,
                "p_tablier_t_m2": p_tablier_t_m2,
                "p_remblai_t_m2": p_remblai_t_m2,
                "q_permanente_t_m2": q_permanente_t_m2,
                "sigma1_t_m2": sigma1_t_m2,
                "sigma2_t_m2": sigma2_t_m2,
                "P_t": P_t,
                "q_bc_t_m2": q_bc_t_m2,
                "q_bt_t_m2": q_bt_t_m2,
                "q_br_t_m2": q_br_t_m2,
                "q_bc_t_par_m": q_bc_t_par_m,
                "q_bt_t_par_m": q_bt_t_par_m,
                "q_br_t_par_m": q_br_t_par_m,
                "qmax_t_m2": qmax_t_m2,
                "q_surcharge_t_m2": q_surcharge_t_m2,
                "sigma_q_t_m2": sigma_q_t_m2,
                "coef_MA": coef_MA
            }
            # stocker aussi pour export / inspection
            self.dernier_resultats["params_kleinlogel"] = params_k

            # construire recap (les valeurs sont déjà en t-units)
            recap_t = construire_tableau_recap(self.dernier_resultats, kle)
            self.dernier_recap = recap_t

            # affichage résumé (t-units) + paramètres détaillés + charges convois utilisées
            summary_lines = []
            summary_lines.append(f"Ka = {Ka:.6f}")
            summary_lines.append(f"σ1 = {sigma1_t_m2:.6f} t/m²   σ2 = {sigma2_t_m2:.6f} t/m²")
            summary_lines.append(f"P piedroit = {P_t:.6f} t (par m courant)")
            summary_lines.append(f"q_tablier (t/m²) = {q_permanente_t_m2:.6f}")
            summary_lines.append("")
            # Charges convois utilisées
            summary_lines.append("--- Charges convois utilisées pour calcul des efforts ---")
            summary_lines.append(f"Bc: q_surface = {q_bc_t_m2:.6f} t/m²   -> q_line = {q_bc_t_par_m:.6f} t/m (largeur trib 1 m)")
            summary_lines.append(f"Bt: q_surface = {q_bt_t_m2:.6f} t/m²   -> q_line = {q_bt_t_par_m:.6f} t/m (largeur trib 1 m)")
            summary_lines.append(f"Br: q_surface = {q_br_t_m2:.6f} t/m²   -> q_line = {q_br_t_par_m:.6f} t/m (largeur trib 1 m)")
            summary_lines.append(f"Surcharge UI -> q_surcharge = {q_surcharge_t_m2:.6f} t/m²  -> sigma_effective_piedroits = {sigma_q_t_m2:.6f} t/m²")
            summary_lines.append("")
            summary_lines.append("Quelques résultats (MA, MB en t·m/ml ; S1 en t/ml) :")
            for label in ["service", "poussee", "voile", "bc", "bt", "br"]:
                vals = self.dernier_resultats.get(label, {})
                MA_tm = vals.get("MA", 0.0)
                MB_tm = vals.get("MB", 0.0)
                S1_t = vals.get("S1", 0.0)
                summary_lines.append(f"{label:10s} MA={MA_tm:10.4f} t·m/ml  MB={MB_tm:10.4f} t·m/ml  S1={S1_t:8.4f} t/ml")

            # ajouter section paramètres Kleinlogel pour vérification
            summary_lines.append("\n--- Paramètres Kleinlogel (pour vérification) ---")
            def fmt_scientific(v): return f"{v:.6e}"
            def fmt_decimal(v): return f"{v:.6f}"
            summary_lines.append(f"j1 = {fmt_scientific(params_k['j1'])}  j2 = {fmt_scientific(params_k['j2'])}  j3 = {fmt_scientific(params_k['j3'])}")
            summary_lines.append(f"k1 = {fmt_decimal(params_k['k1'])}  k2 = {fmt_decimal(params_k['k2'])}")
            summary_lines.append(f"K1 = {fmt_decimal(params_k['K1'])}  K2 = {fmt_decimal(params_k['K2'])}  K3 = {fmt_decimal(params_k['K3'])}  K4 = {fmt_decimal(params_k['K4'])}")
            summary_lines.append(f"F1 = {fmt_scientific(params_k['F1'])}  F2 = {fmt_decimal(params_k['F2'])}")
            summary_lines.append(f"h_eff = {fmt_decimal(params_k['h_eff'])} m  l_eff = {fmt_decimal(params_k['l_eff'])} m")
            summary_lines.append(f"gamma_b = {fmt_decimal(params_k['gamma_b_t_m3'])} t/m³  gamma_sol = {fmt_decimal(params_k['gamma_sol_t_m3'])} t/m³")
            summary_lines.append(f"p_tablier = {fmt_decimal(params_k['p_tablier_t_m2'])} t/m²  p_remblai = {fmt_decimal(params_k['p_remblai_t_m2'])} t/m²")
            summary_lines.append(f"q_permanente = {fmt_decimal(params_k['q_permanente_t_m2'])} t/m²  P_t = {fmt_decimal(params_k['P_t'])} t")
            summary_lines.append(f"q_bc = {fmt_decimal(params_k['q_bc_t_m2'])} t/m²  q_bt = {fmt_decimal(params_k['q_bt_t_m2'])} t/m²  q_br = {fmt_decimal(params_k['q_br_t_m2'])} t/m²")
            summary_lines.append(f"q_bc_line = {fmt_decimal(params_k['q_bc_t_par_m'])} t/m  q_bt_line = {fmt_decimal(params_k['q_bt_t_par_m'])} t/m  q_br_line = {fmt_decimal(params_k['q_br_t_par_m'])} t/m")
            summary_lines.append(f"qmax = {fmt_decimal(params_k['qmax_t_m2'])} t/m²  q_surcharge = {fmt_decimal(params_k['q_surcharge_t_m2'])} t/m²")
            summary_lines.append(f"sigma_q (eff. surcharge on piedroits) = {fmt_decimal(params_k['sigma_q_t_m2'])} t/m²")
            summary_lines.append(f"coef_MA = {fmt_decimal(params_k['coef_MA'])}   (coef_MA = 2*k2*(k1-1))")
            # warning if coef_MA is nearly zero
            if abs(params_k['coef_MA']) < 1e-6:
                summary_lines.append("ATTENTION: coef_MA est proche de zéro -> MA/MD peuvent être nuls (vérifier k1 et k2).")

            self.resume.delete("1.0", tk.END)
            self.resume.insert("1.0", "\n".join(summary_lines))

        except Exception as e:
            messagebox.showerror("Erreur calcul", str(e))

    def afficher_recap(self):
        if not self.dernier_recap:
            messagebox.showinfo("Info", "Aucun résultat calculé. Cliquez sur 'Calculer' d'abord.")
            return
        top = tk.Toplevel(self.master)
        top.title("TABLEAU RECAPITULATIF DES RÉSULTATS DES EFFORTS INTERNES (unités t)")
        sw = top.winfo_screenwidth(); sh = top.winfo_screenheight()
        w = min(1600, sw - 80); h = min(900, sh - 120)
        top.geometry(f"{w}x{h}")

        colonnes = ["Désignation", "MA (t·m/ml)", "MD (t·m/ml)", "MB (t·m/ml)", "MC (t·m/ml)",
                    "M(B-C) Tablier (t·m/ml)", "M(A-D) Radier (t·m/ml)", "M(A-B) Piedroit (t·m/ml)",
                    "S1 (t/ml)", "S2 (t/ml)", "S2' (t/ml)", "S3 (t/ml)"]

        frame = ttk.Frame(top, padding=6); frame.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(frame, orient="vertical"); hsb = ttk.Scrollbar(frame, orient="horizontal")
        tree = ttk.Treeview(frame, columns=colonnes, show="headings", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=tree.yview); hsb.config(command=tree.xview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y); hsb.pack(side=tk.BOTTOM, fill=tk.X); tree.pack(fill=tk.BOTH, expand=True)

        for c in colonnes:
            tree.heading(c, text=c)
        tree.column("Désignation", width=320, anchor=tk.W)
        num_w = max(90, int((w - 360) / (len(colonnes) - 1)))
        for c in colonnes[1:]:
            tree.column(c, width=num_w, anchor=tk.E)
        style = ttk.Style(top)
        style.configure("Treeview", font=("Courier", 10))
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))

        for i, (designation, vals) in enumerate(self.dernier_recap.items(), start=1):
            MA = "{:.6f}".format(vals.get("MA", 0.0))
            MD = "{:.6f}".format(vals.get("MD", 0.0))
            MB = "{:.6f}".format(vals.get("MB", 0.0))
            MC = "{:.6f}".format(vals.get("MC", 0.0))
            M_BC = "{:.6f}".format(vals.get("M_BC", 0.0))
            M_AD = "{:.6f}".format(vals.get("M_AD", 0.0))
            M_AB = "{:.6f}".format(vals.get("M_AB", 0.0))
            S1 = "{:.6f}".format(vals.get("S1", 0.0))
            S2 = "{:.6f}".format(vals.get("S2", 0.0))
            S2p = "{:.6f}".format(vals.get("S2_prime", vals.get("S2'", 0.0)))
            S3 = "{:.6f}".format(vals.get("S3", 0.0))
            lib = f"{i} - {designation}"
            tree.insert("", "end", values=[lib, MA, MD, MB, MC, M_BC, M_AD, M_AB, S1, S2, S2p, S3])

        top.update_idletasks()
        total_width = sum(tree.column(c, option="width") for c in colonnes)
        if total_width < w - 40:
            extra = (w - 40 - total_width) // (len(colonnes) - 1)
            for c in colonnes[1:]:
                tree.column(c, width=tree.column(c, option="width") + extra)

        def copier_selection(event=None):
            sel = tree.selection()
            if not sel: return
            rows = []
            for iid in sel:
                rows.append("\t".join(tree.item(iid, "values")))
            top.clipboard_clear(); top.clipboard_append("\n".join(rows))
        top.bind_all("<Control-c>", copier_selection)

    def exporter_csv(self):
        if not self.dernier_recap:
            messagebox.showinfo("Info", "Aucun résultat calculé. Cliquez sur 'Calculer' d'abord.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"recap_kleinlogel_t_units_{ts}.csv"
        filename = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=default_name,
                                                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filename:
            return
        try:
            headers = ["Designation", "MA_t.m/ml", "MD_t.m/ml", "MB_t.m/ml", "MC_t.m/ml", "M_BC_t.m/ml", "M_AD_t.m/ml", "M_AB_t.m/ml", "S1_t/ml", "S2_t/ml", "S2p_t/ml", "S3_t/ml"]
            with open(filename, mode='w', newline='', encoding='utf-8') as csvf:
                writer = csv.writer(csvf)
                writer.writerow(headers)
                for i, (designation, vals) in enumerate(self.dernier_recap.items(), start=1):
                    MA = vals.get("MA", 0.0)
                    MD = vals.get("MD", 0.0)
                    MB = vals.get("MB", 0.0)
                    MC = vals.get("MC", 0.0)
                    M_BC = vals.get("M_BC", 0.0)
                    M_AD = vals.get("M_AD", 0.0)
                    M_AB = vals.get("M_AB", 0.0)
                    S1 = vals.get("S1", 0.0)
                    S2 = vals.get("S2", 0.0)
                    S2p = vals.get("S2_prime", vals.get("S2'", 0.0))
                    S3 = vals.get("S3", 0.0)
                    lib = f"{i} - {designation}"
                    writer.writerow([lib, MA, MD, MB, MC, M_BC, M_AD, M_AB, S1, S2, S2p, S3])
            # Also export parameters as separate CSV (same folder, same timestamp)
            params_filename = filename.replace(".csv", f"_params_{ts}.csv")
            try:
                with open(params_filename, mode='w', newline='', encoding='utf-8') as pf:
                    pw = csv.writer(pf)
                    pw.writerow(["parametre", "valeur"])
                    params = self.dernier_resultats.get("params_kleinlogel", {})
                    for k, v in params.items():
                        pw.writerow([k, v])
                messagebox.showinfo("Export CSV", f"Récapitulatif exporté :\n{filename}\nParamètres exportés :\n{params_filename}")
            except Exception:
                messagebox.showinfo("Export CSV", f"Récapitulatif exporté :\n{filename}\n(échec export paramètres)")
        except Exception as e:
            messagebox.showerror("Erreur export CSV", str(e))

# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = InterfaceDalot(root)
    root.mainloop()