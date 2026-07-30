# Tequila LCA Studio 🌵🥃

**Tequila LCA Studio** es una aplicación web desarrollada en **Django** diseñada para realizar la **Evaluación del Ciclo de Vida (LCA / ECV)** en la producción de tequila, desde la cuna hasta la puerta (*cradle-to-gate*). La herramienta permite a productores, investigadores y consultores ambientales cuantificar, visualizar y optimizar el impacto ambiental del tequila.

---

## 1. ¿Qué hace la aplicación?

La aplicación permite modelar el inventario de ciclo de vida (LCI) de destilerías y calcular indicadores clave de sostenibilidad (LCIA) utilizando metodologías estándar y modelos simplificados basados en *Brightway2*, *EXIOBASE 3* y *AWARE*.

### Funcionalidades principales:
* **Huella de Carbono (GWP100a)**: Cuantifica las emisiones totales de Gases de Efecto Invernadero (GEI) expresadas en `kg CO₂-eq` por botella o unidad funcional.
* **Huella Hídrica (Modelo AWARE)**: Evalúa la escasez de agua considerando el consumo directo e indirecto de agua en regiones agrícolas y de procesamiento en México (`m³ world-eq`).
* **Estequiometría de CO₂ Biogénico**: Modela las emisiones biogénicas directas generadas durante la fermentación de los azúcares del jugo de agave tequilana Weber.
* **Créditos por Expansión del Sistema**: Incorpora créditos ambientales y offsets por la valorización energética de subproductos como el bagazo de agave (energía térmica/eléctrica) y vinazas.
* **Visualización Dinámica de Flujos (Diagramas de Sankey)**: Gráficos interactivos generados con Plotly que muestran el flujo de impacto ambiental a través de la cadena de suministro (desde insumos agrícolas y energía hasta el producto final).
* **Análisis de Puntos Críticos (*Hotspots*)**: Identifica automáticamente las etapas del proceso (cultivo de agave, cocción, destilación, empaque en botellas de vidrio, etc.) con mayor contribución al impacto ambiental.
* **Gestión Flexible de Inventario**:
  * Edición interactiva de intercambios (insumos de tecnosfera, emisiones de biosfera y salidas).
  * Carga masiva de inventarios vía archivos **CSV** con modos de reemplazo o anexado de datos.
* **Benchmarking Comparativo por Clase de Tequila**: Permite comparar el perfil ambiental según la maduración del tequila:
  * **Blanco / Silver** (Sin maduración)
  * **Reposado** (2 a 12 meses en barrica)
  * **Añejo** (1 a 3 años en barrica)
  * **Extra Añejo** (Más de 3 años en barrica)
* **Exportación de Resultados**: Descarga directa de informes de puntos críticos en formato CSV para análisis externo.

---

## 2. Instalación y Ejecución Local

Sigue estos pasos para instalar y ejecutar el proyecto en tu entorno local.

### Prerrequisitos
* **Python 3.10** o superior instalado.
* Git.

### Pasos de Instalación

1. **Clonar el repositorio** (o navegar al directorio del proyecto):
   ```bash
   git clone https://github.com/tu-usuario/tequila.git
   cd tequila
   ```

2. **Crear y activar un entorno virtual**:
   * En macOS / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * En Windows (PowerShell / CMD):
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```

3. **Instalar dependencias**:
   ```bash
   pip install django pandas plotly brightway2 bw2analyzer
   ```
   *(Nota: Si usas el archivo de dependencias del proyecto, puedes ejecutar `pip install -r requirements.txt` si está disponible).*

4. **Aplicar las migraciones de la base de datos**:
   ```bash
   python manage.py migrate
   ```

5. **(Opcional) Ejecutar las pruebas unitarias**:
   Verifica que la aplicación y los motores de cálculo funcionen correctamente:
   ```bash
   python manage.py test
   ```

6. **Iniciar el servidor de desarrollo local**:
   ```bash
   python manage.py runserver
   ```

7. **Acceder a la aplicación**:
   Abre tu navegador web e ingresa a: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 3. Guía de Uso de la Herramienta

La interfaz web está organizada en tres módulos principales accesibles desde la barra de navegación:

### A. Panel Principal (*Dashboard* - `/`)
* **Ajuste de Parámetros Globales**:
  * **Unidad Funcional (ml)**: Ajusta el volumen de la botella (por defecto `700 ml`). Todos los insumos y resultados se escalarán automáticamente.
  * **Tasa de Reciclaje de Vidrio (%)**: Modifica el porcentaje de vidrio reciclado incorporado en las botellas para evaluar escenarios de economía circular.
* **Indicadores Clave (KPIs)**: Revisa los totales de Huella de Carbono, Huella Hídrica AWARE y CO₂ biogénico.
* **Diagramas de Sankey**: Explora los gráficos interactivos de Sankey para entender visualmente cómo se distribuye el impacto ambiental entre las distintas fases.
* **Tabla de Hotspots**: Consulta la tabla comparativa de etapas para identificar de forma rápida los insumos y procesos con mayor impacto.

### B. Gestión de Inventarios (*Inventory Management* - `/inventory/`)
* **Edición de Formulario**: Modifica manualmente las cantidades, unidades, descripciones y tipos de intercambio (tecnosfera, biosfera, subproductos).
* **Carga Masiva vía CSV**:
  1. Selecciona un archivo CSV con el inventario de tu destilería.
  2. Selecciona el **Modo de Carga**:
     * **Reemplazar inventario existente**: Borra el inventario previo y carga únicamente el contenido del nuevo archivo.
     * **Anexar al inventario existente**: Agrega las nuevas filas manteniendo los datos anteriores.
  3. Haz clic en **Subir CSV**.

### C. Benchmarking Comparativo (*Comparative Benchmarking* - `/benchmark/`)
* Compara el impacto de tu producto contra las métricas de referencia para las distintas clases de tequila (Blanco, Reposado, Añejo y Extra Añejo), evaluando el efecto del tiempo de añejamiento en barricas de roble y la evaporación ("mermas / angel's share").

### D. Exportar Datos (`/export/csv/`)
* En el Panel Principal, utiliza el botón **Exportar Resumen CSV** para descargar un archivo estructurado con todos los resultados de puntos críticos y métricas ambientales.
