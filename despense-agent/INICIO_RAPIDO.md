# 🚀 Inicio Rápido - Servidor WhatsApp

## Pasos para iniciar el servidor y probar

### 1. Iniciar el servidor Flask

En una terminal:
```bash
cd despense-agent
source ../.venv/bin/activate  # O la ruta a tu venv
python whatsapp_server.py
```

Deberías ver:
```
🚀 Iniciando servidor de WhatsApp...
* Running on http://127.0.0.1:5001
```

**⚠️ IMPORTANTE**: Deja esta terminal abierta y corriendo.

### 2. Iniciar ngrok (en otra terminal)

Abre una NUEVA terminal y ejecuta:
```bash
ngrok http 5001
```

Deberías ver:
```
Forwarding  https://tu-url.ngrok.io -> http://localhost:5001
```

**⚠️ IMPORTANTE**: Deja esta terminal también abierta.

### 3. Configurar el webhook en Meta

1. Copia la URL de ngrok (la que termina en `.ngrok.io`)
2. Ve a Meta App Dashboard → WhatsApp → Configuración → Webhooks
3. Configura:
   - **URL**: `https://tu-url-ngrok.ngrok.io/webhook`
   - **Token**: `mi_token` (o el que configuraste)
4. Haz clic en "Verificar y guardar"
5. **CRÍTICO**: Suscríbete al campo `messages`

### 4. Probar el webhook

En otra terminal (con el servidor corriendo):
```bash
python test_webhook.py
```

Deberías ver logs en la terminal del servidor Flask.

### 5. Enviar mensaje real desde WhatsApp

1. Obtén el número de prueba de Meta (en Getting Started)
2. Envía un mensaje a ese número desde WhatsApp
3. Revisa los logs en el servidor Flask

## 🔍 Verificación

- ✅ Servidor Flask corriendo en puerto 5001
- ✅ ngrok corriendo y mostrando la URL
- ✅ Webhook verificado en Meta
- ✅ Suscrito al campo `messages`
- ✅ Número agregado como número de prueba

## ❌ Problemas Comunes

**"No se pudo conectar al servidor"**
→ El servidor Flask no está corriendo. Inícialo primero.

**"No veo requests en ngrok"**
→ Verifica que estés suscrito a `messages` en Meta.

**"Los mensajes no llegan"**
→ Asegúrate de enviar al número correcto (el de Meta, no tu número personal).

