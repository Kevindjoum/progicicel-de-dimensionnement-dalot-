#!/usr/bin/env python3
"""
Exemple d'usage des nouvelles fonctionnalités du progiciel Dalot
Démontre l'utilisation des paramètres avancés et murs en aile
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Pour les tests en mode console sans affichage 3D
def demo_calculs_avances():
    """Démo des calculs avancés avec paramètres personnalisés"""
    
    # Import des classes de calcul
    import numpy as np
    
    # Simulation de la classe SimulationCalculs avec les améliorations
    class SimulationCalculs:
        @staticmethod
        def analyser_dalot(longueur, largeur, hauteur, epaisseur_mur, epaisseur_dalle, params=None):
            if params is None:
                params = {}
            
            # Paramètres utilisateur ou valeurs par défaut
            gamma_sol = params.get('sol_gamma_kN_m3', 20.0)
            phi_deg = params.get('sol_phi_deg', 30.0) 
            q_trafic = params.get('q_trafic_kN_m2', 5.0)
            fck = float(params.get('fck_MPa') or '30')
            gamma_G = params.get('gamma_G', 1.35)
            
            # Calculs des coefficients de poussée  
            phi_rad = np.radians(phi_deg)
            Ka = np.tan(np.pi/4 - phi_rad/2)**2  # Rankine
            K0 = 1 - np.sin(phi_rad)  # Jaky
            
            # Pression latérale avec surcharge
            sigma_h_base = Ka * gamma_sol * 1000 * hauteur + Ka * q_trafic * 1000
            force_poussee = 0.5 * Ka * gamma_sol * 1000 * hauteur**2 + Ka * q_trafic * 1000 * hauteur
            
            return {
                'validation_ok': True,
                'parametres': {
                    'Ka': Ka,
                    'K0': K0, 
                    'gamma_sol_kN_m3': gamma_sol,
                    'phi_deg': phi_deg,
                    'fck_MPa': fck,
                    'gamma_G': gamma_G
                },
                'poussee_terres': {
                    'sigma_h_base': sigma_h_base,
                    'force_poussee_par_metre': force_poussee
                }
            }
    
    print("🏗️ DEMO - Calculs Avancés Progiciel Dalot v2.0")
    print("=" * 50)
    
    # Cas 1: Paramètres par défaut (comportement v1.0)
    print("\n📋 CAS 1: Configuration Standard")
    print("-" * 30)
    
    result1 = SimulationCalculs.analyser_dalot(20, 3, 2, 0.25, 0.3)
    p1 = result1['parametres']
    print(f"Sol: γ={p1['gamma_sol_kN_m3']} kN/m³, φ={p1['phi_deg']}°")
    print(f"Béton: fck={p1['fck_MPa']} MPa")
    print(f"Coefficients: Ka={p1['Ka']:.3f}, K0={p1['K0']:.3f}")
    print(f"Poussée: {result1['poussee_terres']['force_poussee_par_metre']:.0f} N/m")
    
    # Cas 2: Sol argileux avec surcharges
    print("\n📋 CAS 2: Sol Argileux + Surcharges Trafic")
    print("-" * 40)
    
    params_argileux = {
        'sol_gamma_kN_m3': 18.0,    # Sol argileux plus léger
        'sol_phi_deg': 25.0,        # Angle plus faible
        'sol_c_kPa': 15.0,          # Cohésion notable
        'q_trafic_kN_m2': 12.0,     # Trafic lourd
        'fck_MPa': '35',            # Béton haute résistance
        'gamma_G': 1.35,
        'gamma_Q': 1.6              # Facteur majoré pour trafic lourd
    }
    
    result2 = SimulationCalculs.analyser_dalot(20, 3, 2, 0.25, 0.3, params_argileux)
    p2 = result2['parametres'] 
    print(f"Sol: γ={p2['gamma_sol_kN_m3']} kN/m³, φ={p2['phi_deg']}°")
    print(f"Béton: fck={p2['fck_MPa']} MPa")
    print(f"Coefficients: Ka={p2['Ka']:.3f}, K0={p2['K0']:.3f}")
    print(f"Poussée: {result2['poussee_terres']['force_poussee_par_metre']:.0f} N/m")
    print(f"Impact trafic: +{(result2['poussee_terres']['force_poussee_par_metre'] - result1['poussee_terres']['force_poussee_par_metre']):.0f} N/m")
    
    # Cas 3: Sol sableux avec Ka manuel (expertise)
    print("\n📋 CAS 3: Expertise Géotechnique (Ka manuel)")
    print("-" * 45)
    
    params_expertise = {
        'sol_gamma_kN_m3': 21.0,
        'sol_phi_deg': 35.0,        # Sol sableux dense
        'sol_Ka_manuel': '0.27',    # Ka réduit par expertise
        'fck_MPa': '25',
        'q_trafic_kN_m2': 8.0
    }
    
    result3 = SimulationCalculs.analyser_dalot(20, 3, 2, 0.25, 0.3, params_expertise)
    p3 = result3['parametres']
    print(f"Sol: γ={p3['gamma_sol_kN_m3']} kN/m³, φ={p3['phi_deg']}°")
    print(f"Ka manuel: {p3['Ka']:.3f} (vs Rankine: {np.tan(np.pi/4 - np.radians(p3['phi_deg'])/2)**2:.3f})")
    print(f"Poussée: {result3['poussee_terres']['force_poussee_par_metre']:.0f} N/m")
    
    print("\n📊 SYNTHÈSE COMPARATIVE")
    print("-" * 25)
    print(f"{'Cas':<20} {'Ka':<8} {'Poussée (N/m)':<12} {'Écart (%)'}")
    print("-" * 50)
    
    base_poussee = result1['poussee_terres']['force_poussee_par_metre']
    
    for i, (nom, result) in enumerate([
        ("Standard", result1),
        ("Sol argileux", result2), 
        ("Expertise", result3)
    ], 1):
        poussee = result['poussee_terres']['force_poussee_par_metre']
        ecart = ((poussee - base_poussee) / base_poussee) * 100
        ka = result['parametres']['Ka']
        print(f"{nom:<20} {ka:<8.3f} {poussee:<12.0f} {ecart:+6.1f}")
    
    return True

def demo_murs_en_aile():
    """Démo configuration murs en aile"""
    
    print("\n🏛️ DEMO - Configuration Murs en Aile")  
    print("=" * 40)
    
    # Configuration typique pour passage en remblai
    config_remblai = {
        'aile_gauche': {
            'active': True,
            'angle_deg': 135,        # Oblique pour guidage
            'longueur_m': 3.5,
            'epaisseur_m': 0.30,
            'fruit_vh': 0.1,         # Léger fruit pour stabilité
            'offset_m': 0.0
        },
        'aile_droite': {
            'active': True, 
            'angle_deg': 135,
            'longueur_m': 3.5,
            'epaisseur_m': 0.30,
            'fruit_vh': 0.1,
            'offset_m': 0.0
        }
    }
    
    print("📐 Configuration pour Passage en Remblai:")
    for cote, params in config_remblai.items():
        print(f"  {cote.capitalize()}:")
        print(f"    Angle: {params['angle_deg']}° (oblique)")
        print(f"    Longueur: {params['longueur_m']} m")
        print(f"    Fruit: {params['fruit_vh']} V/H")
        print()
    
    # Configuration pour tête de buse
    config_buse = {
        'aile_gauche': {
            'active': True,
            'angle_deg': 90,         # Perpendiculaire
            'longueur_m': 2.0,       # Plus courte
            'epaisseur_m': 0.25,
            'fruit_vh': 0.0,         # Pas de fruit
            'offset_m': 0.2          # Légèrement décalée
        },
        'aile_droite': {
            'active': True,
            'angle_deg': 90, 
            'longueur_m': 2.0,
            'epaisseur_m': 0.25,
            'fruit_vh': 0.0,
            'offset_m': 0.2
        }
    }
    
    print("📐 Configuration pour Tête de Buse:")
    for cote, params in config_buse.items():
        print(f"  {cote.capitalize()}:")
        print(f"    Angle: {params['angle_deg']}° (perpendiculaire)")
        print(f"    Longueur: {params['longueur_m']} m") 
        print(f"    Offset: {params['offset_m']} m")
        print()
    
    print("💡 Recommandations:")
    print("  • Angles 135° pour guidage hydraulique optimal")
    print("  • Longueur = 1.5-2.0 × hauteur dalot")  
    print("  • Fruit 0.1-0.2 V/H pour stabilité structurelle")
    print("  • Épaisseur ≥ 0.25m selon hauteur de remblai")
    
    return True

if __name__ == "__main__":
    print("🚀 PROGICIEL DALOT v2.0 - EXEMPLES D'USAGE")
    print("=" * 55)
    
    try:
        # Demo des calculs avancés
        demo_calculs_avances()
        
        # Demo des murs en aile  
        demo_murs_en_aile()
        
        print("\n✅ DÉMOS TERMINÉES AVEC SUCCÈS")
        print("\n📖 Consultez NOUVELLES_FONCTIONNALITES.md pour le guide complet")
        print("🖥️  Lancez 'python \"code final.py\"' pour l'interface graphique")
        
    except Exception as e:
        print(f"\n❌ Erreur lors des démos: {e}")
        import traceback
        traceback.print_exc()