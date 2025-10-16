import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin, urlparse

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
        """Carga películas desde JSON"""
        try:
            with open(archivo_json, 'r', encoding='utf-8') as f:
                peliculas = json.load(f)
            print(f"✓ {len(peliculas)} películas cargadas desde {archivo_json}")
            return peliculas
        except FileNotFoundError:
            print(f"❌ Error: No se encontró el archivo {archivo_json}")
            return []
    
    def extraer_player_url_episodio(self, url_episodio_serie):
        """
        Extrae la URL del iframe player desde la página de la película
        """
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
        """
        Accede al iframe del player y extrae los servidores de video disponibles
        """
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
                        import re
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
        """
        Sigue la redirección de /r.php para obtener la URL final del video
        """
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
    
    def _extraer_temporadas_episodios(self, soup):
        """Extrae las temporadas y sus episodios"""
        temporadas = []
        
        try:
            # Buscar el selector de temporadas
            season_selector = soup.find('select', id='season-selector')
            
            if not season_selector:
                print("No se encontró selector de temporadas")
                return temporadas
            
            # Obtener todas las opciones de temporada
            options = season_selector.find_all('option')
            
            print(f"\n📺 Temporadas encontradas: {len(options)}")
            
            for option in options:
                temp_numero = option['value']
                temp_nombre = option.text.strip()
                
                print(f"  → {temp_nombre}")
                
                temporada_data = {
                    'numero': temp_numero,
                    'nombre': temp_nombre,
                    'episodios': []
                }
                
                # Buscar los episodios de esta temporada
                # Los episodios están en divs con clase 'se-a'
                episodes_container = soup.find('div', class_='se-a')
                
                if episodes_container:
                    episodios_list = episodes_container.find_all('li', class_='TPostMve')
                    
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
                                'servidores': []  # Se llenará después
                            }
                            
                            temporada_data['episodios'].append(episodio_data)
                    
                    print(f"    ✓ {len(temporada_data['episodios'])} episodios encontrados")
                
                temporadas.append(temporada_data)
            
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
        
        Args:
            url_serie (str): URL de la serie (ej: https://cinecalidad.bar/serie/andor-v4/)
            extraer_urls_finales (bool): Si True, extrae las URLs finales de video (más lento)
        
        Returns:
            dict: Diccionario con toda la información de la serie
        """
        try:
            url_serie = serie.get('enlace')
            
            print(f"\n{'='*60}")
            print(f"Extrayendo datos de: {url_serie}")
            print(f"{'='*60}\n")
            
            response = self.session.get(url_serie, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraer información básica de la serie
            serie_info = self._extraer_info_basica(soup)
            
            # Extraer temporadas y episodios
            temporadas = self._extraer_temporadas_episodios(soup)
            
            # Extraer enlaces de cada episodio
            print("\n🎬 Extrayendo enlaces de servidores de cada episodio...\n")
            for temporada in temporadas:
                for episodio in temporada['episodios']:
                    print(f"  → Procesando: {episodio['titulo']}")
                    servidores = self._extraer_enlaces_episodio(episodio['url'])
                    episodio['servidores'] = servidores
                    time.sleep(delay_entre_episodios) 
            
            # Construir el resultado final
            resultado = {
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
        """
        Procesa múltiples películas
        """
        series = self.cargar_series_json(archivo_json)
        
        if not series:
            return []
        
        if limite:
            series = series[:limite]
        
        resultados = []
        total = len(series)
        
        print(f"\n{'='*80}")
        print(f"Procesando {total} películas...")
        print('='*80)
        
        for i, serie in enumerate(series, 1):
            print(f"\n[{i}/{total}] {serie.get('titulo', 'Sin título')}")
            
            resultado = self.procesar_serie(serie)
            
            if resultado:
                resultados.append(resultado)
            
            # Pausa entre películas
            if i < total:
                time.sleep(delay)
        
        return resultados

    def guardar_resultados(self, resultados, prefijo='series'):
        """
        Guarda resultados únicamente en un archivo JSON
        """
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
    
    def seleccionar_archivo_json(self):
        """
        Lista los archivos JSON disponibles en ../database y permite seleccionar uno
        """
        database_path = os.path.join('..', 'database')
        
        # Verificar que existe la carpeta database
        if not os.path.exists(database_path):
            print(f"❌ Error: No se encontró la carpeta {database_path}")
            return None
        
        # Obtener todos los archivos JSON
        archivos_json = [f for f in os.listdir(database_path) if f.endswith('.json')]
        
        if not archivos_json:
            print(f"❌ No se encontraron archivos JSON en {database_path}")
            return None
        
        # Mostrar lista de archivos
        print("\n📁 Archivos JSON disponibles en database/:")
        print("-" * 60)
        for i, archivo in enumerate(archivos_json, 1):
            ruta_completa = os.path.join(database_path, archivo)
            # Obtener tamaño del archivo
            tamano = os.path.getsize(ruta_completa) / 1024  # KB
            print(f"  {i}. {archivo} ({tamano:.1f} KB)")
        print("-" * 60)
        
        # Solicitar selección
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
    
    # Solicitar archivo JSON
    archivo_json = extractor.seleccionar_archivo_json()
    if not archivo_json:
        exit(1)
    
    # Preguntar cuántas procesar
    print("\n¿Cuántas películas procesar?")
    print("  1. Solo 3 (prueba rápida)")
    print("  2. 10 películas")
    print("  3. 25 películas")
    print("  4. Recuperar servidores")
    print("  5. Todas")
    
    opcion = input("\nOpción (1-5): ").strip()
    limite_map = {'1': 3, '2': 10, '3': 25, '4': -1, '5': None}
    limite = limite_map.get(opcion, 3)

    if limite is not None:
        print(f"\n⚙️ Procesando {limite} películas...")    
    elif limite == -1:
        print("\n⚙️ Recuperando servidores de TODAS las películas (esto puede tardar)...")
    else:
        print("\n⚙️ Procesando TODAS las películas (esto puede tardar)...")
    
    # Procesar
    resultados = extractor.procesar_series(
        archivo_json=archivo_json,
        limite=limite,
        delay=5  
    )
    if resultados:
        print(f"\n{'='*80}")
        print(f"✅ Completado: {len(resultados)} series procesadas")
        print('='*80)
        
        # Guardar
        extractor.guardar_resultados(resultados)
    else:
        print("\n❌ No se procesó ninguna película")