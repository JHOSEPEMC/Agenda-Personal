# 01: Importar librerías
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Agenda
from datetime import datetime
from flask_mail import Message
import random
import os
from config_mail import init_mail, mail
from functools import wraps

# ================================================
# CREAR LA APLICACIÓN FLASK
# ================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_por_defecto')
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ================================================

app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
init_mail(app)

# ================================================
# DECORADORES PARA CONTROL DE ACCESO
# ================================================

def login_required(f):
    """Decorador: requiere que el usuario esté logueado"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ================================================
# RUTAS PRINCIPALES
# ================================================

@app.route('/')
def index():
    """Página principal: redirige según estado de sesión"""
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    return redirect(url_for('login'))

# ================================================
# REGISTRO DE USUARIOS
# ================================================

@app.route('/registrarse')
def register_view():
    """Muestra el formulario de registro"""
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    return render_template('register.html')

@app.route('/registrar', methods=['POST'])
def registrar():
    """Procesa el registro de un nuevo usuario"""
    
    # 01: Obtener datos del formulario
    nombre_usuario = request.form.get('nombre_usuario', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')
    
    # 02: Validar campos obligatorios
    if not nombre_usuario:
        flash('El nombre de usuario es obligatorio', 'error')
        return redirect(url_for('register_view'))
    
    if not correo:
        flash('El correo electrónico es obligatorio', 'error')
        return redirect(url_for('register_view'))
    
    if not password:
        flash('La contraseña es obligatoria', 'error')
        return redirect(url_for('register_view'))
    
    # 03: Validar que las contraseñas coincidan
    if password != password_confirm:
        flash('Las contraseñas no coinciden', 'error')
        return redirect(url_for('register_view'))
    
    # 04: Validar que el correo no esté registrado
    if Usuario.query.filter_by(email=correo).first():
        flash('Este correo ya está registrado', 'error')
        return redirect(url_for('register_view'))
    
    # 05: Validar que el nombre de usuario no esté registrado
    if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
        flash('Este nombre de usuario ya está en uso', 'error')
        return redirect(url_for('register_view'))
    
    # 06: Crear el nuevo usuario
    try:
        nuevo_usuario = Usuario(
            nombre_usuario=nombre_usuario,
            email=correo,
            password_hash=generate_password_hash(password),
            verificado=False
        )
        db.session.add(nuevo_usuario)
        db.session.flush()  # Para obtener el ID del usuario
        
        # 07: Crear una agenda inicial para el usuario
        agenda_inicial = Agenda(
            usuario_id=nuevo_usuario.id,
            fecha=datetime.now().date(),
            anotacion="¡Bienvenido a tu agenda personal! Aquí puedes guardar tus notas."
        )
        db.session.add(agenda_inicial)
        
        # 08: Generar código de verificación
        codigo = str(random.randint(100000, 999999))
        session['correo_verificar'] = correo
        session['codigo_verificacion'] = codigo
        
        # 09: Enviar correo de verificación
        try:
            msg = Message(
                "Verifica tu correo - Agenda Personal",
                recipients=[correo]
            )
            msg.html = render_template(
                "verify_email.html",
                nombres=nombre_usuario,
                codigo=codigo
            )
            mail.send(msg)
        except Exception as e:
            # Si falla el envío, continuamos igual (pero mostramos un aviso)
            flash('No se pudo enviar el correo de verificación, pero puedes continuar', 'warning')
        
        # 10: Guardar todo en la base de datos
        db.session.commit()
        
        flash(f'¡Registro exitoso! Se envió un código de verificación a {correo}', 'success')
        return redirect(url_for('verify'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar usuario: {str(e)}', 'error')
        return redirect(url_for('register_view'))

# ================================================
# VERIFICACIÓN DE CORREO
# ================================================

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    """Verifica el código enviado al correo"""
    
    # Si ya está verificado o no hay correo en sesión, redirigir
    if 'correo_verificar' not in session:
        flash('No hay proceso de verificación activo', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        codigo_ingresado = request.form.get('codigo', '').strip()
        codigo_esperado = session.get('codigo_verificacion')
        
        if codigo_ingresado == codigo_esperado:
            # Verificar al usuario
            correo = session.get('correo_verificar')
            usuario = Usuario.query.filter_by(email=correo).first()
            
            if usuario:
                usuario.verificado = True
                db.session.commit()
                flash('¡Correo verificado exitosamente! Ya puedes iniciar sesión', 'success')
            else:
                flash('Usuario no encontrado', 'error')
            
            # Limpiar sesión
            session.pop('correo_verificar', None)
            session.pop('codigo_verificacion', None)
            return redirect(url_for('login'))
        else:
            flash('Código de verificación incorrecto. Intenta nuevamente.', 'error')
    
    return render_template('verify.html')

# ================================================
# INICIO DE SESIÓN
# ================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión de usuarios"""
    
    if 'user_id' in session:
        return redirect(url_for('ver_agenda'))
    
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip().lower()
        password = request.form.get('password', '')
        
        if not correo or not password:
            flash('Correo y contraseña son obligatorios', 'error')
            return render_template('login.html')
        
        # Buscar usuario por correo
        usuario = Usuario.query.filter_by(email=correo).first()
        
        if not usuario:
            flash('Correo o contraseña incorrectos', 'error')
            return render_template('login.html')
        
        if not check_password_hash(usuario.password_hash, password):
            flash('Correo o contraseña incorrectos', 'error')
            return render_template('login.html')
        
        if not usuario.verificado:
            flash('Debes verificar tu correo primero. Revisa tu bandeja de entrada.', 'error')
            return redirect(url_for('verify'))
        
        # Iniciar sesión
        session['user_id'] = usuario.id
        session['email'] = usuario.email
        session['nombre_usuario'] = usuario.nombre_usuario
        
        flash(f'¡Bienvenido, {usuario.nombre_usuario}!', 'success')
        return redirect(url_for('ver_agenda'))
    
    return render_template('login.html')

