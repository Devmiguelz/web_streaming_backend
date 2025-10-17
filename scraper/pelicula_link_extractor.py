import requests
from bs4 import BeautifulSoup
import json
import os
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
        Extrae la URL del iframe player desde la página de la película.
        Filtra iframes de YouTube para evitar trailers.
        """
        try:
            # Buscar todos los iframes con las clases específicas
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
        url_pelicula = pelicula.get('enlace') or pelicula.get('url_pelicula')
        
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
            'año': pelicula.get('año'),
            'url_pelicula': url_pelicula,
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
    
    def actualizar_servidores_pelicula(self, pelicula, peliculas_database=None):
        """
        Actualiza solo los servidores de una película que ya fue procesada
        """
        titulo = pelicula.get('titulo', 'Desconocido')
        url_pelicula = pelicula.get('url_pelicula') or pelicula.get('enlace')
        
        # Si no tiene URL, buscarla en database
        if not url_pelicula and peliculas_database:
            print(f"  🔍 Buscando URL en database para: {titulo}")
            for p_db in peliculas_database:
                if p_db.get('titulo') == titulo:
                    url_pelicula = p_db.get('enlace')
                    if url_pelicula:
                        print(f"  ✓ URL encontrada en database")
                        pelicula['url_pelicula'] = url_pelicula
                    break
        
        if not url_pelicula:
            print(f"  ⚠️ {titulo}: No tiene URL ni en cache ni en database")
            return pelicula
        
        try:
            response = self.session.get(url_pelicula, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraer URL del player
            player_url = self.extraer_player_url(soup)
            if not player_url:
                print(f"  ⚠️ No se encontró player URL")
                return pelicula
            
            # Actualizar player_url
            pelicula['player_url'] = player_url
            
            # Extraer servidores
            servidores = self.extraer_servidores_video(player_url, url_pelicula)
            
            # Actualizar servidores
            pelicula['servidores'] = servidores
            
            if servidores:
                print(f"  ✅ {len(servidores)} servidores actualizados")
            else:
                print(f"  ⚠️ No se encontraron servidores")
            
            return pelicula
            
        except Exception as e:
            print(f"  ❌ Error actualizando: {e}")
            return pelicula
    
    def recuperar_servidores_faltantes(self, archivo_cache, archivo_database, delay=5):
        """
        Lee el JSON de cache y reprocesa solo las películas sin servidores
        """
        # Cargar películas desde cache
        peliculas = self.cargar_peliculas_json(archivo_cache)

        if not peliculas:
            return []
        
        # Cargar database si se proporciona
        peliculas_database = None
        if archivo_database:
            print(f"\n📥 Cargando database para buscar URLs faltantes...")
            peliculas_database = self.cargar_peliculas_json(archivo_database)
        
        # Filtrar películas sin servidores o con player_url de YouTube
        peliculas_sin_servidores = []
        for pelicula in peliculas:
            servidores = pelicula.get('servidores', [])
            player_url = pelicula.get('player_url', '')
            
            # Si no tiene servidores O si el player_url es de YouTube
            if not servidores or 'youtube.com' in player_url.lower():
                peliculas_sin_servidores.append(pelicula)
        
        total = len(peliculas_sin_servidores)
        
        if total == 0:
            print("✅ Todas las películas ya tienen servidores!")
            return peliculas
        
        print(f"\n{'='*80}")
        print(f"🔄 Recuperando servidores de {total} películas...")
        print('='*80)
        
        for i, pelicula in enumerate(peliculas_sin_servidores, 1):
            print(f"\n[{i}/{total}] {pelicula.get('titulo', 'Sin título')}")
            
            # Actualizar la película
            pelicula_actualizada = self.actualizar_servidores_pelicula(pelicula, peliculas_database)
            
            # Actualizar en la lista original
            titulo = pelicula_actualizada.get('titulo')
            for j, p in enumerate(peliculas):
                if p.get('titulo') == titulo:
                    peliculas[j] = pelicula_actualizada
                    break
            
            # Pausa entre películas
            if i < total:
                time.sleep(delay)
        
        # Guardar resultados actualizados
        self.guardar_resultados(peliculas, prefijo='peliculas_actualizadas')
        
        return peliculas
    
    def recuperar_años_faltantes(self, archivo_cache, archivo_database, delay=1):
        """
        Lee el JSON de cache y actualiza solo las películas sin año desde database
        """
        # Cargar películas desde cache
        peliculas = self.cargar_peliculas_json(archivo_cache)

        if not peliculas:
            return []
        
        # Cargar database si se proporciona
        peliculas_database = None
        if archivo_database:
            print(f"\n📥 Cargando database para buscar años faltantes...")
            peliculas_database = self.cargar_peliculas_json(archivo_database)
        else:
            print("❌ Se requiere archivo database para actualizar años")
            return peliculas
        
        # Filtrar películas sin año
        peliculas_sin_año = []
        for pelicula in peliculas:
            año = pelicula.get('año')
            
            # Si no tiene año o el año está vacío
            if not año or año == "" or año is None:
                peliculas_sin_año.append(pelicula)
        
        total = len(peliculas_sin_año)
        
        if total == 0:
            print("✅ Todas las películas ya tienen año!")
            return peliculas
        
        print(f"\n{'='*80}")
        print(f"🔄 Actualizando años de {total} películas...")
        print('='*80)
        
        actualizadas = 0
        no_encontradas = 0
        
        for i, pelicula in enumerate(peliculas_sin_año, 1):
            titulo = pelicula.get('titulo', 'Sin título')
            print(f"\n[{i}/{total}] {titulo}")
            
            # Buscar año en database
            año_encontrado = None
            for p_db in peliculas_database:
                if p_db.get('titulo') == titulo:
                    año_encontrado = p_db.get('año')
                    break
            
            # Actualizar en la lista original
            for j, p in enumerate(peliculas):
                if p.get('titulo') == titulo:
                    if año_encontrado:
                        peliculas[j]['año'] = año_encontrado
                        print(f"   ✅ Año actualizado: {año_encontrado}")
                        actualizadas += 1
                    else:
                        print(f"   ⚠️  Año no encontrado en database")
                        no_encontradas += 1
                    break
            
            # Pausa entre películas
            if i < total:
                time.sleep(delay)
        
        # Resumen
        print(f"\n{'='*80}")
        print(f"📊 Resumen de actualización de años:")
        print(f"   ✅ Actualizadas: {actualizadas}")
        print(f"   ⚠️  No encontradas: {no_encontradas}")
        print('='*80)
        
        # Guardar resultados actualizados
        self.guardar_resultados(peliculas, prefijo='peliculas_actualizados')

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
            resultado["id"] = i
            
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
    
    def guardar_resultados(self, resultados, prefijo='peliculas'):
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

    def seleccionar_archivo_json(self, carpeta='database'):
        """
        Lista los archivos JSON disponibles y permite seleccionar uno
        """

        database_path = os.path.join(os.path.dirname(__file__), f'../{carpeta}')
        
        # Verificar que existe la carpeta
        if not os.path.exists(database_path):
            print(f"❌ Error: No se encontró la carpeta {database_path}")
            return None
        
        # Obtener todos los archivos JSON
        archivos_json = sorted([f for f in os.listdir(database_path) if f.endswith('.json')])
        
        if not archivos_json:
            print(f"❌ No se encontraron archivos JSON en {database_path}")
            return None
        
        # Mostrar lista de archivos
        print(f"\n📁 Archivos JSON disponibles en {carpeta}/:")
        print("-" * 90)
        for i, archivo in enumerate(archivos_json, 1):
            ruta_completa = os.path.join(database_path, archivo)
            tamano = os.path.getsize(ruta_completa) / 1024
            
            # Intentar leer el número de películas
            try:
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                    num_peliculas = len(datos) if isinstance(datos, list) else "?"
                    # Contar películas sin servidores
                    sin_servidores = sum(1 for p in datos if not p.get('servidores', []))
                    print(f"  {i}. {archivo:<35} ({tamano:>6.1f} KB | {num_peliculas:>4} películas | {sin_servidores:>3} sin servidores)")
            except:
                print(f"  {i}. {archivo:<35} ({tamano:>6.1f} KB)")
        
        print("-" * 90)
        
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
    extractor = AdvancedLinksExtractor()
    
    print("🎬 EXTRACTOR AVANZADO DE ENLACES DE VIDEO")
    print("="*80)
    
    # Menú principal
    print("\n¿Qué deseas hacer?")
    print("  1. Procesar películas desde database/")
    print("  2. Recuperar servidores faltantes desde cache/")
    print("  3. Actualizar años faltantes desde cache/ (requiere database/)")
    
    modo = input("\nOpción (1-3): ").strip()
    
    if modo == '3':

        print("\n🔄 MODO: Actualizar años faltantes")
        archivo_cache = extractor.seleccionar_archivo_json(carpeta='cache')        
        if not archivo_cache:
            print("\n❌ Debes seleccionar un archivo de cache para continuar")
            exit(1)
        
        archivo_database = extractor.seleccionar_archivo_json(carpeta='database')        
        if not archivo_database:
            print("\n❌ Debes seleccionar un archivo de database para continuar")
            exit(1)
        
        # Actualizar años
        extractor.recuperar_años_faltantes(
            archivo_cache=archivo_cache,
            archivo_database=archivo_database,
            delay=1
        )

    elif modo == '2':
        # Modo recuperación
        print("\n🔄 MODO: Recuperar servidores faltantes")
        archivo_cache = extractor.seleccionar_archivo_json(carpeta='cache')
        
        if not archivo_cache:
            print("\n❌ Debes seleccionar un archivo de cache para continuar")
            exit(1)

        # Preguntar si desea cargar database para URLs faltantes
        print("\n¿Deseas cargar un archivo de database/ para buscar URLs faltantes?")
        print("  1. Sí, seleccionar archivo de database/")
        print("  2. No, solo usar URLs que ya están en cache")
        
        usar_db = input("\nOpción (1-2): ").strip()
        
        archivo_database = None
        if usar_db == '1':
            print("\n📂 Selecciona el archivo de database:")
            archivo_database = extractor.seleccionar_archivo_json(carpeta='database')
        
        # Recuperar servidores
        extractor.recuperar_servidores_faltantes(
            archivo_cache=archivo_cache,
            archivo_database=archivo_database,
            delay=5
        )
        
    elif modo == '1':
        # Modo normal
        print("\n📥 MODO: Procesar películas nuevas")
        archivo_database = extractor.seleccionar_archivo_json(carpeta='database')
        
        if not archivo_database:
            exit(1)
        
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
            archivo_json=archivo_database,
            limite=limite,
            delay=5
        )
        
        if resultados:
            print(f"\n{'='*80}")
            print(f"✅ Completado: {len(resultados)} películas procesadas")
            print('='*80)
            
            # Estadísticas
            total_servidores = sum(len(p.get('servidores', [])) for p in resultados)
            sin_servidores = sum(1 for p in resultados if not p.get('servidores', []))
            
            print(f"\n📊 ESTADÍSTICAS:")
            print(f"  - Total servidores encontrados: {total_servidores}")
            print(f"  - Promedio por película: {total_servidores/len(resultados):.1f}")
            print(f"  - Películas sin servidores: {sin_servidores}")
            
            # Guardar
            extractor.guardar_resultados(resultados)
        else:
            print("\n❌ No se procesó ninguna película")