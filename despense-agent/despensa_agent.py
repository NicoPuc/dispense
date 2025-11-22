"""
Agente de Despensa usando LangGraph
Simula la gestión de inventario de una despensa mediante un agente conversacional.
Soporta entradas multimodales: texto, audio e imágenes.
"""

import os
import base64
from typing import TypedDict, Annotated, Literal, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from openai import OpenAI
from prompts import SYSTEM_PROMPT

# Cargar variables de entorno
load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Inicializar cliente de OpenAI para APIs multimodales
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ============================================================================
# BASE DE DATOS SIMULADA (Diccionario global)
# ============================================================================
DESPENSA_DB = {
    "leche": "BAJO",
    "huevos": "ALTO",
    "pan": "MEDIO",
    "azúcar": "ALTO",
    "aceite": "MEDIO",
    "arroz": "BAJO",
    "fideos": "ALTO",
}

# ============================================================================
# ESTADO DEL GRAFO
# ============================================================================
class AgentState(TypedDict):
    """Estado del agente que mantiene el historial de conversación, input del usuario y archivos multimedia."""
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str
    media_file_path: Optional[str]  # Ruta del archivo multimedia (audio o imagen)


# ============================================================================
# HERRAMIENTAS (TOOLS)
# ============================================================================
@tool
def consultar_despensa(item_name: str = None) -> str:
    """
    Consulta el estado actual de items en la despensa.
    
    Args:
        item_name: (Opcional) Nombre específico del ítem a consultar. Si es None, lista todo.
    
    Returns:
        Estado del ítem o lista de ítems relevantes.
    """
    if item_name:
        item_name_lower = item_name.lower().strip()
        # Búsqueda parcial simple
        found = {k: v for k, v in DESPENSA_DB.items() if item_name_lower in k}
        
        if not found:
            return f"Pucha, no encontré nada parecido a '{item_name}' en la despensa."
        
        result = "Esto encontré:\n"
        for k, v in found.items():
            result += f"- {k.capitalize()}: {v}\n"
        return result
    else:
        # Listar todo
        if not DESPENSA_DB:
            return "La despensa está vacía, ¡hay que comprar de todo!"
        
        result = "Acá está el reporte de tu despensa:\n"
        for k, v in DESPENSA_DB.items():
            result += f"- {k.capitalize()}: {v}\n"
        return result


@tool
def actualizar_despensa(description: str, operation_type: Literal["in", "out", "update"]) -> str:
    """
    Actualiza el inventario de la despensa basándose en una descripción natural.
    
    Args:
        description: Texto que describe los productos y cantidades (ej: "2 cajas de leche", "se acabó el arroz").
        operation_type: Tipo de operación:
            - "in": Entrada de productos (compras, regalos).
            - "out": Salida de productos (consumo, pérdidas).
            - "update": Corrección directa del stock ("tengo 3, no 2").
    
    Returns:
        Confirmación de la acción realizada.
    """
    # Aquí iría la llamada a la API real que procesa el texto con IA estructurada.
    # Por ahora simulamos la lógica básica.
    
    print(f"\n[API MOCK] Procesando '{operation_type}' con descripción: '{description}'")
    
    # Simulación simple: buscar palabras clave en la descripción
    affected_items = []
    for item in DESPENSA_DB.keys():
        if item in description.lower():
            affected_items.append(item)
            
            # Lógica mock de actualización
            if operation_type == "in":
                DESPENSA_DB[item] = "ALTO" # Asumimos que si entra, queda alto
            elif operation_type == "out":
                DESPENSA_DB[item] = "BAJO" # Asumimos que si sale, queda bajo
            elif operation_type == "update":
                # En update real, extraeríamos la cantidad/estado del texto
                DESPENSA_DB[item] = "MEDIO" # Mock
    
    if not affected_items:
        return f"[API] Procesé la orden '{operation_type}' pero no reconocí productos específicos en mi DB simple. (En prod la IA lo haría)"
    
    action_map = {
        "in": "agregado a",
        "out": "sacado de",
        "update": "actualizado en"
    }
    
    items_str = ", ".join([i.capitalize() for i in affected_items])
    return f"¡Listo! He {action_map[operation_type]} tu despensa: {items_str}."


