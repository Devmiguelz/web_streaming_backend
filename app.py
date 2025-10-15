from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Permitir peticiones desde el frontend

# Configuración
CACHE_DIR = 'cache'
PELICULAS_FILE = os.path.join(CACHE_DIR, 'peliculas.json')
SERIES_FILE = os.path.join(CACHE_DIR, 'series.json')

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

@app.route('/api/pelicula/<int:id>')
def detalle_pelicula(id):
    """Obtiene el detalle de una película"""
    peliculas = cargar_json(PELICULAS_FILE)
    
    if 0 <= id < len(peliculas):
        return jsonify(peliculas[id])
    
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
    
    # Filtrar por género
    if genero:
        series = [s for s in series if genero in s.get('generos', [])]
    
    # Ordenar
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

@app.route('/api/serie/<int:id>')
def detalle_serie(id):
    """Obtiene el detalle completo de una serie"""
    series = cargar_json(SERIES_FILE)
    
    if 0 <= id < len(series):
        return jsonify(series[id])
    
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

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Error interno del servidor'}), 500

# ==================== INICIO DEL SERVIDOR ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🎬 API de Streaming iniciada")
    print("=" * 60)
    print(f"📁 Películas: {len(cargar_json(PELICULAS_FILE))}")
    print(f"📺 Series: {len(cargar_json(SERIES_FILE))}")
    print("=" * 60)
    print("🌐 Servidor corriendo en http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)