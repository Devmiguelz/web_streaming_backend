"""
pelicula_scraper_playwright_v2.py
Versión mejorada con anti-detección avanzada y manejo de popups
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import uuid
import re
from urllib.parse import urlparse
import random
import time

class ScraperMoviePlaywrightV2:
    """Scraper avanzado con Playwright"""
    
    BASE_URL = "https://cinecalidad.bar"
    
    def obtener_pelicula_por_slug(self, slug):
        """Obtiene información de película con técnicas anti-detección avanzadas"""
        with sync_playwright() as playwright:
            try:
                # Lanzar navegador en modo NO headless para evitar detección
                browser = playwright.chromium.launch(
                    headless=True,  # Cambia a False para debugging
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--window-size=1920,1080'
                    ]
                )
                
                # Crear contexto con fingerprint realista
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='es-ES',
                    timezone_id='America/Bogota',
                    geolocation={'latitude': 10.9639, 'longitude': -74.7964},
                    permissions=['geolocation'],
                    color_scheme='dark',
                    java_script_enabled=True
                )
                
                # Script anti-detección mejorado
                context.add_init_script("""
                    // Ocultar webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Chrome runtime
                    window.navigator.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Plugins realistas
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                            {name: 'Native Client', filename: 'internal-nacl-plugin'}
                        ]
                    });
                    
                    // Languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['es-ES', 'es', 'en-US', 'en']
                    });
                    
                    // Platform
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32'
                    });
                    
                    // Hardware concurrency
                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8
                    });
                    
                    // Device memory
                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8
                    });
                    
                    // Permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({state: Notification.permission}) :
                            originalQuery(parameters)
                    );
                """)
                
                # Crear página
                page = context.new_page()
                
                # Bloquear solo recursos pesados, NO JavaScript
                def route_handler(route):
                    resource_type = route.request.resource_type
                    if resource_type in ['image', 'media', 'font']:
                        route.abort()
                    elif 'google-analytics' in route.request.url or 'doubleclick' in route.request.url:
                        route.abort()
                    else:
                        route.continue_()
                
                page.route('**/*', route_handler)
                
                # Manejar popups/nuevas ventanas
                page.on('popup', lambda popup: popup.close())
                
                # URL de la película
                url_pelicula = f"{self.BASE_URL}/peli/{slug}/"
                print(f"🎬 Navegando a: {url_pelicula}")
                
                # Simular comportamiento humano
                time.sleep(random.uniform(1, 2))
                
                # Navegar
                response = page.goto(url_pelicula, wait_until='domcontentloaded', timeout=30000)
                
                if not response or response.status >= 400:
                    print(f"❌ Error HTTP: {response.status if response else 'Sin respuesta'}")
                    browser.close()
                    return None
                
                # Esperar título
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
                
                # Resultado base
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
                    print(f"🎮 Player encontrado: {player_url}")
                    
                    # Delay realista
                    time.sleep(random.uniform(2, 4))
                    
                    try:
                        print("🔄 Cargando player...")
                        
                        # Navegar al player
                        player_response = page.goto(player_url, wait_until='load', timeout=30000)
                        
                        if not player_response or player_response.status >= 400:
                            print(f"❌ Error cargando player: {player_response.status if player_response else 'Sin respuesta'}")
                            browser.close()
                            return resultado
                        
                        print("⏳ Esperando JavaScript dinámico...")
                        
                        # Esperar más tiempo para JS dinámico
                        time.sleep(6)
                        
                        # Scroll para activar lazy loading
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(1)
                        
                        # Intentar varios selectores
                        selectores_a_probar = [
                            'li[onclick*="go_to_player"]',
                            '.OD li[onclick]',
                            '.OptionsLangDisp li[onclick]',
                            'li[onclick]'
                        ]
                        
                        selector_encontrado = None
                        for selector in selectores_a_probar:
                            try:
                                page.wait_for_selector(selector, timeout=3000)
                                selector_encontrado = selector
                                print(f"✅ Selector encontrado: {selector}")
                                break
                            except PlaywrightTimeout:
                                continue
                        
                        # Extraer con JavaScript del navegador
                        print("🔍 Extrayendo servidores...")
                        servidores_data = page.evaluate("""
                            () => {
                                const botones = document.querySelectorAll('li[onclick]');
                                const servidores = [];
                                
                                console.log('Botones encontrados:', botones.length);
                                
                                botones.forEach((boton, idx) => {
                                    const onclick = boton.getAttribute('onclick');
                                    console.log('Botón', idx, ':', onclick);
                                    
                                    if (onclick && onclick.includes('go_to_player')) {
                                        const match = onclick.match(/go_to_player\\('([^']+)'\\)/);
                                        
                                        if (match) {
                                            const span = boton.querySelector('span');
                                            const p = boton.querySelector('p');
                                            const img = boton.querySelector('img');
                                            
                                            const servidor = {
                                                nombre: span ? span.textContent.trim() : 'Desconocido',
                                                descripcion: p ? p.textContent.trim() : '',
                                                ruta_relativa: match[1],
                                                img_src: img ? img.src : null
                                            };
                                            
                                            console.log('Servidor encontrado:', servidor);
                                            servidores.push(servidor);
                                        }
                                    }
                                });
                                
                                return {
                                    servidores: servidores,
                                    total_li: document.querySelectorAll('li').length,
                                    total_onclick: botones.length,
                                    html_sample: document.body.innerHTML.substring(0, 500)
                                };
                            }
                        """)
                        
                        print(f"📊 Debug - Total LI: {servidores_data['total_li']}, Con onclick: {servidores_data['total_onclick']}")
                        
                        if servidores_data['servidores'] and len(servidores_data['servidores']) > 0:
                            # Construir URLs completas
                            base_url = urlparse(player_url)
                            for srv in servidores_data['servidores']:
                                srv['url_redirect'] = f"{base_url.scheme}://{base_url.netloc}{srv['ruta_relativa']}"
                            
                            resultado['servidores'] = servidores_data['servidores']
                            print(f"✅ {len(servidores_data['servidores'])} servidores extraídos")
                        else:
                            print("⚠️ No se encontraron servidores")
                            print(f"📄 HTML sample: {servidores_data['html_sample'][:200]}...")
                            
                            # Fallback: Extraer con BeautifulSoup
                            player_html = page.content()
                            player_soup = BeautifulSoup(player_html, 'html.parser')
                            servidores_bs = self._extraer_servidores_video(player_soup, player_url)
                            
                            if servidores_bs:
                                resultado['servidores'] = servidores_bs
                                print(f"✅ {len(servidores_bs)} servidores con BeautifulSoup (fallback)")
                        
                    except PlaywrightTimeout:
                        print("⚠️ Timeout cargando player")
                    except Exception as e:
                        print(f"❌ Error en player: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("⚠️ No se encontró player URL")
                
                # Cerrar navegador
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
    
    def _extraer_servidores_video(self, soup, player_url):
        """Extrae servidores con BeautifulSoup (fallback)"""
        try:
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
            print(f"⚠️ Error extrayendo servidores: {e}")
            return []
    
    def obtener_pelicula_por_url_completa(self, url):
        """Obtiene película por URL completa"""
        try:
            slug = url.rstrip('/').split('/')[-1]
            return self.obtener_pelicula_por_slug(slug)
        except Exception as e:
            raise ValueError(f"URL inválida: {str(e)}")


# Instancia singleton
scraper_movie_playwright_v2 = ScraperMoviePlaywrightV2()