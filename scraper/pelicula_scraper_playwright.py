"""
pelicula_scraper_playwright.py
Scraper usando Playwright con context manager - 100% GRATIS
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import uuid
import re
from urllib.parse import urlparse
import random
import time

class ScraperMoviePlaywright:
    """Servicio de scraping con Playwright (simula navegador real)"""
    
    BASE_URL = "https://cinecalidad.bar"
    
    def obtener_pelicula_por_slug(self, slug):
        """
        Obtiene información de película usando Playwright con context manager
        
        Args:
            slug (str): Slug de la película
            
        Returns:
            dict: Información completa de la película
        """
        with sync_playwright() as playwright:
            try:
                # Lanzar navegador con configuración anti-detección
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-gpu'
                    ]
                )
                
                # Crear contexto con configuración realista
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='es-ES',
                    timezone_id='America/Bogota',
                )
                
                # Script anti-detección
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    window.navigator.chrome = {
                        runtime: {}
                    };
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['es-ES', 'es', 'en']
                    });
                """)
                
                # Crear página
                page = context.new_page()
                
                # Bloquear recursos innecesarios para acelerar carga
                page.route("**/*.{png,jpg,jpeg,gif,svg,mp4,webm,mp3,ico,woff,woff2,ttf}", 
                          lambda route: route.abort())
                page.route("**/*google-analytics*", lambda route: route.abort())
                page.route("**/*doubleclick.net*", lambda route: route.abort())
                page.route("**/*facebook.com*", lambda route: route.abort())
                page.route("**/*twitter.com*", lambda route: route.abort())
                
                # Construir URL de la película
                url_pelicula = f"{self.BASE_URL}/peli/{slug}/"
                
                print(f"🎬 Navegando a: {url_pelicula}")
                
                # Simular comportamiento humano con delay
                time.sleep(random.uniform(0.5, 1.5))
                
                # Navegar a la película
                try:
                    page.goto(url_pelicula, wait_until='domcontentloaded', timeout=30000)
                except PlaywrightTimeout:
                    print("⚠️ Timeout en primera carga, reintentando con wait_until='load'...")
                    page.goto(url_pelicula, wait_until='load', timeout=30000)
                
                # Esperar a que cargue el título
                try:
                    page.wait_for_selector('h1.mb-2', timeout=10000)
                    print("✅ Página cargada correctamente")
                except PlaywrightTimeout:
                    print("⚠️ Timeout esperando título, continuando...")
                
                # Obtener HTML de la página principal
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extraer información básica
                info = self._extraer_info_basica(soup)
                
                if not info.get('titulo'):
                    print("❌ No se encontró el título de la película")
                    browser.close()
                    return None
                
                print(f"📝 Película encontrada: {info.get('titulo')}")
                
                # Construir resultado base
                resultado = {
                    'id': str(uuid.uuid4()),
                    **info,
                    'url_pelicula': url_pelicula,
                    'slug': slug,
                    'servidores': []
                }
                
                # Extraer player URL
                player_url = self._extraer_player_url(soup)
                
                if player_url:
                    resultado['player_url'] = player_url
                    print(f"🎮 Player URL encontrada: {player_url}")
                    
                    # Delay antes de cargar el player
                    time.sleep(random.uniform(1, 2))
                    
                    try:
                        # Navegar al player con networkidle para esperar a que cargue todo
                        print("🔄 Cargando player...")
                        try:
                            page.goto(player_url, wait_until='networkidle', timeout=30000)
                        except PlaywrightTimeout:
                            # Fallback a load si networkidle falla
                            page.goto(player_url, wait_until='load', timeout=30000)
                        
                        print("⏳ Esperando a que JavaScript cargue los servidores...")
                        
                        # Esperar más tiempo para que el JavaScript dinámico se ejecute
                        time.sleep(4)
                        
                        # Intentar múltiples selectores
                        servidores_encontrados = False
                        selectores = [
                            'li[onclick*="go_to_player"]',
                            '.OD li',
                            '.OptionsLangDisp li',
                            'li[onclick]'
                        ]
                        
                        for selector in selectores:
                            try:
                                page.wait_for_selector(selector, timeout=3000)
                                print(f"✅ Encontrado selector: {selector}")
                                servidores_encontrados = True
                                break
                            except PlaywrightTimeout:
                                continue
                        
                        if not servidores_encontrados:
                            print("⚠️ No se encontraron selectores conocidos")
                        
                        # Obtener HTML del player
                        player_html = page.content()
                        
                        # DEBUG: Guardar HTML para inspección (descomentar para debug)
                        with open('/tmp/debug_player.html', 'w', encoding='utf-8') as f:
                            f.write(player_html)
                        print("🐛 HTML del player guardado en /tmp/debug_player.html")
                        
                        player_soup = BeautifulSoup(player_html, 'html.parser')
                        
                        # Extraer servidores con BeautifulSoup
                        servidores = self._extraer_servidores_video(player_soup, player_url)
                        
                        # Si no encontró servidores, usar JavaScript en el navegador
                        if len(servidores) == 0:
                            print("⚠️ No se encontraron servidores en HTML, extrayendo con JS...")
                            
                            servidores_js = page.evaluate("""
                                () => {
                                    // Buscar todos los elementos li con onclick
                                    const botones = document.querySelectorAll('li[onclick]');
                                    const servidores = [];
                                    
                                    botones.forEach(boton => {
                                        const onclick = boton.getAttribute('onclick');
                                        
                                        // Verificar si contiene go_to_player
                                        if (onclick && onclick.includes('go_to_player')) {
                                            const match = onclick.match(/go_to_player\\('([^']+)'\\)/);
                                            
                                            if (match) {
                                                const span = boton.querySelector('span');
                                                const p = boton.querySelector('p');
                                                
                                                servidores.push({
                                                    nombre: span ? span.textContent.trim() : 'Desconocido',
                                                    descripcion: p ? p.textContent.trim() : '',
                                                    ruta_relativa: match[1]
                                                });
                                            }
                                        }
                                    });
                                    
                                    return servidores;
                                }
                            """)
                            
                            if servidores_js and len(servidores_js) > 0:
                                # Construir URLs completas
                                base_url = urlparse(player_url)
                                for srv in servidores_js:
                                    srv['url_redirect'] = f"{base_url.scheme}://{base_url.netloc}{srv['ruta_relativa']}"
                                
                                resultado['servidores'] = servidores_js
                                print(f"✅ Servidores extraídos con JS: {len(servidores_js)}")
                            else:
                                print("❌ No se pudieron extraer servidores ni con JS")
                                # Intentar obtener información de debug
                                debug_info = page.evaluate("""
                                    () => {
                                        return {
                                            totalLis: document.querySelectorAll('li').length,
                                            lisConOnclick: document.querySelectorAll('li[onclick]').length,
                                            bodyLength: document.body.innerHTML.length
                                        };
                                    }
                                """)
                                print(f"🔍 Debug - Total <li>: {debug_info.get('totalLis')}, Con onclick: {debug_info.get('lisConOnclick')}")
                        else:
                            resultado['servidores'] = servidores
                            print(f"✅ Servidores extraídos con BeautifulSoup: {len(servidores)}")
                        
                    except PlaywrightTimeout:
                        print("⚠️ Timeout cargando player, continuando sin servidores")
                    except Exception as e:
                        print(f"⚠️ Error cargando player: {e}")
                else:
                    print("⚠️ No se encontró URL del player")
                
                # Cerrar navegador (importante para liberar recursos)
                browser.close()
                print("✅ Scraping completado")
                
                return resultado
                
            except Exception as e:
                print(f"❌ Error en obtener_pelicula_por_slug: {e}")
                try:
                    browser.close()
                except:
                    pass
                raise
    
    def _extraer_info_basica(self, soup):
        """Extrae la información básica de una película"""
        info = {}
        
        try:
            # Título
            titulo_tag = soup.find('h1', class_='mb-2')
            info['titulo'] = titulo_tag.text.strip() if titulo_tag else None
            
            # Imagen
            img_tag = soup.find('figure', class_='md:col-span-2')
            if img_tag:
                img = img_tag.find('img')
                info['imagen'] = img['src'] if img else None
            else:
                info['imagen'] = None
            
            # Trailer
            trailer_iframe = soup.find('iframe', id='videoPlayer')
            info['trailer'] = trailer_iframe['src'] if trailer_iframe and trailer_iframe.get('src') else None
            
            # Descripción
            desc_container = soup.find('div', class_='capturar')
            if desc_container:
                desc_p = desc_container.find('p')
                info['descripcion'] = desc_p.text.strip() if desc_p else None
            else:
                info['descripcion'] = None
            
            # Detalles adicionales
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
            print(f"⚠️ Error extrayendo info básica: {e}")
        
        return info
    
    def _extraer_player_url(self, soup):
        """Extrae la URL del iframe player, filtrando YouTube"""
        try:
            iframes = soup.find_all('iframe', class_='absolute inset-0 w-full h-full')
            
            for iframe in iframes:
                if 'src' in iframe.attrs:
                    src = iframe['src']
                    # Filtrar YouTube
                    if 'youtube.com' not in src.lower() and 'youtu.be' not in src.lower():
                        return src
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error extrayendo player URL: {e}")
            return None
    
    def _extraer_servidores_video(self, soup, player_url):
        """Extrae los servidores de video desde el player"""
        try:
            servidores = []
            botones_servidor = soup.find_all('li', onclick=True)
            
            for boton in botones_servidor:
                try:
                    onclick = boton.get('onclick', '')
                    
                    if 'go_to_player' in onclick:
                        # Extraer la ruta del onclick
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
                    print(f"⚠️ Error extrayendo servidor individual: {e}")
                    continue
            
            return servidores
        
        except Exception as e:
            print(f"⚠️ Error extrayendo servidores: {e}")
            return []
    
    def obtener_pelicula_por_url_completa(self, url):
        """Obtiene información de una película por su URL completa"""
        try:
            slug = url.rstrip('/').split('/')[-1]
            return self.obtener_pelicula_por_slug(slug)
        except Exception as e:
            raise ValueError(f"URL inválida: {str(e)}")


# Instancia singleton
scraper_movie_playwright = ScraperMoviePlaywright()