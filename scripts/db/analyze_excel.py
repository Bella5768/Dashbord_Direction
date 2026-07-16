#!/usr/bin/env python
"""
Script pour analyser la structure des fichiers Excel de migration
Usage: python analyze_excel.py
"""

import os
import sys
import pandas as pd

EXCEL_DIR = os.path.dirname(os.path.abspath(__file__))

def analyze_excel_file(filename):
    """Analyse un fichier Excel"""
    filepath = os.path.join(EXCEL_DIR, filename)
    
    try:
        df = pd.read_excel(filepath)
        print(f"\n📄 {filename}")
        print(f"   Colonnes: {list(df.columns)}")
        print(f"   Lignes: {len(df)}")
        print(f"   Types: {df.dtypes.to_dict()}")
        
        # Afficher les premières lignes
        if len(df) > 0:
            print(f"   Première ligne:")
            for col in df.columns:
                print(f"      {col}: {df[col].iloc[0]}")
        
        return df.columns.tolist(), len(df)
        
    except Exception as e:
        print(f"❌ Erreur lecture {filename}: {e}")
        return [], 0

def main():
    print("=" * 60)
    print("📊 Analyse des fichiers Excel de migration")
    print("=" * 60)
    
    excel_files = [f for f in os.listdir(EXCEL_DIR) if f.endswith('.xlsx')]
    excel_files.sort()
    
    print(f"📁 {len(excel_files)} fichiers Excel trouvés")
    
    for filename in excel_files:
        analyze_excel_file(filename)
    
    print("\n" + "=" * 60)
    print("✅ Analyse terminée")
    print("=" * 60)

if __name__ == '__main__':
    main()
