# Sistema de Agenda Personal e Interacción Multiusuario (Flask)

Este proyecto es una aplicación web desarrollada con Flask diseñada para la realización de una agenda personal, provista de un sistema seguro de inicio de sesión, verificación por correo electrónico, adaptabilidad visual mediante temas e interacción personal privada para los usuarios del Instituto de Educación Superior Tecnológico Público Oxapampa.

---

## 🛠️ GUÍA PARA DESARROLLADORES (Backend & Arquitectura)

Esta sección detalla los componentes lógicos desarrollados en el Backend del sistema para su correcto despliegue, mantenimiento y extensión por parte del equipo de ingeniería.

### 1. Arquitectura de Datos y Modelos (`models.py`)
La base de datos utiliza un motor liviano **SQLite**, mapeado a través del ORM **SQLAlchemy**. Contiene dos entidades principales fuertemente ligadas mediante una relación de uno a uno (1:1):

*   **Modelo `Usuario` (Tabla `usuarios`):**
    *   `id` (Integer, PK): Identificador único del usuario.
    *   `email` (String 120, Unique): Correo electrónico del usuario (utilizado como credencial).
    *   `password_hash` (String 255): Almacenamiento seguro de la contraseña cifrada.
    *   `tipo` (String 20): Define el rol en el sistema (por defecto `'postulante'` para usuarios comunes, administradores como `'admin'`).
    *   `fecha_creacion` (DateTime): Registro de tiempo automático del alta.
    *   `verificado` (Boolean): Bandera de control de activación de cuenta.
*   **Modelo `Postulante` (Tabla `postulantes`):**
    *   Mantiene la información del propietario de la agenda (`nombres`, `apellidos`, `fecha_nacimiento`, `dni`).
    *   `usuario_id` (FK -> `usuarios.id`): Clave foránea que restringe y amarra los datos del perfil al usuario en sesión para garantizar privacidad multiusuario.
    *   `estado` (String 20): Campo de auditoría interna de la cuenta (por defecto `'pendiente'`).

### 2. Control de Rutas y Lógica de Negocio (`app.py`)
El servidor Flask expone los siguientes endpoints esenciales controlados por métodos HTTP específicos:

*   **`/registrarse` [GET] & `/postular` [POST]:** Procesa los formularios de registro de nuevos integrantes. Realiza validaciones estrictas (campos obligatorios, coincidencia de contraseñas, unicidad del correo en la base de datos y validador algorítmico del número de DNI a 8 dígitos).
*   **`/login` [GET/POST]:** Punto de acceso al sistema. Realiza consultas indexadas para verificar al usuario y bloquea el paso si la cuenta no ha cumplido el protocolo de verificación. Al iniciar con éxito, inicializa los estados en la `session` de Flask (`user_id`, `email`, `tipo_usuario`).
*   **`/verify` [GET/POST]:** Valida de forma temporal mediante variables de sesión el código numérico de 6 dígitos autogenerado al registrarse. Al coincidir, impacta la base de datos cambiando el estado del usuario a verificado.
*   **`/dashboard` [GET]:** Área privada protegida por el decorador personalizado `@login_required`. Evita accesos anónimos interceptando las cookies de sesión y renderiza el panel personal del usuario.
*   **`/cambiar-tema` [POST]:** Implementa la inyección de cookies locales de persistencia con una duración máxima de 30 días para alternar los estilos del frontend en base a las preferencias estéticas del cliente.

### 3. Mecanismos de Seguridad Implementados
*   **Seguridad de Credenciales:** Encriptación robusta utilizando la librería `werkzeug.security` mediante algoritmos de hashing seguros (`generate_password_hash` y `check_password_hash`). La base de datos nunca almacena texto plano.
*   **Seguridad de Sesiones:** Inyección de decoradores basados en `functools.wraps` para validar la existencia de `user_id` en las cookies del cliente antes de resolver las peticiones a vistas privadas.
*   **Aislamiento del Entorno:** Dependencia estricta de una clave secreta (`SECRET_KEY`) aleatoria inyectada dinámicamente desde el entorno (`os.environ`), mitigando ataques de secuestro de sesión (Session Hijacking).

### 4. Ecosistema de Dependencias (`requirements.txt`)
El backend se apoya en un conjunto de librerías de Python administradas a través de `pip` para garantizar el correcto funcionamiento del ecosistema:

*   **`Flask==3.1.2` & `Werkzeug==3.1.4`:** Framework principal del servidor web y su motor de utilidades WSGI encargado del enrutamiento y la seguridad de las cookies.
*   **`Flask-SQLAlchemy==3.1.1` & `SQLAlchemy==2.0.45`:** El ORM encargado de traducir las consultas de Python directamente a sentencias SQL en la base de datos SQLite.
*   **`psycopg2-binary==2.9.11`:** Conector precompilado listo para entornos de producción, lo que permite al sistema migrar de manera transparente de SQLite a una base de datos **PostgreSQL**.
*   **`Flask-Mail==0.10.0`:** Componente encargado de establecer los canales SMTP seguros con los servidores de Google para el envío de los códigos de validación de 6 dígitos.
*   **`python-dotenv==1.2.1`:** Librería que inyecta las credenciales locales guardadas en el archivo `.env` al objeto `os.environ` del sistema para evitar filtraciones de seguridad.

---

## 🚀 INSTALACIÓN Y CONFIGURACIÓN

1. **Clonar el repositorio y acceder:**
   ```bash
   git clone https://github.com
   cd flask-login-system
   ```
2. **Crear y activar el entorno virtual:**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```
3. **Instalar dependencias necesarias:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configurar Variables de Entorno (`.env`):** Crea un archivo `.env` en la raíz del proyecto para habilitar las firmas de seguridad y pasarelas de correo SMTP:
   ```text
   SECRET_KEY=tu_clave_secreta_super_segura
   MAIL_SERVER=://gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=tu_correo@gmail.com
   MAIL_PASSWORD=tu_contraseña_de_aplicacion_google
   MAIL_DEFAULT_SENDER=tu_correo@gmail.com
   ```
5. **Ejecutar el Servidor de Desarrollo:**
   ```bash
   python app.py
   ```
   La aplicación se creará de forma automatizada (`db.create_all()`) y estará lista en el puerto: `http://127.0.0.1:5000`.

---

## 📖 MANUAL DE USO CORTO (Guía del Usuario)

¡Bienvenido a tu Agenda Personal! Sigue esta breve guía rápida para comenzar a utilizar la plataforma:

1. **Creación de Cuenta:** Ingresa a la interfaz de registro, rellena tus datos personales utilizando un correo electrónico válido, tu número de DNI y define una contraseña segura.
2. **Verificación Obligatoria:** Una vez enviado el formulario, el sistema enviará de forma automática un código confidencial de 6 dígitos a tu buzón de correo. Digítalo en la pantalla de verificación para activar tu cuenta.
3. **Inicio de Sesión:** Digita tu correo electrónico y contraseña registrados en el portal principal de Login para acceder a tus módulos de trabajo privados.
4. **Modo Claro / Modo Oscuro:** En la barra superior derecha, dispones de un botón para cambiar instantáneamente la estética visual de la agenda de acuerdo a tus necesidades de lectura o comodidad visual en el entorno.
5. **Panel Personal (Dashboard):** Desde aquí podrás visualizar tu perfil y realizar interacciones directas protegidas con tu sesión privada de usuario del Instituto.

---
### Autores
*   **KalebCxDev** - *Frontend*
*   **joshuanavarrovelasquez-desig** - *Backend*
*   **JHOSEPEMC** - *Base de datos*

© 2026 Sistema De Agenda Personal IESTPO