# ================================================
# CERRAR SESIÓN
# ================================================

@app.route('/logout')
def logout():
    """Cierra la sesión del usuario"""
    session.clear()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('login'))

# ================================================
# AGENDA PERSONAL
# ================================================

@app.route('/agenda')
@login_required
def ver_agenda():
    """Muestra todas las anotaciones de la agenda del usuario"""
    
    usuario_id = session['user_id']
    anotaciones = Agenda.query.filter_by(usuario_id=usuario_id).order_by(Agenda.fecha.desc()).all()
    
    return render_template('agenda.html', anotaciones=anotaciones)

@app.route('/agenda/crear', methods=['GET', 'POST'])
@login_required
def crear_anotacion():
    """Crea una nueva anotación en la agenda"""
    
    if request.method == 'POST':
        fecha_str = request.form.get('fecha', '')
        anotacion = request.form.get('anotacion', '').strip()
        
        if not fecha_str:
            flash('La fecha es obligatoria', 'error')
            return render_template('agenda_crear.html')
        
        if not anotacion:
            flash('La anotación no puede estar vacía', 'error')
            return render_template('agenda_crear.html')
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            nueva_anotacion = Agenda(
                usuario_id=session['user_id'],
                fecha=fecha,
                anotacion=anotacion
            )
            
            db.session.add(nueva_anotacion)
            db.session.commit()
            
            flash('Anotación creada exitosamente', 'success')
            return redirect(url_for('ver_agenda'))
            
        except ValueError:
            flash('Formato de fecha inválido', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la anotación: {str(e)}', 'error')
    
    return render_template('agenda_crear.html')

@app.route('/agenda/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_anotacion(id):
    """Edita una anotación existente"""
    
    anotacion = Agenda.query.get_or_404(id)
    
    # Verificar que la anotación pertenece al usuario
    if anotacion.usuario_id != session['user_id']:
        flash('No tienes permiso para editar esta anotación', 'error')
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
            
            anotacion.fecha = fecha
            anotacion.anotacion = nuevo_texto
            anotacion.fecha_actualizacion = datetime.utcnow()
            
            db.session.commit()
            
            flash('Anotación actualizada exitosamente', 'success')
            return redirect(url_for('ver_agenda'))
            
        except ValueError:
            flash('Formato de fecha inválido', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    return render_template('agenda_editar.html', anotacion=anotacion)

@app.route('/agenda/eliminar/<int:id>')
@login_required
def eliminar_anotacion(id):
    """Elimina una anotación"""
    
    anotacion = Agenda.query.get_or_404(id)
    
    # Verificar que la anotación pertenece al usuario
    if anotacion.usuario_id != session['user_id']:
        flash('No tienes permiso para eliminar esta anotación', 'error')
        return redirect(url_for('ver_agenda'))
    
    try:
        db.session.delete(anotacion)
        db.session.commit()
        flash('Anotación eliminada correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('ver_agenda'))

# ================================================
# CAMBIAR TEMA (CLARO/OSCURO)
# ================================================

@app.route('/cambiar-tema', methods=['POST'])
def cambiar_tema():
    """Cambia el tema de la interfaz (claro/oscuro)"""
    
    modo = request.form.get('modo')
    resp = make_response(redirect(request.form.get('next', url_for('ver_agenda'))))
    resp.set_cookie('modo_claro', 'true' if modo == 'claro' else 'false', max_age=30*24*60*60)
    return resp

# ================================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ================================================

with app.app_context():
    db.create_all()  # Crea las tablas si no existen

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
    