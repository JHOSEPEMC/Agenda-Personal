# -- Modelos de base de datos -- #
# 01: imports y configuracion inicial
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()  # instancia de SQLAlchemy para manejar la base de datos

# -- modelo Usuario -- #
# 01: almacena info de usuarios del sistema (simplificado)
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)  # email unico con indice
    password_hash = db.Column(db.String(255), nullable=False)  # contraseña hasheada
    verificado = db.Column(db.Boolean, default=False)  # si verifico su correo
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)  # cuando se creo
    
    # relacion uno a muchos con Agenda
    agendas = db.relationship('Agenda', backref='usuario', cascade="all, delete-orphan")

# -- modelo Agenda -- #
# 01: almacena las anotaciones de los usuarios
class Agenda(db.Model):
    __tablename__ = 'agenda'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)  # FK a usuario
    fecha = db.Column(db.Date, nullable=False)  # fecha de la anotacion
    anotacion = db.Column(db.Text, nullable=True)  # texto de la anotacion
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)  # cuando se creo
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # ultima modificacion
    
    # indice para busquedas rapidas por fecha y usuario
    __table_args__ = (
        db.Index('idx_agenda_usuario_fecha', 'usuario_id', 'fecha'),
    )