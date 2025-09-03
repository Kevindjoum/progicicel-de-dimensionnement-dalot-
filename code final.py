"""
Interface graphique complète pour le dimensionnement des dalots en béton armé
Version finale - Code complet et fonctionnel
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.pyplot as plt

# Simulation des modules de calcul
class SimulationCalculs:
    @staticmethod
    def analyser_dalot(longueur, largeur, hauteur, epaisseur_mur, epaisseur_dalle, params=None):
        """Analyse du dalot avec paramètres personnalisables"""
        try:
            # Paramètres par défaut si non fournis
            if params is None:
                params = {}
            
            # Récupération des paramètres utilisateur ou valeurs par défaut
            gamma_beton = 25.0  # kN/m³
            gamma_sol = params.get('sol_gamma_kN_m3', 20.0)
            phi_deg = params.get('sol_phi_deg', 30.0)
            c_kPa = params.get('sol_c_kPa', 0.0)
            q_trafic = params.get('q_trafic_kN_m2', 5.0)
            q_perm_supp = params.get('q_perm_supp_kN_m2', 2.0)
            gamma_G = params.get('gamma_G', 1.35)
            gamma_Q = params.get('gamma_Q', 1.5)
            
            # Matériaux (avec surcharges possibles)
            fck = float(params.get('fck_MPa') or '30')
            gamma_c = params.get('gamma_c', 1.5)
            alpha_cc = params.get('alpha_cc', 1.0)
            fcd = alpha_cc * fck / gamma_c
            
            fyk = float(params.get('fyk_MPa') or '500')
            gamma_s = params.get('gamma_s', 1.15)
            fyd = fyk / gamma_s
            
            enrobage = float(params.get('enrob_mm') or '30') / 1000  # Convert mm to m
            
            vol_dalle_fond = longueur * largeur * epaisseur_dalle
            vol_dalle_couverture = longueur * largeur * epaisseur_dalle
            vol_murs = 2 * longueur * epaisseur_mur * (hauteur - 2*epaisseur_dalle)
            vol_total = vol_dalle_fond + vol_dalle_couverture + vol_murs
            
            densite_beton = 2500
            masse_totale = vol_total * densite_beton
            
            q_pp_dalle = epaisseur_dalle * gamma_beton * 1000  # Convert to N/m²
            q_service = q_pp_dalle + q_perm_supp * 1000 + q_trafic * 1000  # All in N/m²
            q_ELU = gamma_G * (q_pp_dalle + q_perm_supp * 1000) + gamma_Q * q_trafic * 1000
            
            # Coefficients de poussée des terres
            phi_rad = np.radians(phi_deg)
            
            # Surcharges manuelles ou calcul automatique
            Ka_manuel = params.get('sol_Ka_manuel', '')
            K0_manuel = params.get('sol_K0_manuel', '')
            
            if Ka_manuel and Ka_manuel.strip():
                Ka = float(Ka_manuel)
            else:
                Ka = np.tan(np.pi/4 - phi_rad/2)**2  # Formule de Rankine
                
            if K0_manuel and K0_manuel.strip():
                K0 = float(K0_manuel)
            else:
                K0 = 1 - np.sin(phi_rad)  # Formule de Jaky
            
            # Pression latérale avec surcharge de surface
            sigma_h_base = Ka * gamma_sol * 1000 * hauteur + Ka * q_trafic * 1000  # N/m²
            force_poussee = 0.5 * Ka * gamma_sol * 1000 * hauteur**2 + Ka * q_trafic * 1000 * hauteur  # N/m
            
            # Point d'application (moment d'équilibre)
            if q_trafic > 0:
                M_triangulaire = (Ka * gamma_sol * 1000 * hauteur**2 / 2) * (hauteur / 3)
                M_rectangulaire = (Ka * q_trafic * 1000 * hauteur) * (hauteur / 2)
                point_application = (M_triangulaire + M_rectangulaire) / force_poussee
            else:
                point_application = hauteur / 3
            
            effort_normal_mur = q_service * largeur / 2
            moment_ELU_dalle = q_ELU * largeur**2 / 8
            
            d = epaisseur_dalle - enrobage
            mu = moment_ELU_dalle / (largeur * fcd * 1e6 * d**2)
            
            if mu < 0.372:
                alpha = 1.25 * (1 - np.sqrt(1 - 2*mu))
                z = d * (1 - 0.4*alpha)
                As_theorique = moment_ELU_dalle / (fyd * 1e6 * z)
            else:
                As_theorique = moment_ELU_dalle / (0.8 * fyd * 1e6 * d)
            
            armatures_dalle = SimulationCalculs.choisir_armatures(As_theorique, [8,10,12,14,16,20,25], [10,15,20,25,30])
            armatures_mur = {"diametre": 12, "espacement": 20, "As_fourni": np.pi * (0.012)**2 / 4 / 0.20}
            
            return {
                'validation_ok': True,
                'parametres': {
                    'gamma_sol_kN_m3': gamma_sol,
                    'phi_deg': phi_deg,
                    'c_kPa': c_kPa,
                    'Ka': Ka,
                    'K0': K0,
                    'fck_MPa': fck,
                    'fcd_MPa': fcd,
                    'fyk_MPa': fyk,
                    'fyd_MPa': fyd,
                    'gamma_G': gamma_G,
                    'gamma_Q': gamma_Q,
                    'enrobage_mm': enrobage * 1000
                },
                'volumes_masses': {
                    'dalle_fond': {'volume': vol_dalle_fond, 'masse': vol_dalle_fond * densite_beton, 'info': 'Dalle de fond'},
                    'dalle_couverture': {'volume': vol_dalle_couverture, 'masse': vol_dalle_couverture * densite_beton, 'info': 'Dalle de couverture'},
                    'murs': {'volume': vol_murs, 'masse': vol_murs * densite_beton, 'info': 'Murs latéraux'},
                    'total': {'volume': vol_total, 'masse': masse_totale, 'info': 'Total dalot'}
                },
                'charges_dalle_couverture': {
                    'q_pp_dalle': q_pp_dalle, 'q_trafic': q_trafic * 1000,
                    'q_permanente_supp': q_perm_supp * 1000, 'q_service': q_service, 'q_ELU': q_ELU
                },
                'poussee_terres': {
                    'sigma_h_base': sigma_h_base, 'force_poussee_par_metre': force_poussee,
                    'point_application_hauteur': point_application,
                    'formule_Ka': 'Rankine' if not (Ka_manuel and Ka_manuel.strip()) else 'Manuel',
                    'formule_K0': 'Jaky' if not (K0_manuel and K0_manuel.strip()) else 'Manuel'
                },
                'effort_normal_mur': {'valeur': effort_normal_mur, 'info': 'Effort normal dû aux charges verticales'},
                'ferraillage_dalle_couverture': {
                    'moment_ELU': moment_ELU_dalle, 'As_theorique': As_theorique, 'd_m': d,
                    'resultat': 'Ferraillage calculé', 'info': 'Calcul selon Eurocode 2'
                },
                'armatures_dalle_choisies': armatures_dalle,
                'armatures_mur_choisies': armatures_mur
            }
        except Exception as e:
            return {'erreur': str(e)}
    
    @staticmethod
    def choisir_armatures(As_theorique, diametres, espacements):
        for diametre in diametres:
            for espacement in espacements:
                section_barre = np.pi * (diametre/1000)**2 / 4
                As_fourni = section_barre / (espacement/100)
                if As_fourni >= As_theorique:
                    return {'diametre': diametre, 'espacement': espacement, 'As_fourni': As_fourni}
        return {'diametre': max(diametres), 'espacement': min(espacements), 
                'As_fourni': np.pi * (max(diametres)/1000)**2 / 4 / (min(espacements)/100)}

class DonneesNormalisees:
    LARGEURS_STANDARD = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0]
    HAUTEURS_STANDARD = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0, 3.5, 4.0]
    LONGUEURS_STANDARD = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]
    EPAISSEURS_DALLE = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]
    EPAISSEURS_VOILE = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    
    CLASSES_BETON = {
        "C20/25": {"fck": 20, "fcd": 13.3, "description": "Béton courant"},
        "C25/30": {"fck": 25, "fcd": 16.7, "description": "Béton courant renforcé"},
        "C30/37": {"fck": 30, "fcd": 20.0, "description": "Béton de qualité"},
        "C35/45": {"fck": 35, "fcd": 23.3, "description": "Béton haute résistance"},
        "C40/50": {"fck": 40, "fcd": 26.7, "description": "Béton très haute résistance"}
    }
    
    CLASSES_ACIER = {
        "B400": {"fyk": 400, "fyd": 348, "Es": 200000, "description": "Acier doux"},
        "B500A": {"fyk": 500, "fyd": 435, "Es": 200000, "description": "Acier haute adhérence A"},
        "B500B": {"fyk": 500, "fyd": 435, "Es": 200000, "description": "Acier haute adhérence B"},
        "B500C": {"fyk": 500, "fyd": 435, "Es": 200000, "description": "Acier haute adhérence C"}
    }
    
    DIAMETRES_PRINCIPAUX = ["φ8", "φ10", "φ12", "φ14", "φ16", "φ20", "φ25", "φ32"]
    DIAMETRES_SECONDAIRES = ["φ6", "φ8", "φ10", "φ12"]
    
    ENROBAGES_STANDARD = {
        "XC1 (Sec)": {"valeur": 25, "description": "Intérieur de bâtiments"},
        "XC2 (Humide)": {"valeur": 30, "description": "Surfaces soumises à l'eau"},
        "XC3 (Humidité modérée)": {"valeur": 30, "description": "Atmosphère modérément humide"},
        "XC4 (Cycles humide/sec)": {"valeur": 35, "description": "Surfaces alternativement sèches et humides"}
    }
    
    CLASSES_TRAFIC = {
        "T0 (Aucune)": {"charge": 0.0, "coefficient": 1.0, "description": "Aucune charge de trafic"},
        "T1 (Piétons)": {"charge": 2.5, "coefficient": 1.35, "description": "Circulation piétonne uniquement"},
        "T2 (Véhicules légers)": {"charge": 5.0, "coefficient": 1.35, "description": "Voitures, camionnettes < 3.5t"},
        "T3 (Poids lourds)": {"charge": 15.0, "coefficient": 1.35, "description": "Camions, bus jusqu'à 40t"}
    }
    
    TYPES_REMBLAI = {
        "Terre végétale": {"densite": 18.0, "angle": 25, "description": "Terre naturelle"},
        "Sable compacté": {"densite": 19.0, "angle": 30, "description": "Sable bien compacté"},
        "Grave compactée": {"densite": 20.0, "angle": 35, "description": "Grave-ciment compactée"},
        "Tout-venant": {"densite": 21.0, "angle": 32, "description": "Matériaux concassés"}
    }
    
    HAUTEURS_REMBLAI = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

class Infobulle:
    def __init__(self, widget, texte):
        self.widget = widget
        self.texte = texte
        self.bulle = None
        widget.bind("<Enter>", self._afficher)
        widget.bind("<Leave>", self._masquer)

    def _afficher(self, _event):
        if self.bulle or not self.texte:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except:
            x, y, cx, cy = (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.bulle = tk.Toplevel(self.widget)
        self.bulle.wm_overrideredirect(True)
        self.bulle.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.bulle, text=self.texte, justify="left", background="#ffffe0", 
                        relief="solid", borderwidth=1, font=("TkDefaultFont", 9))
        label.pack(ipadx=5, ipady=3)

    def _masquer(self, _event):
        if self.bulle:
            self.bulle.destroy()
            self.bulle = None

class ApplicationDalotComplete(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Progiciel Dalot BA - Interface Complète v2.0")
        self.geometry("1600x1000")
        self.minsize(1400, 900)

        self.chemin_fichier_courant = None
        self.modifie = False
        self.zoom_factor = 1.1
        self.selected_face = None
        self.original_face_colors = {}
        self.face_properties = {}
        self.dalot_calculations = {}

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self._definir_variables()
        self._creer_interface()
        self._mettre_a_jour_titre_fenetre()
        self.maj_statut("Interface initialisée - Prêt pour le dimensionnement.")
        self.after(100, self._dessiner_dalot_3d)

    def _definir_variables(self):
        # Projet
        self.nom_projet = tk.StringVar(value="Dalot - Nouveau projet")
        self.ingenieur = tk.StringVar(value="Kevindjoum")
        self.localisation = tk.StringVar(value="")
        self.date_projet = tk.StringVar(value="2025-08-31")
        
        # Géométrie
        self.largeur_dalot_m = tk.DoubleVar(value=3.0)
        self.hauteur_dalot_m = tk.DoubleVar(value=2.0)
        self.longueur_dalot_m = tk.DoubleVar(value=20.0)
        self.epaisseur_dalle_sup_m = tk.DoubleVar(value=0.30)
        self.epaisseur_dalle_inf_m = tk.DoubleVar(value=0.30)
        self.epaisseur_voile_lat_m = tk.DoubleVar(value=0.25)
        
        # Matériaux
        self.classe_beton = tk.StringVar(value="C30/37")
        self.classe_acier = tk.StringVar(value="B500B")
        self.classe_exposition = tk.StringVar(value="XC3 (Humidité modérée)")
        
        # Armatures
        self.diametre_principal = tk.StringVar(value="φ16")
        self.diametre_secondaire = tk.StringVar(value="φ12")
        self.espacement_barres_mm = tk.IntVar(value=150)
        
        # Charges
        self.classe_trafic = tk.StringVar(value="T2 (Véhicules légers)")
        self.type_remblai = tk.StringVar(value="Sable compacté")
        self.hauteur_remblai_m = tk.DoubleVar(value=1.5)
        
        # Options
        self.afficher_legendes = tk.BooleanVar(value=True)
        self.afficher_cotes = tk.BooleanVar(value=True)
        self.afficher_armatures = tk.BooleanVar(value=False)
        
        # Murs en aile
        self.aile_g_active = tk.BooleanVar(value=False)
        self.aile_d_active = tk.BooleanVar(value=False)
        self.aile_g_angle_deg = tk.DoubleVar(value=90.0)
        self.aile_d_angle_deg = tk.DoubleVar(value=90.0)
        self.aile_g_long_m = tk.DoubleVar(value=2.0)
        self.aile_d_long_m = tk.DoubleVar(value=2.0)
        self.aile_g_ep_m = tk.DoubleVar(value=0.25)
        self.aile_d_ep_m = tk.DoubleVar(value=0.25)
        self.aile_g_fruit_vh = tk.DoubleVar(value=0.0)
        self.aile_d_fruit_vh = tk.DoubleVar(value=0.0)
        self.aile_g_offset_m = tk.DoubleVar(value=0.0)
        self.aile_d_offset_m = tk.DoubleVar(value=0.0)
        
        # Paramètres sol et charges avancés
        self.sol_gamma_kN_m3 = tk.DoubleVar(value=20.0)
        self.sol_phi_deg = tk.DoubleVar(value=30.0)
        self.sol_c_kPa = tk.DoubleVar(value=0.0)
        self.sol_Ka_manuel = tk.StringVar(value="")  # Vide = calculé automatiquement
        self.sol_K0_manuel = tk.StringVar(value="")  # Vide = calculé automatiquement
        self.q_trafic_kN_m2 = tk.DoubleVar(value=5.0)
        self.q_perm_supp_kN_m2 = tk.DoubleVar(value=2.0)
        self.gamma_G = tk.DoubleVar(value=1.35)
        self.gamma_Q = tk.DoubleVar(value=1.5)
        self.psi0 = tk.DoubleVar(value=0.7)
        
        # Matériaux avancés (surcharges manuelles)
        self.fck_MPa = tk.StringVar(value="")  # Vide = utilise la classe
        self.gamma_c = tk.DoubleVar(value=1.5)
        self.alpha_cc = tk.DoubleVar(value=1.0)
        self.fyk_MPa = tk.StringVar(value="")  # Vide = utilise la classe  
        self.gamma_s = tk.DoubleVar(value=1.15)
        self.Es_MPa = tk.StringVar(value="")  # Vide = utilise la classe
        self.enrob_mm = tk.StringVar(value="")  # Vide = utilise la classe d'exposition
        self.wk_mm = tk.StringVar(value="")  # Vide = pas de vérification fissuration

    def _creer_interface(self):
        self._creer_menus()
        self._creer_barre_outils()
        self._creer_interface_principale()
        self._creer_barre_statut()

    def _creer_menus(self):
        barre_menu = tk.Menu(self)

        menu_fichier = tk.Menu(barre_menu, tearoff=0)
        menu_fichier.add_command(label="Nouveau", accelerator="Ctrl+N", command=self.action_nouveau)
        menu_fichier.add_command(label="Ouvrir...", accelerator="Ctrl+O", command=self.action_ouvrir)
        menu_fichier.add_command(label="Enregistrer", accelerator="Ctrl+S", command=self.action_enregistrer)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Exporter PDF...", command=self.cmd_exporter_pdf)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Quitter", command=self._avant_quitter)
        barre_menu.add_cascade(label="Fichier", menu=menu_fichier)

        menu_calcul = tk.Menu(barre_menu, tearoff=0)
        menu_calcul.add_command(label="Vérifier données", command=self.cmd_verifier_entrees)
        menu_calcul.add_command(label="Lancer calculs", command=self.cmd_lancer_calculs)
        menu_calcul.add_separator()
        menu_calcul.add_command(label="Optimiser sections", command=self.cmd_optimiser)
        barre_menu.add_cascade(label="Calcul", menu=menu_calcul)

        menu_vue = tk.Menu(barre_menu, tearoff=0)
        menu_vue.add_command(label="Vue de face", command=self.cmd_vue_face)
        menu_vue.add_command(label="Vue de côté", command=self.cmd_vue_cote)
        menu_vue.add_command(label="Vue de dessus", command=self.cmd_vue_dessus)
        menu_vue.add_command(label="Vue isométrique", command=self.cmd_vue_isometrique)
        barre_menu.add_cascade(label="Vue", menu=menu_vue)

        menu_aide = tk.Menu(barre_menu, tearoff=0)
        menu_aide.add_command(label="Manuel utilisateur", command=self.cmd_manuel)
        menu_aide.add_command(label="À propos", command=self.cmd_a_propos)
        barre_menu.add_cascade(label="Aide", menu=menu_aide)

        self.config(menu=barre_menu)
        
        # Raccourcis clavier
        self.bind_all("<Control-n>", lambda e: self.action_nouveau())
        self.bind_all("<Control-o>", lambda e: self.action_ouvrir())
        self.bind_all("<Control-s>", lambda e: self.action_enregistrer())

    def _creer_barre_outils(self):
        cadre = ttk.Frame(self, relief="raised", borderwidth=1)
        cadre.pack(side="top", fill="x")

        grp_fichier = ttk.LabelFrame(cadre, text="Fichier")
        grp_fichier.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_fichier, text="Nouveau", command=self.action_nouveau).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_fichier, text="Ouvrir", command=self.action_ouvrir).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_fichier, text="Enregistrer", command=self.action_enregistrer).pack(side="left", padx=2, pady=2)

        grp_calcul = ttk.LabelFrame(cadre, text="Calcul")
        grp_calcul.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_calcul, text="Vérifier", command=self.cmd_verifier_entrees).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_calcul, text="Calculer", command=self.cmd_lancer_calculs).pack(side="left", padx=2, pady=2)
        ttk.Button(grp_calcul, text="Actualiser 3D", command=self._dessiner_dalot_3d).pack(side="left", padx=2, pady=2)

        grp_vue = ttk.LabelFrame(cadre, text="Vues")
        grp_vue.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_vue, text="Face", command=self.cmd_vue_face).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vue, text="Côté", command=self.cmd_vue_cote).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vue, text="Dessus", command=self.cmd_vue_dessus).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vue, text="Iso", command=self.cmd_vue_isometrique).pack(side="left", padx=1, pady=2)

        self.barre_progression = ttk.Progressbar(cadre, mode="determinate", length=200)
        self.barre_progression.pack(side="right", padx=10, pady=5)

    def _creer_interface_principale(self):
        self.paned_principal = ttk.PanedWindow(self, orient="horizontal")
        self.paned_principal.pack(fill="both", expand=True, padx=5, pady=5)

        # Panneau gauche
        self.panneau_gauche = ttk.Frame(self.paned_principal)
        self.paned_principal.add(self.panneau_gauche, weight=1)

        self.notebook_gauche = ttk.Notebook(self.panneau_gauche)
        self.notebook_gauche.pack(fill="both", expand=True)

        self._creer_onglet_parametres()
        self._creer_onglet_resultats()

        # Panneau droit
        self.panneau_droit = ttk.Frame(self.paned_principal)
        self.paned_principal.add(self.panneau_droit, weight=2)

        self._creer_visualisation_3d()

    def _creer_onglet_parametres(self):
        cadre_parametres = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_parametres, text="📋 Paramètres")

        self.notebook_parametres = ttk.Notebook(cadre_parametres)
        self.notebook_parametres.pack(fill="both", expand=True, padx=5, pady=5)

        self._onglet_projet()
        self._onglet_geometrie()
        self._onglet_materiaux()
        self._onglet_charges()

    def _onglet_projet(self):
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="🏗️ Projet")

        grp = ttk.LabelFrame(cadre, text="Informations générales du projet")
        grp.pack(fill="x", padx=10, pady=10)

        self._ajouter_champ(grp, "Nom du projet:", self.nom_projet, 0, "Nom descriptif du projet")
        self._ajouter_champ(grp, "Ingénieur responsable:", self.ingenieur, 1, "Nom de l'ingénieur")
        self._ajouter_champ(grp, "Localisation:", self.localisation, 2, "Lieu d'implantation")
        self._ajouter_champ(grp, "Date:", self.date_projet, 3, "Date du projet")

    def _onglet_geometrie(self):
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="📐 Géométrie")

        grp_dim = ttk.LabelFrame(cadre, text="Dimensions principales du dalot")
        grp_dim.pack(fill="x", padx=10, pady=10)

        self._creer_combo_avec_unite(grp_dim, "Largeur intérieure:", self.largeur_dalot_m, 0, 
                                     DonneesNormalisees.LARGEURS_STANDARD, "m", "Largeur libre du dalot")
        self._creer_combo_avec_unite(grp_dim, "Hauteur intérieure:", self.hauteur_dalot_m, 1, 
                                     DonneesNormalisees.HAUTEURS_STANDARD, "m", "Hauteur libre du dalot")
        self._creer_combo_avec_unite(grp_dim, "Longueur totale:", self.longueur_dalot_m, 2, 
                                     DonneesNormalisees.LONGUEURS_STANDARD, "m", "Longueur totale entre têtes")

        grp_ep = ttk.LabelFrame(cadre, text="Épaisseurs des éléments structuraux")
        grp_ep.pack(fill="x", padx=10, pady=10)

        self._creer_combo_avec_unite(grp_ep, "Dalle supérieure:", self.epaisseur_dalle_sup_m, 0, 
                                     DonneesNormalisees.EPAISSEURS_DALLE, "m", "Épaisseur de la dalle de couverture")
        self._creer_combo_avec_unite(grp_ep, "Dalle inférieure:", self.epaisseur_dalle_inf_m, 1, 
                                     DonneesNormalisees.EPAISSEURS_DALLE, "m", "Épaisseur de la dalle de fond")
        self._creer_combo_avec_unite(grp_ep, "Voiles latéraux:", self.epaisseur_voile_lat_m, 2, 
                                     DonneesNormalisees.EPAISSEURS_VOILE, "m", "Épaisseur des murs latéraux")

        # Groupe Murs en aile
        grp_ailes = ttk.LabelFrame(cadre, text="Murs en aile")
        grp_ailes.pack(fill="x", padx=10, pady=10)

        # Aile gauche
        ttk.Label(grp_ailes, text="Aile gauche:", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(grp_ailes, text="Activer", variable=self.aile_g_active, 
                       command=self._dessiner_dalot_3d).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        ttk.Label(grp_ailes, text="Angle (°):").grid(row=1, column=1, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_g_angle_deg, width=8).grid(row=1, column=2, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Longueur (m):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_g_long_m, width=8).grid(row=2, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Épaisseur (m):").grid(row=2, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_g_ep_m, width=8).grid(row=2, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Fruit V/H:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_g_fruit_vh, width=8).grid(row=3, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Décalage tête (m):").grid(row=3, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_g_offset_m, width=8).grid(row=3, column=3, sticky="w", padx=2, pady=2)

        # Aile droite  
        ttk.Label(grp_ailes, text="Aile droite:", font=("TkDefaultFont", 9, "bold")).grid(row=4, column=0, columnspan=4, sticky="w", padx=5, pady=(10,2))
        ttk.Checkbutton(grp_ailes, text="Activer", variable=self.aile_d_active,
                       command=self._dessiner_dalot_3d).grid(row=5, column=0, sticky="w", padx=5, pady=2)
        
        ttk.Label(grp_ailes, text="Angle (°):").grid(row=5, column=1, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_d_angle_deg, width=8).grid(row=5, column=2, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Longueur (m):").grid(row=6, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_d_long_m, width=8).grid(row=6, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Épaisseur (m):").grid(row=6, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_d_ep_m, width=8).grid(row=6, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Fruit V/H:").grid(row=7, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_d_fruit_vh, width=8).grid(row=7, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_ailes, text="Décalage tête (m):").grid(row=7, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_ailes, textvariable=self.aile_d_offset_m, width=8).grid(row=7, column=3, sticky="w", padx=2, pady=2)

        # Bind events pour actualisation 3D
        for var in [self.aile_g_angle_deg, self.aile_g_long_m, self.aile_g_ep_m, self.aile_g_fruit_vh, self.aile_g_offset_m,
                   self.aile_d_angle_deg, self.aile_d_long_m, self.aile_d_ep_m, self.aile_d_fruit_vh, self.aile_d_offset_m]:
            var.trace('w', lambda *args: self.after(500, self._dessiner_dalot_3d))

    def _onglet_materiaux(self):
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="🧱 Matériaux")

        # Béton
        grp_beton = ttk.LabelFrame(cadre, text="Caractéristiques du béton")
        grp_beton.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_beton, text="Classe de béton:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_beton = ttk.Combobox(grp_beton, textvariable=self.classe_beton, width=20,
                                  values=list(DonneesNormalisees.CLASSES_BETON.keys()), state="readonly")
        combo_beton.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        combo_beton.bind("<<ComboboxSelected>>", self._maj_info_beton)
        
        self.info_beton = ttk.Label(grp_beton, text="", foreground="blue")
        self.info_beton.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self._maj_info_beton()
        
        # Surcharges manuelles béton
        ttk.Label(grp_beton, text="Surcharges manuelles (laisser vide pour utiliser la classe):", 
                 font=("TkDefaultFont", 8, "italic")).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(5,0))
        
        ttk.Label(grp_beton, text="fck (MPa):").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_beton, textvariable=self.fck_MPa, width=8).grid(row=3, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_beton, text="γc:").grid(row=3, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_beton, textvariable=self.gamma_c, width=8).grid(row=3, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_beton, text="αcc:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_beton, textvariable=self.alpha_cc, width=8).grid(row=4, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_beton, text="Enrobage (mm):").grid(row=4, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_beton, textvariable=self.enrob_mm, width=8).grid(row=4, column=3, sticky="w", padx=2, pady=2)

        # Acier
        grp_acier = ttk.LabelFrame(cadre, text="Caractéristiques de l'acier")
        grp_acier.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_acier, text="Classe d'acier:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_acier = ttk.Combobox(grp_acier, textvariable=self.classe_acier, width=20,
                                  values=list(DonneesNormalisees.CLASSES_ACIER.keys()), state="readonly")
        combo_acier.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        combo_acier.bind("<<ComboboxSelected>>", self._maj_info_acier)
        
        self.info_acier = ttk.Label(grp_acier, text="", foreground="blue")
        self.info_acier.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self._maj_info_acier()
        
        # Surcharges manuelles acier
        ttk.Label(grp_acier, text="Surcharges manuelles (laisser vide pour utiliser la classe):",
                 font=("TkDefaultFont", 8, "italic")).grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=(5,0))
        
        ttk.Label(grp_acier, text="fyk (MPa):").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_acier, textvariable=self.fyk_MPa, width=8).grid(row=3, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_acier, text="γs:").grid(row=3, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_acier, textvariable=self.gamma_s, width=8).grid(row=3, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_acier, text="Es (MPa):").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_acier, textvariable=self.Es_MPa, width=8).grid(row=4, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_acier, text="wk (mm):").grid(row=4, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_acier, textvariable=self.wk_mm, width=8).grid(row=4, column=3, sticky="w", padx=2, pady=2)

        # Exposition
        grp_expo = ttk.LabelFrame(cadre, text="Classe d'exposition (enrobage)")
        grp_expo.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_expo, text="Classe d'exposition:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_expo = ttk.Combobox(grp_expo, textvariable=self.classe_exposition, width=25,
                                 values=list(DonneesNormalisees.ENROBAGES_STANDARD.keys()), state="readonly")
        combo_expo.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        combo_expo.bind("<<ComboboxSelected>>", self._maj_info_exposition)
        
        self.info_exposition = ttk.Label(grp_expo, text="", foreground="blue")
        self.info_exposition.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self._maj_info_exposition()

    def _onglet_charges(self):
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="⚖️ Charges")

        grp_trafic = ttk.LabelFrame(cadre, text="Charges de trafic")
        grp_trafic.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_trafic, text="Classe de trafic:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_trafic = ttk.Combobox(grp_trafic, textvariable=self.classe_trafic, width=25,
                                   values=list(DonneesNormalisees.CLASSES_TRAFIC.keys()), state="readonly")
        combo_trafic.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        combo_trafic.bind("<<ComboboxSelected>>", self._maj_info_trafic)
        
        self.info_trafic = ttk.Label(grp_trafic, text="", foreground="blue")
        self.info_trafic.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self._maj_info_trafic()

        grp_remblai = ttk.LabelFrame(cadre, text="Charges de remblai")
        grp_remblai.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_remblai, text="Type de remblai:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_remblai = ttk.Combobox(grp_remblai, textvariable=self.type_remblai, width=20,
                                    values=list(DonneesNormalisees.TYPES_REMBLAI.keys()), state="readonly")
        combo_remblai.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        combo_remblai.bind("<<ComboboxSelected>>", self._maj_info_remblai)

        ttk.Label(grp_remblai, text="Hauteur de remblai:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        ttk.Combobox(grp_remblai, textvariable=self.hauteur_remblai_m, width=15,
                    values=DonneesNormalisees.HAUTEURS_REMBLAI).grid(row=1, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(grp_remblai, text="m").grid(row=1, column=2, sticky="w", padx=2, pady=4)

        self.info_remblai = ttk.Label(grp_remblai, text="", foreground="blue")
        self.info_remblai.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self._maj_info_remblai()

        # Groupe Propriétés du sol
        grp_sol = ttk.LabelFrame(cadre, text="Propriétés du sol (paramètres libres)")
        grp_sol.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(grp_sol, text="Poids volumique γsol (kN/m³):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_sol, textvariable=self.sol_gamma_kN_m3, width=8).grid(row=0, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_sol, text="Angle de frottement φ (°):").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_sol, textvariable=self.sol_phi_deg, width=8).grid(row=0, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_sol, text="Cohésion c (kPa):").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_sol, textvariable=self.sol_c_kPa, width=8).grid(row=1, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_sol, text="Ka manuel (facultatif):").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_sol, textvariable=self.sol_Ka_manuel, width=8).grid(row=2, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_sol, text="K0 manuel (facultatif):").grid(row=2, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_sol, textvariable=self.sol_K0_manuel, width=8).grid(row=2, column=3, sticky="w", padx=2, pady=2)

        # Groupe Charges supplémentaires
        grp_charges_supp = ttk.LabelFrame(cadre, text="Charges supplémentaires et combinaisons")
        grp_charges_supp.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(grp_charges_supp, text="Surcharge trafic q (kN/m²):").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_charges_supp, textvariable=self.q_trafic_kN_m2, width=8).grid(row=0, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_charges_supp, text="Surcharge perm. supp. (kN/m²):").grid(row=0, column=2, sticky="e", padx=5, pady=2)  
        ttk.Entry(grp_charges_supp, textvariable=self.q_perm_supp_kN_m2, width=8).grid(row=0, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_charges_supp, text="Facteurs de combinaison:", 
                 font=("TkDefaultFont", 9, "bold")).grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(10,2))
                 
        ttk.Label(grp_charges_supp, text="γG:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_charges_supp, textvariable=self.gamma_G, width=6).grid(row=2, column=1, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_charges_supp, text="γQ:").grid(row=2, column=2, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_charges_supp, textvariable=self.gamma_Q, width=6).grid(row=2, column=3, sticky="w", padx=2, pady=2)
        
        ttk.Label(grp_charges_supp, text="ψ0:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(grp_charges_supp, textvariable=self.psi0, width=6).grid(row=3, column=1, sticky="w", padx=2, pady=2)

    def _creer_onglet_resultats(self):
        cadre_resultats = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_resultats, text="📊 Résultats")

        notebook_resultats = ttk.Notebook(cadre_resultats)
        notebook_resultats.pack(fill="both", expand=True, padx=5, pady=5)

        # Rapport
        cadre_rapport = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_rapport, text="📋 Rapport")
        
        self.zone_calculs = ScrolledText(cadre_rapport, height=20, wrap="word", font=("Consolas", 9))
        self.zone_calculs.pack(fill="both", expand=True, padx=5, pady=5)

        # Vérifications
        cadre_verif = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_verif, text="✅ Vérifications")
        
        self.zone_verifications = ScrolledText(cadre_verif, height=20, wrap="word", font=("Consolas", 9))
        self.zone_verifications.pack(fill="both", expand=True, padx=5, pady=5)

        # Journal
        cadre_journal = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_journal, text="📝 Journal")
        
        self.zone_journal = ScrolledText(cadre_journal, height=20, wrap="word", font=("Consolas", 9))
        self.zone_journal.pack(fill="both", expand=True, padx=5, pady=5)

        # Boutons
        cadre_btn = ttk.Frame(cadre_resultats)
        cadre_btn.pack(side="bottom", fill="x", padx=5, pady=5)
        
        ttk.Button(cadre_btn, text="📋 Copier rapport", command=self.cmd_copier_resultats).pack(side="left", padx=5)
        ttk.Button(cadre_btn, text="💾 Exporter PDF", command=self.cmd_exporter_pdf).pack(side="left", padx=5)
        ttk.Button(cadre_btn, text="🗑️ Effacer", command=self._effacer_resultats).pack(side="left", padx=5)

    def _creer_visualisation_3d(self):
        cadre_3d = ttk.LabelFrame(self.panneau_droit, text="🎯 Visualisation 3D Interactive du Dalot")
        cadre_3d.pack(fill="both", expand=True, padx=5, pady=5)

        # Contrôles rapides
        cadre_controles = ttk.Frame(cadre_3d)
        cadre_controles.pack(fill="x", padx=5, pady=5)

        ligne1 = ttk.Frame(cadre_controles)
        ligne1.pack(fill="x", pady=2)

        # Entrées de géométrie avec mise à jour automatique
        ttk.Label(ligne1, text="L:").pack(side="left", padx=2)
        entry_l = ttk.Entry(ligne1, textvariable=self.longueur_dalot_m, width=6)
        entry_l.pack(side="left", padx=2)
        entry_l.bind("<KeyRelease>", lambda e: self.after(500, self._dessiner_dalot_3d))

        ttk.Label(ligne1, text="l:").pack(side="left", padx=(10,2))
        entry_largeur = ttk.Entry(ligne1, textvariable=self.largeur_dalot_m, width=6)
        entry_largeur.pack(side="left", padx=2)
        entry_largeur.bind("<KeyRelease>", lambda e: self.after(500, self._dessiner_dalot_3d))

        ttk.Label(ligne1, text="H:").pack(side="left", padx=(10,2))
        entry_h = ttk.Entry(ligne1, textvariable=self.hauteur_dalot_m, width=6)
        entry_h.pack(side="left", padx=2)
        entry_h.bind("<KeyRelease>", lambda e: self.after(500, self._dessiner_dalot_3d))

        ttk.Button(ligne1, text="🔄 Actualiser", command=self._dessiner_dalot_3d).pack(side="left", padx=10)

        # Options d'affichage
        ligne2 = ttk.Frame(cadre_controles)
        ligne2.pack(fill="x", pady=2)

        ttk.Checkbutton(ligne2, text="📋 Légendes", variable=self.afficher_legendes, 
                       command=self._dessiner_dalot_3d).pack(side="left", padx=5)
        ttk.Checkbutton(ligne2, text="📏 Cotes", variable=self.afficher_cotes, 
                       command=self._dessiner_dalot_3d).pack(side="left", padx=5)
        ttk.Checkbutton(ligne2, text="🔧 Armatures", variable=self.afficher_armatures, 
                       command=self._dessiner_dalot_3d).pack(side="left", padx=5)

        # Figure matplotlib 3D
        self.figure_3d = plt.figure(figsize=(12, 9))
        self.ax_3d = self.figure_3d.add_subplot(111, projection='3d')
        
        self.canvas_3d = FigureCanvasTkAgg(self.figure_3d, cadre_3d)
        self.canvas_3d.get_tk_widget().pack(fill="both", expand=True)
        
        self.toolbar_3d = NavigationToolbar2Tk(self.canvas_3d, cadre_3d)
        self.toolbar_3d.update()
        
        # Événements
        self.canvas_3d.mpl_connect("scroll_event", self._on_scroll_zoom)
        self.canvas_3d.mpl_connect("pick_event", self._on_pick_face)

    def _creer_barre_statut(self):
        cadre_statut = ttk.Frame(self, relief="sunken", borderwidth=1)
        cadre_statut.pack(side="bottom", fill="x")
        
        self.libelle_statut = ttk.Label(cadre_statut, text="Prêt pour le dimensionnement", anchor="w")
        self.libelle_statut.pack(side="left", padx=5, pady=3)

        self.label_dimensions = ttk.Label(cadre_statut, text="", anchor="e")
        self.label_dimensions.pack(side="right", padx=5, pady=3)

    def maj_statut(self, texte: str, progression: int = 0):
        self.libelle_statut.config(text=texte)
        if 0 <= progression <= 100:
            self.barre_progression.config(value=progression)
        
        # Mise à jour des dimensions dans la barre de statut
        try:
            L = self.longueur_dalot_m.get()
            l = self.largeur_dalot_m.get()
            h = self.hauteur_dalot_m.get()
            self.label_dimensions.config(text=f"L={L:.1f}m × l={l:.1f}m × H={h:.1f}m")
        except:
            self.label_dimensions.config(text="Dimensions: N/A")
        
        self.update_idletasks()

    # Méthodes utilitaires
    def _ajouter_champ(self, parent, texte_label, var, ligne: int, info: str = ""):
        ttk.Label(parent, text=texte_label).grid(row=ligne, column=0, sticky="e", padx=5, pady=4)
        entree = ttk.Entry(parent, textvariable=var)
        entree.grid(row=ligne, column=1, sticky="we", padx=5, pady=4)
        parent.columnconfigure(1, weight=1)
        if info:
            Infobulle(entree, info)
        entree.bind("<KeyRelease>", lambda e: self._marquer_modifie())

    def _creer_combo_avec_unite(self, parent, texte_label, var, ligne, values, unite, info=""):
        ttk.Label(parent, text=texte_label).grid(row=ligne, column=0, sticky="e", padx=5, pady=4)
        combo = ttk.Combobox(parent, textvariable=var, width=15, values=values)
        combo.grid(row=ligne, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(parent, text=unite).grid(row=ligne, column=2, sticky="w", padx=2, pady=4)
        if info:
            Infobulle(combo, info)
        combo.bind("<<ComboboxSelected>>", lambda e: self._dessiner_dalot_3d())
        combo.bind("<KeyRelease>", lambda e: self.after(500, self._dessiner_dalot_3d))

    # Méthodes de mise à jour des informations
    def _maj_info_beton(self, event=None):
        classe = self.classe_beton.get()
        if classe in DonneesNormalisees.CLASSES_BETON:
            info = DonneesNormalisees.CLASSES_BETON[classe]
            self.info_beton.config(text=f"fck = {info['fck']} MPa, fcd = {info['fcd']} MPa - {info['description']}")

    def _maj_info_acier(self, event=None):
        classe = self.classe_acier.get()
        if classe in DonneesNormalisees.CLASSES_ACIER:
            info = DonneesNormalisees.CLASSES_ACIER[classe]
            self.info_acier.config(text=f"fyk = {info['fyk']} MPa, fyd = {info['fyd']} MPa - {info['description']}")

    def _maj_info_exposition(self, event=None):
        classe = self.classe_exposition.get()
        if classe in DonneesNormalisees.ENROBAGES_STANDARD:
            info = DonneesNormalisees.ENROBAGES_STANDARD[classe]
            self.info_exposition.config(text=f"Enrobage min. = {info['valeur']} mm - {info['description']}")

    def _maj_info_trafic(self, event=None):
        classe = self.classe_trafic.get()
        if classe in DonneesNormalisees.CLASSES_TRAFIC:
            info = DonneesNormalisees.CLASSES_TRAFIC[classe]
            self.info_trafic.config(text=f"Charge = {info['charge']} kN/m² - {info['description']}")

    def _maj_info_remblai(self, event=None):
        type_rem = self.type_remblai.get()
        if type_rem in DonneesNormalisees.TYPES_REMBLAI:
            info = DonneesNormalisees.TYPES_REMBLAI[type_rem]
            self.info_remblai.config(text=f"Densité = {info['densite']} kN/m³, Angle = {info['angle']}° - {info['description']}")

    # Méthodes de visualisation 3D
    def _dessiner_dalot_3d(self):
        try:
            self.ax_3d.clear()
            self.ax_3d.set_facecolor('#F5F5F5')

            self.selected_face = None
            self.original_face_colors = {}
            self.face_properties = {}

            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle_sup = float(self.epaisseur_dalle_sup_m.get())
            e_dalle_inf = float(self.epaisseur_dalle_inf_m.get())

            if L <= 0 or l <= 0 or h <= 0 or e_mur <= 0 or e_dalle_sup <= 0 or e_dalle_inf <= 0:
                raise ValueError("Toutes les dimensions doivent être positives")

            if e_mur >= l/2 or (e_dalle_sup + e_dalle_inf) >= h:
                raise ValueError("Épaisseurs trop importantes")

            # Dessiner les éléments avec de meilleures couleurs
            self._dessiner_element_3d(0, L, 0, l, 0, e_dalle_inf, '#D3D3D3', 'Dalle de fond')
            self._dessiner_element_3d(0, L, 0, l, h-e_dalle_sup, h, '#87CEEB', 'Dalle de couverture')
            self._dessiner_element_3d(0, L, 0, e_mur, e_dalle_inf, h-e_dalle_sup, '#F08080', 'Mur gauche')
            self._dessiner_element_3d(0, L, l-e_mur, l, e_dalle_inf, h-e_dalle_sup, '#F08080', 'Mur droit')
            
            # Ouvertures avec meilleur style
            self._dessiner_ouvertures(L, l, h, e_mur, e_dalle_inf, e_dalle_sup)
            
            # Dessiner les murs en aile
            max_wing_length = 0
            if self.aile_g_active.get():
                max_wing_length = max(max_wing_length, self._dessiner_mur_en_aile('gauche', L, l, h, e_dalle_inf, e_dalle_sup))
            if self.aile_d_active.get():
                max_wing_length = max(max_wing_length, self._dessiner_mur_en_aile('droite', L, l, h, e_dalle_inf, e_dalle_sup))
            
            # Configuration avancée
            self.ax_3d.set_xlabel('Longueur (m)', fontweight='bold')
            self.ax_3d.set_ylabel('Largeur (m)', fontweight='bold')
            self.ax_3d.set_zlabel('Hauteur (m)', fontweight='bold')
            self.ax_3d.set_title(f'🏗️ Dalot 3D - L:{L:.1f}m × l:{l:.1f}m × H:{h:.1f}m', fontsize=14, fontweight='bold')
            
            # Limites optimisées (prendre en compte les ailes)
            margin = 0.15
            y_max = max(l, max_wing_length) if max_wing_length > 0 else l
            self.ax_3d.set_xlim(-L*margin, L*(1+margin))
            self.ax_3d.set_ylim(-y_max*margin, y_max*(1+margin))
            self.ax_3d.set_zlim(0, h*(1+margin))
            
            # Proportions correctes
            max_dim = max(L, y_max, h)
            self.ax_3d.set_box_aspect([L/max_dim, y_max/max_dim, h/max_dim])
            
            # Grille et style
            self.ax_3d.grid(True, alpha=0.3)
            self.ax_3d.xaxis._axinfo["grid"]['color'] = "#E0E0E0"
            self.ax_3d.yaxis._axinfo["grid"]['color'] = "#E0E0E0"
            self.ax_3d.zaxis._axinfo["grid"]['color'] = "#E0E0E0"
            
            if self.afficher_legendes.get():
                self.ax_3d.legend(loc='upper left', fontsize=10)
            
            if self.afficher_cotes.get():
                self._ajouter_cotes_3d(L, l, h)
            
            # Vue isométrique par défaut
            self.ax_3d.view_init(elev=20, azim=45)
            
            self.canvas_3d.draw()
            
            # Mise à jour du statut avec les nouvelles dimensions
            self.maj_statut("Dalot 3D actualisé")
            
            # Lancer calculs en arrière-plan
            self.after(200, self._lancer_calculs_automatique)
            
        except Exception as e:
            messagebox.showerror("Erreur 3D", f"Erreur lors du rendu 3D:\n{str(e)}")
            self.journaliser(f"Erreur 3D: {str(e)}")

    def _dessiner_element_3d(self, x_min, x_max, y_min, y_max, z_min, z_max, couleur, nom):
        vertices = self._creer_sommets_boite(x_min, x_max, y_min, y_max, z_min, z_max)
        faces = self._creer_faces_boite(vertices)

        face_names = ["Inférieure", "Supérieure", "Avant", "Arrière", "Droite", "Gauche"]

        for i, face in enumerate(faces):
            collection = Poly3DCollection([face], alpha=0.8, facecolor=couleur, 
                                        edgecolor='#333333', linewidth=1.0, picker=True)
            self.ax_3d.add_collection3d(collection)
            
            self.original_face_colors[collection] = collection.get_facecolor()
            self.face_properties[collection] = {
                'name': f"{nom} - Face {face_names[i]}",
                'info': f"Élément: {nom}",
                'element_type': nom.lower().replace(' ', '_')
            }

    def _creer_sommets_boite(self, x_min, x_max, y_min, y_max, z_min, z_max):
        return np.array([
            [x_min, y_min, z_min], [x_max, y_min, z_min], [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_max], [x_max, y_min, z_max], [x_max, y_max, z_max], [x_min, y_max, z_max]
        ])

    def _creer_faces_boite(self, vertices):
        faces_indices = [
            [0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], 
            [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]
        ]
        return [[vertices[i] for i in face] for face in faces_indices]

    def _dessiner_ouvertures(self, L, l, h, e_mur, e_dalle_inf, e_dalle_sup):
        # Ouverture entrée (rouge)
        ouv_y = np.array([e_mur, l-e_mur, l-e_mur, e_mur, e_mur])
        ouv_z = np.array([e_dalle_inf, e_dalle_inf, h-e_dalle_sup, h-e_dalle_sup, e_dalle_inf])
        ouv_x_entree = np.zeros_like(ouv_y)
        self.ax_3d.plot(ouv_x_entree, ouv_y, ouv_z, color='#FF4500', linewidth=5, label='🔴 Entrée', alpha=0.9)
        
        # Ouverture sortie (verte)
        ouv_x_sortie = np.full_like(ouv_y, L)
        self.ax_3d.plot(ouv_x_sortie, ouv_y, ouv_z, color='#32CD32', linewidth=5, label='🟢 Sortie', alpha=0.9)
        
        # Ligne d'écoulement (bleue)
        x_eau = np.linspace(0, L, 30)
        y_eau = np.full_like(x_eau, l/2)
        z_eau = np.full_like(x_eau, e_dalle_inf + 0.05)
        self.ax_3d.plot(x_eau, y_eau, z_eau, color='#4169E1', linewidth=4, alpha=0.7, label='💧 Écoulement')

        # Flèches directionnelles
        if L > 5:  # Seulement si assez long
            # Flèche entrée
            self.ax_3d.quiver(-L*0.1, l/2, (h/2), L*0.08, 0, 0, color='red', alpha=0.8, arrow_length_ratio=0.3)
            # Flèche sortie
            self.ax_3d.quiver(L*1.02, l/2, (h/2), L*0.08, 0, 0, color='green', alpha=0.8, arrow_length_ratio=0.3)

    def _dessiner_mur_en_aile(self, cote, L, l, h, e_dalle_inf, e_dalle_sup):
        """Dessine un mur en aile à la tête x=0 avec paramètres géométriques"""
        
        if cote == 'gauche':
            active = self.aile_g_active.get()
            angle_deg = self.aile_g_angle_deg.get()
            longueur = self.aile_g_long_m.get()
            epaisseur = self.aile_g_ep_m.get()
            fruit_vh = self.aile_g_fruit_vh.get()
            offset = self.aile_g_offset_m.get()
            y_base = 0  # Côté gauche commence à y=0
            couleur = '#FFB6C1'  # Rose clair pour aile gauche
            nom = 'Aile gauche'
        else:  # droite
            active = self.aile_d_active.get()
            angle_deg = self.aile_d_angle_deg.get()
            longueur = self.aile_d_long_m.get()
            epaisseur = self.aile_d_ep_m.get() 
            fruit_vh = self.aile_d_fruit_vh.get()
            offset = self.aile_d_offset_m.get()
            y_base = l  # Côté droit commence à y=l
            couleur = '#DDA0DD'  # Prune clair pour aile droite
            nom = 'Aile droite'
        
        if not active or longueur <= 0 or epaisseur <= 0:
            return 0
        
        # Conversion angle en radians et calcul direction
        angle_rad = np.radians(angle_deg)
        h_apparent = h - e_dalle_inf - e_dalle_sup
        
        # Points de base du mur en aile (au niveau du radier + e_dalle_inf)
        x_base = 0  # Tête du dalot
        
        if cote == 'gauche':
            # Direction normale vers l'extérieur côté gauche 
            dir_y = -np.cos(angle_rad) * longueur  # Vers y négatif
            dir_x = np.sin(angle_rad) * longueur
        else:
            # Direction normale vers l'extérieur côté droit
            dir_y = np.cos(angle_rad) * longueur  # Vers y positif  
            dir_x = np.sin(angle_rad) * longueur
        
        # Points aux 4 coins de la base du mur
        if cote == 'gauche':
            # Pour aile gauche: s'étendre vers l'extérieur depuis y=0
            p1_base = [x_base, y_base, e_dalle_inf]
            p2_base = [x_base + dir_x, y_base + dir_y, e_dalle_inf]
            p3_base = [x_base + dir_x, y_base + dir_y - epaisseur, e_dalle_inf]  
            p4_base = [x_base, y_base - epaisseur, e_dalle_inf]
        else:
            # Pour aile droite: s'étendre vers l'extérieur depuis y=l
            p1_base = [x_base, y_base, e_dalle_inf]
            p2_base = [x_base + dir_x, y_base + dir_y, e_dalle_inf]
            p3_base = [x_base + dir_x, y_base + dir_y + epaisseur, e_dalle_inf]
            p4_base = [x_base, y_base + epaisseur, e_dalle_inf]
        
        # Points au sommet avec fruit et décalage
        z_top = h - e_dalle_sup
        fruit_offset_x = fruit_vh * h_apparent
        
        p1_top = [p1_base[0] + fruit_offset_x + offset, p1_base[1], z_top]
        p2_top = [p2_base[0] + fruit_offset_x + offset, p2_base[1], z_top] 
        p3_top = [p3_base[0] + fruit_offset_x + offset, p3_base[1], z_top]
        p4_top = [p4_base[0] + fruit_offset_x + offset, p4_base[1], z_top]
        
        # Créer les 6 faces du mur en aile (comme un hexaèdre)
        faces = [
            [p1_base, p2_base, p3_base, p4_base],  # Face inférieure
            [p1_top, p4_top, p3_top, p2_top],     # Face supérieure  
            [p1_base, p1_top, p2_top, p2_base],   # Face avant
            [p3_base, p2_base, p2_top, p3_top],   # Face extérieure
            [p4_base, p3_base, p3_top, p4_top],   # Face arrière
            [p1_base, p4_base, p4_top, p1_top]    # Face intérieure (côté dalot)
        ]
        
        face_names = ["Inférieure", "Supérieure", "Avant", "Extérieure", "Arrière", "Intérieure"]
        
        # Ajouter les faces à la scène 3D
        for i, face in enumerate(faces):
            collection = Poly3DCollection([face], alpha=0.7, facecolor=couleur, 
                                        edgecolor='#333333', linewidth=1.0, picker=True)
            self.ax_3d.add_collection3d(collection)
            
            self.original_face_colors[collection] = collection.get_facecolor()
            self.face_properties[collection] = {
                'name': f"{nom} - Face {face_names[i]}",
                'info': f"Mur en aile {cote}",
                'element_type': f'aile_{cote}',
                'angle_deg': angle_deg,
                'longueur_m': longueur,
                'epaisseur_m': epaisseur,
                'fruit_vh': fruit_vh,
                'offset_m': offset
            }
        
        # Retourner la portée maximale en Y pour ajuster les limites
        if cote == 'gauche':
            return max(abs(y_base + dir_y), abs(y_base + dir_y - epaisseur))
        else:
            return max(abs(y_base + dir_y), abs(y_base + dir_y + epaisseur))

    def _ajouter_cotes_3d(self, L, l, h):
        offset = 0.12
        # Cotes avec style amélioré
        self.ax_3d.text(L/2, -offset*l, -offset*h, f'L = {L:.1f} m', 
                       fontsize=11, ha='center', color='#2E4057', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        self.ax_3d.text(-offset*L, l/2, -offset*h, f'l = {l:.1f} m', 
                       fontsize=11, ha='center', color='#2E4057', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
        self.ax_3d.text(-offset*L, -offset*l, h/2, f'H = {h:.1f} m', 
                       fontsize=11, ha='center', color='#2E4057', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))

    # Événements 3D
    def _on_scroll_zoom(self, event):
        if event.inaxes == self.ax_3d:
            current_xlim = self.ax_3d.get_xlim3d()
            current_ylim = self.ax_3d.get_ylim3d()
            current_zlim = self.ax_3d.get_zlim3d()

            x_center = (current_xlim[0] + current_xlim[1]) / 2
            y_center = (current_ylim[0] + current_ylim[1]) / 2
            z_center = (current_zlim[0] + current_zlim[1]) / 2

            if event.button == 'up':
                zoom_factor = 1 / self.zoom_factor
            elif event.button == 'down':
                zoom_factor = self.zoom_factor
            else:
                return

            new_xlim = (x_center - (x_center - current_xlim[0]) * zoom_factor,
                       x_center + (current_xlim[1] - x_center) * zoom_factor)
            new_ylim = (y_center - (y_center - current_ylim[0]) * zoom_factor,
                       y_center + (current_ylim[1] - y_center) * zoom_factor)
            new_zlim = (z_center - (z_center - current_zlim[0]) * zoom_factor,
                       z_center + (current_zlim[1] - z_center) * zoom_factor)

            self.ax_3d.set_xlim3d(new_xlim)
            self.ax_3d.set_ylim3d(new_ylim)
            self.ax_3d.set_zlim3d(new_zlim)
            self.canvas_3d.draw_idle()

    def _on_pick_face(self, event):
        if not isinstance(event.artist, Poly3DCollection):
            return

        # Désélectionner la face précédente
        if self.selected_face:
            self.selected_face.set_facecolor(self.original_face_colors[self.selected_face])

        # Sélectionner la nouvelle face
        self.selected_face = event.artist
        if self.selected_face not in self.original_face_colors:
            self.original_face_colors[self.selected_face] = self.selected_face.get_facecolor()

        self.selected_face.set_facecolor('#FF69B4')  # Rose vif pour la sélection
        self.canvas_3d.draw_idle()

        # Afficher les informations
        if self.selected_face in self.face_properties:
            face_info = self.face_properties[self.selected_face]
            self._afficher_info_face(face_info)

    def _afficher_info_face(self, face_info):
        info_text = f"\n{'='*50}\n"
        info_text += f"🎯 FACE SÉLECTIONNÉE\n"
        info_text += f"{'='*50}\n"
        info_text += f"📋 Nom: {face_info['name']}\n"
        info_text += f"ℹ️  Info: {face_info['info']}\n"
        
        element_type = face_info.get('element_type', '')
        
        # Informations détaillées selon le type d'élément
        if 'dalle_de_couverture' in element_type and self.dalot_calculations:
            if 'ferraillage_dalle_couverture' in self.dalot_calculations:
                ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
                armatures = self.dalot_calculations.get('armatures_dalle_choisies', {})
                
                info_text += f"\n🔧 CALCULS DALLE DE COUVERTURE\n"
                info_text += f"{'─'*30}\n"
                if 'moment_ELU' in ferraillage:
                    info_text += f"📊 Moment ELU: {ferraillage['moment_ELU']:.2f} Nm/m\n"
                    info_text += f"🔩 As théorique: {ferraillage['As_theorique']*1e4:.2f} cm²/m\n"
                    if armatures:
                        info_text += f"🛠️  Armatures choisies: φ{armatures.get('diametre', 'N/A')} e={armatures.get('espacement', 'N/A')}cm\n"
                        info_text += f"✅ As fourni: {armatures.get('As_fourni', 0)*1e4:.2f} cm²/m\n"
        
        elif 'mur' in element_type and self.dalot_calculations:
            if 'effort_normal_mur' in self.dalot_calculations:
                effort = self.dalot_calculations['effort_normal_mur']
                info_text += f"\n🏗️  CALCULS MUR LATÉRAL\n"
                info_text += f"{'─'*25}\n"
                info_text += f"⚡ Effort normal: {effort.get('valeur', 0):.2f} N/m\n"
        
        # Informations spécifiques aux murs en aile
        elif element_type.startswith('aile_'):
            info_text += f"\n🏛️ PARAMÈTRES MUR EN AILE\n"
            info_text += f"{'─'*30}\n"
            info_text += f"📐 Angle en plan: {face_info.get('angle_deg', 'N/A'):.0f}°\n"
            info_text += f"📏 Longueur: {face_info.get('longueur_m', 'N/A'):.2f} m\n"
            info_text += f"📐 Épaisseur: {face_info.get('epaisseur_m', 'N/A'):.2f} m\n"
            info_text += f"🔽 Fruit V/H: {face_info.get('fruit_vh', 'N/A'):.2f}\n"
            info_text += f"↕️  Décalage tête: {face_info.get('offset_m', 'N/A'):.2f} m\n"
            
            if self.dalot_calculations and 'poussee_terres' in self.dalot_calculations:
                poussee = self.dalot_calculations['poussee_terres']
                info_text += f"\n🌍 POUSSÉE ASSOCIÉE\n"
                info_text += f"{'─'*20}\n"
                info_text += f"💨 Force poussée: {poussee.get('force_poussee_par_metre', 0):.0f} N/m\n"
                info_text += f"📍 Point application: {poussee.get('point_application_hauteur', 0):.2f} m\n"
                
                armatures_mur = self.dalot_calculations.get('armatures_mur_choisies', {})
                if armatures_mur:
                    info_text += f"🔩 Armatures: φ{armatures_mur.get('diametre', 'N/A')} e={armatures_mur.get('espacement', 'N/A')}cm\n"
        
        info_text += f"\n{'='*50}\n"
        
                # Afficher dans la zone de rapport
        self.zone_calculs.insert(tk.END, info_text)
        self.zone_calculs.see(tk.END)
        self.journaliser(f"Face sélectionnée: {face_info['name']}")

    # Calculs
    def _lancer_calculs_automatique(self):
        """Lance rapidement les calculs après une mise à jour de géométrie"""
        try:
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle = float(self.epaisseur_dalle_sup_m.get())
            
            # Préparer les paramètres utilisateur
            params = {
                'sol_gamma_kN_m3': self.sol_gamma_kN_m3.get(),
                'sol_phi_deg': self.sol_phi_deg.get(),
                'sol_c_kPa': self.sol_c_kPa.get(),
                'sol_Ka_manuel': self.sol_Ka_manuel.get(),
                'sol_K0_manuel': self.sol_K0_manuel.get(),
                'q_trafic_kN_m2': self.q_trafic_kN_m2.get(),
                'q_perm_supp_kN_m2': self.q_perm_supp_kN_m2.get(),
                'gamma_G': self.gamma_G.get(),
                'gamma_Q': self.gamma_Q.get(),
                'fck_MPa': self.fck_MPa.get(),
                'gamma_c': self.gamma_c.get(),
                'alpha_cc': self.alpha_cc.get(),
                'fyk_MPa': self.fyk_MPa.get(),
                'gamma_s': self.gamma_s.get(),
                'Es_MPa': self.Es_MPa.get(),
                'enrob_mm': self.enrob_mm.get(),
                'wk_mm': self.wk_mm.get()
            }
            
            self.dalot_calculations = SimulationCalculs.analyser_dalot(L, l, h, e_mur, e_dalle, params)
            self._mettre_a_jour_verifications()
        except Exception as e:
            self.dalot_calculations = {'erreur': str(e)}
            self.journaliser(f"Erreur calcul automatique: {str(e)}")

    def _mettre_a_jour_verifications(self):
        """Affiche un petit bilan des vérifications dans l'onglet Vérifications"""
        self.zone_verifications.delete("1.0", tk.END)
        lignes = []
        try:
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle_sup = float(self.epaisseur_dalle_sup_m.get())
            e_dalle_inf = float(self.epaisseur_dalle_inf_m.get())

            ok = True
            if L <= 0 or l <= 0 or h <= 0:
                ok = False
                lignes.append("❌ Dimensions L, l, H doivent être > 0")
            if e_mur <= 0 or e_dalle_sup <= 0 or e_dalle_inf <= 0:
                ok = False
                lignes.append("❌ Épaisseurs doivent être > 0")
            if e_mur >= l/2:
                ok = False
                lignes.append("❌ e_mur ≥ l/2 (trop épais)")
            if (e_dalle_sup + e_dalle_inf) >= h:
                ok = False
                lignes.append("❌ e_dalles ≥ H (trop épais)")

            if ok:
                lignes.append("✅ Géométrie cohérente")
            else:
                lignes.append("⚠️  Géométrie incohérente")

            if 'erreur' in self.dalot_calculations:
                lignes.append(f"❌ Erreur calcul: {self.dalot_calculations['erreur']}")
            else:
                lignes.append("✅ Calculs automatiques réalisés")

        except Exception as e:
            lignes.append(f"❌ Erreur vérifications: {str(e)}")

        self.zone_verifications.insert("1.0", "\n".join(lignes))
        self.zone_verifications.see(tk.END)

    # Commandes principales
    def cmd_verifier_entrees(self):
        """Vérification des données avec messages explicites"""
        try:
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle_sup = float(self.epaisseur_dalle_sup_m.get())
            e_dalle_inf = float(self.epaisseur_dalle_inf_m.get())

            erreurs = []
            if L <= 0 or l <= 0 or h <= 0:
                erreurs.append("• L, l, H doivent être strictement positifs.")
            if e_mur <= 0 or e_dalle_sup <= 0 or e_dalle_inf <= 0:
                erreurs.append("• Les épaisseurs doivent être strictement positives.")
            if e_mur >= l/2:
                erreurs.append("• Épaisseur des murs trop importante (e_mur ≥ l/2).")
            if (e_dalle_sup + e_dalle_inf) >= h:
                erreurs.append("• Somme des épaisseurs de dalles ≥ H.")

            if erreurs:
                messagebox.showerror("Vérification des données - Échecs", "\n".join(erreurs))
                self.journaliser("Vérification: ÉCHEC")
                return

            messagebox.showinfo("Vérification des données", "✓ Toutes les données sont valides !")
            self.journaliser("Vérification des données: OK")
            self._mettre_a_jour_verifications()
            self.maj_statut("Données vérifiées avec succès.")
        except Exception as e:
            messagebox.showerror("Erreur de validation", f"❌ Erreur: {str(e)}")
            self.journaliser(f"Erreur de validation: {str(e)}")

    def cmd_lancer_calculs(self):
        """Lance les calculs complets et génère le rapport"""
        self.journaliser("Début des calculs de dimensionnement...")
        self.maj_statut("Calculs en cours...", 10)
        try:
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle = float(self.epaisseur_dalle_sup_m.get())

            self.maj_statut("Analyse structurelle...", 40)
            self.dalot_calculations = SimulationCalculs.analyser_dalot(L, l, h, e_mur, e_dalle)

            self.maj_statut("Génération du rapport...", 75)
            if 'erreur' in self.dalot_calculations:
                rapport = f"ERREUR LORS DES CALCULS\n{self.dalot_calculations['erreur']}"
            else:
                rapport = self._generer_rapport_complet()

            self.zone_calculs.delete("1.0", tk.END)
            self.zone_calculs.insert("1.0", rapport)
            self.zone_calculs.see(tk.END)

            self._mettre_a_jour_verifications()
            self.maj_statut("Calculs terminés ✓", 100)
            self.journaliser("Calculs de dimensionnement terminés")
        except Exception as e:
            messagebox.showerror("Erreur de calcul", f"Erreur: {str(e)}")
            self.journaliser(f"Erreur de calcul: {str(e)}")
            self.maj_statut("Erreur lors des calculs", 0)

    def _generer_rapport_complet(self):
        """Construit un rapport texte lisible à partir des résultats"""
        lignes = []
        lignes.append("===== RAPPORT DE DIMENSIONNEMENT DALOT (Enrichi) =====")
        lignes.append(f"Projet: {self.nom_projet.get()} | Ingénieur: {self.ingenieur.get() or 'N/A'} | Date: {self.date_projet.get()}")
        lignes.append("")
        lignes.append("GÉOMÉTRIE")
        lignes.append(f"- Largeur intérieure l = {self.largeur_dalot_m.get():.2f} m")
        lignes.append(f"- Hauteur intérieure H = {self.hauteur_dalot_m.get():.2f} m")
        lignes.append(f"- Longueur L = {self.longueur_dalot_m.get():.2f} m")
        lignes.append(f"- Dalle sup = {self.epaisseur_dalle_sup_m.get():.2f} m | Dalle inf = {self.epaisseur_dalle_inf_m.get():.2f} m | Murs = {self.epaisseur_voile_lat_m.get():.2f} m")
        
        # Murs en aile
        if self.aile_g_active.get() or self.aile_d_active.get():
            lignes.append("")
            lignes.append("MURS EN AILE")
            if self.aile_g_active.get():
                lignes.append(f"- Aile gauche: L={self.aile_g_long_m.get():.2f}m, α={self.aile_g_angle_deg.get():.0f}°, e={self.aile_g_ep_m.get():.2f}m")
                lignes.append(f"  Fruit V/H={self.aile_g_fruit_vh.get():.2f}, Offset={self.aile_g_offset_m.get():.2f}m")
            if self.aile_d_active.get():
                lignes.append(f"- Aile droite: L={self.aile_d_long_m.get():.2f}m, α={self.aile_d_angle_deg.get():.0f}°, e={self.aile_d_ep_m.get():.2f}m")
                lignes.append(f"  Fruit V/H={self.aile_d_fruit_vh.get():.2f}, Offset={self.aile_d_offset_m.get():.2f}m")
        
        lignes.append("")
        lignes.append("MATÉRIAUX")
        lignes.append(f"- Béton: {self.classe_beton.get()}")
        lignes.append(f"- Acier: {self.classe_acier.get()}")
        lignes.append(f"- Exposition: {self.classe_exposition.get()}")
        
        # Paramètres détaillés
        if 'parametres' in self.dalot_calculations:
            p = self.dalot_calculations['parametres']
            lignes.append("")
            lignes.append("PARAMÈTRES DE CALCUL")
            lignes.append(f"- Béton: fck={p['fck_MPa']:.0f} MPa, fcd={p['fcd_MPa']:.1f} MPa, γc={p.get('gamma_c',1.5):.2f}")
            lignes.append(f"- Acier: fyk={p['fyk_MPa']:.0f} MPa, fyd={p['fyd_MPa']:.0f} MPa, γs={p.get('gamma_s',1.15):.2f}")
            lignes.append(f"- Enrobage: {p['enrobage_mm']:.0f} mm")
            lignes.append(f"- Sol: γsol={p['gamma_sol_kN_m3']:.1f} kN/m³, φ={p['phi_deg']:.0f}°, c={p['c_kPa']:.1f} kPa")
            lignes.append(f"- Coeff. poussée: Ka={p['Ka']:.3f} ({self.dalot_calculations['poussee_terres'].get('formule_Ka','Rankine')}), K0={p['K0']:.3f} ({self.dalot_calculations['poussee_terres'].get('formule_K0','Jaky')})")
            lignes.append(f"- Combinaisons: γG={p['gamma_G']:.2f}, γQ={p['gamma_Q']:.2f}")
        
        lignes.append("")
        if 'volumes_masses' in self.dalot_calculations:
            vm = self.dalot_calculations['volumes_masses']
            lignes.append("VOLUMES ET MASSES")
            for k, v in vm.items():
                if k != 'total':
                    lignes.append(f"- {v['info']}: Vol={v['volume']:.3f} m³ | Masse={v['masse']:.0f} kg")
            lignes.append(f"- Total: Vol={vm['total']['volume']:.3f} m³ | Masse={vm['total']['masse']:.0f} kg")
            lignes.append("")
            
        if 'charges_dalle_couverture' in self.dalot_calculations:
            ch = self.dalot_calculations['charges_dalle_couverture']
            lignes.append("CHARGES SUR DALLE DE COUVERTURE")
            lignes.append(f"- Poids propre dalle: {ch['q_pp_dalle']:.0f} N/m²")
            lignes.append(f"- Trafic: {ch.get('q_trafic',0):.0f} N/m² | Perm. supp.: {ch['q_permanente_supp']:.0f} N/m²")
            lignes.append(f"- Service (ELS): {ch['q_service']:.0f} N/m² | ELU: {ch['q_ELU']:.0f} N/m²")
            lignes.append("")
            
        if 'poussee_terres' in self.dalot_calculations:
            p = self.dalot_calculations['poussee_terres']
            lignes.append("POUSSÉE DES TERRES")
            lignes.append(f"- σh à la base: {p['sigma_h_base']/1000:.1f} kPa (incl. surcharge)")
            lignes.append(f"- Force poussée (par mètre): {p['force_poussee_par_metre']:.0f} N/m")
            lignes.append(f"- Point d'application: {p['point_application_hauteur']:.2f} m depuis la base")
            lignes.append("")
            
        if 'ferraillage_dalle_couverture' in self.dalot_calculations:
            f = self.dalot_calculations['ferraillage_dalle_couverture']
            arm = self.dalot_calculations.get('armatures_dalle_choisies', {})
            lignes.append("FERRAILLAGE DALLE DE COUVERTURE")
            lignes.append(f"- Moment ELU: {f['moment_ELU']:.0f} Nm/m")
            lignes.append(f"- Hauteur utile d: {f.get('d_m',0)*100:.1f} cm")
            lignes.append(f"- As théorique: {f['As_theorique']*1e4:.2f} cm²/m")
            if arm:
                lignes.append(f"- Armatures proposées: φ{arm.get('diametre','?')} @ {arm.get('espacement','?')} cm")
                lignes.append(f"- As fourni: {arm.get('As_fourni',0)*1e4:.2f} cm²/m")
            lignes.append("")
            
        lignes.append("MÉTHODOLOGIE")
        lignes.append("- Poussée des terres: Théorie de Rankine (Ka) et Jaky (K0)")
        lignes.append("- Combinaisons: Eurocode 0 (EN 1990)")
        lignes.append("- Béton armé: Eurocode 2 (EN 1992)")
        lignes.append("")
        lignes.append("NOTE: Résultats indicatifs à valider par un calcul complet selon les normes en vigueur.")
        return "\n".join(lignes)

    # Commandes diverses
    def cmd_copier_resultats(self):
        contenu = self.zone_calculs.get("1.0", tk.END).strip()
        if contenu:
            self.clipboard_clear()
            self.clipboard_append(contenu)
            self.journaliser("Rapport copié dans le presse-papiers")
            self.maj_statut("Rapport copié")
        else:
            messagebox.showinfo("Copie", "Aucun rapport à copier.")

    def cmd_exporter_pdf(self):
        """Export simple du rapport au format .txt (PDF non requis pour éviter des dépendances)"""
        chemin = filedialog.asksaveasfilename(
            title="Exporter le rapport (texte)",
            defaultextension=".txt",
            filetypes=[("Texte", "*.txt")]
        )
        if not chemin:
            return
        try:
            contenu = self.zone_calculs.get("1.0", tk.END)
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(contenu)
            self.journaliser(f"Rapport exporté: {chemin}")
            messagebox.showinfo("Export", "Rapport exporté avec succès (texte).")
        except Exception as e:
            messagebox.showerror("Export", f"Erreur lors de l'export: {str(e)}")

    def _effacer_resultats(self):
        self.zone_calculs.delete("1.0", tk.END)
        self.zone_verifications.delete("1.0", tk.END)
        self.journaliser("Résultats effacés")

    # Vues 3D rapides
    def cmd_vue_face(self):
        self.ax_3d.view_init(elev=0, azim=0)
        self.canvas_3d.draw()

    def cmd_vue_cote(self):
        self.ax_3d.view_init(elev=0, azim=90)
        self.canvas_3d.draw()

    def cmd_vue_dessus(self):
        self.ax_3d.view_init(elev=90, azim=0)
        self.canvas_3d.draw()

    def cmd_vue_isometrique(self):
        self.ax_3d.view_init(elev=20, azim=45)
        self.canvas_3d.draw()

    # Placeholders supplémentaires
    def cmd_optimiser(self):
        messagebox.showinfo("Optimiser", "Module d'optimisation à venir.")
        self.journaliser("Demande d'optimisation (non implémenté)")

    def cmd_manuel(self):
        messagebox.showinfo("Manuel", "Le manuel utilisateur sera disponible prochainement.")
        self.journaliser("Manuel utilisateur consulté")

    def cmd_a_propos(self):
        messagebox.showinfo(
            "À propos",
            "Progiciel de dimensionnement des dalots en béton armé\n"
            "Interface complète avec visualisation 3D interactive.\n"
            "Version 2.0"
        )

    # Fichiers et état
    def action_nouveau(self):
        if self.modifie:
            if not messagebox.askyesno("Confirmation", "Des modifications non enregistrées seront perdues. Continuer ?"):
                return
        # Réinitialiser quelques champs
        self.largeur_dalot_m.set(3.0)
        self.hauteur_dalot_m.set(2.0)
        self.longueur_dalot_m.set(20.0)
        self.epaisseur_dalle_sup_m.set(0.30)
        self.epaisseur_dalle_inf_m.set(0.30)
        self.epaisseur_voile_lat_m.set(0.25)
        self.zone_calculs.delete("1.0", tk.END)
        self.zone_verifications.delete("1.0", tk.END)
        self.zone_journal.delete("1.0", tk.END)
        self.chemin_fichier_courant = None
        self.modifie = False
        self._mettre_a_jour_titre_fenetre()
        self._dessiner_dalot_3d()
        self.journaliser("Nouveau projet")

    def action_ouvrir(self):
        messagebox.showinfo("Ouvrir", "Fonction d'ouverture de projet non implémentée.")
        self.journaliser("Ouverture projet (non implémenté)")

    def action_enregistrer(self):
        messagebox.showinfo("Enregistrer", "Fonction d'enregistrement non implémentée.")
        self.journaliser("Enregistrement (non implémenté)")

    def _marquer_modifie(self):
        if not self.modifie:
            self.modifie = True
            self._mettre_a_jour_titre_fenetre()

    def _mettre_a_jour_titre_fenetre(self):
        mod = "*" if self.modifie else ""
        nom = os.path.basename(self.chemin_fichier_courant) if self.chemin_fichier_courant else "Sans titre"
        self.title(f"{mod}{self.nom_projet.get()} - {nom} | Dalot BA v2.0")

    def _avant_quitter(self):
        if self.modifie:
            if not messagebox.askyesno("Quitter", "Des modifications non enregistrées seront perdues. Quitter ?"):
                return
        self.destroy()

    def journaliser(self, message: str):
        if hasattr(self, "zone_journal"):
            self.zone_journal.insert("end", f"- {message}\n")
            self.zone_journal.see("end")

# Point d'entrée
def main():
    app = ApplicationDalotComplete()
    app.mainloop()

if __name__ == "__main__":
    main()


