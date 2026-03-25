import pandas as pd
import os
from pathlib import Path
from core.normalizer import limpiar_datos, detectar_y_parsear_fechas, normalizar_nombre_col, deduplicar_columnas
from core.scanner import cargar_archivo
from core.utils import EXPORT_ENCODING, EXPORT_SEP
import re

def run(adultos_dir, pediatria_dir, output_file, log):
    """
    Logic for Guardia HPN Process 1.
    Consolidates Adultos and Pediatría folders into a single normalized CSV.
    """
    log("🚀 [INICIO] Proceso Guardia HPN Process 1")
    log(f"   Adultos   : {adultos_dir}")
    log(f"   Pediatría : {pediatria_dir}")
    log(f"   Salida    : {output_file}")
    log("-" * 50)
    
    all_dfs = []
    
    # ── 1. PROCESAR ADULTOS ──────────────────────────────
    log("\n[1/2] Procesando carpeta Adultos...")
    adultos_files = [f for f in Path(adultos_dir).iterdir() if f.suffix.lower() in ['.csv', '.xls', '.xlsx']]
    if not adultos_files:
        log("   [WARN] No se encontraron archivos en la carpeta Adultos.")
    else:
        for f in adultos_files:
            df = _procesar_un_archivo(f, "Adultos", log)
            if df is not None:
                all_dfs.append(df)
            
    # ── 2. PROCESAR PEDIATRÍA ───────────────────────────
    log("\n[2/2] Procesando carpeta Pediatría...")
    pediatria_files = [f for f in Path(pediatria_dir).iterdir() if f.suffix.lower() in ['.csv', '.xls', '.xlsx']]
    if not pediatria_files:
        log("   [WARN] No se encontraron archivos en la carpeta Pediatría.")
    else:
        for f in pediatria_files:
            df = _procesar_un_archivo(f, "Pediatría", log)
            if df is not None:
                all_dfs.append(df)
                
    # ── 3. CONSOLIDAR Y GUARDAR ─────────────────────────
    if not all_dfs:
        log("\n❌ [ERROR] No se pudo procesar ningún archivo. Proceso abortado.")
        return
        
    log(f"\n[3/3] Consolidando {len(all_dfs)} dataframes...")
    try:
        df_final = pd.concat(all_dfs, ignore_index=True)
        
        # Últimos ajustes antes de guardar
        log("   Realizando ajustes finales para Supabase...")
        
        # Eliminar duplicados finales (por si el mismo id estaba en archivos distintos)
        if 'id' in df_final.columns:
            antes = len(df_final)
            df_final = df_final.drop_duplicates(subset=['id'], keep='first')
            despues = len(df_final)
            if antes != despues:
                log(f"   [INFO] Duplicados globales eliminados: {antes - despues}")

        # Filtrar solo las columnas solicitadas
        cols_finales = [
            'id', 'dni', 'edad_dias', 'obra_social', 'sexo', 
            'fecha_de_ingreso', 'fecha_de_atencion', 'fecha_de_egreso', 
            'diag_definitivo', 'cie10_codigo', 'tipo_de_ingreso', 
            'tipo_de_egreso', 'triage', 'servicio'
        ]
        
        # Filtramos solo las que existan para evitar errores
        existentes = [c for c in cols_finales if c in df_final.columns]
        df_final = df_final[existentes]
        log(f"   [INFO] Columnas procesadas y conservadas ({len(existentes)}):")
        log(f"          {'; '.join(existentes)}")
        
        output_path = Path(output_file)
        os.makedirs(output_path.parent, exist_ok=True)
        
        df_final.to_csv(output_path, index=False, encoding=EXPORT_ENCODING, sep=EXPORT_SEP)
        
        log(f"\n✅ [ÉXITO] Archivo consolidado guardado en: {output_path.name}")
        log(f"   Filas totales: {len(df_final):,}")
        log(f"   Columnas: {len(df_final.columns)}")
        
    except Exception as e:
        log(f"\n❌ [ERROR] Fallo al consolidar: {e}")

def _procesar_un_archivo(ruta, origen, log):
    try:
        log(f"   -> Procesando: {ruta.name}")
        df, enc, sep, tipo = cargar_archivo(str(ruta))
        
        # Normalizar columnas
        cols_norm = [normalizar_nombre_col(c) for c in df.columns]
        df.columns = deduplicar_columnas(cols_norm)
        
        # Limpiar datos y fechas
        df = limpiar_datos(df)
        df = detectar_y_parsear_fechas(df, log)
        
        # 1- Eliminar duplicados según columna 'id'
        if 'id' in df.columns:
            antes = len(df)
            df = df.drop_duplicates(subset=['id'], keep='first')
            despues = len(df)
            if antes != despues:
                log(f"      [INFO] Duplicados eliminados: {antes - despues}")
        else:
            log(f"      [WARN] No se encontró columna 'id' para deduplicar.")

        # 2- Consolidar con columna 'servicio'
        df['servicio'] = origen
        
        # 3- Limpiar documento -> dni (solo números)
        if 'documento' in df.columns:
            df['dni'] = df['documento'].apply(_extraer_dni)
        
        # 4- Limpiar edad -> edad_dias (robusto)
        if 'edad' in df.columns:
            df['edad_dias'] = df['edad'].apply(_parse_edad_a_dias).astype('Int64')
            
        # 5- Limpiar codigo_cie10 -> extraer solo el código (ej: K08.8)
        if 'codigo_cie10' in df.columns:
            df['cie10_codigo'] = df['codigo_cie10'].apply(_extraer_cie10)
        
        return df
    except Exception as e:
        log(f"      [ERROR] Fallo en {ruta.name}: {e}")
        return None

def _extraer_dni(val):
    if pd.isna(val) or val == 'nan': return None
    nums = re.findall(r'\d+', str(val))
    return "".join(nums) if nums else None

def _parse_edad_a_dias(val):
    if pd.isna(val) or val == 'nan': return None
    s = str(val).lower()
    total_dias = 0
    
    # Buscar años
    años = re.search(r'(\d+)\s*a[ñn]o', s)
    if años: total_dias += int(años.group(1)) * 365
    
    # Buscar meses
    meses = re.search(r'(\d+)\s*mes', s)
    if meses: total_dias += int(meses.group(1)) * 30
    
    # Buscar días
    dias = re.search(r'(\d+)\s*d[ií]a', s)
    if dias: total_dias += int(dias.group(1))
    
    return total_dias if total_dias > 0 or "0" in s else None

def _extraer_cie10(val):
    if pd.isna(val) or val == 'nan': return None
    s = str(val).strip()
    if not s: return None
    return s.split(' ')[0]

