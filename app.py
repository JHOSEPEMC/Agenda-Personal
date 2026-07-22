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
import re
from contextlib import contextmanager
from sqlalchemy import extract

# -- Constantes de configuracion -- #
SESSION_LIFETIME = 3600  # 1 hora
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300  # 5 minutos
PASSWORD_MIN_LENGTH = 8
CODIGO_VERIFICACION_LENGTH = 6
ANOTACIONES_POR_PAGINA = 10

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_por_defecto')
app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_LIFETIME

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# -- Configuracion de logging -- #
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler(
    os.path.join('logs', 'app.log'),
    maxBytes=10000,
    backupCount=3
)
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
app.logger.addHandler(console_handler)

def log_seguridad(evento, detalles, ip=None):
    if ip is None:
        ip = request.remote_addr if request else '0.0.0.0'
    app.logger.info(f"[SEGURIDAD] {evento} - {detalles} - IP: {ip}")

def log_error(evento, error, ip=None):
    if ip is None:
        ip = request.remote_addr if request else '0.0.0.0'
    app.logger.error(f"[ERROR] {evento} - {str(error)} - IP: {ip}")

app.logger.info("=== APLICACION INICIADA ===")

# -- Definir namedtuple para respuestas -- #
Resultado = namedtuple('Resultado', ['exito', 'mensaje', 'datos'])

# -- Configuracion de la app -- #
app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
init_mail(app)

# -- Context manager para transacciones -- #
@contextmanager
def transaccion():
    try:
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e

# -- Rate limiting en memoria (produccion usar Redis) -- #
intentos_login = defaultdict(list)

def verificar_rate_limit(key, limite=MAX_LOGIN_ATTEMPTS, ventana=LOGIN_WINDOW):
    ahora = datetime.now().timestamp()
    intentos_login[key] = [t for t in intentos_login[key] if ahora - t < ventana]
    
    if len(intentos_login[key]) >= limite:
        tiempo_restante = int(ventana - (ahora - intentos_login[key][0]))
        return Resultado(False, f'Demasiados intentos. Espera {tiempo_restante} segundos', None)
    
    intentos_login[key].append(ahora)
    return Resultado(True, '', None)

# -- Funciones de validacion -- #
def validar_email(email):
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

