from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional # Importar Optional para campos que pueden ser None
from . import models, database
import mercadopago # Importar la librería de MercadoPago
import os
from dotenv import load_dotenv # Para cargar las variables de entorno
from datetime import datetime # Para manejar fechas
from fastapi.middleware.cors import CORSMiddleware # <<-- AÑADIR ESTA LÍNEA

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
print(f"DEBUG: Ruta .env usada por load_dotenv: {os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')}")
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


# Crear todas las tablas al iniciar la aplicación
models.Base.metadata.create_all(bind=database.engine)

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

# Dependencia para obtener la sesión de la base de datos
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Contribuyentes API"}

# Endpoint para obtener información del contribuyente por DNI
@app.get("/contribuyentes/{dni}")
async def get_contribuyente(dni: str, db: Session = Depends(get_db)):
    contribuyente = db.query(models.Contribuyente).filter(models.Contribuyente.dni == dni).first()
    if contribuyente:
        # Devuelve un diccionario para evitar problemas de serialización de objetos ORM directamente
        return {
            "id": contribuyente.id,
            "dni": contribuyente.dni,
            "nombre": contribuyente.nombre,
            "monto_mensual_impuesto": contribuyente.monto_mensual_impuesto,
            "tipo_impuesto": contribuyente.tipo_impuesto,
            "deuda": contribuyente.deuda,
            "estado_suscripcion": contribuyente.estado_suscripcion,
            "id_suscripcion_mp": contribuyente.id_suscripcion_mp,
            "enlace_suscripcion_mp": contribuyente.enlace_suscripcion_mp,
            "fecha_creacion": contribuyente.fecha_creacion.isoformat(), # Formato ISO para fechas
            "ultima_actualizacion": contribuyente.ultima_actualizacion.isoformat() if contribuyente.ultima_actualizacion else None
        }
    raise HTTPException(status_code=404, detail="Contribuyente no encontrado")


# Endpoint para iniciar el pago con MercadoPago
@app.post("/pagar")
async def initiate_payment(dni: str, monto: float, db: Session = Depends(get_db)):
    contribuyente = db.query(models.Contribuyente).filter(models.Contribuyente.dni == dni).first()
    if not contribuyente:
        raise HTTPException(status_code=404, detail="Contribuyente no encontrado")

    # Crear una preferencia de pago en MercadoPago
    preference_data = {
        "items": [
            {
                "title": f"Impuesto {contribuyente.tipo_impuesto} - DNI: {dni}",
                "quantity": 1,
                "unit_price": monto,
                "currency_id": "ARS" # Asumimos ARS (Pesos Argentinos)
            }
        ],
        "payer": {
            "name": contribuyente.nombre,
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
        print("MercadoPago API Full Response:", preference_response) # <-- Cambiada esta línea

        # Verificar si la respuesta contiene un error antes de intentar acceder a "response"
        if "status_code" in preference_response and preference_response["status_code"] >= 400:
            error_detail = preference_response.get("response", {}).get("message", "Error desconocido de MercadoPago")
            raise HTTPException(status_code=preference_response["status_code"], detail=f"Error de MercadoPago: {error_detail}")

        if "response" not in preference_response:
             raise HTTPException(status_code=500, detail=f"Respuesta inesperada de MercadoPago: {preference_response}")


        preference = preference_response["response"]
        payment_link = preference["init_point"] # URL para iniciar el pago

        # Opcional: Actualizar el contribuyente con el enlace de pago temporal
        # contribuyente.enlace_suscripcion_mp = payment_link
        # db.commit()
        # db.refresh(contribuyente)

        return {"message": f"Payment initiated for DNI: {dni}", "payment_link": payment_link}

    except Exception as e:
        # Imprimir la excepción completa para depuración
        print(f"Error detallado en initiate_payment: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear preferencia de pago: {e}")


# Endpoint para el webhook de MercadoPago
@app.post("/webhook/mercadopago")
async def mercadopago_webhook(payload: dict, db: Session = Depends(get_db)):
    print(f"DEBUG: Webhook Payload recibido: {payload}") # <-- Añadir esta línea para ver el payload completo

    if "data" in payload and "id" in payload["data"]:
        payment_id = payload["data"]["id"]
        topic = payload.get("topic") or payload.get("type")

        # <<< --- AÑADIR ESTE BLOQUE --- >>>
        if payment_id == "123456": # Es una notificación de simulación de MercadoPago
            print("DEBUG: Webhook de simulación recibido. No se procesará el pago real.")
            return {"message": "Webhook de simulación procesado correctamente (sin acción de pago real)"}
        # <<< --- FIN DEL BLOQUE A AÑADIR --- >>>

        # Dependiendo del topic, podemos buscar el tipo de recurso
        if topic == "payment":
            payment_info = sdk.payment().get(payment_id)
            if payment_info and payment_info["response"]:
                payment_status = payment_info["response"]["status"]
                external_reference = payment_info["response"].get("external_reference")
                transaction_amount = payment_info["response"].get("transaction_amount")
                date_approved_str = payment_info["response"].get("date_approved")
                date_approved = datetime.fromisoformat(date_approved_str.replace("Z", "+00:00")) if date_approved_str else datetime.now()


                if external_reference:
                    contribuyente = db.query(models.Contribuyente).filter(models.Contribuyente.dni == external_reference).first()
                    if contribuyente:
                        # Actualizar estado de suscripción del contribuyente si aplica
                        if payment_status == "approved":
                            contribuyente.estado_suscripcion = "Activa"
                            contribuyente.deuda = max(0, contribuyente.deuda - transaction_amount) # Reducir deuda
                        elif payment_status in ["rejected", "cancelled"]:
                            contribuyente.estado_suscripcion = "Problema_Pago"
                        db.commit()
                        db.refresh(contribuyente)

                        # Registrar el pago
                        new_pago = models.Pago(
                            contribuyente_dni=contribuyente.dni,
                            monto_pagado=transaction_amount,
                            id_transaccion_mp=payment_id,
                            estado_pago=payment_status,
                            fecha_pago_real=date_approved,
                            metodo_registro="Webhook_MP"
                        )
                        db.add(new_pago)
                        db.commit()
                        db.refresh(new_pago)
                        print(f"Pago {payment_id} procesado para DNI {external_reference}. Estado: {payment_status}")
                        return {"message": "Webhook processed successfully"}
                    else:
                        print(f"Contribuyente con DNI {external_reference} no encontrado.")
                        raise HTTPException(status_code=404, detail=f"Contribuyente con DNI {external_reference} no encontrado.")
                else:
                    print(f"External reference no encontrada en pago {payment_id}.")
                    raise HTTPException(status_code=400, detail="External reference no encontrada en la notificación de pago.")
            else:
                print(f"Detalles de pago para ID {payment_id} no encontrados.")
                raise HTTPException(status_code=400, detail="Detalles de pago no encontrados.")
        # Aquí se podrían añadir más lógicas para otros topics como "preapproval" (suscripciones)
        # elif topic == "preapproval":
        #     # Lógica para manejar la creación o actualización de suscripciones
        #     pass

    print("MercadoPago Webhook recibido (sin data.id o topic conocido):", payload)
    return {"message": "Webhook received successfully (no action taken)"}
