import json
import os
import sys
import requests
import resend
import time
import uuid
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
from scraper.serie_scraper_live import scraper_serie_live
from service.cache_service import cache_service

USAR_PLAYWRIGHT = False
scraper_movie_live = None

try:
    print("🔍 Intentando cargar Playwright scraper...")
    from scraper.pelicula_scraper_playwright_v3 import scraper_movie_playwright_v3
    
    # Probar si Playwright puede ejecutarse
    print("🧪 Probando Playwright...")
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            browser.close()
            scraper_movie_live = scraper_movie_playwright_v3
            USAR_PLAYWRIGHT = True
            print("✅ Playwright scraper funcional")
        except Exception as e:
            print(f"⚠️ Playwright instalado pero no funcional: {e}")
            raise ImportError("Chromium dependencies missing")
            
except Exception as e:
    print(f"⚠️ Playwright no disponible: {e}")
    print("🔄 Cargando scraper simple...")
    try:
        from scraper.pelicula_scraper_live import scraper_movie_live
        print("✅ Scraper simple cargado exitosamente")
    except ImportError as e2:
        print(f"❌ Error crítico: No se pudo cargar ningún scraper: {e2}")
        scraper_movie_live = None

# Importar scraper de series
from scraper.serie_scraper_live import scraper_serie_live
from service.cache_service import cache_service

# Cargar variables de entorno
load_dotenv()

# ==================== CONFIGURACIÓN DE LA APP ====================
if sys.platform == 'win32':
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
else:
    app = Flask(__name__)

# Configurar rate limiting
limiter = Limiter(
    get_remote_address, 
    app=app,
    default_limits=[],  
    storage_uri="memory://",  
    strategy="fixed-window"  
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
DATABASE_DIR = 'database'
PELICULAS_FILE = os.path.join(DATABASE_DIR, 'peliculas_paginas.json')
SERIES_FILE = os.path.join(DATABASE_DIR, 'series_paginas.json')

resend.api_key = os.getenv('RESEND_API_KEY')
EMAIL_DESTINATARIO = os.getenv('EMAIL_DESTINATARIO')

# Crear directorio de cache si no existe
os.makedirs(DATABASE_DIR, exist_ok=True)

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

@app.route('/api/<tipo>/<slug>/relacionados', methods=['GET'])
def obtener_relacionados(tipo, slug):
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
        item_actual = next((item for item in datos if item.get('slug') == slug), None)
        
        if not item_actual:
            return jsonify({'error': f'Item con ID {slug} no encontrado'}), 404
        
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
                'id': item_actual.get('id'),
                'slug': slug,
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

@app.route('/api/pelicula/<string:slug>')
def pelicula_por_url(slug):
    """
    Obtiene película por su slug haciendo scraping en vivo
    
    Ejemplo: 
        GET /api/pelicula/url/steve
        -> Busca en https://cinecalidad.bar/peli/steve/
    
    Returns:
        JSON con toda la información de la película incluyendo servidores
    """
    try:
        cached_data = cache_service.get(slug)
        
        if cached_data:
            # Caché encontrada y válida
            response = jsonify(cached_data)
            response.headers['X-Cache'] = 'HIT'
            return response, 200
        
        resultado = scraper_movie_live.obtener_pelicula_por_slug(slug)
        
        if not resultado:
            return jsonify({
                'error': 'Película no encontrada',
                'slug': slug
            }), 404
        
        cache_service.set(slug, resultado)
        
        response = jsonify(resultado)
        response.headers['X-Cache'] = 'MISS'
        return response, 200
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify({
                'error': 'Película no encontrada',
                'slug': slug
            }), 404
        return jsonify({
            'error': f'Error HTTP: {e.response.status_code}',
            'detalle': str(e)
        }), 500
        
    except requests.exceptions.Timeout:
        return jsonify({
            'error': 'Timeout al conectar con el servidor',
            'slug': slug
        }), 504
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': 'Error de conexión',
            'detalle': str(e)
        }), 500

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

@app.route('/api/serie/<string:slug>')
def serie_info_basica(slug):
    """
    PASO 1: Obtiene solo información básica de la serie (RÁPIDO)
    - Título, descripción, imagen, géneros, etc.
    - Lista de temporadas disponibles (sin episodios)
    
    Ejemplo: /api/serie/la-nueva-brigada
    """
    try:
        # Intentar obtener del caché
        cache_key = f"serie_info_{slug}"
        cached_data = cache_service.get(cache_key)
        
        if cached_data:
            response = jsonify(cached_data)
            response.headers['X-Cache'] = 'HIT'
            return response, 200
        
        url_serie = f"{scraper_serie_live.base_url}/serie/{slug}/"
        
        http_response = scraper_serie_live.hacer_peticion_segura(url_serie)
        soup = BeautifulSoup(http_response.content, 'html.parser')
        
        serie_info = scraper_serie_live.extraer_info_basica(soup)
        
        season_selector = soup.find('select', id='season-selector')
        temporadas_disponibles = []
        serie_id = None
        
        if season_selector:
            options = season_selector.find_all('option')
            serie_id = options[0].get('data-serie') if options else None
            
            for option in options:
                temporadas_disponibles.append({
                    'numero': option['value'],
                    'nombre': option.text.strip(),
                    'episodios_cargados': False
                })
        
        resultado = {
            'id': str(uuid.uuid4()),
            **serie_info,
            'url_serie': url_serie,
            'slug': slug,
            'serie_id': serie_id,
            'temporadas': temporadas_disponibles,
            'tipo': 'info_basica'
        }
        
        cache_service.set(cache_key, resultado)
        
        response = jsonify(resultado)
        response.headers['X-Cache'] = 'MISS'
        return response, 200
        
    except Exception as e:
        return jsonify({
            'error': 'Error al obtener información básica',
            'detalle': str(e)
        }), 500

