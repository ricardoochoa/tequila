"""
importador_exiobase.py
======================
Importa EXIOBASE 3 (formato pxp/Monetario) al entorno de Brightway2 para
el proyecto Tequila LCA Studio.

VERSIÓN COMPATIBLE CON:
  - bw2io    0.8.12  (Exiobase3MonetaryImporter eliminado en ≥0.8.x)
  - bw2data  3.6.6
  - brightway2 2.4.7
  - pymrio   0.6.x
  - pandas   3.0.x

ESTRATEGIA:
  Como bw2io ≥ 0.8.x ya no incluye Exiobase3MonetaryImporter, usamos pymrio
  para parsear los archivos y calcular los multiplicadores M = S·L.

  Luego pre-agregamos el impacto de GWP100 por sector usando factores IPCC AR5
  directamente embebidos en este script (mapeados a nombres exactos de estresores
  de EXIOBASE 3.10.x). Escribimos un único intercambio sintético de biósfera
  "Carbon dioxide, fossil" por sector, con amount = kg CO2-eq / M.EUR output.

  Resultado: Brightway LCA({sector: demanda}, method=GWP100).score devuelve
  el impacto correcto en kg CO2-eq directamente desde la matriz.

  La base de datos se registra bajo "EXIOBASE_3" — nombre exacto que espera:
    bw_calculator.py → `"EXIOBASE_3" in bw.databases`

Uso:
    cd c:\\Users\\Ferna\\Desktop\\x\\tequila
    python importador_exiobase.py
"""

import os
import sys
import zipfile
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("exio_importer")

# ---------------------------------------------------------------------------
# Configuración — DB_NAME debe coincidir EXACTAMENTE con bw_calculator.py
# ---------------------------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_NAME = "Tequila_LCA_Mexico"
DB_NAME      = "EXIOBASE_3"          # ← exact match for `"EXIOBASE_3" in bw.databases`
ZIP_PATH     = os.path.join(BASE_DIR, "scratch", "IOT_2024_pxp.zip")
EXTRACT_DIR  = os.path.join(BASE_DIR, "scratch", "exiobase_2024_pxp")

# ---------------------------------------------------------------------------
# GWP100 characterization factors (IPCC AR5, 100-year horizon)
# Mapped to exact EXIOBASE 3.10.x stressor names from air_emissions/F.txt.
# Units: all EXIOBASE air stressors are in kg/M.EUR of output.
# Source: IPCC AR5 WG1 Table 8.SM.16 + EXIOBASE documentation.
# ---------------------------------------------------------------------------
GWP100_FACTORS = {
    # CO2
    "CO2 - combustion - air":              1.0,
    "CO2_bio - combustion - air":          0.0,   # biogenic — excluded per convention
    "CO2 - agriculture - peat decay - air":1.0,
    "CO2 - waste - fossil - air":          1.0,
    "CO2 - waste - biogenic - air":        0.0,   # biogenic — excluded
    # CH4
    "CH4 - combustion - air":             28.0,
    "CH4_bio - combustion - air":         28.0,
    "CH4 - agriculture - air":            28.0,
    "CH4 - waste - air":                  28.0,
    # N2O
    "N2O - combustion - air":            265.0,
    "N2O_bio - combustion - air":        265.0,
    "N2O - agriculture - air":           265.0,
    # Fluorinated gases (SF6, HFCs, PFCs)
    "SF6 - air":                        23500.0,
    "HFC - air":                         1430.0,  # HFC-134a representative
    "PFC - air":                         7390.0,  # PFC-14 representative
}

# AWARE water scarcity characterization factors for factor_inputs water stressors.
# Units: m3 world-eq / m3 withdrawn.  Using global average = 1.0 as safe default
# (proper regionalized values require AWARE region mapping beyond scope here).
AWARE_FACTOR_DEFAULT = 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_pymrio():
    """Instala pymrio si no está disponible."""
    try:
        import pymrio  # noqa
    except ModuleNotFoundError:
        log.info("pymrio no encontrado. Instalando con pip...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymrio", "-q"])
        log.info("pymrio instalado correctamente.")


