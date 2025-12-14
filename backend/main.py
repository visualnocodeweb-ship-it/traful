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

# <<-- OBTENER NGROK_PUBLIC_URL -->>
NGROK_PUBLIC_URL = os.getenv("NGROK_PUBLIC_URL")
if not NGROK_PUBLIC_URL:
    raise ValueError("NGROK_PUBLIC_URL no está configurado en el archivo .env")
print(f"DEBUG: NGROK_PUBLIC_URL obtenido: {NGROK_PUBLIC_URL}")
# <<-- FIN OBTENER NGROK_PUBLIC_URL -->>

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
            "dni": fields.get("dni"),
            "nombre": fields.get("nombre"),
            "monto_mensual_impuesto": fields.get("monto_mensual_impuesto"),
            "tipo_impuesto": fields.get("tipo_impuesto"),
            "deuda": fields.get("deuda"),
            "estado_suscripcion": fields.get("estado_suscripcion"),
            "id_suscripcion_mp": fields.get("id_suscripcion_mp"),
            "enlace_suscripcion_mp": fields.get("enlace_suscripcion_mp"),
            "fecha_creacion": fields.get("fecha_creacion"),
            "ultima_actualizacion": fields.get("ultima_actualizacion")
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
                "title": f"Impuesto {fields.get('tipo_impuesto')} - DNI: {dni}",
                "quantity": 1,
                "unit_price": monto,
                "currency_id": "ARS" # Asumimos ARS (Pesos Argentinos)
            }
        ],
        "payer": {
            "name": fields.get('nombre'),
            "surname": "", # Se puede parsear el nombre o dejar vacío
            "email": "test_user@test.com" # Email de prueba, debería ser real
        },
        "back_urls": {
            "success": f"{NGROK_PUBLIC_URL}/success", # <<-- USAR NGROK_PUBLIC_URL
            "pending": f"{NGROK_PUBLIC_URL}/pending",
            "failure": f"{NGROK_PUBLIC_URL}/failure",
        },
        "notification_url": f"{NGROK_PUBLIC_URL}/webhook/mercadopago", # <<-- USAR NGROK_PUBLIC_URL
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
                            updates['estado_suscripcion'] = "Activa"
                            # Asegúrate de que 'deuda' en Airtable sea un número.
                            current_deuda = fields.get('deuda', 0)
                            updates['deuda'] = max(0, current_deuda - transaction_amount)
                        elif payment_status in ["rejected", "cancelled"]:
                            updates['estado_suscripcion'] = "Problema_Pago"
                        
                        if updates:
                            airtable_contribuyentes.update(contribuyente_id, updates)

                        # Registrar el pago en la tabla de pagos de Airtable
                        new_pago_fields = {
                            "contribuyente_dni": external_reference,
                            "monto_pagado": transaction_amount,
                            "id_transaccion_mp": payment_id,
                            "estado_pago": payment_status,
                            "fecha_pago_real": date_approved.isoformat(),
                            "metodo_registro": "Webhook_MP"
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
