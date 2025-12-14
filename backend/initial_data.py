from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from . import models
import os

# Asegúrate de que las tablas estén creadas
models.Base.metadata.create_all(bind=engine)

def create_initial_data(db: Session):
    # Contribuyente de ejemplo
    contribuyente_existente = db.query(models.Contribuyente).filter(models.Contribuyente.dni == "12345678").first()
    if not contribuyente_existente:
        contribuyente1 = models.Contribuyente(
            dni="12345678",
            nombre="Juan Pérez",
            monto_mensual_impuesto=500.0,
            tipo_impuesto="Tasa Retributiva",
            deuda=0.0,
            estado_suscripcion="Activa",
            id_suscripcion_mp="MP_SUB_123",
            enlace_suscripcion_mp="https://mercadopago.com/mp_link_123"
        )
        db.add(contribuyente1)
        db.commit()
        db.refresh(contribuyente1)
        print(f"Contribuyente {contribuyente1.nombre} creado.")
    else:
        print(f"Contribuyente {contribuyente_existente.nombre} ya existe.")

    contribuyente_con_deuda = db.query(models.Contribuyente).filter(models.Contribuyente.dni == "87654321").first()
    if not contribuyente_con_deuda:
        contribuyente2 = models.Contribuyente(
            dni="87654321",
            nombre="María García",
            monto_mensual_impuesto=750.0,
            tipo_impuesto="Derechos de Construcción",
            deuda=1500.0, # Ejemplo de deuda
            estado_suscripcion="Pendiente",
            id_suscripcion_mp=None,
            enlace_suscripcion_mp=None
        )
        db.add(contribuyente2)
        db.commit()
        db.refresh(contribuyente2)
        print(f"Contribuyente {contribuyente2.nombre} creado.")
    else:
        print(f"Contribuyente {contribuyente_con_deuda.nombre} ya existe.")

if __name__ == "__main__":
    db = SessionLocal()
    create_initial_data(db)
    db.close()
    print("Datos iniciales cargados.")