def _setup_brightway():
    """Inicializa el proyecto Brightway2 y biosphere3."""
    import brightway2 as bw

    bw.projects.set_current(PROJECT_NAME)
    log.info(f"Proyecto Brightway activo: '{bw.projects.current}'")

    if "biosphere3" not in bw.databases:
        log.info("Inicializando biosphere3 (puede tardar unos minutos)...")
        bw.bw2setup()
        log.info("biosphere3 inicializada.")
    else:
        log.info("biosphere3 ya presente.")

    return bw


def _extract_zip():
    """Descomprime el ZIP si la carpeta destino no existe o está vacía."""
    if not os.path.exists(ZIP_PATH):
        log.error(f"No se encontró el archivo ZIP: {ZIP_PATH}")
        log.error("Descarga IOT_2024_pxp.zip de https://zenodo.org/record/5589597")
        sys.exit(1)

    key_file = os.path.join(EXTRACT_DIR, "Z.txt")
    if os.path.exists(key_file):
        log.info(f"Datos ya extraídos en '{EXTRACT_DIR}' — se omite extracción.")
        return

    log.info(f"Descomprimiendo '{os.path.basename(ZIP_PATH)}' en '{EXTRACT_DIR}'...")
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(EXTRACT_DIR)
    log.info("Extracción completada.")


def _find_co2_fossil_key(bw):
    """
    Localiza la clave de 'Carbon dioxide, fossil' en biosphere3.
    Devuelve (database, code) para usar como input en intercambios.
    """
    bio_db = bw.Database("biosphere3")
    proxy_code = "exio_co2_fossil_proxy"

    # --- THE FIX: Check if proxy already exists in SQLite from a previous run ---
    try:
        return bio_db.get(code=proxy_code).key
    except:
        pass
    # ----------------------------------------------------------------------------

    # Búsqueda por nombre exacto
    candidates = [
        "Carbon dioxide, fossil",
        "Carbon dioxide",
        "CO2",
    ]
    for name in candidates:
        results = bio_db.search(name, limit=5)
        for r in results:
            n = r.get("name", "").lower()
            if "carbon dioxide" in n and "fossil" in n:
                return r.key
            if n == "carbon dioxide":
                return r.key

    # Crear flujo proxy si no se encontró
    log.warning("'Carbon dioxide, fossil' no encontrado en biosphere3. Creando flujo proxy.")
    proxy = bio_db.new_activity(
        code=proxy_code,
        name="Carbon dioxide, fossil",
        unit="kg",
        type="emission",
        categories=("air", "unspecified"),
    )
    proxy.save()
    log.info(f"Flujo proxy creado: ('biosphere3', '{proxy_code}')")
    return ("biosphere3", proxy_code)


def _find_water_key(bw):
    """
    Localiza un flujo de consumo de agua en biosphere3 para AWARE.
    """
    bio_db = bw.Database("biosphere3")
    proxy_code = "exio_water_proxy"

    # --- THE FIX: Check if proxy already exists in SQLite from a previous run ---
    try:
        return bio_db.get(code=proxy_code).key
    except:
        pass
    # ----------------------------------------------------------------------------

    results = bio_db.search("Water", limit=10)
    for r in results:
        n = r.get("name", "").lower()
        cat = str(r.get("categories", "")).lower()
        if "water" in n and ("ground" in n or "surface" in n or "fresh" in n):
            return r.key

    proxy = bio_db.new_activity(
        code=proxy_code,
        name="Water, unspecified natural origin",
        unit="m3",
        type="natural resource",
        categories=("natural resource", "in water"),
    )
    proxy.save()
    return ("biosphere3", proxy_code)

