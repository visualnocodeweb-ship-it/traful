from fastapi import FastAPI, HTTPException
import mercadopago # Importar la librería de MercadoPago
import os
from dotenv import load_dotenv # Para cargar las variables de entorno
from datetime import datetime # Para manejar fechas
from fastapi.middleware.cors import CORSMiddleware # <<-- AÑADIR ESTA LÍNEA
from airtable import Airtable # <<-- NUEVA IMPORTACIÓN DE AIRTABLE

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
print(f"DEBUG: Ruta .env usada por load_dotenv: {os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')}")

# Variables de entorno para MercadoPago
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
print(f"DEBUG: MERCADOPAGO_ACCESS_TOKEN obtenido: {MERCADOPAGO_ACCESS_TOKEN}")
if not MERCADOPAGO_ACCESS_TOKEN:
    raise ValueError("MERCADOPAGO_ACCESS_TOKEN no está configurado en el archivo .env")

# <<-- ELIMINAMOS NGROK_PUBLIC_URL Y USAMOS LA URL FIJA DEL BACKEND -->>
BACKEND_PUBLIC_URL = "https://traful.onrender.com"
print(f"DEBUG: BACKEND_PUBLIC_URL configurada: {BACKEND_PUBLIC_URL}")
# <<-- FIN NGROK_PUBLIC_URL -->>

sdk = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)

# Variables de entorno para Airtable
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_CONTRIBUYENTES_TABLE_NAME = os.getenv("AIRTABLE_CONTRIBUYENTES_TABLE_NAME")
AIRTABLE_PAGOS_TABLE_NAME = os.getenv("AIRTABLE_PAGOS_TABLE_NAME")

if not AIRTABLE_API_KEY:
    raise ValueError("AIRTABLE_API_KEY no está configurado en el archivo .env")
if not AIRTABLE_BASE_ID:
    raise ValueError("AIRTABLE_BASE_ID no está configurado en el archivo .env")
if not AIRTABLE_CONTRIBUYENTES_TABLE_NAME:
    raise ValueError("AIRTABLE_CONTRIBUYENTES_TABLE_NAME no está configurado en el archivo .env")
if not AIRTABLE_PAGOS_TABLE_NAME:
    raise ValueError("AIRTABLE_PAGOS_TABLE_NAME no está configurado en el archivo .env")

# Inicializar clientes de Airtable
airtable_contribuyentes = Airtable(AIRTABLE_BASE_ID, AIRTABLE_CONTRIBUYENTES_TABLE_NAME, api_key=AIRTABLE_API_KEY)
airtable_pagos = Airtable(AIRTABLE_BASE_ID, AIRTABLE_PAGOS_TABLE_NAME, api_key=AIRTABLE_API_KEY)

app = FastAPI()

# <<-- AÑADIR ESTE BLOQUE DE CONFIGURACIÓN CORS -->>
origins = [
    "http://localhost:5173",  # Origen de la aplicación React
    "http://127.0.0.1:5173",  # Posiblemente también se acceda por 127.0.0.1
    "https://trafulfrontend.onrender.com", # <<-- NUEVO: Origen del frontend desplegado
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos los encabezados
)
# <<-- FIN DEL BLOQUE CORS -->>

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Contribuyentes API (Airtable Version)"}

# Endpoint para obtener información del contribuyente por DNI desde Airtable
@app.get("/contribuyentes/{dni}")
async def get_contribuyente(dni: str):
    # Buscar el contribuyente por DNI en Airtable
    # Airtable search devuelve una lista de registros que coinciden
    # Asumimos que DNI es un campo único en Airtable
    records = airtable_contribuyentes.search('ID_Contribuyente', dni) # Buscar en el campo 'ID_Contribuyente'

    if records:
        contribuyente_record = records[0] # Tomar el primer registro encontrado
        fields = contribuyente_record['fields']
        # Devolver un diccionario con los campos del contribuyente
        return {
            "id": contribuyente_record['id'], # El ID del registro de Airtable
            "dni": fields.get("ID_Contribuyente"), # Usar ID_Contribuyente como DNI
            "nombre": fields.get("Nombre_Contribuyente"), # Usar Nombre_Contribuyente
            "monto_mensual_impuesto": fields.get("Monto_Mensual_Impuesto"),
            "tipo_impuesto": fields.get("Tipo_Impuesto"),
            "deuda": None, # Este campo no existe en la tabla Contribuyentes
            "estado_suscripcion": fields.get("Estado_Suscripcion"),
            "id_suscripcion_mp": fields.get("ID_Suscripcion_MP"),
            "enlace_suscripcion_mp": fields.get("Enlace_Suscripcion_MP"),
            "fecha_creacion": contribuyente_record.get('createdTime'), # Airtable tiene 'createdTime'
            "ultima_actualizacion": None # Este campo no existe en la tabla Contribuyentes

        }
    raise HTTPException(status_code=404, detail="Contribuyente no encontrado")


