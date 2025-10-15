import requests
from bs4 import BeautifulSoup
import json
import csv
import time
from urllib.parse import urljoin, urlparse
import base64

class AdvancedLinksExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def cargar_peliculas_json(self, archivo_json):
        """Carga películas desde JSON"""
        try:
            with open(archivo_json, 'r', encoding='utf-8') as f:
                peliculas = json.load(f)
            print(f"✓ {len(peliculas)} películas cargadas desde {archivo_json}")
            return peliculas
        except FileNotFoundError:
            print(f"❌ Error: No se encontró el archivo {archivo_json}")
            return []
    
    def extraer_player_url(self, soup):
        """
        Extrae la URL del iframe player desde la página de la película
        """
        try:                        
            iframe = soup.find('iframe')
            if iframe and 'src' in iframe.attrs:
                player_url = iframe['src']
                print(f"  ✓ Player URL encontrada: {player_url}")
                return player_url
            else:
                print("  ⚠️ No se encontró iframe")
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
    
    def _extraer_info_pelicula(self, soup):
        """Extrae la información básica de una película"""
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

                    # Mapeamos los posibles campos
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

            print(f"✓ Información básica extraída: {info.get('titulo', 'Sin título')}")

        except Exception as e:
            print(f"❌ Error al extraer información básica de película: {e}")

        return info

    def procesar_pelicula(self, pelicula):
        """
        Procesa una película completa: extrae player y todos los servidores
        """
        titulo = pelicula.get('titulo', 'Desconocido')
        url_pelicula = pelicula.get('enlace')
        
        if not url_pelicula:
            print(f"  ⚠️ {titulo}: No tiene URL")
            return None
        
        response = self.session.get(url_pelicula, headers=self.headers, timeout=15)
        response.raise_for_status()
            
        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. Extraer info básica
        info_basica = self._extraer_info_pelicula(soup)
        
        resultado = {
            **info_basica,
            'servidores': []
        }
        
        # 2. Extraer URL del player
        player_url = self.extraer_player_url(soup)
        if not player_url:
            return resultado
        
        resultado['player_url'] = player_url
        
        # 3. Extraer servidores del player
        servidores = self.extraer_servidores_video(player_url, url_pelicula)
                
        resultado['servidores'] = servidores
        
        return resultado
    
    def procesar_peliculas(self, archivo_json, limite=None, delay=10):
        """
        Procesa múltiples películas
        """
        peliculas = self.cargar_peliculas_json(archivo_json)
        
        if not peliculas:
            return []
        
        if limite:
            peliculas = peliculas[:limite]
        
        resultados = []
        total = len(peliculas)
        
        print(f"\n{'='*80}")
        print(f"Procesando {total} películas...")
        print('='*80)
        
        for i, pelicula in enumerate(peliculas, 1):
            print(f"\n[{i}/{total}] {pelicula.get('titulo', 'Sin título')}")
            
            resultado = self.procesar_pelicula(pelicula)
            
            if resultado:
                # Mostrar servidores encontrados
                if resultado.get('servidores'):
                    for servidor in resultado['servidores']:
                        print(f"    ✓ {servidor['nombre']} - {servidor['descripcion']}")
                else:
                    print("    ⚠️ No se encontraron servidores")
                
                resultados.append(resultado)
            
            # Pausa entre películas
            if i < total:
                time.sleep(delay)
        
        return resultados
    
    def guardar_resultados(self, resultados, prefijo='peliculas_servidores'):
        """
        Guarda resultados únicamente en un archivo JSON
        """
        if not resultados:
            print("No hay resultados para guardar")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archivo_json = f'{prefijo}_{timestamp}.json'

        with open(archivo_json, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

        print(f"\n✓ JSON guardado: {archivo_json}")


# Ejemplo de uso
if __name__ == "__main__":
    extractor = AdvancedLinksExtractor()
    
    print("🎬 EXTRACTOR AVANZADO DE ENLACES DE VIDEO")
    print("="*80)
    
    # Solicitar archivo JSON
    archivo_json = input("\nArchivo JSON de películas (default: peliculas_pagina_1.json): ").strip()
    if not archivo_json:
        archivo_json = "peliculas_pagina_1.json"
    
    # Preguntar cuántas procesar
    print("\n¿Cuántas películas procesar?")
    print("  1. Solo 3 (prueba rápida)")
    print("  2. 10 películas")
    print("  3. 25 películas")
    print("  4. Todas")
    
    opcion = input("\nOpción (1-4): ").strip()
    limite_map = {'1': 3, '2': 10, '3': 25, '4': None}
    limite = limite_map.get(opcion, 3)
    
    if limite:
        print(f"\n⚙️ Procesando {limite} películas...")
    else:
        print("\n⚙️ Procesando TODAS las películas (esto puede tardar)...")
    
    # Procesar
    resultados = extractor.procesar_peliculas(
        archivo_json=archivo_json,
        limite=limite,
        delay=5
    )
    
    if resultados:
        print(f"\n{'='*80}")
        print(f"✅ Completado: {len(resultados)} películas procesadas")
        print('='*80)
        
        # Estadísticas
        total_servidores = sum(len(p.get('servidores', [])) for p in resultados)
        print(f"\n📊 ESTADÍSTICAS:")
        print(f"  - Total servidores encontrados: {total_servidores}")
        print(f"  - Promedio por película: {total_servidores/len(resultados):.1f}")
        
        # Guardar
        extractor.guardar_resultados(resultados)
    else:
        print("\n❌ No se procesó ninguna película")