def _compute_gwp_per_sector(io_system):
    """
    Calcula el GWP total (kg CO2-eq / M.EUR de output) para cada sector
    usando los multiplicadores M de la extensión air_emissions.

    Nota sobre pandas 3.x: DataFrame.mul(Index, axis=0) hace alineación por
    etiquetas (label-based), lo que falla cuando el Index resultado de .map()
    tiene índice entero vs. el índice de cadenas de M. Se usa numpy array
    para forzar multiplicación posicional.

    Devuelve una Series: {(region, sector): gwp_value_kg_co2eq}
    """
    import numpy as np
    import pandas as pd

    log.info("Calculando GWP100 pre-agregado por sector...")

    ae = io_system.air_emissions
    if ae.M is None:
        raise RuntimeError("La matriz M de air_emissions no fue calculada. "
                           "Asegúrate de llamar io.calc_all() antes.")

    M = ae.M   # DataFrame: index=stressors, columns=MultiIndex(region, sector)

    # Construir array numpy posicional (evita alineación por etiquetas de pandas 3.x)
    gwp_array = np.array([GWP100_FACTORS.get(str(s), 0.0) for s in M.index],
                         dtype=float)

    matched = int((gwp_array > 0).sum())
    log.info(f"  Stressors con factor GWP > 0: {matched} de {len(gwp_array)} "
             f"({[str(s) for s, v in zip(M.index, gwp_array) if v > 0]})")

    if matched == 0:
        log.error("¡NINGÚN stressor coincidió con GWP100_FACTORS!")
        log.error(f"Primeros 5 stressors en M.index: {list(M.index[:5])}")
        raise RuntimeError("GWP mapping falló — revisa los nombres de stressors.")

    # Dot product posicional: gwp_array @ M  →  Series(region, sector)
    # CRÍTICO: M contiene NaN (celdas vacías en tablas MRIO = sin emisión = 0).
    # En numpy: 0 * NaN = NaN, lo que propagaría NaN a todos los sectores.
    # nan_to_num convierte NaN→0 antes del producto punto.
    M_clean = np.nan_to_num(M.values, nan=0.0, posinf=0.0, neginf=0.0)
    gwp_values = gwp_array @ M_clean          # numpy dot: shape (n_sectors,)
    gwp_series = pd.Series(gwp_values, index=M.columns)

    log.info(f"GWP calculado para {len(gwp_series)} sectores.")
    log.info(f"  Rango: [{gwp_series.min():.4f}, {gwp_series.max():.4f}] kg CO2-eq/M.EUR")

    return gwp_series


def _compute_water_per_sector(io_system):
    """
    EXIOBASE 3.10.2 pxp no tiene extensión de agua independiente.
    factor_inputs contiene solo cuentas económicas (salarios, impuestos,
    superávit operativo) — no stressors físicos de agua.

    Se devuelve Series de ceros. El intercambio de agua no se escribe
    en las actividades de Brightway2 cuando el valor es 0.
    """
    import pandas as pd
    log.info("Water footprint: extensión física de agua no disponible en "
             "EXIOBASE 3.10.2 pxp — factor_inputs contiene solo cuentas económicas.")
    return pd.Series(0.0, index=io_system.air_emissions.M.columns)


