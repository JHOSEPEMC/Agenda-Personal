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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_por_defecto')
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# -- Configuracion de la app -- #
# 01: base de datos
app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db.init_app(app)
init_mail(app)

# -- Decoradores para control de acceso -- #
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesion', 'error')
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
    
    # 02: validaciones
    if not nombre_usuario:
        flash('Nombre de usuario obligatorio', 'error')
        return redirect(url_for('register_view'))
    if not correo:
        flash('Correo obligatorio', 'error')
        return redirect(url_for('register_view'))
    if not password:
        flash('Contraseña obligatoria', 'error')
        return redirect(url_for('register_view'))
    if password != password_confirm:
        flash('Las contraseñas no coinciden', 'error')
        return redirect(url_for('register_view'))
    if Usuario.query.filter_by(email=correo).first():
        flash('Este correo ya está registrado', 'error')
        return redirect(url_for('register_view'))
    if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
        flash('Este nombre de usuario ya está en uso', 'error')
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
        
        # agenda inicial
        agenda_inicial = Agenda(
            usuario_id=nuevo_usuario.id,
            fecha=datetime.now().date(),
            anotacion="¡Bienvenido a tu agenda personal!"
        )
        db.session.add(agenda_inicial)
        
        # codigo de verificacion
        codigo = str(random.randint(100000, 999999))
        session.update({'correo_verificar': correo, 'codigo_verificacion': codigo})
        
        # enviar correo
        try:
            msg = Message("Verifica tu correo", recipients=[correo])
            msg.html = render_template("verify_email.html", nombres=nombre_usuario, codigo=codigo)
            mail.send(msg)
        except:
            flash('No se pudo enviar el correo', 'warning')
        
        db.session.commit()
        flash(f'Registro exitoso. Código enviado a {correo}', 'success')
        return redirect(url_for('verify'))
    except:
        db.session.rollback()
        flash('Error en el registro', 'error')
        return redirect(url_for('register_view'))

# -- verificacion de correo -- #
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'correo_verificar' not in session:
        flash('No hay proceso de verificación activo', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if request.form.get('codigo') == session.get('codigo_verificacion'):
            usuario = Usuario.query.filter_by(email=session.get('correo_verificar')).first()
            if usuario:
                usuario.verificado = True
                db.session.commit()
            session.pop('correo_verificar', None)
            session.pop('codigo_verificacion', None)
            flash('Correo verificado! Ya puedes iniciar sesión', 'success')
            return redirect(url_for('login'))
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
        
        if not correo or not password:
            flash('Correo y contraseña son obligatorios', 'error')
            return render_template('login.html')
        
        usuario = Usuario.query.filter_by(email=correo).first()
        
        if not usuario or not check_password_hash(usuario.password_hash, password):
            flash('Correo o contraseña incorrectos', 'error')
            return render_template('login.html')
        
        if not usuario.verificado:
            flash('Debes verificar tu correo primero', 'error')
            return redirect(url_for('verify'))
        
        session.update({
            'user_id': usuario.id,
            'email': usuario.email,
            'nombre_usuario': usuario.nombre_usuario
        })
        flash(f'Bienvenido, {usuario.nombre_usuario}!', 'success')
        return redirect(url_for('ver_agenda'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'success')
    return redirect(url_for('login'))

# -- agenda personal -- #
@app.route('/agenda')
@login_required
def ver_agenda():
    anotaciones = Agenda.query.filter_by(usuario_id=session['user_id']).order_by(Agenda.fecha.desc()).all()
    return render_template('agenda.html', anotaciones=anotaciones)

@app.route('/agenda/crear', methods=['GET', 'POST'])
@login_required
def crear_anotacion():
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
            flash('Anotación creada', 'success')
            return redirect(url_for('ver_agenda'))
        except:
            db.session.rollback()
            flash('Error al crear', 'error')
    
    return render_template('agenda_crear.html')

@app.route('/agenda/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_anotacion(id):
    anotacion = Agenda.query.get_or_404(id)
    
    if anotacion.usuario_id != session['user_id']:
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
            anotacion.fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            anotacion.anotacion = nuevo_texto
            anotacion.fecha_actualizacion = datetime.utcnow()
            db.session.commit()
            flash('Anotación actualizada', 'success')
            return redirect(url_for('ver_agenda'))
        except:
            db.session.rollback()
            flash('Error al actualizar', 'error')
    
    return render_template('agenda_editar.html', anotacion=anotacion)

@app.route('/agenda/eliminar/<int:id>')
@login_required
def eliminar_anotacion(id):
    anotacion = Agenda.query.get_or_404(id)
    
    if anotacion.usuario_id != session['user_id']:
        flash('No tienes permiso', 'error')
        return redirect(url_for('ver_agenda'))
    
    try:
        db.session.delete(anotacion)
        db.session.commit()
        flash('Anotación eliminada', 'success')
    except:
        db.session.rollback()
        flash('Error al eliminar', 'error')
    
    return redirect(url_for('ver_agenda'))

# -- funciones adicionales -- #
@app.route('/cambiar-tema', methods=['POST'])
def cambiar_tema():
    modo = request.form.get('modo')
    resp = make_response(redirect(request.form.get('next', url_for('ver_agenda'))))
    resp.set_cookie('modo_claro', 'true' if modo == 'claro' else 'false', max_age=30*24*60*60)
    return resp

# -- inicializacion -- #
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)