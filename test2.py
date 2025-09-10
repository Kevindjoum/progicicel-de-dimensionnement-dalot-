#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Progiciel de dimensionnement des dalots en béton armé
Intégration des algorithmes de calcul Kleinlogel
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, font, PhotoImage
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import math
import csv
import time
from datetime import datetime
import os
import sys
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import threading

# constantes de conversion
GN_PAR_T = 9810.0                     # 1 t ≈ 9810 N (utilisé uniquement pour conversion UI -> t)
KILO_NEWTON_EN_N = 1000.0             # 1 kN = 1000 N

# ----------------------------
# Classes de données pour Kleinlogel
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

class DonneesNormalisees:
    LARGEURS_STANDARD = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0]
    HAUTEURS_STANDARD = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    LONGUEURS_STANDARD = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]
    EPAISSEURS_DALLE = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80]
    EPAISSEURS_VOILE = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]
    
    CLASSES_BETON = {
        "C20/25": {"fc28": 20, "ft28": 1.6, "E": 30000, "description": "Béton ordinaire"},
        "C25/30": {"fc28": 25, "ft28": 1.8, "E": 31000, "description": "Béton courant"},
        "C30/37": {"fc28": 30, "ft28": 2.1, "E": 33000, "description": "Béton de résistance moyenne"},
        "C35/45": {"fc28": 35, "ft28": 2.2, "E": 34000, "description": "Béton de haute résistance"},
        "C40/50": {"fc28": 40, "ft28": 2.5, "E": 35000, "description": "Béton de très haute résistance"},
        "C45/55": {"fc28": 45, "ft28": 2.7, "E": 36000, "description": "Béton hautes performances"},
        "C50/60": {"fc28": 50, "ft28": 2.9, "E": 37000, "description": "Béton très hautes performances"}
    }
    
    CLASSES_ACIER = {
        "S400": {"fyk": 400, "Es": 200000, "description": "Acier doux"},
        "S500A": {"fyk": 500, "Es": 200000, "description": "Acier haute adhérence classe A"},
        "S500B": {"fyk": 500, "Es": 200000, "description": "Acier haute adhérence classe B"},
        "S500C": {"fyk": 500, "Es": 200000, "description": "Acier haute adhérence classe C"},
        "S600": {"fyk": 600, "Es": 200000, "description": "Acier haute résistance"}
    }
    
    DIAMETRES_PRINCIPAUX = [8, 10, 12, 14, 16, 20, 25, 32]
    DIAMETRES_SECONDAIRES = [6, 8, 10, 12, 14, 16]
    ESPACEMENTS_STANDARD = [100, 125, 150, 175, 200, 250, 300]
    
    ENROBAGES_STANDARD = {
        "XC1": 15,
        "XC2": 25,
        "XC3": 35,
        "XC4": 40,
        "XD1": 45,
        "XD2": 50,
        "XD3": 55,
        "XS1": 45,
        "XS2": 50,
        "XS3": 55
    }
    
    CLASSES_TRAFIC = {
        "T0": {"description": "Trafic très faible (< 25 PL/jour)", "coef": 1.0},
        "T1": {"description": "Trafic faible (25-50 PL/jour)", "coef": 1.1},
        "T2": {"description": "Trafic moyen (50-150 PL/jour)", "coef": 1.2},
        "T3": {"description": "Trafic fort (150-300 PL/jour)", "coef": 1.3},
        "T4": {"description": "Trafic très fort (300-750 PL/jour)", "coef": 1.4},
        "T5": {"description": "Trafic exceptionnel (> 750 PL/jour)", "coef": 1.5}
    }
    
    TYPES_REMBLAI = {
        "Sable": {"gamma": 18, "phi": 30, "c": 0, "description": "Sable propre"},
        "Gravier": {"gamma": 20, "phi": 35, "c": 0, "description": "Gravier propre"},
        "Limon": {"gamma": 17, "phi": 25, "c": 10000, "description": "Limon peu plastique"},
        "Argile": {"gamma": 19, "phi": 20, "c": 20000, "description": "Argile peu plastique"},
        "Tout-venant": {"gamma": 21, "phi": 33, "c": 5000, "description": "Matériau de remblai standard"}
    }
    
    HAUTEURS_REMBLAI = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]

class Infobulle:
    def __init__(self, widget, texte):
        self.widget = widget
        self.texte = texte
        self.bulle = None
        self.widget.bind("<Enter>", self._afficher)
        self.widget.bind("<Leave>", self._masquer)

    def _afficher(self, _event):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.bulle = tk.Toplevel(self.widget)
        self.bulle.wm_overrideredirect(True)
        self.bulle.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(self.bulle, text=self.texte, justify=tk.LEFT,
                           background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                           font=("Arial", "9", "normal"), wraplength=250)
        label.pack(padx=2, pady=2)

    def _masquer(self, _event):
        if self.bulle:
            self.bulle.destroy()
            self.bulle = None

class GestionnaireProjet:
    @staticmethod
    def sauvegarder_projet(app, chemin_fichier):
        try:
            donnees = {
                "geometrie": {
                    "Li_m": app.Li_m.get(),
                    "Hi_m": app.Hi_m.get(),
                    "e_dalle_m": app.e_dalle_m.get(),
                    "e_voile_m": app.e_voile_m.get(),
                    "e_radier_m": app.e_radier_m.get(),
                },
                "materiaux": {
                    "classe_beton": app.classe_beton.get(),
                    "classe_acier": app.classe_acier.get(),
                    "classe_exposition": app.classe_exposition.get(),
                },
                "charges": {
                    "hr_m": app.hr_m.get(),
                    "type_remblai": app.type_remblai.get(),
                    "classe_trafic": app.classe_trafic.get(),
                    "gamma_b_kN_m3": app.gamma_b_kN_m3.get(),
                    "gamma_sol_kN_m3": app.gamma_sol_kN_m3.get(),
                    "phi_deg": app.phi_deg.get(),
                    "c_pa": app.c_pa.get(),
                    "q_surcharge_kN_m2": app.q_surcharge_kN_m2.get(),
                    "bc": app.bc.get(),
                    "bt": app.bt.get(),
                }
            }
            with open(chemin_fichier, 'w') as f:
                import json
                json.dump(donnees, f, indent=4)
            app.fichier_courant = chemin_fichier
            app._mettre_a_jour_titre_fenetre()
            app._marquer_modifie(False)
            return True
        except Exception as e:
            messagebox.showerror("Erreur sauvegarde", f"Impossible de sauvegarder: {str(e)}")
            return False

    @staticmethod
    def charger_projet(app, chemin_fichier):
        try:
            with open(chemin_fichier, 'r') as f:
                import json
                donnees = json.load(f)
            
            # Charger géométrie
            app.Li_m.set(donnees["geometrie"]["Li_m"])
            app.Hi_m.set(donnees["geometrie"]["Hi_m"])
            app.e_dalle_m.set(donnees["geometrie"]["e_dalle_m"])
            app.e_voile_m.set(donnees["geometrie"]["e_voile_m"])
            app.e_radier_m.set(donnees["geometrie"]["e_radier_m"])
            
            # Charger matériaux
            app.classe_beton.set(donnees["materiaux"]["classe_beton"])
            app.classe_acier.set(donnees["materiaux"]["classe_acier"])
            app.classe_exposition.set(donnees["materiaux"]["classe_exposition"])
            
            # Charger charges
            app.hr_m.set(donnees["charges"]["hr_m"])
            app.type_remblai.set(donnees["charges"]["type_remblai"])
            app.classe_trafic.set(donnees["charges"]["classe_trafic"])
            app.gamma_b_kN_m3.set(donnees["charges"]["gamma_b_kN_m3"])
            app.gamma_sol_kN_m3.set(donnees["charges"]["gamma_sol_kN_m3"])
            app.phi_deg.set(donnees["charges"]["phi_deg"])
            app.c_pa.set(donnees["charges"]["c_pa"])
            app.q_surcharge_kN_m2.set(donnees["charges"]["q_surcharge_kN_m2"])
            app.bc.set(donnees["charges"]["bc"])
            app.bt.set(donnees["charges"]["bt"])
            
            app.fichier_courant = chemin_fichier
            app._mettre_a_jour_titre_fenetre()
            app._marquer_modifie(False)
            app._maj_info_beton()
            app._maj_info_acier()
            app._maj_info_exposition()
            app._maj_info_trafic()
            app._maj_info_remblai()
            app._dessiner_dalot_3d()
            return True
        except Exception as e:
            messagebox.showerror("Erreur chargement", f"Impossible de charger: {str(e)}")
            return False

