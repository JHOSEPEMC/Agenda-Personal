# Sistema de Admisión y Gestión de Archivos (Flask)

Este proyecto es una aplicación web desarrollada con **Flask** para la realizacion de una agenda personal con Inicio de sesión e interanccion personal.

## Características Principales

### Usuarios y Autenticación
*   **Registro de Postulantes:** Formulario de registro con validación de datos (DNI, correo único, contraseña).
*   **Verificación por Correo:** Envío de código de verificación al correo electrónico para activar la cuenta.
*   **Inicio de Sesión:** Sistema de login seguro con hash de contraseñas.
*   **Roles:** Diferenciación entre `admin` y `postulante`.
*   **Perfil de Usuario:** Visualización y edición de datos personales.

### Gestión de Archivos
*   **Subida de Archivos:** Los postulantes pueden subir documentos (PDF, imágenes, etc.).
*   **Almacenamiento Híbrido:**
    *   **Local:** Por defecto, los archivos se guardan en la carpeta `uploads/`.
    *   **Cloudinary:** Si se configuran las credenciales, los archivos se suben automáticamente a la nube.
*   **Validaciones:** Control de extensiones permitidas y tamaño máximo de archivo (5MB).
*   **Descarga y Eliminación:** Gestión completa de los archivos propios.

### Panel de Administración (Admin Dashboard)
*   **Resumen General:** Contadores de usuarios, archivos y postulantes pendientes.
*   **Gestión de Usuarios:** Listado de todos los postulantes registrados.
*   **Cambio de Estado:** El administrador puede aprobar, rechazar o mantener en pendiente a los postulantes.
*   **Gestión de Archivos Global:** El admin puede ver, descargar y eliminar cualquier archivo del sistema.

## Tecnologías Utilizadas

*   **Backend:** Python 3, Flask.
*   **Base de Datos:** SQLite (Configuración actual, escalable a PostgreSQL).
*   **ORM:** SQLAlchemy.
*   **Frontend:** HTML5, CSS3 (Diseño Responsive), Jinja2 Templates.
*   **Email:** Flask-Mail (Gmail SMTP).
*   **Almacenamiento Cloud:** Cloudinary SDK.

## Requisitos Previos

*   Python 3.10 o superior.
*   Pip (Gestor de paquetes de Python).

## Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/KalebCxDev/flask-login-system.git
    cd flask-login-system
    ```

2.  **Crear y activar un entorno virtual:**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar Variables de Entorno (.env):**
    Crea un archivo `.env` en la raíz del proyecto con el siguiente contenido:

    ```ini
    # Seguridad de Flask
    SECRET_KEY=tu_clave_secreta_super_segura

    # Configuración de Correo (Gmail)
    MAIL_SERVER=smtp.gmail.com
    MAIL_PORT=587
    MAIL_USE_TLS=True
    MAIL_USERNAME=tucorreo@gmail.com
    MAIL_PASSWORD=tu_contraseña_de_app
    MAIL_DEFAULT_SENDER=tucorreo@gmail.com

    # Configuración de Cloudinary (Opcional, si no se pone usa almacenamiento local)
    CLOUDINARY_CLOUD_NAME=cloudinary_cloud_name
    CLOUDINARY_API_KEY=tu_api_key
    CLOUDINARY_API_SECRET=tu_api_secret

    ```

5.  **Inicializar la Base de Datos:**
    La base de datos se crea automáticamente al ejecutar la aplicación por primera vez gracias a `db.create_all()` en `app.py`.

## Ejecución

Para correr el servidor de desarrollo:

```bash
python app.py
```

La aplicación estará disponible en `http://127.0.0.1:5000`.

## Estructura del Proyecto

```
flask-login-system/
├── app.py                  # Archivo principal de la aplicación (Rutas y Lógica)
├── models.py               # Modelos de Base de Datos (Usuario, Postulante, Archivo)
├── config_mail.py          # Configuración del servidor de correo
├── cloudinary_utils.py     # Funciones auxiliares para Cloudinary
├── requirements.txt        # Dependencias del proyecto
├── .env                    # Variables de entorno (No incluir en repositorios públicos)
├── instance/               # Base de datos SQLite
├── static/                 # Archivos estáticos
│   ├── css/                # Hojas de estilo
│   └── js/                 # Scripts JavaScript
├── templates/              # Plantillas HTML (Jinja2)
│   ├── base.html           # Layout base
│   ├── login.html          # Login
│   ├── register.html       # Registro
│   ├── dashboard.html      # Panel del postulante
│   ├── admin_*.html        # Paneles de administración
│   └── ...
└── uploads/                # Carpeta para archivos subidos localmente
```

## Seguridad

*   **Contraseñas:** Hasheadas con `werkzeug.security`.
*   **Rutas Protegidas:** Decoradores `@login_required` y `@admin_required`.
*   **Archivos:** Validación de extensiones y nombres de archivo seguros (UUID).

## Autores

*   KalebCxDev - *Frontend *
*   joshuanavarrovelasquez-desig - *Backend *
*   JHOSEPEMC - *Base de datos *

---
© 2026 Sistema de Admisión IESTPO
