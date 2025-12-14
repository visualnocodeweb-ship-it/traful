import csv
import os
import re
import requests
import json

# --- CONFIGURACIÓN ---
# Lee las credenciales de Airtable desde variables de entorno para mayor seguridad.
# El usuario debe configurar estas variables en su entorno de ejecución.
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")

SOURCE_FILE = 'retributivos.csv'

def clean_amount(amount_str):
    """Limpia y convierte un string de monto a un número flotante."""
    if not amount_str:
        return 0.0
    # Elimina el símbolo de moneda, espacios en blanco y separadores de miles.
    cleaned_str = re.sub(r'[$\\s.]', '', amount_str)
    # Reemplaza la coma decimal por un punto.
    cleaned_str = cleaned_str.replace(',', '.')
    try:
        return float(cleaned_str)
    except (ValueError, TypeError):
        return 0.0

def process_csv_data(file_path):
    """
    Lee y procesa los datos del archivo CSV según las reglas de negocio.
    """
    records_to_upload = []
    print(f"Procesando el archivo: {file_path}")

    try:
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            
            # Limpiar cabeceras
            headers = [h.strip() for h in next(reader)]
            print(f"Cabeceras detectadas: {headers}")

            # Encontrar los índices de las columnas necesarias
            try:
                idx_contribuyente = headers.index('CONTRIBUYENTE')
                idx_dni = headers.index('DNI')
                idx_nomenclatura = headers.index('NOMENCLATURA CATASTRAL')
                idx_diciembre = headers.index('DICIEMBRE')
            except ValueError as e:
                print(f"Error: Falta una columna esperada en el CSV: {e}")
                return []

            for row in reader:
                monto_diciembre = clean_amount(row[idx_diciembre])

                # Regla: Solo importar filas con un valor mayor a cero en DICIEMBRE.
                if monto_diciembre > 0:
                    dni = row[idx_dni].strip()
                    nomenclatura = row[idx_nomenclatura].strip()

                    # Regla: Usar DNI o, si está ausente, Nomenclatura Catastral.
                    id_contribuyente = dni if dni else nomenclatura
                    
                    if not id_contribuyente or id_contribuyente == "sin mensura":
                        print(f"Advertencia: Se omitió una fila por falta de DNI y Nomenclatura válida. Contribuyente: {row[idx_contribuyente]}")
                        continue

                    record = {
                        "fields": {
                            "ID_Contribuyente": id_contribuyente,
                            "Nombre_Contribuyente": row[idx_contribuyente].strip(),
                            "Monto_Mensual_Impuesto": monto_diciembre,
                            "Tipo_Impuesto": "Tasa Retributiva"
                        }
                    }
                    records_to_upload.append(record)

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{file_path}'.")
        return []
    except Exception as e:
        print(f"Ocurrió un error inesperado al procesar el CSV: {e}")
        return []
        
    print(f"Se procesaron {len(records_to_upload)} registros válidos para subir a Airtable.")
    return records_to_upload

def upload_to_airtable(records):
    """
    Sube los registros a la tabla de Airtable especificada.
    """
    if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
        print("Error: Faltan las variables de entorno de Airtable (AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME).")
        print("No se puede continuar con la subida de datos.")
        return

    print(f"Iniciando la subida de {len(records)} registros a la tabla '{AIRTABLE_TABLE_NAME}' en Airtable...")
    
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Airtable API permite crear hasta 10 registros por solicitud.
    for i in range(0, len(records), 10):
        chunk = records[i:i+10]
        data = json.dumps({"records": chunk})
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()  # Lanza un error para respuestas 4xx/5xx
            print(f"Lote de {len(chunk)} registros subido exitosamente.")
        except requests.exceptions.HTTPError as e:
            print(f"Error al subir un lote a Airtable: {e}")
            print("Respuesta del servidor:", response.text)
            # Podrías agregar lógica aquí para reintentar o guardar los registros fallidos.
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión al intentar subir un lote: {e}")

    print("Proceso de subida a Airtable finalizado.")

def main():
    """Función principal del script."""
    processed_records = process_csv_data(SOURCE_FILE)
    
    if processed_records:
        # La función de subida se activa para ejecutarse.
        upload_to_airtable(processed_records)


if __name__ == "__main__":
    main()
