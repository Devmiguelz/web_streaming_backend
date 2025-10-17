import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urlparse
import uuid
import re

class CineCalidadSerieExtractor:

    def __init__(self):
        self.base_url = "https://cinecalidad.bar"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def cargar_series_json(self, archivo_json):
        """Carga series desde JSON"""
        try:
            with open(archivo_json, 'r', encoding='utf-8') as f:
                series = json.load(f)
            print(f"✓ {len(series)} series cargadas desde {archivo_json}")
            return series
        except FileNotFoundError:
            print(f"❌ Error: No se encontró el archivo {archivo_json}")
            return []
    
    def extraer_player_url_episodio(self, url_episodio_serie):
        """Extrae la URL del iframe player desde la página del episodio"""
        try:
            response = self.session.get(url_episodio_serie, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar el iframe
            iframes = soup.find_all('iframe', class_='absolute inset-0 w-full h-full')
        
            if not iframes:
                print("  ⚠️ No se encontraron iframes con las clases especificadas")
                return None
            
            # Filtrar iframes que NO sean de YouTube
            for iframe in iframes:
                if 'src' in iframe.attrs:
                    src = iframe['src']
                    
                    # Excluir iframes de YouTube (trailers)
                    if 'youtube.com' not in src.lower() and 'youtu.be' not in src.lower():
                        print(f"  ✓ Player URL encontrada: {src}")
                        return src
            
            print("  ⚠️ No se encontró iframe válido (solo trailers de YouTube)")
            return None
                
        except Exception as e:
            print(f"  ❌ Error extrayendo player URL: {e}")
            return None

    def extraer_servidores_video(self, player_url, referer_url):
        """Accede al iframe del player y extrae los servidores de video disponibles"""
        try:
            # Headers específicos con referer
            headers_player = self.headers.copy()
            headers_player['Referer'] = referer_url
            
            print(f"  → Accediendo al player...")
            response = self.session.get(player_url, headers=headers_player, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            servidores = []
            
            # Buscar todos los botones de servidor (los <li> con onclick)
            botones_servidor = soup.find_all('li', onclick=True)
            
            for boton in botones_servidor:
                try:
                    # Extraer el onclick
                    onclick = boton.get('onclick', '')
                    
                    # El onclick contiene: go_to_player('/r.php?id=...&hash=...')
                    if 'go_to_player' in onclick:
                        # Extraer la URL entre comillas
                        match = re.search(r"go_to_player\('([^']+)'\)", onclick)
                        if match:
                            ruta_relativa = match.group(1)
                            
                            # Construir URL completa
                            base_url = urlparse(player_url)
                            url_completa = f"{base_url.scheme}://{base_url.netloc}{ruta_relativa}"
                            
                            # Extraer nombre del servidor
                            span = boton.find('span')
                            nombre_servidor = span.text.strip() if span else 'Desconocido'
                            
                            # Extraer descripción
                            p = boton.find('p')
                            descripcion = p.text.strip() if p else ''
                            
                            servidor_info = {
                                'nombre': nombre_servidor,
                                'descripcion': descripcion,
                                'url_redirect': url_completa,
                                'ruta_relativa': ruta_relativa
                            }
                            
                            servidores.append(servidor_info)
                            
                except Exception as e:
                    print(f"    Error extrayendo servidor: {e}")
                    continue
            
            print(f"  ✓ {len(servidores)} servidores encontrados")
            return servidores
            
        except Exception as e:
            print(f"  ❌ Error accediendo al player: {e}")
            return []

    def obtener_url_final_video(self, redirect_url, referer_url):
        """Sigue la redirección de /r.php para obtener la URL final del video"""
        try:
            headers_redirect = self.headers.copy()
            headers_redirect['Referer'] = referer_url
            
            # Hacer petición pero NO seguir redirects automáticamente
            response = self.session.get(
                redirect_url, 
                headers=headers_redirect, 
                timeout=15,
                allow_redirects=False
            )
            
            # Si hay redirección (código 3xx)
            if 300 <= response.status_code < 400:
                url_final = response.headers.get('Location')
                return url_final
            
            # Si no hay redirección, intentar extraer del HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            iframe = soup.find('iframe')
            if iframe and 'src' in iframe.attrs:
                return iframe['src']
            
            return None
            
        except Exception as e:
            print(f"    Error obteniendo URL final: {e}")
            return None
    
    def _extraer_info_basica(self, soup):
        """Extrae la información básica de la serie"""
        info = {}
        
        try:
            # Título
            titulo_tag = soup.find('h1', class_='mb-2')
            info['titulo'] = titulo_tag.text.strip() if titulo_tag else None
            
            # Imagen principal
            img_tag = soup.find('figure', class_='md:col-span-2')
            if img_tag:
                img = img_tag.find('img')
                info['imagen'] = img['src'] if img else None
            
            # Trailer (YouTube)
            trailer_iframe = soup.find('iframe', id='videoPlayer')
            if trailer_iframe and 'src' in trailer_iframe.attrs:
                info['trailer'] = trailer_iframe['src']
            else:
                info['trailer'] = None
            
            # Descripción
            desc_container = soup.find('div', class_='capturar')
            if desc_container:
                desc_p = desc_container.find('p')
                info['descripcion'] = desc_p.text.strip() if desc_p else None
            else:
                info['descripcion'] = None
            
            # Lista de detalles
            aside = soup.find('aside', class_='md:col-span-3')
            if aside:
                ul = aside.find('ul', class_='list-none')
                if ul:
                    items = ul.find_all('li')
                    
                    for item in items:
                        texto = item.text.strip()
                        
                        # Título original
                        if 'Título original' in texto:
                            info['titulo_original'] = texto.replace('Título original', '').strip()
                        
                        # Enlaces TMDB/IMDB
                        if 'Mas detalles en' in texto:
                            tmdb_link = item.find('a', class_='tmdb-s')
                            imdb_link = item.find('a', class_='imdb-s')
                            info['tmdb'] = tmdb_link['href'] if tmdb_link and tmdb_link.get('href') else None
                            info['imdb'] = imdb_link['href'] if imdb_link and imdb_link.get('href') else None
                        
                        # Géneros
                        if 'Géneros' in texto:
                            generos_links = item.find_all('a')
                            info['generos'] = [g.text.strip() for g in generos_links]
            
            print(f"✓ Información básica extraída: {info.get('titulo', 'Sin título')}")
            
        except Exception as e:
            print(f"Error al extraer información básica: {e}")
        
        return info
    
    def _cargar_episodios_temporada(self, serie_id, temporada_numero, url_serie):
        """
        Hace una petición AJAX para cargar los episodios de una temporada específica
        """
        try:

            ajax_url = f"{self.base_url}/wp-admin/admin-ajax.php"
            
            data = {
                'action': 'action_change_episode',
                'serie': str(serie_id),
                'season': str(temporada_numero)
            }
            
            ajax_headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': url_serie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = self.session.post(
                ajax_url,
                data=data,
                headers=ajax_headers,
                timeout=15
            )
            response.raise_for_status()

            try:
                json_response = response.json()
                
                if json_response.get('res') == 'conexion' and 'd' in json_response:
                    episodios = []
                    
                    for ep_data in json_response['d']:
                        imagen_url = None
                        if ep_data.get('image'):
                            img_match = re.search(r'src="([^"]+)"', ep_data['image'])
                            if img_match:
                                imagen_url = img_match.group(1)
                        
                        episodio_data = {
                            'numero': f"{ep_data.get('season_number')}X{ep_data.get('episode')}",
                            'titulo': ep_data.get('nameep'),
                            'url': ep_data.get('url'),
                            'imagen': imagen_url,
                            'estado': ep_data.get('availability', {}).get('text'),
                            'servidores': []
                        }
                        
                        episodios.append(episodio_data)
                    
                    print(f"    ✓ {len(episodios)} episodios encontrados (JSON)")
                    return episodios
                else:
                    print(f"    ⚠️ Respuesta JSON inesperada: {json_response}")
                    
            except json.JSONDecodeError:

                print(f"    → Respuesta no es JSON, intentando parsear HTML...")
                
                html_episodios = response.text
                
                if not html_episodios or html_episodios.strip() == '':
                    print(f"    ⚠️ No se recibieron episodios para temporada {temporada_numero}")
                    return []
                
                soup = BeautifulSoup(html_episodios, 'html.parser')
                episodios_list = soup.find_all('li', class_='TPostMve')
                
                episodios = []
                
                for ep in episodios_list:
                    article = ep.find('article')
                    if article:
                        link_tag = article.find('a')
                        titulo_tag = article.find('h2', class_='episodiotitle')
                        numero_tag = article.find('span', class_='tilpisode')
                        img_tag = article.find('img')
                        estado_tag = article.find('span', class_='displ')
                        
                        episodio_data = {
                            'numero': numero_tag.text.strip() if numero_tag else None,
                            'titulo': titulo_tag.text.strip() if titulo_tag else None,
                            'url': link_tag['href'] if link_tag else None,
                            'imagen': img_tag['src'] if img_tag else None,
                            'estado': estado_tag.text.strip() if estado_tag else None,
                            'servidores': []
                        }
                        
                        episodios.append(episodio_data)
                
                print(f"    ✓ {len(episodios)} episodios encontrados (HTML)")
                return episodios
            
        except Exception as e:
            print(f"    ❌ Error cargando episodios de temporada {temporada_numero}: {e}")
            return []
    
    def _extraer_temporadas_episodios(self, soup, url_serie):
        """Extrae las temporadas y sus episodios usando AJAX"""
        temporadas = []
        
        try:
            season_selector = soup.find('select', id='season-selector')
            
            if not season_selector:
                print("No se encontró selector de temporadas")
                return temporadas
            
            options = season_selector.find_all('option')
            
            if not options:
                print("No se encontraron opciones de temporada")
                return temporadas
            
            serie_id = options[0].get('data-serie') if options else None
            
            if not serie_id:
                print("⚠️ No se pudo extraer el ID de la serie")
                return temporadas
            
            print(f"\n📺 Temporadas encontradas: {len(options)} (Serie ID: {serie_id})")
            
            for option in options:
                temp_numero = option['value']
                temp_nombre = option.text.strip()
                
                print(f"\n  → {temp_nombre}")
                
                temporada_data = {
                    'numero': temp_numero,
                    'nombre': temp_nombre,
                    'episodios': []
                }
                
                episodios = self._cargar_episodios_temporada(serie_id, temp_numero, url_serie)
                temporada_data['episodios'] = episodios
                
                temporadas.append(temporada_data)
                
                time.sleep(1)
            
        except Exception as e:
            print(f"Error al extraer temporadas y episodios: {e}")
        
        return temporadas
    
    def _extraer_enlaces_episodio(self, url_episodio):
        """Extrae los enlaces de servidores de un episodio específico"""
        servidores = []
        
        # 1. Extraer URL del player
        player_url = self.extraer_player_url_episodio(url_episodio)
        if not player_url:
            return servidores
                
        servidores = self.extraer_servidores_video(player_url, url_episodio)
                
        return servidores
    
    def procesar_serie(self, serie, delay_entre_episodios=5):
        """
        Extrae todos los datos de una serie incluyendo episodios y enlaces
        """
        try:
            url_serie = serie.get('enlace')
            
            print(f"\n{'='*60}")
            print(f"Extrayendo datos de: {url_serie}")
            print(f"{'='*60}\n")
            
            response = self.session.get(url_serie, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            serie_info = self._extraer_info_basica(soup)
            
            temporadas = self._extraer_temporadas_episodios(soup, url_serie)
            
            print("\n🎬 Extrayendo enlaces de servidores de cada episodio...\n")
            for temporada in temporadas:
                print(f"\n📂 Procesando {temporada['nombre']}...")
                for episodio in temporada['episodios']:
                    print(f"  → {episodio['titulo']}")
                    servidores = self._extraer_enlaces_episodio(episodio['url'])
                    episodio['servidores'] = servidores
                    time.sleep(delay_entre_episodios)
            
            resultado = {
                'id': f"{uuid.uuid4()}",
                **serie_info,
                'url_serie': url_serie,
                'temporadas': temporadas
            }
            
            print(f"\n{'='*60}")
            print(f"✓ Extracción completada exitosamente")
            print(f"{'='*60}\n")
            
            return resultado
            
        except Exception as e:
            print(f"❌ Error al extraer datos de la serie: {e}")
            return None

    def procesar_series(self, archivo_json, limite=None, delay=5):
        """Procesa múltiples series"""
        series = self.cargar_series_json(archivo_json)
        
        if not series:
            return []
        
        if limite:
            series = series[:limite]
        
        resultados = []
        total = len(series)
        
        print(f"\n{'='*80}")
        print(f"Procesando {total} series...")
        print('='*80)
        
        for i, serie in enumerate(series, 1):
            print(f"\n[{i}/{total}] {serie.get('titulo', 'Sin título')}")
            
            resultado = self.procesar_serie(serie, delay_entre_episodios=delay)
            
            if resultado:
                resultados.append(resultado)
            
            if i < total:
                time.sleep(delay)
        
        return resultados

    def guardar_resultados(self, resultados, prefijo='series_new'):
        """Guarda resultados en un archivo JSON"""
        if not resultados:
            print("No hay resultados para guardar")
            return
        
        carpeta_destino = os.path.join(os.path.dirname(__file__), '../cache')
        archivo = f'{prefijo}.json'
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_archivo = os.path.join(carpeta_destino, archivo)

        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        print(f"\n✓ JSON guardado: {ruta_archivo}")
    
    def recuperar_propiedad_faltantes(self, archivo_cache, archivo_database, delay=1):
        """Lee el JSON de cache y actualiza propiedades faltantes desde database"""
        series = self.cargar_series_json(archivo_cache)

        if not series:
            return []
        
        series_database = None
        if archivo_database:
            print(f"\n📥 Cargando database para buscar propiedades faltantes...")
            series_database = self.cargar_series_json(archivo_database)
        else:
            print("❌ Se requiere archivo database para actualizar propiedades")
            return series
        
        serie_sin_propiedad = []
        for serie in series:
            propiedad = serie.get('propiedad')
            
            if not propiedad or propiedad == "" or propiedad is None:
                serie_sin_propiedad.append(serie)
        
        total = len(serie_sin_propiedad)
        
        if total == 0:
            print("✅ Todas las series ya tienen la propiedad!")
            return series
        
        print(f"\n{'='*80}")
        print(f"🔄 Actualizando propiedades de {total} series...")
        print('='*80)
        
        actualizadas = 0
        no_encontradas = 0
        
        for i, serie in enumerate(serie_sin_propiedad, 1):
            titulo = serie.get('titulo', 'Sin título')
            print(f"\n[{i}/{total}] {titulo}")
            
            propiedad_encontrada = None
            for s_db in series_database:
                if s_db.get('titulo') == titulo:
                    propiedad_encontrada = s_db.get('tipo')
                    break
            
            for j, s in enumerate(series):
                if s.get('titulo') == titulo:
                    if propiedad_encontrada:
                        series[j]['id'] = f"{uuid.uuid4()}"
                        print(f"   ✅ Propiedad actualizada: {propiedad_encontrada}")
                        actualizadas += 1
                    else:
                        print(f"   ⚠️  Propiedad no encontrada en database")
                        no_encontradas += 1
                    break
            
            if i < total:
                time.sleep(delay)
        
        print(f"\n{'='*80}")
        print(f"📊 Resumen de actualización:")
        print(f"   ✅ Actualizadas: {actualizadas}")
        print(f"   ⚠️  No encontradas: {no_encontradas}")
        print('='*80)
        
        self.guardar_resultados(series, prefijo='series_actualizadas')

    def seleccionar_archivo_json(self, carpeta='database'):
        """Lista los archivos JSON disponibles y permite seleccionar uno"""
        database_path = os.path.join(os.path.dirname(__file__), f'../{carpeta}')
        
        if not os.path.exists(database_path):
            print(f"❌ Error: No se encontró la carpeta {database_path}")
            return None
        
        archivos_json = sorted([f for f in os.listdir(database_path) if f.endswith('.json')])
        
        if not archivos_json:
            print(f"❌ No se encontraron archivos JSON en {database_path}")
            return None
        
        print(f"\n📁 Archivos JSON disponibles en {carpeta}/:")
        print("-" * 90)
        for i, archivo in enumerate(archivos_json, 1):
            ruta_completa = os.path.join(database_path, archivo)
            tamano = os.path.getsize(ruta_completa) / 1024
            
            try:
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                    num_items = len(datos) if isinstance(datos, list) else "?"
                    sin_servidores = sum(1 for p in datos if not p.get('servidores', []))
                    print(f"  {i}. {archivo:<35} ({tamano:>6.1f} KB | {num_items:>4} series | {sin_servidores:>3} sin servidores)")
            except:
                print(f"  {i}. {archivo:<35} ({tamano:>6.1f} KB)")
        
        print("-" * 90)
        
        while True:
            try:
                seleccion = input(f"\nSelecciona un archivo (1-{len(archivos_json)}) o Enter para cancelar: ").strip()
                
                if not seleccion:
                    print("❌ Operación cancelada")
                    return None
                
                indice = int(seleccion) - 1
                
                if 0 <= indice < len(archivos_json):
                    archivo_seleccionado = archivos_json[indice]
                    ruta_completa = os.path.join(database_path, archivo_seleccionado)
                    print(f"✓ Archivo seleccionado: {archivo_seleccionado}")
                    return ruta_completa
                else:
                    print(f"⚠️ Por favor ingresa un número entre 1 y {len(archivos_json)}")
                    
            except ValueError:
                print("⚠️ Por favor ingresa un número válido")
            except KeyboardInterrupt:
                print("\n❌ Operación cancelada")
                return None


# Ejemplo de uso
if __name__ == "__main__":
    extractor = CineCalidadSerieExtractor()
    
    print("🎬 EXTRACTOR DE SERIES - CINECALIDAD")
    print("="*80)

    print("\n¿Qué deseas hacer?")
    print("  1. Procesar series desde database/")
    print("  2. Actualizar propiedades faltantes desde cache/ (requiere database/)")

    modo = input("\nOpción (1-2): ").strip()
        
    if modo == '2':
        print("\n🔄 MODO: Actualizar propiedades faltantes")
        archivo_cache = extractor.seleccionar_archivo_json(carpeta='cache')        
        if not archivo_cache:
            print("\n❌ Debes seleccionar un archivo de cache para continuar")
            exit(1)
        
        archivo_database = extractor.seleccionar_archivo_json(carpeta='database')        
        if not archivo_database:
            print("\n❌ Debes seleccionar un archivo de database para continuar")
            exit(1)
        
        extractor.recuperar_propiedad_faltantes(
            archivo_cache=archivo_cache,
            archivo_database=archivo_database,
            delay=0
        )

    elif modo == '1':
        archivo_json = extractor.seleccionar_archivo_json()

        if not archivo_json:
            exit(1)

        print("\n¿Cuántas series procesar?")
        print("  1. Solo 1 (prueba rápida)")
        print("  2. 3 series")
        print("  3. 10 series")
        print("  4. Todas")
        
        opcion = input("\nOpción (1-4): ").strip()
        limite_map = {'1': 1, '2': 3, '3': 10, '4': None}
        limite = limite_map.get(opcion, 1)

        if limite is not None:
            print(f"\n⚙️ Procesando {limite} series...")    
        else:
            print("\n⚙️ Procesando TODAS las series (esto puede tardar)...")
        
        resultados = extractor.procesar_series(
            archivo_json=archivo_json,
            limite=limite,
            delay=3
        )
        
        if resultados:
            print(f"\n{'='*80}")
            print(f"✅ Completado: {len(resultados)} series procesadas")
            print('='*80)
            
            extractor.guardar_resultados(resultados)
        else:
            print("\n❌ No se procesó ninguna serie")
    else:
        print("❌ Opción inválida")