class ExporteurPDF:
    @staticmethod
    def generer_rapport_pdf(app, chemin_fichier):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            
            # Générer d'abord une capture du modèle 3D
            temp_img = "temp_dalot_3d.png"
            app.figure_3d.savefig(temp_img, dpi=150, bbox_inches='tight')
            
            ExporteurPDF._generer_pdf_reportlab(app, chemin_fichier, temp_img)
            
            # Supprimer l'image temporaire
            if os.path.exists(temp_img):
                os.remove(temp_img)
                
            messagebox.showinfo("Export PDF", f"Rapport exporté avec succès dans:\n{chemin_fichier}")
            return True
        except ImportError:
            # Si ReportLab n'est pas disponible, générer un rapport HTML
            return ExporteurPDF._generer_rapport_html(app, chemin_fichier)
        except Exception as e:
            messagebox.showerror("Erreur PDF", f"Impossible de générer le PDF: {str(e)}")
            return False

    @staticmethod
    def _generer_pdf_reportlab(app, chemin_fichier, image_path):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        
        doc = SimpleDocTemplate(chemin_fichier, pagesize=A4)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', alignment=1, parent=styles['Heading1']))
        styles.add(ParagraphStyle(name='Justify', alignment=4, parent=styles['Normal']))
        
        elements = []
        
        # Titre
        elements.append(Paragraph("Rapport de dimensionnement de dalot", styles['Center']))
        elements.append(Spacer(1, 10 * mm))
        
        # Date et info projet
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        elements.append(Paragraph(f"Date: {date_str}", styles['Normal']))
        elements.append(Paragraph(f"Projet: {os.path.basename(app.fichier_courant if app.fichier_courant else 'Nouveau projet')}", styles['Normal']))
        elements.append(Spacer(1, 5 * mm))
        
        # Image du dalot
        try:
            img = Image(image_path)
            img.drawHeight = 80 * mm
            img.drawWidth = 120 * mm
            elements.append(img)
            elements.append(Spacer(1, 5 * mm))
        except:
            elements.append(Paragraph("Visualisation 3D non disponible", styles['Italic']))
            
        # Paramètres géométriques
        elements.append(Paragraph("Paramètres géométriques", styles['Heading2']))
        data = [
            ["Paramètre", "Valeur", "Unité"],
            ["Largeur intérieure", f"{app.Li_m.get():.2f}", "m"],
            ["Hauteur intérieure", f"{app.Hi_m.get():.2f}", "m"],
            ["Épaisseur dalle", f"{app.e_dalle_m.get():.2f}", "m"],
            ["Épaisseur voile", f"{app.e_voile_m.get():.2f}", "m"],
            ["Épaisseur radier", f"{app.e_radier_m.get():.2f}", "m"]
        ]
        t = Table(data, colWidths=[80 * mm, 40 * mm, 30 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 5 * mm))
        
        # Matériaux
        elements.append(Paragraph("Matériaux", styles['Heading2']))
        classe_beton = app.classe_beton.get()
        classe_acier = app.classe_acier.get()
        
        data = [
            ["Matériau", "Classe", "Caractéristiques"],
            ["Béton", classe_beton, f"fc28 = {DonneesNormalisees.CLASSES_BETON[classe_beton]['fc28']} MPa"],
            ["Acier", classe_acier, f"fyk = {DonneesNormalisees.CLASSES_ACIER[classe_acier]['fyk']} MPa"],
            ["Exposition", app.classe_exposition.get(), f"Enrobage = {DonneesNormalisees.ENROBAGES_STANDARD[app.classe_exposition.get()]} mm"]
        ]
        t = Table(data, colWidths=[50 * mm, 40 * mm, 60 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 5 * mm))
        
        # Charges
        elements.append(Paragraph("Charges et sollicitations", styles['Heading2']))
        elements.append(Paragraph("Paramètres de chargement:", styles['Normal']))
        
        data = [
            ["Paramètre", "Valeur", "Unité"],
            ["Hauteur de remblai", f"{app.hr_m.get():.2f}", "m"],
            ["Type de remblai", app.type_remblai.get(), ""],
            ["Classe de trafic", app.classe_trafic.get(), ""],
            ["Poids volumique du béton", f"{app.gamma_b_kN_m3.get():.1f}", "kN/m³"],
            ["Poids volumique du sol", f"{app.gamma_sol_kN_m3.get():.1f}", "kN/m³"],
            ["Angle de frottement (φ)", f"{app.phi_deg.get():.1f}", "°"],
            ["Cohésion", f"{app.c_pa.get():.1f}", "Pa"],
            ["Surcharge routière", f"{app.q_surcharge_kN_m2.get():.1f}", "kN/m²"],
            ["Coefficient Bc", f"{app.bc.get():.2f}", ""],
            ["Coefficient Bt", f"{app.bt.get():.2f}", ""]
        ]
        t = Table(data, colWidths=[80 * mm, 40 * mm, 30 * mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 5 * mm))
        
        # Détails des calculs
        elements.append(Paragraph("Détails des calculs", styles['Heading2']))
        
        # Vérifier si les résultats sont disponibles
        if hasattr(app, 'dernier_recap') and app.dernier_recap:
            elements.append(Paragraph("Paramètres Kleinlogel calculés:", styles['Normal']))
            
            params_k = app.dernier_resultats.get("params_kleinlogel", {})
            data = [
                ["Paramètre", "Valeur"],
                ["j1", f"{params_k.get('j1', 0):.6e}"],
                ["j2", f"{params_k.get('j2', 0):.6e}"],
                ["j3", f"{params_k.get('j3', 0):.6e}"],
                ["k1", f"{params_k.get('k1', 0):.6f}"],
                ["k2", f"{params_k.get('k2', 0):.6f}"],
                ["F1", f"{params_k.get('F1', 0):.6e}"],
                ["h_eff", f"{params_k.get('h_eff', 0):.6f} m"],
                ["l_eff", f"{params_k.get('l_eff', 0):.6f} m"]
            ]
            t = Table(data, colWidths=[70 * mm, 80 * mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 5 * mm))
            
            # Charges de convoi calculées
            elements.append(Paragraph("Charges de convoi calculées:", styles['Normal']))
            data = [
                ["Charge", "Valeur (t/m²)", "Valeur (t/m)"],
                ["Convoi Bc", f"{params_k.get('q_bc_t_m2', 0):.6f}", f"{params_k.get('q_bc_t_par_m', 0):.6f}"],
                ["Convoi Bt", f"{params_k.get('q_bt_t_m2', 0):.6f}", f"{params_k.get('q_bt_t_par_m', 0):.6f}"],
                ["Convoi Br", f"{params_k.get('q_br_t_m2', 0):.6f}", f"{params_k.get('q_br_t_par_m', 0):.6f}"],
                ["Max Convoi", f"{params_k.get('qmax_t_m2', 0):.6f}", "-"],
                ["Surcharge", f"{params_k.get('q_surcharge_t_m2', 0):.6f}", "-"]
            ]
            t = Table(data, colWidths=[50 * mm, 50 * mm, 50 * mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 5 * mm))
            
            # Récapitulatif des résultats
            elements.append(Paragraph("Récapitulatif des résultats:", styles['Normal']))
            
            # En-tête du tableau
            recap_data = [["Cas", "MA (t·m/ml)", "MB (t·m/ml)", "MC (t·m/ml)", "MD (t·m/ml)", 
                           "M_BC (t·m/ml)", "S1 (t/ml)", "S3 (t/ml)"]]
            
            # Ajouter chaque cas
            for designation, vals in app.dernier_recap.items():
                recap_data.append([
                    designation,
                    f"{vals.get('MA', 0):.4f}",
                    f"{vals.get('MB', 0):.4f}",
                    f"{vals.get('MC', 0):.4f}",
                    f"{vals.get('MD', 0):.4f}",
                    f"{vals.get('M_BC', 0):.4f}",
                    f"{vals.get('S1', 0):.4f}",
                    f"{vals.get('S3', 0):.4f}"
                ])
            
            # Mettre en évidence les résultats finaux (ELU, ELS)
            t = Table(recap_data, colWidths=[60*mm, 20*mm, 20*mm, 20*mm, 20*mm, 20*mm, 20*mm, 20*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                # Mettre en évidence les résultats importants
                ('BACKGROUND', (0, -2), (-1, -1), colors.lightyellow),
                ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(t)
            
        else:
            elements.append(Paragraph("Aucun résultat de calcul disponible. Veuillez lancer le calcul depuis l'application.", styles['Italic']))
        
        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph("Note: Ce rapport a été généré automatiquement par le logiciel de dimensionnement de dalots.", styles['Italic']))
        
        # Générer le PDF
        doc.build(elements)
        return True

    @staticmethod
    def _generer_rapport_html(app, chemin_fichier):
        """Génère un rapport au format HTML si ReportLab n'est pas disponible"""
        try:
            # Changer l'extension en .html
            chemin_html = os.path.splitext(chemin_fichier)[0] + ".html"
            
            with open(chemin_html, 'w', encoding='utf-8') as f:
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Rapport de dimensionnement de dalot</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ color: #003366; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .highlight {{ background-color: #ffffdd; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Rapport de dimensionnement de dalot</h1>
    <p>Date: {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
    <p>Projet: {os.path.basename(app.fichier_courant if app.fichier_courant else 'Nouveau projet')}</p>
    
    <h2>Paramètres géométriques</h2>
    <table>
        <tr><th>Paramètre</th><th>Valeur</th><th>Unité</th></tr>
        <tr><td>Largeur intérieure</td><td>{app.Li_m.get():.2f}</td><td>m</td></tr>
        <tr><td>Hauteur intérieure</td><td>{app.Hi_m.get():.2f}</td><td>m</td></tr>
        <tr><td>Épaisseur dalle</td><td>{app.e_dalle_m.get():.2f}</td><td>m</td></tr>
        <tr><td>Épaisseur voile</td><td>{app.e_voile_m.get():.2f}</td><td>m</td></tr>
        <tr><td>Épaisseur radier</td><td>{app.e_radier_m.get():.2f}</td><td>m</td></tr>
    </table>
    
    <h2>Matériaux</h2>
    <table>
        <tr><th>Matériau</th><th>Classe</th><th>Caractéristiques</th></tr>
        <tr><td>Béton</td><td>{app.classe_beton.get()}</td><td>fc28 = {DonneesNormalisees.CLASSES_BETON[app.classe_beton.get()]['fc28']} MPa</td></tr>
        <tr><td>Acier</td><td>{app.classe_acier.get()}</td><td>fyk = {DonneesNormalisees.CLASSES_ACIER[app.classe_acier.get()]['fyk']} MPa</td></tr>
        <tr><td>Exposition</td><td>{app.classe_exposition.get()}</td><td>Enrobage = {DonneesNormalisees.ENROBAGES_STANDARD[app.classe_exposition.get()]} mm</td></tr>
    </table>
    
    <h2>Charges et sollicitations</h2>
    <table>
        <tr><th>Paramètre</th><th>Valeur</th><th>Unité</th></tr>
        <tr><td>Hauteur de remblai</td><td>{app.hr_m.get():.2f}</td><td>m</td></tr>
        <tr><td>Type de remblai</td><td>{app.type_remblai.get()}</td><td></td></tr>
        <tr><td>Classe de trafic</td><td>{app.classe_trafic.get()}</td><td></td></tr>
        <tr><td>Poids volumique du béton</td><td>{app.gamma_b_kN_m3.get():.1f}</td><td>kN/m³</td></tr>
        <tr><td>Poids volumique du sol</td><td>{app.gamma_sol_kN_m3.get():.1f}</td><td>kN/m³</td></tr>
        <tr><td>Angle de frottement (φ)</td><td>{app.phi_deg.get():.1f}</td><td>°</td></tr>
        <tr><td>Cohésion</td><td>{app.c_pa.get():.1f}</td><td>Pa</td></tr>
        <tr><td>Surcharge routière</td><td>{app.q_surcharge_kN_m2.get():.1f}</td><td>kN/m²</td></tr>
        <tr><td>Coefficient Bc</td><td>{app.bc.get():.2f}</td><td></td></tr>
        <tr><td>Coefficient Bt</td><td>{app.bt.get():.2f}</td><td></td></tr>
    </table>
""")

                # Ajouter les résultats s'ils sont disponibles
                if hasattr(app, 'dernier_recap') and app.dernier_recap:
                    f.write("""
    <h2>Détails des calculs</h2>
    <h3>Paramètres Kleinlogel calculés</h3>
    <table>
        <tr><th>Paramètre</th><th>Valeur</th></tr>
""")
                    params_k = app.dernier_resultats.get("params_kleinlogel", {})
                    for param in ['j1', 'j2', 'j3', 'k1', 'k2', 'F1', 'h_eff', 'l_eff']:
                        value = params_k.get(param, 0)
                        format_str = "{:.6e}" if param in ['j1', 'j2', 'j3', 'F1'] else "{:.6f}"
                        unit = " m" if param in ['h_eff', 'l_eff'] else ""
                        f.write(f"        <tr><td>{param}</td><td>{format_str.format(value)}{unit}</td></tr>\n")
                    
                    f.write("""
    </table>
    
    <h3>Charges de convoi calculées</h3>
    <table>
        <tr><th>Charge</th><th>Valeur (t/m²)</th><th>Valeur (t/m)</th></tr>
""")
                    for charge, label in [('q_bc_t_m2', 'Convoi Bc'), ('q_bt_t_m2', 'Convoi Bt'), 
                                          ('q_br_t_m2', 'Convoi Br'), ('qmax_t_m2', 'Max Convoi'),
                                          ('q_surcharge_t_m2', 'Surcharge')]:
                        val_m2 = params_k.get(charge, 0)
                        val_m = params_k.get(charge.replace('_m2', '_par_m'), '-')
                        val_m = f"{val_m:.6f}" if isinstance(val_m, (float, int)) else "-"
                        f.write(f"        <tr><td>{label}</td><td>{val_m2:.6f}</td><td>{val_m}</td></tr>\n")
                        
                    f.write("""
    </table>
    
    <h3>Récapitulatif des résultats</h3>
    <table>
        <tr><th>Cas</th><th>MA (t·m/ml)</th><th>MB (t·m/ml)</th><th>MC (t·m/ml)</th><th>MD (t·m/ml)</th>
            <th>M_BC (t·m/ml)</th><th>S1 (t/ml)</th><th>S3 (t/ml)</th></tr>
""")
                    for i, (designation, vals) in enumerate(app.dernier_recap.items()):
                        highlight = " class='highlight'" if designation in ["combinaison ELU (1.35G+1.5Q)", "combinaison ELS (G+Q)"] else ""
                        f.write(f"        <tr{highlight}><td>{designation}</td>"
                                f"<td>{vals.get('MA', 0):.4f}</td>"
                                f"<td>{vals.get('MB', 0):.4f}</td>"
                                f"<td>{vals.get('MC', 0):.4f}</td>"
                                f"<td>{vals.get('MD', 0):.4f}</td>"
                                f"<td>{vals.get('M_BC', 0):.4f}</td>"
                                f"<td>{vals.get('S1', 0):.4f}</td>"
                                f"<td>{vals.get('S3', 0):.4f}</td></tr>\n")
                        
                    f.write("    </table>\n")
                else:
                    f.write("<p><i>Aucun résultat de calcul disponible. Veuillez lancer le calcul depuis l'application.</i></p>\n")
                
                f.write("""
    <hr>
    <p><i>Note: Ce rapport a été généré automatiquement par le logiciel de dimensionnement de dalots.</i></p>
</body>
</html>
""")
            
            messagebox.showinfo("Export HTML", f"Rapport exporté avec succès dans:\n{chemin_html}")
            return True
        except Exception as e:
            messagebox.showerror("Erreur HTML", f"Impossible de générer le rapport HTML: {str(e)}")
            return False

class ApplicationDalotComplete(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Progiciel de dimensionnement des dalots en béton armé")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        
        # Initialiser les variables
        self._definir_variables()
        
        # Créer l'interface
        self._creer_interface()
        
        # Variables de contrôle
        self.fichier_courant = None
        self.modifie = False
        self._mettre_a_jour_titre_fenetre()
        
        # Résultats des calculs
        self.dernier_resultats = {}
        self.dernier_recap = {}
        
        # Dessiner le dalot initial
        self._dessiner_dalot_3d()
        
        # Configuration du comportement à la fermeture
        self.protocol("WM_DELETE_WINDOW", self._avant_quitter)

    def _definir_variables(self):
        # Géométrie
        self.Li_m = tk.DoubleVar(value=3.0)
        self.Hi_m = tk.DoubleVar(value=2.5)
        self.e_dalle_m = tk.DoubleVar(value=0.20)
        self.e_voile_m = tk.DoubleVar(value=0.20)
        self.e_radier_m = tk.DoubleVar(value=0.20)
        
        # Matériaux
        self.classe_beton = tk.StringVar(value="C25/30")
        self.classe_acier = tk.StringVar(value="S500B")
        self.classe_exposition = tk.StringVar(value="XC2")
        
        # Charges et sol (variables de Kleinlogel intégrées)
        self.hr_m = tk.DoubleVar(value=1.0)
        self.type_remblai = tk.StringVar(value="Tout-venant")
        self.classe_trafic = tk.StringVar(value="T2")
        self.gamma_b_kN_m3 = tk.DoubleVar(value=25.0)
        self.gamma_sol_kN_m3 = tk.DoubleVar(value=18.0)
        self.phi_deg = tk.DoubleVar(value=30.0)
        self.c_pa = tk.DoubleVar(value=5000.0)
        self.q_surcharge_kN_m2 = tk.DoubleVar(value=10.0)
        self.bc = tk.DoubleVar(value=1.1)
        self.bt = tk.DoubleVar(value=1.0)
        
        # Informations sur les matériaux
        self.info_beton = tk.StringVar()
        self.info_acier = tk.StringVar()
        self.info_exposition = tk.StringVar()
        self.info_trafic = tk.StringVar()
        self.info_remblai = tk.StringVar()
        
        # Journal
        self.texte_journal = tk.StringVar(value="Prêt")
        self.progression = tk.IntVar(value=0)

    def _creer_interface(self):
        # Créer la barre de menus
        self._creer_menus()
        
        # Configurer les raccourcis
        self._configurer_raccourcis()
        
        # Barre d'outils avancée
        self._creer_barre_outils_avancee()
        
        # Interface principale
        self._creer_interface_principale()
        
        # Barre de statut
        self._creer_barre_statut_avancee()

    def _creer_menus(self):
        menu_bar = tk.Menu(self)
        
        # Menu Fichier
        menu_fichier = tk.Menu(menu_bar, tearoff=0)
        menu_fichier.add_command(label="Nouveau", command=self.action_nouveau, accelerator="Ctrl+N")
        menu_fichier.add_command(label="Ouvrir...", command=self.action_ouvrir, accelerator="Ctrl+O")
        menu_fichier.add_command(label="Enregistrer", command=self.action_enregistrer, accelerator="Ctrl+S")
        menu_fichier.add_command(label="Enregistrer sous...", command=self.action_enregistrer_sous)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Exporter PDF", command=self.cmd_exporter_pdf)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Quitter", command=self._avant_quitter)
        menu_bar.add_cascade(label="Fichier", menu=menu_fichier)
        
        # Menu Calcul
        menu_calcul = tk.Menu(menu_bar, tearoff=0)
        menu_calcul.add_command(label="Vérifier les entrées", command=self.cmd_verifier_entrees)
        menu_calcul.add_command(label="Lancer les calculs", command=self.cmd_lancer_calculs, accelerator="F5")
        menu_calcul.add_separator()
        menu_calcul.add_command(label="Générer rapport complet", command=self.cmd_generer_rapport)
        menu_bar.add_cascade(label="Calcul", menu=menu_calcul)
        
        # Menu Vue
        menu_vue = tk.Menu(menu_bar, tearoff=0)
        menu_vue.add_command(label="Vue isométrique", command=self.cmd_vue_isometrique)
        menu_vue.add_command(label="Vue de face", command=self.cmd_vue_face)
        menu_vue.add_command(label="Vue de côté", command=self.cmd_vue_cote)
        menu_vue.add_command(label="Vue de dessus", command=self.cmd_vue_dessus)
        menu_vue.add_separator()
        menu_vue.add_command(label="Réinitialiser la vue", command=self.cmd_reset_vue)
        menu_vue.add_command(label="Zoom adapté", command=self.cmd_zoom_adapte)
        menu_vue.add_separator()
        menu_vue.add_command(label="Capturer la vue 3D", command=self.cmd_capture_3d)
        menu_vue.add_command(label="Animation 3D", command=self.cmd_animation_3d)
        menu_bar.add_cascade(label="Vue", menu=menu_vue)
        
        # Menu Aide
        menu_aide = tk.Menu(menu_bar, tearoff=0)
        menu_aide.add_command(label="Manuel utilisateur", command=self.cmd_manuel)
        menu_aide.add_command(label="Tutoriels", command=self.cmd_tutoriels)
        menu_aide.add_separator()
        menu_aide.add_command(label="À propos", command=self.cmd_a_propos)
        menu_bar.add_cascade(label="Aide", menu=menu_aide)
        
        self.config(menu=menu_bar)

    def _configurer_raccourcis(self):
        """Configure les raccourcis clavier"""
        self.bind_all("<Control-n>", lambda e: self.action_nouveau())
        self.bind_all("<Control-o>", lambda e: self.action_ouvrir())
        self.bind_all("<Control-s>", lambda e: self.action_enregistrer())
        self.bind_all("<F5>", lambda e: self.cmd_lancer_calculs())
        self.bind_all("<Escape>", lambda e: self.cmd_reset_vue())

    def _creer_barre_outils_avancee(self):
        """Crée la barre d'outils principale"""
        cadre_principal = ttk.Frame(self, relief="raised", borderwidth=1)
        cadre_principal.pack(side="top", fill="x")

        # Ligne 1 : Fichier et calculs
        ligne1 = ttk.Frame(cadre_principal)
        ligne1.pack(fill="x", pady=2)

        grp_fichier = ttk.LabelFrame(ligne1, text="📁 Fichier")
        grp_fichier.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_fichier, text="Nouveau", command=self.action_nouveau, width=8).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_fichier, text="Ouvrir", command=self.action_ouvrir, width=8).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_fichier, text="Enregistrer", command=self.action_enregistrer, width=10).pack(side="left", padx=2, pady=2)

        grp_calcul = ttk.LabelFrame(ligne1, text="🔧 Calculs")
        grp_calcul.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_calcul, text="Vérifier", command=self.cmd_verifier_entrees, width=8).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_calcul, text="Calculer", command=self.cmd_lancer_calculs, width=8).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_calcul, text="Rapport", command=self.cmd_generer_rapport, width=8).pack(side="left", padx=2, pady=2)

        grp_3d = ttk.LabelFrame(ligne1, text="🎯 3D")
        grp_3d.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_3d, text="Actualiser", command=self._dessiner_dalot_3d, width=9).pack(side="left", padx=2, pady=2)
        
        # Barre de progression
        self.barre_progression = ttk.Progressbar(ligne1, mode="determinate", length=250, variable=self.progression)
        self.barre_progression.pack(side="right", padx=10, pady=5)
        
        self.label_progression = ttk.Label(ligne1, textvariable=self.texte_journal)
        self.label_progression.pack(side="right", padx=5, pady=5)

    def _creer_interface_principale(self):
        """Crée l'interface principale avec les onglets"""
        self.paned_principal = ttk.PanedWindow(self, orient="horizontal")
        self.paned_principal.pack(fill="both", expand=True, padx=5, pady=5)

        # Panneau gauche (paramètres)
        self.panneau_gauche = ttk.Frame(self.paned_principal, width=500)
        self.paned_principal.add(self.panneau_gauche, weight=30)

        self.notebook_gauche = ttk.Notebook(self.panneau_gauche)
        self.notebook_gauche.pack(fill="both", expand=True)

        self._creer_onglet_parametres()
        self._creer_onglet_resultats()

        # Panneau droit (visualisation 3D)
        self.panneau_droit = ttk.Frame(self.paned_principal, width=700)
        self.paned_principal.add(self.panneau_droit, weight=70)

        self._creer_visualisation_3d_avancee()

    def _creer_onglet_parametres(self):
        """Crée l'onglet des paramètres avec sous-onglets"""
        cadre_parametres = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_parametres, text="📋 Paramètres")

        self.notebook_parametres = ttk.Notebook(cadre_parametres)
        self.notebook_parametres.pack(fill="both", expand=True, padx=5, pady=5)

        self._creer_onglet_geometrie()
        self._creer_onglet_materiaux()
        self._creer_onglet_charges()

    def _creer_onglet_geometrie(self):
        """Crée l'onglet de géométrie"""
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="📐 Géométrie")

        ttk.Label(cadre, text="Dimensions intérieures du dalot", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, pady=5, sticky="w")
        
        # Largeur intérieure
        ttk.Label(cadre, text="Largeur intérieure (Li):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        combo_largeur = ttk.Combobox(cadre, textvariable=self.Li_m, values=DonneesNormalisees.LARGEURS_STANDARD, width=10)
        combo_largeur.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="m").grid(row=1, column=2, sticky="w", padx=2, pady=5)
        Infobulle(combo_largeur, "Largeur intérieure du dalot")
        combo_largeur.bind("<<ComboboxSelected>>", lambda e: self._marquer_modifie())
        combo_largeur.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        # Hauteur intérieure
        ttk.Label(cadre, text="Hauteur intérieure (Hi):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        combo_hauteur = ttk.Combobox(cadre, textvariable=self.Hi_m, values=DonneesNormalisees.HAUTEURS_STANDARD, width=10)
        combo_hauteur.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="m").grid(row=2, column=2, sticky="w", padx=2, pady=5)
        Infobulle(combo_hauteur, "Hauteur intérieure du dalot")
        combo_hauteur.bind("<<ComboboxSelected>>", lambda e: self._marquer_modifie())
        combo_hauteur.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, text="Épaisseurs des éléments", font=("Arial", 10, "bold")).grid(row=3, column=0, columnspan=3, pady=5, sticky="w")
        
        # Épaisseur dalle
        ttk.Label(cadre, text="Épaisseur dalle:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        combo_dalle = ttk.Combobox(cadre, textvariable=self.e_dalle_m, values=DonneesNormalisees.EPAISSEURS_DALLE, width=10)
        combo_dalle.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="m").grid(row=4, column=2, sticky="w", padx=2, pady=5)
        Infobulle(combo_dalle, "Épaisseur de la dalle supérieure")
        combo_dalle.bind("<<ComboboxSelected>>", lambda e: self._marquer_modifie())
        combo_dalle.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        # Épaisseur voile
        ttk.Label(cadre, text="Épaisseur voile:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        combo_voile = ttk.Combobox(cadre, textvariable=self.e_voile_m, values=DonneesNormalisees.EPAISSEURS_VOILE, width=10)
        combo_voile.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="m").grid(row=5, column=2, sticky="w", padx=2, pady=5)
        Infobulle(combo_voile, "Épaisseur des voiles (murs) latéraux")
        combo_voile.bind("<<ComboboxSelected>>", lambda e: self._marquer_modifie())
        combo_voile.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        # Épaisseur radier
        ttk.Label(cadre, text="Épaisseur radier:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
        combo_radier = ttk.Combobox(cadre, textvariable=self.e_radier_m, values=DonneesNormalisees.EPAISSEURS_DALLE, width=10)
        combo_radier.grid(row=6, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="m").grid(row=6, column=2, sticky="w", padx=2, pady=5)
        Infobulle(combo_radier, "Épaisseur du radier (dalle inférieure)")
        combo_radier.bind("<<ComboboxSelected>>", lambda e: self._marquer_modifie())
        combo_radier.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        # Bouton pour mettre à jour la visualisation 3D
        ttk.Button(cadre, text="Actualiser visualisation 3D", command=self._dessiner_dalot_3d).grid(row=7, column=0, columnspan=3, pady=10)

    def _creer_onglet_materiaux(self):
        """Crée l'onglet des matériaux"""
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="🧱 Matériaux")

        # Béton
        ttk.Label(cadre, text="Béton", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=2, pady=5, sticky="w")
        
        ttk.Label(cadre, text="Classe de béton:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        combo_beton = ttk.Combobox(cadre, textvariable=self.classe_beton, values=list(DonneesNormalisees.CLASSES_BETON.keys()), width=15, state="readonly")
        combo_beton.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        Infobulle(combo_beton, "Classe de résistance du béton")
        combo_beton.bind("<<ComboboxSelected>>", self._maj_info_beton)
        
        ttk.Label(cadre, text="Poids volumique:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        entry_gamma = ttk.Entry(cadre, textvariable=self.gamma_b_kN_m3, width=15)
        entry_gamma.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="kN/m³").grid(row=2, column=2, sticky="w", padx=2, pady=5)
        Infobulle(entry_gamma, "Poids volumique du béton")
        entry_gamma.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, textvariable=self.info_beton, foreground="blue").grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        
        # Acier
        ttk.Label(cadre, text="Acier", font=("Arial", 10, "bold")).grid(row=4, column=0, columnspan=2, pady=5, sticky="w")
        
        ttk.Label(cadre, text="Classe d'acier:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        combo_acier = ttk.Combobox(cadre, textvariable=self.classe_acier, values=list(DonneesNormalisees.CLASSES_ACIER.keys()), width=15, state="readonly")
        combo_acier.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        Infobulle(combo_acier, "Classe de résistance de l'acier")
        combo_acier.bind("<<ComboboxSelected>>", self._maj_info_acier)
        
        ttk.Label(cadre, textvariable=self.info_acier, foreground="blue").grid(row=6, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        
        # Exposition
        ttk.Label(cadre, text="Exposition", font=("Arial", 10, "bold")).grid(row=7, column=0, columnspan=2, pady=5, sticky="w")
        
        ttk.Label(cadre, text="Classe d'exposition:").grid(row=8, column=0, sticky="e", padx=5, pady=5)
        combo_expo = ttk.Combobox(cadre, textvariable=self.classe_exposition, values=list(DonneesNormalisees.ENROBAGES_STANDARD.keys()), width=15, state="readonly")
        combo_expo.grid(row=8, column=1, sticky="w", padx=5, pady=5)
        Infobulle(combo_expo, "Classe d'exposition du béton selon EC2")
        combo_expo.bind("<<ComboboxSelected>>", self._maj_info_exposition)
        
        ttk.Label(cadre, textvariable=self.info_exposition, foreground="blue").grid(row=9, column=0, columnspan=3, sticky="w", padx=5, pady=2)

    def _creer_onglet_charges(self):
        """Crée l'onglet des charges (intègre les paramètres Kleinlogel)"""
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="⚖️ Charges")

        # Remblai
        ttk.Label(cadre, text="Remblai", font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, pady=5, sticky="w")
        
        ttk.Label(cadre, text="Hauteur de remblai:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        combo_hr = ttk.Combobox(cadre, textvariable=self.hr_m, values=DonneesNormalisees.HAUTEURS_REMBLAI, width=10)
        combo_hr.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="m").grid(row=1, column=2, sticky="w", padx=2, pady=5)
        Infobulle(combo_hr, "Hauteur du remblai au-dessus du dalot")
        combo_hr.bind("<<ComboboxSelected>>", lambda e: self._marquer_modifie())
        combo_hr.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, text="Type de remblai:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        combo_type = ttk.Combobox(cadre, textvariable=self.type_remblai, values=list(DonneesNormalisees.TYPES_REMBLAI.keys()), width=15, state="readonly")
        combo_type.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        Infobulle(combo_type, "Type de sol utilisé pour le remblai")
        combo_type.bind("<<ComboboxSelected>>", self._maj_info_remblai)
        
        ttk.Label(cadre, text="Poids volumique:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        entry_gamma_sol = ttk.Entry(cadre, textvariable=self.gamma_sol_kN_m3, width=10)
        entry_gamma_sol.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="kN/m³").grid(row=3, column=2, sticky="w", padx=2, pady=5)
        Infobulle(entry_gamma_sol, "Poids volumique du sol de remblai")
        entry_gamma_sol.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, text="Angle de frottement:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        entry_phi = ttk.Entry(cadre, textvariable=self.phi_deg, width=10)
        entry_phi.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="°").grid(row=4, column=2, sticky="w", padx=2, pady=5)
        Infobulle(entry_phi, "Angle de frottement interne du sol")
        entry_phi.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, text="Cohésion:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        entry_c = ttk.Entry(cadre, textvariable=self.c_pa, width=10)
        entry_c.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="Pa").grid(row=5, column=2, sticky="w", padx=2, pady=5)
        Infobulle(entry_c, "Cohésion du sol (en Pascals)")
        entry_c.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, textvariable=self.info_remblai, foreground="blue").grid(row=6, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        
        # Trafic
        ttk.Label(cadre, text="Trafic", font=("Arial", 10, "bold")).grid(row=7, column=0, columnspan=3, pady=5, sticky="w")
        
        ttk.Label(cadre, text="Classe de trafic:").grid(row=8, column=0, sticky="e", padx=5, pady=5)
        combo_trafic = ttk.Combobox(cadre, textvariable=self.classe_trafic, values=list(DonneesNormalisees.CLASSES_TRAFIC.keys()), width=15, state="readonly")
        combo_trafic.grid(row=8, column=1, sticky="w", padx=5, pady=5)
        Infobulle(combo_trafic, "Classe de trafic routier")
        combo_trafic.bind("<<ComboboxSelected>>", self._maj_info_trafic)
        
        ttk.Label(cadre, text="Surcharge routière:").grid(row=9, column=0, sticky="e", padx=5, pady=5)
        entry_q = ttk.Entry(cadre, textvariable=self.q_surcharge_kN_m2, width=10)
        entry_q.grid(row=9, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(cadre, text="kN/m²").grid(row=9, column=2, sticky="w", padx=2, pady=5)
        Infobulle(entry_q, "Surcharge routière uniforme")
        entry_q.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, textvariable=self.info_trafic, foreground="blue").grid(row=10, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        
        # Coefficients convois (paramètres spécifiques de Kleinlogel)
        ttk.Label(cadre, text="Coefficients des convois", font=("Arial", 10, "bold")).grid(row=11, column=0, columnspan=3, pady=5, sticky="w")
        
        ttk.Label(cadre, text="Coefficient Bc:").grid(row=12, column=0, sticky="e", padx=5, pady=5)
        entry_bc = ttk.Entry(cadre, textvariable=self.bc, width=10)
        entry_bc.grid(row=12, column=1, sticky="w", padx=5, pady=5)
        Infobulle(entry_bc, "Coefficient pour le convoi Bc (par défaut 1.1)")
        entry_bc.bind("<KeyRelease>", lambda e: self._marquer_modifie())
        
        ttk.Label(cadre, text="Coefficient Bt:").grid(row=13, column=0, sticky="e", padx=5, pady=5)
        entry_bt = ttk.Entry(cadre, textvariable=self.bt, width=10)
        entry_bt.grid(row=13, column=1, sticky="w", padx=5, pady=5)
        Infobulle(entry_bt, "Coefficient pour le convoi Bt (par défaut 1.0)")
        entry_bt.bind("<KeyRelease>", lambda e: self._marquer_modifie())

    def _creer_onglet_resultats(self):
        """Crée l'onglet des résultats"""
        cadre_resultats = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_resultats, text="📊 Résultats")

        notebook_resultats = ttk.Notebook(cadre_resultats)
        notebook_resultats.pack(fill="both", expand=True, padx=5, pady=5)

        # Rapport
        cadre_rapport = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_rapport, text="📋 Rapport")
        
        # Zone de texte avec défilement pour les résultats
        self.texte_resultats = tk.Text(cadre_rapport, wrap="word", height=20, font=("Courier", 10))
        scrollbar = ttk.Scrollbar(cadre_rapport, orient="vertical", command=self.texte_resultats.yview)
        self.texte_resultats.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.texte_resultats.pack(side="left", fill="both", expand=True)
        
        # Boutons sous la zone de texte
        frame_boutons = ttk.Frame(cadre_resultats)
        frame_boutons.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(frame_boutons, text="Copier résultats", command=self._copier_resultats).pack(side="left", padx=5)
        ttk.Button(frame_boutons, text="Exporter PDF", command=self.cmd_exporter_pdf).pack(side="left", padx=5)
        ttk.Button(frame_boutons, text="Effacer", command=lambda: self.texte_resultats.delete("1.0", tk.END)).pack(side="left", padx=5)

    def _creer_visualisation_3d_avancee(self):
        """Crée la zone de visualisation 3D avancée"""
        cadre_3d = ttk.LabelFrame(self.panneau_droit, text="🎯 Visualisation 3D")
        cadre_3d.pack(fill="both", expand=True, padx=5, pady=5)

        # Contrôles en haut
        cadre_controles = ttk.Frame(cadre_3d)
        cadre_controles.pack(fill="x", padx=5, pady=5)

        ttk.Button(cadre_controles, text="Vue isométrique", command=self.cmd_vue_isometrique).pack(side="left", padx=2)
        ttk.Button(cadre_controles, text="Vue de face", command=self.cmd_vue_face).pack(side="left", padx=2)
        ttk.Button(cadre_controles, text="Vue de côté", command=self.cmd_vue_cote).pack(side="left", padx=2)
        ttk.Button(cadre_controles, text="Vue de dessus", command=self.cmd_vue_dessus).pack(side="left", padx=2)
        ttk.Button(cadre_controles, text="Reset vue", command=self.cmd_reset_vue).pack(side="left", padx=2)

        # Figure matplotlib 3D
        self.figure_3d = Figure(figsize=(8, 6), facecolor='white')
        self.ax_3d = self.figure_3d.add_subplot(111, projection='3d')
        
        self.canvas_3d = FigureCanvasTkAgg(self.figure_3d, master=cadre_3d)
        self.canvas_3d.get_tk_widget().pack(fill="both", expand=True)
        
        # Toolbar minimale
        frame_toolbar = ttk.Frame(cadre_3d)
        frame_toolbar.pack(side="bottom", fill="x")
        
        ttk.Button(frame_toolbar, text="Capture 3D", command=self.cmd_capture_3d, width=10).pack(side="left", padx=2)
        ttk.Button(frame_toolbar, text="Animation 3D", command=self.cmd_animation_3d, width=10).pack(side="left", padx=2)
        
        # Variables pour la navigation
        self.mouse_pressed = False
        self.last_mouse_pos = None
        
        # Événements pour rotation et zoom
        self.canvas_3d.mpl_connect("scroll_event", self._on_scroll_zoom)
        self.canvas_3d.mpl_connect("button_press_event", self._on_click_3d)
        self.canvas_3d.mpl_connect("button_release_event", self._on_release_3d)
        self.canvas_3d.mpl_connect("motion_notify_event", self._on_motion_3d)

    def _creer_barre_statut_avancee(self):
        """Crée la barre de statut en bas de l'application"""
        cadre_statut = ttk.Frame(self, relief="sunken", borderwidth=1)
        cadre_statut.pack(side="bottom", fill="x")
        
        self.libelle_statut = ttk.Label(cadre_statut, text="Prêt pour le dimensionnement")
        self.libelle_statut.pack(side="left", padx=5, pady=3)

        # Indicateur de modification
        self.indicateur_modifie = ttk.Label(cadre_statut, text="", foreground="red", font=("Arial", 9, "bold"))
        self.indicateur_modifie.pack(side="right", padx=5, pady=3)
        
        # Informations géométriques
        self.info_geom = ttk.Label(cadre_statut, text="")
        self.info_geom.pack(side="right", padx=10, pady=3)
        
        self._maj_info_statut()

    # Méthodes de mise à jour des informations
    def _maj_info_beton(self, event=None):
        """Met à jour les informations sur le béton sélectionné"""
        classe = self.classe_beton.get()
        if classe in DonneesNormalisees.CLASSES_BETON:
            info = DonneesNormalisees.CLASSES_BETON[classe]
            self.info_beton.set(f"fc28 = {info['fc28']} MPa, ft28 = {info['ft28']} MPa - {info['description']}")
        else:
            self.info_beton.set("")
        self._marquer_modifie()

    def _maj_info_acier(self, event=None):
        """Met à jour les informations sur l'acier sélectionné"""
        classe = self.classe_acier.get()
        if classe in DonneesNormalisees.CLASSES_ACIER:
            info = DonneesNormalisees.CLASSES_ACIER[classe]
            self.info_acier.set(f"fyk = {info['fyk']} MPa, Es = {info['Es']/1000} GPa - {info['description']}")
        else:
            self.info_acier.set("")
        self._marquer_modifie()

    def _maj_info_exposition(self, event=None):
        """Met à jour les informations sur la classe d'exposition"""
        classe = self.classe_exposition.get()
        if classe in DonneesNormalisees.ENROBAGES_STANDARD:
            enrobage = DonneesNormalisees.ENROBAGES_STANDARD[classe]
            self.info_exposition.set(f"Enrobage minimum = {enrobage} mm")
        else:
            self.info_exposition.set("")
        self._marquer_modifie()

    def _maj_info_trafic(self, event=None):
        """Met à jour les informations sur la classe de trafic"""
        classe = self.classe_trafic.get()
        if classe in DonneesNormalisees.CLASSES_TRAFIC:
            info = DonneesNormalisees.CLASSES_TRAFIC[classe]
            self.info_trafic.set(f"{info['description']} - Coefficient: {info['coef']}")
        else:
            self.info_trafic.set("")
        self._marquer_modifie()

    def _maj_info_remblai(self, event=None):
        """Met à jour les informations sur le type de remblai"""
        type_remblai = self.type_remblai.get()
        if type_remblai in DonneesNormalisees.TYPES_REMBLAI:
            info = DonneesNormalisees.TYPES_REMBLAI[type_remblai]
            # Mettre à jour les valeurs par défaut
            self.gamma_sol_kN_m3.set(info['gamma'])
            self.phi_deg.set(info['phi'])
            self.c_pa.set(info['c'])
            self.info_remblai.set(f"γ = {info['gamma']} kN/m³, φ = {info['phi']}°, c = {info['c']} Pa - {info['description']}")
        else:
            self.info_remblai.set("")
        self._marquer_modifie()

    def _maj_info_statut(self):
        """Met à jour les informations de la barre de statut"""
        try:
            Li = self.Li_m.get()
            Hi = self.Hi_m.get()
            e_dalle = self.e_dalle_m.get()
            e_voile = self.e_voile_m.get()
            e_radier = self.e_radier_m.get()
            
            # Calcul des dimensions extérieures
            Le = Li + 2 * e_voile
            He = Hi + e_dalle + e_radier
            
            self.info_geom.config(text=f"Dimensions: {Le:.2f}m × {He:.2f}m (ext.) | {Li:.2f}m × {Hi:.2f}m (int.)")
        except:
            self.info_geom.config(text="")

    # Méthodes de dessin 3D
    def _dessiner_dalot_3d(self):
        """Dessine le dalot en 3D avec une échelle réaliste et utilise tout l'espace disponible"""
        try:
            self.ax_3d.clear()
            
            # Récupérer les dimensions
            Li = self.Li_m.get()
            Hi = self.Hi_m.get()
            e_dalle = self.e_dalle_m.get()
            e_voile = self.e_voile_m.get()
            e_radier = self.e_radier_m.get()
            
            # Dimensions extérieures
            Le = Li + 2 * e_voile
            He = Hi + e_dalle + e_radier
            
            # Longueur du dalot (représentant la largeur de la route)
            # Utiliser une valeur significative pour la visualisation
            longueur_dalot = max(10.0, Le * 3)  # Au moins 10m ou 3 fois la largeur
            
            # Définir les couleurs avec un rendu plus réaliste
            couleur_dalle = '#90CAF9'   # Bleu clair pour la dalle supérieure
            couleur_voile = '#EF9A9A'   # Rouge clair pour les voiles
            couleur_radier = '#B0BEC5'  # Gris pour le radier
            
            # Dessiner les éléments avec des dimensions réalistes
            # Radier (dalle inférieure)
            self._dessiner_boite_3d(0, longueur_dalot, 0, Le, 0, e_radier, couleur_radier, 'Radier')
            
            # Voile gauche
            self._dessiner_boite_3d(0, longueur_dalot, 0, e_voile, e_radier, e_radier+Hi, couleur_voile, 'Voile gauche')
            
            # Voile droit
            self._dessiner_boite_3d(0, longueur_dalot, Le-e_voile, Le, e_radier, e_radier+Hi, couleur_voile, 'Voile droit')
            
            # Dalle supérieure
            self._dessiner_boite_3d(0, longueur_dalot, 0, Le, e_radier+Hi, He, couleur_dalle, 'Dalle')
            
            # Ajouter des repères visuels pour l'échelle
            self._ajouter_dimensions_3d(longueur_dalot, Le, He)
            
            # Dessiner un sol simplifié pour le contexte
            xs = np.array([0, longueur_dalot, longueur_dalot, 0])
            ys = np.array([-Le*0.5, -Le*0.5, Le*1.5, Le*1.5])
            zs = np.zeros(4) - 0.05  # Légèrement sous le niveau du radier
            self.ax_3d.plot_trisurf(xs, ys, zs, alpha=0.3, color='#8D6E63')  # Couleur terre
            
            # Dessiner remblai au-dessus du dalot
            hr = self.hr_m.get()
            if hr > 0:
                # Surface supérieure du remblai
                xs_remblai = np.array([0, longueur_dalot, longueur_dalot, 0])
                ys_remblai = np.array([-Le*0.5, -Le*0.5, Le*1.5, Le*1.5])
                zs_remblai = np.ones(4) * (He + hr)
                self.ax_3d.plot_trisurf(xs_remblai, ys_remblai, zs_remblai, alpha=0.4, color='#A1887F')
                
                # Faces latérales du remblai (simplifiées)
                faces_remblai = [
                    [[0, -Le*0.5, 0], [longueur_dalot, -Le*0.5, 0], [longueur_dalot, -Le*0.5, He+hr], [0, -Le*0.5, He+hr]],
                    [[0, Le*1.5, 0], [longueur_dalot, Le*1.5, 0], [longueur_dalot, Le*1.5, He+hr], [0, Le*1.5, He+hr]],
                    [[0, -Le*0.5, He], [0, Le*1.5, He], [0, Le*1.5, He+hr], [0, -Le*0.5, He+hr]],
                    [[longueur_dalot, -Le*0.5, He], [longueur_dalot, Le*1.5, He], [longueur_dalot, Le*1.5, He+hr], [longueur_dalot, -Le*0.5, He+hr]]
                ]
                collection_remblai = Poly3DCollection(faces_remblai, alpha=0.2, linewidth=0.5, edgecolor='#795548')
                collection_remblai.set_facecolor('#A1887F')
                self.ax_3d.add_collection3d(collection_remblai)
                
                # Texte pour indiquer la hauteur du remblai
                self.ax_3d.text(longueur_dalot/2, Le*1.7, He+hr/2, f"Remblai\n{hr:.2f}m", ha='center', va='center')
            
            # Dessiner axes de référence et légendes
            self.ax_3d.set_xlabel('Longueur (m)', fontsize=12, fontweight='bold')
            self.ax_3d.set_ylabel('Largeur (m)', fontsize=12, fontweight='bold')
            self.ax_3d.set_zlabel('Hauteur (m)', fontsize=12, fontweight='bold')
            
            # Ajuster les limites avec une marge
            marge_x = longueur_dalot * 0.1
            marge_y = Le * 1.0  # Marge plus grande pour l'axe Y
            marge_z = (He + hr) * 0.3
            self.ax_3d.set_xlim(-marge_x, longueur_dalot + marge_x)
            self.ax_3d.set_ylim(-Le*0.7, Le*1.7)
            self.ax_3d.set_zlim(-marge_z/2, He + hr + marge_z/2)
            
            # Assurer que les proportions sont correctes
            # Utiliser un rapport d'aspect cohérent pour un rendu plus réaliste
            max_range = max(longueur_dalot, Le*2.4, He+hr)
            self.ax_3d.set_box_aspect([longueur_dalot/max_range, Le*2.4/max_range, (He+hr)/max_range])
            
            # Ajouter un titre détaillé
            self.ax_3d.set_title(f'Dalot: L={longueur_dalot:.1f}m × l={Le:.2f}m × H={He:.2f}m\nDimensions intérieures: {Li:.2f}m × {Hi:.2f}m\nHauteur remblai: {hr:.2f}m', 
                            fontsize=12, fontweight='bold')
            
            # Améliorer l'éclairage pour un rendu plus réaliste
            self.ax_3d.view_init(elev=25, azim=30)
            
            # Ajouter une grille
            self.ax_3d.grid(True, linestyle='--', alpha=0.6)
            
            # Actualiser le canvas avec une taille optimisée
            self.canvas_3d.draw()
            
            # Mettre à jour la barre de statut
            self._maj_info_statut()
            
        except Exception as e:
            messagebox.showerror("Erreur de visualisation", f"Erreur: {str(e)}")

    def _ajouter_dimensions_3d(self, longueur, largeur, hauteur):
        """Ajoute des annotations de dimensions sur le modèle 3D"""
        # Style des flèches
        arrow_props = dict(arrowstyle='<->', color='black', lw=2, shrinkA=5, shrinkB=5)
        
        # Longueur (axe X)
        x_mid = longueur / 2
        self.ax_3d.text(x_mid, -largeur*0.4, -hauteur*0.1, f'Longueur: {longueur:.1f} m', 
                       ha='center', va='center', fontsize=10, fontweight='bold')
        self.ax_3d.annotate('', xy=(longueur, -largeur*0.3, 0), xytext=(0, -largeur*0.3, 0), 
                          arrowprops=arrow_props)
        
        # Largeur (axe Y)
        y_mid = largeur / 2
        self.ax_3d.text(-longueur*0.05, y_mid, -hauteur*0.1, f'Largeur: {largeur:.2f} m', 
                       ha='center', va='center', fontsize=10, fontweight='bold', rotation=90)
        self.ax_3d.annotate('', xy=(-longueur*0.1, largeur, 0), xytext=(-longueur*0.1, 0, 0), 
                          arrowprops=arrow_props)
        
        # Hauteur (axe Z)
        z_mid = hauteur / 2
        self.ax_3d.text(-longueur*0.1, -largeur*0.3, z_mid, f'Hauteur: {hauteur:.2f} m', 
                       ha='center', va='center', fontsize=10, fontweight='bold')
        self.ax_3d.annotate('', xy=(-longueur*0.05, -largeur*0.3, hauteur), 
                          xytext=(-longueur*0.05, -largeur*0.3, 0), arrowprops=arrow_props)
        
        # Dimensions intérieures
        Li = self.Li_m.get()
        Hi = self.Hi_m.get()
        
        # Largeur intérieure
        self.ax_3d.annotate('', xy=(longueur*0.7, Li, 0), xytext=(longueur*0.7, 0, 0), 
                          arrowprops=dict(arrowstyle='<->', color='blue', lw=2, shrinkA=5, shrinkB=5))
        self.ax_3d.text(longueur*0.75, Li/2, 0, f'Li: {Li:.2f} m', 
                       ha='center', va='center', fontsize=9, color='blue')
        
        # Hauteur intérieure
        self.ax_3d.annotate('', xy=(longueur*0.8, Li+0.1, Hi+self.e_radier_m.get()), 
                         xytext=(longueur*0.8, Li+0.1, self.e_radier_m.get()), 
                         arrowprops=dict(arrowstyle='<->', color='blue', lw=2, shrinkA=5, shrinkB=5))
        self.ax_3d.text(longueur*0.85, Li+0.1, Hi/2+self.e_radier_m.get(), f'Hi: {Hi:.2f} m', 
                      ha='center', va='center', fontsize=9, color='blue')

    def _dessiner_boite_3d(self, x_min, x_max, y_min, y_max, z_min, z_max, couleur, label=None):
        """Dessine une boîte 3D aux coordonnées spécifiées"""
        vertices = self._creer_sommets_boite(x_min, x_max, y_min, y_max, z_min, z_max)
        faces = self._creer_faces_boite(vertices)
        
        collection = Poly3DCollection(faces, alpha=0.7, linewidth=1, edgecolor='black')
        collection.set_facecolor(couleur)
        
        self.ax_3d.add_collection3d(collection)
        
        if label:
            # Centrer le label
            x_center = (x_min + x_max) / 2
            y_center = (y_min + y_max) / 2
            z_center = (z_min + z_max) / 2
            
            # Ajouter le label au centre de la boîte
            self.ax_3d.text(x_center, y_center, z_center, label, fontsize=8, ha='center', va='center')

    def _creer_sommets_boite(self, x_min, x_max, y_min, y_max, z_min, z_max):
        """Crée les 8 sommets d'une boîte 3D"""
        return [
            [x_min, y_min, z_min], [x_max, y_min, z_min], [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_max], [x_max, y_min, z_max], [x_max, y_max, z_max], [x_min, y_max, z_max]
        ]
    
    def _creer_faces_boite(self, vertices):
        """Crée les 6 faces d'une boîte à partir des sommets"""
        return [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # face inférieure
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # face supérieure
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # face avant
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # face arrière
            [vertices[1], vertices[2], vertices[6], vertices[5]],  # face droite
            [vertices[0], vertices[3], vertices[7], vertices[4]]   # face gauche
        ]

    # Événements 3D
    def _on_scroll_zoom(self, event):
        """Gestion du zoom avec la molette"""
        if event.inaxes == self.ax_3d:
            factor = 0.9 if event.button == 'down' else 1.1
            
            x_limits = self.ax_3d.get_xlim3d()
            y_limits = self.ax_3d.get_ylim3d()
            z_limits = self.ax_3d.get_zlim3d()
            
            x_range = (x_limits[1] - x_limits[0]) * factor
            y_range = (y_limits[1] - y_limits[0]) * factor
            z_range = (z_limits[1] - z_limits[0]) * factor
            
            x_center = (x_limits[1] + x_limits[0]) / 2
            y_center = (y_limits[1] + y_limits[0]) / 2
            z_center = (z_limits[1] + z_limits[0]) / 2
            
            self.ax_3d.set_xlim3d([x_center - x_range/2, x_center + x_range/2])
            self.ax_3d.set_ylim3d([y_center - y_range/2, y_center + y_range/2])
            self.ax_3d.set_zlim3d([z_center - z_range/2, z_center + z_range/2])
            
            self.canvas_3d.draw()

    def _on_click_3d(self, event):
        """Gestion du clic pour la rotation"""
        if event.inaxes == self.ax_3d:
            self.mouse_pressed = True
            self.last_mouse_pos = (event.xdata, event.ydata)

    def _on_release_3d(self, event):
        """Gestion du relâchement du clic"""
        self.mouse_pressed = False

    def _on_motion_3d(self, event):
        """Gestion du mouvement de souris pour la rotation"""
        if self.mouse_pressed and self.last_mouse_pos and event.inaxes == self.ax_3d:
            dx = event.xdata - self.last_mouse_pos[0]
            dy = event.ydata - self.last_mouse_pos[1]
            
            # Récupérer l'angle de vue actuel
            elev = self.ax_3d.elev
            azim = self.ax_3d.azim
            
            # Ajuster l'angle de vue
            self.ax_3d.view_init(elev=elev - dy*0.5, azim=azim + dx*0.5)
            
            self.canvas_3d.draw()
            self.last_mouse_pos = (event.xdata, event.ydata)

    # Commandes des vues 3D
    def cmd_vue_isometrique(self):
        """Vue isométrique avec animation"""
        self.ax_3d.view_init(elev=30, azim=45)
        self.canvas_3d.draw()

    def cmd_vue_face(self):
        """Vue de face avec animation"""
        self.ax_3d.view_init(elev=0, azim=0)
        self.canvas_3d.draw()

    def cmd_vue_cote(self):
        """Vue de côté avec animation"""
        self.ax_3d.view_init(elev=0, azim=90)
        self.canvas_3d.draw()

    def cmd_vue_dessus(self):
        """Vue de dessus avec animation"""
        self.ax_3d.view_init(elev=90, azim=0)
        self.canvas_3d.draw()

    def cmd_reset_vue(self):
        """Reset de la vue"""
        self._dessiner_dalot_3d()

    def cmd_zoom_adapte(self):
        """Zoom adapté au contenu"""
        try:
            Li = self.Li_m.get()
            Hi = self.Hi_m.get()
            e_dalle = self.e_dalle_m.get()
            e_voile = self.e_voile_m.get()
            e_radier = self.e_radier_m.get()
            
            # Dimensions extérieures
            Le = Li + 2 * e_voile
            He = Hi + e_dalle + e_radier
            
            # Ajuster les limites avec une marge
            marge = max(Le, Hi) * 0.1
            self.ax_3d.set_xlim(0-marge, Le+marge)
            self.ax_3d.set_ylim(0-marge, Li+2*e_voile+marge)
            self.ax_3d.set_zlim(0-marge, He+marge)
            
            self.canvas_3d.draw()
        except:
            pass

    def cmd_capture_3d(self):
        """Capture la vue 3D actuelle"""
        try:
            fichier = filedialog.asksaveasfilename(
                title="Enregistrer la capture 3D",
                defaultextension=".png",
                filetypes=[("Images PNG", "*.png"), ("Images JPEG", "*.jpg"), ("Tous fichiers", "*.*")]
            )
            if fichier:
                self.figure_3d.savefig(fichier, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Capture", f"Image enregistrée dans {fichier}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer l'image: {str(e)}")

    def cmd_animation_3d(self):
        """Animation rotative 3D"""
        def rotation(angle):
            self.ax_3d.view_init(elev=30, azim=angle)
            self.canvas_3d.draw()
            if angle < 360:
                self.after(50, lambda: rotation(angle + 5))
        
        rotation(0)

    # Nouvelle méthode pour la génération de rapport
    def cmd_generer_rapport(self):
        """Génère un rapport complet des calculs avec vérification préalable"""
        if hasattr(self, 'dernier_recap') and self.dernier_recap:
            self._generer_rapport_complet_avance()
        else:
            if messagebox.askyesno("Rapport", "Aucun calcul n'a encore été effectué.\nVoulez-vous lancer les calculs maintenant?"):
                self.cmd_lancer_calculs()
                # Attendre 6 secondes pour que les calculs se terminent avant de générer le rapport
                self.after(6100, self._generer_rapport_complet_avance)

    # Méthodes de calcul
    def cmd_verifier_entrees(self):
        """Vérifie la validité des entrées"""
        try:
            # Vérification des valeurs
            Li = self.Li_m.get()
            Hi = self.Hi_m.get()
            e_dalle = self.e_dalle_m.get()
            e_voile = self.e_voile_m.get()
            e_radier = self.e_radier_m.get()
            hr = self.hr_m.get()
            
            erreurs = []
            
            if Li <= 0 or Hi <= 0 or e_dalle <= 0 or e_voile <= 0 or e_radier <= 0:
                erreurs.append("Toutes les dimensions doivent être positives")
            
            if e_voile > Li/2:
                erreurs.append("L'épaisseur des voiles est trop importante par rapport à la largeur")
            
            if e_dalle + e_radier > Hi:
                erreurs.append("La somme des épaisseurs de dalle et radier dépasse la hauteur intérieure")
            
            if hr < 0:
                erreurs.append("La hauteur de remblai ne peut pas être négative")
            
            if erreurs:
                messagebox.showerror("Erreurs dans les entrées", "\n".join(erreurs))
                return False
            
            messagebox.showinfo("Validation", "Les paramètres sont valides. Vous pouvez lancer les calculs.")
            return True
            
        except Exception as e:
            messagebox.showerror("Erreur de validation", f"Erreur: {str(e)}")
            return False

    def cmd_lancer_calculs(self):
        """Lance les calculs avec simulation de progression"""
        if not self.cmd_verifier_entrees():
            return
        
        # Démarrer le calcul dans un thread séparé
        self.thread_calcul = threading.Thread(target=self._effectuer_calculs)
        self.thread_calcul.daemon = True
        self.thread_calcul.start()
        
        # Démarrer l'animation de la barre de progression
        self._simuler_progression()

    def _simuler_progression(self):
        """Simule une progression de 6 secondes"""
        self.progression.set(0)
        self.texte_journal.set("Initialisation des calculs...")
        
        def actualiser_progression(etape=0, max_etapes=100):
            if etape <= max_etapes:
                pct = etape * 100 // max_etapes
                self.progression.set(pct)
                
                if etape == 10:
                    self.texte_journal.set("Chargement des paramètres...")
                elif etape == 20:
                    self.texte_journal.set("Préparation des matrices de calcul...")
                elif etape == 40:
                    self.texte_journal.set("Calcul des sollicitations...")
                elif etape == 60:
                    self.texte_journal.set("Traitement des résultats...")
                elif etape == 80:
                    self.texte_journal.set("Génération du rapport...")
                elif etape == 95:
                    self.texte_journal.set("Finalisation...")
                    
                self.after(60, lambda: actualiser_progression(etape + 1, max_etapes))
            else:
                self.texte_journal.set("Calculs terminés")
                self._generer_rapport_complet_avance()
        
        # Durée totale : 6 secondes (100 étapes à 60ms = 6000ms)
        actualiser_progression(0, 100)

    def _effectuer_calculs(self):
        """Effectue les calculs de Kleinlogel"""
        try:
            # Construire les objets pour Kleinlogel
            geom = GeometrieDalot(
                Li_m=self.Li_m.get(),
                Hi_m=self.Hi_m.get(),
                e_dalle_m=self.e_dalle_m.get(),
                e_voile_m=self.e_voile_m.get(),
                e_radier_m=self.e_radier_m.get()
            )
            
            materiau = Materiau(gamma_b_kN_m3=self.gamma_b_kN_m3.get())
            sol = Sol(
                gamma_sol_kN_m3=self.gamma_sol_kN_m3.get(),
                phi_deg=self.phi_deg.get(),
                c_pa=self.c_pa.get()
            )
            
            kle = Kleinlogel(
                geom=geom,
                materiau=materiau,
                sol=sol,
                F_br_tonnes=10.0,
                bc_defaut=self.bc.get(),
                bt_defaut=self.bt.get()
            )
            
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
            self.dernier_recap = construire_tableau_recap(self.dernier_resultats, kle)
            
        except Exception as e:
            messagebox.showerror("Erreur de calcul", f"Erreur: {str(e)}")

    def _generer_rapport_complet_avance(self):
        """Génère un rapport complet des résultats de calcul avec description minutieuse"""
        if not hasattr(self, "dernier_recap") or not self.dernier_recap:
            messagebox.showinfo("Information", "Aucun résultat disponible. Veuillez d'abord lancer les calculs.")
            return
        
        self.texte_resultats.delete("1.0", tk.END)
        
        # En-tête
        self.texte_resultats.insert(tk.END, "=" * 80 + "\n")
        self.texte_resultats.insert(tk.END, "RAPPORT DE DIMENSIONNEMENT DALOT - MÉTHODE DE KLEINLOGEL\n")
        self.texte_resultats.insert(tk.END, "=" * 80 + "\n\n")
        
        # Paramètres géométriques
        self.texte_resultats.insert(tk.END, "PARAMÈTRES GÉOMÉTRIQUES\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, f"Largeur intérieure (Li): {self.Li_m.get():.2f} m\n")
        self.texte_resultats.insert(tk.END, f"Hauteur intérieure (Hi): {self.Hi_m.get():.2f} m\n")
        self.texte_resultats.insert(tk.END, f"Épaisseur dalle: {self.e_dalle_m.get():.2f} m\n")
        self.texte_resultats.insert(tk.END, f"Épaisseur voile: {self.e_voile_m.get():.2f} m\n")
        self.texte_resultats.insert(tk.END, f"Épaisseur radier: {self.e_radier_m.get():.2f} m\n")
        
        # Dimensions calculées
        Le = self.Li_m.get() + 2 * self.e_voile_m.get()
        He = self.Hi_m.get() + self.e_dalle_m.get() + self.e_radier_m.get()
        self.texte_resultats.insert(tk.END, f"Dimensions extérieures: {Le:.2f}m × {He:.2f}m\n\n")
        
        # Matériaux
        self.texte_resultats.insert(tk.END, "MATÉRIAUX\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        classe_beton = self.classe_beton.get()
        classe_acier = self.classe_acier.get()
        info_beton = DonneesNormalisees.CLASSES_BETON[classe_beton]
        info_acier = DonneesNormalisees.CLASSES_ACIER[classe_acier]
        
        self.texte_resultats.insert(tk.END, f"Béton: {classe_beton} - fc28 = {info_beton['fc28']} MPa\n")
        self.texte_resultats.insert(tk.END, f"Acier: {classe_acier} - fyk = {info_acier['fyk']} MPa\n")
        self.texte_resultats.insert(tk.END, f"Exposition: {self.classe_exposition.get()}\n")
        self.texte_resultats.insert(tk.END, f"Poids volumique béton: {self.gamma_b_kN_m3.get():.1f} kN/m³\n\n")
        
        # Charges
        self.texte_resultats.insert(tk.END, "PARAMÈTRES DE CHARGEMENT\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, f"Hauteur de remblai: {self.hr_m.get():.2f} m\n")
        self.texte_resultats.insert(tk.END, f"Type de remblai: {self.type_remblai.get()}\n")
        self.texte_resultats.insert(tk.END, f"Poids volumique sol: {self.gamma_sol_kN_m3.get():.1f} kN/m³\n")
        self.texte_resultats.insert(tk.END, f"Angle de frottement: {self.phi_deg.get():.1f}°\n")
        self.texte_resultats.insert(tk.END, f"Cohésion: {self.c_pa.get():.1f} Pa\n")
        self.texte_resultats.insert(tk.END, f"Classe de trafic: {self.classe_trafic.get()}\n")
        self.texte_resultats.insert(tk.END, f"Surcharge routière: {self.q_surcharge_kN_m2.get():.1f} kN/m²\n")
        self.texte_resultats.insert(tk.END, f"Coefficient Bc: {self.bc.get():.2f}\n")
        self.texte_resultats.insert(tk.END, f"Coefficient Bt: {self.bt.get():.2f}\n\n")
        
        # Description détaillée des étapes de calcul
        self.texte_resultats.insert(tk.END, "MÉTHODE DE CALCUL DÉTAILLÉE\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, "Le calcul est effectué selon la méthode de Kleinlogel pour les cadres fermés.\n")
        self.texte_resultats.insert(tk.END, "Cette méthode utilise les formules suivantes :\n\n")
        
        self.texte_resultats.insert(tk.END, "1. Détermination des paramètres géométriques :\n")
        self.texte_resultats.insert(tk.END, "   • h_eff = Hi + e_dalle/2 + e_radier/2\n")
        self.texte_resultats.insert(tk.END, "   • l_eff = Li + e_voile\n")
        self.texte_resultats.insert(tk.END, "   • j1 = (e_radier)³/12\n")
        self.texte_resultats.insert(tk.END, "   • j2 = (e_voile)³/12\n")
        self.texte_resultats.insert(tk.END, "   • j3 = (e_dalle)³/12\n")
        self.texte_resultats.insert(tk.END, "   • k1 = j3/j1\n")
        self.texte_resultats.insert(tk.END, "   • k2 = (j3/j2)*(h_eff/l_eff)\n\n")
        
        self.texte_resultats.insert(tk.END, "2. Calcul du coefficient de poussée des terres :\n")
        self.texte_resultats.insert(tk.END, "   • Ka = tan²(45° - φ/2)\n\n")
        
        self.texte_resultats.insert(tk.END, "3. Calcul des charges :\n")
        self.texte_resultats.insert(tk.END, "   • Poids propre dalle = γb × e_dalle\n")
        self.texte_resultats.insert(tk.END, "   • Poids remblai = γsol × hauteur_remblai\n")
        self.texte_resultats.insert(tk.END, "   • Poussée des terres σ1 = Ka × γsol × hauteur_remblai\n")
        self.texte_resultats.insert(tk.END, "   • Poussée des terres σ2 = Ka × γsol × (hauteur_remblai + hauteur_totale)\n")
        self.texte_resultats.insert(tk.END, "   • Charges de convoi (Bc, Bt, Br) selon formulaire adapté\n\n")
        
        self.texte_resultats.insert(tk.END, "4. Application des formules de Kleinlogel pour chaque cas de charge :\n")
        self.texte_resultats.insert(tk.END, "   • Charges uniformes, poussées symétriques, charges concentrées\n")
        self.texte_resultats.insert(tk.END, "   • Combinaison des effets : G = charges permanentes, Q = charges variables\n")
        self.texte_resultats.insert(tk.END, "   • ELS : G + Q\n")
        self.texte_resultats.insert(tk.END, "   • ELU : 1.35G + 1.5Q\n\n")
        
        # Paramètres Kleinlogel
        params_k = self.dernier_resultats["params_kleinlogel"]
        self.texte_resultats.insert(tk.END, "PARAMÈTRES DE CALCUL KLEINLOGEL\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, f"Ka = {params_k['Ka']:.6f} (coefficient de poussée active)\n")
        self.texte_resultats.insert(tk.END, f"h_eff = {params_k['h_eff']:.6f} m (hauteur effective)\n")
        self.texte_resultats.insert(tk.END, f"l_eff = {params_k['l_eff']:.6f} m (largeur effective)\n")
        self.texte_resultats.insert(tk.END, f"j1 = {params_k['j1']:.6e} m⁴ (inertie radier)\n")
        self.texte_resultats.insert(tk.END, f"j2 = {params_k['j2']:.6e} m⁴ (inertie voile)\n")
        self.texte_resultats.insert(tk.END, f"j3 = {params_k['j3']:.6e} m⁴ (inertie dalle)\n")
        self.texte_resultats.insert(tk.END, f"k1 = {params_k['k1']:.6f} (ratio j3/j1)\n")
        self.texte_resultats.insert(tk.END, f"k2 = {params_k['k2']:.6f} (ratio j3/j2 × h_eff/l_eff)\n")
        self.texte_resultats.insert(tk.END, f"F1 = {params_k['F1']:.6e} (K1×K2-k2²)\n")
        self.texte_resultats.insert(tk.END, f"F2 = {params_k['F2']:.6f} (1+k1+6×k2)\n\n")
        
        # Charges calculées avec plus de détails
        self.texte_resultats.insert(tk.END, "DÉTAIL DES CHARGES CALCULÉES\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, f"Poids volumique béton: {params_k['gamma_b_t_m3']:.4f} t/m³\n")
        self.texte_resultats.insert(tk.END, f"Poids volumique sol: {params_k['gamma_sol_t_m3']:.4f} t/m³\n\n")
        
        self.texte_resultats.insert(tk.END, "Charges permanentes :\n")
        self.texte_resultats.insert(tk.END, f"• Poids propre dalle: {params_k['p_tablier_t_m2']:.4f} t/m²\n")
        self.texte_resultats.insert(tk.END, f"• Poids remblai: {params_k['p_remblai_t_m2']:.4f} t/m²\n")
        self.texte_resultats.insert(tk.END, f"• Charge permanente totale: {params_k['q_permanente_t_m2']:.4f} t/m²\n\n")
        
        self.texte_resultats.insert(tk.END, "Poussée des terres :\n")
        self.texte_resultats.insert(tk.END, f"• σ1 (haut): {params_k['sigma1_t_m2']:.4f} t/m²\n")
        self.texte_resultats.insert(tk.END, f"• σ2 (bas): {params_k['sigma2_t_m2']:.4f} t/m²\n")
        self.texte_resultats.insert(tk.END, f"• Poids propre voile (P): {params_k['P_t']:.4f} t/ml\n\n")
        
        self.texte_resultats.insert(tk.END, "Charges de convoi :\n")
        self.texte_resultats.insert(tk.END, f"• Convoi Bc: {params_k['q_bc_t_m2']:.6f} t/m² → {params_k['q_bc_t_par_m']:.6f} t/m\n")
        self.texte_resultats.insert(tk.END, f"• Convoi Bt: {params_k['q_bt_t_m2']:.6f} t/m² → {params_k['q_bt_t_par_m']:.6f} t/m\n")
        self.texte_resultats.insert(tk.END, f"• Convoi Br: {params_k['q_br_t_m2']:.6f} t/m² → {params_k['q_br_t_par_m']:.6f} t/m\n")
        self.texte_resultats.insert(tk.END, f"• Convoi maximal: {params_k['qmax_t_m2']:.6f} t/m²\n\n")
        
        self.texte_resultats.insert(tk.END, "Surcharge routière :\n")
        self.texte_resultats.insert(tk.END, f"• Surcharge: {params_k['q_surcharge_t_m2']:.6f} t/m²\n")
        self.texte_resultats.insert(tk.END, f"• Poussée induite (σ): {params_k['sigma_q_t_m2']:.6f} t/m²\n\n")
        
        # Tableau récapitulatif détaillé des résultats
        self.texte_resultats.insert(tk.END, "TABLEAU RÉCAPITULATIF DES RÉSULTATS\n")
        self.texte_resultats.insert(tk.END, "-" * 80 + "\n")
        self.texte_resultats.insert(tk.END, "La section du dalot comporte 4 nœuds principaux :\n")
        self.texte_resultats.insert(tk.END, "• A: jonction radier-voile gauche\n")
        self.texte_resultats.insert(tk.END, "• B: jonction dalle-voile gauche\n")
        self.texte_resultats.insert(tk.END, "• C: jonction dalle-voile droit\n")
        self.texte_resultats.insert(tk.END, "• D: jonction radier-voile droit\n\n")
        
        self.texte_resultats.insert(tk.END, "Les valeurs suivantes sont exprimées en t·m/ml pour les moments et t/ml pour les efforts tranchants.\n\n")
        
        self.texte_resultats.insert(tk.END, f"{'CAS DE CHARGE':<30} {'MA':<10} {'MB':<10} {'MC':<10} {'MD':<10} {'M_BC':<10} {'M_AD':<10} {'M_AB':<10} {'M_CD':<10}\n")
        self.texte_resultats.insert(tk.END, "-" * 110 + "\n")
        
        # Ajouter chaque cas avec tous les moments
        for designation, vals in self.dernier_recap.items():
            MA = vals.get('MA', 0.0)
            MB = vals.get('MB', 0.0)
            MC = vals.get('MC', 0.0)
            MD = vals.get('MD', 0.0)
            M_BC = vals.get('M_BC', 0.0)
            M_AD = vals.get('M_AD', 0.0)
            M_AB = vals.get('M_AB', 0.0)
            M_CD = vals.get('M_CD', 0.0)
            
            self.texte_resultats.insert(tk.END, f"{designation:<30} {MA:<10.4f} {MB:<10.4f} {MC:<10.4f} {MD:<10.4f} {M_BC:<10.4f} {M_AD:<10.4f} {M_AB:<10.4f} {M_CD:<10.4f}\n")
            
            # Mettre en évidence les combinaisons ELU et ELS
            if designation in ["combinaison ELU (1.35G+1.5Q)", "combinaison ELS (G+Q)"]:
                self.texte_resultats.insert(tk.END, "-" * 110 + "\n")
        
        self.texte_resultats.insert(tk.END, "\n")
        
        # Tableau des efforts tranchants
        self.texte_resultats.insert(tk.END, "EFFORTS TRANCHANTS ET NORMAUX\n")
        self.texte_resultats.insert(tk.END, "-" * 60 + "\n")
        self.texte_resultats.insert(tk.END, f"{'CAS DE CHARGE':<30} {'S1':<10} {'S2':<10} {'S3':<10}\n")
        self.texte_resultats.insert(tk.END, "-" * 60 + "\n")
        
        # Ajouter chaque cas
        for designation, vals in self.dernier_recap.items():
            S1 = vals.get('S1', 0.0)
            S2 = vals.get('S2', 0.0)
            S3 = vals.get('S3', 0.0)
            self.texte_resultats.insert(tk.END, f"{designation:<30} {S1:<10.4f} {S2:<10.4f} {S3:<10.4f}\n")
            
            # Mettre en évidence les combinaisons ELU et ELS
            if designation in ["combinaison ELU (1.35G+1.5Q)", "combinaison ELS (G+Q)"]:
                self.texte_resultats.insert(tk.END, "-" * 60 + "\n")
        
        self.texte_resultats.insert(tk.END, "\nLégende des efforts :\n")
        self.texte_resultats.insert(tk.END, "• S1 : effort tranchant dans les piédroits adjacents au radier\n")
        self.texte_resultats.insert(tk.END, "• S2 : effort tranchant dans les piédroits adjacents à la dalle\n")
        self.texte_resultats.insert(tk.END, "• S3 : effort normal dans la dalle et le radier\n\n")
        
        # Signification physique des résultats
        self.texte_resultats.insert(tk.END, "INTERPRÉTATION DES RÉSULTATS\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, "• MA, MB, MC, MD : moments fléchissants aux nœuds (positif = traction côté intérieur)\n")
        self.texte_resultats.insert(tk.END, "• M_BC : moment fléchissant au milieu de la dalle supérieure\n")
        self.texte_resultats.insert(tk.END, "• M_AD : moment fléchissant au milieu du radier\n")
        self.texte_resultats.insert(tk.END, "• M_AB, M_CD : moments fléchissants au milieu des piédroits\n")
        self.texte_resultats.insert(tk.END, "• S1, S2, S3 : efforts tranchants et normaux aux extrémités des éléments\n\n")
        
        # Conclusion
        self.texte_resultats.insert(tk.END, "CONCLUSION\n")
        self.texte_resultats.insert(tk.END, "-" * 40 + "\n")
        self.texte_resultats.insert(tk.END, "Les calculs ont été réalisés avec la méthode de Kleinlogel pour les cadres fermés.\n")
        self.texte_resultats.insert(tk.END, "Cette méthode permet de déterminer les sollicitations dans le dalot sous différentes charges.\n\n")
        
        # Récupérer les valeurs ELU
        elu_vals = self.dernier_recap["combinaison ELU (1.35G+1.5Q)"]
        self.texte_resultats.insert(tk.END, "Valeurs de dimensionnement à l'ELU :\n")
        self.texte_resultats.insert(tk.END, f"• Moment maximal dans la dalle : M_BC = {elu_vals.get('M_BC', 0.0):.4f} t·m/ml\n")
        self.texte_resultats.insert(tk.END, f"• Moment maximal dans le radier : M_AD = {elu_vals.get('M_AD', 0.0):.4f} t·m/ml\n")
        self.texte_resultats.insert(tk.END, f"• Moment maximal dans les piédroits : max(M_AB, M_CD) = {max(elu_vals.get('M_AB', 0.0), elu_vals.get('M_CD', 0.0)):.4f} t·m/ml\n")
        self.texte_resultats.insert(tk.END, f"• Effort tranchant maximal : S1 = {elu_vals.get('S1', 0.0):.4f} t/ml\n\n")
        
        self.texte_resultats.insert(tk.END, "Pour le dimensionnement des armatures, il faut :\n")
        self.texte_resultats.insert(tk.END, "1. Convertir ces efforts en unités SI (1 t·m/ml = 9.81 kN·m/m)\n")
        self.texte_resultats.insert(tk.END, "2. Calculer les sections d'armatures requises selon les principes de l'Eurocode 2\n")
        self.texte_resultats.insert(tk.END, "3. Vérifier les conditions de service (fissuration, flèche)\n\n")
        
        # Date génération
        self.texte_resultats.insert(tk.END, "-" * 80 + "\n")
        self.texte_resultats.insert(tk.END, f"Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n")
        
        # Remonter au début du rapport
        self.texte_resultats.see("1.0")
        
        return "Rapport généré avec succès"

    def _copier_resultats(self):
        """Copie les résultats dans le presse-papiers"""
        texte = self.texte_resultats.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(texte)
        messagebox.showinfo("Copie", "Résultats copiés dans le presse-papiers")

    # Méthodes pour les opérations de fichier
    def action_nouveau(self):
        """Crée un nouveau projet"""
        if self.modifie:
            reponse = messagebox.askyesnocancel("Nouveau projet", 
                                              "Le projet actuel a été modifié.\nVoulez-vous l'enregistrer avant de créer un nouveau projet ?")
            if reponse is None:  # Annuler
                return
            elif reponse:  # Oui
                if not self.action_enregistrer():
                    return
        
        # Réinitialiser les variables
        self.Li_m.set(1)
        self.Hi_m.set(1)
        self.e_dalle_m.set(0.20)
        self.e_voile_m.set(0.20)
        self.e_radier_m.set(0.20)
        
        self.hr_m.set(1.0)
        self.type_remblai.set("Tout-venant")
        self.classe_trafic.set("T2")
        self.gamma_b_kN_m3.set(25.0)
        self.gamma_sol_kN_m3.set(18.0)
        self.phi_deg.set(30.0)
        self.c_pa.set(5000.0)
        self.q_surcharge_kN_m2.set(9)
        self.bc.set(1.1)
        self.bt.set(1.0)
        
        self.classe_beton.set("C25/30")
        self.classe_acier.set("S500B")
        self.classe_exposition.set("XC2")
        
        # Mettre à jour les infos
        self._maj_info_beton()
        self._maj_info_acier()
        self._maj_info_exposition()
        self._maj_info_trafic()
        self._maj_info_remblai()
        
        # Effacer les résultats
        self.texte_resultats.delete("1.0", tk.END)
        
        # Réinitialiser les variables de contrôle
        self.fichier_courant = None
        self.modifie = False
        self._mettre_a_jour_titre_fenetre()
        
        # Actualiser la visualisation 3D
        self._dessiner_dalot_3d()
        
        # Effacer les résultats de calcul précédents
        self.dernier_resultats = {}
        self.dernier_recap = {}
        
        messagebox.showinfo("Nouveau projet", "Un nouveau projet a été créé")

    def action_ouvrir(self):
        """Ouvre un projet existant"""
        if self.modifie:
            reponse = messagebox.askyesnocancel("Ouvrir projet", 
                                              "Le projet actuel a été modifié.\nVoulez-vous l'enregistrer avant d'ouvrir un autre projet ?")
            if reponse is None:  # Annuler
                return
            elif reponse:  # Oui
                if not self.action_enregistrer():
                    return
        
        fichier = filedialog.askopenfilename(
            title="Ouvrir un projet",
            filetypes=[("Fichiers projet", "*.dalot"), ("Tous fichiers", "*.*")]
        )
        
        if fichier:
            if GestionnaireProjet.charger_projet(self, fichier):
                messagebox.showinfo("Ouverture", f"Projet chargé avec succès:\n{fichier}")

    def action_enregistrer(self):
        """Enregistre le projet actuel"""
        if self.fichier_courant:
            return GestionnaireProjet.sauvegarder_projet(self, self.fichier_courant)
        else:
            return self.action_enregistrer_sous()

    def action_enregistrer_sous(self):
        """Enregistre le projet sous un nouveau nom"""
        fichier = filedialog.asksaveasfilename(
            title="Enregistrer le projet",
            defaultextension=".dalot",
            filetypes=[("Fichiers projet", "*.dalot"), ("Tous fichiers", "*.*")]
        )
        
        if fichier:
            return GestionnaireProjet.sauvegarder_projet(self, fichier)
        return False

    def cmd_exporter_pdf(self):
        """Exporte les résultats au format PDF"""
        if not hasattr(self, "dernier_recap") or not self.dernier_recap:
            messagebox.showinfo("Information", "Aucun résultat disponible. Veuillez d'abord lancer les calculs.")
            return
        
        fichier = filedialog.asksaveasfilename(
            title="Exporter en PDF",
            defaultextension=".pdf",
            filetypes=[("Fichiers PDF", "*.pdf"), ("Fichiers HTML", "*.html"), ("Tous fichiers", "*.*")]
        )
        
        if fichier:
            ExporteurPDF.generer_rapport_pdf(self, fichier)

    # Méthodes auxiliaires
    def _marquer_modifie(self, modifie=True):
        """Marque le projet comme modifié"""
        self.modifie = modifie
        self._mettre_a_jour_titre_fenetre()
        self._maj_info_statut()

    def _mettre_a_jour_titre_fenetre(self):
        """Met à jour le titre de la fenêtre en fonction de l'état"""
        titre = "Progiciel de dimensionnement des dalots en béton armé"
        if self.fichier_courant:
            nom_fichier = os.path.basename(self.fichier_courant)
            titre = f"{nom_fichier} - {titre}"
        if self.modifie:
            titre = f"*{titre}"
        self.title(titre)

    def _avant_quitter(self):
        """Actions à effectuer avant de quitter l'application"""
        if self.modifie:
            reponse = messagebox.askyesnocancel("Quitter", 
                                              "Le projet actuel a été modifié.\nVoulez-vous l'enregistrer avant de quitter ?")
            if reponse is None:  # Annuler
                return
            elif reponse:  # Oui
                if not self.action_enregistrer():
                    return
        
        self.destroy()

    # Commandes pour l'aide
    def cmd_manuel(self):
        """Affiche le manuel utilisateur"""
        messagebox.showinfo("Manuel utilisateur", 
                         "Le manuel utilisateur n'est pas encore disponible.\n\n"
                         "Ce logiciel permet le dimensionnement des dalots en béton armé "
                         "en utilisant la méthode de Kleinlogel pour le calcul des efforts.")

    def cmd_tutoriels(self):
        """Affiche les tutoriels"""
        messagebox.showinfo("Tutoriels", 
                         "Les tutoriels ne sont pas encore disponibles.\n\n"
                         "Pour utiliser ce logiciel :\n"
                         "1. Renseignez les paramètres géométriques\n"
                         "2. Définissez les matériaux\n"
                         "3. Configurez les charges\n"
                         "4. Lancez les calculs\n"
                         "5. Consultez les résultats")

    def cmd_a_propos(self):
        """Affiche les informations sur le logiciel"""
        messagebox.showinfo("À propos",
                         "Progiciel de dimensionnement des dalots en béton armé\n"
                         "Version 1.0\n\n"
                         "Intégration des algorithmes de calcul Kleinlogel\n"
                         "Développé par Kevindjoum\n\n"
                         "Ce logiciel permet le dimensionnement des dalots en béton armé "
                         "en utilisant la méthode de Kleinlogel pour le calcul des efforts.")

# Point d'entrée de l'application
if __name__ == "__main__":
    app = ApplicationDalotComplete()
    app.mainloop()