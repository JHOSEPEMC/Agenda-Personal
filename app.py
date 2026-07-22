# -- Configuracion inicial de la aplicacion -- #
# 01: importar librerias
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Agenda
from datetime import datetime, timedelta
from collections import defaultdict, namedtuple
from flask_mail import Message
import random, os, secrets
from config_mail import init_mail, mail
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import re #Para una mejor validacion de email.


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_por_defecto')
# Configurar tiempo de sesión (1 hora)
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# -- Configuracion de logging -- #
# 01: crear carpeta de logs si no existe
if not os.path.exists('logs'):
    os.mkdir('logs')

# 02: configurar handler para archivo de logs
file_handler = RotatingFileHandler(
    os.path.join('logs', 'app.log'),
    maxBytes=10000,
    backupCount=3
)
file_handler.setLevel(logging.INFO)

# 03: configurar formato de logs
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

# 04: configurar logs para consola (solo en desarrollo)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
app.logger.addHandler(console_handler)

# 05: funcion para loguear eventos de seguridad
def log_seguridad(evento, detalles, ip=None):
    if ip is None:
        ip = request.remote_addr if request else '0.0.0.0'
    app.logger.info(f"[SEGURIDAD] {evento} - {detalles} - IP: {ip}")

# 06: funcion para loguear errores
def log_error(evento, error, ip=None):
    if ip is None:
        ip = request.remote_addr if request else '0.0.0.0'
    app.logger.error(f"[ERROR] {evento} - {str(error)} - IP: {ip}")

app.logger.info("=== APLICACION INICIADA ===")

# -- Definir namedtuple para respuestas -- #
Resultado = namedtuple('Resultado', ['exito', 'mensaje', 'datos'])

# -- Configuracion de la app -- #
# 01: base de datos
app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
init_mail(app)

# Diccionario para almacenar intentos de login (en producción usar Redis)
intentos_login = defaultdict(list)

def verificar_rate_limit(key, limite=5, ventana=300):  # 5 intentos en 5 minutos
    ahora = datetime.now().timestamp()
    # Limpiar intentos antiguos
    intentos_login[key] = [t for t in intentos_login[key] if ahora - t < ventana]
    
    if len(intentos_login[key]) >= limite:
        tiempo_restante = int(ventana - (ahora - intentos_login[key][0]))
        return Resultado(False, f'Demasiados intentos. Espera {tiempo_restante} segundos', None)
    
    intentos_login[key].append(ahora)
    return Resultado(True, '', None)

# -- Funciones de validacion auxiliares -- #
def validar_email(email):
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

def validar_password(password):
    """Valida que la contraseña cumpla con los requisitos de seguridad"""
    if len(password) < 8:
        return Resultado(False, "La contraseña debe tener al menos 8 caracteres", None)
    if not any(c.isupper() for c in password):
        return Resultado(False, "La contraseña debe tener al menos una mayúscula", None)
    if not any(c.islower() for c in password):
        return Resultado(False, "La contraseña debe tener al menos una minúscula", None)
    if not any(c.isdigit() for c in password):
        return Resultado(False, "La contraseña debe tener al menos un número", None)
    return Resultado(True, "", None)

def validar_campos_obligatorios(datos):
    """Valida que todos los campos requeridos estén presentes"""
    for campo, valor in datos.items():
        if not valor:
            return Resultado(False, f"El campo {campo} es obligatorio", None)
    return Resultado(True, "", None)

def verificar_duplicados(modelo, **filtros):
    """Verifica si existe un registro con los filtros dados"""
    return modelo.query.filter_by(**filtros).first() is not None

# -- Funcion para enviar email de verificacion -- #
def enviar_email_verificacion(correo, nombre_usuario, codigo):
    """Envía email de verificación con manejo de errores"""
    try:
        msg = Message("Verifica tu correo", recipients=[correo])
        msg.html = render_template("verify_email.html", 
                                    nombres=nombre_usuario, 
                                    codigo=codigo)
        mail.send(msg)
        app.logger.info(f"Email de verificación enviado a: {correo}")
        return Resultado(True, "", None)
    except Exception as e:
        log_error('ENVIO_EMAIL', e)
        return Resultado(False, str(e), None)

