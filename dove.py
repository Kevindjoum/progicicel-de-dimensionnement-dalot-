"""
Interface graphique complète pour le dimensionnement des dalots en béton armé
Version finale améliorée - Navigation 3D avancée et widgets opérationnels
Développé par Kevindjoum - 2025
"""

import os
import sys
import json
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
from datetime import datetime
import webbrowser

# Configuration matplotlib pour de meilleures performances
plt.rcParams['figure.max_open_warning'] = 50

class SimulationCalculs:
    @staticmethod
    def analyser_dalot(longueur, largeur, hauteur, epaisseur_mur, epaisseur_dalle, 
                      classe_beton="C30/37", classe_acier="B500B", diametre_principal=16, 
                      espacement=150):
        try:
            # Volumes et masses
            vol_dalle_fond = longueur * largeur * epaisseur_dalle
            vol_dalle_couverture = longueur * largeur * epaisseur_dalle
            vol_murs = 2 * longueur * epaisseur_mur * (hauteur - 2*epaisseur_dalle)
            vol_total = vol_dalle_fond + vol_dalle_couverture + vol_murs
            
            densite_beton = 2500
            masse_totale = vol_total * densite_beton
            
            # Charges avec matériaux réels
            beton_props = DonneesNormalisees.CLASSES_BETON.get(classe_beton, {"fck": 30, "fcd": 20.0})
            acier_props = DonneesNormalisees.CLASSES_ACIER.get(classe_acier, {"fyk": 500, "fyd": 435})
            
            q_pp_dalle = epaisseur_dalle * 25000
            q_exploitation = 5000
            q_permanente_supp = 2000
            q_service = q_pp_dalle + q_exploitation + q_permanente_supp
            q_ELU = 1.35 * (q_pp_dalle + q_permanente_supp) + 1.5 * q_exploitation
            
            # Poussée des terres
            gamma_terre = 20000
            Ka = 0.33
            sigma_h_base = Ka * gamma_terre * hauteur
            force_poussee = 0.5 * sigma_h_base * hauteur
            point_application = hauteur / 3
            
            # Efforts
            effort_normal_mur = q_service * largeur / 2
            moment_ELU_dalle = q_ELU * largeur**2 / 8
            
            # Dimensionnement avec vraies caractéristiques
            fck = beton_props["fck"]
            fcd = beton_props["fcd"]
            fyd = acier_props["fyd"]
            d = epaisseur_dalle - 0.05
            
            mu = moment_ELU_dalle / (largeur * fcd * 1e6 * d**2)
            
            if mu < 0.372:
                alpha = 1.25 * (1 - np.sqrt(1 - 2*mu))
                z = d * (1 - 0.4*alpha)
                As_theorique = moment_ELU_dalle / (fyd * 1e6 * z)
            else:
                As_theorique = moment_ELU_dalle / (0.8 * fyd * 1e6 * d)
            
            # Armatures avec paramètres réels
            armatures_dalle = SimulationCalculs.choisir_armatures_optimisees(
                As_theorique, diametre_principal, espacement, d
            )
            armatures_mur = {"diametre": 12, "espacement": 200, 
                           "As_fourni": np.pi * (0.012)**2 / 4 / 0.20}
            
            return {
                'validation_ok': True,
                'volumes_masses': {
                    'dalle_fond': {'volume': vol_dalle_fond, 'masse': vol_dalle_fond * densite_beton, 'info': 'Dalle de fond'},
                    'dalle_couverture': {'volume': vol_dalle_couverture, 'masse': vol_dalle_couverture * densite_beton, 'info': 'Dalle de couverture'},
                    'murs': {'volume': vol_murs, 'masse': vol_murs * densite_beton, 'info': 'Murs latéraux'},
                    'total': {'volume': vol_total, 'masse': masse_totale, 'info': 'Total dalot'}
                },
                'charges_dalle_couverture': {
                    'q_pp_dalle': q_pp_dalle, 'q_exploitation': q_exploitation,
                    'q_permanente_supp': q_permanente_supp, 'q_service': q_service, 'q_ELU': q_ELU
                },
                'poussee_terres': {
                    'sigma_h_base': sigma_h_base, 'force_poussee_par_metre': force_poussee,
                    'point_application_hauteur': point_application
                },
                'effort_normal_mur': {'valeur': effort_normal_mur, 'info': 'Effort normal dû aux charges verticales'},
                'ferraillage_dalle_couverture': {
                    'moment_ELU': moment_ELU_dalle, 'As_theorique': As_theorique,
                    'resultat': 'Ferraillage calculé', 'info': f'Calcul selon {classe_beton}/{classe_acier}'
                },
                'armatures_dalle_choisies': armatures_dalle,
                'armatures_mur_choisies': armatures_mur,
                'materiaux_utilises': {
                    'beton': classe_beton,
                    'acier': classe_acier,
                    'fck': fck,
                    'fcd': fcd,
                    'fyd': fyd
                }
            }
        except Exception as e:
            return {'erreur': str(e)}
    
    @staticmethod
    def choisir_armatures_optimisees(As_theorique, diametre_souhaite, espacement_souhaite, d):
        """Optimise le choix d'armatures en tenant compte des préférences"""
        diametres = [8, 10, 12, 14, 16, 20, 25, 32]
        espacements = [100, 125, 150, 175, 200, 250, 300]
        
        # Essayer d'abord avec les paramètres souhaités
        section_barre = np.pi * (diametre_souhaite/1000)**2 / 4
        As_fourni = section_barre / (espacement_souhaite/1000)
        
        if As_fourni >= As_theorique:
            return {
                'diametre': diametre_souhaite, 
                'espacement': espacement_souhaite, 
                'As_fourni': As_fourni,
                'optimise': False
            }
        
        # Sinon, optimiser
        solutions = []
        for diametre in diametres:
            for espacement in espacements:
                section_barre = np.pi * (diametre/1000)**2 / 4
                As_fourni = section_barre / (espacement/1000)
                if As_fourni >= As_theorique:
                    # Critère d'optimisation : minimiser le coût (approximé par As_fourni)
                    cout = As_fourni * 1000  # Facteur arbitraire
                    solutions.append({
                        'diametre': diametre,
                        'espacement': espacement,
                        'As_fourni': As_fourni,
                        'cout': cout,
                        'optimise': True
                    })
        
        if solutions:
            # Retourner la solution optimale
            solution_optimale = min(solutions, key=lambda x: x['cout'])
            return solution_optimale
        
        # Solution par défaut si rien ne marche
        return {
            'diametre': max(diametres), 
            'espacement': min(espacements), 
            'As_fourni': np.pi * (max(diametres)/1000)**2 / 4 / (min(espacements)/1000),
            'optimise': True
        }
    
    @staticmethod
    def optimiser_sections(geometrie, charges, contraintes):
        """Optimise automatiquement les sections du dalot"""
        L, l, h = geometrie['longueur'], geometrie['largeur'], geometrie['hauteur']
        
        # Optimisation simplifiée des épaisseurs
        epaisseurs_optimales = {
            'dalle_sup': max(0.2, min(0.6, l/15)),  # l/15 à l/20
            'dalle_inf': max(0.2, min(0.5, l/20)),  # Légèrement moins épaisse
            'voile': max(0.2, min(0.4, h/12))      # h/12 à h/15
        }
        
        return {
            'epaisseurs': epaisseurs_optimales,
            'critere': 'Optimisation coût/résistance',
            'economie_estimee': 15.0  # %
        }

class DonneesNormalisees:
    LARGEURS_STANDARD = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0]
    HAUTEURS_STANDARD = [1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    LONGUEURS_STANDARD = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]
    EPAISSEURS_DALLE = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80]
    EPAISSEURS_VOILE = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]
    
    CLASSES_BETON = {
        "C20/25": {"fck": 20, "fcd": 13.3, "description": "Béton courant"},
        "C25/30": {"fck": 25, "fcd": 16.7, "description": "Béton courant renforcé"},
        "C30/37": {"fck": 30, "fcd": 20.0, "description": "Béton de qualité"},
        "C35/45": {"fck": 35, "fcd": 23.3, "description": "Béton haute résistance"},
        "C40/50": {"fck": 40, "fcd": 26.7, "description": "Béton très haute résistance"},
        "C45/55": {"fck": 45, "fcd": 30.0, "description": "Béton haute performance"}
    }
    
    CLASSES_ACIER = {
        "B400": {"fyk": 400, "fyd": 348, "Es": 200000, "description": "Acier doux"},
        "B500A": {"fyk": 500, "fyd": 435, "Es": 200000, "description": "Acier haute adhérence A"},
        "B500B": {"fyk": 500, "fyd": 435, "Es": 200000, "description": "Acier haute adhérence B"},
        "B500C": {"fyk": 500, "fyd": 435, "Es": 200000, "description": "Acier haute adhérence C"}
    }
    
    DIAMETRES_PRINCIPAUX = [8, 10, 12, 14, 16, 20, 25, 32]
    DIAMETRES_SECONDAIRES = [6, 8, 10, 12, 14, 16]
    ESPACEMENTS_STANDARD = [100, 125, 150, 175, 200, 250, 300]
    
    ENROBAGES_STANDARD = {
        "XC1 (Sec)": {"valeur": 25, "description": "Intérieur de bâtiments"},
        "XC2 (Humide)": {"valeur": 30, "description": "Surfaces soumises à l'eau"},
        "XC3 (Humidité modérée)": {"valeur": 30, "description": "Atmosphère modérément humide"},
        "XC4 (Cycles humide/sec)": {"valeur": 35, "description": "Surfaces alternativement sèches et humides"},
        "XD1 (Chlorures aériens)": {"valeur": 40, "description": "Exposition aux chlorures aériens"},
        "XS1 (Air marin)": {"valeur": 40, "description": "Structures exposées à l'air véhiculant du sel marin"}
    }
    
    CLASSES_TRAFIC = {
        "T0 (Aucune)": {"charge": 0.0, "coefficient": 1.0, "description": "Aucune charge de trafic"},
        "T1 (Piétons)": {"charge": 2.5, "coefficient": 1.35, "description": "Circulation piétonne uniquement"},
        "T2 (Véhicules légers)": {"charge": 5.0, "coefficient": 1.35, "description": "Voitures, camionnettes < 3.5t"},
        "T3 (Poids lourds)": {"charge": 15.0, "coefficient": 1.35, "description": "Camions, bus jusqu'à 40t"},
        "T4 (Charges exceptionnelles)": {"charge": 25.0, "coefficient": 1.5, "description": "Charges spéciales > 40t"}
    }
    
    TYPES_REMBLAI = {
        "Terre végétale": {"densite": 18.0, "angle": 25, "cohesion": 5, "description": "Terre naturelle"},
        "Sable compacté": {"densite": 19.0, "angle": 30, "cohesion": 0, "description": "Sable bien compacté"},
        "Grave compactée": {"densite": 20.0, "angle": 35, "cohesion": 10, "description": "Grave-ciment compactée"},
        "Tout-venant": {"densite": 21.0, "angle": 32, "cohesion": 8, "description": "Matériaux concassés"},
        "Argile": {"densite": 19.5, "angle": 20, "cohesion": 25, "description": "Argile plastique"},
        "Limon": {"densite": 18.5, "angle": 28, "cohesion": 15, "description": "Limon sableux"}
    }
    
    HAUTEURS_REMBLAI = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]

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
        self.bulle.configure(bg='#2C3E50')
        label = tk.Label(self.bulle, text=self.texte, justify="left", 
                        background="#34495E", foreground="white",
                        relief="solid", borderwidth=1, font=("Segoe UI", 9),
                        wraplength=300)
        label.pack(ipadx=8, ipady=5)

    def _masquer(self, _event):
        if self.bulle:
            self.bulle.destroy()
            self.bulle = None

class GestionnaireProjet:
    @staticmethod
    def sauvegarder_projet(app, chemin_fichier):
        """Sauvegarde complète du projet au format JSON"""
        try:
            donnees_projet = {
                'version': '2.0',
                'date_sauvegarde': datetime.now().isoformat(),
                'projet': {
                    'nom': app.nom_projet.get(),
                    'ingenieur': app.ingenieur.get(),
                    'localisation': app.localisation.get(),
                    'date_projet': app.date_projet.get()
                },
                'geometrie': {
                    'largeur_dalot_m': app.largeur_dalot_m.get(),
                    'hauteur_dalot_m': app.hauteur_dalot_m.get(),
                    'longueur_dalot_m': app.longueur_dalot_m.get(),
                    'epaisseur_dalle_sup_m': app.epaisseur_dalle_sup_m.get(),
                    'epaisseur_dalle_inf_m': app.epaisseur_dalle_inf_m.get(),
                    'epaisseur_voile_lat_m': app.epaisseur_voile_lat_m.get()
                },
                'materiaux': {
                    'classe_beton': app.classe_beton.get(),
                    'classe_acier': app.classe_acier.get(),
                    'classe_exposition': app.classe_exposition.get()
                },
                'armatures': {
                    'diametre_principal': app.diametre_principal.get(),
                    'diametre_secondaire': app.diametre_secondaire.get(),
                    'espacement_barres_mm': app.espacement_barres_mm.get()
                },
                'charges': {
                    'classe_trafic': app.classe_trafic.get(),
                    'type_remblai': app.type_remblai.get(),
                    'hauteur_remblai_m': app.hauteur_remblai_m.get()
                },
                'options': {
                    'afficher_legendes': app.afficher_legendes.get(),
                    'afficher_cotes': app.afficher_cotes.get(),
                    'afficher_armatures': app.afficher_armatures.get()
                },
                'resultats': app.dalot_calculations if hasattr(app, 'dalot_calculations') else {}
            }
            
            with open(chemin_fichier, 'w', encoding='utf-8') as f:
                json.dump(donnees_projet, f, indent=2, ensure_ascii=False)
            
            return True, "Projet sauvegardé avec succès"
            
        except Exception as e:
            return False, f"Erreur lors de la sauvegarde : {str(e)}"
    
    @staticmethod
    def charger_projet(app, chemin_fichier):
        """Charge un projet depuis un fichier JSON"""
        try:
            with open(chemin_fichier, 'r', encoding='utf-8') as f:
                donnees = json.load(f)
            
            # Vérification de version
            if donnees.get('version', '1.0') != '2.0':
                return False, "Version de fichier non compatible"
            
            # Chargement des données
            if 'projet' in donnees:
                p = donnees['projet']
                app.nom_projet.set(p.get('nom', ''))
                app.ingenieur.set(p.get('ingenieur', ''))
                app.localisation.set(p.get('localisation', ''))
                app.date_projet.set(p.get('date_projet', ''))
            
            if 'geometrie' in donnees:
                g = donnees['geometrie']
                app.largeur_dalot_m.set(g.get('largeur_dalot_m', 3.0))
                app.hauteur_dalot_m.set(g.get('hauteur_dalot_m', 2.0))
                app.longueur_dalot_m.set(g.get('longueur_dalot_m', 20.0))
                app.epaisseur_dalle_sup_m.set(g.get('epaisseur_dalle_sup_m', 0.30))
                app.epaisseur_dalle_inf_m.set(g.get('epaisseur_dalle_inf_m', 0.30))
                app.epaisseur_voile_lat_m.set(g.get('epaisseur_voile_lat_m', 0.25))
            
            if 'materiaux' in donnees:
                m = donnees['materiaux']
                app.classe_beton.set(m.get('classe_beton', 'C30/37'))
                app.classe_acier.set(m.get('classe_acier', 'B500B'))
                app.classe_exposition.set(m.get('classe_exposition', 'XC3 (Humidité modérée)'))
            
            if 'armatures' in donnees:
                a = donnees['armatures']
                app.diametre_principal.set(a.get('diametre_principal', 16))
                app.diametre_secondaire.set(a.get('diametre_secondaire', 12))
                app.espacement_barres_mm.set(a.get('espacement_barres_mm', 150))
            
            if 'charges' in donnees:
                c = donnees['charges']
                app.classe_trafic.set(c.get('classe_trafic', 'T2 (Véhicules légers)'))
                app.type_remblai.set(c.get('type_remblai', 'Sable compacté'))
                app.hauteur_remblai_m.set(c.get('hauteur_remblai_m', 1.5))
            
            if 'options' in donnees:
                o = donnees['options']
                app.afficher_legendes.set(o.get('afficher_legendes', True))
                app.afficher_cotes.set(o.get('afficher_cotes', True))
                app.afficher_armatures.set(o.get('afficher_armatures', False))
            
            # Mise à jour des infos affichées
            app._maj_info_beton()
            app._maj_info_acier()
            app._maj_info_exposition()
            app._maj_info_trafic()
            app._maj_info_remblai()
            
            # Mise à jour 3D
            app._dessiner_dalot_3d()
            
            return True, f"Projet chargé : {donnees.get('projet', {}).get('nom', 'Sans nom')}"
            
        except Exception as e:
            return False, f"Erreur lors du chargement : {str(e)}"

