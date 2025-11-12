"""
pelicula_scraper_playwright_v3.py
FIX: Manejo correcto de referrer para evitar 403
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import uuid
import re
from urllib.parse import urlparse
import random
import time

class ScraperMoviePlaywrightV3:
    """Scraper con manejo correcto de referrer"""
    
    BASE_URL = "https://cinecalidad.bar"
    
    def obtener_pelicula_por_slug(self, slug):
        """Obtiene información de película respetando referrer"""
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-gpu',
                        '--window-size=1920,1080'
                    ]
                )
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='es-ES',
                    timezone_id='America/Bogota',
                    java_script_enabled=True
                )
                
                # Script anti-detección
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    window.navigator.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {}
                    };
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            {name: 'Chrome PDF Plugin'},
                            {name: 'Chrome PDF Viewer'},
                            {name: 'Native Client'}
                        ]
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['es-ES', 'es', 'en']
                    });
                """)
                
                page = context.new_page()
                
                # Bloquear solo recursos pesados
                def route_handler(route):
                    resource_type = route.request.resource_type
                    if resource_type in ['image', 'media', 'font']:
                        route.abort()
                    elif 'google-analytics' in route.request.url or 'doubleclick' in route.request.url:
                        route.abort()
                    else:
                        route.continue_()
                
                page.route('**/*', route_handler)
                page.on('popup', lambda popup: popup.close())
                
                # Navegar a la página de la película
                url_pelicula = f"{self.BASE_URL}/peli/{slug}/"
                print(f"🎬 Navegando a: {url_pelicula}")
                
                time.sleep(random.uniform(1, 2))
                
                response = page.goto(url_pelicula, wait_until='domcontentloaded', timeout=30000)
                
                if not response or response.status >= 400:
                    print(f"❌ Error HTTP: {response.status if response else 'Sin respuesta'}")
                    browser.close()
                    return None
                
                try:
                    page.wait_for_selector('h1.mb-2', timeout=10000)
                    print("✅ Página principal cargada")
                except PlaywrightTimeout:
                    print("⚠️ Timeout esperando título")
                
                # Extraer información básica
                html = page.content()
                soup = BeautifulSoup(html, 'html.parser')
                info = self._extraer_info_basica(soup)
                
                if not info.get('titulo'):
                    print("❌ No se encontró la película")
                    browser.close()
                    return None
                
                print(f"📝 Película: {info.get('titulo')}")
                
                resultado = {
                    'id': str(uuid.uuid4()),
                    **info,
                    'url_pelicula': url_pelicula,
                    'slug': slug,
                    'servidores': []
                }
                
                # Extraer player URL del HTML
                player_url = self._extraer_player_url(soup)
                
                if player_url:
                    resultado['player_url'] = player_url
                    print(f"🎮 Player encontrado: {player_url}")
                    
                    # MÉTODO 1: Hacer clic en el iframe para que cargue naturalmente
                    print("🖱️ Método 1: Simulando clic en el iframe...")
                    time.sleep(2)
                    
                    try:
                        # Buscar el iframe en la página
                        iframe_selector = 'iframe.absolute.inset-0.w-full.h-full'
                        
                        # Esperar a que el iframe esté visible
                        page.wait_for_selector(iframe_selector, timeout=5000)
                        
                        # Hacer scroll al iframe
                        page.evaluate("""
                            () => {
                                const iframe = document.querySelector('iframe.absolute.inset-0.w-full.h-full');
                                if (iframe) {
                                    iframe.scrollIntoView({behavior: 'smooth', block: 'center'});
                                }
                            }
                        """)
                        
                        time.sleep(2)
                        
                        # Obtener el frame del player (ya está cargado en la página principal)
                        player_frame = None
                        for frame in page.frames:
                            if player_url in frame.url:
                                player_frame = frame
                                print("✅ Frame del player encontrado en la página principal")
                                break
                        
                        if player_frame:
                            # Esperar a que cargue el contenido del frame
                            time.sleep(5)
                            
                            # Extraer servidores desde el frame
                            servidores_data = player_frame.evaluate("""
                                () => {
                                    const botones = document.querySelectorAll('li[onclick]');
                                    const servidores = [];
                                    
                                    botones.forEach((boton) => {
                                        const onclick = boton.getAttribute('onclick');
                                        
                                        if (onclick && onclick.includes('go_to_player')) {
                                            const match = onclick.match(/go_to_player\\('([^']+)'\\)/);
                                            
                                            if (match) {
                                                const span = boton.querySelector('span');
                                                const p = boton.querySelector('p');
                                                const img = boton.querySelector('img');
                                                
                                                servidores.push({
                                                    nombre: span ? span.textContent.trim() : 'Desconocido',
                                                    descripcion: p ? p.textContent.trim() : '',
                                                    ruta_relativa: match[1],
                                                    img_src: img ? img.src : null
                                                });
                                            }
                                        }
                                    });
                                    
                                    return {
                                        servidores: servidores,
                                        total_li: document.querySelectorAll('li').length,
                                        total_onclick: document.querySelectorAll('li[onclick]').length
                                    };
                                }
                            """)
                            
                            print(f"📊 Frame - Total LI: {servidores_data['total_li']}, Con onclick: {servidores_data['total_onclick']}")
                            
                            if servidores_data['servidores'] and len(servidores_data['servidores']) > 0:
                                # Construir URLs completas
                                base_url = urlparse(player_url)
                                for srv in servidores_data['servidores']:
                                    srv['url_redirect'] = f"{base_url.scheme}://{base_url.netloc}{srv['ruta_relativa']}"
                                
                                resultado['servidores'] = servidores_data['servidores']
                                print(f"✅ {len(servidores_data['servidores'])} servidores extraídos desde el frame")
                            else:
                                print("⚠️ No se encontraron servidores en el frame")
                        
                        else:
                            print("⚠️ No se pudo acceder al frame del player")
                            
                    except Exception as e:
                        print(f"⚠️ Error con método de frame: {e}")
                    
                    # MÉTODO 2: Si el método 1 falló, navegar con referrer correcto
                    if len(resultado['servidores']) == 0:
                        print("🔄 Método 2: Navegando con referrer...")
                        try:
                            # Navegar con referer explícito
                            player_response = page.goto(
                                player_url,
                                wait_until='load',
                                timeout=30000,
                                referer=url_pelicula  # ¡CLAVE! Simular que venimos de la página
                            )
                            
                            if player_response and player_response.status < 400:
                                print("✅ Player cargado con referrer")
                                
                                time.sleep(6)
                                
                                # Scroll para activar lazy loading
                                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                time.sleep(2)
                                page.evaluate("window.scrollTo(0, 0)")
                                time.sleep(1)
                                
                                # Extraer servidores
                                servidores_data = page.evaluate("""
                                    () => {
                                        const botones = document.querySelectorAll('li[onclick]');
                                        const servidores = [];
                                        
                                        botones.forEach((boton) => {
                                            const onclick = boton.getAttribute('onclick');
                                            
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
                                        
                                        return {
                                            servidores: servidores,
                                            total_li: document.querySelectorAll('li').length,
                                            total_onclick: document.querySelectorAll('li[onclick]').length
                                        };
                                    }
                                """)
                                
                                print(f"📊 Navegación directa - Total LI: {servidores_data['total_li']}, Con onclick: {servidores_data['total_onclick']}")
                                
                                if servidores_data['servidores'] and len(servidores_data['servidores']) > 0:
                                    base_url = urlparse(player_url)
                                    for srv in servidores_data['servidores']:
                                        srv['url_redirect'] = f"{base_url.scheme}://{base_url.netloc}{srv['ruta_relativa']}"
                                    
                                    resultado['servidores'] = servidores_data['servidores']
                                    print(f"✅ {len(servidores_data['servidores'])} servidores extraídos con navegación")
                            else:
                                print(f"❌ Error cargando player: {player_response.status if player_response else 'Sin respuesta'}")
                                
                        except Exception as e:
                            print(f"❌ Error en método 2: {e}")
                    
                    # MÉTODO 3: Extraer headers del iframe y hacer petición manual
                    if len(resultado['servidores']) == 0:
                        print("🔄 Método 3: Extrayendo headers del iframe...")
                        try:
                            # Interceptar la petición del iframe
                            iframe_headers = {}
                            
                            def handle_request(request):
                                if player_url in request.url:
                                    iframe_headers['headers'] = request.headers
                                    print(f"📋 Headers interceptados del iframe")
                            
                            page.on('request', handle_request)
                            
                            # Recargar la página para capturar headers
                            page.reload(wait_until='load')
                            time.sleep(3)
                            
                            if iframe_headers:
                                print(f"✅ Headers capturados: {list(iframe_headers.get('headers', {}).keys())}")
                        
                        except Exception as e:
                            print(f"⚠️ Error en método 3: {e}")
                else:
                    print("⚠️ No se encontró player URL")
                
                browser.close()
                print("✅ Scraping completado")
                
                return resultado
                
            except Exception as e:
                print(f"❌ Error general: {e}")
                import traceback
                traceback.print_exc()
                try:
                    browser.close()
                except:
                    pass
                raise
    
    def _extraer_info_basica(self, soup):
        """Extrae información básica de la película"""
        info = {}
        
        try:
            titulo_tag = soup.find('h1', class_='mb-2')
            info['titulo'] = titulo_tag.text.strip() if titulo_tag else None
            
            img_tag = soup.find('figure', class_='md:col-span-2')
            if img_tag:
                img = img_tag.find('img')
                info['imagen'] = img['src'] if img else None
            else:
                info['imagen'] = None
            
            trailer_iframe = soup.find('iframe', id='videoPlayer')
            info['trailer'] = trailer_iframe['src'] if trailer_iframe and trailer_iframe.get('src') else None
            
            desc_container = soup.find('div', class_='capturar')
            if desc_container:
                desc_p = desc_container.find('p')
                info['descripcion'] = desc_p.text.strip() if desc_p else None
            else:
                info['descripcion'] = None
            
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
        """Extrae la URL del player iframe"""
        try:
            iframes = soup.find_all('iframe', class_='absolute inset-0 w-full h-full')
            
            for iframe in iframes:
                if 'src' in iframe.attrs:
                    src = iframe['src']
                    if 'youtube.com' not in src.lower() and 'youtu.be' not in src.lower():
                        return src
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error extrayendo player URL: {e}")
            return None
    
    def obtener_pelicula_por_url_completa(self, url):
        """Obtiene película por URL completa"""
        try:
            slug = url.rstrip('/').split('/')[-1]
            return self.obtener_pelicula_por_slug(slug)
        except Exception as e:
            raise ValueError(f"URL inválida: {str(e)}")


# Instancia singleton
scraper_movie_playwright_v3 = ScraperMoviePlaywrightV3()