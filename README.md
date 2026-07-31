# Sistema de Agenda Personal e Interacción Multiusuario (Flask)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge&logo=sqlite&logoColor=white)
![Licencia](https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge)

Aplicación web desarrollada en Flask para la gestión de agendas personales y colaboración multiusuario. Ofrece registro seguro con verificación por correo electrónico (OTP), aislamiento de notas por usuario, filtros por fecha y personalización de temas (Claro/Oscuro).

---

## Tabla de Contenidos
- [Características Principales](#características-principales)
- [Tecnologías Utilizadas](#tecnologías-utilizadas)
- [Arquitectura de Base de Datos](#arquitectura-de-base-de-datos)
- [Rutas y Endpoints](#rutas-y-endpoints)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Configuración y Variables de Entorno](#configuración-y-variables-de-entorno)
- [Guía de Instalación](#guía-de-instalación)
- [Manual de Uso](#manual-de-uso)
- [Capturas de Pantalla](#capturas-de-pantalla)
- [Solución de Problemas](#solución-de-problemas)
- [Autores](#autores)

---

## Características Principales

1. **Autenticación y Seguridad:**
   - Registro con validación de contraseña y verificación mediante código OTP de 6 dígitos enviado por Flask-Mail.
   - Protección contra fuerza bruta con límite de intentos (Rate Limiting).
   - Contraseñas encriptadas mediante Werkzeug.

2. **Gestión de Agenda (CRUD):**
   - Crear, editar, listar y eliminar notas organizadas por fecha.
   - Control para evitar notas duplicadas en un mismo día por usuario.

3. **Filtros y Búsqueda:**
   - Filtro por mes, año y períodos (Hoy, Futuras, Pasadas).
   - Búsqueda por palabras clave y paginación de 10 elementos.

4. **Personalización:**
   - Alternancia entre Modo Claro y Oscuro guardado en cookies.

---

## Tecnologías Utilizadas

- **Lenguaje:** Python 3.11
- **Framework:** Flask 3.1.2
- **Base de Datos / ORM:** SQLite / Flask-SQLAlchemy 3.1.1
- **Seguridad:** Werkzeug 3.1.4
- **Envío de Correos:** Flask-Mail 0.10.0
- **Servidor Producción:** Gunicorn 23.0.0
- **Frontend:** HTML5, CSS3, JavaScript