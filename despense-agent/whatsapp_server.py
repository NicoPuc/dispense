"""
Servidor Flask para integrar el Agente de Despensa con WhatsApp usando Meta WhatsApp Cloud API
"""

import os
import requests
import tempfile
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from despensa_agent import run_agent
from langchain_core.messages import HumanMessage, AIMessage

# Cargar variables de entorno
load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)

# Configuración de WhatsApp Cloud API
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mi_token_secreto")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v22.0")  # Actualizado a v22.0 según el curl de Meta
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"

# Almacenar historial de conversación por número de teléfono
chat_histories = {}

# Estadísticas de webhooks recibidos
webhook_stats = {
    "total_requests": 0,
    "from_meta": 0,
    "not_from_meta": 0,
    "with_messages": 0,
    "test_messages": 0,
    "real_messages": 0
}


def send_whatsapp_message(to: str, message: str):
    """
    Envía un mensaje de texto a través de WhatsApp Cloud API.
    
    Args:
        to: Número de teléfono del destinatario (formato: 1234567890)
        message: Mensaje de texto a enviar
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("⚠️  Error: WHATSAPP_TOKEN o WHATSAPP_PHONE_NUMBER_ID no configurados")
        return False
    
    # Formatear número de teléfono (debe incluir código de país sin +)
    phone_number = to.replace("+", "").replace(" ", "").replace("-", "")
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message
        }
    }
    
    try:
        print(f"\n📤 Enviando mensaje a WhatsApp:")
        print(f"   Para: {phone_number}")
        print(f"   URL: {WHATSAPP_API_URL}")
        print(f"   Mensaje: {message[:50]}..." if len(message) > 50 else f"   Mensaje: {message}")
        
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ Mensaje enviado correctamente")
            print(f"   Respuesta: {response.json()}")
            return True
        else:
            print(f"❌ Error en respuesta: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            response.raise_for_status()
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error enviando mensaje a WhatsApp: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Respuesta: {e.response.text}")
        return False


def download_media(media_id: str, mime_type: str) -> str:
    """
    Descarga un archivo multimedia desde WhatsApp Cloud API.
    
    Args:
        media_id: ID del archivo multimedia en WhatsApp
        mime_type: Tipo MIME del archivo (ej: "audio/ogg", "image/jpeg")
    
    Returns:
        Ruta al archivo descargado temporalmente
    """
    if not WHATSAPP_TOKEN:
        print("❌ ERROR: WHATSAPP_TOKEN no configurado")
        return None
    
    # Obtener URL del archivo
    media_url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    
    try:
        print(f"   📡 Obteniendo URL de descarga...")
        print(f"      Media URL: {media_url}")
        
        # Obtener URL de descarga
        response = requests.get(media_url, headers=headers, timeout=30)
        response.raise_for_status()
        media_data = response.json()
        download_url = media_data.get("url")
        
        print(f"   📦 Respuesta de Meta:")
        print(f"      Keys: {list(media_data.keys())}")
        print(f"      Download URL: {download_url[:100] if download_url else 'None'}...")
        
        if not download_url:
            print(f"❌ ERROR: No se encontró URL de descarga en la respuesta")
            print(f"   Respuesta completa: {media_data}")
            return None
        
        # Descargar el archivo
        print(f"   ⬇️  Descargando archivo desde Meta...")
        download_response = requests.get(download_url, headers=headers, timeout=60)
        download_response.raise_for_status()
        
        file_size = len(download_response.content)
        print(f"   ✅ Archivo descargado: {file_size} bytes ({file_size / 1024:.2f} KB)")
        
        # Determinar extensión del archivo
        extension_map = {
            "audio/ogg": ".ogg",
            "audio/ogg; codecs=opus": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/wav": ".wav",
            "audio/x-m4a": ".m4a",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp"
        }
        extension = extension_map.get(mime_type, ".tmp")
        
        print(f"   📝 MIME Type: {mime_type}")
        print(f"   📝 Extensión asignada: {extension}")
        
        # Guardar en archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
            tmp_file.write(download_response.content)
            tmp_path = tmp_file.name
            print(f"   💾 Archivo guardado en: {tmp_path}")
            return tmp_path
    
    except requests.exceptions.Timeout:
        print(f"❌ ERROR: Timeout descargando archivo multimedia")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR descargando archivo multimedia: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ ERROR inesperado descargando archivo: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Verifica el webhook de WhatsApp (requerido por Meta).
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Verificación de webhook fallida")
        return "Forbidden", 403


@app.route("/debug", methods=["GET", "POST"])
def debug_endpoint():
    """
    Endpoint de debug para ver los datos recibidos (similar a n8n).
    """
    if request.method == "GET":
        return jsonify({
            "status": "debug_endpoint_active",
            "message": "Envía un POST con datos para verlos aquí",
            "webhook_url": "/webhook"
        })
    
    # Mostrar datos recibidos de forma legible
    data = request.get_json() if request.is_json else request.form.to_dict()
    headers = dict(request.headers)
    
    debug_info = {
        "method": request.method,
        "headers": headers,
        "data": data,
        "raw_data": request.get_data(as_text=True) if not request.is_json else None
    }
    
    print("\n" + "="*70)
    print("🔍 DEBUG ENDPOINT - Datos recibidos")
    print("="*70)
    print(json.dumps(debug_info, indent=2, ensure_ascii=False))
    print("="*70 + "\n")
    
    return jsonify(debug_info)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """
    Maneja los mensajes entrantes de WhatsApp.
    """
    # Log INMEDIATO - antes de cualquier procesamiento
    print("\n" + "="*70)
    print("🔥 POST RECIBIDO EN /webhook")
    print("="*70)
    print(f"📥 Método: {request.method}")
    print(f"📥 Content-Type: {request.headers.get('Content-Type', 'N/A')}")
    print(f"📥 User-Agent: {request.headers.get('User-Agent', 'N/A')}")
    print(f"📥 X-Hub-Signature-256: {request.headers.get('X-Hub-Signature-256', 'N/A')}")
    print(f"📥 Raw data length: {len(request.get_data())} bytes")
    
    # Intentar obtener datos raw antes de parsear JSON
    try:
        raw_data = request.get_data(as_text=True)
        print(f"📥 Raw data (primeros 500 chars): {raw_data[:500]}")
    except Exception as e:
        print(f"⚠️  No se pudo obtener raw data: {e}")
    
    try:
        data = request.get_json()
        
        # Log detallado para debugging (similar a n8n)
        print("\n" + "="*70)
        print("📥 WEBHOOK RECIBIDO - " + str(request.headers.get('X-Hub-Signature-256', 'Sin firma')))
        print("="*70)
        print("📦 Datos completos recibidos:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("="*70)
        
        # Mostrar headers importantes
        print("\n📋 Headers importantes:")
        print(f"   Content-Type: {request.headers.get('Content-Type')}")
        print(f"   User-Agent: {request.headers.get('User-Agent', 'N/A')}")
        print("="*70 + "\n")
        
        if not data:
            print("⚠️  No se recibieron datos")
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # WhatsApp envía notificaciones en 'entry'
        if "object" not in data:
            print(f"⚠️  Objeto no encontrado en datos. Keys: {list(data.keys()) if data else 'None'}")
            return jsonify({"status": "ok"}), 200
        
        if data["object"] != "whatsapp_business_account":
            print(f"⚠️  Objeto no es whatsapp_business_account: {data.get('object')}")
            return jsonify({"status": "ok"}), 200
        
        entries = data.get("entry", [])
        print(f"📋 Entradas encontradas: {len(entries)}")
        
        if not entries:
            print("⚠️  No hay entradas en el webhook")
            print("💡 Esto puede ser normal si es solo una notificación de estado")
            return jsonify({"status": "ok"}), 200
        
        # Variable para rastrear si se procesó algún mensaje
        mensajes_procesados = 0
        
        for entry_idx, entry in enumerate(entries):
            print(f"\n📂 Procesando entrada #{entry_idx + 1}")
            changes = entry.get("changes", [])
            print(f"🔄 Cambios encontrados: {len(changes)}")
            
            for change_idx, change in enumerate(changes):
                print(f"\n   " + "-"*60)
                print(f"   🔄 Procesando cambio #{change_idx + 1}")
                print(f"   " + "-"*60)
                
                value = change.get("value", {})
                field = change.get("field", "unknown")
                print(f"   📊 Campo del webhook: '{field}'")
                print(f"   📊 Keys disponibles en 'value': {list(value.keys())}")
                
                # Mostrar metadata si existe
                metadata = value.get("metadata", {})
                if metadata:
                    print(f"\n   📱 Metadata:")
                    print(f"      - Display Phone Number: {metadata.get('display_phone_number')}")
                    print(f"      - Phone Number ID: {metadata.get('phone_number_id')}")
                
                # Verificar si hay contacts (información del contacto)
                contacts = value.get("contacts", [])
                if contacts:
                    print(f"\n   👤 Contactos encontrados: {len(contacts)}")
                    for contact_idx, contact in enumerate(contacts):
                        profile = contact.get("profile", {})
                        wa_id = contact.get("wa_id")
                        print(f"      Contacto #{contact_idx + 1}:")
                        print(f"         - Nombre: {profile.get('name', 'N/A')}")
                        print(f"         - WhatsApp ID: {wa_id}")
                
                # Verificar si hay mensajes
                messages = value.get("messages", [])
                print(f"\n   💬 Mensajes encontrados: {len(messages)}")
                
                # Verificar si hay statuses (notificaciones de estado)
                statuses = value.get("statuses", [])
                if statuses:
                    print(f"   📊 Notificaciones de estado encontradas: {len(statuses)}")
                    for status in statuses:
                        print(f"      - Status: {status.get('status')}, ID: {status.get('id')}, Recipient: {status.get('recipient_id')}")
                
                # Mostrar estructura completa si no hay mensajes (para debug)
                if not messages and not statuses:
                    print(f"\n   ⚠️  No se encontraron mensajes ni statuses")
                    print(f"   📦 Estructura completa del 'value' para debug:")
                    print(f"   {json.dumps(value, indent=6, ensure_ascii=False)}")
                
                if not messages:
                    # Puede ser una notificación de estado, no un mensaje nuevo
                    print(f"   ⚠️  No hay mensajes en este cambio")
                    print(f"   💡 Esto puede ser una notificación de estado o un tipo de evento diferente")
                    print(f"   📋 Todos los datos disponibles en 'value':")
                    print(f"   {json.dumps(value, indent=6, ensure_ascii=False)}")
                    continue
                
                webhook_stats["with_messages"] += 1
                print(f"\n   ✅ ¡MENSAJES ENCONTRADOS! Procesando {len(messages)} mensaje(s)...")
                
                for msg_idx, message in enumerate(messages):
                    print(f"\n   " + "="*60)
                    print(f"   📨 MENSAJE #{msg_idx + 1} RECIBIDO:")
                    print(f"   " + "="*60)
                    print(f"   {json.dumps(message, indent=6, ensure_ascii=False)}")
                    print(f"   " + "="*60)
                    
                    # Obtener información del mensaje
                    from_number = message.get("from")
                    message_id = message.get("id")
                    message_type = message.get("type")
                    timestamp = message.get("timestamp")
                    
                    print(f"\n   📋 Información extraída del mensaje:")
                    print(f"      👤 De (from_number): {from_number}")
                    print(f"      🆔 ID del mensaje: {message_id}")
                    print(f"      📝 Tipo: {message_type}")
                    print(f"      ⏰ Timestamp: {timestamp}")
                    
                    # Mostrar contenido según el tipo
                    if message_type == "text":
                        text_body = message.get("text", {}).get("body", "")
                        print(f"      💬 Texto: {text_body}")
                    elif message_type in ["audio", "voice"]:
                        audio_data = message.get("audio") or message.get("voice")
                        print(f"      🎤 Audio ID: {audio_data.get('id') if audio_data else 'N/A'}")
                    elif message_type == "image":
                        image_data = message.get("image", {})
                        print(f"      🖼️  Imagen ID: {image_data.get('id') if image_data else 'N/A'}")
                    
                    print(f"\n   🔄 Iniciando procesamiento del mensaje...")
                    
                    if not from_number:
                        print(f"   ❌ ERROR: No se encontró número de teléfono en el mensaje")
                        print(f"   📦 Mensaje completo para debug:")
                        print(f"   {json.dumps(message, indent=6, ensure_ascii=False)}")
                        continue
                    
                    # Obtener o crear historial de conversación
                    if from_number not in chat_histories:
                        chat_histories[from_number] = []
                        print(f"   ✅ Nuevo historial creado para {from_number}")
                    else:
                        print(f"   📚 Historial existente encontrado para {from_number} ({len(chat_histories[from_number])} mensajes previos)")
                    
                    chat_history = chat_histories[from_number]
                    
                    # Detectar si es mensaje de prueba o real
                    # Los mensajes de prueba de Meta suelen tener números como "16315551181"
                    # Los mensajes reales tienen números reales de WhatsApp
                    is_test_message = from_number in ["16315551181", "1234567890"] or "test" in str(message.get("id", "")).lower()
                    
                    if is_test_message:
                        webhook_stats["test_messages"] += 1
                        print(f"   🧪 Mensaje de PRUEBA detectado")
                    else:
                        webhook_stats["real_messages"] += 1
                        print(f"   📱 Mensaje REAL detectado de {from_number}")
                    
                    # Procesar según el tipo de mensaje
                    if message_type == "text":
                        # Mensaje de texto
                        text_body = message.get("text", {}).get("body", "")
                        print(f"   📝 Procesando mensaje de texto: '{text_body}'")
                        mensajes_procesados += 1
                        process_text_message(from_number, text_body, chat_history)
                    
                    elif message_type == "audio" or message_type == "voice":
                        # Mensaje de audio
                        print(f"   🎤 Procesando mensaje de audio...")
                        mensajes_procesados += 1
                        audio_data = message.get("audio") or message.get("voice")
                        if audio_data:
                            media_id = audio_data.get("id")
                            mime_type = audio_data.get("mime_type", "audio/ogg")
                            process_audio_message(from_number, media_id, mime_type, chat_history)
                        else:
                            print(f"   ⚠️  No se encontraron datos de audio en el mensaje")
                    
                    elif message_type == "image":
                        # Mensaje de imagen
                        print(f"   🖼️  Procesando mensaje de imagen...")
                        mensajes_procesados += 1
                        image_data = message.get("image", {})
                        if image_data:
                            media_id = image_data.get("id")
                            mime_type = image_data.get("mime_type", "image/jpeg")
                            process_image_message(from_number, media_id, mime_type, chat_history)
                        else:
                            print(f"   ⚠️  No se encontraron datos de imagen en el mensaje")
                    
                    else:
                        # Tipo de mensaje no soportado
                        print(f"   ⚠️  Tipo de mensaje no soportado: {message_type}")
                        print(f"   📦 Mensaje completo: {json.dumps(message, indent=6, ensure_ascii=False)}")
                        mensajes_procesados += 1
                        send_whatsapp_message(
                            from_number,
                            "Lo siento, solo puedo procesar mensajes de texto, audio e imágenes."
                        )
        
        print("\n" + "="*70)
        print(f"✅ WEBHOOK PROCESADO - {mensajes_procesados} mensaje(s) procesado(s)")
        print("="*70 + "\n")
        return jsonify({"status": "ok", "messages_processed": mensajes_procesados}), 200
    
    except Exception as e:
        print(f"\n❌ Error procesando webhook: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n📦 Datos que causaron el error:")
        try:
            print(f"   Raw data: {request.get_data(as_text=True)[:500]}")
        except:
            print("   No se pudo obtener raw data")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.before_request
def log_request_info():
    """Log todas las requests para debugging"""
    if request.path == "/webhook" and request.method == "POST":
        webhook_stats["total_requests"] += 1
        print(f"\n🔍 [BEFORE_REQUEST] {request.method} {request.path}")
        print(f"   Headers: {dict(request.headers)}")
        print(f"   Remote Addr: {request.remote_addr}")
        # Verificar si viene de Meta
        user_agent = request.headers.get('User-Agent', '')
        if 'facebook' in user_agent.lower() or 'meta' in user_agent.lower():
            webhook_stats["from_meta"] += 1
            print(f"   ✅ Request viene de Meta/Facebook")
        else:
            webhook_stats["not_from_meta"] += 1
            print(f"   ⚠️  Request NO viene de Meta (User-Agent: {user_agent})")


@app.route("/stats", methods=["GET"])
def get_stats():
    """Endpoint para ver estadísticas de webhooks recibidos"""
    return jsonify({
        "webhook_stats": webhook_stats,
        "chat_histories_count": len(chat_histories),
        "message": "Estas son las estadísticas de webhooks recibidos. Si 'from_meta' es 0 cuando envías mensajes reales, Meta no está enviando webhooks."
    })


def process_text_message(from_number: str, text: str, chat_history: list):
    """
    Procesa un mensaje de texto.
    """
    try:
        print(f"📨 Mensaje de texto recibido de {from_number}: {text}")
        
        # Ejecutar el agente
        response = run_agent(text, chat_history, None)
        
        # Manejar respuesta estructurada o simple
        respuesta_texto = response
        extracto_estructurado = None
        
        if isinstance(response, dict):
            respuesta_texto = response.get("respuesta", str(response))
            extracto_estructurado = response.get("extracto_estructurado")
            resultado_procesado = response.get("resultado_procesado")
            
            if extracto_estructurado:
                print(f"\n{'='*70}")
                print(f"📦 EXTRACTO ESTRUCTURADO - LISTO PARA INTEGRACIÓN CON BD")
                print(f"{'='*70}")
                print(f"✅ Acción: {extracto_estructurado.get('accion')}")
                print(f"✅ Productos: {len(extracto_estructurado.get('productos', []))}")
                print(f"✅ Intención: {extracto_estructurado.get('intencion')}")
                
                if extracto_estructurado.get('productos'):
                    print(f"\n📋 Productos extraídos:")
                    for idx, producto in enumerate(extracto_estructurado.get('productos', []), 1):
                        nombre = producto.get('nombre', 'N/A')
                        cantidad = producto.get('cantidad', 'N/A')
                        unidad = producto.get('unidad', 'unidad')
                        print(f"   {idx}. {nombre}: {cantidad} {unidad}")
                
                print(f"\n📄 JSON completo del extracto:")
                print(json.dumps(extracto_estructurado, ensure_ascii=False, indent=2))
                
                if resultado_procesado:
                    print(f"\n🔄 Resultado del procesamiento:")
                    print(json.dumps(resultado_procesado, ensure_ascii=False, indent=2))
                
                print(f"\n💡 Este JSON está listo para enviar a tu endpoint de BD")
                print(f"{'='*70}\n")
        
        # Enviar respuesta
        send_whatsapp_message(from_number, respuesta_texto)
        
        # Actualizar historial
        chat_history.append(HumanMessage(content=text))
        chat_history.append(AIMessage(content=respuesta_texto))
        
    except Exception as e:
        print(f"❌ Error procesando mensaje de texto: {e}")
        send_whatsapp_message(
            from_number,
            "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."
        )


def process_audio_message(from_number: str, media_id: str, mime_type: str, chat_history: list):
    """
    Procesa un mensaje de audio.
    """
    try:
        print(f"\n{'='*70}")
        print(f"🎤 PROCESANDO MENSAJE DE AUDIO")
        print(f"{'='*70}")
        print(f"   De: {from_number}")
        print(f"   Media ID: {media_id}")
        print(f"   MIME Type: {mime_type}")
        
        # Descargar archivo de audio
        print(f"\n📥 Descargando archivo de audio...")
        audio_path = download_media(media_id, mime_type)
        
        if not audio_path:
            print(f"❌ ERROR: No se pudo descargar el archivo de audio")
            print(f"   Media ID: {media_id}")
            print(f"   MIME Type: {mime_type}")
            send_whatsapp_message(
                from_number,
                "Lo siento, no pude descargar el archivo de audio. Por favor, intenta de nuevo."
            )
            return
        
        print(f"✅ Archivo descargado: {audio_path}")
        
        # Verificar que el archivo existe y tiene contenido
        if not os.path.exists(audio_path):
            print(f"❌ ERROR: El archivo descargado no existe: {audio_path}")
            send_whatsapp_message(
                from_number,
                "Lo siento, hubo un error con el archivo de audio. Por favor, intenta de nuevo."
            )
            return
        
        file_size = os.path.getsize(audio_path)
        print(f"   Tamaño del archivo: {file_size} bytes ({file_size / 1024:.2f} KB)")
        
        if file_size == 0:
            print(f"❌ ERROR: El archivo está vacío")
            send_whatsapp_message(
                from_number,
                "Lo siento, el archivo de audio está vacío. Por favor, intenta de nuevo."
            )
            try:
                os.remove(audio_path)
            except:
                pass
            return
        
        # Verificar extensión del archivo
        file_ext = os.path.splitext(audio_path)[1].lower()
        print(f"   Extensión del archivo: {file_ext}")
        
        # Ejecutar el agente con el archivo de audio
        print(f"\n🤖 Ejecutando agente con archivo de audio...")
        print(f"   Ruta: {audio_path}")
        print(f"   Historial previo: {len(chat_history)} mensajes")
        
        response = run_agent("", chat_history, audio_path)
        
        # Manejar respuesta estructurada o simple
        respuesta_texto = response
        extracto_estructurado = None
        
        if isinstance(response, dict):
            respuesta_texto = response.get("respuesta", str(response))
            extracto_estructurado = response.get("extracto_estructurado")
            resultado_procesado = response.get("resultado_procesado")
            
            if extracto_estructurado:
                print(f"\n{'='*70}")
                print(f"📦 EXTRACTO ESTRUCTURADO - LISTO PARA INTEGRACIÓN CON BD")
                print(f"{'='*70}")
                print(f"✅ Acción: {extracto_estructurado.get('accion')}")
                print(f"✅ Productos: {len(extracto_estructurado.get('productos', []))}")
                print(f"✅ Intención: {extracto_estructurado.get('intencion')}")
                
                if extracto_estructurado.get('productos'):
                    print(f"\n📋 Productos extraídos:")
                    for idx, producto in enumerate(extracto_estructurado.get('productos', []), 1):
                        nombre = producto.get('nombre', 'N/A')
                        cantidad = producto.get('cantidad', 'N/A')
                        unidad = producto.get('unidad', 'unidad')
                        print(f"   {idx}. {nombre}: {cantidad} {unidad}")
                
                print(f"\n📄 JSON completo del extracto:")
                print(json.dumps(extracto_estructurado, ensure_ascii=False, indent=2))
                
                if resultado_procesado:
                    print(f"\n🔄 Resultado del procesamiento:")
                    print(json.dumps(resultado_procesado, ensure_ascii=False, indent=2))
                
                print(f"\n💡 Este JSON está listo para enviar a tu endpoint de BD")
                print(f"{'='*70}\n")
        
        print(f"\n✅ Respuesta del agente recibida:")
        print(f"   Longitud: {len(respuesta_texto)} caracteres")
        print(f"   Contenido: {respuesta_texto[:200]}..." if len(respuesta_texto) > 200 else f"   Contenido: {respuesta_texto}")
        
        # Enviar respuesta
        print(f"\n📤 Enviando respuesta a WhatsApp...")
        send_whatsapp_message(from_number, respuesta_texto)
        
        # Actualizar historial
        chat_history.append(HumanMessage(content=f"Archivo audio: {audio_path}"))
        chat_history.append(AIMessage(content=respuesta_texto))
        
        print(f"✅ Mensaje de audio procesado correctamente")
        print(f"{'='*70}\n")
        
        # Limpiar archivo temporal
        try:
            os.remove(audio_path)
            print(f"🗑️  Archivo temporal eliminado: {audio_path}")
        except Exception as cleanup_error:
            print(f"⚠️  No se pudo eliminar archivo temporal: {cleanup_error}")
    
    except Exception as e:
        print(f"\n❌ ERROR procesando mensaje de audio: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*70}\n")
        send_whatsapp_message(
            from_number,
            "Lo siento, hubo un error procesando tu audio. Por favor, intenta de nuevo."
        )


def process_image_message(from_number: str, media_id: str, mime_type: str, chat_history: list):
    """
    Procesa un mensaje de imagen.
    """
    try:
        print(f"🖼️  Mensaje de imagen recibido de {from_number}")
        
        # Descargar archivo de imagen
        image_path = download_media(media_id, mime_type)
        
        if not image_path:
            send_whatsapp_message(
                from_number,
                "Lo siento, no pude descargar la imagen. Por favor, intenta de nuevo."
            )
            return
        
        # Ejecutar el agente con la imagen
        response = run_agent("", chat_history, image_path)
        
        # Manejar respuesta estructurada o simple
        respuesta_texto = response
        extracto_estructurado = None
        
        if isinstance(response, dict):
            respuesta_texto = response.get("respuesta", str(response))
            extracto_estructurado = response.get("extracto_estructurado")
            resultado_procesado = response.get("resultado_procesado")
            
            if extracto_estructurado:
                print(f"\n{'='*70}")
                print(f"📦 EXTRACTO ESTRUCTURADO - LISTO PARA INTEGRACIÓN CON BD")
                print(f"{'='*70}")
                print(f"✅ Acción: {extracto_estructurado.get('accion')}")
                print(f"✅ Productos: {len(extracto_estructurado.get('productos', []))}")
                print(f"✅ Intención: {extracto_estructurado.get('intencion')}")
                
                if extracto_estructurado.get('productos'):
                    print(f"\n📋 Productos extraídos:")
                    for idx, producto in enumerate(extracto_estructurado.get('productos', []), 1):
                        nombre = producto.get('nombre', 'N/A')
                        cantidad = producto.get('cantidad', 'N/A')
                        unidad = producto.get('unidad', 'unidad')
                        print(f"   {idx}. {nombre}: {cantidad} {unidad}")
                
                print(f"\n📄 JSON completo del extracto:")
                print(json.dumps(extracto_estructurado, ensure_ascii=False, indent=2))
                
                if resultado_procesado:
                    print(f"\n🔄 Resultado del procesamiento:")
                    print(json.dumps(resultado_procesado, ensure_ascii=False, indent=2))
                
                print(f"\n💡 Este JSON está listo para enviar a tu endpoint de BD")
                print(f"{'='*70}\n")
        
        # Enviar respuesta
        send_whatsapp_message(from_number, respuesta_texto)
        
        # Actualizar historial
        chat_history.append(HumanMessage(content=f"Archivo imagen: {image_path}"))
        chat_history.append(AIMessage(content=respuesta_texto))
        
        # Limpiar archivo temporal
        try:
            os.remove(image_path)
        except:
            pass
    
    except Exception as e:
        print(f"❌ Error procesando mensaje de imagen: {e}")
        import traceback
        traceback.print_exc()
        send_whatsapp_message(
            from_number,
            "Lo siento, hubo un error procesando tu imagen. Por favor, intenta de nuevo."
        )


if __name__ == "__main__":
    # Verificar configuración
    if not WHATSAPP_TOKEN:
        print("⚠️  Advertencia: WHATSAPP_TOKEN no configurado")
    if not WHATSAPP_PHONE_NUMBER_ID:
        print("⚠️  Advertencia: WHATSAPP_PHONE_NUMBER_ID no configurado")
    
    # Puerto configurable (por defecto 5001 para evitar conflicto con AirPlay en macOS)
    PORT = int(os.getenv("FLASK_PORT", 5001))
    
    print("🚀 Iniciando servidor de WhatsApp...")
    print(f"📡 Webhook URL: https://tu-dominio.com/webhook")
    print(f"🔐 Verify Token: {WHATSAPP_VERIFY_TOKEN}")
    print(f"🌐 Puerto: {PORT}")
    print(f"\n🔍 Endpoints disponibles:")
    print(f"   - POST /webhook (webhook principal de WhatsApp)")
    print(f"   - GET/POST /debug (endpoint de debug para ver datos)")
    print(f"   - GET /stats (estadísticas de webhooks recibidos)")
    print(f"\n💡 Para desarrollo local, usa ngrok:")
    print(f"   ngrok http {PORT}")
    print("   Luego configura el webhook en Meta con: https://tu-url-ngrok.ngrok.io/webhook")
    print("\n⚠️  Si el puerto está en uso, cambia FLASK_PORT en .env o desactiva AirPlay Receiver")
    
    # Verificar credenciales
    print(f"\n🔑 Verificación de credenciales:")
    print(f"   ✅ WHATSAPP_VERIFY_TOKEN: {'Configurado' if WHATSAPP_VERIFY_TOKEN else '❌ NO CONFIGURADO'}")
    print(f"   {'✅' if WHATSAPP_TOKEN else '❌'} WHATSAPP_TOKEN: {'Configurado' if WHATSAPP_TOKEN else 'NO CONFIGURADO (necesario para enviar mensajes)'}")
    print(f"   {'✅' if WHATSAPP_PHONE_NUMBER_ID else '❌'} WHATSAPP_PHONE_NUMBER_ID: {'Configurado' if WHATSAPP_PHONE_NUMBER_ID else 'NO CONFIGURADO (necesario para enviar mensajes)'}")
    print(f"   {'✅' if os.getenv('OPENAI_API_KEY') else '❌'} OPENAI_API_KEY: {'Configurado' if os.getenv('OPENAI_API_KEY') else 'NO CONFIGURADO (necesario para el agente)'}")
    
    # Ejecutar servidor
    app.run(host="0.0.0.0", port=PORT, debug=True)

