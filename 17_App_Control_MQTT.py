import json
import math
import random
import string
import threading
import time
from collections import deque
from datetime import datetime
from html import escape

import streamlit as st

try:
    import paho.mqtt.client as mqtt
except ImportError:  # se avisa en pantalla; la app no puede conectarse sin esta librería
    mqtt = None

try:
    from zoneinfo import ZoneInfo

    ZONA = ZoneInfo("America/Bogota")
except Exception:  # sin base de zonas horarias se usa la hora del servidor
    ZONA = None

st.set_page_config(
    page_title="Control MQTT · Daniel Flórez",
    page_icon="🎛️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# =====================================================================
#  AJUSTES  (los valores por defecto coinciden con el sketch de Wokwi)
# =====================================================================
BROKER_DEFECTO = "broker.hivemq.com"
PUERTO_DEFECTO = 1883
PREFIJO_DEFECTO = "dflorez/control17"   # debe ser idéntico a PREFIJO en el sketch de Wokwi

MAX_CONEXIONES = 4         # conexiones simultáneas permitidas en este servidor
INACTIVO_MAX = 900         # segundos sin uso tras los que se cierra una conexión
SIN_DATOS_AVISO = 10       # segundos sin noticias del ESP32 para mostrar una ayuda
REFRESCO_SEG = 2           # cada cuánto se actualiza el estado en pantalla
MAX_HISTORIAL_ORDENES = 15

# =====================================================================
#  ESTILO (paleta fría basada en #3f71a6)
# =====================================================================
PRIMARIO = "#3f71a6"
OSCURO = "#1b2f45"
CLARO = "#eaf2f9"
SUAVE = "#a9c7e3"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@500;600;700&display=swap');

:root, .stApp { color-scheme: light; }
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; font-size: 1.06rem; }
.stApp { background: linear-gradient(180deg, #f6fafd 0%, __CLARO__ 100%); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 860px; padding-top: 3rem; padding-bottom: 4rem; }
[data-testid="stHeaderActionElements"] { display: none !important; }

/* Texto de la página principal: siempre oscuro, aunque el navegador esté en modo oscuro */
.block-container p, .block-container li, .block-container label,
.block-container [data-testid="stMarkdownContainer"],
.block-container [data-testid="stWidgetLabel"] * { color: __OSCURO__; }
.block-container [data-testid="stCaptionContainer"] * { color: #4d6479 !important; }

/* Hero */
.hero { text-align: center; padding: 1rem 0 .5rem 0; }
.hero .etiqueta {
    color: __PRIMARIO__; letter-spacing: .25em; text-transform: uppercase;
    font-size: .85rem; font-weight: 600;
}
.hero h1 {
    font-family: 'Playfair Display', serif; font-size: 3.1rem; color: __OSCURO__;
    margin: .3rem 0 .6rem 0; line-height: 1.12;
}
.hero p { color: #4d6479 !important; font-size: 1.2rem; max-width: 640px; margin: 0 auto; }
.linea { width: 70px; height: 4px; border-radius: 4px; background: __PRIMARIO__; margin: 1.4rem auto; }
h2, h3 { font-family: 'Playfair Display', serif !important; color: __OSCURO__ !important; }

/* Tarjetas (contenedores con key="tarjeta_...") */
[class*="st-key-tarjeta"] {
    background: #ffffff !important;
    border: 1px solid __SUAVE__88 !important;
    border-radius: 18px !important;
    box-shadow: 0 8px 24px rgba(63, 113, 166, .08);
    padding: 1.4rem 1.5rem 1.3rem 1.5rem !important;
}
[class*="st-key-tarjeta"] p, [class*="st-key-tarjeta"] label, [class*="st-key-tarjeta"] li,
[class*="st-key-tarjeta"] [data-testid="stWidgetLabel"] * { color: __OSCURO__ !important; }

/*__CAMPOS__*/

/* Botones */
.stButton > button, .stDownloadButton > button {
    background: __PRIMARIO__; color: #ffffff !important; border: 1.5px solid __PRIMARIO__;
    border-radius: 999px; padding: .6rem 1.4rem; font-weight: 600; transition: all .2s ease;
}
.stButton > button p, .stDownloadButton > button p { color: #ffffff !important; }
.stButton > button:hover, .stDownloadButton > button:hover {
    background: __OSCURO__; border-color: __OSCURO__; transform: translateY(-2px);
}

/* Estado de la conexión */
.estado {
    display: inline-flex; align-items: center; gap: 10px; border-radius: 999px; padding: 7px 18px;
    font-weight: 600; font-size: .95rem; margin-bottom: .6rem;
}
.estado .punto { width: 11px; height: 11px; border-radius: 50%; background: currentColor; }
.estado.ok { background: #e8f6ef; color: #1f7a52 !important; }
.estado.espera { background: #fff6e0; color: #96630a !important; }
.estado.error { background: #fdecec; color: #b03030 !important; }
.estado.ok .punto { animation: pulso 1.6s ease-in-out infinite; }
@keyframes pulso { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .35; transform: scale(.75); } }
@media (prefers-reduced-motion: reduce) { .estado.ok .punto { animation: none; } }
.dato-linea { color: #4d6479 !important; font-size: .92rem; margin: .1rem 0 .8rem 0; }

/* Medidas */
.medidas { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin: .4rem 0; }
.medida {
    background: linear-gradient(160deg, #f6fafd, __CLARO__); border: 1px solid __SUAVE__99;
    border-radius: 16px; padding: 1.1rem 1.2rem; text-align: center;
}
.medida .nombre { font-size: .8rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: #4d6479 !important; }
.medida .valor { font-family: 'Playfair Display', serif; font-size: 3.2rem; line-height: 1.15; color: __PRIMARIO__ !important; font-weight: 700; }
.medida .unidad { font-size: 1.3rem; font-weight: 500; color: __OSCURO__ !important; }
.medida .delta { font-size: .85rem; color: #4d6479 !important; min-height: 1.2em; }

/* Mando */
.subtitulo { font-size: .8rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: #4d6479 !important; margin: 1rem 0 .4rem 0; }
[class*="st-key-sec_"] button { background: #ffffff; border: 1.5px solid __PRIMARIO__; }
[class*="st-key-sec_"] button p { color: __PRIMARIO__ !important; }
[class*="st-key-sec_"] button:hover { background: __CLARO__; border-color: __PRIMARIO__; }
[class*="st-key-sec_"] button:hover p { color: __OSCURO__ !important; }

/* Piezas del dispositivo */
.piezas { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: .4rem 0; }
.pieza { background: linear-gradient(160deg, #f6fafd, __CLARO__); border: 1px solid __SUAVE__99; border-radius: 16px; padding: 1.1rem 1.2rem; text-align: center; }
.pieza .nombre { font-size: .8rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: #4d6479 !important; }
.pieza .lectura { font-family: 'Playfair Display', serif; font-size: 1.9rem; font-weight: 700; color: __PRIMARIO__ !important; margin-top: .2rem; }
.lampara { height: 96px; display: flex; align-items: center; justify-content: center; }
.bombillo { width: 62px; height: 62px; border-radius: 50%; background: #cfdbe7; border: 3px solid #b3c4d4; transition: all .3s ease; }
.lampara.encendido .bombillo { background: #ffd34d; border-color: #f0a030; box-shadow: 0 0 0 8px #ffd34d55, 0 0 34px 10px #ffd34daa; }
.lampara.desconocido .bombillo { background: #eef3f8; border-style: dashed; }
.medidor { width: 100%; max-width: 230px; height: auto; margin-top: .2rem; }
.medidor.desconocido { opacity: .55; }

/* Sidebar */
[data-testid="stSidebar"] { background: __OSCURO__; }
[data-testid="stSidebar"] * { color: #e6f0f9 !important; }

#MainMenu, footer { visibility: hidden; }
</style>
"""


def inyectar_css() -> None:
    css = CSS.replace("/*__CAMPOS__*/", CSS_CAMPOS)
    for token, valor in {
        "__PRIMARIO__": PRIMARIO, "__OSCURO__": OSCURO, "__CLARO__": CLARO, "__SUAVE__": SUAVE,
    }.items():
        css = css.replace(token, valor)
    st.markdown(css, unsafe_allow_html=True)


CSS_CAMPOS = """
/* ---- Campos, selectores, desplegables y avisos: siempre claros (a prueba de modo oscuro) ---- */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stTextArea"] [data-baseweb="textarea"] {
    background-color: #ffffff !important; border: 1px solid __SUAVE__ !important;
    border-radius: 12px !important; box-shadow: none !important;
}
[data-testid="stTextInput"] [data-baseweb="input"] *,
[data-testid="stNumberInput"] [data-baseweb="input"] *,
[data-testid="stTextArea"] [data-baseweb="textarea"] * {
    background-color: transparent !important; border-color: transparent !important; box-shadow: none !important;
    color: __OSCURO__ !important; -webkit-text-fill-color: __OSCURO__ !important; fill: __OSCURO__ !important;
}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within,
[data-testid="stNumberInput"] [data-baseweb="input"]:focus-within,
[data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
    border-color: __PRIMARIO__ !important; box-shadow: 0 0 0 1px __PRIMARIO__ !important;
}
[data-testid="stTextInput"] input::placeholder { color: #7d93a8 !important; -webkit-text-fill-color: #7d93a8 !important; opacity: 1; }

/* Avisos (st.info, st.warning, st.error, st.success) */
[data-testid="stAlert"] { --alerta-fondo: __CLARO__; --alerta-borde: __SUAVE__; }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { --alerta-fondo: #fff6e0; --alerta-borde: #f2d08a; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { --alerta-fondo: #fdecec; --alerta-borde: #f0b4b4; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { --alerta-fondo: #e8f6ef; --alerta-borde: #a6d8bf; }
[data-testid="stAlert"] {
    background-color: var(--alerta-fondo) !important; border: 1px solid var(--alerta-borde) !important;
    border-radius: 14px !important; overflow: hidden;
}
[data-testid="stAlert"] > div, [data-testid="stAlert"] [data-baseweb="notification"] {
    background-color: var(--alerta-fondo) !important; border: none !important; border-radius: 14px !important;
}
[data-testid="stAlert"] * { color: __OSCURO__ !important; -webkit-text-fill-color: __OSCURO__ !important; }
[data-testid="stAlert"] p, [data-testid="stAlert"] span, [data-testid="stAlert"] div { background-color: transparent !important; }

/* Desplegables (st.expander): la barra del título también es clara */
[data-testid="stExpander"] details {
    background-color: #ffffff !important; border: 1px solid __SUAVE__88 !important; border-radius: 16px !important;
    box-shadow: 0 8px 24px rgba(63, 113, 166, .08); overflow: hidden;
}
[data-testid="stExpander"] summary { background-color: #ffffff !important; }
[data-testid="stExpander"] summary:hover { background-color: __CLARO__ !important; }
[data-testid="stExpander"] summary * { background-color: transparent !important; color: __OSCURO__ !important; fill: __OSCURO__ !important; }
[data-testid="stExpander"] p, [data-testid="stExpander"] li, [data-testid="stExpander"] label { color: __OSCURO__ !important; }
[data-testid="stExpander"] svg { fill: __OSCURO__ !important; color: __OSCURO__ !important; }

/* Interruptor (st.toggle) */
[data-testid="stCheckbox"] label, [data-testid="stToggle"] label { color: __OSCURO__ !important; }

/* El menú con el cambio de tema se oculta: esta página está diseñada solo en claro */
[data-testid="stMainMenu"] { display: none !important; }
"""


# =====================================================================
#  CONEXIÓN MQTT
#
#  Esta vez la app PUBLICA órdenes y además ESCUCHA el estado del ESP32:
#    app  --(publica)-->  <prefijo>/orden   --> broker --> ESP32 (suscrito)
#    app  <--(suscrita)-- <prefijo>/estado  <-- broker <-- ESP32 (publica, retenido)
#  Así la página no solo "manda", también muestra lo que el dispositivo CONFIRMA.
# =====================================================================
def crear_cliente_paho(id_cliente: str):
    """Crea el cliente MQTT; funciona igual con paho-mqtt 1.x y 2.x."""
    if mqtt is None:
        raise RuntimeError("Falta la librería paho-mqtt en requirements.txt")
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=id_cliente)  # paho 2.x
    except AttributeError:
        return mqtt.Client(client_id=id_cliente)  # paho 1.x


def prefijo_valido(prefijo: str) -> str:
    """Devuelve '' si el prefijo sirve, o el motivo por el que no."""
    if not prefijo:
        return "Escribe un prefijo de tópicos."
    if any(c in prefijo for c in "+#") or " " in prefijo:
        return "El prefijo no puede tener espacios ni los símbolos + o #."
    if prefijo.startswith(("/", "$")) or prefijo.endswith("/") or "//" in prefijo:
        return "El prefijo no debe empezar ni terminar con «/», ni empezar con «$»."
    if len(prefijo) > 100:
        return "El prefijo es demasiado largo."
    return ""


def interpretar_estado(texto: str) -> dict:
    """{'online': bool|None, 'led': 'ON'|'OFF'|None, 'servo': float|None} desde el JSON del ESP32."""
    salida = {"online": None, "led": None, "servo": None}
    try:
        dato = json.loads(texto)
    except ValueError:
        return salida
    if not isinstance(dato, dict):
        return salida
    if isinstance(dato.get("online"), bool):
        salida["online"] = dato["online"]
    if str(dato.get("led", "")).upper() in ("ON", "OFF"):
        salida["led"] = str(dato["led"]).upper()
    servo = dato.get("servo")
    if isinstance(servo, (int, float)) and not isinstance(servo, bool) and math.isfinite(servo):
        salida["servo"] = float(min(180.0, max(0.0, servo)))
    return salida


class Conexion:
    """Una conexión MQTT persistente: publica órdenes y guarda el último estado del ESP32."""

    def __init__(self, broker: str, puerto: int, prefijo: str, fabrica=None):
        self.broker, self.puerto, self.prefijo = broker, puerto, prefijo
        self.t_orden = f"{prefijo}/orden"
        self.t_estado = f"{prefijo}/estado"
        # ID único por conexión (si dos clientes comparten ID, el broker expulsa al anterior)
        sufijo = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.id_cliente = f"streamlit-ctrl-{sufijo}"
        self.conectado = False
        self.error = ""
        self.creado = time.time()
        self.ultimo_uso = self.creado
        self.dispositivo = {"online": None, "led": None, "servo": None}
        self.estado_hora = 0.0       # cuándo llegó el último estado
        self.estado_crudo = ""
        self.estado_retenido = False  # True si lo entregó el broker de su memoria (no en vivo)
        self.enviados = 0
        self._cerrojo = threading.Lock()

        self.cliente = (fabrica or crear_cliente_paho)(self.id_cliente)
        self.cliente.on_connect = self._al_conectar
        self.cliente.on_disconnect = self._al_desconectar
        self.cliente.on_connect_fail = self._al_fallar
        self.cliente.on_message = self._al_recibir
        self.cliente.reconnect_delay_set(min_delay=1, max_delay=15)
        self.cliente.connect_async(broker, puerto, keepalive=30)
        self.cliente.loop_start()

    # --- Hilo de paho ---
    def _al_conectar(self, cliente, userdata, flags, rc, *extra):
        codigo = getattr(rc, "value", rc)
        if codigo == 0:
            self.conectado = True
            self.error = ""
            cliente.subscribe(self.t_estado, qos=1)  # se repite en cada reconexión
        else:
            self.conectado = False
            self.error = f"El broker rechazó la conexión (código {codigo})."

    def _al_desconectar(self, cliente, userdata, *args):
        self.conectado = False

    def _al_fallar(self, cliente, userdata, *args):
        self.conectado = False
        self.error = (
            f"No se pudo conectar con {self.broker}:{self.puerto}. "
            "Revisa la dirección, el puerto o la conexión a internet."
        )

    def _al_recibir(self, cliente, userdata, mensaje):
        if mensaje.topic != self.t_estado:
            return
        texto = mensaje.payload.decode("utf-8", errors="replace")
        datos = interpretar_estado(texto)
        with self._cerrojo:
            self.estado_crudo = texto
            self.estado_hora = time.time()
            self.estado_retenido = bool(getattr(mensaje, "retain", False))
            if datos["online"] is False:
                # Testamento del ESP32: se apagó o perdió la red. Se conservan led/servo viejos.
                self.dispositivo["online"] = False
            else:
                self.dispositivo = {
                    "online": datos["online"] if datos["online"] is not None else True,
                    "led": datos["led"] or self.dispositivo["led"],
                    "servo": datos["servo"] if datos["servo"] is not None else self.dispositivo["servo"],
                }

    # --- Desde Streamlit ---
    def estado(self) -> str:
        if self.conectado:
            return "conectado"
        return "error" if self.error else "conectando"

    def lectura(self) -> tuple:
        with self._cerrojo:
            return dict(self.dispositivo), self.estado_hora, self.estado_retenido, self.estado_crudo

    def publicar(self, carga: dict, espera: float = 3.0) -> tuple:
        """Publica con QoS 1 y espera la confirmación del broker. Devuelve (ok, texto)."""
        if not self.conectado:
            return False, "Todavía no hay conexión con el broker. Espera unos segundos y vuelve a intentar."
        try:
            info = self.cliente.publish(self.t_orden, json.dumps(carga), qos=1)
        except Exception as error:  # noqa: BLE001 - se muestra al usuario tal cual
            return False, f"No se pudo enviar: {error}"
        if info.rc != 0:
            return False, f"El envío falló (código {info.rc}). Revisa la conexión."
        limite = time.time() + espera
        while time.time() < limite:
            if info.is_published():
                self.enviados += 1
                return True, "El broker recibió la orden."
            time.sleep(0.05)
        return False, "El broker no confirmó la orden a tiempo. Intenta de nuevo."

    def detener(self) -> None:
        try:
            self.cliente.disconnect()
            self.cliente.loop_stop()
        except Exception:
            pass


@st.cache_resource
def registro() -> dict:
    return {"cerrojo": threading.Lock(), "conexiones": {}}


def obtener_conexion(broker: str, puerto: int, prefijo: str) -> Conexion:
    reg = registro()
    clave = (broker, puerto, prefijo)
    ahora = time.time()
    with reg["cerrojo"]:
        activas = reg["conexiones"]
        for k, c in list(activas.items()):
            if k != clave and ahora - c.ultimo_uso > INACTIVO_MAX:
                c.detener()
                del activas[k]
        conexion = activas.get(clave)
        if conexion is None:
            while len(activas) >= MAX_CONEXIONES:
                k_viejo = min(activas, key=lambda k: activas[k].ultimo_uso)
                activas.pop(k_viejo).detener()
            conexion = Conexion(broker, puerto, prefijo)
            activas[clave] = conexion
        conexion.ultimo_uso = ahora
        return conexion


# =====================================================================
#  DIBUJOS (lámpara del LED y medidor del servo)
# =====================================================================
def hace_cuanto(segundos: float) -> str:
    segundos = max(0, int(segundos))
    if segundos < 60:
        return f"hace {segundos} s"
    return f"hace {segundos // 60} min {segundos % 60} s"


def html_led(estado) -> str:
    clase = {"ON": "encendido", "OFF": "apagado"}.get(estado, "desconocido")
    texto = {"ON": "Encendido", "OFF": "Apagado"}.get(estado, "Sin datos")
    return (
        '<div class="pieza"><div class="nombre">LED (GPIO 2)</div>'
        f'<div class="lampara {clase}"><span class="bombillo"></span></div>'
        f'<div class="lectura">{texto}</div></div>'
    )


def html_servo(angulo) -> str:
    """Medidor semicircular: 0° a la izquierda, 180° a la derecha."""
    if angulo is None:
        aguja, texto, clase = "", "Sin datos", "desconocido"
    else:
        rad = math.radians(angulo)
        x, y = 100 - 68 * math.cos(rad), 100 - 68 * math.sin(rad)
        aguja = (
            f'<line x1="100" y1="100" x2="{x:.1f}" y2="{y:.1f}" stroke="{OSCURO}" '
            'stroke-width="5" stroke-linecap="round"/>'
        )
        texto, clase = f"{angulo:.0f}°", ""
    return (
        '<div class="pieza"><div class="nombre">Servo (GPIO 13)</div>'
        f'<svg class="medidor {clase}" viewBox="0 0 200 118" role="img" aria-label="Ángulo del servo: {escape(texto)}">'
        f'<path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="{CLARO}" stroke-width="16" stroke-linecap="round"/>'
        f'<path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="{SUAVE}" stroke-width="2" stroke-dasharray="2 8"/>'
        f"{aguja}"
        f'<circle cx="100" cy="100" r="8" fill="{PRIMARIO}"/>'
        '<text x="20" y="116" font-size="11" text-anchor="middle" fill="#4d6479">0°</text>'
        '<text x="180" y="116" font-size="11" text-anchor="middle" fill="#4d6479">180°</text>'
        "</svg>"
        f'<div class="lectura">{escape(texto)}</div></div>'
    )


def describir_dispositivo(conexion: Conexion) -> tuple:
    """(clase CSS, texto del distintivo, ayuda o None) según lo que informa el ESP32."""
    estado = conexion.estado()
    ahora = time.time()
    if estado == "error":
        return "error", "Sin conexión con el broker", conexion.error
    if estado == "conectando":
        ayuda = None
        if ahora - conexion.creado > SIN_DATOS_AVISO:
            ayuda = "Está tardando más de lo normal. Revisa el broker y el puerto en «Ajustes de conexión»."
        return "espera", "Conectando al broker…", ayuda
    dispositivo, hora, _retenido, _crudo = conexion.lectura()
    if hora == 0.0:
        ayuda = None
        if ahora - conexion.creado > SIN_DATOS_AVISO:
            ayuda = (
                "Hay conexión con el broker, pero el ESP32 todavía no ha informado su estado. "
                "¿Está corriendo la simulación en Wokwi? ¿El PREFIJO del sketch es idéntico al de esta página?"
            )
        return "espera", "Broker conectado · esperando al ESP32", ayuda
    if dispositivo["online"] is False:
        return "error", "ESP32 desconectado", (
            "El broker avisó que el ESP32 se desconectó (apagaste la simulación o perdió la red). "
            "Los valores de abajo son los últimos que informó."
        )
    return "ok", "ESP32 en línea", None


# =====================================================================
#  ÓRDENES (se ejecutan al pulsar un botón, antes de redibujar la página)
# =====================================================================
def registrar_envio(descripcion: str, ok: bool, detalle: str) -> None:
    historial = st.session_state.setdefault("historial", [])
    historial.insert(0, (time.time(), descripcion, ok))
    del historial[MAX_HISTORIAL_ORDENES:]
    st.session_state["resultado"] = (ok, f"{descripcion}: {detalle}")


def enviar_orden(estado_led: str) -> None:
    conexion = obtener_conexion(*st.session_state["cfg"])
    ok, detalle = conexion.publicar({"Act1": estado_led})
    registrar_envio(f"LED {'encendido' if estado_led == 'ON' else 'apagado'}", ok, detalle)


def enviar_servo(valor=None) -> None:
    """valor=None envía lo que marca el deslizador; con un número, ese preset."""
    if valor is not None:
        st.session_state["valor_servo"] = int(valor)  # mueve también el deslizador
    valor = float(st.session_state["valor_servo"])
    conexion = obtener_conexion(*st.session_state["cfg"])
    ok, detalle = conexion.publicar({"Analog": valor})
    registrar_envio(f"Servo a {valor:.0f} % ({valor * 1.8:.0f}°)", ok, detalle)


# =====================================================================
#  PÁGINA
# =====================================================================
inyectar_css()

with st.sidebar:
    st.subheader("Cómo funciona")
    st.markdown(
        "1. Al pulsar un botón, esta página **publica** una orden en el tópico `…/orden`.\n"
        "2. El **broker** MQTT la recibe y confirma.\n"
        "3. El ESP32 de Wokwi está **suscrito** a ese tópico: enciende el LED o mueve el servo.\n"
        "4. El ESP32 **publica su estado** en `…/estado` y esta página lo muestra: "
        "así ves lo que el dispositivo realmente hizo."
    )
    st.subheader("Privacidad")
    st.markdown(
        "El broker público es compartido: cualquiera que conozca el prefijo puede mandar órdenes. "
        "Usa un prefijo propio y no lo publiques."
    )

st.markdown(
    """
    <div class="hero">
        <div class="etiqueta">Internet de las cosas</div>
        <h1>Control remoto</h1>
        <p>Enciende un LED y mueve un servo en un ESP32 simulado en Wokwi, enviando órdenes por MQTT.</p>
        <div class="linea"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if mqtt is None:
    st.error("Falta la librería `paho-mqtt`. Agrégala a `requirements.txt` y reinicia la app.")
    st.stop()

with st.container(key="tarjeta_conexion"):
    st.subheader("Conexión")
    st.caption(
        "Los valores por defecto ya funcionan con el sketch incluido. "
        "Si cambias el prefijo aquí, cámbialo igual en el sketch."
    )
    with st.expander("Ajustes de conexión"):
        broker = st.text_input("Broker MQTT", value=BROKER_DEFECTO, help="Dirección del servidor MQTT").strip()
        puerto = st.number_input("Puerto", value=PUERTO_DEFECTO, min_value=1, max_value=65535, step=1,
                                 help="1883 es el puerto estándar sin cifrado.")
        prefijo = st.text_input(
            "Prefijo de tópicos", value=PREFIJO_DEFECTO,
            help="Las órdenes van a «prefijo/orden» y el estado llega por «prefijo/estado».",
        ).strip()
    st.caption("Auto-actualizar el estado cada 2 s está activado.")

error_prefijo = prefijo_valido(prefijo)
if not broker or " " in broker:
    st.error("Escribe una dirección de broker válida (sin espacios).")
    st.stop()
if error_prefijo:
    st.error(error_prefijo)
    st.stop()

try:
    conexion = obtener_conexion(broker, int(puerto), prefijo)
except Exception as error:
    st.error(f"No se pudo iniciar la conexión: {error}")
    st.stop()
st.session_state["cfg"] = (broker, int(puerto), prefijo)
st.session_state.setdefault("valor_servo", 50)

st.write("")
with st.container(key="tarjeta_mando"):
    st.subheader("Mando")

    st.markdown('<div class="subtitulo">LED</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("Encender", key="led_on", on_click=enviar_orden, args=("ON",), use_container_width=True)
    with c2:
        st.button("Apagar", key="sec_led_off", on_click=enviar_orden, args=("OFF",), use_container_width=True)

    st.markdown('<div class="subtitulo">Servo</div>', unsafe_allow_html=True)
    st.slider(
        "Posición del servo (%)", min_value=0, max_value=100, step=1, key="valor_servo",
        help="0 % = 0° y 100 % = 180°.",
    )
    p0, p1, p2, p3 = st.columns(4)
    for col, (nombre, v) in zip((p0, p1, p2), (("0°", 0), ("90°", 50), ("180°", 100))):
        with col:
            st.button(nombre, key=f"sec_preset_{v}", on_click=enviar_servo, args=(v,), use_container_width=True)
    with p3:
        st.button("Enviar", key="servo_enviar", on_click=enviar_servo, use_container_width=True)

    resultado = st.session_state.get("resultado")
    if resultado:
        ok, texto = resultado
        (st.success if ok else st.error)(texto)
    else:
        st.caption("Aquí verás si el broker recibió cada orden.")

    historial = st.session_state.get("historial", [])
    if historial:
        with st.expander("Órdenes enviadas"):
            for epoch, descripcion, ok in historial:
                marca = "✓" if ok else "✗"
                st.markdown(f"{marca} {hora_local(epoch):%H:%M:%S} · {descripcion}")

st.write("")


@st.fragment(run_every=REFRESCO_SEG)
def panel() -> None:
    conexion.ultimo_uso = time.time()
    clase, texto_estado, ayuda = describir_dispositivo(conexion)
    dispositivo, hora, retenido, crudo = conexion.lectura()

    with st.container(key="tarjeta_dispositivo"):
        st.subheader("Estado del dispositivo")
        st.markdown(
            f'<div class="estado {clase}"><span class="punto"></span>{escape(texto_estado)}</div>',
            unsafe_allow_html=True,
        )
        detalle = f"{escape(conexion.broker)}:{conexion.puerto} · prefijo {escape(conexion.prefijo)}"
        if hora:
            detalle += f" · último estado {hace_cuanto(time.time() - hora)}"
            if retenido:
                detalle += " (guardado en el broker)"
        st.markdown(f'<div class="dato-linea">{detalle}</div>', unsafe_allow_html=True)
        if ayuda:
            st.warning(ayuda)
        st.markdown(
            '<div class="piezas">' + html_led(dispositivo["led"]) + html_servo(dispositivo["servo"]) + "</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    with st.expander("Detalles técnicos"):
        st.markdown(
            f"- **Broker:** `{conexion.broker}` · **puerto:** `{conexion.puerto}` (MQTT sin cifrar)\n"
            f"- **Tópico de órdenes:** `{conexion.t_orden}` · **QoS:** 1\n"
            f"- **Tópico de estado:** `{conexion.t_estado}` · **QoS:** 1 (retenido por el ESP32)\n"
            f"- **ID de cliente de esta app:** `{conexion.id_cliente}`\n"
            f"- **Órdenes confirmadas por el broker:** {conexion.enviados}"
        )
        if crudo:
            st.caption("Último estado crudo recibido:")
            st.code(crudo, language="json")


panel()
