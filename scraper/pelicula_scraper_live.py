"""
pelicula_scraper_live.py
Servicio de scraping en vivo para películas de CineCalidad
VERSIÓN MEJORADA - Anti-detección
"""

import requests
from bs4 import BeautifulSoup
import random
import uuid
from urllib.parse import urlparse
import re
import time

class ScraperMovieService:
    """Servicio para hacer scraping en vivo de películas"""
    
    BASE_URL = "https://cinecalidad.bar"
    
    # User agents más diversos y actualizados
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]
    
    # Referers comunes para simular tráfico orgánico
    REFERERS = [
        'https://www.google.com/',
        'https://www.google.com.co/',
        'https://www.google.com.mx/',
        'https://www.bing.com/',
        'https://duckduckgo.com/',
    ]
    
    def __init__(self):
        self.session = requests.Session()
        # Configurar la sesión para mantener cookies
        self.session.cookies.set('cookie_notice_accepted', 'true', domain='.cinecalidad.bar')
    
    def _get_random_headers(self, referer=None):
        """Genera headers realistas con todas las cabeceras necesarias"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8,es-419;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none' if not referer else 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Referer': referer if referer else random.choice(self.REFERERS),
        }
    
    def _hacer_peticion_segura(self, url, referer=None, max_reintentos=3):
        """
        Hace una petición HTTP con reintentos y delays aleatorios
        """
        for intento in range(max_reintentos):
            try:
                # Delay aleatorio para simular comportamiento humano
                if intento > 0:
                    time.sleep(random.uniform(2, 4))
                else:
                    time.sleep(random.uniform(0.5, 1.5))
                
                headers = self._get_random_headers(referer)
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=20,
                    allow_redirects=True
                )
                
                # Si es 403, reintentar
                if response.status_code == 403:
                    print(f"⚠️ 403 detectado en intento {intento + 1}/{max_reintentos}")
                    if intento < max_reintentos - 1:
                        continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.HTTPError as e:
                if intento == max_reintentos - 1:
                    raise
                print(f"⚠️ Error HTTP en intento {intento + 1}: {e}")
                
            except requests.exceptions.Timeout:
                if intento == max_reintentos - 1:
                    raise
                print(f"⚠️ Timeout en intento {intento + 1}")
                
            except requests.exceptions.RequestException as e:
                if intento == max_reintentos - 1:
                    raise
                print(f"⚠️ Error de conexión en intento {intento + 1}: {e}")
        
        raise requests.exceptions.RequestException("Se agotaron los reintentos")
    
    def _extraer_info_basica(self, soup):
        """Extrae la información básica de una película desde el HTML"""
        info = {}

        try:
            # 🎬 Título
            titulo_tag = soup.find('h1', class_='mb-2')
            info['titulo'] = titulo_tag.text.strip() if titulo_tag else None

            # 🖼️ Imagen principal
            img_tag = soup.find('figure', class_='md:col-span-2')
            if img_tag:
                img = img_tag.find('img')
                info['imagen'] = img['src'] if img else None
            else:
                info['imagen'] = None

            # 🎞️ Trailer (YouTube)
            trailer_iframe = soup.find('iframe', id='videoPlayer')
            info['trailer'] = trailer_iframe['src'] if trailer_iframe and trailer_iframe.get('src') else None

            # 📝 Descripción
            desc_container = soup.find('div', class_='capturar')
            if desc_container:
                desc_p = desc_container.find('p')
                info['descripcion'] = desc_p.text.strip() if desc_p else None
            else:
                info['descripcion'] = None

            # 📋 Detalles adicionales
            movie_details = soup.find('div', class_='movie-details')
            if movie_details:
                filas = movie_details.find_all('tr')
                for fila in filas:
                    th = fila.find('th')
                    td = fila.find('td')

                    if not th or not td:
                        continue

                    etiqueta = th.text.strip().lower()
                    valor = td.text.strip()

                    if 'título original' in etiqueta:
                        info['titulo_original'] = valor
                    elif 'duración' in etiqueta:
                        info['duracion'] = valor
                    elif 'rating' in etiqueta:
                        info['rating'] = valor
                    elif 'géneros' in etiqueta:
                        generos_links = td.find_all('a')
                        info['generos'] = [g.text.strip() for g in generos_links] if generos_links else [valor]
                    elif 'director' in etiqueta:
                        directores = td.find_all('span', class_='por')
                        info['director'] = [d.text.strip() for d in directores] if directores else [valor]
                    elif 'actores' in etiqueta:
                        actores = td.find_all('span', class_='por')
                        info['actores'] = [a.text.strip() for a in actores] if actores else [valor]
                    elif 'año' in etiqueta:
                        info['año'] = valor

        except Exception as e:
            print(f"Error extrayendo info básica: {e}")

        return info

    def _extraer_player_url(self, soup):
        """Extrae la URL del iframe player, filtrando YouTube"""
        try:
            iframes = soup.find_all('iframe', class_='absolute inset-0 w-full h-full')
            
            if not iframes:
                return None
            
            # Filtrar iframes que NO sean de YouTube
            for iframe in iframes:
                if 'src' in iframe.attrs:
                    src = iframe['src']
                    if 'youtube.com' not in src.lower() and 'youtu.be' not in src.lower():
                        return src
            
            return None
                    
        except Exception as e:
            print(f"Error extrayendo player URL: {e}")
            return None

    def _extraer_servidores_video(self, player_url, referer_url):
        """Extrae los servidores de video desde el player"""
        try:
            # Usar la función segura con reintentos
            response = self._hacer_peticion_segura(player_url, referer=referer_url)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            servidores = []
            
            # Buscar botones de servidor
            botones_servidor = soup.find_all('li', onclick=True)
            
            for boton in botones_servidor:
                try:
                    onclick = boton.get('onclick', '')
                    
                    if 'go_to_player' in onclick:
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
                    print(f"Error extrayendo servidor: {e}")
                    continue
            
            return servidores
            
        except Exception as e:
            print(f"Error accediendo al player: {e}")
            return []

    def obtener_pelicula_por_slug(self, slug):
        """
        Obtiene información completa de una película por su slug
        
        Args:
            slug (str): Slug de la película (ej: 'steve', 'inception')
            
        Returns:
            dict: Información completa de la película o None si hay error
            
        Raises:
            requests.exceptions.HTTPError: Si la película no existe (404)
            requests.exceptions.Timeout: Si hay timeout
            requests.exceptions.RequestException: Otros errores de conexión
        """
        try:
            # Construir URL completa
            url_pelicula = f"{self.BASE_URL}/peli/{slug}/"
            
            print(f"🎬 Scrapeando: {url_pelicula}")
            
            # Hacer petición con reintentos y headers mejorados
            response = self._hacer_peticion_segura(url_pelicula)
            
            print(f"✅ Respuesta recibida: {response.status_code}")
            
            # Parsear HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Extraer información básica
            info_basica = self._extraer_info_basica(soup)
            
            # Verificar que encontramos la película
            if not info_basica.get('titulo'):
                return None
            
            # 2. Construir resultado base
            resultado = {
                'id': str(uuid.uuid4()),
                **info_basica,
                'url_pelicula': url_pelicula,
                'slug': slug,
                'servidores': []
            }
            
            # 3. Extraer URL del player
            player_url = self._extraer_player_url(soup)
            if player_url:
                resultado['player_url'] = player_url
                print(f"🎮 Player encontrado: {player_url}")
                
                # 4. Extraer servidores del player (con delay)
                time.sleep(random.uniform(1, 2))
                servidores = self._extraer_servidores_video(player_url, url_pelicula)
                resultado['servidores'] = servidores
                print(f"📡 Servidores encontrados: {len(servidores)}")
            
            return resultado
            
        except Exception as e:
            # Re-lanzar la excepción para que el controller la maneje
            print(f"❌ Error en obtener_pelicula_por_slug: {e}")
            raise

    def obtener_pelicula_por_url_completa(self, url):
        """
        Obtiene información de una película por su URL completa
        
        Args:
            url (str): URL completa (ej: 'https://cinecalidad.bar/peli/steve/')
            
        Returns:
            dict: Información completa de la película o None si hay error
        """
        try:
            # Extraer slug de la URL
            slug = url.rstrip('/').split('/')[-1]
            return self.obtener_pelicula_por_slug(slug)
        except Exception as e:
            raise ValueError(f"URL inválida: {str(e)}")


# Instancia singleton del servicio
scraper_movie_live = ScraperMovieService()