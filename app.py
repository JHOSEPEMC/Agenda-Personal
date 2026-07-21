# -- Configuracion inicial de la aplicacion -- #
# 01: importar librerias
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Agenda
from datetime import datetime
from flask_mail import Message
import random, os
from config_mail import init_mail, mail
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import re #Para una mejor validacion de email.

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_por_defecto')
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

# -- Configuracion de la app -- #
# 01: base de datos
app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
init_mail(app)

# -- Funcion de mejor validacion de email.
def validar_email(email):
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

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

# -- rutas principales -- #
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    return redirect(url_for('login'))

# -- registro de usuarios -- #
@app.route('/registrarse')
def register_view():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    return render_template('register.html')

@app.route('/registrar', methods=['POST'])
def registrar():
    # 01: obtener datos
    nombre_usuario = request.form.get('nombre_usuario', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')
    
    app.logger.info(f"Intento de registro - Usuario: {nombre_usuario}, Email: {correo}")
    
    # 02: validaciones
    if not nombre_usuario:
        flash('Nombre de usuario obligatorio', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Nombre de usuario vacio - Email: {correo}')
        return redirect(url_for('register_view'))
    if not correo:
        flash('Correo obligatorio', 'error')
        log_seguridad('REGISTRO_FALLIDO', 'Correo vacio')
        return redirect(url_for('register_view'))
    if not validar_email(correo):
        flash('El correo no tiene un formato válido', 'error')
        return redirect(url_for('register_view'))
    if not password:
        flash('Contraseña obligatoria', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseña vacia - Email: {correo}')
        return redirect(url_for('register_view'))
    if password != password_confirm:
        flash('Las contraseñas no coinciden', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseñas no coinciden - Email: {correo}')
        return redirect(url_for('register_view'))
    if len(password) < 8:
        flash('La contraseña debe tener al menos 8 caracteres', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseña muy corta - Email: {correo}')
        return redirect(url_for('register_view'))
    if not any(c.isupper() for c in password):
        flash('La contraseña debe tener al menos una mayúscula', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseña sin mayúscula - Email: {correo}')
        return redirect(url_for('register_view'))
    if not any(c.islower() for c in password):
        flash('La contraseña debe tener al menos una minúscula', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseña sin minúscula - Email: {correo}')
        return redirect(url_for('register_view'))
    if not any(c.isdigit() for c in password):
        flash('La contraseña debe tener al menos un número', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Contraseña sin número - Email: {correo}')
        return redirect(url_for('register_view'))
    
    # Validar email duplicado
    if Usuario.query.filter_by(email=correo).first():
        flash('Este correo ya está registrado', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Email duplicado: {correo}')
        return redirect(url_for('register_view'))
    if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
        flash('Este nombre de usuario ya está en uso', 'error')
        log_seguridad('REGISTRO_FALLIDO', f'Usuario duplicado: {nombre_usuario}')
        return redirect(url_for('register_view'))
    
    # 03: crear usuario
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
        
        # enviar correo
        try:
            msg = Message("Verifica tu correo", recipients=[correo])
            msg.html = render_template("verify_email.html", nombres=nombre_usuario, codigo=codigo)
            mail.send(msg)
            app.logger.info(f"Email de verificación enviado a: {correo}")
        except Exception as e:
            log_error('ENVIO_EMAIL', e)
            flash('No se pudo enviar el correo', 'warning')
        
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
        
        if codigo_ingresado == codigo_guardado:
            try:
                usuario = Usuario.query.filter_by(email=correo).first()
                if usuario:
                    usuario.verificado = True
                    db.session.commit()
                    app.logger.info(f"Usuario verificado - ID: {usuario.id}, Email: {correo}")
                    log_seguridad('VERIFICACION_EXITOSA', f'Email: {correo}')
                else:
                    app.logger.warning(f"Usuario no encontrado en verificación - Email: {correo}")
                    flash('Usuario no encontrado', 'error')
                    return redirect(url_for('login'))
                
                session.pop('correo_verificar', None)
                session.pop('codigo_verificacion', None)
                flash('Correo verificado! Ya puedes iniciar sesión', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                log_error('VERIFICACION_USUARIO', e)
                flash('Error al verificar', 'error')
        else:
            app.logger.warning(f"Código incorrecto para verificación - Email: {correo}")
            log_seguridad('VERIFICACION_FALLIDA', f'Código incorrecto - Email: {correo}')
            flash('Código incorrecto', 'error')
    
    return render_template('verify.html')

# -- autenticacion -- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip().lower()
        password = request.form.get('password', '')
        
        app.logger.info(f"Intento de login - Email: {correo}")
        
        if not correo or not password:
            flash('Correo y contraseña son obligatorios', 'error')
            log_seguridad('LOGIN_FALLIDO', f'Campos vacíos - Email: {correo}')
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
            
            flash(f'Bienvenido, {usuario.nombre_usuario}!', 'success')
            return redirect(url_for('ver_agenda'))
            
        except Exception as e:
            log_error('LOGIN_USUARIO', e)
            flash('Error al iniciar sesión', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
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
def ver_agenda():
    try:
        usuario_id = session['user_id']
        app.logger.info(f"Acceso a agenda - Usuario ID: {usuario_id}")
        
        anotaciones = Agenda.query.filter_by(usuario_id=usuario_id).order_by(Agenda.fecha.desc()).all()
        app.logger.info(f"Anotaciones cargadas - Usuario ID: {usuario_id}, Total: {len(anotaciones)}")
        
        return render_template('agenda.html', anotaciones=anotaciones)
    except Exception as e:
        log_error('VER_AGENDA', e)
        flash('Error al cargar la agenda', 'error')
        return render_template('agenda.html', anotaciones=[])

@app.route('/agenda/crear', methods=['GET', 'POST'])
@login_required
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
            
            # Verificar si ya existe anotación para esa fecha
            existente = Agenda.query.filter_by(usuario_id=usuario_id, fecha=fecha).first()
            if existente:
                flash('Ya existe una anotación para esta fecha', 'warning')
                log_seguridad('CREAR_ANOTACION_FALLIDO', f'Anotación duplicada - Usuario: {usuario_id}, Fecha: {fecha}')
                return redirect(url_for('editar_anotacion', id=existente.id))
            
            nueva_anotacion = Agenda(
                usuario_id=usuario_id,
                fecha=fecha,
                anotacion=anotacion
            )
            db.session.add(nueva_anotacion)
            db.session.commit()
            
            app.logger.info(f"Anotación creada - ID: {nueva_anotacion.id}, Usuario: {usuario_id}, Fecha: {fecha}")
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
def editar_anotacion(id):
    try:
        anotacion = Agenda.query.get_or_404(id)
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
                anotacion.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                anotacion.anotacion = nuevo_texto
                anotacion.fecha_actualizacion = datetime.utcnow()
                db.session.commit()
                
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
def eliminar_anotacion(id):
    try:
        anotacion = Agenda.query.get_or_404(id)
        usuario_id = session['user_id']
        
        if anotacion.usuario_id != usuario_id:
            flash('No tienes permiso', 'error')
            log_seguridad('ELIMINAR_ANOTACION_FALLIDO', f'Usuario sin permiso - Usuario: {usuario_id}, Anotacion: {id}')
            return redirect(url_for('ver_agenda'))
        
        try:
            db.session.delete(anotacion)
            db.session.commit()
            
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
    debug_mode = os.environ.get("FLASK_DEBUG", "True") == "True"
    app.logger.info(f"Iniciando servidor en puerto {port}, debug={debug_mode}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)