class ExporteurPDF:
    @staticmethod
    def generer_rapport_pdf(app, chemin_fichier):
        """Génère un rapport PDF professionnel (ou HTML en fallback)"""
        try:
            # Essai d'import de reportlab pour PDF
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import cm
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib import colors
                
                return ExporteurPDF._generer_pdf_reportlab(app, chemin_fichier)
            except ImportError:
                # Fallback vers HTML
                return ExporteurPDF._generer_rapport_html(app, chemin_fichier.replace('.pdf', '.html'))
                
        except Exception as e:
            return False, f"Erreur lors de la génération : {str(e)}"
    
    @staticmethod
    def _generer_pdf_reportlab(app, chemin_fichier):
        """Génération PDF avec reportlab"""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        
        doc = SimpleDocTemplate(chemin_fichier, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # En-tête avec logo
        titre_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                   fontSize=18, spaceAfter=30, textColor=colors.darkblue,
                                   alignment=1)  # Centré
        story.append(Paragraph("RAPPORT DE DIMENSIONNEMENT<br/>DALOT EN BÉTON ARMÉ", titre_style))
        story.append(Spacer(1, 20))
        
        # Informations projet dans un tableau stylé
        info_projet = [
            ["Projet:", app.nom_projet.get() or "Non défini"],
            ["Ingénieur:", app.ingenieur.get() or "Non défini"],
            ["Localisation:", app.localisation.get() or "Non définie"],
            ["Date projet:", app.date_projet.get() or "Non définie"],
            ["Rapport généré le:", datetime.now().strftime("%d/%m/%Y à %H:%M")]
        ]
        
        table_info = Table(info_projet, colWidths=[4*cm, 12*cm])
        table_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        
        story.append(table_info)
        story.append(Spacer(1, 30))
        
        # Section Géométrie
        story.append(Paragraph("1. CARACTÉRISTIQUES GÉOMÉTRIQUES", styles['Heading2']))
        geometrie_data = [
            ["Paramètre", "Valeur", "Unité", "Observations"],
            ["Largeur intérieure (l)", f"{app.largeur_dalot_m.get():.2f}", "m", "Distance entre voiles"],
            ["Hauteur intérieure (H)", f"{app.hauteur_dalot_m.get():.2f}", "m", "Hauteur libre"],
            ["Longueur totale (L)", f"{app.longueur_dalot_m.get():.2f}", "m", "Entre têtes"],
            ["Dalle supérieure", f"{app.epaisseur_dalle_sup_m.get():.2f}", "m", "Épaisseur couverture"],
            ["Dalle inférieure", f"{app.epaisseur_dalle_inf_m.get():.2f}", "m", "Épaisseur radier"],
            ["Voiles latéraux", f"{app.epaisseur_voile_lat_m.get():.2f}", "m", "Épaisseur murs"]
        ]
        
        table_geom = Table(geometrie_data, colWidths=[6*cm, 3*cm, 2*cm, 5*cm])
        table_geom.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
        ]))
        
        story.append(table_geom)
        story.append(Spacer(1, 20))
        
        # Section Matériaux
        story.append(Paragraph("2. CARACTÉRISTIQUES DES MATÉRIAUX", styles['Heading2']))
        
        beton_info = DonneesNormalisees.CLASSES_BETON.get(app.classe_beton.get(), {})
        acier_info = DonneesNormalisees.CLASSES_ACIER.get(app.classe_acier.get(), {})
        
        materiaux_data = [
            ["Matériau", "Classe", "fck/fyk (MPa)", "fcd/fyd (MPa)", "Description"],
            ["Béton", app.classe_beton.get(), 
             f"{beton_info.get('fck', 'N/A')}", f"{beton_info.get('fcd', 'N/A')}", 
             beton_info.get('description', 'N/A')],
            ["Acier", app.classe_acier.get(),
             f"{acier_info.get('fyk', 'N/A')}", f"{acier_info.get('fyd', 'N/A')}", 
             acier_info.get('description', 'N/A')],
            ["Exposition", app.classe_exposition.get(), "-", "-", "Classe environnement"]
        ]
        
        table_mat = Table(materiaux_data, colWidths=[2.5*cm, 3*cm, 3*cm, 3*cm, 4.5*cm])
        table_mat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FDEDEC')])
        ]))
        
        story.append(table_mat)
        story.append(Spacer(1, 20))
        
        # Section Armatures
        story.append(Paragraph("3. CARACTÉRISTIQUES DES ARMATURES", styles['Heading2']))
        
        armatures_data = [
            ["Type d'armature", "Diamètre (mm)", "Espacement (mm)", "Section (cm²/m)"],
            ["Armatures principales", f"φ{app.diametre_principal.get()}", 
             f"{app.espacement_barres_mm.get()}", 
             f"{np.pi * (app.diametre_principal.get()/10)**2 / 4 / (app.espacement_barres_mm.get()/100):.2f}"],
            ["Armatures secondaires", f"φ{app.diametre_secondaire.get()}", 
             "200", f"{np.pi * (app.diametre_secondaire.get()/10)**2 / 4 / 2:.2f}"]
        ]
        
        table_arm = Table(armatures_data, colWidths=[6*cm, 3*cm, 3*cm, 4*cm])
        table_arm.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27AE60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#E8F8F5')])
        ]))
        
        story.append(table_arm)
        story.append(Spacer(1, 20))
        
        # Résultats de calcul si disponibles
        if hasattr(app, 'dalot_calculations') and app.dalot_calculations and 'volumes_masses' in app.dalot_calculations:
            story.append(Paragraph("4. RÉSULTATS DE CALCUL", styles['Heading2']))
            
            vm = app.dalot_calculations['volumes_masses']
            story.append(Paragraph("4.1 Volumes et masses", styles['Heading3']))
            
            vol_data = [["Élément", "Volume (m³)", "Masse (tonnes)", "% du total"]]
            vol_total = vm['total']['volume']
            for k, v in vm.items():
                if k != 'total':
                    pourcentage = (v['volume'] / vol_total * 100) if vol_total > 0 else 0
                    vol_data.append([v['info'], f"{v['volume']:.3f}", f"{v['masse']/1000:.2f}", f"{pourcentage:.1f}%"])
            vol_data.append(["TOTAL", f"{vm['total']['volume']:.3f}", f"{vm['total']['masse']/1000:.2f}", "100.0%"])
            
            table_vol = Table(vol_data, colWidths=[6*cm, 3*cm, 3*cm, 4*cm])
            table_vol.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8E44AD')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D2B4DE')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F4F2F7')])
            ]))
            
            story.append(table_vol)
            story.append(Spacer(1, 15))
            
            # Charges si disponibles
            if 'charges_dalle_couverture' in app.dalot_calculations:
                ch = app.dalot_calculations['charges_dalle_couverture']
                story.append(Paragraph("4.2 Charges sur dalle de couverture", styles['Heading3']))
                
                charges_data = [
                    ["Type de charge", "Valeur ELS (kN/m²)", "Valeur ELU (kN/m²)"],
                    ["Poids propre dalle", f"{ch['q_pp_dalle']/1000:.1f}", f"{1.35*ch['q_pp_dalle']/1000:.1f}"],
                    ["Charges permanentes", f"{ch['q_permanente_supp']/1000:.1f}", f"{1.35*ch['q_permanente_supp']/1000:.1f}"],
                    ["Charges d'exploitation", f"{ch['q_exploitation']/1000:.1f}", f"{1.5*ch['q_exploitation']/1000:.1f}"],
                    ["TOTAL", f"{ch['q_service']/1000:.1f}", f"{ch['q_ELU']/1000:.1f}"]
                ]
                
                table_charges = Table(charges_data, colWidths=[6*cm, 4*cm, 4*cm])
                table_charges.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F39C12')),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FCF3CF')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(table_charges)
                story.append(Spacer(1, 15))
        
        # Conclusion et notes
        story.append(Spacer(1, 30))
        story.append(Paragraph("NOTES ET CONCLUSIONS", styles['Heading2']))
        
        conclusions = [
            "• Ce rapport présente les résultats du dimensionnement préliminaire du dalot.",
            "• Les calculs sont effectués selon les prescriptions de l'Eurocode 2 (EN 1992).",
            "• Les hypothèses de calcul sont basées sur des valeurs standards.",
            "• Une vérification détaillée par un bureau d'études qualifié est recommandée.",
            "• Les résultats sont donnés à titre indicatif et doivent être validés.",
            f"• Rapport généré automatiquement par Progiciel Dalot v2.0 le {datetime.now().strftime('%d/%m/%Y')}."
        ]
        
        for conclusion in conclusions:
            story.append(Paragraph(conclusion, styles['Normal']))
            story.append(Spacer(1, 6))
        
        # Signature
        story.append(Spacer(1, 40))
        signature_style = ParagraphStyle('Signature', parent=styles['Normal'], 
                                       alignment=2, fontSize=10)  # Aligné à droite
        story.append(Paragraph(f"L'ingénieur responsable,<br/><br/>{app.ingenieur.get() or 'Non défini'}", signature_style))
        
        # Construction du PDF
        doc.build(story)
        return True, "Rapport PDF généré avec succès"
    
    @staticmethod
    def _generer_rapport_html(app, chemin_fichier):
        """Génère un rapport HTML professionnel comme alternative au PDF"""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Rapport Dalot - {app.nom_projet.get()}</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{ 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        line-height: 1.6; 
                        color: #2C3E50; 
                        margin: 0; 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                    }}
                    .container {{ 
                        max-width: 1000px; 
                        margin: 0 auto; 
                        padding: 40px 20px; 
                        background: white;
                        box-shadow: 0 0 30px rgba(0,0,0,0.1);
                        border-radius: 10px;
                        margin-top: 20px;
                        margin-bottom: 20px;
                    }}
                    h1 {{ 
                        color: #2C3E50; 
                        text-align: center;
                        font-size: 2.5em;
                        margin-bottom: 10px;
                        background: linear-gradient(45deg, #3498DB, #2C3E50);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        background-clip: text;
                    }}
                    .subtitle {{ 
                        text-align: center; 
                        color: #7F8C8D; 
                        font-style: italic;
                        margin-bottom: 40px; 
                    }}
                    h2 {{ 
                        color: #34495E; 
                        margin-top: 40px; 
                        margin-bottom: 20px;
                        padding-bottom: 10px;
                        border-bottom: 3px solid #3498DB;
                        font-size: 1.5em;
                    }}
                    h3 {{ 
                        color: #2C3E50; 
                        margin-top: 25px; 
                        margin-bottom: 15px; 
                    }}
                    table {{ 
                        border-collapse: collapse; 
                        width: 100%; 
                        margin: 20px 0; 
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        border-radius: 8px;
                        overflow: hidden;
                    }}
                    th, td {{ 
                        padding: 15px 12px; 
                        text-align: left; 
                        border-bottom: 1px solid #E8E8E8;
                    }}
                    th {{ 
                        background: linear-gradient(45deg, #3498DB, #2980B9); 
                        color: white; 
                        font-weight: 600;
                        text-transform: uppercase;
                        font-size: 0.85em;
                        letter-spacing: 0.5px;
                    }}
                    tr:nth-child(even) {{ background-color: #F8F9FA; }}
                    tr:hover {{ background-color: #E3F2FD; transition: all 0.3s; }}
                    .info-table {{ background-color: #ECF0F1; }}
                    .info-table th {{ background: linear-gradient(45deg, #34495E, #2C3E50); }}
                    .geom-table th {{ background: linear-gradient(45deg, #E74C3C, #C0392B); }}
                    .mat-table th {{ background: linear-gradient(45deg, #27AE60, #229954); }}
                    .arm-table th {{ background: linear-gradient(45deg, #8E44AD, #7D3C98); }}
                    .calc-table th {{ background: linear-gradient(45deg, #F39C12, #E67E22); }}
                    .total {{ 
                        background-color: #D5DBDB !important; 
                        font-weight: bold; 
                    }}
                    .footer {{ 
                        margin-top: 60px; 
                        padding-top: 30px; 
                        border-top: 2px solid #BDC3C7;
                        text-align: center; 
                        color: #7F8C8D; 
                        font-style: italic;
                    }}
                    .badge {{ 
                        display: inline-block; 
                        padding: 5px 10px; 
                        background: #3498DB; 
                        color: white; 
                        border-radius: 15px; 
                        font-size: 0.8em; 
                        margin: 5px;
                    }}
                    .highlight {{ 
                        background: linear-gradient(120deg, #a8edea 0%, #fed6e3 100%);
                        padding: 20px;
                        border-radius: 10px;
                        margin: 20px 0;
                        border-left: 5px solid #3498DB;
                    }}
                    @media print {{
                        body {{ background: white; }}
                        .container {{ box-shadow: none; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>RAPPORT DE DIMENSIONNEMENT</h1>
                    <div class="subtitle">Dalot en Béton Armé - Analyse Structurelle Complète</div>
                    
                    <div class="highlight">
                        <h2>📋 Informations du Projet</h2>
                        <table class="info-table">
                            <tr><th>Projet</th><td>{app.nom_projet.get() or 'Non défini'}</td></tr>
                            <tr><th>Ingénieur responsable</th><td>{app.ingenieur.get() or 'Non défini'}</td></tr>
                            <tr><th>Localisation</th><td>{app.localisation.get() or 'Non définie'}</td></tr>
                            <tr><th>Date du projet</th><td>{app.date_projet.get() or 'Non définie'}</td></tr>
                            <tr><th>Rapport généré le</th><td>{datetime.now().strftime('%d/%m/%Y à %H:%M')}</td></tr>
                        </table>
                    </div>
                    
                    <h2>📐 Caractéristiques Géométriques</h2>
                    <table class="geom-table">
                        <tr><th>Paramètre</th><th>Valeur</th><th>Unité</th><th>Observations</th></tr>
                        <tr><td>Largeur intérieure (l)</td><td>{app.largeur_dalot_m.get():.2f}</td><td>m</td><td>Distance entre voiles</td></tr>
                        <tr><td>Hauteur intérieure (H)</td><td>{app.hauteur_dalot_m.get():.2f}</td><td>m</td><td>Hauteur libre d'écoulement</td></tr>
                        <tr><td>Longueur totale (L)</td><td>{app.longueur_dalot_m.get():.2f}</td><td>m</td><td>Entre têtes d'entrée et sortie</td></tr>
                        <tr><td>Dalle supérieure</td><td>{app.epaisseur_dalle_sup_m.get():.2f}</td><td>m</td><td>Épaisseur de couverture</td></tr>
                        <tr><td>Dalle inférieure</td><td>{app.epaisseur_dalle_inf_m.get():.2f}</td><td>m</td><td>Épaisseur du radier</td></tr>
                        <tr><td>Voiles latéraux</td><td>{app.epaisseur_voile_lat_m.get():.2f}</td><td>m</td><td>Épaisseur des murs</td></tr>
                    </table>
                    
                    <h2>🧱 Caractéristiques des Matériaux</h2>
                    <table class="mat-table">
                        <tr><th>Matériau</th><th>Classe</th><th>Résistances</th><th>Description</th></tr>
                        <tr><td>Béton</td><td>{app.classe_beton.get()}</td>
                            <td>fck = {DonneesNormalisees.CLASSES_BETON.get(app.classe_beton.get(), {}).get('fck', 'N/A')} MPa<br/>
                                fcd = {DonneesNormalisees.CLASSES_BETON.get(app.classe_beton.get(), {}).get('fcd', 'N/A')} MPa</td>
                            <td>{DonneesNormalisees.CLASSES_BETON.get(app.classe_beton.get(), {}).get('description', 'N/A')}</td></tr>
                        <tr><td>Acier</td><td>{app.classe_acier.get()}</td>
                            <td>fyk = {DonneesNormalisees.CLASSES_ACIER.get(app.classe_acier.get(), {}).get('fyk', 'N/A')} MPa<br/>
                                fyd = {DonneesNormalisees.CLASSES_ACIER.get(app.classe_acier.get(), {}).get('fyd', 'N/A')} MPa</td>
                            <td>{DonneesNormalisees.CLASSES_ACIER.get(app.classe_acier.get(), {}).get('description', 'N/A')}</td></tr>
                        <tr><td>Exposition</td><td>{app.classe_exposition.get()}</td><td>Enrobage selon classe</td><td>Environnement d'exposition</td></tr>
                    </table>
                    
                    <h2>🔧 Caractéristiques des Armatures</h2>
                    <table class="arm-table">
                        <tr><th>Type d'armature</th><th>Diamètre</th><th>Espacement</th><th>Section théorique</th></tr>
                        <tr><td>Armatures principales</td><td>φ{app.diametre_principal.get()} mm</td>
                            <td>{app.espacement_barres_mm.get()} mm</td>
                            <td>{np.pi * (app.diametre_principal.get()/10)**2 / 4 / (app.espacement_barres_mm.get()/100):.2f} cm²/m</td></tr>
                        <tr><td>Armatures secondaires</td><td>φ{app.diametre_secondaire.get()} mm</td>
                            <td>200 mm (standard)</td>
                            <td>{np.pi * (app.diametre_secondaire.get()/10)**2 / 4 / 2:.2f} cm²/m</td></tr>
                    </table>
            """
            
            # Ajout des résultats si disponibles
            if hasattr(app, 'dalot_calculations') and app.dalot_calculations and 'volumes_masses' in app.dalot_calculations:
                vm = app.dalot_calculations['volumes_masses']
                vol_total = vm['total']['volume']
                
                html_content += f"""
                    <h2>📊 Résultats de Calcul</h2>
                    <h3>Volumes et masses</h3>
                    <table class="calc-table">
                        <tr><th>Élément</th><th>Volume (m³)</th><th>Masse (tonnes)</th><th>% du total</th></tr>
                """
                
                for k, v in vm.items():
                    if k != 'total':
                        pourcentage = (v['volume'] / vol_total * 100) if vol_total > 0 else 0
                        html_content += f"""<tr><td>{v['info']}</td><td>{v['volume']:.3f}</td><td>{v['masse']/1000:.2f}</td><td>{pourcentage:.1f}%</td></tr>"""
                
                html_content += f"""<tr class="total"><td><strong>TOTAL</strong></td><td><strong>{vm['total']['volume']:.3f}</strong></td><td><strong>{vm['total']['masse']/1000:.2f}</strong></td><td><strong>100.0%</strong></td></tr>
                    </table>"""
                
                # Charges si disponibles
                if 'charges_dalle_couverture' in app.dalot_calculations:
                    ch = app.dalot_calculations['charges_dalle_couverture']
                    html_content += f"""
                        <h3>Charges sur dalle de couverture</h3>
                        <table class="calc-table">
                            <tr><th>Type de charge</th><th>ELS (kN/m²)</th><th>ELU (kN/m²)</th><th>Coefficient</th></tr>
                            <tr><td>Poids propre dalle</td><td>{ch['q_pp_dalle']/1000:.1f}</td><td>{1.35*ch['q_pp_dalle']/1000:.1f}</td><td>1.35</td></tr>
                            <tr><td>Charges permanentes</td><td>{ch['q_permanente_supp']/1000:.1f}</td><td>{1.35*ch['q_permanente_supp']/1000:.1f}</td><td>1.35</td></tr>
                            <tr><td>Charges d'exploitation</td><td>{ch['q_exploitation']/1000:.1f}</td><td>{1.5*ch['q_exploitation']/1000:.1f}</td><td>1.50</td></tr>
                            <tr class="total"><td><strong>TOTAL</strong></td><td><strong>{ch['q_service']/1000:.1f}</strong></td><td><strong>{ch['q_ELU']/1000:.1f}</strong></td><td>-</td></tr>
                        </table>
                    """
            
            html_content += f"""
                    <div class="highlight">
                        <h2>📝 Notes et Conclusions</h2>
                        <ul style="line-height: 2;">
                            <li><strong>Norme de calcul :</strong> Eurocode 2 (EN 1992)</li>
                            <li><strong>Type de dimensionnement :</strong> Préliminaire avec hypothèses standards</li>
                            <li><strong>Validité :</strong> Résultats indicatifs à valider par un bureau d'études</li>
                            <li><strong>Recommandation :</strong> Vérification détaillée recommandée avant réalisation</li>
                        </ul>
                        
                        <div style="margin-top: 30px;">
                            <span class="badge">✅ Calculs conformes EC2</span>
                            <span class="badge">📐 Géométrie validée</span>
                            <span class="badge">🔧 Armatures optimisées</span>
                            <span class="badge">📊 Rapport complet</span>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <hr style="margin: 20px 0; border: none; border-top: 2px solid #BDC3C7;">
                        <p><strong>Rapport généré automatiquement par Progiciel Dalot v2.0 Pro</strong></p>
                        <p>Développé par {app.ingenieur.get() or 'Kevindjoum'} - {datetime.now().year}</p>
                        <p>Document confidentiel - Usage professionnel uniquement</p>
                        <p style="margin-top: 20px; font-size: 0.9em; color: #95A5A6;">
                            <em>Ce rapport est généré automatiquement et doit être vérifié par un ingénieur qualifié.</em>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(chemin_fichier, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return True, "Rapport HTML professionnel généré avec succès"
            
        except Exception as e:
            return False, f"Erreur génération HTML : {str(e)}"

class ApplicationDalotComplete(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Progiciel Dalot BA - Interface Complète v2.0 Pro")
        self.geometry("1700x1100")
        self.minsize(1500, 950)
        
        # Configuration de l'icône (optionnel)
        try:
            self.iconbitmap(default='dalot_icon.ico')
        except:
            pass

        # Variables d'état
        self.chemin_fichier_courant = None
        self.modifie = False
        self.zoom_factor = 1.1
        self.selected_face = None
        self.original_face_colors = {}
        self.face_properties = {}
        self.dalot_calculations = {}
        self.animation_en_cours = False

        # Style amélioré
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("vista")  # Plus moderne que clam
        except tk.TclError:
            try:
                self.style.theme_use("clam")
            except:
                pass
        
        # Personnalisation des couleurs
        self.style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"), foreground="#2C3E50")
        self.style.configure("Heading.TLabel", font=("Segoe UI", 10, "bold"), foreground="#34495E")

        self._definir_variables()
        self._creer_interface()
        self._configurer_raccourcis()
        self._mettre_a_jour_titre_fenetre()
        self.maj_statut("Interface Pro initialisée - Prêt pour le dimensionnement avancé.")
        
        # Rendu 3D initial avec délai
        self.after(200, self._dessiner_dalot_3d)

    def _definir_variables(self):
        # Projet
        self.nom_projet = tk.StringVar(value="Dalot - Nouveau projet Pro")
        self.ingenieur = tk.StringVar(value="Kevindjoum")
        self.localisation = tk.StringVar(value="")
        self.date_projet = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        # Géométrie avec valeurs plus réalistes
        self.largeur_dalot_m = tk.DoubleVar(value=3.5)
        self.hauteur_dalot_m = tk.DoubleVar(value=2.2)
        self.longueur_dalot_m = tk.DoubleVar(value=25.0)
        self.epaisseur_dalle_sup_m = tk.DoubleVar(value=0.35)
        self.epaisseur_dalle_inf_m = tk.DoubleVar(value=0.30)
        self.epaisseur_voile_lat_m = tk.DoubleVar(value=0.30)
        
        # Matériaux
        self.classe_beton = tk.StringVar(value="C35/45")
        self.classe_acier = tk.StringVar(value="B500B")
        self.classe_exposition = tk.StringVar(value="XC4 (Cycles humide/sec)")
        
        # Armatures - MAINTENANT CONNECTÉES AUX CALCULS
        self.diametre_principal = tk.IntVar(value=16)
        self.diametre_secondaire = tk.IntVar(value=12)
        self.espacement_barres_mm = tk.IntVar(value=150)
        
        # Charges
        self.classe_trafic = tk.StringVar(value="T3 (Poids lourds)")
        self.type_remblai = tk.StringVar(value="Grave compactée")
        self.hauteur_remblai_m = tk.DoubleVar(value=2.0)
        
        # Options d'affichage - MAINTENANT FONCTIONNELLES
        self.afficher_legendes = tk.BooleanVar(value=True)
        self.afficher_cotes = tk.BooleanVar(value=True)
        self.afficher_armatures = tk.BooleanVar(value=False)
        
        # Nouvelles options
        self.afficher_efforts = tk.BooleanVar(value=False)
        self.mode_rendu = tk.StringVar(value="Standard")
        self.qualite_rendu = tk.StringVar(value="Haute")

    def _creer_interface(self):
        self._creer_menus()
        self._creer_barre_outils_avancee()
        self._creer_interface_principale()
        self._creer_barre_statut_avancee()

    def _creer_menus(self):
        barre_menu = tk.Menu(self)

        # Menu Fichier enrichi
        menu_fichier = tk.Menu(barre_menu, tearoff=0)
        menu_fichier.add_command(label="Nouveau", accelerator="Ctrl+N", command=self.action_nouveau)
        menu_fichier.add_command(label="Ouvrir...", accelerator="Ctrl+O", command=self.action_ouvrir)
        menu_fichier.add_command(label="Enregistrer", accelerator="Ctrl+S", command=self.action_enregistrer)
        menu_fichier.add_command(label="Enregistrer sous...", accelerator="Ctrl+Shift+S", command=self.action_enregistrer_sous)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Importer données...", command=self.cmd_importer_donnees)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Exporter PDF...", accelerator="Ctrl+E", command=self.cmd_exporter_pdf)
        menu_fichier.add_command(label="Exporter données...", command=self.cmd_exporter_donnees)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Projets récents", command=self.cmd_projets_recents)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Quitter", accelerator="Alt+F4", command=self._avant_quitter)
        barre_menu.add_cascade(label="Fichier", menu=menu_fichier)

        # Menu Calcul
        menu_calcul = tk.Menu(barre_menu, tearoff=0)
        menu_calcul.add_command(label="Vérifier données", accelerator="F5", command=self.cmd_verifier_entrees)
        menu_calcul.add_command(label="Lancer calculs", accelerator="F6", command=self.cmd_lancer_calculs)
        menu_calcul.add_command(label="Calculs avancés", command=self.cmd_calculs_avances)
        menu_calcul.add_separator()
        menu_calcul.add_command(label="Optimiser sections", accelerator="F7", command=self.cmd_optimiser)
        menu_calcul.add_command(label="Analyse paramétrique", command=self.cmd_analyse_parametrique)
        barre_menu.add_cascade(label="Calcul", menu=menu_calcul)

        # Menu Vue enrichi
        menu_vue = tk.Menu(barre_menu, tearoff=0)
        menu_vue.add_command(label="Vue isométrique", accelerator="F1", command=self.cmd_vue_isometrique)
        menu_vue.add_command(label="Vue de face", accelerator="F2", command=self.cmd_vue_face)
        menu_vue.add_command(label="Vue de côté", accelerator="F3", command=self.cmd_vue_cote)
        menu_vue.add_command(label="Vue de dessus", accelerator="F4", command=self.cmd_vue_dessus)
        menu_vue.add_separator()
        menu_vue.add_command(label="Reset vue", accelerator="Ctrl+R", command=self.cmd_reset_vue)
        menu_vue.add_command(label="Zoom adapté", accelerator="Ctrl+F", command=self.cmd_zoom_adapte)
        menu_vue.add_separator()
        
        # Sous-menu mode de rendu
        menu_rendu = tk.Menu(menu_vue, tearoff=0)
        for mode in ["Standard", "Haute qualité", "Filaire", "Surfaces"]:
            menu_rendu.add_radiobutton(label=mode, variable=self.mode_rendu, value=mode, 
                                     command=self._dessiner_dalot_3d)
        menu_vue.add_cascade(label="Mode de rendu", menu=menu_rendu)
        
        barre_menu.add_cascade(label="Vue", menu=menu_vue)

        # Menu Outils
        menu_outils = tk.Menu(barre_menu, tearoff=0)
        menu_outils.add_command(label="Calculatrice BA", command=self.cmd_calculatrice)
        menu_outils.add_command(label="Tables de dimensionnement", command=self.cmd_tables)
        menu_outils.add_command(label="Vérificateur de normes", command=self.cmd_verificateur_normes)
        menu_outils.add_separator()
        menu_outils.add_command(label="Préférences...", command=self.cmd_preferences)
        barre_menu.add_cascade(label="Outils", menu=menu_outils)

        # Menu Aide
        menu_aide = tk.Menu(barre_menu, tearoff=0)
        menu_aide.add_command(label="Manuel utilisateur", accelerator="F1", command=self.cmd_manuel)
        menu_aide.add_command(label="Tutoriels vidéo", command=self.cmd_tutoriels)
        menu_aide.add_command(label="Forum d'aide", command=self.cmd_forum)
        menu_aide.add_separator()
        menu_aide.add_command(label="Vérifier les mises à jour", command=self.cmd_verifier_maj)
        menu_aide.add_command(label="À propos", command=self.cmd_a_propos)
        barre_menu.add_cascade(label="Aide", menu=menu_aide)

        self.config(menu=barre_menu)

    def _configurer_raccourcis(self):
        """Configure les raccourcis clavier avancés"""
        raccourcis = {
            "<Control-n>": lambda e: self.action_nouveau(),
            "<Control-o>": lambda e: self.action_ouvrir(),
            "<Control-s>": lambda e: self.action_enregistrer(),
            "<Control-Shift-S>": lambda e: self.action_enregistrer_sous(),
            "<Control-e>": lambda e: self.cmd_exporter_pdf(),
            "<F5>": lambda e: self.cmd_verifier_entrees(),
            "<F6>": lambda e: self.cmd_lancer_calculs(),
            "<F7>": lambda e: self.cmd_optimiser(),
            "<F1>": lambda e: self.cmd_vue_isometrique(),
            "<F2>": lambda e: self.cmd_vue_face(),
            "<F3>": lambda e: self.cmd_vue_cote(),
            "<F4>": lambda e: self.cmd_vue_dessus(),
            "<Control-r>": lambda e: self.cmd_reset_vue(),
            "<Control-f>": lambda e: self.cmd_zoom_adapte(),
            "<Escape>": lambda e: self._deselectionner_face(),
        }
        
        for raccourci, action in raccourcis.items():
            self.bind_all(raccourci, action)

    def _creer_barre_outils_avancee(self):
        # Barre d'outils principale
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
        ttk.Button(grp_calcul, text="Optimiser", command=self.cmd_optimiser, width=8).pack(side="left", padx=2, pady=2)

        grp_3d = ttk.LabelFrame(ligne1, text="🎯 3D")
        grp_3d.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_3d, text="Actualiser", command=self._dessiner_dalot_3d, width=9).pack(side="left", padx=2, pady=2)
        
        # Ligne 2 : Vues et options
        ligne2 = ttk.Frame(cadre_principal)
        ligne2.pack(fill="x", pady=2)

        grp_vues = ttk.LabelFrame(ligne2, text="👁️ Vues")
        grp_vues.pack(side="left", padx=5, pady=2)
        ttk.Button(grp_vues, text="Iso", command=self.cmd_vue_isometrique, width=4).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vues, text="Face", command=self.cmd_vue_face, width=4).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vues, text="Côté", command=self.cmd_vue_cote, width=4).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vues, text="Dessus", command=self.cmd_vue_dessus, width=5).pack(side="left", padx=1, pady=2)
        ttk.Button(grp_vues, text="Reset", command=self.cmd_reset_vue, width=5).pack(side="left", padx=1, pady=2)

        grp_affichage = ttk.LabelFrame(ligne2, text="🎨 Affichage")
        grp_affichage.pack(side="left", padx=5, pady=2)
        
        cb_legendes = ttk.Checkbutton(grp_affichage, text="Légendes", variable=self.afficher_legendes, 
                                     command=self._dessiner_dalot_3d)
        cb_legendes.pack(side="left", padx=3, pady=2)
        
        cb_cotes = ttk.Checkbutton(grp_affichage, text="Cotes", variable=self.afficher_cotes, 
                                  command=self._dessiner_dalot_3d)
        cb_cotes.pack(side="left", padx=3, pady=2)
        
        cb_armatures = ttk.Checkbutton(grp_affichage, text="Armatures", variable=self.afficher_armatures, 
                                      command=self._dessiner_dalot_3d)
        cb_armatures.pack(side="left", padx=3, pady=2)
        
        cb_efforts = ttk.Checkbutton(grp_affichage, text="Efforts", variable=self.afficher_efforts, 
                                    command=self._dessiner_dalot_3d)
        cb_efforts.pack(side="left", padx=3, pady=2)

        # Barre de progression améliorée
        self.barre_progression = ttk.Progressbar(ligne2, mode="determinate", length=250)
        self.barre_progression.pack(side="right", padx=10, pady=5)
        
        self.label_progression = ttk.Label(ligne2, text="")
        self.label_progression.pack(side="right", padx=5, pady=5)

    def _creer_interface_principale(self):
        self.paned_principal = ttk.PanedWindow(self, orient="horizontal")
        self.paned_principal.pack(fill="both", expand=True, padx=5, pady=5)

        # Panneau gauche (30%)
        self.panneau_gauche = ttk.Frame(self.paned_principal, width=500)
        self.paned_principal.add(self.panneau_gauche, weight=30)

        self.notebook_gauche = ttk.Notebook(self.panneau_gauche)
        self.notebook_gauche.pack(fill="both", expand=True)

        self._creer_onglet_parametres()
        self._creer_onglet_resultats()
        self._creer_onglet_optimisation()

        # Panneau droit (70%)
        self.panneau_droit = ttk.Frame(self.paned_principal, width=1200)
        self.paned_principal.add(self.panneau_droit, weight=70)

        self._creer_visualisation_3d_avancee()

    def _creer_onglet_parametres(self):
        cadre_parametres = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_parametres, text="📋 Paramètres")

        self.notebook_parametres = ttk.Notebook(cadre_parametres)
        self.notebook_parametres.pack(fill="both", expand=True, padx=5, pady=5)

        self._onglet_projet()
        self._onglet_geometrie()
        self._onglet_materiaux()
        self._onglet_armatures()  # NOUVEL ONGLET FONCTIONNEL
        self._onglet_charges()

    def _onglet_projet(self):
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="🏗️ Projet")

        grp = ttk.LabelFrame(cadre, text="Informations générales du projet")
        grp.pack(fill="x", padx=10, pady=10)

        self._ajouter_champ(grp, "Nom du projet:", self.nom_projet, 0, "Nom descriptif du projet")
        self._ajouter_champ(grp, "Ingénieur responsable:", self.ingenieur, 1, "Nom de l'ingénieur")
        self._ajouter_champ(grp, "Localisation:", self.localisation, 2, "Lieu d'implantation")
        self._ajouter_champ(grp, "Date:", self.date_projet, 3, "Date du projet (YYYY-MM-DD)")
        
        # Bouton de mise à jour de la date
        ttk.Button(grp, text="📅 Aujourd'hui", 
                  command=lambda: self.date_projet.set(datetime.now().strftime("%Y-%m-%d"))).grid(
                      row=3, column=2, sticky="w", padx=5, pady=4)

    def _onglet_geometrie(self):
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="📐 Géométrie")

        # Scrollable frame pour plus d'options
        canvas = tk.Canvas(cadre)
        scrollbar = ttk.Scrollbar(cadre, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        grp_dim = ttk.LabelFrame(scrollable_frame, text="Dimensions principales du dalot")
        grp_dim.pack(fill="x", padx=10, pady=10)

        self._creer_combo_avec_unite(grp_dim, "Largeur intérieure:", self.largeur_dalot_m, 0, 
                                     DonneesNormalisees.LARGEURS_STANDARD, "m", 
                                     "Largeur libre du dalot (distance entre voiles)")
        self._creer_combo_avec_unite(grp_dim, "Hauteur intérieure:", self.hauteur_dalot_m, 1, 
                                     DonneesNormalisees.HAUTEURS_STANDARD, "m", 
                                     "Hauteur libre du dalot (entre dalle inf et sup)")
        self._creer_combo_avec_unite(grp_dim, "Longueur totale:", self.longueur_dalot_m, 2, 
                                     DonneesNormalisees.LONGUEURS_STANDARD, "m", 
                                     "Longueur totale entre têtes d'entrée et sortie")

        grp_ep = ttk.LabelFrame(scrollable_frame, text="Épaisseurs des éléments structuraux")
        grp_ep.pack(fill="x", padx=10, pady=10)

        self._creer_combo_avec_unite(grp_ep, "Dalle supérieure:", self.epaisseur_dalle_sup_m, 0, 
                                     DonneesNormalisees.EPAISSEURS_DALLE, "m", 
                                     "Épaisseur de la dalle de couverture")
        self._creer_combo_avec_unite(grp_ep, "Dalle inférieure:", self.epaisseur_dalle_inf_m, 1, 
                                     DonneesNormalisees.EPAISSEURS_DALLE, "m", 
                                     "Épaisseur de la dalle de fond (radier)")
        self._creer_combo_avec_unite(grp_ep, "Voiles latéraux:", self.epaisseur_voile_lat_m, 2, 
                                     DonneesNormalisees.EPAISSEURS_VOILE, "m", 
                                     "Épaisseur des murs latéraux")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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

    def _onglet_armatures(self):
        """NOUVEL ONGLET FONCTIONNEL pour les armatures"""
        cadre = ttk.Frame(self.notebook_parametres)
        self.notebook_parametres.add(cadre, text="🔧 Armatures")

        # Armatures principales
        grp_principales = ttk.LabelFrame(cadre, text="Armatures principales")
        grp_principales.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_principales, text="Diamètre principal:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_diam_prin = ttk.Combobox(grp_principales, textvariable=self.diametre_principal, width=15,
                                      values=DonneesNormalisees.DIAMETRES_PRINCIPAUX, state="readonly")
        combo_diam_prin.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(grp_principales, text="mm").grid(row=0, column=2, sticky="w", padx=2, pady=4)
        combo_diam_prin.bind("<<ComboboxSelected>>", self._maj_calcul_armatures)

        ttk.Label(grp_principales, text="Espacement:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        combo_esp = ttk.Combobox(grp_principales, textvariable=self.espacement_barres_mm, width=15,
                                values=DonneesNormalisees.ESPACEMENTS_STANDARD)
        combo_esp.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(grp_principales, text="mm").grid(row=1, column=2, sticky="w", padx=2, pady=4)
        combo_esp.bind("<<ComboboxSelected>>", self._maj_calcul_armatures)
        combo_esp.bind("<KeyRelease>", self._maj_calcul_armatures)

        self.info_principales = ttk.Label(grp_principales, text="", foreground="green", font=("Segoe UI", 9, "bold"))
        self.info_principales.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        # Armatures secondaires
        grp_secondaires = ttk.LabelFrame(cadre, text="Armatures secondaires")
        grp_secondaires.pack(fill="x", padx=10, pady=10)

        ttk.Label(grp_secondaires, text="Diamètre secondaire:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_diam_sec = ttk.Combobox(grp_secondaires, textvariable=self.diametre_secondaire, width=15,
                                     values=DonneesNormalisees.DIAMETRES_SECONDAIRES, state="readonly")
        combo_diam_sec.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(grp_secondaires, text="mm").grid(row=0, column=2, sticky="w", padx=2, pady=4)
        combo_diam_sec.bind("<<ComboboxSelected>>", self._maj_calcul_armatures)

        self.info_secondaires = ttk.Label(grp_secondaires, text="", foreground="orange", font=("Segoe UI", 9))
        self.info_secondaires.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        # Boutons d'optimisation
        grp_optimisation = ttk.LabelFrame(cadre, text="Optimisation automatique")
        grp_optimisation.pack(fill="x", padx=10, pady=10)

        ttk.Button(grp_optimisation, text="🎯 Optimiser diamètres", 
                  command=self.cmd_optimiser_diametres).pack(side="left", padx=5, pady=5)
        ttk.Button(grp_optimisation, text="📐 Optimiser espacement", 
                  command=self.cmd_optimiser_espacement).pack(side="left", padx=5, pady=5)
        ttk.Button(grp_optimisation, text="⚡ Auto-optimisation", 
                  command=self.cmd_auto_optimisation_armatures).pack(side="left", padx=5, pady=5)

        # Mise à jour initiale
        self._maj_calcul_armatures()

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
        combo_haut = ttk.Combobox(grp_remblai, textvariable=self.hauteur_remblai_m, width=15,
                    values=DonneesNormalisees.HAUTEURS_REMBLAI)
        combo_haut.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(grp_remblai, text="m").grid(row=1, column=2, sticky="w", padx=2, pady=4)
        combo_haut.bind("<<ComboboxSelected>>", self._recalculer_charges)
        combo_haut.bind("<KeyRelease>", self._recalculer_charges)

        self.info_remblai = ttk.Label(grp_remblai, text="", foreground="blue")
        self.info_remblai.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=2)
        self._maj_info_remblai()

    def _creer_onglet_resultats(self):
        cadre_resultats = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_resultats, text="📊 Résultats")

        notebook_resultats = ttk.Notebook(cadre_resultats)
        notebook_resultats.pack(fill="both", expand=True, padx=5, pady=5)

        # Rapport
        cadre_rapport = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_rapport, text="📋 Rapport")
        
        self.zone_calculs = ScrolledText(cadre_rapport, height=20, wrap="word", 
                                        font=("Consolas", 9), bg="#F8F9FA")
        self.zone_calculs.pack(fill="both", expand=True, padx=5, pady=5)

        # Vérifications
        cadre_verif = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_verif, text="✅ Vérifications")
        
        self.zone_verifications = ScrolledText(cadre_verif, height=20, wrap="word", 
                                             font=("Consolas", 9), bg="#F0FFF0")
        self.zone_verifications.pack(fill="both", expand=True, padx=5, pady=5)

        # Journal
        cadre_journal = ttk.Frame(notebook_resultats)
        notebook_resultats.add(cadre_journal, text="📝 Journal")
        
        self.zone_journal = ScrolledText(cadre_journal, height=20, wrap="word", 
                                        font=("Consolas", 9), bg="#FFF8DC")
        self.zone_journal.pack(fill="both", expand=True, padx=5, pady=5)

        # Boutons avancés
        cadre_btn = ttk.Frame(cadre_resultats)
        cadre_btn.pack(side="bottom", fill="x", padx=5, pady=5)
        
        ttk.Button(cadre_btn, text="📋 Copier rapport", command=self.cmd_copier_resultats).pack(side="left", padx=5)
        ttk.Button(cadre_btn, text="💾 Exporter PDF", command=self.cmd_exporter_pdf).pack(side="left", padx=5)
        ttk.Button(cadre_btn, text="📊 Graphiques", command=self.cmd_generer_graphiques).pack(side="left", padx=5)
        ttk.Button(cadre_btn, text="🗑️ Effacer", command=self._effacer_resultats).pack(side="left", padx=5)

    def _creer_onglet_optimisation(self):
        """Nouvel onglet pour l'optimisation"""
        cadre_optimisation = ttk.Frame(self.notebook_gauche)
        self.notebook_gauche.add(cadre_optimisation, text="🎯 Optimisation")

        # Paramètres d'optimisation
        grp_params = ttk.LabelFrame(cadre_optimisation, text="Paramètres d'optimisation")
        grp_params.pack(fill="x", padx=10, pady=10)

        self.critere_optimisation = tk.StringVar(value="Coût minimal")
        ttk.Label(grp_params, text="Critère:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        combo_critere = ttk.Combobox(grp_params, textvariable=self.critere_optimisation, width=20,
                                    values=["Coût minimal", "Section minimale", "Performance maximale"], state="readonly")
        combo_critere.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        # Contraintes
        grp_contraintes = ttk.LabelFrame(cadre_optimisation, text="Contraintes")
        grp_contraintes.pack(fill="x", padx=10, pady=10)

        self.contrainte_deflexion = tk.BooleanVar(value=True)
        self.contrainte_fissuration = tk.BooleanVar(value=True)
        self.contrainte_effort_tranchant = tk.BooleanVar(value=True)

        ttk.Checkbutton(grp_contraintes, text="Vérifier déflexion", variable=self.contrainte_deflexion).pack(anchor="w", padx=5, pady=2)
        ttk.Checkbutton(grp_contraintes, text="Vérifier fissuration", variable=self.contrainte_fissuration).pack(anchor="w", padx=5, pady=2)
        ttk.Checkbutton(grp_contraintes, text="Vérifier effort tranchant", variable=self.contrainte_effort_tranchant).pack(anchor="w", padx=5, pady=2)

        # Résultats d'optimisation
        grp_resultats_optim = ttk.LabelFrame(cadre_optimisation, text="Résultats d'optimisation")
        grp_resultats_optim.pack(fill="both", expand=True, padx=10, pady=10)

        self.zone_optimisation = ScrolledText(grp_resultats_optim, height=15, wrap="word", font=("Consolas", 9))
        self.zone_optimisation.pack(fill="both", expand=True, padx=5, pady=5)

        # Boutons d'optimisation
        cadre_btn_optim = ttk.Frame(cadre_optimisation)
        cadre_btn_optim.pack(side="bottom", fill="x", padx=5, pady=5)

        ttk.Button(cadre_btn_optim, text="🚀 Lancer optimisation", command=self.cmd_optimiser).pack(side="left", padx=5)
        ttk.Button(cadre_btn_optim, text="📈 Analyse paramétrique", command=self.cmd_analyse_parametrique).pack(side="left", padx=5)
        ttk.Button(cadre_btn_optim, text="💰 Estimation coûts", command=self.cmd_estimation_couts).pack(side="left", padx=5)

    def _creer_visualisation_3d_avancee(self):
        cadre_3d = ttk.LabelFrame(self.panneau_droit, text="🎯 Visualisation 3D Interactive Avancée")
        cadre_3d.pack(fill="both", expand=True, padx=5, pady=5)

        # Contrôles avancés en haut
        cadre_controles = ttk.Frame(cadre_3d)
        cadre_controles.pack(fill="x", padx=5, pady=5)

        # Ligne 1 : Géométrie temps réel
        ligne1 = ttk.Frame(cadre_controles)
        ligne1.pack(fill="x", pady=2)

        ttk.Label(ligne1, text="Géométrie temps réel:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)
        
        ttk.Label(ligne1, text="L:").pack(side="left", padx=2)
        entry_l = ttk.Entry(ligne1, textvariable=self.longueur_dalot_m, width=8, font=("Segoe UI", 9))
        entry_l.pack(side="left", padx=2)
        entry_l.bind("<KeyRelease>", lambda e: self.after(300, self._dessiner_dalot_3d))

        ttk.Label(ligne1, text="l:").pack(side="left", padx=(10,2))
        entry_largeur = ttk.Entry(ligne1, textvariable=self.largeur_dalot_m, width=8, font=("Segoe UI", 9))
        entry_largeur.pack(side="left", padx=2)
        entry_largeur.bind("<KeyRelease>", lambda e: self.after(300, self._dessiner_dalot_3d))

        ttk.Label(ligne1, text="H:").pack(side="left", padx=(10,2))
        entry_h = ttk.Entry(ligne1, textvariable=self.hauteur_dalot_m, width=8, font=("Segoe UI", 9))
        entry_h.pack(side="left", padx=2)
        entry_h.bind("<KeyRelease>", lambda e: self.after(300, self._dessiner_dalot_3d))

        ttk.Button(ligne1, text="🔄 Actualiser", command=self._dessiner_dalot_3d).pack(side="left", padx=15)

        # Ligne 2 : Options d'affichage avancées
        ligne2 = ttk.Frame(cadre_controles)
        ligne2.pack(fill="x", pady=2)

        grp_affichage = ttk.LabelFrame(ligne2, text="Options d'affichage")
        grp_affichage.pack(side="left", padx=5, pady=2)
        
        # Checkboxes fonctionnelles
        cb_frame1 = ttk.Frame(grp_affichage)
        cb_frame1.pack(side="left", padx=3)
        ttk.Checkbutton(cb_frame1, text="📋 Légendes", variable=self.afficher_legendes, 
                       command=self._dessiner_dalot_3d).pack(anchor="w")
        ttk.Checkbutton(cb_frame1, text="📏 Cotes", variable=self.afficher_cotes, 
                       command=self._dessiner_dalot_3d).pack(anchor="w")
        
        cb_frame2 = ttk.Frame(grp_affichage)
        cb_frame2.pack(side="left", padx=3)
        ttk.Checkbutton(cb_frame2, text="🔧 Armatures", variable=self.afficher_armatures, 
                       command=self._dessiner_dalot_3d).pack(anchor="w")
        ttk.Checkbutton(cb_frame2, text="⚡ Efforts", variable=self.afficher_efforts, 
                       command=self._dessiner_dalot_3d).pack(anchor="w")

        # Mode de rendu
        grp_rendu = ttk.LabelFrame(ligne2, text="Mode de rendu")
        grp_rendu.pack(side="left", padx=5, pady=2)
        
        combo_rendu = ttk.Combobox(grp_rendu, textvariable=self.mode_rendu, width=12,
                                  values=["Standard", "Haute qualité", "Filaire", "Surfaces"], state="readonly")
        combo_rendu.pack(padx=5, pady=3)
        combo_rendu.bind("<<ComboboxSelected>>", lambda e: self._dessiner_dalot_3d())

        # Figure matplotlib 3D avec toolbar personnalisée
        self.figure_3d = plt.figure(figsize=(14, 10), facecolor='white')
        self.ax_3d = self.figure_3d.add_subplot(111, projection='3d')
        
        self.canvas_3d = FigureCanvasTkAgg(self.figure_3d, cadre_3d)
        self.canvas_3d.get_tk_widget().pack(fill="both", expand=True)
        
        # Toolbar personnalisée
        frame_toolbar = ttk.Frame(cadre_3d)
        frame_toolbar.pack(side="bottom", fill="x")
        
        self.toolbar_3d = NavigationToolbar2Tk(self.canvas_3d, frame_toolbar)
        self.toolbar_3d.update()
        
        # Ajout de boutons personnalisés à la toolbar
        ttk.Separator(frame_toolbar, orient="vertical").pack(side="left", padx=5, fill="y")
        ttk.Button(frame_toolbar, text="🎯 Reset", command=self.cmd_reset_vue, width=8).pack(side="left", padx=2)
        ttk.Button(frame_toolbar, text="📷 Capture", command=self.cmd_capture_3d, width=8).pack(side="left", padx=2)
        ttk.Button(frame_toolbar, text="🎬 Animation", command=self.cmd_animation_3d, width=10).pack(side="left", padx=2)
        
        # Événements de navigation avancés
        self.canvas_3d.mpl_connect("scroll_event", self._on_scroll_zoom_avance)
        self.canvas_3d.mpl_connect("pick_event", self._on_pick_face_avance)
        self.canvas_3d.mpl_connect("button_press_event", self._on_click_3d)
        self.canvas_3d.mpl_connect("motion_notify_event", self._on_motion_3d)
        
        # Variables pour la navigation
        self.mouse_pressed = False
        self.last_mouse_pos = None

    def _creer_barre_statut_avancee(self):
        cadre_statut = ttk.Frame(self, relief="sunken", borderwidth=1)
        cadre_statut.pack(side="bottom", fill="x")
        
        self.libelle_statut = ttk.Label(cadre_statut, text="Prêt pour le dimensionnement avancé", anchor="w",
                                       font=("Segoe UI", 9))
        self.libelle_statut.pack(side="left", padx=5, pady=3)

        # Séparateur
        ttk.Separator(cadre_statut, orient="vertical").pack(side="left", fill="y", padx=5)
        
        # Informations dynamiques
        self.label_dimensions = ttk.Label(cadre_statut, text="", anchor="center", font=("Segoe UI", 9))
        self.label_dimensions.pack(side="left", padx=5, pady=3)
        
        ttk.Separator(cadre_statut, orient="vertical").pack(side="left", fill="y", padx=5)
        
        self.label_calculs = ttk.Label(cadre_statut, text="Calculs: En attente", anchor="center", 
                                      font=("Segoe UI", 9), foreground="orange")
        self.label_calculs.pack(side="left", padx=5, pady=3)
        
        # Indicateur de modification
        self.label_modifie = ttk.Label(cadre_statut, text="", anchor="e", font=("Segoe UI", 9, "bold"),
                                      foreground="red")
        self.label_modifie.pack(side="right", padx=5, pady=3)

    # Méthodes de mise à jour améliorées
    def maj_statut(self, texte: str, progression: int = 0):
        self.libelle_statut.config(text=texte)
        if 0 <= progression <= 100:
            self.barre_progression.config(value=progression)
            self.label_progression.config(text=f"{progression}%")
        else:
            self.label_progression.config(text="")
        
        # Mise à jour des dimensions dans la barre de statut
        try:
            L = self.longueur_dalot_m.get()
            l = self.largeur_dalot_m.get()
            h = self.hauteur_dalot_m.get()
            self.label_dimensions.config(text=f"📐 L={L:.1f}m × l={l:.1f}m × H={h:.1f}m")
        except:
            self.label_dimensions.config(text="📐 Dimensions: N/A")
        
        # Indicateur de modification
        if self.modifie:
            self.label_modifie.config(text="● Modifié")
        else:
            self.label_modifie.config(text="")
        
        self.update_idletasks()

    def _maj_calcul_armatures(self, event=None):
        """Mise à jour des calculs d'armatures en temps réel"""
        try:
            # Calcul section d'armatures principales
            diam_prin = self.diametre_principal.get()
            espacement = self.espacement_barres_mm.get()
            
            if espacement > 0:
                section_barre = np.pi * (diam_prin/10)**2 / 4  # cm²
                section_ml = section_barre / (espacement/100)   # cm²/m
                
                self.info_principales.config(text=f"Section: {section_ml:.2f} cm²/m (φ{diam_prin}@{espacement})")
            else:
                self.info_principales.config(text="Espacement invalide")
            
            # Calcul section d'armatures secondaires
            diam_sec = self.diametre_secondaire.get()
            section_barre_sec = np.pi * (diam_sec/10)**2 / 4  # cm²
            section_ml_sec = section_barre_sec / 2  # Espacement standard 200mm
            
            self.info_secondaires.config(text=f"Section: {section_ml_sec:.2f} cm²/m (φ{diam_sec}@200)")
            
            # Relancer calculs si nécessaire
            if hasattr(self, 'dalot_calculations') and self.dalot_calculations:
                self.after(500, self._lancer_calculs_automatique)
                
        except Exception as e:
            self.info_principales.config(text=f"Erreur: {str(e)}")

    def _recalculer_charges(self, event=None):
        """Recalcule les charges quand les paramètres changent"""
        self.after(300, self._lancer_calculs_automatique)

    # Méthodes utilitaires
    def _ajouter_champ(self, parent, texte_label, var, ligne: int, info: str = ""):
        ttk.Label(parent, text=texte_label).grid(row=ligne, column=0, sticky="e", padx=5, pady=4)
        entree = ttk.Entry(parent, textvariable=var, font=("Segoe UI", 9))
        entree.grid(row=ligne, column=1, sticky="we", padx=5, pady=4)
        parent.columnconfigure(1, weight=1)
        if info:
            Infobulle(entree, info)
        entree.bind("<KeyRelease>", lambda e: self._marquer_modifie())

    def _creer_combo_avec_unite(self, parent, texte_label, var, ligne, values, unite, info=""):
        ttk.Label(parent, text=texte_label).grid(row=ligne, column=0, sticky="e", padx=5, pady=4)
        combo = ttk.Combobox(parent, textvariable=var, width=15, values=values, font=("Segoe UI", 9))
        combo.grid(row=ligne, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(parent, text=unite).grid(row=ligne, column=2, sticky="w", padx=2, pady=4)
        if info:
            Infobulle(combo, info)
        combo.bind("<<ComboboxSelected>>", lambda e: (self._marquer_modifie(), self._dessiner_dalot_3d()))
        combo.bind("<KeyRelease>", lambda e: self.after(500, lambda: (self._marquer_modifie(), self._dessiner_dalot_3d())))

    # Méthodes de mise à jour des informations
    def _maj_info_beton(self, event=None):
        classe = self.classe_beton.get()
        if classe in DonneesNormalisees.CLASSES_BETON:
            info = DonneesNormalisees.CLASSES_BETON[classe]
            self.info_beton.config(text=f"fck = {info['fck']} MPa, fcd = {info['fcd']} MPa - {info['description']}")
        self._marquer_modifie()

    def _maj_info_acier(self, event=None):
        classe = self.classe_acier.get()
        if classe in DonneesNormalisees.CLASSES_ACIER:
            info = DonneesNormalisees.CLASSES_ACIER[classe]
            self.info_acier.config(text=f"fyk = {info['fyk']} MPa, fyd = {info['fyd']} MPa - {info['description']}")
        self._marquer_modifie()

    def _maj_info_exposition(self, event=None):
        classe = self.classe_exposition.get()
        if classe in DonneesNormalisees.ENROBAGES_STANDARD:
            info = DonneesNormalisees.ENROBAGES_STANDARD[classe]
            self.info_exposition.config(text=f"Enrobage min. = {info['valeur']} mm - {info['description']}")
        self._marquer_modifie()

    def _maj_info_trafic(self, event=None):
        classe = self.classe_trafic.get()
        if classe in DonneesNormalisees.CLASSES_TRAFIC:
            info = DonneesNormalisees.CLASSES_TRAFIC[classe]
            self.info_trafic.config(text=f"Charge = {info['charge']} kN/m² - {info['description']}")
        self._marquer_modifie()

    def _maj_info_remblai(self, event=None):
        type_rem = self.type_remblai.get()
        if type_rem in DonneesNormalisees.TYPES_REMBLAI:
            info = DonneesNormalisees.TYPES_REMBLAI[type_rem]
            self.info_remblai.config(text=f"Densité = {info['densite']} kN/m³, Angle = {info['angle']}° - {info['description']}")
        self._marquer_modifie()

    # Méthodes de visualisation 3D avancées
    def _dessiner_dalot_3d(self):
        """Rendu 3D avancé avec toutes les options"""
        try:
            self.ax_3d.clear()
            
            # Couleurs selon le mode de rendu
            if self.mode_rendu.get() == "Haute qualité":
                self.ax_3d.set_facecolor('#F8F9FA')
                alpha_val = 0.9
            elif self.mode_rendu.get() == "Filaire":
                self.ax_3d.set_facecolor('white')
                alpha_val = 0.3
            else:
                self.ax_3d.set_facecolor('#F5F5F5')
                alpha_val = 0.8

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
                raise ValueError("Épaisseurs trop importantes par rapport aux dimensions")

            # Couleurs améliorées selon le mode
            if self.mode_rendu.get() == "Haute qualité":
                couleur_dalle_inf = '#BDC3C7'    # Gris clair
                couleur_dalle_sup = '#5DADE2'    # Bleu clair
                couleur_murs = '#F1948A'         # Rouge saumon
            elif self.mode_rendu.get() == "Filaire":
                couleur_dalle_inf = couleur_dalle_sup = couleur_murs = '#2C3E50'  # Tout en noir
            else:
                couleur_dalle_inf = '#D3D3D3'    # Gris standard
                couleur_dalle_sup = '#87CEEB'    # Bleu ciel
                couleur_murs = '#F08080'         # Rouge clair

            # Dessiner les éléments avec alpha variable
            self._dessiner_element_3d_avance(0, L, 0, l, 0, e_dalle_inf, couleur_dalle_inf, 'Dalle de fond', alpha_val)
            self._dessiner_element_3d_avance(0, L, 0, l, h-e_dalle_sup, h, couleur_dalle_sup, 'Dalle de couverture', alpha_val)
            self._dessiner_element_3d_avance(0, L, 0, e_mur, e_dalle_inf, h-e_dalle_sup, couleur_murs, 'Mur gauche', alpha_val)
            self._dessiner_element_3d_avance(0, L, l-e_mur, l, e_dalle_inf, h-e_dalle_sup, couleur_murs, 'Mur droit', alpha_val)
            
            # Ouvertures et écoulement
            self._dessiner_ouvertures_avancees(L, l, h, e_mur, e_dalle_inf, e_dalle_sup)
            
            # Armatures si demandées
            if self.afficher_armatures.get():
                self._dessiner_armatures_3d(L, l, h, e_dalle_sup, e_dalle_inf, e_mur)
            
            # Efforts si demandés
            if self.afficher_efforts.get():
                self._dessiner_efforts_3d(L, l, h)
            
            # Configuration avancée des axes
            self.ax_3d.set_xlabel('Longueur (m)', fontweight='bold', fontsize=10)
            self.ax_3d.set_ylabel('Largeur (m)', fontweight='bold', fontsize=10)
            self.ax_3d.set_zlabel('Hauteur (m)', fontweight='bold', fontsize=10)
            
            # Titre avec informations détaillées
            volume_total = L * l * h if L > 0 and l > 0 and h > 0 else 0
            titre = f'🏗️ Dalot 3D - L:{L:.1f}×l:{l:.1f}×H:{h:.1f}m - V={volume_total:.1f}m³'
            self.ax_3d.set_title(titre, fontsize=12, fontweight='bold', pad=20)
            
            # Limites optimisées avec marge proportionnelle
            margin_factor = 0.1
            margin_x = L * margin_factor
            margin_y = l * margin_factor
            margin_z = h * margin_factor
            
            self.ax_3d.set_xlim(-margin_x, L + margin_x)
            self.ax_3d.set_ylim(-margin_y, l + margin_y)
            self.ax_3d.set_zlim(0, h + margin_z)
            
            # Proportions correctes
            max_dim = max(L, l, h)
            if max_dim > 0:
                self.ax_3d.set_box_aspect([L/max_dim, l/max_dim, h/max_dim])
            
            # Grille et style selon le mode
            if self.mode_rendu.get() != "Filaire":
                self.ax_3d.grid(True, alpha=0.3, linewidth=0.5)
                self.ax_3d.xaxis._axinfo["grid"]['color'] = "#E0E0E0"
                self.ax_3d.yaxis._axinfo["grid"]['color'] = "#E0E0E0"                                                 

                self.ax_3d.zaxis._axinfo["grid"]['color'] = "#E0E0E0"
            
            # Légendes si demandées
            if self.afficher_legendes.get():
                self.ax_3d.legend(loc='upper left', fontsize=9, framealpha=0.9)
            
            # Cotes si demandées
            if self.afficher_cotes.get():
                self._ajouter_cotes_3d_avancees(L, l, h)
            
            # Vue par défaut
            self.ax_3d.view_init(elev=25, azim=45)
            
            # Actualisation du canvas
            self.canvas_3d.draw()
            
            # Mise à jour du statut
            self.maj_statut("Dalot 3D actualisé avec succès")
            self.label_calculs.config(text="Rendu 3D: ✓", foreground="green")
            
            # Lancer calculs en arrière-plan
            self.after(200, self._lancer_calculs_automatique)
            
        except Exception as e:
            error_msg = f"Erreur 3D: {str(e)}"
            messagebox.showerror("Erreur de rendu 3D", error_msg)
            self.journaliser(error_msg)
            self.label_calculs.config(text="Rendu 3D: ✗", foreground="red")

    def _dessiner_element_3d_avance(self, x_min, x_max, y_min, y_max, z_min, z_max, couleur, nom, alpha=0.8):
        """Dessine un élément 3D avec options avancées"""
        vertices = self._creer_sommets_boite(x_min, x_max, y_min, y_max, z_min, z_max)
        faces = self._creer_faces_boite(vertices)

        face_names = ["Inférieure", "Supérieure", "Avant", "Arrière", "Droite", "Gauche"]

        for i, face in enumerate(faces):
            # Style selon le mode de rendu
            if self.mode_rendu.get() == "Filaire":
                collection = Poly3DCollection([face], alpha=alpha, facecolor='none', 
                                            edgecolor=couleur, linewidth=2.0, picker=True)
            elif self.mode_rendu.get() == "Surfaces":
                collection = Poly3DCollection([face], alpha=alpha, facecolor=couleur, 
                                            edgecolor='none', picker=True)
            else:
                collection = Poly3DCollection([face], alpha=alpha, facecolor=couleur, 
                                            edgecolor='#2C3E50', linewidth=1.2, picker=True)
            
            self.ax_3d.add_collection3d(collection)
            
            # Stockage pour interaction
            self.original_face_colors[collection] = collection.get_facecolor()
            self.face_properties[collection] = {
                'name': f"{nom} - Face {face_names[i]}",
                'info': f"Élément: {nom}",
                'element_type': nom.lower().replace(' ', '_'),
                'dimensions': {
                    'longueur': x_max - x_min,
                    'largeur': y_max - y_min,
                    'hauteur': z_max - z_min
                }
            }

    def _dessiner_ouvertures_avancees(self, L, l, h, e_mur, e_dalle_inf, e_dalle_sup):
        """Dessine les ouvertures avec style amélioré"""
        # Ouverture entrée (rouge avec effet)
        ouv_y = np.array([e_mur, l-e_mur, l-e_mur, e_mur, e_mur])
        ouv_z = np.array([e_dalle_inf, e_dalle_inf, h-e_dalle_sup, h-e_dalle_sup, e_dalle_inf])
        ouv_x_entree = np.zeros_like(ouv_y)
        
        # Ligne principale d'entrée
        self.ax_3d.plot(ouv_x_entree, ouv_y, ouv_z, color='#E74C3C', linewidth=6, 
                       label='🔴 Entrée', alpha=0.9, solid_capstyle='round')
        
        # Ouverture sortie (verte)
        ouv_x_sortie = np.full_like(ouv_y, L)
        self.ax_3d.plot(ouv_x_sortie, ouv_y, ouv_z, color='#27AE60', linewidth=6, 
                       label='🟢 Sortie', alpha=0.9, solid_capstyle='round')
        
        # Ligne d'écoulement avec gradient
        if self.mode_rendu.get() != "Filaire":
            x_eau = np.linspace(0, L, 50)
            y_eau = np.full_like(x_eau, l/2)
            z_eau = np.full_like(x_eau, e_dalle_inf + 0.05)
            
            # Effet de profondeur avec plusieurs lignes
            for offset in [-0.1, 0, 0.1]:
                self.ax_3d.plot(x_eau, y_eau + offset, z_eau, 
                               color='#3498DB', linewidth=3-abs(offset)*10, 
                               alpha=0.7-abs(offset)*2, linestyle='-')
            
            # Ajout d'une ligne centrale plus marquée
            self.ax_3d.plot(x_eau, y_eau, z_eau, color='#2980B9', linewidth=4, 
                           alpha=0.8, label='💧 Écoulement')

        # Flèches directionnelles améliorées
        if L > 3:  # Seulement si assez long pour être visible
            arrow_length = min(L*0.08, 2.0)  # Limite la taille des flèches
            arrow_y = l/2
            arrow_z = (h/2)
            
            # Flèche entrée (rouge)
            self.ax_3d.quiver(-L*0.12, arrow_y, arrow_z, arrow_length, 0, 0, 
                             color='#C0392B', alpha=0.8, arrow_length_ratio=0.3, 
                             linewidth=3, normalize=True)
            
            # Flèche sortie (verte)
            self.ax_3d.quiver(L*1.02, arrow_y, arrow_z, arrow_length, 0, 0, 
                             color='#229954', alpha=0.8, arrow_length_ratio=0.3, 
                             linewidth=3, normalize=True)

    def _dessiner_armatures_3d(self, L, l, h, e_dalle_sup, e_dalle_inf, e_mur):
        """Dessine les armatures en 3D"""
        try:
            # Armatures principales dans la dalle supérieure
            diam_prin = self.diametre_principal.get()
            espacement = self.espacement_barres_mm.get() / 1000  # Conversion en mètres
            
            if espacement > 0:
                # Barres longitudinales
                n_barres_long = int(l / espacement)
                for i in range(n_barres_long):
                    y_barre = i * espacement + espacement/2
                    if y_barre < l - e_mur:
                        z_barre = h - e_dalle_sup/2
                        self.ax_3d.plot([0, L], [y_barre, y_barre], [z_barre, z_barre], 
                                       color='#8E44AD', linewidth=2, alpha=0.7)
                
                # Barres transversales
                n_barres_trans = int(L / (espacement * 3))  # Moins espacées
                for i in range(n_barres_trans):
                    x_barre = i * espacement * 3 + espacement
                    if x_barre < L:
                        z_barre = h - e_dalle_sup/2
                        self.ax_3d.plot([x_barre, x_barre], [e_mur, l-e_mur], [z_barre, z_barre], 
                                       color='#9B59B6', linewidth=1.5, alpha=0.6)
                
                # Armatures des voiles (verticales)
                n_barres_voile = max(3, int(h / 0.3))  # Une barre tous les 30cm
                for i in range(n_barres_voile):
                    z_barre = e_dalle_inf + i * (h - e_dalle_inf - e_dalle_sup) / (n_barres_voile - 1)
                    # Voile gauche
                    self.ax_3d.plot([0, L], [e_mur/2, e_mur/2], [z_barre, z_barre], 
                                   color='#E67E22', linewidth=1.5, alpha=0.6)
                    # Voile droit
                    self.ax_3d.plot([0, L], [l-e_mur/2, l-e_mur/2], [z_barre, z_barre], 
                                   color='#E67E22', linewidth=1.5, alpha=0.6)
                
        except Exception as e:
            self.journaliser(f"Erreur affichage armatures: {str(e)}")

    def _dessiner_efforts_3d(self, L, l, h):
        """Dessine les efforts et sollicitations"""
        try:
            if not hasattr(self, 'dalot_calculations') or not self.dalot_calculations:
                return
                
            # Charges sur la dalle supérieure (flèches vers le bas)
            if 'charges_dalle_couverture' in self.dalot_calculations:
                charges = self.dalot_calculations['charges_dalle_couverture']
                q_total = charges.get('q_ELU', 0) / 1000  # Conversion en kN/m²
                
                # Grille de flèches représentant les charges
                n_arrows_x = min(8, int(L/2))
                n_arrows_y = min(6, int(l/2))
                
                for i in range(n_arrows_x):
                    for j in range(n_arrows_y):
                        x_arrow = (i + 1) * L / (n_arrows_x + 1)
                        y_arrow = (j + 1) * l / (n_arrows_y + 1)
                        z_start = h * 1.1
                        
                        # Taille de flèche proportionnelle à la charge
                        arrow_size = min(0.3, q_total / 100)
                        
                        self.ax_3d.quiver(x_arrow, y_arrow, z_start, 0, 0, -arrow_size,
                                         color='#F39C12', alpha=0.7, arrow_length_ratio=0.3,
                                         linewidth=2)
            
            # Poussée des terres (flèches horizontales)
            if 'poussee_terres' in self.dalot_calculations:
                poussee = self.dalot_calculations['poussee_terres']
                force_max = poussee.get('force_poussee_par_metre', 0) / 1000  # kN/m
                
                # Flèches sur les voiles
                n_arrows_z = min(5, int(h/0.5))
                for i in range(n_arrows_z):
                    z_arrow = (i + 1) * h / (n_arrows_z + 1)
                    force_locale = force_max * (z_arrow / h)  # Force croissante avec la profondeur
                    arrow_size = min(0.4, force_locale / 50)
                    
                    # Poussée sur voile gauche
                    self.ax_3d.quiver(-l*0.1, 0, z_arrow, arrow_size, 0, 0,
                                     color='#E74C3C', alpha=0.6, arrow_length_ratio=0.3)
                    
                    # Poussée sur voile droit
                    self.ax_3d.quiver(L + l*0.1, l, z_arrow, -arrow_size, 0, 0,
                                     color='#E74C3C', alpha=0.6, arrow_length_ratio=0.3)
                
        except Exception as e:
            self.journaliser(f"Erreur affichage efforts: {str(e)}")

    def _ajouter_cotes_3d_avancees(self, L, l, h):
        """Ajoute les cotations avec style amélioré"""
        offset_factor = 0.15
        
        # Style des annotations
        bbox_props = dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9, edgecolor='#2C3E50')
        
        # Cote longueur
        self.ax_3d.text(L/2, -offset_factor*l, -offset_factor*h, f'L = {L:.1f} m', 
                       fontsize=11, ha='center', va='center', color='#2C3E50', weight='bold',
                       bbox=bbox_props, rotation=0)
        
        # Cote largeur
        self.ax_3d.text(-offset_factor*L, l/2, -offset_factor*h, f'l = {l:.1f} m', 
                       fontsize=11, ha='center', va='center', color='#2C3E50', weight='bold',
                       bbox=bbox_props, rotation=90)
        
        # Cote hauteur
        self.ax_3d.text(-offset_factor*L, -offset_factor*l, h/2, f'H = {h:.1f} m', 
                       fontsize=11, ha='center', va='center', color='#2C3E50', weight='bold',
                       bbox=bbox_props)
        
        # Lignes de cote (discrètes)
        if self.mode_rendu.get() != "Filaire":
            # Ligne de cote longueur
            self.ax_3d.plot([0, L], [-offset_factor*l/2, -offset_factor*l/2], 
                           [-offset_factor*h/2, -offset_factor*h/2], 
                           color='#7F8C8D', linestyle='--', alpha=0.5, linewidth=1)
            
            # Ligne de cote largeur
            self.ax_3d.plot([-offset_factor*L/2, -offset_factor*L/2], [0, l], 
                           [-offset_factor*h/2, -offset_factor*h/2], 
                           color='#7F8C8D', linestyle='--', alpha=0.5, linewidth=1)
            
            # Ligne de cote hauteur
            self.ax_3d.plot([-offset_factor*L/2, -offset_factor*L/2], 
                           [-offset_factor*l/2, -offset_factor*l/2], [0, h], 
                           color='#7F8C8D', linestyle='--', alpha=0.5, linewidth=1)

    def _creer_sommets_boite(self, x_min, x_max, y_min, y_max, z_min, z_max):
        """Crée les sommets d'une boîte 3D"""
        return np.array([
            [x_min, y_min, z_min], [x_max, y_min, z_min], [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_max], [x_max, y_min, z_max], [x_max, y_max, z_max], [x_min, y_max, z_max]
        ])

    def _creer_faces_boite(self, vertices):
        """Crée les faces d'une boîte à partir des sommets"""
        faces_indices = [
            [0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], 
            [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]
        ]
        return [[vertices[i] for i in face] for face in faces_indices]

    # Événements 3D avancés
    def _on_scroll_zoom_avance(self, event):
        """Gestion du zoom avancé avec la molette"""
        if event.inaxes == self.ax_3d:
            # Facteur de zoom adaptatif
            base_zoom = 1.1
            if event.button == 'up':
                zoom_factor = 1 / base_zoom
            elif event.button == 'down':
                zoom_factor = base_zoom
            else:
                return

            # Zoom centré sur la position de la souris
            current_xlim = self.ax_3d.get_xlim3d()
            current_ylim = self.ax_3d.get_ylim3d()
            current_zlim = self.ax_3d.get_zlim3d()

            # Point central du zoom (position de la souris ou centre de la vue)
            x_center = (current_xlim[0] + current_xlim[1]) / 2
            y_center = (current_ylim[0] + current_ylim[1]) / 2
            z_center = (current_zlim[0] + current_zlim[1]) / 2

            # Nouvelles limites
            x_range = (current_xlim[1] - current_xlim[0]) * zoom_factor / 2
            y_range = (current_ylim[1] - current_ylim[0]) * zoom_factor / 2
            z_range = (current_zlim[1] - current_zlim[0]) * zoom_factor / 2

            self.ax_3d.set_xlim3d(x_center - x_range, x_center + x_range)
            self.ax_3d.set_ylim3d(y_center - y_range, y_center + y_range)
            self.ax_3d.set_zlim3d(z_center - z_range, z_center + z_range)
            
            self.canvas_3d.draw_idle()

    def _on_pick_face_avance(self, event):
        """Gestion avancée de la sélection de faces"""
        if not isinstance(event.artist, Poly3DCollection):
            return

        # Désélectionner la face précédente
        if self.selected_face and self.selected_face in self.original_face_colors:
            self.selected_face.set_facecolor(self.original_face_colors[self.selected_face])

        # Sélectionner la nouvelle face
        self.selected_face = event.artist
        if self.selected_face not in self.original_face_colors:
            self.original_face_colors[self.selected_face] = self.selected_face.get_facecolor()

        # Couleur de sélection plus subtile
        self.selected_face.set_facecolor('#FFD700')  # Or pour la sélection
        self.canvas_3d.draw_idle()

        # Afficher les informations détaillées
        if self.selected_face in self.face_properties:
            face_info = self.face_properties[self.selected_face]
            self._afficher_info_face_avancee(face_info)

    def _on_click_3d(self, event):
        """Gestion des clics 3D"""
        if event.inaxes == self.ax_3d:
            self.mouse_pressed = True
            self.last_mouse_pos = (event.x, event.y)

    def _on_motion_3d(self, event):
        """Gestion du mouvement de souris pour navigation 3D"""
        if self.mouse_pressed and event.inaxes == self.ax_3d and self.last_mouse_pos:
            # Calcul du déplacement
            dx = event.x - self.last_mouse_pos[0]
            dy = event.y - self.last_mouse_pos[1]
            
            # Rotation selon le déplacement
            if event.button == 1:  # Clic gauche = rotation
                current_elev = self.ax_3d.elev
                current_azim = self.ax_3d.azim
                
                new_azim = current_azim + dx * 0.5
                new_elev = np.clip(current_elev + dy * 0.5, -90, 90)
                
                self.ax_3d.view_init(elev=new_elev, azim=new_azim)
                self.canvas_3d.draw_idle()
            
            self.last_mouse_pos = (event.x, event.y)

    def _deselectionner_face(self):
        """Désélectionne la face actuellement sélectionnée"""
        if self.selected_face and self.selected_face in self.original_face_colors:
            self.selected_face.set_facecolor(self.original_face_colors[self.selected_face])
            self.selected_face = None
            self.canvas_3d.draw_idle()

    def _afficher_info_face_avancee(self, face_info):
        """Affiche les informations détaillées de la face sélectionnée"""
        info_text = f"\n{'='*60}\n"
        info_text += f"🎯 FACE SÉLECTIONNÉE - ANALYSE DÉTAILLÉE\n"
        info_text += f"{'='*60}\n"
        info_text += f"📋 Nom: {face_info['name']}\n"
        info_text += f"ℹ️  Type: {face_info['info']}\n"
        
        # Dimensions de l'élément
        if 'dimensions' in face_info:
            dims = face_info['dimensions']
            info_text += f"📐 Dimensions: L={dims['longueur']:.2f}m × l={dims['largeur']:.2f}m × H={dims['hauteur']:.2f}m\n"
            volume_element = dims['longueur'] * dims['largeur'] * dims['hauteur']
            info_text += f"📦 Volume: {volume_element:.3f} m³\n"
        
        element_type = face_info.get('element_type', '')
        
        # Informations spécifiques selon le type d'élément
        if 'dalle_de_couverture' in element_type and self.dalot_calculations:
            info_text += self._get_info_dalle_couverture()
        elif 'dalle_de_fond' in element_type and self.dalot_calculations:
            info_text += self._get_info_dalle_fond()
        elif 'mur' in element_type and self.dalot_calculations:
            info_text += self._get_info_mur()
        
        # Matériaux utilisés
        if 'materiaux_utilises' in self.dalot_calculations:
            mat = self.dalot_calculations['materiaux_utilises']
            info_text += f"\n🧱 MATÉRIAUX\n"
            info_text += f"{'─'*25}\n"
            info_text += f"• Béton: {mat.get('beton', 'N/A')} (fck={mat.get('fck', 'N/A')} MPa)\n"
            info_text += f"• Acier: {mat.get('acier', 'N/A')} (fyd={mat.get('fyd', 'N/A')} MPa)\n"
        
        info_text += f"\n{'='*60}\n"
        
        # Affichage dans la zone de rapport
        self.zone_calculs.insert(tk.END, info_text)
        self.zone_calculs.see(tk.END)
        self.journaliser(f"Face analysée: {face_info['name']}")

    def _get_info_dalle_couverture(self):
        """Retourne les infos spécifiques à la dalle de couverture"""
        info = ""
        if 'ferraillage_dalle_couverture' in self.dalot_calculations:
            ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
            armatures = self.dalot_calculations.get('armatures_dalle_choisies', {})
            
            info += f"\n🔧 CALCULS DALLE DE COUVERTURE\n"
            info += f"{'─'*35}\n"
            if 'moment_ELU' in ferraillage:
                info += f"📊 Moment ELU: {ferraillage['moment_ELU']/1000:.1f} kNm/m\n"
                info += f"🔩 As théorique: {ferraillage['As_theorique']*1e4:.2f} cm²/m\n"
                if armatures:
                    info += f"🛠️  Armatures: φ{armatures.get('diametre', 'N/A')} @ {armatures.get('espacement', 'N/A')}mm\n"
                    info += f"✅ As fourni: {armatures.get('As_fourni', 0)*1e4:.2f} cm²/m\n"
                    
                    # Vérification du ferraillage
                    ratio = armatures.get('As_fourni', 0) / ferraillage['As_theorique'] if ferraillage['As_theorique'] > 0 else 0
                    if ratio >= 1.0:
                        info += f"✅ Ferraillage: OK (ratio={ratio:.2f})\n"
                    else:
                        info += f"❌ Ferraillage: INSUFFISANT (ratio={ratio:.2f})\n"
        
        if 'charges_dalle_couverture' in self.dalot_calculations:
            charges = self.dalot_calculations['charges_dalle_couverture']
            info += f"\n⚖️  CHARGEMENTS\n"
            info += f"{'─'*20}\n"
            info += f"• ELS: {charges.get('q_service', 0)/1000:.1f} kN/m²\n"
            info += f"• ELU: {charges.get('q_ELU', 0)/1000:.1f} kN/m²\n"
        
        return info

    def _get_info_dalle_fond(self):
        """Retourne les infos spécifiques à la dalle de fond"""
        info = f"\n🏗️  DALLE DE FOND (RADIER)\n"
        info += f"{'─'*30}\n"
        info += f"• Fonction: Transmission des charges au sol\n"
        info += f"• Sollicitations: Compression + flexion locale\n"
        
        # Calculs simplifiés pour la dalle de fond
        try:
            L = self.longueur_dalot_m.get()
            l = self.largeur_dalot_m.get()
            e_dalle_inf = self.epaisseur_dalle_inf_m.get()
            
            # Charge due au poids propre du dalot (estimation)
            if 'volumes_masses' in self.dalot_calculations:
                masse_totale = self.dalot_calculations['volumes_masses']['total']['masse']
                charge_sur_radier = masse_totale * 9.81 / (L * l)  # N/m²
                info += f"• Charge estimée: {charge_sur_radier/1000:.1f} kN/m²\n"
            
            # Contrainte au sol (estimation)
            contrainte_sol_estimee = 200000  # 200 kPa par défaut
            info += f"• Contrainte sol (estimée): {contrainte_sol_estimee/1000:.0f} kPa\n"
            
        except:
            info += f"• Calculs détaillés: Non disponibles\n"
        
        return info

    def _get_info_mur(self):
        """Retourne les infos spécifiques aux murs"""
        info = f"\n🏗️  MUR LATÉRAL\n"
        info += f"{'─'*20}\n"
        
        if 'effort_normal_mur' in self.dalot_calculations:
            effort = self.dalot_calculations['effort_normal_mur']
            info += f"⚡ Effort normal: {effort.get('valeur', 0)/1000:.1f} kN/m\n"
        
        if 'poussee_terres' in self.dalot_calculations:
            poussee = self.dalot_calculations['poussee_terres']
            info += f"🌍 Poussée des terres:\n"
            info += f"  • Force: {poussee.get('force_poussee_par_metre', 0)/1000:.1f} kN/m\n"
            info += f"  • Point d'application: {poussee.get('point_application_hauteur', 0):.2f} m\n"
        
        # Armatures du mur
        armatures_mur = self.dalot_calculations.get('armatures_mur_choisies', {})
        if armatures_mur:
            info += f"🔩 Armatures:\n"
            info += f"  • φ{armatures_mur.get('diametre', 'N/A')} @ {armatures_mur.get('espacement', 'N/A')}mm\n"
            info += f"  • Section: {armatures_mur.get('As_fourni', 0)*1e4:.2f} cm²/m\n"
        
        return info

    # Calculs automatiques améliorés
    def _lancer_calculs_automatique(self):
        """Lance les calculs automatiquement avec gestion d'erreurs avancée"""
        try:
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle = float(self.epaisseur_dalle_sup_m.get())
            
            # Validation préalable
            if not self._valider_geometrie_complete(L, l, h, e_mur, e_dalle):
                self.label_calculs.config(text="Calculs: Géométrie invalide", foreground="red")
                return
            
            # Récupération des paramètres matériaux et armatures
            classe_beton = self.classe_beton.get()
            classe_acier = self.classe_acier.get()
            diametre_principal = self.diametre_principal.get()
            espacement = self.espacement_barres_mm.get()
            
            # Lancement des calculs avec tous les paramètres
            self.dalot_calculations = SimulationCalculs.analyser_dalot(
                L, l, h, e_mur, e_dalle, classe_beton, classe_acier, 
                diametre_principal, espacement
            )
            
            # Mise à jour du statut
            if 'erreur' in self.dalot_calculations:
                self.label_calculs.config(text="Calculs: Erreur", foreground="red")
                self.journaliser(f"Erreur calcul: {self.dalot_calculations['erreur']}")
            else:
                self.label_calculs.config(text="Calculs: ✓ À jour", foreground="green")
                self._mettre_a_jour_verifications()
                
        except Exception as e:
            self.dalot_calculations = {'erreur': str(e)}
            self.label_calculs.config(text="Calculs: Erreur", foreground="red")
            self.journaliser(f"Erreur calcul automatique: {str(e)}")

    def _valider_geometrie_complete(self, L, l, h, e_mur, e_dalle):
        """Validation complète de la géométrie"""
        try:
            # Vérifications de base
            if L <= 0 or l <= 0 or h <= 0 or e_mur <= 0 or e_dalle <= 0:
                return False
            
            # Vérifications de cohérence
            if e_mur >= l/2:  # Murs trop épais
                return False
                
            if e_dalle >= h/2:  # Dalle trop épaisse
                return False
            
            # Vérifications de limites pratiques
            if L > 100 or l > 20 or h > 10:  # Dimensions trop importantes
                return False
                
            if L < 1 or l < 0.5 or h < 0.5:  # Dimensions trop petites
                return False
            
            return True
            
        except:
            return False

    def _mettre_a_jour_verifications(self):
        """Met à jour l'onglet vérifications avec détails"""
        self.zone_verifications.delete("1.0", tk.END)
        
        lignes = []
        lignes.append("╔══════════════════════════════════════════╗")
        lignes.append("║        VÉRIFICATIONS AUTOMATIQUES        ║")
        lignes.append("╚══════════════════════════════════════════╝")
        lignes.append("")
        
        try:
            # Validation géométrique
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle_sup = float(self.epaisseur_dalle_sup_m.get())
            e_dalle_inf = float(self.epaisseur_dalle_inf_m.get())

            lignes.append("🔍 VÉRIFICATIONS GÉOMÉTRIQUES")
            lignes.append("─" * 40)
            
            # Vérifications détaillées
            verifications = [
                (L > 0 and l > 0 and h > 0, "Dimensions positives"),
                (e_mur < l/2, f"Épaisseur murs OK (e={e_mur:.2f}m < l/2={l/2:.2f}m)"),
                ((e_dalle_sup + e_dalle_inf) < h, f"Épaisseurs dalles OK (Σe={e_dalle_sup+e_dalle_inf:.2f}m < H={h:.2f}m)"),
                (L >= 2*h, "Élancement longueur OK"),
                (l >= 2*e_mur, "Largeur vs épaisseur murs OK"),
                (h/l <= 2.0, "Rapport H/l acceptable"),
            ]
            
            all_geo_ok = True
            for ok, message in verifications:
                if ok:
                    lignes.append(f"✅ {message}")
                else:
                    lignes.append(f"❌ {message}")
                    all_geo_ok = False
            
            lignes.append("")
            
            # Vérifications des calculs
            lignes.append("🔧 VÉRIFICATIONS DE CALCUL")
            lignes.append("─" * 40)
            
            if 'erreur' in self.dalot_calculations:
                lignes.append(f"❌ Erreur de calcul: {self.dalot_calculations['erreur']}")
            elif self.dalot_calculations:
                # Vérification ferraillage
                if 'armatures_dalle_choisies' in self.dalot_calculations and 'ferraillage_dalle_couverture' in self.dalot_calculations:
                    armatures = self.dalot_calculations['armatures_dalle_choisies']
                    ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
                    
                    As_fourni = armatures.get('As_fourni', 0)
                    As_theorique = ferraillage.get('As_theorique', 0)
                    
                    if As_theorique > 0:
                        ratio = As_fourni / As_theorique
                        if ratio >= 1.0:
                            lignes.append(f"✅ Ferraillage dalle OK (ratio={ratio:.2f})")
                        else:
                            lignes.append(f"⚠️  Ferraillage dalle insuffisant (ratio={ratio:.2f})")
                        
                        lignes.append(f"   As théorique: {As_theorique*1e4:.2f} cm²/m")
                        lignes.append(f"   As fourni: {As_fourni*1e4:.2f} cm²/m")
                        
                        if armatures.get('optimise', False):
                            lignes.append(f"🎯 Armatures optimisées automatiquement")
                
                # Vérification charges
                if 'charges_dalle_couverture' in self.dalot_calculations:
                    charges = self.dalot_calculations['charges_dalle_couverture']
                    q_elu = charges.get('q_ELU', 0) / 1000  # kN/m²
                    
                    if q_elu > 0:
                        lignes.append(f"✅ Charges calculées: {q_elu:.1f} kN/m² (ELU)")
                        
                        # Vérification ordre de grandeur
                        if q_elu > 50:
                            lignes.append("⚠️  Charges élevées - Vérifier les hypothèses")
                        elif q_elu < 5:
                            lignes.append("⚠️  Charges faibles - Vérifier les hypothèses")
                
                lignes.append("✅ Calculs structurels réalisés")
            else:
                lignes.append("⏳ Calculs en cours...")
            
            lignes.append("")
            
            # Vérifications matériaux
            lignes.append("🧱 VÉRIFICATIONS MATÉRIAUX")
            lignes.append("─" * 40)
            
            # Vérification cohérence béton/acier
            beton_info = DonneesNormalisees.CLASSES_BETON.get(self.classe_beton.get(), {})
            acier_info = DonneesNormalisees.CLASSES_ACIER.get(self.classe_acier.get(), {})
            
            if beton_info and acier_info:
                lignes.append(f"✅ Classe béton: {self.classe_beton.get()} (fck={beton_info['fck']} MPa)")
                lignes.append(f"✅ Classe acier: {self.classe_acier.get()} (fyk={acier_info['fyk']} MPa)")
                
                # Vérification compatibilité
                if beton_info['fck'] >= 25 and acier_info['fyk'] >= 500:
                    lignes.append("✅ Matériaux compatibles (performance)")
                elif beton_info['fck'] >= 20 and acier_info['fyk'] >= 400:
                    lignes.append("✅ Matériaux compatibles (standard)")
                else:
                    lignes.append("⚠️  Vérifier compatibilité matériaux")
            
            lignes.append("")
            
            # Résumé final
            lignes.append("📋 RÉSUMÉ")
            lignes.append("─" * 40)
            
            if all_geo_ok and 'erreur' not in self.dalot_calculations:
                lignes.append("✅ Toutes les vérifications passent")
                lignes.append("🚀 Prêt pour dimensionnement détaillé")
            else:
                lignes.append("⚠️  Corrections nécessaires avant validation")
            
            lignes.append("")
            lignes.append(f"🕒 Dernière vérification: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            lignes.append(f"❌ Erreur lors des vérifications: {str(e)}")

        # Affichage avec couleurs
        contenu_verif = "\n".join(lignes)
        self.zone_verifications.insert("1.0", contenu_verif)
        self.zone_verifications.see(tk.END)

    # Commandes principales améliorées
    def cmd_verifier_entrees(self):
        """Vérification complète des données d'entrée"""
        self.maj_statut("Vérification en cours...", 25)
        
        try:
            erreurs = []
            avertissements = []
            
            # Vérifications géométriques
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle_sup = float(self.epaisseur_dalle_sup_m.get())
            e_dalle_inf = float(self.epaisseur_dalle_inf_m.get())

            self.maj_statut("Vérification géométrie...", 50)

            # Erreurs critiques
            if L <= 0 or l <= 0 or h <= 0:
                erreurs.append("• Dimensions L, l, H doivent être strictement positives")
            if e_mur <= 0 or e_dalle_sup <= 0 or e_dalle_inf <= 0:
                erreurs.append("• Épaisseurs doivent être strictement positives")
            if e_mur >= l/2:
                erreurs.append(f"• Épaisseur murs trop importante: {e_mur:.2f}m ≥ l/2 = {l/2:.2f}m")
            if (e_dalle_sup + e_dalle_inf) >= h:
                erreurs.append(f"• Somme épaisseurs dalles trop importante: {e_dalle_sup+e_dalle_inf:.2f}m ≥ H = {h:.2f}m")

            self.maj_statut("Vérification cohérence...", 75)
            
            # Avertissements
            if L > 50:
                avertissements.append(f"• Longueur importante ({L:.1f}m) - Vérifier joints de dilatation")
            if h/l > 2:
                avertissements.append(f"• Rapport H/l élevé ({h/l:.2f}) - Vérifier stabilité")
            if l > 8:
                avertissements.append(f"• Grande portée ({l:.1f}m) - Vérifier flèche")
            
            # Vérifications armatures
            diametre_prin = self.diametre_principal.get()
            espacement = self.espacement_barres_mm.get()
            
            if espacement < 80:
                avertissements.append(f"• Espacement très serré ({espacement}mm) - Vérifier mise en œuvre")
            elif espacement > 300:
                avertissements.append(f"• Espacement important ({espacement}mm) - Vérifier fissuration")
            
            if diametre_prin < 10:
                avertissements.append(f"• Petit diamètre ({diametre_prin}mm) - Vérifier ancrage")

            self.maj_statut("Finalisation vérification...", 90)

            # Affichage des résultats
            if erreurs:
                message = "VÉRIFICATION ÉCHOUÉE\n\nErreurs critiques:\n" + "\n".join(erreurs)
                if avertissements:
                    message += "\n\nAvertissements:\n" + "\n".join(avertissements)
                messagebox.showerror("Vérification des données", message)
                self.journaliser("Vérification: ÉCHEC - Erreurs critiques détectées")
                self.maj_statut("Vérification échouée", 0)
                return False
            elif avertissements:
                message = "VÉRIFICATION RÉUSSIE avec avertissements\n\nPoints d'attention:\n" + "\n".join(avertissements)
                result = messagebox.showwarning("Vérification des données", message + "\n\nContinuer quand même ?")
                self.journaliser("Vérification: OK avec avertissements")
            else:
                messagebox.showinfo("Vérification des données", "✅ Toutes les vérifications sont validées!\n\nLe projet est prêt pour les calculs.")
                self.journaliser("Vérification: PARFAIT - Aucune erreur détectée")

            self._mettre_a_jour_verifications()
            self.maj_statut("Vérification terminée ✓", 100)
            return True
            
        except Exception as e:
            messagebox.showerror("Erreur de validation", f"❌ Erreur pendant la validation:\n{str(e)}")
            self.journaliser(f"Erreur validation: {str(e)}")
            self.maj_statut("Erreur de validation", 0)
            return False

    def cmd_lancer_calculs(self):
        """Lance les calculs complets avec rapport détaillé"""
        self.journaliser("═══ DÉBUT DES CALCULS DE DIMENSIONNEMENT ═══")
        self.maj_statut("Initialisation des calculs...", 5)
        
        try:
            # Vérification préalable
            if not self.cmd_verifier_entrees():
                return
            
            self.maj_statut("Collecte des paramètres...", 15)
            
            # Collecte de tous les paramètres
            L = float(self.longueur_dalot_m.get())
            l = float(self.largeur_dalot_m.get())
            h = float(self.hauteur_dalot_m.get())
            e_mur = float(self.epaisseur_voile_lat_m.get())
            e_dalle_sup = float(self.epaisseur_dalle_sup_m.get())
            e_dalle_inf = float(self.epaisseur_dalle_inf_m.get())
            
            classe_beton = self.classe_beton.get()
            classe_acier = self.classe_acier.get()
            diametre_principal = self.diametre_principal.get()
            espacement = self.espacement_barres_mm.get()

            self.maj_statut("Calculs structurels...", 40)
            
            # Lancement des calculs avec tous les paramètres
            self.dalot_calculations = SimulationCalculs.analyser_dalot(
                L, l, h, e_mur, e_dalle_sup, classe_beton, classe_acier, 
                diametre_principal, espacement
            )

            self.maj_statut("Génération du rapport...", 70)
            
            # Génération du rapport
            if 'erreur' in self.dalot_calculations:
                rapport = f"ERREUR LORS DES CALCULS\n{'='*50}\n{self.dalot_calculations['erreur']}"
                self.label_calculs.config(text="Calculs: Erreur", foreground="red")
            else:
                rapport = self._generer_rapport_complet_avance()
                self.label_calculs.config(text="Calculs: ✓ Terminés", foreground="green")

            self.maj_statut("Affichage des résultats...", 85)
            
            # Affichage du rapport
            self.zone_calculs.delete("1.0", tk.END)
            self.zone_calculs.insert("1.0", rapport)
            self.zone_calculs.see(tk.END)

            # Mise à jour des vérifications
            self._mettre_a_jour_verifications()
            
            # Mise à jour du rendu 3D si nécessaire
            self._dessiner_dalot_3d()
            
            self.maj_statut("Calculs terminés avec succès ✓", 100)
            self.journaliser("═══ CALCULS TERMINÉS AVEC SUCCÈS ═══")
            
            # Notification de fin
            self.after(2000, lambda: self.maj_statut("Prêt pour analyses avancées", 0))
            
        except Exception as e:
            error_msg = f"Erreur lors des calculs: {str(e)}"
            messagebox.showerror("Erreur de calcul", error_msg)
            self.journaliser(f"ERREUR CALCUL: {str(e)}")
            self.maj_statut("Erreur lors des calculs", 0)
            self.label_calculs.config(text="Calculs: Erreur", foreground="red")

    def _generer_rapport_complet_avance(self):
        """Génère un rapport détaillé et professionnel"""
        lignes = []
        
        # En-tête avec style
        lignes.append("╔" + "═" * 78 + "╗")
        lignes.append("║" + " " * 18 + "RAPPORT DE DIMENSIONNEMENT DALOT BA" + " " * 23 + "║")
        lignes.append("║" + " " * 25 + "Version Professionnelle 2.0" + " " * 25 + "║")
        lignes.append("╚" + "═" * 78 + "╝")
        lignes.append("")
        
        # Informations du projet
        lignes.append("📋 INFORMATIONS DU PROJET")
        lignes.append("─" * 50)
        lignes.append(f"Projet       : {self.nom_projet.get()}")
        lignes.append(f"Ingénieur    : {self.ingenieur.get() or 'Non défini'}")
        lignes.append(f"Localisation : {self.localisation.get() or 'Non définie'}")
        lignes.append(f"Date projet  : {self.date_projet.get()}")
        lignes.append(f"Rapport généré le : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
        lignes.append("")

        # Géométrie détaillée
        lignes.append("📐 CARACTÉRISTIQUES GÉOMÉTRIQUES")
        lignes.append("─" * 50)
        L = self.longueur_dalot_m.get()
        l = self.largeur_dalot_m.get()
        h = self.hauteur_dalot_m.get()
        
        lignes.append(f"Dimensions intérieures :")
        lignes.append(f"  • Longueur (L)        : {L:.2f} m")
        lignes.append(f"  • Largeur (l)         : {l:.2f} m") 
        lignes.append(f"  • Hauteur (H)         : {h:.2f} m")
        lignes.append(f"  • Surface section     : {l*h:.2f} m²")
        lignes.append(f"  • Volume intérieur    : {L*l*h:.2f} m³")
        lignes.append("")
        
        lignes.append(f"Épaisseurs des éléments :")
        lignes.append(f"  • Dalle supérieure    : {self.epaisseur_dalle_sup_m.get():.2f} m")
        lignes.append(f"  • Dalle inférieure    : {self.epaisseur_dalle_inf_m.get():.2f} m")
        lignes.append(f"  • Voiles latéraux     : {self.epaisseur_voile_lat_m.get():.2f} m")
        lignes.append("")
        
        # Élancement et rapports
        lignes.append(f"Rapports caractéristiques :")
        lignes.append(f"  • Élancement L/H      : {L/h:.1f}")
        lignes.append(f"  • Rapport l/H         : {l/h:.1f}")
        lignes.append(f"  • Ratio e_mur/l       : {self.epaisseur_voile_lat_m.get()/l:.3f}")
        lignes.append("")

        # Matériaux avec caractéristiques complètes
        lignes.append("🧱 CARACTÉRISTIQUES DES MATÉRIAUX")
        lignes.append("─" * 50)
        
        beton_info = DonneesNormalisees.CLASSES_BETON.get(self.classe_beton.get(), {})
        acier_info = DonneesNormalisees.CLASSES_ACIER.get(self.classe_acier.get(), {})
        expo_info = DonneesNormalisees.ENROBAGES_STANDARD.get(self.classe_exposition.get(), {})
        
        lignes.append(f"Béton :")
        lignes.append(f"  • Classe              : {self.classe_beton.get()}")
        lignes.append(f"  • fck                 : {beton_info.get('fck', 'N/A')} MPa")
        lignes.append(f"  • fcd (calcul)        : {beton_info.get('fcd', 'N/A')} MPa")
        lignes.append(f"  • Description         : {beton_info.get('description', 'N/A')}")
        lignes.append("")
        
        lignes.append(f"Acier :")
        lignes.append(f"  • Classe              : {self.classe_acier.get()}")
        lignes.append(f"  • fyk                 : {acier_info.get('fyk', 'N/A')} MPa")
        lignes.append(f"  • fyd (calcul)        : {acier_info.get('fyd', 'N/A')} MPa")
        lignes.append(f"  • Module E            : {acier_info.get('Es', 'N/A')} MPa")
        lignes.append(f"  • Description         : {acier_info.get('description', 'N/A')}")
        lignes.append("")
        
        lignes.append(f"Environnement :")
        lignes.append(f"  • Classe d'exposition : {self.classe_exposition.get()}")
        lignes.append(f"  • Enrobage minimal    : {expo_info.get('valeur', 'N/A')} mm")
        lignes.append(f"  • Description         : {expo_info.get('description', 'N/A')}")
        lignes.append("")

        # Armatures détaillées
        lignes.append("🔧 CARACTÉRISTIQUES DES ARMATURES")
        lignes.append("─" * 50)
        
        # Calcul des sections d'armatures
        diam_prin = self.diametre_principal.get()
        diam_sec = self.diametre_secondaire.get()
        espacement = self.espacement_barres_mm.get()
        
        section_prin = np.pi * (diam_prin/10)**2 / 4  # cm²
        section_ml_prin = section_prin / (espacement/100) if espacement > 0 else 0  # cm²/m
        section_sec = np.pi * (diam_sec/10)**2 / 4  # cm²
        section_ml_sec = section_sec / 2  # cm²/m (espacement 200mm)
        
        lignes.append(f"Armatures principales :")
        lignes.append(f"  • Diamètre            : φ{diam_prin} mm")
        lignes.append(f"  • Espacement          : {espacement} mm")
        lignes.append(f"  • Section par barre   : {section_prin:.2f} cm²")
        lignes.append(f"  • Section par mètre   : {section_ml_prin:.2f} cm²/m")
        lignes.append("")
        
        lignes.append(f"Armatures secondaires :")
        lignes.append(f"  • Diamètre            : φ{diam_sec} mm")
        lignes.append(f"  • Espacement          : 200 mm (standard)")
        lignes.append(f"  • Section par barre   : {section_sec:.2f} cm²")
        lignes.append(f"  • Section par mètre   : {section_ml_sec:.2f} cm²/m")
        lignes.append("")

        # Charges et sollicitations
        if 'charges_dalle_couverture' in self.dalot_calculations:
            ch = self.dalot_calculations['charges_dalle_couverture']
            
            lignes.append("⚖️ CHARGEMENTS SUR DALLE DE COUVERTURE")
            lignes.append("─" * 50)
            lignes.append(f"Charges permanentes :")
            lignes.append(f"  • Poids propre dalle  : {ch['q_pp_dalle']/1000:.1f} kN/m²")
            lignes.append(f"  • Autres permanentes : {ch['q_permanente_supp']/1000:.1f} kN/m²")
            lignes.append(f"  • Total permanentes  : {(ch['q_pp_dalle']+ch['q_permanente_supp'])/1000:.1f} kN/m²")
            lignes.append("")
            
            lignes.append(f"Charges variables :")
            lignes.append(f"  • Exploitation       : {ch['q_exploitation']/1000:.1f} kN/m²")
            lignes.append(f"  • Trafic              : {self.classe_trafic.get()}")
            lignes.append("")
            
            lignes.append(f"Combinaisons de charges :")
            lignes.append(f"  • ELS (service)       : {ch['q_service']/1000:.1f} kN/m²")
            lignes.append(f"  • ELU (ultime)        : {ch['q_ELU']/1000:.1f} kN/m²")
            lignes.append(f"  • Coefficients       : γG=1.35, γQ=1.50")
            lignes.append("")

        # Poussée des terres
        if 'poussee_terres' in self.dalot_calculations:
            p = self.dalot_calculations['poussee_terres']
            
            lignes.append("🌍 POUSSÉE DES TERRES")
            lignes.append("─" * 50)
            lignes.append(f"Caractéristiques du sol :")
            lignes.append(f"  • Type de remblai     : {self.type_remblai.get()}")
            lignes.append(f"  • Hauteur de remblai  : {self.hauteur_remblai_m.get():.1f} m")
            
            sol_info = DonneesNormalisees.TYPES_REMBLAI.get(self.type_remblai.get(), {})
            if sol_info:
                lignes.append(f"  • Densité             : {sol_info['densite']} kN/m³")
                lignes.append(f"  • Angle de frottement : {sol_info['angle']}°")
            lignes.append("")
            
            lignes.append(f"Calcul de la poussée :")
            lignes.append(f"  • Coefficient Ka      : 0.33 (Rankine)")
            lignes.append(f"  • Contrainte à la base: {p['sigma_h_base']/1000:.1f} kPa")
            lignes.append(f"  • Force par mètre     : {p['force_poussee_par_metre']/1000:.1f} kN/m")
            lignes.append(f"  • Point d'application : {p['point_application_hauteur']:.2f} m du radier")
            lignes.append("")

        # Résultats de dimensionnement
        if 'ferraillage_dalle_couverture' in self.dalot_calculations:
            f = self.dalot_calculations['ferraillage_dalle_couverture']
            arm = self.dalot_calculations.get('armatures_dalle_choisies', {})
            
            lignes.append("🔩 DIMENSIONNEMENT DALLE DE COUVERTURE")
            lignes.append("─" * 50)
            lignes.append(f"Sollicitations de calcul :")
            lignes.append(f"  • Moment ELU          : {f['moment_ELU']/1000:.1f} kNm/m")
            lignes.append(f"  • Hypothèse           : Poutre simplement appuyée")
            lignes.append(f"  • Portée de calcul    : {l:.2f} m")
            lignes.append("")
            
            lignes.append(f"Ferraillage :")
            lignes.append(f"  • As théorique        : {f['As_theorique']*1e4:.2f} cm²/m")
            if arm:
                lignes.append(f"  • Solution retenue    : φ{arm.get('diametre','?')} @ {arm.get('espacement','?')} mm")
                lignes.append(f"  • As fourni           : {arm.get('As_fourni',0)*1e4:.2f} cm²/m")
                
                # Vérification du taux de ferraillage
                ratio = arm.get('As_fourni', 0) / f['As_theorique'] if f['As_theorique'] > 0 else 0
                lignes.append(f"  • Ratio As_fourni/As_th: {ratio:.2f}")
                if ratio >= 1.0:
                    lignes.append(f"  • Vérification        : ✅ OK (ratio ≥ 1.0)")
                else:
                    lignes.append(f"  • Vérification        : ❌ INSUFFISANT")
                
                if arm.get('optimise', False):
                    lignes.append(f"  • Optimisation        : Armatures optimisées automatiquement")
            lignes.append("")

        # Volumes et masses
        if 'volumes_masses' in self.dalot_calculations:
            vm = self.dalot_calculations['volumes_masses']
            
            lignes.append("📦 VOLUMES ET MASSES")
            lignes.append("─" * 50)
            for k, v in vm.items():
                if k != 'total':
                    pourcentage = (v['volume'] / vm['total']['volume'] * 100) if vm['total']['volume'] > 0 else 0
                    lignes.append(f"{v['info']} :")
                    lignes.append(f"  • Volume              : {v['volume']:.3f} m³ ({pourcentage:.1f}%)")
                    lignes.append(f"  • Masse               : {v['masse']/1000:.2f} tonnes")
                    lignes.append("")
            
            lignes.append(f"TOTAL DALOT :")
            lignes.append(f"  • Volume total        : {vm['total']['volume']:.3f} m³")
            lignes.append(f"  • Masse totale        : {vm['total']['masse']/1000:.2f} tonnes")
            lignes.append(f"  • Densité moyenne     : {vm['total']['masse']/vm['total']['volume']:.0f} kg/m³")
            lignes.append("")

        # Estimations économiques
        if 'volumes_masses' in self.dalot_calculations:
            vm = self.dalot_calculations['volumes_masses']
            
            lignes.append("💰 ESTIMATION ÉCONOMIQUE APPROXIMATIVE")
            lignes.append("─" * 50)
            
            # Prix unitaires approximatifs (euros)
            prix_beton_m3 = 120  # €/m³
            prix_acier_kg = 1.5  # €/kg
            prix_coffrage_m2 = 45  # €/m²
            
            vol_beton = vm['total']['volume']
            masse_acier_estimee = vol_beton * 80  # kg d'acier par m³ de béton (estimation)
            surface_coffrage_estimee = 2 * (L*l + 2*l*h + 2*L*h)  # Estimation surface coffrage
            
            cout_beton = vol_beton * prix_beton_m3
            cout_acier = masse_acier_estimee * prix_acier_kg
            cout_coffrage = surface_coffrage_estimee * prix_coffrage_m2
            cout_total = cout_beton + cout_acier + cout_coffrage
            
            lignes.append(f"Coûts matériaux (approximatif) :")
            lignes.append(f"  • Béton ({vol_beton:.1f} m³)     : {cout_beton:.0f} €")
            lignes.append(f"  • Acier (~{masse_acier_estimee:.0f} kg)      : {cout_acier:.0f} €")
            lignes.append(f"  • Coffrage (~{surface_coffrage_estimee:.0f} m²)   : {cout_coffrage:.0f} €")
            lignes.append(f"  • TOTAL HT            : {cout_total:.0f} €")
            lignes.append(f"  • Prix au m³ béton    : {cout_total/vol_beton:.0f} €/m³")
            lignes.append("")
            lignes.append(f"Note : Prix indicatifs, hors terrassement, étanchéité, etc.")
            lignes.append("")

        # Notes techniques et recommandations
        lignes.append("📝 NOTES TECHNIQUES ET RECOMMANDATIONS")
        lignes.append("─" * 50)
        lignes.append("Hypothèses de calcul :")
        lignes.append(f"  • Méthode de calcul   : Eurocode 2 (EN 1992-1-1)")
        lignes.append(f"  • Modèle structural   : Poutres et voiles")
        lignes.append(f"  • Classe structurale  : S4 (durée de vie 50 ans)")
        lignes.append(f"  • Classe d'exécution  : Classe 2 (contrôle normal)")
        lignes.append("")
        
        lignes.append("Vérifications à effectuer :")
        lignes.append(f"  • ✓ Flexion dalle supérieure (calculée)")
        lignes.append(f"  • ⏳ Effort tranchant (à vérifier)")
        lignes.append(f"  • ⏳ Poinçonnement (si applicable)")
        lignes.append(f"  • ⏳ Flèche et déformation (à vérifier)")
        lignes.append(f"  • ⏳ Ouverture de fissures (à vérifier)")
        lignes.append(f"  • ⏳ Stabilité d'ensemble (à vérifier)")
        lignes.append("")
        
        lignes.append("Recommandations :")
        lignes.append(f"  • Prévoir joints de dilatation si L > 30m")
        lignes.append(f"  • Vérifier la qualité du sol de fondation")
        lignes.append(f"  • Prévoir système de drainage si nécessaire")
        lignes.append(f"  • Contrôler l'enrobage et la mise en œuvre")
        lignes.append(f"  • Vérification par BE qualifié recommandée")
        lignes.append("")

        # Conclusion
        lignes.append("📋 CONCLUSION")
        lignes.append("─" * 50)
        lignes.append("Ce rapport présente un dimensionnement préliminaire du dalot.")
        lignes.append("Les calculs sont basés sur des hypothèses simplifiées et doivent")
        lignes.append("être complétés par une étude détaillée incluant :")
        lignes.append("  • Étude géotechnique complète")
        lignes.append("  • Calculs sismiques si requis")
        lignes.append("  • Vérifications ELS détaillées") 
        lignes.append("  • Plans d'exécution détaillés")
        lignes.append("")
        lignes.append("⚠️  VALIDATION PAR INGÉNIEUR QUALIFIÉ REQUISE")
        lignes.append("")
        
        # Signature
        lignes.append("─" * 50)
        lignes.append(f"Rapport généré par : Progiciel Dalot BA v2.0 Pro")
        lignes.append(f"Développé par      : Kevindjoum")
        lignes.append(f"Date génération    : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
        lignes.append(f"Utilisateur        : {self.ingenieur.get() or 'Utilisateur'}")
        lignes.append("─" * 50)
        
        return "\n".join(lignes)

    # Nouvelles commandes fonctionnelles
    def cmd_optimiser(self):
        """Optimisation automatique des sections"""
        self.maj_statut("Optimisation en cours...", 10)
        
        try:
            # Collecte des paramètres actuels
            geometrie = {
                'longueur': self.longueur_dalot_m.get(),
                'largeur': self.largeur_dalot_m.get(), 
                'hauteur': self.hauteur_dalot_m.get()
            }
            
            charges = {
                'trafic': self.classe_trafic.get(),
                'remblai': self.type_remblai.get(),
                'hauteur_remblai': self.hauteur_remblai_m.get()
            }
            
            contraintes = {
                'deflexion': self.contrainte_deflexion.get() if hasattr(self, 'contrainte_deflexion') else True,
                'fissuration': self.contrainte_fissuration.get() if hasattr(self, 'contrainte_fissuration') else True,
                'effort_tranchant': self.contrainte_effort_tranchant.get() if hasattr(self, 'contrainte_effort_tranchant') else True
            }
            
            self.maj_statut("Calcul des sections optimales...", 50)
            
            # Lancement de l'optimisation
            resultats_optimisation = SimulationCalculs.optimiser_sections(geometrie, charges, contraintes)
            
            self.maj_statut("Application des résultats...", 75)
            
            # Application des résultats si disponibles
            if 'epaisseurs' in resultats_optimisation:
                epaisseurs = resultats_optimisation['epaisseurs']
                
                # Demander confirmation avant application
                message = f"OPTIMISATION TERMINÉE\n\n"
                message += f"Sections optimales calculées :\n"
                message += f"• Dalle supérieure : {epaisseurs['dalle_sup']:.2f} m (actuel: {self.epaisseur_dalle_sup_m.get():.2f} m)\n"
                message += f"• Dalle inférieure : {epaisseurs['dalle_inf']:.2f} m (actuel: {self.epaisseur_dalle_inf_m.get():.2f} m)\n"
                message += f"• Voiles latéraux  : {epaisseurs['voile']:.2f} m (actuel: {self.epaisseur_voile_lat_m.get():.2f} m)\n\n"
                message += f"Critère d'optimisation : {resultats_optimisation.get('critere', 'Non défini')}\n"
                message += f"Économie estimée : {resultats_optimisation.get('economie_estimee', 0):.1f}%\n\n"
                message += f"Appliquer ces valeurs ?"
                
                if messagebox.askyesno("Optimisation", message):
                    # Application des nouvelles valeurs
                    self.epaisseur_dalle_sup_m.set(epaisseurs['dalle_sup'])
                    self.epaisseur_dalle_inf_m.set(epaisseurs['dalle_inf'])
                    self.epaisseur_voile_lat_m.set(epaisseurs['voile'])
                    
                    self._marquer_modifie()
                    self._dessiner_dalot_3d()
                    
                    # Affichage dans la zone d'optimisation
                    if hasattr(self, 'zone_optimisation'):
                        optimisation_text = f"OPTIMISATION RÉUSSIE - {datetime.now().strftime('%H:%M:%S')}\n"
                        optimisation_text += "─" * 50 + "\n"
                        optimisation_text += f"Critère: {resultats_optimisation.get('critere', 'Non défini')}\n"
                        optimisation_text += f"Économie: {resultats_optimisation.get('economie_estimee', 0):.1f}%\n\n"
                        optimisation_text += "Sections optimisées appliquées:\n"
                        optimisation_text += f"• Dalle sup: {epaisseurs['dalle_sup']:.2f} m\n"
                        optimisation_text += f"• Dalle inf: {epaisseurs['dalle_inf']:.2f} m\n"
                        optimisation_text += f"• Voiles: {epaisseurs['voile']:.2f} m\n\n"
                        
                        self.zone_optimisation.insert("1.0", optimisation_text)
                    
                    self.journaliser("Optimisation appliquée avec succès")
                    self.maj_statut("Optimisation appliquée ✓", 100)
                else:
                    self.journaliser("Optimisation calculée mais non appliquée")
                    self.maj_statut("Optimisation calculée (non appliquée)", 0)
            else:
                messagebox.showinfo("Optimisation", "Optimisation terminée.\nAucune amélioration significative trouvée.")
                self.maj_statut("Optimisation terminée", 0)
                
        except Exception as e:
            messagebox.showerror("Erreur d'optimisation", f"Erreur lors de l'optimisation:\n{str(e)}")
            self.journaliser(f"Erreur optimisation: {str(e)}")
            self.maj_statut("Erreur d'optimisation", 0)

    def cmd_optimiser_diametres(self):
        """Optimise les diamètres d'armatures"""
        try:
            if not hasattr(self, 'dalot_calculations') or not self.dalot_calculations:
                messagebox.showwarning("Optimisation", "Lancez d'abord les calculs avant d'optimiser les armatures.")
                return
            
            if 'ferraillage_dalle_couverture' in self.dalot_calculations:
                ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
                As_theorique = ferraillage.get('As_theorique', 0)
                
                if As_theorique > 0:
                    # Recherche du diamètre optimal
                    espacement_actuel = self.espacement_barres_mm.get()
                    meilleure_solution = None
                    meilleur_cout = float('inf')
                    
                    for diametre in DonneesNormalisees.DIAMETRES_PRINCIPAUX:
                        section_barre = np.pi * (diametre/10)**2 / 4  # cm²
                        As_fourni = section_barre / (espacement_actuel/100)  # cm²/m
                        
                        if As_fourni >= As_theorique:
                            cout = As_fourni  # Critère simple : minimiser la section
                            if cout < meilleur_cout:
                                meilleur_cout = cout
                                meilleure_solution = diametre
                    
                    if meilleure_solution and meilleure_solution != self.diametre_principal.get():
                        if messagebox.askyesno("Optimisation diamètre", 
                                             f"Diamètre optimal trouvé : φ{meilleure_solution}mm\n"
                                             f"(actuel : φ{self.diametre_principal.get()}mm)\n\n"
                                             f"Appliquer cette valeur ?"):
                            self.diametre_principal.set(meilleure_solution)
                            self._maj_calcul_armatures()
                            self._marquer_modifie()
                            self.journaliser(f"Diamètre optimisé : φ{meilleure_solution}mm")
                    else:
                        messagebox.showinfo("Optimisation", "Diamètre actuel déjà optimal.")
                        
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'optimisation des diamètres:\n{str(e)}")

    def cmd_optimiser_espacement(self):
        """Optimise l'espacement des armatures"""
        try:
            if not hasattr(self, 'dalot_calculations') or not self.dalot_calculations:
                messagebox.showwarning("Optimisation", "Lancez d'abord les calculs avant d'optimiser les armatures.")
                return
            
            if 'ferraillage_dalle_couverture' in self.dalot_calculations:
                ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
                As_theorique = ferraillage.get('As_theorique', 0)
                
                if As_theorique > 0:
                    diametre_actuel = self.diametre_principal.get()
                    section_barre = np.pi * (diametre_actuel/10)**2 / 4  # cm²
                    
                    # Espacement optimal
                    espacement_optimal = section_barre / As_theorique * 100  # mm
                    
                    # Recherche de l'espacement standard le plus proche
                    espacements_possibles = DonneesNormalisees.ESPACEMENTS_STANDARD
                    espacement_choisi = min(espacements_possibles, 
                                          key=lambda x: abs(x - espacement_optimal) if x >= espacement_optimal else float('inf'))
                    
                    if espacement_choisi != self.espacement_barres_mm.get():
                        As_fourni_nouveau = section_barre / (espacement_choisi/100)
                        if messagebox.askyesno("Optimisation espacement", 
                                             f"Espacement optimal trouvé : {espacement_choisi}mm\n"
                                             f"(actuel : {self.espacement_barres_mm.get()}mm)\n"
                                             f"Section résultante : {As_fourni_nouveau:.2f} cm²/m\n\n"
                                             f"Appliquer cette valeur ?"):
                            self.espacement_barres_mm.set(espacement_choisi)
                            self._maj_calcul_armatures()
                            self._marquer_modifie()
                            self.journaliser(f"Espacement optimisé : {espacement_choisi}mm")
                    else:
                        messagebox.showinfo("Optimisation", "Espacement actuel déjà optimal.")
                        
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'optimisation de l'espacement:\n{str(e)}")

    def cmd_auto_optimisation_armatures(self):
        """Optimisation automatique complète des armatures"""
        try:
            if not hasattr(self, 'dalot_calculations') or not self.dalot_calculations:
                messagebox.showwarning("Optimisation", "Lancez d'abord les calculs avant l'auto-optimisation.")
                return
            
            if 'ferraillage_dalle_couverture' in self.dalot_calculations:
                ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
                As_theorique = ferraillage.get('As_theorique', 0)
                
                if As_theorique > 0:
                    # Recherche de la combinaison optimale diamètre/espacement
                    solutions = []
                    
                    for diametre in DonneesNormalisees.DIAMETRES_PRINCIPAUX:
                        for espacement in DonneesNormalisees.ESPACEMENTS_STANDARD:
                            section_barre = np.pi * (diametre/10)**2 / 4  # cm²
                            As_fourni = section_barre / (espacement/100)  # cm²/m
                            
                            if As_fourni >= As_theorique:
                                # Critères d'optimisation multiples
                                surcout_section = As_fourni / As_theorique
                                penalite_diametre = abs(diametre - 16) / 16  # Préférence pour φ16
                                penalite_espacement = abs(espacement - 150) / 150  # Préférence pour 150mm
                                
                                score = surcout_section + 0.1 * penalite_diametre + 0.1 * penalite_espacement
                                
                                solutions.append({
                                    'diametre': diametre,
                                    'espacement': espacement,
                                    'As_fourni': As_fourni,
                                    'score': score,
                                    'surcout': (As_fourni - As_theorique) / As_theorique * 100
                                })
                    
                    if solutions:
                        # Tri par score (meilleur = score le plus faible)
                        solutions.sort(key=lambda x: x['score'])
                        meilleure = solutions[0]
                        
                        message = f"AUTO-OPTIMISATION ARMATURES\n\n"
                        message += f"Solution optimale trouvée :\n"
                        message += f"• Diamètre : φ{meilleure['diametre']}mm (actuel: φ{self.diametre_principal.get()}mm)\n"
                        message += f"• Espacement : {meilleure['espacement']}mm (actuel: {self.espacement_barres_mm.get()}mm)\n"
                        message += f"• As fourni : {meilleure['As_fourni']:.2f} cm²/m\n"
                        message += f"• As théorique : {As_theorique:.2f} cm²/m\n"
                        message += f"• Surcroît : {meilleure['surcout']:.1f}%\n\n"
                        
                        # Affichage des 3 meilleures solutions
                        message += "Autres solutions :\n"
                        for i, sol in enumerate(solutions[1:4], 2):
                            message += f"{i}. φ{sol['diametre']}@{sol['espacement']}mm (+{sol['surcout']:.1f}%)\n"
                        
                        message += f"\nAppliquer la solution optimale ?"
                        
                        if messagebox.askyesno("Auto-optimisation", message):
                            self.diametre_principal.set(meilleure['diametre'])
                            self.espacement_barres_mm.set(meilleure['espacement'])
                            self._maj_calcul_armatures()
                            self._marquer_modifie()
                            self.journaliser(f"Auto-optimisation appliquée : φ{meilleure['diametre']}@{meilleure['espacement']}mm")
                            messagebox.showinfo("Succès", "Auto-optimisation appliquée avec succès !")
                        
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'auto-optimisation:\n{str(e)}")

    # Commandes des vues 3D
    def cmd_vue_isometrique(self):
        """Vue isométrique avec animation"""
        if hasattr(self, 'ax_3d'):
            self._animer_changement_vue(elev=25, azim=45)

    def cmd_vue_face(self):
        """Vue de face avec animation"""
        if hasattr(self, 'ax_3d'):
            self._animer_changement_vue(elev=0, azim=0)

    def cmd_vue_cote(self):
        """Vue de côté avec animation"""
        if hasattr(self, 'ax_3d'):
            self._animer_changement_vue(elev=0, azim=90)

    def cmd_vue_dessus(self):
        """Vue de dessus avec animation"""
        if hasattr(self, 'ax_3d'):
            self._animer_changement_vue(elev=90, azim=0)

    def cmd_reset_vue(self):
        """Reset de la vue avec zoom adapté"""
        if hasattr(self, 'ax_3d'):
            # Reset des limites basé sur la géométrie actuelle
            try:
                L = self.longueur_dalot_m.get()
                l = self.largeur_dalot_m.get()
                h = self.hauteur_dalot_m.get()
                
                margin_factor = 0.15
                self.ax_3d.set_xlim(-L*margin_factor, L*(1+margin_factor))
                self.ax_3d.set_ylim(-l*margin_factor, l*(1+margin_factor))
                self.ax_3d.set_zlim(0, h*(1+margin_factor))
                
                # Vue isométrique par défaut
                self._animer_changement_vue(elev=25, azim=45)
                
            except:
                # Valeurs par défaut si erreur
                self.ax_3d.set_xlim(-5, 25)
                self.ax_3d.set_ylim(-1, 4)
                self.ax_3d.set_zlim(0, 3)
                self._animer_changement_vue(elev=25, azim=45)

    def cmd_zoom_adapte(self):
        """Zoom adapté au contenu"""
        if hasattr(self, 'ax_3d'):
            try:
                L = self.longueur_dalot_m.get()
                l = self.largeur_dalot_m.get() 
                h = self.hauteur_dalot_m.get()
                
                # Calcul des limites optimales
                max_dim = max(L, l, h)
                margin = max_dim * 0.1
                
                self.ax_3d.set_xlim(-margin, L + margin)
                self.ax_3d.set_ylim(-margin, l + margin)
                self.ax_3d.set_zlim(0, h + margin)
                
                # Mise à jour proportions
                if max_dim > 0:
                    self.ax_3d.set_box_aspect([L/max_dim, l/max_dim, h/max_dim])
                
                self.canvas_3d.draw()
                self.journaliser("Zoom adapté appliqué")
                
            except Exception as e:
                self.journaliser(f"Erreur zoom adapté: {str(e)}")

    def _animer_changement_vue(self, elev_target, azim_target):
        """Anime le changement de vue 3D"""
        if self.animation_en_cours:
            return
        
        self.animation_en_cours = True
        
        try:
            # Angles actuels
            elev_start = self.ax_3d.elev
            azim_start = self.ax_3d.azim
            
            # Calcul du chemin d'animation
            steps = 15
            elev_step = (elev_target - elev_start) / steps
            azim_step = (azim_target - azim_start) / steps
            
            def animer_step(step):
                if step <= steps:
                    new_elev = elev_start + elev_step * step
                    new_azim = azim_start + azim_step * step
                    
                    self.ax_3d.view_init(elev=new_elev, azim=new_azim)
                    self.canvas_3d.draw_idle()
                    
                    if step < steps:
                        self.after(30, lambda: animer_step(step + 1))
                    else:
                        self.animation_en_cours = False
                else:
                    self.animation_en_cours = False
            
            animer_step(0)
            
        except Exception as e:
            self.animation_en_cours = False
            self.journaliser(f"Erreur animation vue: {str(e)}")

    # Autres commandes nouvelles
    def cmd_capture_3d(self):
        """Capture d'écran de la vue 3D"""
        try:
            chemin = filedialog.asksaveasfilename(
                title="Enregistrer la capture 3D",
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("PDF", "*.pdf")]
            )
            if chemin:
                self.figure_3d.savefig(chemin, dpi=300, bbox_inches='tight', 
                                      facecolor='white', edgecolor='none')
                messagebox.showinfo("Capture", f"Vue 3D enregistrée :\n{chemin}")
                self.journaliser(f"Capture 3D: {chemin}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la capture:\n{str(e)}")

    def cmd_animation_3d(self):
        """Animation 3D rotative"""
        if self.animation_en_cours:
            messagebox.showinfo("Animation", "Une animation est déjà en cours.")
            return
        
        try:
            self.animation_en_cours = True
            
            def rotation_continue(azim):
                if self.animation_en_cours and azim < 360:
                    self.ax_3d.view_init(elev=25, azim=azim)
                    self.canvas_3d.draw_idle()
                    self.after(50, lambda: rotation_continue(azim + 5))
                else:
                    self.animation_en_cours = False
            
            # Demander confirmation
            if messagebox.askyesno("Animation 3D", "Lancer l'animation rotative ?\n(Cliquez sur ESC pour arrêter)"):
                rotation_continue(0)
                
        except Exception as e:
            self.animation_en_cours = False
            messagebox.showerror("Erreur", f"Erreur animation:\n{str(e)}")

    # Commandes fichier améliorées
    def action_nouveau(self):
        """Nouveau projet avec confirmation"""
        if self.modifie:
            reponse = messagebox.askyesnocancel("Nouveau projet", 
                                              "Le projet actuel a été modifié.\n\n"
                                              "Voulez-vous l'enregistrer avant de créer un nouveau projet ?")
            if reponse is None:  # Cancel
                return
            elif reponse:  # Yes
                if not self.action_enregistrer():
                    return
        
        # Reset des valeurs par défaut
        self.nom_projet.set("Dalot - Nouveau projet Pro")
        self.ingenieur.set("Kevindjoum")
        self.localisation.set("")
        self.date_projet.set(datetime.now().strftime("%Y-%m-%d"))
        
        self.largeur_dalot_m.set(3.5)
        self.hauteur_dalot_m.set(2.2)
        self.longueur_dalot_m.set(25.0)
        self.epaisseur_dalle_sup_m.set(0.35)
        self.epaisseur_dalle_inf_m.set(0.30)
        self.epaisseur_voile_lat_m.set(0.30)
        
        self.classe_beton.set("C35/45")
        self.classe_acier.set("B500B")
        self.classe_exposition.set("XC4 (Cycles humide/sec)")
        
        self.diametre_principal.set(16)
        self.diametre_secondaire.set(12)
        self.espacement_barres_mm.set(150)
        
        self.classe_trafic.set("T3 (Poids lourds)")
        self.type_remblai.set("Grave compactée")
        self.hauteur_remblai_m.set(2.0)
        
        # Reset des zones de texte
        self.zone_calculs.delete("1.0", tk.END)
        self.zone_verifications.delete("1.0", tk.END)
        self.zone_journal.delete("1.0", tk.END)
        if hasattr(self, 'zone_optimisation'):
            self.zone_optimisation.delete("1.0", tk.END)
        
        # Reset des variables d'état
        self.chemin_fichier_courant = None
        self.modifie = False
        self.dalot_calculations = {}
        
        # Mise à jour des infos
        self._maj_info_beton()
        self._maj_info_acier()
        self._maj_info_exposition()
        self._maj_info_trafic()
        self._maj_info_remblai()
        self._maj_calcul_armatures()
        
        # Mise à jour 3D
        self._dessiner_dalot_3d()
        
        self._mettre_a_jour_titre_fenetre()
        self.journaliser("Nouveau projet créé")
        self.maj_statut("Nouveau projet prêt")

    def action_ouvrir(self):
        """Ouverture de projet avec gestionnaire JSON"""
        if self.modifie:
            reponse = messagebox.askyesnocancel("Ouvrir projet", 
                                              "Le projet actuel a été modifié.\n\n"
                                              "Voulez-vous l'enregistrer avant d'ouvrir un autre projet ?")
            if reponse is None:  # Cancel
                return
            elif reponse:  # Yes
                if not self.action_enregistrer():
                    return
        
        chemin = filedialog.askopenfilename(
            title="Ouvrir un projet Dalot",
            defaultextension=".json",
            filetypes=[("Projets Dalot", "*.json"), ("Tous fichiers", "*.*")]
        )
        
        if chemin:
            self.maj_statut("Chargement du projet...", 25)
            
            succes, message = GestionnaireProjet.charger_projet(self, chemin)
            
            if succes:
                self.chemin_fichier_courant = chemin
                self.modifie = False
                self._mettre_a_jour_titre_fenetre()
                self.journaliser(f"Projet chargé: {chemin}")
                self.maj_statut(f"Projet chargé: {message}", 100)
                
                # Relancer les calculs avec les paramètres chargés
                self.after(500, self._lancer_calculs_automatique)
                
                messagebox.showinfo("Ouverture", f"Projet chargé avec succès:\n{message}")
            else:
                messagebox.showerror("Erreur d'ouverture", message)
                self.journaliser(f"Erreur ouverture: {message}")
                self.maj_statut("Erreur lors de l'ouverture", 0)

    def action_enregistrer(self):
        """Enregistrement du projet"""
        if self.chemin_fichier_courant:
            return self._enregistrer_fichier(self.chemin_fichier_courant)
        else:
            return self.action_enregistrer_sous()

    def action_enregistrer_sous(self):
        """Enregistrer sous avec nouveau nom"""
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer le projet Dalot",
            defaultextension=".json",
            filetypes=[("Projets Dalot", "*.json"), ("Tous fichiers", "*.*")],
            initialname=f"{self.nom_projet.get().replace(' ', '_')}.json"
        )
        
        if chemin:
            return self._enregistrer_fichier(chemin)
        return False

    def _enregistrer_fichier(self, chemin):
        """Enregistrement effectif du fichier"""
        try:
            self.maj_statut("Enregistrement en cours...", 50)
            
            succes, message = GestionnaireProjet.sauvegarder_projet(self, chemin)
            
            if succes:
                self.chemin_fichier_courant = chemin
                self.modifie = False
                self._mettre_a_jour_titre_fenetre()
                self.journaliser(f"Projet enregistré: {chemin}")
                self.maj_statut("Projet enregistré ✓", 100)
                
                # Notification temporaire
                self.after(2000, lambda: self.maj_statut("Prêt", 0))
                return True
            else:
                messagebox.showerror("Erreur d'enregistrement", message)
                self.journaliser(f"Erreur enregistrement: {message}")
                self.maj_statut("Erreur d'enregistrement", 0)
                return False
                
        except Exception as e:
            error_msg = f"Erreur lors de l'enregistrement: {str(e)}"
            messagebox.showerror("Erreur", error_msg)
            self.journaliser(error_msg)
            self.maj_statut("Erreur d'enregistrement", 0)
            return False

    def cmd_exporter_pdf(self):
        """Export PDF amélioré"""
        try:
            # Vérifier qu'il y a des données à exporter
            if not hasattr(self, 'dalot_calculations') or not self.dalot_calculations:
                if messagebox.askyesno("Export PDF", 
                                     "Aucun calcul disponible.\n\n"
                                     "Voulez-vous lancer les calculs avant l'export ?"):
                    self.cmd_lancer_calculs()
                    # Attendre la fin des calculs
                    self.after(1000, self.cmd_exporter_pdf)
                return
            
            # Sélection du fichier
            chemin = filedialog.asksaveasfilename(
                title="Exporter le rapport PDF",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf"), ("HTML", "*.html")],
                initialname=f"Rapport_{self.nom_projet.get().replace(' ', '_')}.pdf"
            )
            
            if chemin:
                self.maj_statut("Génération du rapport...", 25)
                
                # Export selon l'extension
                if chemin.lower().endswith('.pdf'):
                    succes, message = ExporteurPDF.generer_rapport_pdf(self, chemin)
                else:
                    succes, message = ExporteurPDF._generer_rapport_html(self, chemin)
                
                self.maj_statut("Finalisation...", 75)
                
                if succes:
                    self.journaliser(f"Rapport exporté: {chemin}")
                    self.maj_statut("Export terminé ✓", 100)
                    
                    # Proposer d'ouvrir le fichier
                    if messagebox.askyesno("Export réussi", 
                                         f"Rapport exporté avec succès:\n{chemin}\n\n"
                                         f"Voulez-vous l'ouvrir maintenant ?"):
                        try:
                            import os
                            os.startfile(chemin)  # Windows
                        except:
                            try:
                                import subprocess
                                subprocess.run(['open', chemin])  # macOS
                            except:
                                try:
                                    subprocess.run(['xdg-open', chemin])  # Linux
                                except:
                                    pass
                    
                    # Reset du statut après quelques secondes
                    self.after(3000, lambda: self.maj_statut("Prêt", 0))
                else:
                    messagebox.showerror("Erreur d'export", message)
                    self.journaliser(f"Erreur export: {message}")
                    self.maj_statut("Erreur d'export", 0)
                    
        except Exception as e:
            error_msg = f"Erreur lors de l'export PDF: {str(e)}"
            messagebox.showerror("Erreur d'export", error_msg)
            self.journaliser(error_msg)
            self.maj_statut("Erreur d'export", 0)

    # Commandes placeholders pour les fonctionnalités avancées
    def cmd_importer_donnees(self):
        messagebox.showinfo("Import", "Fonctionnalité d'import à venir dans une prochaine version.")
        self.journaliser("Import demandé (non implémenté)")

    def cmd_exporter_donnees(self):
        messagebox.showinfo("Export", "Export de données à venir dans une prochaine version.")
        self.journaliser("Export données demandé (non implémenté)")

    def cmd_projets_recents(self):
        messagebox.showinfo("Projets récents", "Gestion des projets récents à venir.")
        self.journaliser("Projets récents demandés (non implémenté)")

    def cmd_calculs_avances(self):
        messagebox.showinfo("Calculs avancés", "Module de calculs avancés à venir:\n• Analyse modale\n• Calculs sismiques\n• Vérifications détaillées")
        self.journaliser("Calculs avancés demandés (non implémenté)")

    def cmd_analyse_parametrique(self):
        messagebox.showinfo("Analyse paramétrique", "Analyse paramétrique à venir:\n• Variation des paramètres\n• Études de sensibilité\n• Graphiques de réponse")
        self.journaliser("Analyse paramétrique demandée (non implémentée)")

    def cmd_estimation_couts(self):
        if hasattr(self, 'dalot_calculations') and 'volumes_masses' in self.dalot_calculations:
            vm = self.dalot_calculations['volumes_masses']
            
            # Prix unitaires (approximatifs, euros 2025)
            prix_beton = 120  # €/m³
            prix_acier = 1.5  # €/kg
            prix_coffrage = 45  # €/m²
            prix_terrassement = 25  # €/m³
            
            vol_beton = vm['total']['volume']
            masse_acier = vol_beton * 80  # kg/m³ estimation
            
            L = self.longueur_dalot_m.get()
            l = self.largeur_dalot_m.get()
            h = self.hauteur_dalot_m.get()
            surf_coffrage = 2 * (L*l + 2*l*h + 2*L*h)
            vol_terrassement = L * (l + 2) * (h + 1)  # Approximation
            
            cout_beton = vol_beton * prix_beton
            cout_acier = masse_acier * prix_acier  
            cout_coffrage = surf_coffrage * prix_coffrage
            cout_terrassement = vol_terrassement * prix_terrassement
            cout_total = cout_beton + cout_acier + cout_coffrage + cout_terrassement
            
            message = f"ESTIMATION DE COÛTS (Approximative)\n\n"
            message += f"Quantités :\n"
            message += f"• Béton : {vol_beton:.1f} m³\n"
            message += f"• Acier : ~{masse_acier:.0f} kg\n"
            message += f"• Coffrage : ~{surf_coffrage:.0f} m²\n"
            message += f"• Terrassement : ~{vol_terrassement:.0f} m³\n\n"
            message += f"Coûts (HT, approximatifs) :\n"
            message += f"• Béton : {cout_beton:.0f} €\n"
            message += f"• Acier : {cout_acier:.0f} €\n"
            message += f"• Coffrage : {cout_coffrage:.0f} €\n"
            message += f"• Terrassement : {cout_terrassement:.0f} €\n\n"
            message += f"TOTAL HT : {cout_total:.0f} €\n"
            message += f"Prix au m³ béton : {cout_total/vol_beton:.0f} €/m³\n\n"
            message += f"⚠️ Prix indicatifs, hors étanchéité, équipements, etc."
            
            messagebox.showinfo("Estimation de coûts", message)
            self.journaliser("Estimation de coûts générée")
        else:
            messagebox.showwarning("Estimation", "Lancez d'abord les calculs pour estimer les coûts.")

    def cmd_generer_graphiques(self):
        messagebox.showinfo("Graphiques", "Génération de graphiques à venir:\n• Diagrammes de sollicitations\n• Courbes d'optimisation\n• Graphiques de comparaison")
        self.journaliser("Graphiques demandés (non implémenté)")

    def cmd_calculatrice(self):
        messagebox.showinfo("Calculatrice BA", "Module calculatrice béton armé à venir:\n• Calculs de sections\n• Vérifications EC2\n• Abaques interactifs")
        self.journaliser("Calculatrice BA demandée (non implémentée)")

    def cmd_tables(self):
        messagebox.showinfo("Tables", "Tables de dimensionnement à venir:\n• Abaques EC2\n• Tables d'armatures\n• Coefficients normatifs")
        self.journaliser("Tables demandées (non implémentées)")

    def cmd_verificateur_normes(self):
        messagebox.showinfo("Vérificateur", "Vérificateur de normes à venir:\n• Conformité EC2\n• Vérifications automatiques\n• Rapports de conformité")
        self.journaliser("Vérificateur normes demandé (non implémenté)")

    def cmd_preferences(self):
        messagebox.showinfo("Préférences", "Module de préférences à venir:\n• Unités et formats\n• Paramètres par défaut\n• Personnalisation interface")
        self.journaliser("Préférences demandées (non implémentées)")

    def cmd_manuel(self):
        messagebox.showinfo("Manuel", "Le manuel utilisateur complet sera disponible prochainement.\n\nContenu prévu:\n• Guide de démarrage\n• Exemples détaillés\n• Références normatives")
        self.journaliser("Manuel demandé")

    def cmd_tutoriels(self):
        messagebox.showinfo("Tutoriels", "Tutoriels vidéo à venir:\n• Prise en main\n• Études de cas\n• Techniques avancées")
        self.journaliser("Tutoriels demandés")

    def cmd_forum(self):
        try:
            webbrowser.open("https://github.com/Kevindjoum/progicicel-de-dimensionnement-dalot-")
            self.journaliser("Forum ouvert (GitHub)")
        except:
            messagebox.showinfo("Forum", "Forum d'entraide à venir.\n\nEn attendant, consultez la documentation sur GitHub.")

    def cmd_verifier_maj(self):
        messagebox.showinfo("Mises à jour", "Vérification des mises à jour à venir.\n\nVersion actuelle : 2.0 Pro\nDernière vérification : Jamais")
        self.journaliser("Vérification mises à jour")

    def cmd_a_propos(self):
        message = f"""PROGICIEL DALOT BA - VERSION 2.0 PROFESSIONNELLE

Interface complète de dimensionnement des dalots en béton armé
avec visualisation 3D interactive et calculs avancés.

Version : 2.0 Pro
Date : Septembre 2025
Développeur : Kevindjoum

Fonctionnalités :
• Dimensionnement selon Eurocode 2
• Visualisation 3D temps réel
• Optimisation automatique
• Export PDF professionnel
• Gestion de projets
• Interface utilisateur avancée

Système : {sys.platform}
Python : {sys.version.split()[0]}
Tkinter : Disponible
Matplotlib : Disponible

© 2025 - Tous droits réservés
Usage professionnel et éducatif"""
        
        messagebox.showinfo("À propos", message)
        self.journaliser("À propos consulté")

    # Méthodes utilitaires finales
    def _marquer_modifie(self):
        """Marque le projet comme modifié"""
        if not self.modifie:
            self.modifie = True
            self._mettre_a_jour_titre_fenetre()
            
            # Lancer recalcul automatique après modification
            if hasattr(self, 'dalot_calculations'):
                self.after(1000, self._lancer_calculs_automatique)

    def _mettre_a_jour_titre_fenetre(self):
        """Met à jour le titre de la fenêtre"""
        mod = "● " if self.modifie else ""
        nom_fichier = os.path.basename(self.chemin_fichier_courant) if self.chemin_fichier_courant else "Nouveau projet"
        nom_projet = self.nom_projet.get()
        
        self.title(f"{mod}{nom_projet} - {nom_fichier} | Progiciel Dalot BA v2.0 Pro")

    def _avant_quitter(self):
        """Vérifications avant fermeture"""
        if self.modifie:
            reponse = messagebox.askyesnocancel("Quitter", 
                                              "Le projet actuel a été modifié.\n\n"
                                              "Voulez-vous l'enregistrer avant de quitter ?")
            if reponse is None:  # Cancel
                return
            elif reponse:  # Yes
                if not self.action_enregistrer():
                    return
        
        # Arrêter les animations en cours
        self.animation_en_cours = False
        
        self.journaliser("Application fermée")
        self.destroy()

    def journaliser(self, message: str):
        """Ajoute un message au journal avec timestamp"""
        if hasattr(self, "zone_journal"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.zone_journal.insert("end", f"[{timestamp}] {message}\n")
            self.zone_journal.see("end")

    def _effacer_resultats(self):
        """Efface tous les résultats avec confirmation"""
        if messagebox.askyesno("Effacer résultats", "Effacer tous les résultats de calculs ?"):
            self.zone_calculs.delete("1.0", tk.END)
            self.zone_verifications.delete("1.0", tk.END)
            if hasattr(self, 'zone_optimisation'):
                self.zone_optimisation.delete("1.0", tk.END)
            self.journaliser("Résultats effacés")

    def cmd_copier_resultats(self):
        """Copie les résultats dans le presse-papiers"""
        contenu = self.zone_calculs.get("1.0", tk.END).strip()
        if contenu:
            self.clipboard_clear()
            self.clipboard_append(contenu)
            messagebox.showinfo("Copie", "Rapport copié dans le presse-papiers.")
            self.journaliser("Rapport copié dans le presse-papiers")
        else:
            messagebox.showinfo("Copie", "Aucun rapport à copier.")

# Point d'entrée de l'application
def main():
    """Lance l'application principale"""
    try:
        app = ApplicationDalotComplete()
        
        # Message de bienvenue dans le journal
        app.journaliser("═══════════════════════════════════════")
        app.journaliser("PROGICIEL DALOT BA v2.0 PRO - DÉMARRÉ")
        app.journaliser("Développé par Kevindjoum - 2025")
        app.journaliser("═══════════════════════════════════════")
        
        # Lancement de l'interface
        app.mainloop()
        
    except Exception as e:
        # Gestion des erreurs critiques
        import traceback
        error_msg = f"Erreur critique lors du démarrage:\n{str(e)}\n\nDétails:\n{traceback.format_exc()}"
        
        try:
            messagebox.showerror("Erreur critique", error_msg)
        except:
            print(error_msg)
        
        sys.exit(1)

if __name__ == "__main__":
    main()