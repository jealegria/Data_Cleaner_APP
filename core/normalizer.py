import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
from core.utils import *
from core.scanner import cargar_archivo

def limpiar_datos(df):
    for col in df.columns:
        serie = df[col].astype(str)
        serie = serie.str.strip()
        serie = serie.replace({'': np.nan, 'nan': np.nan, 'None': np.nan, 'NaN': np.nan})
        df[col] = serie
    return df


def es_columna_de_fecha(nombre_col, serie):
    keywords = ['fecha', 'ingreso', 'egreso', 'atencion', 'nacimiento', 'date', 'alta', 'baja']
    nombre = nombre_col.lower()
    tiene_keyword = any(k in nombre for k in keywords)
    if not tiene_keyword:
        return False

    no_nulos = serie.dropna()
    no_nulos = no_nulos[no_nulos != 'nan']
    if len(no_nulos) == 0:
        return False

    muestra = no_nulos.head(100)
    try:
        parseada = pd.to_datetime(muestra, format='mixed', dayfirst=True, errors='coerce')
        pct_ok = parseada.notna().mean()
        return pct_ok > 0.7
    except:
        return False


def detectar_y_parsear_fechas(df, log):
    cols_fecha = [col for col in df.columns if es_columna_de_fecha(col, df[col])]

    if not cols_fecha:
        log("    (no se detectaron columnas de fecha)")
        return df

    for col in cols_fecha:
        serie_orig = df[col].copy()
        serie_clean = serie_orig.replace({'nan': np.nan, '': np.nan})

        convertida = pd.to_datetime(serie_clean, format='mixed', dayfirst=True, errors='coerce')

        total_no_nulos = serie_clean.notna().sum()
        fallos = int(convertida.isna().sum() - serie_clean.isna().sum())
        fallos = max(fallos, 0)

        df[col] = convertida.dt.strftime('%d/%m/%Y %H:%M:%S').where(
            convertida.notna(), other=np.nan
        )

        log(f"    [OK] {col}")
        log(f"       Parseadas OK : {total_no_nulos - fallos:,} de {total_no_nulos:,}")

        if fallos > 0:
            mask_fallo = convertida.isna() & serie_clean.notna()
            ejemplos = serie_clean[mask_fallo].dropna().head(3).tolist()
            log(f"       [WARN] Fallos : {fallos} valores no parsearon -> NaN")
            if ejemplos:
                log(f"       Ejemplos   : {ejemplos}")

    return df


# ══════════════════════════════════════════════════════════════
#  PROCESAMIENTO PRINCIPAL
# ══════════════════════════════════════════════════════════════

def procesar_archivo(ruta, carpeta_salida, log, accion):
    nombre = Path(ruta).name
    log(f"\n{'═' * 65}")
    log(f"  PROCESANDO: {nombre} ({accion.upper()})")
    log(f"{'═' * 65}")

    # ── 1. CARGAR ─────────────────────────────────────────────
    log("\n  [1/4] Cargando archivo...")
    try:
        df, encoding, separator, tipo = cargar_archivo(ruta)
        log(f"    Tipo      : {tipo}")
        log(f"    Encoding  : {encoding}")
        log(f"    Separator : {separator}")
        log(f"    Forma     : {len(df):,} filas x {len(df.columns)} columnas")
    except Exception as e:
        log(f"    [ERROR] Error al cargar: {e}")
        return None

    # ── 2. NORMALIZAR COLUMNAS ────────────────────────────────
    log("\n  [2/4] Normalizando nombres de columnas...")
    cols_originales = list(df.columns)
    cols_norm = [normalizar_nombre_col(c) for c in cols_originales]
    cols_dedup = deduplicar_columnas(cols_norm)

    cambios = [(o, n) for o, n in zip(cols_originales, cols_dedup) if str(o) != n]
    df.columns = cols_dedup

    if cambios:
        for orig, nuevo in cambios:
            log(f"    {str(orig)!r:40} -> {nuevo}")
    else:
        log("    (ningun cambio necesario en nombres de columna)")

    duplicados = [n for n in cols_dedup if re.search(r'_\d+$', n)]
    if duplicados:
        log(f"    [WARN] Duplicados resueltos con sufijo: {duplicados}")

    # ── 3. LIMPIAR DATOS Y FECHAS ─────────────────────────────
    log("\n  [3/4] Limpiando datos (vacios -> NaN) y formateando fechas...")
    df = limpiar_datos(df)
    df = detectar_y_parsear_fechas(df, log)

    if accion == "analizar":
        log("\n  [INFO] Analisis finalizado. Revisa la pestaña 'Estructura y Tipos'.")
        return df

    # ── 4. GUARDAR ────────────────────────────────────────────
    log("\n  [4/4] Guardando CSV normalizado...")
    stem = Path(ruta).stem
    nombre_salida = f"{stem}_normalizado.csv"
    ruta_salida = Path(carpeta_salida) / nombre_salida

    df.to_csv(ruta_salida, index=False, encoding=EXPORT_ENCODING, sep=EXPORT_SEP)
    tamanio = os.path.getsize(ruta_salida) / 1024

    log(f"    Archivo   : {nombre_salida}")
    log(f"    Encoding  : {EXPORT_ENCODING}")
    log(f"    Separator : {EXPORT_SEP}")
    log(f"    Ruta      : {ruta_salida}")
    log(f"    Tamaño    : {tamanio:.1f} KB")
    log(f"    [OK] Normalizacion y guardado completados")

    return df


# ══════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════

