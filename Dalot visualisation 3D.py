import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, PolyCollection
import numpy as np
from matplotlib.patches import Polygon as MplPolygon
import base64
from io import BytesIO
from PIL import Image, ImageTk

# --- IMPORTER LES NOUVEAUX MODULES ---
import données_dentrée as dde
import normes_et_formules as dvc
import BOUTON_CALCULER as doc
# --- FIN DE L'IMPORT --- 

class DalotViewer3D:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Visualiseur 3D de Dalot")
        # self.root.geometry("1600x950") # Supprimé pour permettre le redimensionnement libre
        
        self.longueur = dde.DEFAULT_LONGUEUR
        self.largeur = dde.DEFAULT_LARGEUR
        self.hauteur = dde.DEFAULT_HAUTEUR
        self.epaisseur_mur = dde.DEFAULT_EPAISSEUR_MUR
        self.epaisseur_dalle = dde.DEFAULT_EPAISSEUR_DALLE
        
        self.zoom_factor = 1.1  
        self.selected_face = None 
        self.original_face_colors = {} 
        self.face_properties = {} 
        self.dalot_calculations = {} 

        self.tk_images = {} 

        self.setup_ui()
        self.create_plot()
        self.draw_dalot()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        control_frame = ttk.LabelFrame(main_frame, text="Paramètres du Dalot", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(control_frame, text="Longueur (m):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.longueur_var = tk.DoubleVar(value=self.longueur)
        ttk.Entry(control_frame, textvariable=self.longueur_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(control_frame, text="Largeur (m):").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.largeur_var = tk.DoubleVar(value=self.largeur)
        ttk.Entry(control_frame, textvariable=self.largeur_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(control_frame, text="Hauteur (m):").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.hauteur_var = tk.DoubleVar(value=self.hauteur)
        ttk.Entry(control_frame, textvariable=self.hauteur_var, width=10).grid(row=1, column=1, padx=5)
        
        ttk.Label(control_frame, text="Épaisseur murs (m):").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.epaisseur_mur_var = tk.DoubleVar(value=self.epaisseur_mur)
        ttk.Entry(control_frame, textvariable=self.epaisseur_mur_var, width=10).grid(row=1, column=3, padx=5)
        
        ttk.Label(control_frame, text="Épaisseur dalle (m):").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.epaisseur_dalle_var = tk.DoubleVar(value=self.epaisseur_dalle)
        ttk.Entry(control_frame, textvariable=self.epaisseur_dalle_var, width=10).grid(row=2, column=1, padx=5)
        
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=3, column=0, columnspan=4, pady=10)
        
        ttk.Button(button_frame, text="Mettre à jour", command=self.update_dalot).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Vue de face", command=self.vue_face).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Vue de côté", command=self.vue_cote).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Vue dessus", command=self.vue_dessus).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Vue isométrique", command=self.vue_iso).pack(side=tk.LEFT, padx=5)

        # --- NOUVEAU : Utilisation de PanedWindow pour le redimensionnement ---
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Panneau gauche: Résultats des calculs et diagrammes
        left_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(left_panel, weight=1) # Poids pour le redimensionnement

        notebook = ttk.Notebook(left_panel)
        notebook.pack(fill=tk.BOTH, expand=True)

        calc_tab = ttk.Frame(notebook)
        notebook.add(calc_tab, text="Rapport de Calculs")

        calculation_frame = ttk.LabelFrame(calc_tab, text="Détails des Calculs", padding=10)
        calculation_frame.pack(fill=tk.BOTH, expand=True)
        
        self.calculation_output = tk.Text(calculation_frame, wrap=tk.WORD, height=15, width=60)
        self.calculation_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        calc_scroll = ttk.Scrollbar(calculation_frame, command=self.calculation_output.yview)
        calc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.calculation_output.config(yscrollcommand=calc_scroll.set)

        diagrams_tab = ttk.Frame(notebook)
        notebook.add(diagrams_tab, text="Diagrammes et Plans")

        schema_2d_frame = ttk.LabelFrame(diagrams_tab, text="Schéma 2D du Dalot", padding=5)
        schema_2d_frame.pack(fill=tk.X, pady=(5, 0))
        self.schema_2d_label = ttk.Label(schema_2d_frame)
        self.schema_2d_label.pack(pady=2)

        dalle_diagrams_frame = ttk.LabelFrame(diagrams_tab, text="Diagrammes Dalle de Couverture", padding=5)
        dalle_diagrams_frame.pack(fill=tk.X, pady=(5, 0))
        self.moment_diagram_dalle_label = ttk.Label(dalle_diagrams_frame)
        self.moment_diagram_dalle_label.pack(side=tk.LEFT, padx=5, pady=2)
        self.tranchant_diagram_dalle_label = ttk.Label(dalle_diagrams_frame)
        self.tranchant_diagram_dalle_label.pack(side=tk.LEFT, padx=5, pady=2)

        mur_diagrams_frame = ttk.LabelFrame(diagrams_tab, text="Diagrammes Murs Latéraux", padding=5)
        mur_diagrams_frame.pack(fill=tk.X, pady=(5, 0))
        self.moment_diagram_mur_label = ttk.Label(mur_diagrams_frame)
        self.moment_diagram_mur_label.pack(side=tk.LEFT, padx=5, pady=2)
        self.tranchant_diagram_mur_label = ttk.Label(mur_diagrams_frame)
        self.tranchant_diagram_mur_label.pack(side=tk.LEFT, padx=5, pady=2)
        self.normal_diagram_mur_label = ttk.Label(mur_diagrams_frame)
        self.normal_diagram_mur_label.pack(side=tk.LEFT, padx=5, pady=2)

        rebar_plan_frame = ttk.LabelFrame(diagrams_tab, text="Plan de Ferraillage Simplifié", padding=5)
        rebar_plan_frame.pack(fill=tk.X, pady=(5, 0))
        self.rebar_plan_label = ttk.Label(rebar_plan_frame)
        self.rebar_plan_label.pack(pady=2)
        
        # Panneau droit: Visualisation 3D
        right_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(right_panel, weight=2) # Poids pour le redimensionnement (plus grand que le gauche)
        # --- FIN NOUVEAU ---

        plot_frame = ttk.LabelFrame(right_panel, text="Visualisation 3D du Dalot", padding=10)
        plot_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- MODIFICATION ICI : Suppression de figsize ---
        self.fig = plt.figure() 
        # --- FIN MODIFICATION ---
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        
        self.canvas.mpl_connect("scroll_event", self.on_scroll_zoom)
        self.canvas.mpl_connect("pick_event", self.on_pick_face)
        
    def on_scroll_zoom(self, event):
        if event.inaxes == self.ax: 
            current_xlim = self.ax.get_xlim3d()
            current_ylim = self.ax.get_ylim3d()
            current_zlim = self.ax.get_zlim3d()

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

            self.ax.set_xlim3d(new_xlim)
            self.ax.set_ylim3d(new_ylim)
            self.ax.set_zlim3d(new_zlim)
            self.canvas.draw_idle()
            
    def on_pick_face(self, event):
        if isinstance(event.artist, PolyCollection):
            
            if self.selected_face:
                self.selected_face.set_facecolor(self.original_face_colors[self.selected_face])
                self.selected_face = None

            picked_collection = event.artist
            
            if picked_collection in self.face_properties:
                self.selected_face = picked_collection
                
                if self.selected_face not in self.original_face_colors:
                    self.original_face_colors[self.selected_face] = self.selected_face.get_facecolor()

                self.selected_face.set_facecolor('red') 
                self.canvas.draw_idle()
                
                face_name = self.face_properties[picked_collection].get('name', 'Face Inconnue')
                face_info = self.face_properties[picked_collection].get('info', 'Pas d\'info spécifique.')
                
                output_str = f"--- Informations sur la face sélectionnée ---\n"
                output_str += f"Nom: {face_name}\n"
                output_str += f"Info: {face_info}\n"
                output_str += f"--------------------------------------------------\n"
                
                if "dalle de couverture" in face_name.lower() and 'ferraillage_dalle_couverture' in self.dalot_calculations:
                    ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
                    armatures = self.dalot_calculations['armatures_dalle_choisies']
                    output_str += f"\n--- Calculs pour la Dalle de Couverture ---\n"
                    if 'moment_ELU' in ferraillage:
                        output_str += f"Moment fléchissant ELU: {ferraillage['moment_ELU']:.2f} Nm/m\n"
                        output_str += f"Section d'acier théorique (As): {ferraillage['As_theorique'] * 1e4:.2f} cm²/m\n"
                        output_str += f"Armatures choisies: Φ{armatures['diametre']} e={armatures['espacement']}cm (As fourni: {armatures['As_fourni'] * 1e4:.2f} cm²/m)\n"
                    else:
                        output_str += f"Résultat: {ferraillage['resultat']}\n"
                    output_str += f"Info: {ferraillage['info']}\n"
                    output_str += f"--------------------------------------------------\n"
                elif "mur" in face_name.lower() and 'armatures_mur_choisies' in self.dalot_calculations:
                    armatures = self.dalot_calculations['armatures_mur_choisies']
                    effort_normal = self.dalot_calculations.get('effort_normal_mur', {}).get('valeur', 'N/A')
                    sol_mur = doc.calculer_sollicitations_mur_poussee(
                        self.hauteur_var.get(), self.epaisseur_dalle_var.get(), 
                        self.dalot_calculations.get('poussee_terres', {}).get('force_poussee_par_metre', 0)
                    )
                    
                    output_str += f"\n--- Calculs pour le Mur ---\n"
                    output_str += f"Effort normal (ELU): {effort_normal:.2f} N/m\n"
                    output_str += f"Moment max (Poussée): {sol_mur.get('moment_max', 'N/A'):.2f} Nm/m\n"
                    output_str += f"Tranchant max (Poussée): {sol_mur.get('tranchant_max', 'N/A'):.2f} N/m\n"
                    output_str += f"Armatures choisies (exemple): Φ{armatures['diametre']} e={armatures['espacement']}cm (As fourni: {armatures['As_fourni'] * 1e4:.2f} cm²/m)\n"
                    output_str += f"--------------------------------------------------\n"

                self.display_calculation_results(output_str)
            else:
                print("Clic sur un objet non enregistré ou non pickable.")


    def create_plot(self):
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_zlabel('Z (m)')
        self.ax.set_title('Dalot 3D - Structure de drainage')
        
        self.ax.set_facecolor('#EEEEEE') 
        
    def create_box_vertices(self, x_min, x_max, y_min, y_max, z_min, z_max):
        vertices = [
            [x_min, y_min, z_min], [x_max, y_min, z_min], [x_max, y_max, z_min], [x_min, y_max, z_min],  
            [x_min, y_min, z_max], [x_max, y_min, z_max], [x_max, y_max, z_max], [x_min, y_max, z_max]    
        ]
        return np.array(vertices)
    
    def create_box_faces(self, vertices):
        faces_indices = [
            [0, 1, 2, 3],  
            [4, 5, 6, 7],  
            [0, 1, 5, 4],  
            [2, 3, 7, 6],  
            [1, 2, 6, 5],  
            [3, 0, 4, 7]    
        ]
        
        return [[vertices[i] for i in face] for face in faces_indices]
    
    def draw_box(self, x_min, x_max, y_min, y_max, z_min, z_max, color='lightgray', alpha=0.8, part_name="Boîte"):
        vertices = self.create_box_vertices(x_min, x_max, y_min, y_max, z_min, z_max)
        faces_coords = self.create_box_faces(vertices)

        collections_list = []
        face_names = ["Face inférieure", "Face supérieure", "Face avant", "Face arrière", "Face droite", "Face gauche"]

        for i, face in enumerate(faces_coords):
            collection = Poly3DCollection([face], alpha=alpha, facecolor=color, edgecolor='black', linewidth=0.5, picker=True)
            self.ax.add_collection3d(collection)
            collections_list.append(collection)
            
            self.original_face_colors[collection] = collection.get_facecolor() 
            self.face_properties[collection] = {
                'name': f"{part_name} - {face_names[i]}",
                'info': f"Composant du dalot: {part_name}"
            }
        return collections_list
    
    def draw_dalot(self):
        self.ax.clear()
        self.ax.set_facecolor('#EEEEEE') 

        if self.selected_face:
            self.selected_face.set_facecolor(self.original_face_colors[self.selected_face])
            self.selected_face = None
        self.original_face_colors = {}
        self.face_properties = {} 
        self.all_dalot_parts = []

        try:
            L = self.longueur_var.get()
            l = self.largeur_var.get()
            h = self.hauteur_var.get()
            e_mur = self.epaisseur_mur_var.get()
            e_dalle = self.epaisseur_dalle_var.get()
        except tk.TclError:
            messagebox.showerror("Erreur de saisie", "Veuillez entrer des valeurs numériques valides pour les dimensions.")
            return
        
        try:
            dvc.valider_dimensions_dalot(L, l, h, e_mur, e_dalle)
        except dvc.DalotValidationError as e:
            messagebox.showerror("Erreur de Validation", str(e))
            return
        
        self.all_dalot_parts.extend(self.draw_box(0, L, 0, l, 0, e_dalle, color='lightgray', alpha=0.8, part_name="Dalle de fond"))
        self.all_dalot_parts.extend(self.draw_box(0, L, 0, l, h-e_dalle, h, color='lightgray', alpha=0.8, part_name="Dalle de couverture"))
        self.all_dalot_parts.extend(self.draw_box(0, L, 0, e_mur, e_dalle, h-e_dalle, color='lightblue', alpha=0.8, part_name="Mur gauche"))
        self.all_dalot_parts.extend(self.draw_box(0, L, l-e_mur, l, e_dalle, h-e_dalle, color='lightblue', alpha=0.8, part_name="Mur droit"))
        
        ouv_y = np.array([e_mur, l-e_mur, l-e_mur, e_mur, e_mur])
        ouv_z = np.array([e_dalle, e_dalle, h-e_dalle, h-e_dalle, e_dalle])
        ouv_x = np.zeros_like(ouv_y)
        self.ax.plot(ouv_x, ouv_y, ouv_z, 'r-', linewidth=3, label='Ouverture entrée')
        
        ouv_x_sortie = np.full_like(ouv_y, L)
        self.ax.plot(ouv_x_sortie, ouv_y, ouv_z, 'r-', linewidth=3, label='Ouverture sortie')
        
        x_eau = np.linspace(0, L, 20)
        y_eau = np.full_like(x_eau, l/2)
        z_eau = np.full_like(x_eau, e_dalle + 0.1)
        self.ax.plot(x_eau, y_eau, z_eau, 'b-', linewidth=2, alpha=0.7, label='Écoulement')
        
        self.ax.set_xlabel('Longueur (m)')
        self.ax.set_ylabel('Largeur (m)')
        self.ax.set_zlabel('Hauteur (m)')
        self.ax.set_title(f'Dalot 3D - L:{L}m × l:{l}m × H:{h}m')
        
        self.ax.set_xlim(0, L * 1.2)
        self.ax.set_ylim(0, l * 1.2)
        self.ax.set_zlim(0, h * 1.2)
        
        self.ax.set_box_aspect([L, l, h])
        
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        self.ax.text(L/2, -0.1*l, -0.1*h, f'L = {L} m', fontsize=10, ha='center', color='gray')
        self.ax.text(-0.1*L, l/2, -0.1*h, f'l = {l} m', fontsize=10, ha='center', color='gray')
        self.ax.text(-0.1*L, -0.1*l, h/2, f'H = {h} m', fontsize=10, ha='center', color='gray')
        
        self.canvas.draw()
        
        self.run_calculations()

    def run_calculations(self):
        L = self.longueur_var.get()
        l = self.largeur_var.get()
        h = self.hauteur_var.get()
        e_mur = self.epaisseur_mur_var.get()
        e_dalle = self.epaisseur_dalle_var.get()
        
        self.dalot_calculations = doc.analyser_dalot(L, l, h, e_mur, e_dalle)
        
        output_str = "--- Rapport de Calculs du Dalot ---\n\n"
        
        self.tk_images.clear() 

        if 'erreur' in self.dalot_calculations:
            output_str += f"Erreur lors des calculs: {self.dalot_calculations['erreur']}\n"
            self.display_diagram_image(None, self.schema_2d_label, 'schema_2d')
            self.display_diagram_image(None, self.moment_diagram_dalle_label, 'moment_dalle')
            self.display_diagram_image(None, self.tranchant_diagram_dalle_label, 'tranchant_dalle')
            self.display_diagram_image(None, self.moment_diagram_mur_label, 'moment_mur')
            self.display_diagram_image(None, self.tranchant_diagram_mur_label, 'tranchant_mur')
            self.display_diagram_image(None, self.normal_diagram_mur_label, 'normal_mur')
            self.display_diagram_image(None, self.rebar_plan_label, 'rebar_plan')
        else:
            output_str += f"Validation des dimensions: {'OK' if self.dalot_calculations.get('validation_ok', False) else 'ÉCHEC'}\n\n"

            output_str += "Volumes et Masses :\n"
            for key, val in self.dalot_calculations['volumes_masses'].items():
                if key != 'total':
                    output_str += f"- {val['info']}: Vol={val['volume']:.3f} m³, Masse={val['masse']:.2f} kg\n"
            output_str += f"- {self.dalot_calculations['volumes_masses']['total']['info']}: Vol={self.dalot_calculations['volumes_masses']['total']['volume']:.3f} m³, Masse={self.dalot_calculations['volumes_masses']['total']['masse']:.2f} kg\n\n"

            output_str += "Charges sur Dalle de Couverture :\n"
            charges = self.dalot_calculations['charges_dalle_couverture']
            output_str += f"- Poids propre dalle: {charges['q_pp_dalle']:.2f} N/m²\n"
            output_str += f"- Charge exploitation: {charges['q_exploitation']:.2f} N/m²\n"
            output_str += f"- Charge permanente supp.: {charges['q_permanente_supp']:.2f} N/m²\n"
            output_str += f"- Charge service (ELS): {charges['q_service']:.2f} N/m²\n"
            output_str += f"- Charge ELU: {charges['q_ELU']:.2f} N/m²\n\n"

            output_str += "Poussée des Terres (par mètre linéaire de mur) :\n"
            poussee = self.dalot_calculations['poussee_terres']
            output_str += f"- Contrainte horiz. à la base: {poussee['sigma_h_base'] / 1000:.2f} kPa\n"
            output_str += f"- Force poussée: {poussee['force_poussee_par_metre']:.2f} N/m\n"
            output_str += f"- Pt application (depuis base): {poussee['point_application_hauteur']:.2f} m\n\n"

            output_str += "Effort Normal Mur :\n"
            normal_mur = self.dalot_calculations['effort_normal_mur']
            output_str += f"- {normal_mur['info']}: {normal_mur['valeur']:.2f} N/m\n\n"

            output_str += "Ferraillage Dalle de Couverture (Simplifié) :\n"
            ferraillage = self.dalot_calculations['ferraillage_dalle_couverture']
            armatures_choisies = self.dalot_calculations['armatures_dalle_choisies']
            if 'moment_ELU' in ferraillage:
                output_str += f"- Moment fléchissant ELU: {ferraillage['moment_ELU']:.2f} Nm/m\n"
                output_str += f"- Section d'acier théorique (As): {ferraillage['As_theorique'] * 1e4:.2f} cm²/m\n"
                output_str += f"- Armatures choisies: Φ{armatures_choisies['diametre']} e={armatures_choisies['espacement']}cm (As fourni: {armatures_choisies['As_fourni'] * 1e4:.2f} cm²/m)\n"
            else:
                output_str += f"- Résultat: {ferraillage['resultat']}\n"
            output_str += f"Info: {ferraillage['info']}\n\n"
            
            output_str += "Ferraillage Murs (Exemple Simplifié) :\n"
            armatures_mur = self.dalot_calculations['armatures_mur_choisies']
            output_str += f"- Armatures choisies: Φ{armatures_mur['diametre']} e={armatures_mur['espacement']}cm (As fourni: {armatures_mur['As_fourni'] * 1e4:.2f} cm²/m)\n\n"

            output_str += "NOTE: Ces calculs sont simplifiés et ne remplacent pas une étude d'ingénierie détaillée."
            
            self.display_diagram_image(self.dalot_calculations.get('schema_2d_dalot_b64'), self.schema_2d_label, 'schema_2d')
            self.display_diagram_image(self.dalot_calculations.get('diagramme_moment_dalle_b64'), self.moment_diagram_dalle_label, 'moment_dalle')
            self.display_diagram_image(self.dalot_calculations.get('diagramme_tranchant_dalle_b64'), self.tranchant_diagram_dalle_label, 'tranchant_dalle')
            self.display_diagram_image(self.dalot_calculations.get('diagramme_moment_mur_b64'), self.moment_diagram_mur_label, 'moment_mur')
            self.display_diagram_image(self.dalot_calculations.get('diagramme_tranchant_mur_b64'), self.tranchant_diagram_mur_label, 'tranchant_mur')
            self.display_diagram_image(self.dalot_calculations.get('diagramme_normal_mur_b64'), self.normal_diagram_mur_label, 'normal_mur')
            self.display_diagram_image(self.dalot_calculations.get('plan_ferraillage_b64'), self.rebar_plan_label, 'rebar_plan')

        self.display_calculation_results(output_str)

    def display_calculation_results(self, text):
        self.calculation_output.delete(1.0, tk.END)
        self.calculation_output.insert(tk.END, text)
        self.calculation_output.see(tk.END) 

    def display_diagram_image(self, base64_image_data, label_widget, image_key):
        if base64_image_data:
            try:
                img_data = base64.b64decode(base64_image_data)
                img = Image.open(BytesIO(img_data))
                max_width = 400 
                max_height = 300 
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                
                label_widget.config(image='')
                self.tk_images[image_key] = photo 
                label_widget.config(image=photo)
                
            except Exception as e:
                print(f"Erreur lors de l'affichage de l'image (clé: {image_key}) : {e}")
                label_widget.config(image='')
                if image_key in self.tk_images:
                    del self.tk_images[image_key]
        else:
            label_widget.config(image='')
            if image_key in self.tk_images:
                del self.tk_images[image_key]

    def update_dalot(self):
        self.draw_dalot() 
    
    def vue_face(self):
        self.ax.view_init(elev=0, azim=0)
        self.canvas.draw()
    
    def vue_cote(self):
        self.ax.view_init(elev=0, azim=90)
        self.canvas.draw()
    
    def vue_dessus(self):
        self.ax.view_init(elev=90, azim=0)
        self.canvas.draw()
    
    def vue_iso(self):
        self.ax.view_init(elev=20, azim=45)
        self.canvas.draw()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = DalotViewer3D()
    app.run()
