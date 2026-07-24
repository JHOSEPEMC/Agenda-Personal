# GUÍA PARA DESARROLLADORES - BACKEND (`doc/`)

Este documento contiene la especificación técnica del lado del servidor para los desarrolladores del proyecto de la Agenda Personal (IESTPO).

## 1. Arquitectura de Datos (`models.py`)
El backend gestiona la persistencia mediante **SQLite** y el ORM **SQLAlchemy**, estructurado en dos entidades con relación de uno a uno (1:1):
- **Usuario (Tabla `usuarios`):** Almacena las credenciales principales (`id`, `email`, `password_hash`, `tipo`, `verificado`). El campo `tipo` restringe el acceso discriminando entre `'admin'` y `'postulante'`.
- **Postulante (Tabla `postulantes`):** Almacena el perfil del propietario de la agenda (`nombres`, `apellidos`, `dni`). Utiliza `usuario_id` como Clave Foránea para asegurar que cada usuario acceda únicamente a sus propios registros de forma privada.

## 2. Lógica de Endpoints y Rutas (`app.py`)
- **`/registrarse` y `/postular` [GET/POST]:** Captura los datos de registro, valida la unicidad del correo electrónico en la base de datos y restringe el DNI a 8 caracteres numéricos exactos.
- **`/login` [GET/POST]:** Autentica al usuario mediante el sistema de hashes. Bloquea el paso si la cuenta no ha verificado su correo. Inicializa la sesión con las variables `user_id`, `email` y `tipo_usuario`.
- **`/verify` [GET/POST]:** Contrasta el código aleatorio de 6 dígitos enviado por correo para activar el estado de verificación del perfil.
- **`/dashboard` [GET]:** Vista privada protegida mediante el decorador `@login_required` para impedir ingresos anónimos al entorno de la agenda.
- **`/cambiar-tema` [POST]:** Inyecta cookies locales por 30 días para persistir la preferencia de Modo Claro o Modo Oscuro del usuario.

### Vista del Entorno de Desarrollo
A continuación se muestra el servidor de desarrollo corriendo localmente en la rama de documentación:

Colocar imagen relacionada a esto


## 3. Capa de Seguridad
- **Cifrado:** Uso estricto de `werkzeug.security` para el hashing de contraseñas (`generate_password_hash` y `check_password_hash`).
- **Aislamiento:** Uso de claves secretas (`SECRET_KEY`) cargadas dinámicamente desde variables de entorno locales (`.env`).

---

## MANUAL DE USO CORTO (Guía de Usuario)

1. **Crear Cuenta:** Regístrate con tus datos personales, DNI y un correo electrónico válido en la interfaz de registro.
2. **Validar Código:** Copia el código de 6 dígitos enviado automáticamente a tu correo y digítalo en el portal para activar tu usuario.
3. **Iniciar Sesión:** Introduce tus credenciales validadas en la pantalla de Login.
4. **Alternar Tema:** Utiliza el botón del menú superior para cambiar instantáneamente la estética entre Modo Claro y Modo Oscuro.
5. **Gestionar Agenda:** Accede a tu panel privado (Dashboard) para administrar de forma segura tus actividades e interacciones personales.

### Vista de la Interfaz de la Agenda (Registro)
Esta es la interfaz gráfica que verá el usuario al interactuar con el sistema del Instituto:

![Interfaz de Registro de la Agenda] igualmente colocar fotoprueba ejemplo:
(capturas/diagramas/Captura de pantalla (2).png)

## SOLUCIÓN DE PROBLEMAS COMUNES (Troubleshooting)

### Error: `KeyError: 'SECRET_KEY'` o fallo al arrancar el servidor
*   **Causa:** El backend no encuentra el archivo de variables ocultas `.env` en la raíz.
*   **Solución:** Asegurarse de renombrar el archivo a `.env` a secas (sin extensiones como `.txt` o `.example`) y verificar que la línea `SECRET_KEY=...` esté correctamente declarada.

### Error de compilación con `psycopg2` en Windows
*   **Causa:** Se está intentando instalar dependencias heredadas en entornos con versiones de Python demasiado recientes (como 3.12 o superiores) donde no existen instaladores precompilados.
*   **Solución:** Desplegar el entorno virtual utilizando de forma estricta **Python 3.11**, el cual cuenta con compatibilidad directa de binarios (`.whl`) optimizados para sistemas Windows.