from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from .database import Base

class Contribuyente(Base):
    __tablename__ = "contribuyentes"

    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String, unique=True, index=True)
    nombre = Column(String)
    monto_mensual_impuesto = Column(Float)
    tipo_impuesto = Column(String)
    deuda = Column(Float, default=0.0)
    estado_suscripcion = Column(String, default="Pendiente") # Ej: Pendiente, Activa, Cancelada, Problema_Pago
    id_suscripcion_mp = Column(String, nullable=True) # ID de la suscripción en MercadoPago
    enlace_suscripcion_mp = Column(String, nullable=True) # Enlace de pago de MercadoPago
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    ultima_actualizacion = Column(DateTime(timezone=True), onupdate=func.now())

class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    contribuyente_dni = Column(String, index=True) # Enlaza con el DNI del contribuyente
    monto_pagado = Column(Float)
    id_transaccion_mp = Column(String, unique=True)
    estado_pago = Column(String) # Ej: Pagado, Pendiente, Rechazado, Cancelado
    fecha_pago_real = Column(DateTime(timezone=True))
    metodo_registro = Column(String) # Ej: Webhook_MP, Manual
    notas_pago = Column(String, nullable=True)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