# Endpoint para iniciar el pago con MercadoPago usando Airtable
@app.post("/pagar")
async def initiate_payment(dni: str, monto: float):
    # Buscar el contribuyente por DNI en Airtable
    records = airtable_contribuyentes.search('ID_Contribuyente', dni)
    if not records:
        raise HTTPException(status_code=404, detail="Contribuyente no encontrado")

    contribuyente_record = records[0]
    fields = contribuyente_record['fields']

    # Crear una preferencia de pago en MercadoPago
    preference_data = {
        "items": [
            {
                "title": f"Impuesto {fields.get('Tipo_Impuesto')} - DNI: {dni}", # Usar Tipo_Impuesto
                "quantity": 1,
                "unit_price": monto,
                "currency_id": "ARS" # Asumimos ARS (Pesos Argentinos)
            }
        ],
        "payer": {
            "name": fields.get('Nombre_Contribuyente'), # Usar Nombre_Contribuyente
            "surname": "", # Se puede parsear el nombre o dejar vacío
            "email": "test_user@test.com" # Email de prueba, debería ser real
        },
        "back_urls": {
            "success": f"{BACKEND_PUBLIC_URL}/success", # <<-- USAR BACKEND_PUBLIC_URL
            "pending": f"{BACKEND_PUBLIC_URL}/pending",
            "failure": f"{BACKEND_PUBLIC_URL}/failure",
        },
        "notification_url": f"{BACKEND_PUBLIC_URL}/webhook/mercadopago", # <<-- USAR BACKEND_PUBLIC_URL
        "external_reference": dni # Usamos el DNI como referencia externa
    }

    try:
        preference_response = sdk.preference().create(preference_data)
        print("MercadoPago API Full Response:", preference_response)

        if "status_code" in preference_response and preference_response["status_code"] >= 400:
            error_detail = preference_response.get("response", {}).get("message", "Error desconocido de MercadoPago")
            raise HTTPException(status_code=preference_response["status_code"], detail=f"Error de MercadoPago: {error_detail}")

        if "response" not in preference_response:
             raise HTTPException(status_code=500, detail=f"Respuesta inesperada de MercadoPago: {preference_response}")

        preference = preference_response["response"]
        payment_link = preference["init_point"]

        # Opcional: Actualizar el contribuyente con el enlace de pago temporal en Airtable
        # if payment_link:
        #     airtable_contribuyentes.update(contribuyente_record['id'], {'enlace_suscripcion_mp': payment_link})

        return {"message": f"Payment initiated for DNI: {dni}", "payment_link": payment_link}

    except Exception as e:
        print(f"Error detallado en initiate_payment: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear preferencia de pago: {e}")


# Endpoint para el webhook de MercadoPago usando Airtable
@app.post("/webhook/mercadopago")
async def mercadopago_webhook(payload: dict):
    print(f"DEBUG: Webhook Payload recibido: {payload}")

    if "data" in payload and "id" in payload["data"]:
        payment_id = payload["data"]["id"]
        topic = payload.get("topic") or payload.get("type")

        if payment_id == "123456": # Es una notificación de simulación de MercadoPago
            print("DEBUG: Webhook de simulación recibido. No se procesará el pago real.")
            return {"message": "Webhook de simulación procesado correctamente (sin acción de pago real)"}

        if topic == "payment":
            payment_info = sdk.payment().get(payment_id)
            if payment_info and payment_info["response"]:
                payment_status = payment_info["response"]["status"]
                external_reference = payment_info["response"].get("external_reference")
                transaction_amount = payment_info["response"].get("transaction_amount")
                date_approved_str = payment_info["response"].get("date_approved")
                date_approved = datetime.fromisoformat(date_approved_str.replace("Z", "+00:00")) if date_approved_str else datetime.now()

                if external_reference:
                    records = airtable_contribuyentes.search('ID_Contribuyente', external_reference)
                    if records:
                        contribuyente_record = records[0]
                        contribuyente_id = contribuyente_record['id']
                        fields = contribuyente_record['fields']

                        # Actualizar estado de suscripción del contribuyente en Airtable
                        updates = {}
                        if payment_status == "approved":
                            updates['Estado_Suscripcion'] = "Activa" # Usar el nombre de campo correcto
                            # La deuda no está en la tabla Contribuyentes, por lo que no se actualiza aquí.
                        elif payment_status in ["rejected", "cancelled"]:
                            updates['Estado_Suscripcion'] = "Problema_Pago" # Usar el nombre de campo correcto
                        
                        if updates:
                            airtable_contribuyentes.update(contribuyente_id, updates)

                        # Registrar el pago en la tabla de pagos de Airtable
                        # Nota: El campo 'Socio' en Pagos_Mensuales es un linked record y espera un array de Record IDs.
                        # Para asociar un pago a un contribuyente, necesitamos el Record ID del contribuyente.
                        new_pago_fields = {
                            "ID_Pago": f"{external_reference}-{date_approved.strftime('%Y%m%d%H%M%S')}", # Generar un ID único para el pago
                            "Socio": [contribuyente_id], # Enlazar al contribuyente usando su Record ID de Airtable
                            "Año_Mes": date_approved.strftime('%Y-%m'),
                            "Fecha_Pago_Real": date_approved.isoformat(),
                            "Monto_Pagado": transaction_amount,
                            "ID_Transaccion_MP": payment_id,
                            "Estado_Pago": payment_status,
                            "Metodo_Registro": "Webhook_MP",
                            "Fecha_Registro": datetime.now().isoformat()
                        }
                        airtable_pagos.insert(new_pago_fields)

                        print(f"Pago {payment_id} procesado para DNI {external_reference}. Estado: {payment_status}")
                        return {"message": "Webhook processed successfully"}
                    else:
                        print(f"Contribuyente con DNI {external_reference} no encontrado en Airtable.")
                        raise HTTPException(status_code=404, detail=f"Contribuyente con DNI {external_reference} no encontrado.")
                else:
                    print(f"External reference no encontrada en pago {payment_id}.")
                    raise HTTPException(status_code=400, detail="External reference no encontrada en la notificación de pago.")
            else:
                print(f"Detalles de pago para ID {payment_id} no encontrados.")
                raise HTTPException(status_code=400, detail="Detalles de pago no encontrados.")

    print("MercadoPago Webhook recibido (sin data.id o topic conocido):", payload)
    return {"message": "Webhook received successfully (no action taken)"}