def validar_password(password, nombre_usuario=None):
    if len(password) < PASSWORD_MIN_LENGTH:
        return Resultado(False, f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres", None)
    if not any(c.isupper() for c in password):
        return Resultado(False, "La contraseña debe tener al menos una mayúscula", None)
    if not any(c.islower() for c in password):
        return Resultado(False, "La contraseña debe tener al menos una minúscula", None)
    if not any(c.isdigit() for c in password):
        return Resultado(False, "La contraseña debe tener al menos un número", None)
    if nombre_usuario and password.lower() == nombre_usuario.lower():
        return Resultado(False, "La contraseña no puede ser igual al nombre de usuario", None)
    return Resultado(True, "", None)

def validar_campos_obligatorios(datos):
    for campo, valor in datos.items():
        if not valor:
            return Resultado(False, f"El campo {campo} es obligatorio", None)
    return Resultado(True, "", None)

def verificar_duplicados(modelo, **filtros):
    return modelo.query.filter_by(**filtros).first() is not None

# -- Funcion para enviar email -- #
def enviar_email_verificacion(correo, nombre_usuario, codigo):
    try:
        msg = Message("Verifica tu correo", recipients=[correo])
        msg.html = render_template("verify_email.html", nombres=nombre_usuario, codigo=codigo)
        mail.send(msg)
        app.logger.info(f"Email de verificación enviado a: {correo}")
        return Resultado(True, "", None)
    except Exception as e:
        log_error('ENVIO_EMAIL', e)
        return Resultado(False, str(e), None)

# -- Funcion para verificar codigo -- #
def verificar_codigo_verificacion(codigo_ingresado, codigo_guardado, correo):
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
    return Agenda.query.filter_by(usuario_id=usuario_id).order_by(Agenda.fecha.desc()).all()

def obtener_anotacion_por_id(anotacion_id):
    return Agenda.query.get_or_404(anotacion_id)

def obtener_anotacion_por_fecha(usuario_id, fecha):
    return Agenda.query.filter_by(usuario_id=usuario_id, fecha=fecha).first()

def crear_anotacion(usuario_id, fecha, texto):
    nueva = Agenda(usuario_id=usuario_id, fecha=fecha, anotacion=texto)
    db.session.add(nueva)
    db.session.commit()
    return nueva

def actualizar_anotacion(anotacion, fecha, texto):
    anotacion.fecha = fecha
    anotacion.anotacion = texto
    anotacion.fecha_actualizacion = datetime.utcnow()
    db.session.commit()
    return anotacion

def eliminar_anotacion(anotacion):
    db.session.delete(anotacion)
    db.session.commit()

def obtener_anotaciones_paginadas(usuario_id, page=1, per_page=ANOTACIONES_POR_PAGINA):
    """Obtiene anotaciones paginadas"""
    return Agenda.query.filter_by(usuario_id=usuario_id)\
        .order_by(Agenda.fecha.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

def obtener_anotaciones_por_mes(usuario_id, mes, año):
    """Obtiene anotaciones filtradas por mes y año"""
    return Agenda.query.filter_by(usuario_id=usuario_id)\
        .filter(extract('month', Agenda.fecha) == mes)\
        .filter(extract('year', Agenda.fecha) == año)\
        .order_by(Agenda.fecha.desc()).all()

# -- Validacion de registro agrupada -- #
def validar_registro(nombre_usuario, correo, password, password_confirm):
    resultado = validar_campos_obligatorios({
        'nombre_usuario': nombre_usuario,
        'correo': correo,
        'password': password
    })
    if not resultado.exito:
        return resultado
    
    if not validar_email(correo):
        return Resultado(False, "El correo no tiene un formato válido", None)
    
    if password != password_confirm:
        return Resultado(False, "Las contraseñas no coinciden", None)
    
    resultado = validar_password(password, nombre_usuario)
    if not resultado.exito:
        return resultado
    
    if verificar_duplicados(Usuario, email=correo):
        return Resultado(False, "Este correo ya está registrado", None)
    
    if verificar_duplicados(Usuario, nombre_usuario=nombre_usuario):
        return Resultado(False, "Este nombre de usuario ya está en uso", None)
    
    return Resultado(True, "", None)

# -- Decoradores -- #
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
    @wraps(f)
    def decorated(*args, **kwargs):
        app.logger.info(f"Petición: {request.method} {request.path} - IP: {request.remote_addr}")
        return f(*args, **kwargs)
    return decorated

# -- Rutas principales -- #
@app.route('/')
@log_request
def index():
    return redirect(url_for('ver_agenda')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/registrarse')
@log_request
def register_view():
    return redirect(url_for('ver_agenda')) if 'user_id' in session else render_template('register.html')

@app.route('/registrar', methods=['POST'])
@log_request
def registrar():
    nombre_usuario = request.form.get('nombre_usuario', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')
    
    app.logger.info(f"Intento de registro - Usuario: {nombre_usuario}, Email: {correo}")
    
    resultado = validar_registro(nombre_usuario, correo, password, password_confirm)
    if not resultado.exito:
        flash(resultado.mensaje, 'error')
        log_seguridad('REGISTRO_FALLIDO', f'{resultado.mensaje} - Email: {correo}')
        return redirect(url_for('register_view'))
    
    try:
        with transaccion():
            nuevo_usuario = Usuario(
                nombre_usuario=nombre_usuario,
                email=correo,
                password_hash=generate_password_hash(password),
                verificado=False
            )
            db.session.add(nuevo_usuario)
            db.session.flush()
            
            agenda_inicial = Agenda(
                usuario_id=nuevo_usuario.id,
                fecha=datetime.now().date(),
                anotacion="¡Bienvenido a tu agenda personal!"
            )
            db.session.add(agenda_inicial)
            
            codigo = str(random.randint(100000, 999999))
            session.update({'correo_verificar': correo, 'codigo_verificacion': codigo})
            
            resultado_email = enviar_email_verificacion(correo, nombre_usuario, codigo)
            if not resultado_email.exito:
                flash('No se pudo enviar el correo de verificación', 'warning')
        
        log_seguridad('REGISTRO_EXITOSO', f'Usuario: {nombre_usuario}, Email: {correo}')
        flash(f'Registro exitoso. Código enviado a {correo}', 'success')
        return redirect(url_for('verify'))
        
    except Exception as e:
        log_error('REGISTRO_USUARIO', e)
        flash('Error en el registro', 'error')
        return redirect(url_for('register_view'))

@app.route('/verify', methods=['GET', 'POST'])
@log_request
def verify():
    if 'correo_verificar' not in session:
        flash('No hay proceso de verificación activo', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        codigo_ingresado = request.form.get('codigo', '')
        codigo_guardado = session.get('codigo_verificacion')
        correo = session.get('correo_verificar')
        
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

@app.route('/reenviar-codigo')
@log_request
def reenviar_codigo():
    correo = session.get('correo_verificar')
    if not correo:
        flash('No hay proceso de verificación activo', 'error')
        return redirect(url_for('login'))
    
    usuario = Usuario.query.filter_by(email=correo).first()
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('login'))
    
    if usuario.verificado:
        flash('El usuario ya está verificado', 'info')
        session.pop('correo_verificar', None)
        session.pop('codigo_verificacion', None)
        return redirect(url_for('login'))
    
    # Generar nuevo código
    codigo = str(random.randint(100000, 999999))
    session['codigo_verificacion'] = codigo
    
    # Enviar nuevo email
    resultado = enviar_email_verificacion(correo, usuario.nombre_usuario, codigo)
    if resultado.exito:
        flash('Nuevo código enviado a tu correo', 'success')
    else:
        flash('Error al enviar el código. Intenta nuevamente.', 'error')
    
    return redirect(url_for('verify'))

@app.route('/login', methods=['GET', 'POST'])
@log_request
def login():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip().lower()
        password = request.form.get('password', '')
        
        resultado_rate = verificar_rate_limit(f"login_{correo}_{request.remote_addr}")
        if not resultado_rate.exito:
            flash(resultado_rate.mensaje, 'error')
            return render_template('login.html')
        
        resultado_campos = validar_campos_obligatorios({'correo': correo, 'password': password})
        if not resultado_campos.exito:
            flash(resultado_campos.mensaje, 'error')
            return render_template('login.html')
        
        if not validar_email(correo):
            flash('El correo no tiene un formato válido', 'error')
            return render_template('login.html')
        
        try:
            usuario = Usuario.query.filter_by(email=correo).first()
            
            if not usuario or not check_password_hash(usuario.password_hash, password):
                log_seguridad('LOGIN_FALLIDO', f'Credenciales incorrectas - Email: {correo}')
                flash('Correo o contraseña incorrectos', 'error')
                return render_template('login.html')
            
            if not usuario.verificado:
                log_seguridad('LOGIN_FALLIDO', f'Usuario no verificado - Email: {correo}')
                flash('Debes verificar tu correo primero', 'error')
                return redirect(url_for('verify'))
            
            session.update({
                'user_id': usuario.id,
                'email': usuario.email,
                'nombre_usuario': usuario.nombre_usuario
            })
            session.permanent = True
            
            log_seguridad('LOGIN_EXITOSO', f'Usuario: {usuario.nombre_usuario}, Email: {correo}')
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
    session.clear()
    flash('Sesión cerrada', 'success')
    return redirect(url_for('login'))

# -- Agenda -- #
@app.route('/agenda')
@login_required
@log_request
def ver_agenda():
    try:
        usuario_id = session['user_id']
        
        # Obtener parámetros de filtro
        mes = request.args.get('mes', type=int)
        año = request.args.get('año', type=int)
        page = request.args.get('page', 1, type=int)
        
        if mes and año:
            # Filtrar por mes/año
            anotaciones = obtener_anotaciones_por_mes(usuario_id, mes, año)
            pagination = None
        else:
            # Paginación normal
            pagination = obtener_anotaciones_paginadas(usuario_id, page)
            anotaciones = pagination.items
        
        # Obtener meses disponibles para el filtro
        meses_disponibles = db.session.query(
            extract('year', Agenda.fecha).label('año'),
            extract('month', Agenda.fecha).label('mes')
        ).filter_by(usuario_id=usuario_id)\
         .group_by('año', 'mes')\
         .order_by('año', 'mes').all()
        
        return render_template('agenda.html', 
                             anotaciones=anotaciones,
                             pagination=pagination,
                             mes_actual=mes,
                             año_actual=año,
                             meses_disponibles=meses_disponibles)
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
        
        if not fecha_str:
            flash('La fecha es obligatoria', 'error')
            return render_template('agenda_crear.html')
        if not anotacion:
            flash('La anotación no puede estar vacía', 'error')
            return render_template('agenda_crear.html')
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # Validar que no sea fecha futura
            if fecha > datetime.now().date():
                flash('No puedes crear anotaciones en el futuro', 'error')
                return render_template('agenda_crear.html')
            
            existente = obtener_anotacion_por_fecha(usuario_id, fecha)
            if existente:
                flash('Ya existe una anotación para esta fecha', 'warning')
                return redirect(url_for('editar_anotacion', id=existente.id))
            
            with transaccion():
                crear_anotacion(usuario_id, fecha, anotacion)
            
            flash('Anotación creada', 'success')
            return redirect(url_for('ver_agenda'))
            
        except Exception as e:
            log_error('CREAR_ANOTACION', e)
            flash('Error al crear', 'error')
    
    return render_template('agenda_crear.html')

@app.route('/agenda/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@log_request
def editar_anotacion(id):
    try:
        anotacion = obtener_anotacion_por_id(id)
        usuario_id = session['user_id']
        
        if anotacion.usuario_id != usuario_id:
            flash('No tienes permiso', 'error')
            return redirect(url_for('ver_agenda'))
        
        if request.method == 'POST':
            fecha_str = request.form.get('fecha', '')
            nuevo_texto = request.form.get('anotacion', '').strip()
            
            if not fecha_str:
                flash('La fecha es obligatoria', 'error')
                return render_template('agenda_editar.html', anotacion=anotacion)
            if not nuevo_texto:
                flash('La anotación no puede estar vacía', 'error')
                return render_template('agenda_editar.html', anotacion=anotacion)
            
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                
                # Validar que no sea fecha futura
                if fecha > datetime.now().date():
                    flash('No puedes poner una fecha futura', 'error')
                    return render_template('agenda_editar.html', anotacion=anotacion)
                
                with transaccion():
                    actualizar_anotacion(anotacion, fecha, nuevo_texto)
                
                flash('Anotación actualizada', 'success')
                return redirect(url_for('ver_agenda'))
            except Exception as e:
                log_error('EDITAR_ANOTACION', e)
                flash('Error al actualizar', 'error')
        
        return render_template('agenda_editar.html', anotacion=anotacion)
        
    except Exception as e:
        log_error('EDITAR_ANOTACION_GET', e)
        flash('Error al cargar la anotación', 'error')
        return redirect(url_for('ver_agenda'))

@app.route('/agenda/eliminar/<int:id>', methods=['POST'])
@login_required
@log_request
def eliminar_anotacion(id):
    try:
        anotacion = obtener_anotacion_por_id(id)
        usuario_id = session['user_id']
        
        if anotacion.usuario_id != usuario_id:
            flash('No tienes permiso', 'error')
            return redirect(url_for('ver_agenda'))
        
        with transaccion():
            eliminar_anotacion(anotacion)
        
        flash('Anotación eliminada', 'success')
        
    except Exception as e:
        log_error('ELIMINAR_ANOTACION', e)
        flash('Error al eliminar', 'error')
    
    return redirect(url_for('ver_agenda'))

# -- Funciones adicionales -- #
@app.route('/cambiar-tema', methods=['POST'])
@log_request
def cambiar_tema():
    modo = request.form.get('modo')
    resp = make_response(redirect(request.form.get('next', url_for('ver_agenda'))))
    resp.set_cookie('modo_claro', 'true' if modo == 'claro' else 'false', max_age=30*24*60*60)
    return resp

# -- Manejadores de errores -- #
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

# -- Inicializacion -- #
with app.app_context():
    try:
        db.create_all()
        app.logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        app.logger.error(f"Error al inicializar la base de datos: {e}")

app.logger.info("=== APLICACION LISTA ===")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False") == "True"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)