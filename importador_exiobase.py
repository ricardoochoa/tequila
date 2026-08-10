import os
import sys
import brightway2 as bw
import bw2io as bi

def main():
    print("=====================================================")
    print("   Instalador de EXIOBASE 3 para Tequila LCA Studio  ")
    print("=====================================================")
    
    project_name = "Tequila_LCA_Mexico"
    db_name = "EXIOBASE_3"
    ruta_exiobase = os.path.join("scratch", "exiobase3")

    # 1. Configurar el proyecto correcto de Brightway2
    bw.projects.set_current(project_name)
    
    # 2. Verificar si la base de datos ya fue instalada
    if db_name in bw.databases:
        print(f"\n✅ ¡La base de datos '{db_name}' ya está instalada en el proyecto '{project_name}'!")
        print("No es necesario volver a importarla.")
        return

    # 3. Verificar si la carpeta con los datos de EXIOBASE existe
    if not os.path.exists(ruta_exiobase):
        print(f"\n❌ ERROR: No se encontró la ruta '{ruta_exiobase}'.")
        print("Por favor, asegúrate de crear la carpeta 'scratch/exiobase3/' y")
        print("extraer ahí los archivos del ZIP de EXIOBASE 3 antes de continuar.")
        sys.exit(1)

    print(f"\nLeyendo archivos desde '{ruta_exiobase}'...")
    print("⚠️  ADVERTENCIA: Este proceso puede tardar entre 5 y 15 minutos")
    print("y consumirá varios Gigabytes de memoria RAM. ¡No cierres la terminal!")
    print("-----------------------------------------------------\n")
    
    try:
        # Inicializar el importador (Asumiendo versión Monetaria, que es el estándar)
        exio_importer = bi.importers.Exiobase3MonetaryImporter(ruta_exiobase, db_name=db_name)
        
        print("\n⏳ Aplicando estrategias de normalización (vinculando flujos)...")
        exio_importer.apply_strategies()
        
        print("\n💾 Escribiendo la base de datos en Brightway2 (SQLite)...")
        exio_importer.write_database()
        
        print("\n🎉 ¡EXIOBASE 3 importado y registrado exitosamente!")
        print("El motor de cálculo de LCA está listo para usarse.")
        
    except Exception as e:
        print(f"\n❌ Ocurrió un error durante la importación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()