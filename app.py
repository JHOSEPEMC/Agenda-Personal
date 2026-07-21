# -- Configuracion inicial de la aplicacion -- #
# 01: importar librerias
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash  # para manejo de contraseñas
from models import db, Usuario, Agenda #Modelo nuevo, "agenda"
from datetime import datetime
from flask_mail import Message
import random, os
from config_mail import init_mail, mail
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']  # clave secreta desde variables de entorno
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
# 01: requiere que el usuario este logueado
def login_required(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        if 'user_id' not in session: flash('Debes iniciar sesión','error'); return redirect(url_for('login'))
        return f(*args,**kwargs)
    return decorated

# -- funciones auxiliares -- #
# 01: valida que el dni tenga 8 digitos
''' def validar_dni(dni): return len(dni)==8 and dni.isdigit() ''' #quitando validar dni

# -- rutas principales -- #
@app.route('/')
def index():
    return redirect(url_for('login') if 'user_id' in session else url_for('register_view'))

@app.route('/registrarse')
def register_view():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return render_template('register.html')

# -- registro de usuarios ya registrados -- #
# 01: procesa el formulario de registro
@app.route('/postular',methods=['POST'])
def postular():
    datos={k:request.form.get(k,'').strip() for k in ['nombres','correo','password']}
    datos['correo']=datos['correo'].lower()
    
    # validaciones basicas
    if not all(datos.values()): flash('Todos los campos son obligatorios','error'); return redirect(url_for('register_view'))
    if request.form.get('password')!=request.form.get('password_confirm'): flash('Las contraseñas no coinciden','error'); return redirect(url_for('register_view'))
    #if not validar_dni(datos['dni']): flash('El DNI debe tener 8 dígitos','error'); return redirect(url_for('register_view'))
    if Usuario.query.filter_by(email=datos['correo']).first(): flash('El correo ya está registrado','error'); return redirect(url_for('register_view'))
    
    try:
        # crea usuario y postulante
        nuevo_usuario=Usuario(email=datos['correo'],password_hash=generate_password_hash(datos['password']),tipo='postulante',verificado=False)
        db.session.add(nuevo_usuario); db.session.flush()
        
        nueva_agenda=Agenda(
            usuario_id=nuevo_usuario.id,
            nombres=datos['nombres'],
            apellidos=datos['apellidos'],
            fecha_nacimiento=datetime.strptime(datos['fecha_nacimiento'],'%Y-%m-%d').date(),
            #dni=datos['dni'],
            estado='pendiente'
        )
        db.session.add(nueva_agenda)
        
        # genera codigo de verificacion y guarda en session
        codigo=str(random.randint(100000,999999))
        session.update({'correo_verificar':datos['correo'],'codigo_verificacion':codigo})
        
        # envia correo de verificacion
        try:
            msg=Message("Verifica tu correo en App Iestpoxapampa",recipients=[datos['correo']])
            msg.html=render_template("verify_email.html",nombres=datos['nombres'],codigo=codigo); mail.send(msg)
        except: pass  # si falla el envio continua igual
        
        db.session.commit()
        flash(f'Registro exitoso. Código enviado a {datos["correo"]}','success')
        return redirect(url_for('verify'))
    except:
        db.session.rollback(); flash('Error en el registro','error'); return redirect(url_for('register_view'))

# -- autenticacion -- #
@app.route('/login',methods=['GET','POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method=='POST':
        usuario=Usuario.query.filter_by(email=request.form.get('correo','').strip().lower()).first()
        if not usuario or not check_password_hash(usuario.password_hash,request.form.get('password','')):
            flash('Correo o contraseña incorrectos','error')
        elif usuario.tipo=='postulante' and not usuario.verificado:
            flash('Debes verificar tu correo primero','error'); return redirect(url_for('verify'))
        else:
            session.update({'user_id':usuario.id,'email':usuario.email,'tipo_usuario':usuario.tipo})
            flash('Bienvenido!','success')
            return redirect(url_for('dashboard'))
    return render_template('login.html')

# -- verificacion de correo -- #
@app.route('/verify',methods=['GET','POST'])
def verify():
    if request.method=='POST':
        if request.form.get('codigo')==session.get('codigo_verificacion'):
            if usuario:=Usuario.query.filter_by(email=session.get('correo_verificar')).first():
                usuario.verificado=True; db.session.commit()
            session.pop('correo_verificar',None); session.pop('codigo_verificacion',None)
            flash('Correo verificado! Ya puedes iniciar sesión','success'); return redirect(url_for('login'))
        flash('Código incorrecto','error')
    return render_template('verify.html')

@app.route('/logout')
def logout():
    session.clear(); flash('Sesión cerrada','success'); return redirect(url_for('login'))

# -- area de usuarios -- #
@app.route('/agenda')
@login_required
def dashboard():
    _agenda=Agenda.query.filter_by(usuario_id=session['user_id']).first()
    return render_template('agenda.html', _agenda=_agenda)

# -- funciones adicionales -- #
@app.route('/cambiar-tema', methods=['POST'])
def cambiar_tema():
    modo = request.form.get('modo')
    resp = make_response(redirect(request.form.get('next', url_for('index'))))
    resp.set_cookie('modo_claro', 'true' if modo == 'claro' else 'false', max_age=30*24*60*60)  # cookie por 30 dias
    return resp

# -- inicializacion -- #
with app.app_context(): db.create_all()  # crea tablas si no existen
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port, debug=True)