# -- Modelos de base de datos -- #
# 01: imports y configuracion inicial
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()  # instancia de SQLAlchemy para manejar la base de datos

# -- modelo Usuario -- #
# 01: almacena info de usuarios del sistema
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)  # email unico
    password_hash = db.Column(db.String(255), nullable=False)  # contraseña hasheada
    tipo = db.Column(db.String(20), default='postulante')  # postulante o admin
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)  # cuando se creo
    verificado = db.Column(db.Boolean, default=False)  # si verifico su correo
    # relacion uno a uno con Postulante
    postulante = db.relationship('Postulante', backref='usuario', uselist=False, cascade="all, delete-orphan")

# -- modelo Postulante -- #
# 01: info especifica de los postulantes
class Postulante(db.Model):
    __tablename__ = 'postulantes'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)  # FK a usuario
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=False)  # fecha de nacimiento
    dni = db.Column(db.String(20))  # documento de identidad
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aprobado, rechazado
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)  # cuando se registro