# -- Funcion para verificar codigo de verificacion -- #
def verificar_codigo_verificacion(codigo_ingresado, codigo_guardado, correo):
    """Verifica el código y actualiza el usuario si es correcto"""
    if codigo_ingresado != codigo_guardado:
        return Resultado(False, "Código incorrecto", None)
    
    usuario = Usuario.query.filter_by(email=correo).first()
    if not usuario:
        return Resultado(False, "Usuario no encontrado", None)
    
    if usuario.verificado:
        return Resultado(False, "El usuario ya está verificado", None)
    
    usuario.verificado = True
    db.session.commit()
    return Resultado(True, "Correo verificado exitosamente", usuario)

# -- Funciones helper para agenda -- #
def obtener_anotaciones(usuario_id):
    """Obtiene todas las anotaciones de un usuario ordenadas por fecha descendente"""
    return Agenda.query.filter_by(usuario_id=usuario_id).order_by(Agenda.fecha.desc()).all()

def obtener_anotacion_por_id(anotacion_id):
    """Obtiene una anotación por su ID o lanza 404"""
    return Agenda.query.get_or_404(anotacion_id)

def obtener_anotacion_por_fecha(usuario_id, fecha):
    """Obtiene una anotación específica por usuario y fecha"""
    return Agenda.query.filter_by(usuario_id=usuario_id, fecha=fecha).first()

def crear_anotacion(usuario_id, fecha, texto):
    """Crea una nueva anotación para un usuario"""
    nueva = Agenda(
        usuario_id=usuario_id,
        fecha=fecha,
        anotacion=texto
    )
    db.session.add(nueva)
    db.session.commit()
    return nueva

def actualizar_anotacion(anotacion, fecha, texto):
    """Actualiza una anotación existente"""
    anotacion.fecha = fecha
    anotacion.anotacion = texto
    anotacion.fecha_actualizacion = datetime.utcnow()
    db.session.commit()
    return anotacion

def eliminar_anotacion(anotacion):
    """Elimina una anotación"""
    db.session.delete(anotacion)
    db.session.commit()

# -- Decoradores para control de acceso -- #
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesion', 'error')
            log_seguridad('ACCESO_DENEGADO', 'Intento de acceso a ruta protegida', request.remote_addr)
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def log_request(f):
    """Decorador que loguea automáticamente la petición"""
    @wraps(f)
    def decorated(*args, **kwargs):
        app.logger.info(f"Petición: {request.method} {request.path} - IP: {request.remote_addr}")
        return f(*args, **kwargs)
    return decorated

# -- rutas principales -- #
@app.route('/')
@log_request
def index():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    return redirect(url_for('login'))

# -- registro de usuarios -- #
@app.route('/registrarse')
@log_request
def register_view():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    return render_template('register.html')