def _write_to_brightway(bw, io_system, gwp_series, water_series):
    """
    Escribe cada sector de EXIOBASE como una actividad en Brightway2.

    Cada actividad tiene:
      - 1 exchange de producción (production, 1.0 M.EUR)
      - 1 exchange de biósfera CO2 con amount = gwp_pre-agregado (kg CO2-eq/M.EUR)
      - 1 exchange de biósfera agua  (m3/M.EUR)

    Este diseño permite que bw.LCA({act: demanda}, method=GWP100).score
    devuelva directamente el impacto correcto en kg CO2-eq.
    """
    log.info(f"Localizando flujos de biósfera para intercambios...")
    co2_key   = _find_co2_fossil_key(bw)
    water_key = _find_water_key(bw)
    log.info(f"  CO2  key: {co2_key}")
    log.info(f"  Agua key: {water_key}")

    db = bw.Database(DB_NAME)
    db.register()
    log.info(f"Base de datos '{DB_NAME}' registrada.")

    sector_cols = list(io_system.air_emissions.M.columns)  # MultiIndex (region, sector)
    total = len(sector_cols)

    log.info(f"Construyendo {total} actividades para escritura...")

    data = {}

    for i, (region, sector) in enumerate(sector_cols):
        if i % 1000 == 0:
            log.info(f"  Preparando actividades: {i}/{total}...")

        # Código único y buscable: usado por bw_calculator.py → exio_db.search()
        code = f"{region}__{sector}".replace(" ", "_").replace("/", "-")

        gwp_val   = float(gwp_series.get((region, sector), 0.0))
        water_val = float(water_series.get((region, sector), 0.0)) * AWARE_FACTOR_DEFAULT

        exchanges = [
            {
                "input":  (DB_NAME, code),
                "amount": 1.0,
                "type":   "production",
                "unit":   "M.EUR",
            },
        ]

        if gwp_val != 0.0:
            exchanges.append({
                "input":  co2_key,
                "name":   "Carbon dioxide, fossil",
                "amount": gwp_val,
                "unit":   "kg",
                "type":   "biosphere",
            })

        if water_val > 0.0:
            exchanges.append({
                "input":  water_key,
                "name":   "Water, unspecified natural origin",
                "amount": water_val,
                "unit":   "m3",
                "type":   "biosphere",
            })

        data[(DB_NAME, code)] = {
            "code":      code,
            "name":      sector,
            "location":  region,
            "unit":      "M.EUR",
            "type":      "process",
            "database":  DB_NAME,
            "comment":   f"EXIOBASE 3.10.2 pxp 2024 | GWP={gwp_val:.4f} kg CO2-eq/M.EUR",
            "exchanges": exchanges,
        }

    log.info(f"Escribiendo {len(data)} actividades en SQLite (puede tardar varios minutos)...")
    db.write(data)

    log.info(f"✅ '{DB_NAME}' escrita con {len(data)} actividades.")
    log.info(f"   Bases de datos en proyecto: {list(bw.databases)}")


def main():
    print("=" * 65)
    print("  Instalador EXIOBASE 3 → Brightway2")
    print("  Compatible con bw2io 0.8.12 + pymrio 0.6.x + pandas 3.x")
    print("=" * 65)
    print(f"  Proyecto BW  : {PROJECT_NAME}")
    print(f"  BD registrada: {DB_NAME}  ← coincide con bw_calculator.py")
    print(f"  Archivo ZIP  : {ZIP_PATH}")
    print(f"  Directorio   : {EXTRACT_DIR}")
    print()

    # 0. Asegurar pymrio disponible
    _ensure_pymrio()

    # 1. Inicializar Brightway2
    bw = _setup_brightway()

    # 2. Idempotencia
    if DB_NAME in bw.databases:
        log.info(f"'{DB_NAME}' ya registrada en Brightway2. Nada que hacer.")
        log.info("El motor Tier 2 (EXIOBASE) está activo.")
        return

    # 3. Extraer ZIP si es necesario
    _extract_zip()

    # 4. Parsear EXIOBASE y calcular M = S·L con pymrio
    import pymrio
    log.info(f"Cargando EXIOBASE desde '{EXTRACT_DIR}'...")
    log.warning("Este proceso puede tardar 10–30 min y usar varios GB de RAM.")
    io = pymrio.parse_exiobase3(path=EXTRACT_DIR)

    log.info("Calculando matrices A, L, S y multiplicadores M (M = S·L)...")
    io.calc_all()
    log.info("Cálculo de multiplicadores completado.")

    # 5. Pre-agregar GWP100 y agua por sector
    gwp_series   = _compute_gwp_per_sector(io)
    water_series = _compute_water_per_sector(io)

    # 6. Escribir en Brightway2
    _write_to_brightway(bw, io, gwp_series, water_series)

    print()
    print("=" * 65)
    print(f"  ✅  EXIOBASE 3 importado exitosamente como '{DB_NAME}'")
    print(f"  Tier 2 EXIOBASE activo en Tequila LCA Studio.")
    print("=" * 65)


if __name__ == "__main__":
    main()