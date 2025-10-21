"""
pelicula_scraper_live.py
Servicio de scraping en vivo para películas de CineCalidad
"""

import requests
from bs4 import BeautifulSoup
import random
import uuid
from urllib.parse import urlparse
import re


class ScraperMovieService:
    """Servicio para hacer scraping en vivo de películas"""
    
    BASE_URL = "https://cinecalidad.bar"
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    
    def __init__(self):
        self.session = requests.Session()
    
    def _get_random_headers(self):
        """Genera headers con User-Agent aleatorio"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
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
            headers = self._get_random_headers()
            headers['Referer'] = referer_url
            
            response = self.session.get(player_url, headers=headers, timeout=15)
            response.raise_for_status()
            
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
            
            # Hacer petición
            response = self.session.get(
                url_pelicula, 
                headers=self._get_random_headers(), 
                timeout=15
            )
            response.raise_for_status()
            
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
                
                # 4. Extraer servidores del player
                servidores = self._extraer_servidores_video(player_url, url_pelicula)
                resultado['servidores'] = servidores
            
            return resultado
            
        except Exception as e:
            # Re-lanzar la excepción para que el controller la maneje
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