@app.route('/registrar', methods=['POST'])
@log_request
def registrar():
    # 01: obtener datos
    nombre_usuario = request.form.get('nombre_usuario', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')
    
    app.logger.info(f"Intento de registro - Usuario: {nombre_usuario}, Email: {correo}")
    
    # 02: validar campos obligatorios
    resultado = validar_campos_obligatorios({
        'nombre_usuario': nombre_usuario,
        'correo': correo,
        'password': password
    })
    if not resultado.exito:
        flash(resultado.mensaje, 'error')
        log_seguridad('REGISTRO_FALLIDO', f'{resultado.mensaje} - Email: {correo}')
        return redirect(url_for('register_view'))
    
    # 03: validar email
    if not validar_email(correo):
        flash('El correo no tiene un formato válido', 'error')
        return redirect(url_for('register_view'))
    
    # 04: validar contraseñas
    if password != password_confirm:
        flash('Las contraseñas no coinciden', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseñas no coinciden - Email: {correo}')
        return redirect(url_for('register_view'))
    
    resultado = validar_password(password)
    if not resultado.exito:
        flash(resultado.mensaje, 'error')
        log_seguridad('REGISTRO_FALLIDO', f'{resultado.mensaje} - Email: {correo}')
        return redirect(url_for('register_view'))
    
    # 05: verificar duplicados
    if verificar_duplicados(Usuario, email=correo):
        flash('Este correo ya está registrado', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Email duplicado: {correo}')
        return redirect(url_for('register_view'))
    
    if verificar_duplicados(Usuario, nombre_usuario=nombre_usuario):
        flash('Este nombre de usuario ya está en uso', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Usuario duplicado: {nombre_usuario}')
        return redirect(url_for('register_view'))
    
    # 06: crear usuario
    try:
        nuevo_usuario = Usuario(
            nombre_usuario=nombre_usuario,
            email=correo,
            password_hash=generate_password_hash(password),
            verificado=False
        )
        db.session.add(nuevo_usuario)
        db.session.flush()
        app.logger.info(f"Usuario creado en BD - ID: {nuevo_usuario.id}, Email: {correo}")
        
        # agenda inicial
        agenda_inicial = Agenda(
            usuario_id=nuevo_usuario.id,
            fecha=datetime.now().date(),
            anotacion="¡Bienvenido a tu agenda personal!"
        )
        db.session.add(agenda_inicial)
        app.logger.info(f"Agenda inicial creada para usuario ID: {nuevo_usuario.id}")
        
        # codigo de verificacion
        codigo = str(random.randint(100000, 999999))
        session.update({'correo_verificar': correo, 'codigo_verificacion': codigo})
        app.logger.info(f"Código de verificación generado para: {correo}")
        
        # enviar correo usando la función auxiliar
        resultado = enviar_email_verificacion(correo, nombre_usuario, codigo)
        if not resultado.exito:
            flash('No se pudo enviar el correo de verificación', 'warning')
        
        db.session.commit()
        log_seguridad('REGISTRO_EXITOSO', f'Usuario: {nombre_usuario}, Email: {correo}')
        flash(f'Registro exitoso. Código enviado a {correo}', 'success')
        return redirect(url_for('verify'))
        
    except Exception as e:
        db.session.rollback()
        log_error('REGISTRO_USUARIO', e)
        flash('Error en el registro', 'error')
        return redirect(url_for('register_view'))

# -- verificacion de correo -- #
@app.route('/verify', methods=['GET', 'POST'])
@log_request
def verify():
    if 'correo_verificar' not in session:
        flash('No hay proceso de verificación activo', 'error')
        log_seguridad('VERIFICACION_SIN_SESION', 'Intento de verificación sin sesión activa')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        codigo_ingresado = request.form.get('codigo', '')
        codigo_guardado = session.get('codigo_verificacion')
        correo = session.get('correo_verificar')
        
        app.logger.info(f"Intento de verificación - Email: {correo}")
        
        # Usar la función auxiliar para verificar el código
        resultado = verificar_codigo_verificacion(codigo_ingresado, codigo_guardado, correo)
        
        if resultado.exito:
            session.pop('correo_verificar', None)
            session.pop('codigo_verificacion', None)
            flash(resultado.mensaje, 'success')
            log_seguridad('VERIFICACION_EXITOSA', f'Email: {correo}')
            return redirect(url_for('login'))
        else:
            flash(resultado.mensaje, 'error')
            if resultado.mensaje == "Usuario no encontrado":
                return redirect(url_for('login'))
    return render_template('verify.html')

# -- autenticacion -- #
@app.route('/login', methods=['GET', 'POST'])
@log_request
def login():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip().lower()
        password = request.form.get('password', '')
        
        app.logger.info(f"Intento de login - Email: {correo}")
        
        key = f"login_{correo}_{request.remote_addr}"
        resultado = verificar_rate_limit(key)
        # Espera para nuevos intentos al logear.
        if not resultado.exito:
            flash(resultado.mensaje, 'error')
            log_seguridad('RATE_LIMIT', f'Email: {correo}, IP: {request.remote_addr}')
            return render_template('login.html')
        
        # Validar campos obligatorios
        resultado = validar_campos_obligatorios({
            'correo': correo,
            'password': password
        })
        if not resultado.exito:
            flash(resultado.mensaje, 'error')
            log_seguridad('LOGIN_FALLIDO', f'Campos vacíos - Email: {correo}')
            return render_template('login.html')
        
        # Validacion de email en login
        if not validar_email(correo):
            flash('El correo no tiene un formato válido', 'error')
            return render_template('login.html')
        
        try:
            usuario = Usuario.query.filter_by(email=correo).first()
            
            if not usuario:
                log_seguridad('LOGIN_FALLIDO', f'Usuario no existe - Email: {correo}')
                flash('Correo o contraseña incorrectos', 'error')
                return render_template('login.html')
            
            if not check_password_hash(usuario.password_hash, password):
                log_seguridad('LOGIN_FALLIDO', f'Contraseña incorrecta - Email: {correo}')
                flash('Correo o contraseña incorrectos', 'error')
                return render_template('login.html')
            
            if not usuario.verificado:
                log_seguridad('LOGIN_FALLIDO', f'Usuario no verificado - Email: {correo}')
                flash('Debes verificar tu correo primero', 'error')
                return redirect(url_for('verify'))
            
            # Login exitoso
            session.update({
                'user_id': usuario.id,
                'email': usuario.email,
                'nombre_usuario': usuario.nombre_usuario
            })
            
            log_seguridad('LOGIN_EXITOSO', f'Usuario: {usuario.nombre_usuario}, Email: {correo}')
            app.logger.info(f"Login exitoso - ID: {usuario.id}, Email: {correo}")
            session.permanent = True
            flash(f'Bienvenido, {usuario.nombre_usuario}!', 'success')
            return redirect(url_for('ver_agenda'))
            
        except Exception as e:
            log_error('LOGIN_USUARIO', e)
            flash('Error al iniciar sesión', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
@log_request
def logout():
    if 'user_id' in session:
        log_seguridad('LOGOUT', f'Usuario: {session.get("nombre_usuario")}, Email: {session.get("email")}')
        app.logger.info(f"Logout - Usuario ID: {session.get('user_id')}")
    session.clear()
    flash('Sesión cerrada', 'success')
    return redirect(url_for('login'))

# -- agenda personal -- #
@app.route('/agenda')
@login_required
@log_request
def ver_agenda():
    try:
        usuario_id = session['user_id']
        app.logger.info(f"Acceso a agenda - Usuario ID: {usuario_id}")
        
        # Usar función helper para obtener anotaciones
        anotaciones = obtener_anotaciones(usuario_id)
        app.logger.info(f"Anotaciones cargadas - Usuario ID: {usuario_id}, Total: {len(anotaciones)}")
        
        return render_template('agenda.html', anotaciones=anotaciones)
    except Exception as e:
        log_error('VER_AGENDA', e)
        flash('Error al cargar la agenda', 'error')
        return render_template('agenda.html', anotaciones=[])

@app.route('/agenda/crear', methods=['GET', 'POST'])
@login_required
@log_request
def crear_anotacion():
    if request.method == 'POST':
        fecha_str = request.form.get('fecha', '')
        anotacion = request.form.get('anotacion', '').strip()
        
        usuario_id = session['user_id']
        app.logger.info(f"Creando anotación - Usuario ID: {usuario_id}, Fecha: {fecha_str}")
        
        if not fecha_str:
            flash('La fecha es obligatoria', 'error')
            log_seguridad('CREAR_ANOTACION_FALLIDO', f'Fecha vacía - Usuario: {usuario_id}')
            return render_template('agenda_crear.html')
        if not anotacion:
            flash('La anotación no puede estar vacía', 'error')
            log_seguridad('CREAR_ANOTACION_FALLIDO', f'Anotación vacía - Usuario: {usuario_id}')
            return render_template('agenda_crear.html')
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # Verificar si ya existe anotación para esa fecha usando helper
            existente = obtener_anotacion_por_fecha(usuario_id, fecha)
            if existente:
                flash('Ya existe una anotación para esta fecha', 'warning')
                log_seguridad('CREAR_ANOTACION_FALLIDO', f'Anotación duplicada - Usuario: {usuario_id}, Fecha: {fecha}')
                return redirect(url_for('editar_anotacion', id=existente.id))
            
            # Crear anotación usando helper
            crear_anotacion(usuario_id, fecha, anotacion)
            
            app.logger.info(f"Anotación creada - Usuario: {usuario_id}, Fecha: {fecha}")
            log_seguridad('CREAR_ANOTACION', f'Usuario: {usuario_id}, Fecha: {fecha}')
            
            flash('Anotación creada', 'success')
            return redirect(url_for('ver_agenda'))
            
        except Exception as e:
            db.session.rollback()
            log_error('CREAR_ANOTACION', e)
            flash('Error al crear', 'error')
    
    return render_template('agenda_crear.html')

@app.route('/agenda/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@log_request
def editar_anotacion(id):
    try:
        # Obtener anotación usando helper
        anotacion = obtener_anotacion_por_id(id)
        usuario_id = session['user_id']
        
        if anotacion.usuario_id != usuario_id:
            flash('No tienes permiso', 'error')
            log_seguridad('EDITAR_ANOTACION_FALLIDO', f'Usuario sin permiso - Usuario: {usuario_id}, Anotacion: {id}')
            return redirect(url_for('ver_agenda'))
        
        if request.method == 'POST':
            fecha_str = request.form.get('fecha', '')
            nuevo_texto = request.form.get('anotacion', '').strip()
            
            app.logger.info(f"Editando anotación - ID: {id}, Usuario: {usuario_id}")
            
            if not fecha_str:
                flash('La fecha es obligatoria', 'error')
                return render_template('agenda_editar.html', anotacion=anotacion)
            if not nuevo_texto:
                flash('La anotación no puede estar vacía', 'error')
                return render_template('agenda_editar.html', anotacion=anotacion)
            
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                
                # Actualizar usando helper
                actualizar_anotacion(anotacion, fecha, nuevo_texto)
                
                app.logger.info(f"Anotación actualizada - ID: {id}, Usuario: {usuario_id}")
                log_seguridad('EDITAR_ANOTACION', f'Usuario: {usuario_id}, Anotacion: {id}')
                
                flash('Anotación actualizada', 'success')
                return redirect(url_for('ver_agenda'))
            except Exception as e:
                db.session.rollback()
                log_error('EDITAR_ANOTACION', e)
                flash('Error al actualizar', 'error')
        
        return render_template('agenda_editar.html', anotacion=anotacion)
        
    except Exception as e:
        log_error('EDITAR_ANOTACION_GET', e)
        flash('Error al cargar la anotación', 'error')
        return redirect(url_for('ver_agenda'))

@app.route('/agenda/eliminar/<int:id>')
@login_required
@log_request
def eliminar_anotacion(id):
    try:
        # Obtener anotación usando helper
        anotacion = obtener_anotacion_por_id(id)
        usuario_id = session['user_id']
        
        if anotacion.usuario_id != usuario_id:
            flash('No tienes permiso', 'error')
            log_seguridad('ELIMINAR_ANOTACION_FALLIDO', f'Usuario sin permiso - Usuario: {usuario_id}, Anotacion: {id}')
            return redirect(url_for('ver_agenda'))
        
        try:
            # Eliminar usando helper
            eliminar_anotacion(anotacion)
            
            app.logger.info(f"Anotación eliminada - ID: {id}, Usuario: {usuario_id}")
            log_seguridad('ELIMINAR_ANOTACION', f'Usuario: {usuario_id}, Anotacion: {id}')
            
            flash('Anotación eliminada', 'success')
        except Exception as e:
            db.session.rollback()
            log_error('ELIMINAR_ANOTACION', e)
            flash('Error al eliminar', 'error')
        
    except Exception as e:
        log_error('ELIMINAR_ANOTACION_GET', e)
        flash('Error al cargar la anotación', 'error')
    
    return redirect(url_for('ver_agenda'))

# -- funciones adicionales -- #
@app.route('/cambiar-tema', methods=['POST'])
@log_request
def cambiar_tema():
    modo = request.form.get('modo')
    resp = make_response(redirect(request.form.get('next', url_for('ver_agenda'))))
    resp.set_cookie('modo_claro', 'true' if modo == 'claro' else 'false', max_age=30*24*60*60)
    app.logger.info(f"Cambio de tema - Modo: {modo}, IP: {request.remote_addr}")
    return resp

# -- Manejadores de errores globales -- #
@app.errorhandler(404)
def not_found(error):
    app.logger.warning(f"Error 404 - Ruta no encontrada: {request.path} - IP: {request.remote_addr}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    log_error('ERROR_500', error)
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    log_error('ERROR_GENERAL', error)
    flash('Error interno del servidor', 'error')
    return redirect(url_for('login'))

# -- inicializacion -- #
with app.app_context():
    try:
        db.create_all()
        app.logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        app.logger.error(f"Error al inicializar la base de datos: {e}")

app.logger.info("=== APLICACION LISTA ===")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False") == "True" #Debug_mode
    app.logger.info(f"Iniciando servidor en puerto {port}, debug={debug_mode}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)