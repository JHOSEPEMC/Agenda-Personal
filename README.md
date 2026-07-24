# 📔 Sistema de Agenda Personal e Interacción Multiusuario (Flask)

Este proyecto es una aplicación web desarrollada con **Flask** diseñada para la gestión de una agenda personal. Implementa funcionalidades completas de autenticación, control de sesiones privadas y adaptabilidad visual para los usuarios del Instituto de Educación Superior Tecnológico Público Oxapampa.

---

## 🛠️ DOCUMENTACIÓN DEL PROYECTO

Toda la documentación detallada del sistema ha sido organizada de forma modular. Puedes acceder a las guías completas haciendo clic en los siguientes enlaces dentro del repositorio:

*   **[Guía Completa para Desarrolladores (Backend & Arquitectura)](doc/guia_tecnica.md):** Contiene la especificación de los modelos de base de datos (`models.py`), la lógica de las rutas de Flask (`app.py`), los mecanismos de seguridad y el ecosistema de dependencias.
*   **[Manual de Uso Corto para el Usuario](doc/guia_tecnica.md#%F0%9F%9A%80-manual-de-uso-corto-gu%C3%ADa-de-usuario):** Pasos rápidos para registrarse, verificar la cuenta por correo electrónico y alternar entre los modos visuales de la agenda.

---

## 🚀 INSTALACIÓN Y CONFIGURACIÓN RÁPIDA

1. **Clonar el repositorio:**
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
3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configurar Variables de Entorno (`.env`):** Crea un archivo `.env` en la raíz con tus credenciales secretas y del servidor de correos SMTP.
5. **Ejecutar el Servidor:**
   ```bash
   python app.py
   ```
   La aplicación estará lista en: `http://127.0.0.1:5000`.

---

## 👥 Autores
*   **KalebCxDev** - *Frontend*
*   **joshuanavarrovelasquez-desig** - *Backend*
*   **JHOSEPEMC** - *Base de datos*

© 2026 Sistema De Agenda Personal IESTPO