@tool
def consultar_reposicion_de_productos() -> str:
    """
    Calcula y devuelve una lista de compras sugerida basada en el stock crítico y consumo del usuario.
    
    Returns:
        Lista de productos sugeridos para comprar (Shopping List).
    """
    print("\n[TEST] - Consulta sobre reposicion de productos")
    
    # Lógica mock: recomendar todo lo que esté en "BAJO"
    shopping_list = [k for k, v in DESPENSA_DB.items() if v == "BAJO"]
    
    if not shopping_list:
        return "¡Buenas noticias! Tu despensa está tiki-taca, no necesitas comprar nada urgente."
    
    result = "Según mis cálculos, deberías reponer esto urgente:\n"
    for item in shopping_list:
        result += f"🛒 {item.capitalize()}\n"
        
    return result


# ============================================================================
# HERRAMIENTAS MULTIMODALES (TOOLS)
# ============================================================================
@tool
def transcribir_audio(audio_file_path: str) -> str:
    """
    Transcribe un archivo de audio a texto usando OpenAI Whisper API.
    """
    if not os.path.exists(audio_file_path):
        return f"Error: El archivo de audio '{audio_file_path}' no existe."
    
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es"
            )
        return transcript.text.strip()
    except Exception as e:
        return f"Error al transcribir audio: {str(e)}"


@tool
def procesar_imagen(image_file_path: str) -> str:
    """
    Procesa una imagen usando OpenAI Vision API para identificar productos.
    """
    if not os.path.exists(image_file_path):
        return f"Error: El archivo de imagen '{image_file_path}' no existe."
    
    try:
        # Leer y codificar
        file_ext = os.path.splitext(image_file_path)[1].lower()
        mime_type = "image/jpeg" if file_ext in ['.jpg', '.jpeg'] else f"image/{file_ext[1:]}"
        
        with open(image_file_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identifica los productos en esta imagen y lista qué ves (ej: '1 caja de leche, 2 manzanas'). Sé directo."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al procesar imagen: {str(e)}"


# ============================================================================
# NODO DEL AGENTE
# ============================================================================
def agent_node(state: AgentState) -> AgentState:
    """
    Nodo del agente que razona sobre la intención del usuario.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    messages = state["messages"]
    media_file_path = state.get("media_file_path")
    
    # Herramientas disponibles
    all_tools = [
        consultar_despensa,
        actualizar_despensa,
        consultar_reposicion_de_productos
    ]
    
    # Agregar herramientas multimodales si hay archivo
    if media_file_path:
        file_ext = os.path.splitext(media_file_path)[1].lower()
        if file_ext in ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac']:
            all_tools.append(transcribir_audio)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            all_tools.append(procesar_imagen)
            
    llm_with_tools = llm.bind_tools(all_tools)
    
    # Inyectar contexto multimodal si es necesario
    if media_file_path and not any(msg.content.startswith("El usuario ha enviado un archivo") for msg in messages if isinstance(msg, HumanMessage)):
         # Ya se maneja en run_agent, pero por seguridad
         pass

    # Inyectar System Prompt
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm_with_tools.invoke(messages)
    
    return {
        "messages": [response],
        "user_input": state["user_input"],
        "media_file_path": state.get("media_file_path")
    }


# ============================================================================
# ENRUTADOR
# ============================================================================
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


# ============================================================================
# GRAFO
# ============================================================================
def create_despensa_graph():
    workflow = StateGraph(AgentState)
    
    all_tools = [
        consultar_despensa,
        actualizar_despensa,
        consultar_reposicion_de_productos,
        transcribir_audio,
        procesar_imagen
    ]
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(all_tools))
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()


# ============================================================================
# EJECUCIÓN
# ============================================================================
def run_agent(user_input: str = "", chat_history: list[BaseMessage] = None, media_file_path: Optional[str] = None):
    app = create_despensa_graph()
    
    initial_messages = list(chat_history) if chat_history else []
    
    if user_input:
        initial_messages.append(HumanMessage(content=user_input))
    elif media_file_path:
        file_type = "audio" if os.path.splitext(media_file_path)[1].lower() in ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac'] else "imagen"
        initial_messages.append(HumanMessage(content=f"El usuario ha enviado un archivo {file_type}: {media_file_path}"))
    
    initial_state = {
        "messages": initial_messages,
        "user_input": user_input or "",
        "media_file_path": media_file_path
    }
    
    # LangGraph state updates are additive by default for lists, but we want to be careful
    result = app.invoke(initial_state)
    last_message = result["messages"][-1]
    
    return last_message.content


if __name__ == "__main__":
    print("🏪 Agente de Despensa (Modo Pruebas)")
    # ... lógica de prueba similar a la anterior ...
