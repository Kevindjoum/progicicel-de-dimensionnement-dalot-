"""
Interface graphique (Tkinter) pour un progiciel de dimensionnement des dalots en béton armé.
- Exclusivement Python + tkinter, numpy, matplotlib, pandas
- Aucune logique de calcul implémentée (placeholders "TODO")
- Variables et libellés en français
- Conçu pour être lisible et modifiable par un débutant en programmation

Fonctions principales:
- Menu Fichier (Nouveau / Ouvrir / Enregistrer / Enregistrer sous / Importer CSV / Exporter CSV / Quitter)
- Onglets d'entrée: Projet, Hydrologie, Hydraulique, Structure, Géotechnique, Options
- Zone de visualisation 2D (plan) et 3D (volume) via matplotlib
- Zone Résultats (texte) et Journal (log)
- Barre d'outils (Vérifier, Lancer calculs, Réinitialiser, Mettre à jour 2D/3D)
- Barre de statut et barre de progression

Remarque: Les “calculs” seront intégrés plus tard dans les fonctions marquées TODO.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

# Bibliothèques demandées (même si peu utilisées à ce stade)
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  # nécessaire pour activer la 3D dans matplotlib


# ----------------------------
# Utilitaires d'interface
# ----------------------------

class Infobulle:
    """
    Petite classe utilitaire pour afficher une infobulle (tooltip) quand la souris survole un widget.
    Usage:
        Infobulle(widget, "Texte d'aide")
    """

    def __init__(self, widget, texte):
        self.widget = widget
        self.texte = texte
        self.bulle = None
        widget.bind("<Enter>", self._afficher)
        widget.bind("<Leave>", self._masquer)

    def _afficher(self, _event):
        if self.bulle or not self.texte:
            return
        x, y, cx, cy = self.widget.bbox("insert") if self.widget.winfo_exists() else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.bulle = tk.Toplevel(self.widget)
        self.bulle.wm_overrideredirect(True)
        self.bulle.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.bulle, text=self.texte, justify="left",
            background="#ffffe0", relief="solid", borderwidth=1,
            font=("TkDefaultFont", 9)
        )
        label.pack(ipadx=5, ipady=3)

    def _masquer(self, _event):
        if self.bulle:
            self.bulle.destroy()
            self.bulle = None


# ----------------------------
# Application principale
# ----------------------------

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Progiciel Dalot BA - Interface (Tkinter)")
        self.geometry("1280x800")
        self.minsize(1100, 700)

        # Suivi d'état fichier
        self.chemin_fichier_courant = None
        self.modifie = False

        # Style ttk simple (peut être enrichi plus tard)
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # Définition des variables (toutes en français)
        self._definir_variables()

        # Construction de l'interface
        self._creer_menus()
        self._creer_barre_outils()
        self._creer_pane_principal()
        self._creer_barre_statut()

        # Raccourcis clavier
        self.bind_all("<Control-n>", lambda e: self.action_nouveau())
        self.bind_all("<Control-o>", lambda e: self.action_ouvrir())
        self.bind_all("<Control-s>", lambda e: self.action_enregistrer())

        # Gestion fermeture
        self.protocol("WM_DELETE_WINDOW", self._avant_quitter)

        # Initialisation visuels
        self._mettre_a_jour_titre_fenetre()
        self.maj_statut("Prêt.")

    # ----------------------------
    # Définition des variables
    # ----------------------------
    def _definir_variables(self):
        # Métadonnées projet
        self.nom_projet = tk.StringVar(value="Nouveau projet")
        self.ingenieur = tk.StringVar(value="")
        self.localisation = tk.StringVar(value="")
        self.date_projet = tk.StringVar(value="")

        # Hydrologie (exemples de champs)
        self.surface_bassin_km2 = tk.DoubleVar(value=2.0)
        self.coeff_ruissellement = tk.DoubleVar(value=0.6)
        self.intensite_pluie_mm_h = tk.DoubleVar(value=80.0)
        self.temps_concentration_min = tk.DoubleVar(value=30.0)

        # Hydraulique / Géométrie dalot
        self.largeur_dalot_m = tk.DoubleVar(value=3.0)
        self.hauteur_dalot_m = tk.DoubleVar(value=2.0)
        self.pente_dalot = tk.DoubleVar(value=0.005)
        self.longueur_dalot_m = tk.DoubleVar(value=20.0)
        self.rugosite_manning = tk.DoubleVar(value=0.013)
        self.tirant_amont_max_m = tk.DoubleVar(value=0.6)
        self.nombre_cellules = tk.IntVar(value=1)

        # Structure (pré-dimensionnement – placeholders)
        self.epaisseur_dalle_m = tk.DoubleVar(value=0.30)
        self.enrobage_m = tk.DoubleVar(value=0.05)
        self.diametre_barres_m = tk.DoubleVar(value=0.016)
        self.travee_m = tk.DoubleVar(value=3.0)
        self.charges_remblai_kNm2 = tk.DoubleVar(value=20.0)
        self.charges_trafic_kNm2 = tk.DoubleVar(value=10.0)
        self.betons_fck_mpa = tk.DoubleVar(value=30.0)
        self.acier_fyk_mpa = tk.DoubleVar(value=500.0)

        # Géotechnique
        self.portance_admissible_kpa = tk.DoubleVar(value=200.0)
        self.niveau_nappe_m = tk.DoubleVar(value=1.0)
        self.densite_remblai_kNm3 = tk.DoubleVar(value=20.0)

        # Options
        self.systeme_unites = tk.StringVar(value="SI (m, kN, s)")
        self.theme_couleur = tk.StringVar(value="Clair")
        self.afficher_legendes = tk.BooleanVar(value=True)
        self.mode_avance = tk.BooleanVar(value=False)

    # ----------------------------
    # Menus
    # ----------------------------
    def _creer_menus(self):
        barre_menu = tk.Menu(self)

        menu_fichier = tk.Menu(barre_menu, tearoff=0)
        menu_fichier.add_command(label="Nouveau", accelerator="Ctrl+N", command=self.action_nouveau)
        menu_fichier.add_command(label="Ouvrir...", accelerator="Ctrl+O", command=self.action_ouvrir)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Enregistrer", accelerator="Ctrl+S", command=self.action_enregistrer)
        menu_fichier.add_command(label="Enregistrer sous...", command=self.action_enregistrer_sous)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Importer CSV...", command=self.action_importer_csv)
        menu_fichier.add_command(label="Exporter CSV...", command=self.action_exporter_csv)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Quitter", command=self._avant_quitter)
        barre_menu.add_cascade(label="Fichier", menu=menu_fichier)

        menu_outils = tk.Menu(barre_menu, tearoff=0)
        menu_outils.add_command(label="Préférences...", command=self.cmd_preferences)
        barre_menu.add_cascade(label="Outils", menu=menu_outils)

        menu_aide = tk.Menu(barre_menu, tearoff=0)
        menu_aide.add_command(label="À propos", command=self.cmd_a_propos)
        barre_menu.add_cascade(label="Aide", menu=menu_aide)

        self.config(menu=barre_menu)

    # ----------------------------
    # Barre d'outils
    # ----------------------------
    def _creer_barre_outils(self):
        cadre = ttk.Frame(self)
        cadre.pack(side="top", fill="x")

        btn_verifier = ttk.Button(cadre, text="Vérifier entrées", command=self.cmd_verifier_entrees)
        btn_calculs = ttk.Button(cadre, text="Lancer calculs (TODO)", command=self.cmd_lancer_calculs)
        btn_reset = ttk.Button(cadre, text="Réinitialiser", command=self.cmd_reinitialiser_formulaire)
        btn_2d = ttk.Button(cadre, text="Mettre à jour 2D", command=self.cmd_mettre_a_jour_2d)
        btn_3d = ttk.Button(cadre, text="Mettre à jour 3D", command=self.cmd_mettre_a_jour_3d)

        btn_verifier.pack(side="left", padx=5, pady=5)
        btn_calculs.pack(side="left", padx=5, pady=5)
        btn_reset.pack(side="left", padx=5, pady=5)
        btn_2d.pack(side="left", padx=20, pady=5)
        btn_3d.pack(side="left", padx=5, pady=5)

        # Barre de progression (pour futures opérations longues)
        self.barre_progression = ttk.Progressbar(cadre, mode="determinate", length=200)
        self.barre_progression.pack(side="right", padx=10, pady=5)

    # ----------------------------
    # Panes principal: gauche (onglets) / droite (plots & résultats)
    # ----------------------------
    def _creer_pane_principal(self):
        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)

        # Pane gauche: onglets d'entrée
        self.cadre_gauche = ttk.Frame(pane)
        pane.add(self.cadre_gauche, weight=1)

        self.onglets_entree = ttk.Notebook(self.cadre_gauche)
        self.onglets_entree.pack(fill="both", expand=True, padx=5, pady=5)

        self._onglet_projet()
        self._onglet_hydrologie()
        self._onglet_hydraulique()
        self._onglet_structure()
        self._onglet_geotechnique()
        self._onglet_options()

        # Pane droite: visualisation & résultats
        self.cadre_droit = ttk.Frame(pane)
        pane.add(self.cadre_droit, weight=2)

        self.onglets_sortie = ttk.Notebook(self.cadre_droit)
        self.onglets_sortie.pack(fill="both", expand=True, padx=5, pady=5)

        self._onglet_traces_2d()
        self._onglet_vue_3d()
        self._onglet_resultats()
        self._onglet_journal()

    # ----------------------------
    # Barre de statut
    # ----------------------------
    def _creer_barre_statut(self):
        cadre_statut = ttk.Frame(self)
        cadre_statut.pack(side="bottom", fill="x")
        self.libelle_statut = ttk.Label(cadre_statut, text="Prêt.", anchor="w")
        self.libelle_statut.pack(side="left", padx=5, pady=3)

    def maj_statut(self, texte: str):
        self.libelle_statut.config(text=texte)
        self.update_idletasks()

    # ----------------------------
    # Onglets d'entrée
    # ----------------------------
    def _onglet_projet(self):
        cadre = ttk.Frame(self.onglets_entree)
        self.onglets_entree.add(cadre, text="Projet")

        grp = ttk.LabelFrame(cadre, text="Informations du projet")
        grp.pack(fill="x", padx=10, pady=10)

        self._ajouter_champ(grp, "Nom du projet:", self.nom_projet, ligne=0, info="Titre de votre étude.")
        self._ajouter_champ(grp, "Ingénieur:", self.ingenieur, ligne=1, info="Nom du responsable des calculs.")
        self._ajouter_champ(grp, "Localisation:", self.localisation, ligne=2, info="Lieu ou tronçon concerné.")
        self._ajouter_champ(grp, "Date:", self.date_projet, ligne=3, info="Format libre (ex: 2025-08-28).")

    def _onglet_hydrologie(self):
        cadre = ttk.Frame(self.onglets_entree)
        self.onglets_entree.add(cadre, text="Hydrologie")

        grp = ttk.LabelFrame(cadre, text="Paramètres hydrologiques")
        grp.pack(fill="x", padx=10, pady=10)

        self._ajouter_champ(grp, "Surface bassin (km²):", self.surface_bassin_km2, ligne=0,
                            info="Superficie du bassin versant contributif.")
        self._ajouter_champ(grp, "Coeff. ruissellement C:", self.coeff_ruissellement, ligne=1,
                            info="0 < C < 1, selon occupation des sols.")
        self._ajouter_champ(grp, "Intensité pluie (mm/h):", self.intensite_pluie_mm_h, ligne=2,
                            info="Intensité à la durée égale au temps de concentration.")
        self._ajouter_champ(grp, "Temps de concentration (min):", self.temps_concentration_min, ligne=3,
                            info="Durée caractéristique d’écoulement du bassin.")

    def _onglet_hydraulique(self):
        cadre = ttk.Frame(self.onglets_entree)
        self.onglets_entree.add(cadre, text="Hydraulique")

        grp_geo = ttk.LabelFrame(cadre, text="Géométrie du dalot (boîte)")
        grp_geo.pack(fill="x", padx=10, pady=10)

        self._ajouter_champ(grp_geo, "Largeur intérieure (m):", self.largeur_dalot_m, 0,
                            info="Largeur d'une cellule.")
        self._ajouter_champ(grp_geo, "Hauteur intérieure (m):", self.hauteur_dalot_m, 1,
                            info="Hauteur libre de la section.")
        self._ajouter_champ(grp_geo, "Nombre de cellules:", self.nombre_cellules, 2,
                            info="Nombre de boîtes en parallèle.")
        self._ajouter_champ(grp_geo, "Pente (-):", self.pente_dalot, 3,
                            info="Pente de l’ouvrage (ex: 0.005 = 0.5%).")
        self._ajouter_champ(grp_geo, "Longueur (m):", self.longueur_dalot_m, 4,
                            info="Longueur totale entre têtes.")
        self._ajouter_champ(grp_geo, "Rugosité de Manning n:", self.rugosite_manning, 5,
                            info="Béton lisse typiquement 0.012–0.015.")

        grp_hwa = ttk.LabelFrame(cadre, text="Conditions amont/aval")
        grp_hwa.pack(fill="x", padx=10, pady=10)
        self._ajouter_champ(grp_hwa, "Tirant amont max (m):", self.tirant_amont_max_m, 0,
                            info="Hauteur d’eau admissible au-dessus de la génératrice.")

    def _onglet_structure(self):
        cadre = ttk.Frame(self.onglets_entree)
        self.onglets_entree.add(cadre, text="Structure")

        grp_dim = ttk.LabelFrame(cadre, text="Paramètres géométriques/armatures (toit/plancher)")
        grp_dim.pack(fill="x", padx=10, pady=10)
        self._ajouter_champ(grp_dim, "Épaisseur dalle (m):", self.epaisseur_dalle_m, 0,
                            info="Épaisseur du voile horizontal.")
        self._ajouter_champ(grp_dim, "Enrobage (m):", self.enrobage_m, 1,
                            info="Distance béton/acier.")
        self._ajouter_champ(grp_dim, "Diamètre barres (m):", self.diametre_barres_m, 2,
                            info="Diamètre des barres principales.")
        self._ajouter_champ(grp_dim, "Portée/Travée (m):", self.travee_m, 3,
                            info="Distances entre appuis internes (voiles).")

        grp_ch = ttk.LabelFrame(cadre, text="Charges (simplifiées)")
        grp_ch.pack(fill="x", padx=10, pady=10)
        self._ajouter_champ(grp_ch, "Charges remblai (kN/m²):", self.charges_remblai_kNm2, 0,
                            info="Pression équivalente du remblai.")
        self._ajouter_champ(grp_ch, "Charges trafic (kN/m²):", self.charges_trafic_kNm2, 1,
                            info="Approximation des charges roulantes.")
        self._ajouter_champ(grp_ch, "Béton fck (MPa):", self.betons_fck_mpa, 2,
                            info="Résistance caractéristique béton.")
        self._ajouter_champ(grp_ch, "Acier fyk (MPa):", self.acier_fyk_mpa, 3,
                            info="Limite d’élasticité acier.")

    def _onglet_geotechnique(self):
        cadre = ttk.Frame(self.onglets_entree)
        self.onglets_entree.add(cadre, text="Géotechnique")

        grp_geo = ttk.LabelFrame(cadre, text="Paramètres géotechniques (simplifiés)")
        grp_geo.pack(fill="x", padx=10, pady=10)
        self._ajouter_champ(grp_geo, "Portance admissible (kPa):", self.portance_admissible_kpa, 0,
                            info="Capacité du sol (à vérifier selon EN 1997).")
        self._ajouter_champ(grp_geo, "Niveau de nappe (m):", self.niveau_nappe_m, 1,
                            info="Cote de la nappe phréatique.")
        self._ajouter_champ(grp_geo, "Densité remblai (kN/m³):", self.densite_remblai_kNm3, 2,
                            info="Poids volumique du remblai.")

    def _onglet_options(self):
        cadre = ttk.Frame(self.onglets_entree)
        self.onglets_entree.add(cadre, text="Options")

        grp_opt = ttk.LabelFrame(cadre, text="Options d’affichage et préférences")
        grp_opt.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_opt, text="Système d’unités:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_unit = ttk.Combobox(grp_opt, textvariable=self.systeme_unites, values=["SI (m, kN, s)"], state="readonly")
        combo_unit.grid(row=0, column=1, sticky="we", padx=5, pady=4)

        ttk.Label(grp_opt, text="Thème:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        combo_theme = ttk.Combobox(grp_opt, textvariable=self.theme_couleur, values=["Clair", "Sombre"], state="readonly")
        combo_theme.grid(row=1, column=1, sticky="we", padx=5, pady=4)
        combo_theme.bind("<<ComboboxSelected>>", self._appliquer_theme)

        chk_leg = ttk.Checkbutton(grp_opt, text="Afficher légendes", variable=self.afficher_legendes, command=self._rafraichir_plots)
        chk_leg.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=4)

        chk_adv = ttk.Checkbutton(grp_opt, text="Mode avancé (afficher options supplémentaires)", variable=self.mode_avance, command=self._basculer_mode_avance)
        chk_adv.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=4)

        grp_opt.columnconfigure(1, weight=1)

    def _ajouter_champ(self, parent, texte_label, var, ligne: int, info: str = ""):
        """Ajoute un label + entrée typée selon la variable (StringVar/DoubleVar/IntVar)."""
        ttk.Label(parent, text=texte_label).grid(row=ligne, column=0, sticky="e", padx=5, pady=4)
        # Choix du widget selon le type de variable
        if isinstance(var, tk.BooleanVar):
            entree = ttk.Checkbutton(parent, variable=var)
        else:
            entree = ttk.Entry(parent, textvariable=var)
        entree.grid(row=ligne, column=1, sticky="we", padx=5, pady=4)
        parent.columnconfigure(1, weight=1)
        if info:
            Infobulle(entree, info)
        # Marquer comme modifié à la saisie
        entree.bind("<KeyRelease>", lambda e: self._marquer_modifie())

    # ----------------------------
    # Onglets de sortie (plots, résultats, journal)
    # ----------------------------
    def _onglet_traces_2d(self):
        cadre = ttk.Frame(self.onglets_sortie)
        self.onglets_sortie.add(cadre, text="Tracé 2D")

        # Figure 2D
        self.figure_2d = Figure(figsize=(5, 4), dpi=100)
        self.axe_2d = self.figure_2d.add_subplot(111)
        self.axe_2d.set_title("Plan 2D du dalot (schéma)")
        self.axe_2d.set_xlabel("x (m)")
        self.axe_2d.set_ylabel("y (m)")

        self.canvas_2d = FigureCanvasTkAgg(self.figure_2d, master=cadre)
        self.canvas_2d.draw()
        self.canvas_2d.get_tk_widget().pack(fill="both", expand=True)

        self.toolbar_2d = NavigationToolbar2Tk(self.canvas_2d, cadre, pack_toolbar=False)
        self.toolbar_2d.update()
        self.toolbar_2d.pack(side="bottom", fill="x")

        # Boutons d'actions spécifiques 2D
        cadre_btn = ttk.Frame(cadre)
        cadre_btn.pack(side="bottom", fill="x")
        ttk.Button(cadre_btn, text="Exporter PNG 2D", command=self.cmd_exporter_image_2d).pack(side="right", padx=5, pady=5)
        ttk.Button(cadre_btn, text="Mettre à jour 2D", command=self.cmd_mettre_a_jour_2d).pack(side="right", padx=5, pady=5)

        # Premier rendu
        self._dessiner_2d()

    def _onglet_vue_3d(self):
        cadre = ttk.Frame(self.onglets_sortie)
        self.onglets_sortie.add(cadre, text="Vue 3D")

        # Figure 3D
        self.figure_3d = Figure(figsize=(5, 4), dpi=100)
        self.axe_3d = self.figure_3d.add_subplot(111, projection="3d")
        self.axe_3d.set_title("Volume 3D du dalot (schéma)")
        self.axe_3d.set_xlabel("x (m)")
        self.axe_3d.set_ylabel("y (m)")
        self.axe_3d.set_zlabel("z (m)")

        self.canvas_3d = FigureCanvasTkAgg(self.figure_3d, master=cadre)
        self.canvas_3d.draw()
        self.canvas_3d.get_tk_widget().pack(fill="both", expand=True)

        self.toolbar_3d = NavigationToolbar2Tk(self.canvas_3d, cadre, pack_toolbar=False)
        self.toolbar_3d.update()
        self.toolbar_3d.pack(side="bottom", fill="x")

        cadre_btn = ttk.Frame(cadre)
        cadre_btn.pack(side="bottom", fill="x")
        ttk.Button(cadre_btn, text="Exporter PNG 3D", command=self.cmd_exporter_image_3d).pack(side="right", padx=5, pady=5)
        ttk.Button(cadre_btn, text="Mettre à jour 3D", command=self.cmd_mettre_a_jour_3d).pack(side="right", padx=5, pady=5)

        self._dessiner_3d()

    def _onglet_resultats(self):
        cadre = ttk.Frame(self.onglets_sortie)
        self.onglets_sortie.add(cadre, text="Résultats")

        grp = ttk.LabelFrame(cadre, text="Résumé des résultats (sera rempli après calculs)")
        grp.pack(fill="both", expand=True, padx=10, pady=10)

        self.zone_resultats = ScrolledText(grp, height=15, wrap="word")
        self.zone_resultats.pack(fill="both", expand=True, padx=5, pady=5)

        cadre_btn = ttk.Frame(grp)
        cadre_btn.pack(fill="x")
        ttk.Button(cadre_btn, text="Copier", command=self.cmd_copier_resultats).pack(side="left", padx=5, pady=5)
        ttk.Button(cadre_btn, text="Effacer", command=lambda: self.zone_resultats.delete("1.0", "end")).pack(side="left", padx=5, pady=5)

    def _onglet_journal(self):
        cadre = ttk.Frame(self.onglets_sortie)
        self.onglets_sortie.add(cadre, text="Journal")

        grp = ttk.LabelFrame(cadre, text="Journal des actions")
        grp.pack(fill="both", expand=True, padx=10, pady=10)

        self.zone_journal = ScrolledText(grp, height=15, wrap="word")
        self.zone_journal.pack(fill="both", expand=True, padx=5, pady=5)

    # ----------------------------
    # Dessins (simples schémas)
    # ----------------------------
    def _dessiner_2d(self):
        """Dessine un schéma 2D simple (rectangle du dalot et annotation)."""
        self.axe_2d.clear()
        largeur = float(self.largeur_dalot_m.get())
        hauteur = float(self.hauteur_dalot_m.get())
        nb = int(self.nombre_cellules.get())

        # Dessin de nb cellules côte à côte
        espacement = 0.5  # m, espace fictif entre cellules pour le schéma
        x_depart = 0.0
        for i in range(nb):
            rect_x = x_depart + i * (largeur + espacement)
            xs = [rect_x, rect_x + largeur, rect_x + largeur, rect_x, rect_x]
            ys = [0, 0, hauteur, hauteur, 0]
            self.axe_2d.plot(xs, ys, color="navy", label="Cellule" if i == 0 else None)

        self.axe_2d.set_aspect("equal", adjustable="datalim")
        self.axe_2d.set_xlabel("x (m)")
        self.axe_2d.set_ylabel("y (m)")
        self.axe_2d.set_title("Plan 2D du dalot (schéma)")

        if self.afficher_legendes.get():
            self.axe_2d.legend(loc="upper right")

        # Ajuster les limites avec marges
        max_x = nb * (largeur + espacement)
        self.axe_2d.set_xlim(-0.5, max(largeur + 0.5, max_x))
        self.axe_2d.set_ylim(-0.5, hauteur + 0.5)

        self.canvas_2d.draw()

    def _dessiner_3d(self):
        """Dessine une boîte 3D simple représentant une cellule de dalot."""
        self.axe_3d.clear()
        largeur = float(self.largeur_dalot_m.get())
        hauteur = float(self.hauteur_dalot_m.get())
        longueur = float(self.longueur_dalot_m.get())

        # Sommets de la boîte (origine à 0,0,0)
        X = [0, largeur]
        Y = [0, longueur]
        Z = [0, hauteur]

        # Arêtes de la boîte (tracé filaire)
        def segment(p1, p2):
            self.axe_3d.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], color="darkgreen")

        coins = {
            "A": (X[0], Y[0], Z[0]),
            "B": (X[1], Y[0], Z[0]),
            "C": (X[1], Y[1], Z[0]),
            "D": (X[0], Y[1], Z[0]),
            "E": (X[0], Y[0], Z[1]),
            "F": (X[1], Y[0], Z[1]),
            "G": (X[1], Y[1], Z[1]),
            "H": (X[0], Y[1], Z[1]),
        }

        # Bas
        segment(coins["A"], coins["B"])
        segment(coins["B"], coins["C"])
        segment(coins["C"], coins["D"])
        segment(coins["D"], coins["A"])
        # Haut
        segment(coins["E"], coins["F"])
        segment(coins["F"], coins["G"])
        segment(coins["G"], coins["H"])
        segment(coins["H"], coins["E"])
        # Piliers
        segment(coins["A"], coins["E"])
        segment(coins["B"], coins["F"])
        segment(coins["C"], coins["G"])
        segment(coins["D"], coins["H"])

        self.axe_3d.set_xlabel("x (m)")
        self.axe_3d.set_ylabel("y (m)")
        self.axe_3d.set_zlabel("z (m)")
        self.axe_3d.set_title("Volume 3D du dalot (schéma)")

        if self.afficher_legendes.get():
            self.axe_3d.legend([], [])  # pas d'objets avec label pour le moment

        # Ajuster les limites
        self.axe_3d.set_xlim(0, max(largeur, 1.0))
        self.axe_3d.set_ylim(0, max(longueur, 1.0))
        self.axe_3d.set_zlim(0, max(hauteur, 1.0))
        self.canvas_3d.draw()

    def _rafraichir_plots(self):
        self._dessiner_2d()
        self._dessiner_3d()

    # ----------------------------
    # Commandes principales (stubs/placeholder)
    # ----------------------------
    def cmd_verifier_entrees(self):
        """
        Vérifie superficiellement que les champs numériques sont valides.
        Cette validation est basique et sera renforcée plus tard.
        """
        try:
            _ = float(self.surface_bassin_km2.get())
            _ = float(self.coeff_ruissellement.get())
            _ = float(self.intensite_pluie_mm_h.get())
            _ = int(self.nombre_cellules.get())
            # Ajouter d'autres vérifications si besoin
        except (ValueError, tk.TclError):
            messagebox.showerror("Erreur", "Certaines entrées ne sont pas valides. Corrigez-les.")
            self.journaliser("Échec de la vérification des entrées.")
            return

        messagebox.showinfo("Vérification", "Entrées conformes (vérification simple).")
        self.journaliser("Vérification des entrées: OK.")
        self.maj_statut("Entrées vérifiées.")

    def cmd_lancer_calculs(self):
        """
        Lieu d’intégration des programmes de calcul (hydrologie, hydraulique, structure, géotechnique).
        TODO: appeler vos fonctions ici, puis afficher les résultats et mettre à jour les graphes.
        """
        self.journaliser("Début des calculs (TODO).")
        self.maj_statut("Calculs en cours (TODO)...")
        # TODO: Implémenter les appels aux modules de calcul et remplir self.zone_resultats
        messagebox.showinfo("Calculs", "Les calculs seront intégrés ici (TODO).")
        self.journaliser("Fin des calculs (TODO).")
        self.maj_statut("Prêt.")

    def cmd_reinitialiser_formulaire(self):
        if not messagebox.askyesno("Confirmation", "Réinitialiser toutes les valeurs ?"):
            return
        self._definir_variables()  # réinstancie les variables avec valeurs par défaut
        # Recréer les onglets d'entrée pour refléter les nouvelles variables
        self._reconstruire_onglets_entree()
        self._rafraichir_plots()
        self.zone_resultats.delete("1.0", "end")
        self.journaliser("Formulaire réinitialisé.")
        self.modifie = False
        self._mettre_a_jour_titre_fenetre()

    def _reconstruire_onglets_entree(self):
        """Reconstruit les onglets d'entrée après réinit des variables."""
        for tab_id in self.onglets_entree.tabs():
            self.onglets_entree.forget(tab_id)
        self._onglet_projet()
        self._onglet_hydrologie()
        self._onglet_hydraulique()
        self._onglet_structure()
        self._onglet_geotechnique()
        self._onglet_options()

    def cmd_mettre_a_jour_2d(self):
        self._dessiner_2d()
        self.journaliser("Mise à jour du tracé 2D.")
        self.maj_statut("Tracé 2D mis à jour.")

    def cmd_mettre_a_jour_3d(self):
        self._dessiner_3d()
        self.journaliser("Mise à jour de la vue 3D.")
        self.maj_statut("Vue 3D mise à jour.")

    def cmd_exporter_image_2d(self):
        chemin = filedialog.asksaveasfilename(
            title="Exporter l'image 2D",
            defaultextension=".png",
            filetypes=[("Image PNG", "*.png")]
        )
        if not chemin:
            return
        try:
            self.figure_2d.savefig(chemin, dpi=200)
            self.journaliser(f"Image 2D exportée: {chemin}")
            messagebox.showinfo("Export", "Image 2D exportée avec succès.")
        except Exception as e:
            messagebox.showerror("Erreur export", str(e))

    def cmd_exporter_image_3d(self):
        chemin = filedialog.asksaveasfilename(
            title="Exporter l'image 3D",
            defaultextension=".png",
            filetypes=[("Image PNG", "*.png")]
        )
        if not chemin:
            return
        try:
            self.figure_3d.savefig(chemin, dpi=200)
            self.journaliser(f"Image 3D exportée: {chemin}")
            messagebox.showinfo("Export", "Image 3D exportée avec succès.")
        except Exception as e:
            messagebox.showerror("Erreur export", str(e))

    def cmd_copier_resultats(self):
        contenu = self.zone_resultats.get("1.0", "end").strip()
        if not contenu:
            messagebox.showinfo("Résultats", "Aucun résultat à copier.")
            return
        self.clipboard_clear()
        self.clipboard_append(contenu)
        self.journaliser("Résultats copiés dans le presse-papiers.")
        self.maj_statut("Résultats copiés.")

    def cmd_preferences(self):
        messagebox.showinfo("Préférences", "Ici, vous pourrez configurer des préférences (TODO).")

    def cmd_a_propos(self):
        messagebox.showinfo(
            "À propos",
            "Progiciel de dimensionnement des dalots en BA (interface Tkinter)\n"
            "Ce prototype contient uniquement l’interface.\n"
            "Calculs à intégrer ultérieurement."
        )

    def _appliquer_theme(self, _event=None):
        theme = self.theme_couleur.get()
        if theme == "Sombre":
            self.style.configure(".", background="#2b2b2b", foreground="white")
            self.style.map("TButton", foreground=[("active", "white")])
        else:
            self.style.configure(".", background="", foreground="")
        self.journaliser(f"Thème appliqué: {theme}")

    def _basculer_mode_avance(self):
        etat = "Activé" if self.mode_avance.get() else "Désactivé"
        self.journaliser(f"Mode avancé: {etat}")
        messagebox.showinfo("Mode avancé", f"Mode avancé {etat} (placeholder).")

    # ----------------------------
    # Journal & statut
    # ----------------------------
    def journaliser(self, message: str):
        if hasattr(self, "zone_journal"):
            self.zone_journal.insert("end", f"- {message}\n")
            self.zone_journal.see("end")

    # ----------------------------
    # Gestion fichier (CSV via pandas)
    # ----------------------------
    def _collecter_donnees(self) -> dict:
        """
        Rassemble toutes les variables dans un dict.
        Clés = noms conviviaux; valeurs = scalaires.
        """
        data = {
            # Projet
            "nom_projet": self.nom_projet.get(),
            "ingenieur": self.ingenieur.get(),
            "localisation": self.localisation.get(),
            "date_projet": self.date_projet.get(),
            # Hydrologie
            "surface_bassin_km2": self.surface_bassin_km2.get(),
            "coeff_ruissellement": self.coeff_ruissellement.get(),
            "intensite_pluie_mm_h": self.intensite_pluie_mm_h.get(),
            "temps_concentration_min": self.temps_concentration_min.get(),
            # Hydraulique
            "largeur_dalot_m": self.largeur_dalot_m.get(),
            "hauteur_dalot_m": self.hauteur_dalot_m.get(),
            "nombre_cellules": self.nombre_cellules.get(),
            "pente_dalot": self.pente_dalot.get(),
            "longueur_dalot_m": self.longueur_dalot_m.get(),
            "rugosite_manning": self.rugosite_manning.get(),
            "tirant_amont_max_m": self.tirant_amont_max_m.get(),
            # Structure
            "epaisseur_dalle_m": self.epaisseur_dalle_m.get(),
            "enrobage_m": self.enrobage_m.get(),
            "diametre_barres_m": self.diametre_barres_m.get(),
            "travee_m": self.travee_m.get(),
            "charges_remblai_kNm2": self.charges_remblai_kNm2.get(),
            "charges_trafic_kNm2": self.charges_trafic_kNm2.get(),
            "betons_fck_mpa": self.betons_fck_mpa.get(),
            "acier_fyk_mpa": self.acier_fyk_mpa.get(),
            # Géotechnique
            "portance_admissible_kpa": self.portance_admissible_kpa.get(),
            "niveau_nappe_m": self.niveau_nappe_m.get(),
            "densite_remblai_kNm3": self.densite_remblai_kNm3.get(),
            # Options
            "systeme_unites": self.systeme_unites.get(),
            "theme_couleur": self.theme_couleur.get(),
            "afficher_legendes": self.afficher_legendes.get(),
            "mode_avance": self.mode_avance.get(),
        }
        return data

    def _remplir_depuis_dict(self, data: dict):
        """
        Met à jour les variables depuis un dict (clés identiques à _collecter_donnees()).
        """
        def set_if_exist(varname, converter=None):
            if varname in data:
                val = data[varname]
                if converter:
                    try:
                        val = converter(val)
                    except Exception:
                        pass
                getattr(self, varname).set(val)

        # Projet
        set_if_exist("nom_projet", str)
        set_if_exist("ingenieur", str)
        set_if_exist("localisation", str)
        set_if_exist("date_projet", str)
        # Hydrologie
        set_if_exist("surface_bassin_km2", float)
        set_if_exist("coeff_ruissellement", float)
        set_if_exist("intensite_pluie_mm_h", float)
        set_if_exist("temps_concentration_min", float)
        # Hydraulique
        set_if_exist("largeur_dalot_m", float)
        set_if_exist("hauteur_dalot_m", float)
        set_if_exist("nombre_cellules", int)
        set_if_exist("pente_dalot", float)
        set_if_exist("longueur_dalot_m", float)
        set_if_exist("rugosite_manning", float)
        set_if_exist("tirant_amont_max_m", float)
        # Structure
        set_if_exist("epaisseur_dalle_m", float)
        set_if_exist("enrobage_m", float)
        set_if_exist("diametre_barres_m", float)
        set_if_exist("travee_m", float)
        set_if_exist("charges_remblai_kNm2", float)
        set_if_exist("charges_trafic_kNm2", float)
        set_if_exist("betons_fck_mpa", float)
        set_if_exist("acier_fyk_mpa", float)
        # Géotechnique
        set_if_exist("portance_admissible_kpa", float)
        set_if_exist("niveau_nappe_m", float)
        set_if_exist("densite_remblai_kNm3", float)
        # Options
        set_if_exist("systeme_unites", str)
        set_if_exist("theme_couleur", str)
        set_if_exist("afficher_legendes", bool)
        set_if_exist("mode_avance", bool)

    def action_nouveau(self):
        if self.modifie:
            if not messagebox.askyesno("Confirmation", "Des modifications non enregistrées seront perdues. Continuer ?"):
                return
        self.cmd_reinitialiser_formulaire()
        self.chemin_fichier_courant = None
        self._mettre_a_jour_titre_fenetre()

    def action_ouvrir(self):
        chemin = filedialog.askopenfilename(
            title="Ouvrir un fichier CSV de projet",
            filetypes=[("Fichier CSV", "*.csv")]
        )
        if not chemin:
            return
        try:
            df = pd.read_csv(chemin)
            if df.empty:
                raise ValueError("Le fichier CSV est vide.")
            data = df.iloc[0].to_dict()
            self._remplir_depuis_dict(data)
            self._reconstruire_onglets_entree()
            self._rafraichir_plots()
            self.chemin_fichier_courant = chemin
            self.modifie = False
            self._mettre_a_jour_titre_fenetre()
            self.journaliser(f"Fichier chargé: {chemin}")
            self.maj_statut("Fichier chargé.")
        except Exception as e:
            messagebox.showerror("Erreur d'ouverture", str(e))

    def action_enregistrer(self):
        if not self.chemin_fichier_courant:
            return self.action_enregistrer_sous()
        try:
            data = self._collecter_donnees()
            df = pd.DataFrame([data])
            df.to_csv(self.chemin_fichier_courant, index=False)
            self.modifie = False
            self._mettre_a_jour_titre_fenetre()
            self.journaliser(f"Enregistré: {self.chemin_fichier_courant}")
            self.maj_statut("Enregistré.")
        except Exception as e:
            messagebox.showerror("Erreur d'enregistrement", str(e))

    def action_enregistrer_sous(self):
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer sous (CSV)",
            defaultextension=".csv",
            filetypes=[("Fichier CSV", "*.csv")]
        )
        if not chemin:
            return
        self.chemin_fichier_courant = chemin
        self.action_enregistrer()

    def action_importer_csv(self):
        """Importe un CSV (mêmes colonnes que celles exportées par l'app)."""
        self.action_ouvrir()

    def action_exporter_csv(self):
        """Exporte l'état actuel vers CSV."""
        self.action_enregistrer_sous()

    # ----------------------------
    # Aides internes
    # ----------------------------
    def _marquer_modifie(self):
        if not self.modifie:
            self.modifie = True
            self._mettre_a_jour_titre_fenetre()

    def _mettre_a_jour_titre_fenetre(self):
        nom = os.path.basename(self.chemin_fichier_courant) if self.chemin_fichier_courant else "Sans titre"
        mod = "*" if self.modifie else ""
        self.title(f"{mod}{self.nom_projet.get()} - {nom} | Progiciel Dalot BA")

    def _avant_quitter(self):
        if self.modifie:
            if not messagebox.askyesno("Quitter", "Des modifications non enregistrées seront perdues. Quitter ?"):
                return
        self.destroy()


# ----------------------------
# Point d'entrée
# ----------------------------
def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()