@app.route('/api/serie/<string:slug>/temporada/<int:temporada_num>')
def serie_temporada_completa(slug, temporada_num):
    """
    PASO 2: Obtiene episodios y servidores de UNA temporada específica
    
    Ejemplo: /api/serie/la-nueva-brigada/temporada/1
    """
    try:
        # Intentar obtener del caché
        cache_key = f"serie_temp_{slug}_s{temporada_num}"
        cached_data = cache_service.get(cache_key)
        
        if cached_data:
            response = jsonify(cached_data)
            response.headers['X-Cache'] = 'HIT'
            return response, 200
        
        # Construir URL y obtener serie_id
        url_serie = f"{scraper_serie_live.base_url}/serie/{slug}/"
        http_response = scraper_serie_live.hacer_peticion_segura(url_serie)
        soup = BeautifulSoup(http_response.content, 'html.parser')
        
        season_selector = soup.find('select', id='season-selector')
        if not season_selector:
            return jsonify({'error': 'No se encontró selector de temporadas'}), 404
        
        options = season_selector.find_all('option')
        serie_id = options[0].get('data-serie') if options else None
        
        if not serie_id:
            return jsonify({'error': 'No se pudo obtener ID de la serie'}), 404
        
        episodios = scraper_serie_live.cargar_episodios_temporada(
            serie_id, 
            str(temporada_num), 
            url_serie
        )
        
        for episodio in episodios:
            if episodio.get('url'):
                servidores = scraper_serie_live.extraer_enlaces_episodio(episodio['url'])
                episodio['servidores'] = servidores
                time.sleep(1)
        
        resultado = {
            'slug': slug,
            'temporada_numero': temporada_num,
            'total_episodios': len(episodios),
            'episodios': episodios
        }
        
        cache_service.set(cache_key, resultado)
        
        response = jsonify(resultado)
        response.headers['X-Cache'] = 'MISS'
        return response, 200
        
    except Exception as e:
        return jsonify({
            'error': 'Error al cargar temporada',
            'detalle': str(e)
        }), 500

@app.route('/api/serie/<string:slug>/completa')
def serie_completa(slug):
    """
    ENDPOINT COMPLETO: Obtiene toda la serie con todos los episodios y servidores
    (Este es el endpoint original, pero más lento)
    
    Ejemplo: /api/serie/la-nueva-brigada/completa
    """
    try:
        cache_key = f"serie_completa_{slug}"
        cached_data = cache_service.get(cache_key)
        
        if cached_data:
            response = jsonify(cached_data)
            response.headers['X-Cache'] = 'HIT'
            return response, 200
        
        serie_data = scraper_serie_live.scrapear_serie_por_slug(slug)
        
        if not serie_data:
            return jsonify({
                'error': 'Serie no encontrada',
                'slug': slug
            }), 404
        
        cache_service.set(cache_key, serie_data)
        
        response = jsonify(serie_data)
        response.headers['X-Cache'] = 'MISS'
        return response, 200
        
    except Exception as e:
        return jsonify({
            'error': 'Error al procesar la serie',
            'detalle': str(e)
        }), 500

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

# ==================== ADMINISTRACIÓN ====================

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
    Envía un email usando Resend
    """
    try:
        if not resend.api_key:
            print('❌ Error: RESEND_API_KEY no configurado')
            return False
        
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
        
        params = {
            "from": "onboarding@resend.dev",
            "to": [EMAIL_DESTINATARIO],
            "subject": f"[Cinevo Contacto] {asunto}",
            "html": html,
            "reply_to": email 
        }
        
        email_response = resend.Emails.send(params)
        print(f'✅ Email enviado: {email_response}')
        return True
        
    except Exception as e:
        print(f'❌ Error enviando email con Resend: {str(e)}')
        return False

# ==================== INICIO DEL SERVIDOR ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 API de Streaming iniciada")
    print("=" * 60)
    print(f"🔧 Scraper mode: {'Playwright' if USAR_PLAYWRIGHT else 'Simple (requests)'}")
    print(f"📁 Películas: {len(cargar_json(PELICULAS_FILE))}")
    print(f"📺 Series: {len(cargar_json(SERIES_FILE))}")
    print("=" * 60)

    if sys.platform == 'win32':
        from waitress import serve
        print("Running with Waitress on Windows...")
        serve(app, host='0.0.0.0', port=5400)
    else:
        print("Running Flask development server...")
        app.run(host='0.0.0.0', port=5400)