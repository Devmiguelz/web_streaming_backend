import json
import os
import sys
import smtplib
from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ==================== CONFIGURACIÓN DE LA APP ====================
if sys.platform == 'win32':
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
else:
    app = Flask(__name__)

# Configurar rate limiting
limiter = Limiter(
    get_remote_address,  # Función para identificar al cliente (por IP)
    app=app,
    default_limits=[],  # Límites por defecto
    storage_uri="memory://",  # Backend de almacenamiento
    strategy="fixed-window"  # Estrategia de conteo
)

# Obtener el entorno
ENV = os.environ.get('FLASK_ENV', 'production')

if ENV == 'development':
    # En desarrollo: permitir localhost
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5400",
                "http://127.0.0.1:5400"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    print("🔧 CORS configurado para DESARROLLO")
else:
    ALLOWED_ORIGINS = [
        "https://web-streaming-frontend.pages.dev",  
        "https://cinevo.lat"            
    ]
    
    CORS(app, resources={
        r"/api/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    print(f"🔒 CORS configurado para PRODUCCIÓN: {ALLOWED_ORIGINS}")

# Configuración
CACHE_DIR = 'cache'
PELICULAS_FILE = os.path.join(CACHE_DIR, 'peliculas.json')
SERIES_FILE = os.path.join(CACHE_DIR, 'series.json')

EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT'))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_DESTINATARIO = os.getenv('EMAIL_DESTINATARIO')

# Crear directorio de cache si no existe
os.makedirs(CACHE_DIR, exist_ok=True)

# ==================== UTILIDADES ====================

def cargar_json(archivo):
    """Carga datos desde un archivo JSON"""
    try:
        if os.path.exists(archivo):
            with open(archivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error cargando {archivo}: {e}")
        return []

def guardar_json(archivo, datos):
    """Guarda datos en un archivo JSON"""
    try:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error guardando {archivo}: {e}")
        return False

def paginar(items, pagina, por_pagina=20):
    """Pagina una lista de items"""
    inicio = (pagina - 1) * por_pagina
    fin = inicio + por_pagina
    total_paginas = (len(items) + por_pagina - 1) // por_pagina
    
    return {
        'items': items[inicio:fin],
        'pagina_actual': pagina,
        'total_paginas': total_paginas,
        'total_items': len(items),
        'items_por_pagina': por_pagina
    }

# ==================== RUTAS FRONTEND ====================

@app.route('/')
def index():
    """Página principal"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Servir archivos estáticos"""
    return send_from_directory(app.static_folder, path)

# ==================== API RELACIONADOS ====================

@app.route('/api/<tipo>/<item_id>/relacionados', methods=['GET'])
def obtener_relacionados(tipo, item_id):
    """
    Obtiene contenido relacionado por género y año
    Parámetros:
        - tipo: 'peliculas' o 'series'
        - item_id: ID del item actual
    Query params opcionales:
        - limite: cantidad de resultados (default: 10)
    """
    try:
        # Validar tipo
        if tipo not in ['peliculas', 'series']:
            return jsonify({'error': 'Tipo inválido'}), 400
        
        # Obtener el límite de resultados
        limite = request.args.get('limite', 10, type=int)
        if limite > 20:
            limite = 20  # Máximo 20 resultados
        
        # Cargar datos según el tipo
        archivo = PELICULAS_FILE if tipo == 'peliculas' else SERIES_FILE
        datos = cargar_json(archivo)
        
        if not datos:
            return jsonify({'error': 'No se pudieron cargar los datos'}), 500
        
        # Buscar el item actual
        item_actual = next((item for item in datos if item.get('id') == item_id), None)
        
        if not item_actual:
            return jsonify({'error': f'Item con ID {item_id} no encontrado'}), 404
        
        # Obtener géneros y año del item actual
        generos_actual = item_actual.get('generos', [])
        año_actual = item_actual.get('año')
        
        # Calcular relacionados con puntuación
        relacionados = []
        
        for item in datos:
            # Saltar el item actual
            if item == item_actual:
                continue
            
            puntuacion = 0
            
            # Puntos por géneros compartidos
            generos_item = item.get('generos', [])
            if generos_actual and generos_item:
                generos_comunes = set(generos_actual) & set(generos_item)
                puntuacion += len(generos_comunes) * 3  # 3 puntos por género común
            
            # Puntos por año cercano
            año_item = item.get('año')
            if año_actual and año_item:
                try:
                    diferencia_años = abs(int(año_actual) - int(año_item))
                    if diferencia_años == 0:
                        puntuacion += 5
                    elif diferencia_años <= 1:
                        puntuacion += 3
                    elif diferencia_años <= 3:
                        puntuacion += 2
                    elif diferencia_años <= 5:
                        puntuacion += 1
                except (ValueError, TypeError):
                    pass
            
            # Solo incluir si tiene alguna relación
            if puntuacion > 0:
                relacionados.append({
                    'item': item,
                    'puntuacion': puntuacion
                })
        
        # Ordenar por puntuación descendente
        relacionados.sort(key=lambda x: x['puntuacion'], reverse=True)
        
        # Limitar resultados
        relacionados = relacionados[:limite]
        
        # Extraer solo los items (sin la puntuación)
        resultado = [r['item'] for r in relacionados]
        
        return jsonify({
            'relacionados': resultado,
            'total': len(resultado),
            'item_actual': {
                'id': item_id,
                'titulo': item_actual.get('titulo') or item_actual.get('nombre'),
                'generos': generos_actual,
                'año': año_actual
            }
        })
    
    except Exception as e:
        print(f'Error obteniendo relacionados: {str(e)}')
        return jsonify({'error': 'Error procesando la solicitud'}), 500

# ==================== API PELÍCULAS ====================

@app.route('/api/peliculas')
def listar_peliculas():
    """Lista todas las películas con paginación"""
    peliculas = cargar_json(PELICULAS_FILE)
    
    # Parámetros de consulta
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = request.args.get('por_pagina', 20, type=int)
    genero = request.args.get('genero', None)
    año = request.args.get('año', None)
    calidad = request.args.get('calidad', None)
    ordenar = request.args.get('ordenar', 'reciente')
    
    # Filtrar
    if genero:
        peliculas = [p for p in peliculas if genero in p.get('generos', [])]
    
    if año:
        peliculas = [p for p in peliculas if str(p.get('año', '')) == str(año)]
    
    if calidad:
        peliculas = [p for p in peliculas if p.get('calidad', '') == calidad]
    
    # Ordenar
    if ordenar == 'titulo':
        peliculas.sort(key=lambda x: x.get('titulo', ''))
    elif ordenar == 'año':
        peliculas.sort(key=lambda x: x.get('año', 0), reverse=True)
    
    # Paginar
    resultado = paginar(peliculas, pagina, por_pagina)
    
    return jsonify(resultado)

@app.route('/api/peliculas/buscar')
def buscar_peliculas():
    """Busca películas por título"""
    query = request.args.get('q', '').lower()
    pagina = request.args.get('pagina', 1, type=int)
    
    if not query:
        return jsonify({'error': 'Se requiere un término de búsqueda'}), 400
    
    peliculas = cargar_json(PELICULAS_FILE)
    
    # Buscar en título y descripción
    resultados = [
        p for p in peliculas 
        if query in p.get('titulo', '').lower() or 
           query in p.get('descripcion', '').lower()
    ]
    
    return jsonify(paginar(resultados, pagina))

@app.route('/api/pelicula/<string:id>')
def detalle_pelicula(id):
    """Obtiene el detalle de una película"""
    peliculas = cargar_json(PELICULAS_FILE)
    
    if not peliculas:
        return jsonify({'error': 'No se pudieron cargar los datos'}), 500
    
    pelicula = next((p for p in peliculas if p.get('id') == id), None)
    
    if pelicula:
        return jsonify(pelicula)
    
    return jsonify({'error': 'Película no encontrada'}), 404

@app.route('/api/pelicula/url/<path:url>')
def pelicula_por_url(url):
    """Obtiene película por su URL original"""
    peliculas = cargar_json(PELICULAS_FILE)
    
    for pelicula in peliculas:
        if pelicula.get('enlace') == url or pelicula.get('url_pelicula') == url:
            return jsonify(pelicula)
    
    return jsonify({'error': 'Película no encontrada'}), 404

# ==================== API SERIES ====================

@app.route('/api/series')
def listar_series():
    """Lista todas las series con paginación"""
    series = cargar_json(SERIES_FILE)
    
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = request.args.get('por_pagina', 20, type=int)
    genero = request.args.get('genero', None)
    ordenar = request.args.get('ordenar', 'reciente')
    
    if genero:
        series = [s for s in series if genero in s.get('generos', [])]
    
    if ordenar == 'titulo':
        series.sort(key=lambda x: x.get('titulo', ''))
    
    resultado = paginar(series, pagina, por_pagina)
    
    return jsonify(resultado)

@app.route('/api/series/buscar')
def buscar_series():
    """Busca series por título"""
    query = request.args.get('q', '').lower()
    pagina = request.args.get('pagina', 1, type=int)
    
    if not query:
        return jsonify({'error': 'Se requiere un término de búsqueda'}), 400
    
    series = cargar_json(SERIES_FILE)
    
    resultados = [
        s for s in series 
        if query in s.get('titulo', '').lower() or 
           query in s.get('descripcion', '').lower()
    ]
    
    return jsonify(paginar(resultados, pagina))

@app.route('/api/serie/<string:id>')
def detalle_serie(id):
    """Obtiene el detalle completo de una serie"""
    series = cargar_json(SERIES_FILE)
    
    serie = next((p for p in series if p.get('id') == id), None)

    if serie:
        return jsonify(serie)
    
    return jsonify({'error': 'Serie no encontrada'}), 404

@app.route('/api/serie/url/<path:url>')
def serie_por_url(url):
    """Obtiene serie por su URL original"""
    series = cargar_json(SERIES_FILE)
    
    for serie in series:
        if serie.get('url_serie') == url:
            return jsonify(serie)
    
    return jsonify({'error': 'Serie no encontrada'}), 404

# ==================== API GÉNEROS ====================

@app.route('/api/generos/peliculas')
def generos_peliculas():
    """Lista todos los géneros de películas"""
    peliculas = cargar_json(PELICULAS_FILE)
    generos = set()
    
    for pelicula in peliculas:
        generos.update(pelicula.get('generos', []))
    
    return jsonify(sorted(list(generos)))

@app.route('/api/generos/series')
def generos_series():
    """Lista todos los géneros de series"""
    series = cargar_json(SERIES_FILE)
    generos = set()
    
    for serie in series:
        generos.update(serie.get('generos', []))
    
    return jsonify(sorted(list(generos)))

# ==================== API ESTADÍSTICAS ====================

@app.route('/api/stats')
def estadisticas():
    """Obtiene estadísticas generales"""
    peliculas = cargar_json(PELICULAS_FILE)
    series = cargar_json(SERIES_FILE)
    
    total_episodios = sum(
        len(temp.get('episodios', []))
        for serie in series
        for temp in serie.get('temporadas', [])
    )
    
    return jsonify({
        'total_peliculas': len(peliculas),
        'total_series': len(series),
        'total_episodios': total_episodios,
        'ultima_actualizacion': datetime.now().isoformat()
    })

# ==================== ADMINISTRACIÓN ====================

@app.route('/api/admin/actualizar', methods=['POST'])
def actualizar_datos():
    """Endpoint para actualizar datos desde los scrapers"""
    # IMPORTANTE: Agregar autenticación aquí
    
    data = request.get_json()
    tipo = data.get('tipo')
    datos = data.get('datos')
    
    if tipo == 'peliculas':
        if guardar_json(PELICULAS_FILE, datos):
            return jsonify({'mensaje': 'Películas actualizadas'})
    
    elif tipo == 'series':
        if guardar_json(SERIES_FILE, datos):
            return jsonify({'mensaje': 'Series actualizadas'})
    
    return jsonify({'error': 'Error al actualizar'}), 500

@app.route('/api/contacto', methods=['POST'])
@limiter.limit("5 per hour")
def contacto():
    """
    Endpoint para recibir mensajes del formulario de contacto
    """
    try:
        # Obtener datos del formulario
        data = request.get_json()
        
        # Validar campos requeridos
        campos_requeridos = ['nombre', 'email', 'asunto', 'mensaje']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({
                    'error': f'El campo {campo} es requerido'
                }), 400
        
        nombre = data.get('nombre').strip()
        email = data.get('email').strip()
        asunto = data.get('asunto').strip()
        mensaje = data.get('mensaje').strip()
        
        # Validación básica de email
        if '@' not in email or '.' not in email:
            return jsonify({
                'error': 'Email inválido'
            }), 400
        
        # Validar longitud de campos
        if len(nombre) < 2 or len(nombre) > 100:
            return jsonify({
                'error': 'El nombre debe tener entre 2 y 100 caracteres'
            }), 400
        
        if len(mensaje) < 10 or len(mensaje) > 5000:
            return jsonify({
                'error': 'El mensaje debe tener entre 10 y 5000 caracteres'
            }), 400
        
        # Enviar el email
        if enviar_email(nombre, email, asunto, mensaje):
            return jsonify({
                'mensaje': 'Mensaje enviado con éxito',
                'status': 'success'
            }), 200
        else:
            return jsonify({
                'error': 'Error al enviar el mensaje. Por favor, intenta de nuevo.'
            }), 500
    
    except Exception as e:
        print(f'Error en endpoint contacto: {str(e)}')
        return jsonify({
            'error': 'Error procesando la solicitud'
        }), 500

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Error interno del servidor'}), 500

# ==================== ENVIO DE CORREO ====================

def enviar_email(nombre, email, asunto, mensaje):
    """
    Envía un email usando SMTP
    """
    try:
        # Crear el mensaje
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[Cinevo Contacto] {asunto}'
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_DESTINATARIO
        msg['Reply-To'] = email
        
        # Contenido del email en texto plano
        texto_plano = f"""
        Nuevo mensaje de contacto desde Cinevo
        
        Nombre: {nombre}
        Email: {email}
        Asunto: {asunto}
        Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        Mensaje:
        {mensaje}
        """
        
        # Contenido del email en HTML
        html = f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f4f4f4;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #e50914, #b20710);
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                    }}
                    .content {{
                        background: white;
                        padding: 20px;
                        border-radius: 0 0 5px 5px;
                    }}
                    .info-item {{
                        margin: 10px 0;
                        padding: 10px;
                        background: #f9f9f9;
                        border-left: 3px solid #e50914;
                    }}
                    .label {{
                        font-weight: bold;
                        color: #e50914;
                    }}
                    .mensaje {{
                        background: #f9f9f9;
                        padding: 15px;
                        border-radius: 5px;
                        margin-top: 15px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>🎬 Nuevo mensaje de Cinevo</h2>
                    </div>
                    <div class="content">
                        <div class="info-item">
                            <span class="label">Nombre:</span> {nombre}
                        </div>
                        <div class="info-item">
                            <span class="label">Email:</span> {email}
                        </div>
                        <div class="info-item">
                            <span class="label">Asunto:</span> {asunto}
                        </div>
                        <div class="info-item">
                            <span class="label">Fecha:</span> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                        </div>
                        <div class="mensaje">
                            <p class="label">Mensaje:</p>
                            <p>{mensaje.replace(chr(10), '<br>')}</p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Adjuntar ambas versiones
        parte_texto = MIMEText(texto_plano, 'plain', 'utf-8')
        parte_html = MIMEText(html, 'html', 'utf-8')
        
        msg.attach(parte_texto)
        msg.attach(parte_html)
        
        # Conectar al servidor SMTP y enviar
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()  # Seguridad TLS
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        return True
    
    except Exception as e:
        print(f'Error enviando email: {str(e)}')
        return False

# ==================== INICIO DEL SERVIDOR ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 API de Streaming iniciada")
    print("=" * 60)
    print(f"📁 Películas: {len(cargar_json(PELICULAS_FILE))}")
    print(f"📺 Series: {len(cargar_json(SERIES_FILE))}")
    print("=" * 60)
    print("🌐 Servidor corriendo en http://localhost:5400")
    print("=" * 60)

    if sys.platform == 'win32':
        from waitress import serve
        print("Running with Waitress on Windows...")
        serve(app, host='0.0.0.0', port=5400)
    else:
        print("Running Flask development server...")
        app.run(host='0.0.0.0', port=5400)