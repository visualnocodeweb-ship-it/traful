import csv
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend import models
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Asegúrate de que las tablas estén creadas
models.Base.metadata.create_all(bind=engine)

def import_contribuyentes_from_csv(db: Session, csv_file_path: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(script_dir, "..") # Un nivel arriba para llegar a la raíz del proyecto
    full_csv_path = os.path.join(project_root, csv_file_path)

    print(f"DEBUG: Buscando CSV en: {full_csv_path}")

    if not os.path.exists(full_csv_path):
        print(f"ERROR: El archivo CSV no se encontró en la ruta: {full_csv_path}")
        return

    with open(full_csv_path, mode='r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            raw_dni = row['DNI'].strip()
            # Limpiar el DNI: quitar puntos. Si el DNI contiene varios números (ej: "123 456"), tomamos el primero
            dni_clean = raw_dni.replace('.', '').replace(' ', '') # Eliminar todos los puntos y espacios
            dni_parts = dni_clean.split()
            dni = dni_parts[0] if dni_parts else "" # Tomar el primer DNI si hay varios, o vacío si no hay ninguno

            nombre = row['CONTRIBUYENTE'].strip()
            monto_str = row['DICIEMBRE']
            tipo_impuesto = "Tasa Retributiva"

            if not dni:
                print(f"ADVERTENCIA: Fila ignorada por DNI vacío para contribuyente '{nombre}'.")
                continue

            try:
                monto_str_cleaned = monto_str.replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
                if monto_str_cleaned == '-':
                    monto_mensual_impuesto = 0.0
                else:
                    monto_mensual_impuesto = float(monto_str_cleaned)
            except ValueError:
                print(f"ADVERTENCIA: No se pudo convertir el monto '{monto_str}' a número para DNI {dni}. Se usará 0.0.")
                monto_mensual_impuesto = 0.0

            try:
                contribuyente_existente = db.query(models.Contribuyente).filter(models.Contribuyente.dni == dni).first()

                if contribuyente_existente:
                    contribuyente_existente.nombre = nombre
                    contribuyente_existente.monto_mensual_impuesto = monto_mensual_impuesto
                    contribuyente_existente.tipo_impuesto = tipo_impuesto
                    db.add(contribuyente_existente) # Asegurarse de que esté en la sesión
                    print(f"Contribuyente con DNI {dni} actualizado.")
                else:
                    nuevo_contribuyente = models.Contribuyente(
                        dni=dni,
                        nombre=nombre,
                        monto_mensual_impuesto=monto_mensual_impuesto,
                        tipo_impuesto=tipo_impuesto
                    )
                    db.add(nuevo_contribuyente)
                    print(f"Contribuyente con DNI {dni} creado.")
                db.commit() # Commit por cada registro para evitar que un error de uno detenga todo
            except Exception as e:
                db.rollback() # Hacer rollback si hay un error
                print(f"ERROR: No se pudo procesar el contribuyente con DNI {dni} ({nombre}). Error: {e}")
        # db.commit() # Ya no es necesario un commit al final del bucle si se hace por registro
    print("Importación del CSV completada.")

if __name__ == "__main__":
    db = SessionLocal()
    # Asumiendo que el CSV se llama 'retributivos.csv' y está en la raíz del proyecto
    import_contribuyentes_from_csv(db, 'retributivos.csv')
    db.close()
