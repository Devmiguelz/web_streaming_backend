import requests
from bs4 import BeautifulSoup
import uuid
import re
import random
import time
from urllib.parse import urlparse


class ScraperSerieService:
    """Servicio para scraping en vivo de series de CineCalidad"""
    
    def __init__(self):
        self.base_url = "https://cinecalidad.bar"
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        ]
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def get_random_headers(self):
        """Genera headers con User-Agent aleatorio"""
        headers = self.headers.copy()
        headers['User-Agent'] = random.choice(self.user_agents)
        return headers

    def hacer_peticion_segura(self, url, max_reintentos=3):
        """Hace una petición HTTP con protección anti-bloqueo"""
        for intento in range(1, max_reintentos + 1):
            try:
                if intento > 1:
                    time.sleep(random.uniform(2, 5))
                
                response = self.session.get(
                    url, 
                    headers=self.get_random_headers(),
                    timeout=15
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if intento == max_reintentos:
                    raise Exception(f"Error al hacer petición después de {max_reintentos} intentos: {str(e)}")
        
        return None

    def extraer_player_url_episodio(self, url_episodio):
        """Extrae la URL del iframe player desde la página del episodio"""
        try:
            response = self.hacer_peticion_segura(url_episodio)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            iframes = soup.find_all('iframe', class_='absolute inset-0 w-full h-full')
            
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

    def extraer_servidores_video(self, player_url, referer_url):
        """Accede al iframe del player y extrae los servidores de video disponibles"""
        try:
            headers_player = self.get_random_headers()
            headers_player['Referer'] = referer_url
            
            response = self.session.get(player_url, headers=headers_player, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            servidores = []
            
            botones_servidor = soup.find_all('li', onclick=True)
            
            for boton in botones_servidor:
                try:
                    onclick = boton.get('onclick', '')
                    
                    if 'go_to_player' in onclick:
                        match = re.search(r"go_to_player\('([^']+)'\)", onclick)
                        if match:
                            ruta_relativa = match.group(1)
                            base_url = urlparse(player_url)
                            url_completa = f"{base_url.scheme}://{base_url.netloc}{ruta_relativa}"
                            
                            span = boton.find('span')
                            nombre_servidor = span.text.strip() if span else 'Desconocido'
                            
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
                    continue
            
            return servidores
            
        except Exception as e:
            print(f"Error extrayendo servidores: {e}")
            return []

    def extraer_info_basica(self, soup):
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
            
        except Exception as e:
            print(f"Error extrayendo info básica: {e}")
        
        return info

    def cargar_episodios_temporada(self, serie_id, temporada_numero, url_serie):
        """Hace petición AJAX para cargar episodios de una temporada"""
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
                'User-Agent': random.choice(self.user_agents)
            }
            
            response = self.session.post(
                ajax_url,
                data=data,
                headers=ajax_headers,
                timeout=15
            )
            response.raise_for_status()

            # Intentar parsear como JSON
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
                    
                    return episodios
                    
            except:
                # Si no es JSON, parsear como HTML
                html_episodios = response.text
                
                if not html_episodios or html_episodios.strip() == '':
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
                
                return episodios
            
        except Exception as e:
            print(f"Error cargando episodios: {e}")
            return []

    def extraer_temporadas_episodios(self, soup, url_serie):
        """Extrae las temporadas y sus episodios usando AJAX"""
        temporadas = []
        
        try:
            season_selector = soup.find('select', id='season-selector')
            
            if not season_selector:
                return temporadas
            
            options = season_selector.find_all('option')
            
            if not options:
                return temporadas
            
            serie_id = options[0].get('data-serie') if options else None
            
            if not serie_id:
                return temporadas
            
            for option in options:
                temp_numero = option['value']
                temp_nombre = option.text.strip()
                
                temporada_data = {
                    'numero': temp_numero,
                    'nombre': temp_nombre,
                    'episodios': []
                }
                
                episodios = self.cargar_episodios_temporada(serie_id, temp_numero, url_serie)
                temporada_data['episodios'] = episodios
                
                temporadas.append(temporada_data)
                
                time.sleep(0.5)  # Pequeña pausa entre temporadas
            
        except Exception as e:
            print(f"Error extrayendo temporadas: {e}")
        
        return temporadas

    def extraer_enlaces_episodio(self, url_episodio):
        """Extrae los enlaces de servidores de un episodio específico"""
        player_url = self.extraer_player_url_episodio(url_episodio)
        if not player_url:
            return []
                
        return self.extraer_servidores_video(player_url, url_episodio)

    def scrapear_serie_por_slug(self, slug):
        """
        Scrapea una serie en vivo desde CineCalidad usando su slug
        
        Args:
            slug: El slug de la serie (ej: 'la-nueva-brigada')
            
        Returns:
            dict: Datos completos de la serie con temporadas, episodios y servidores
        """
        try:
            # Construir URL completa
            url_serie = f"{self.base_url}/serie/{slug}/"
            
            # Hacer petición inicial
            response = self.hacer_peticion_segura(url_serie)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraer información básica
            serie_info = self.extraer_info_basica(soup)
            
            # Extraer temporadas y episodios
            temporadas = self.extraer_temporadas_episodios(soup, url_serie)
            
            # Extraer enlaces de servidores para cada episodio
            for temporada in temporadas:
                for episodio in temporada['episodios']:
                    if episodio.get('url'):
                        servidores = self.extraer_enlaces_episodio(episodio['url'])
                        episodio['servidores'] = servidores
                        time.sleep(1)  # Pausa entre episodios
            
            # Construir resultado final
            resultado = {
                'id': str(uuid.uuid4()),
                **serie_info,
                'url_serie': url_serie,
                'temporadas': temporadas
            }
            
            return resultado
            
        except Exception as e:
            raise Exception(f"Error al scrapear serie: {str(e)}")


# Instancia singleton del servicio
scraper_serie_live = ScraperSerieService()