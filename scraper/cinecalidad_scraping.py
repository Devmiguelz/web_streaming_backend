import requests
from bs4 import BeautifulSoup
import json
import time

class CinecalidadScraper:
    def __init__(self):
        self.base_url = "https://cinecalidad.bar"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def extraer_peliculas(self, url=None, pagina=1, tipo='pelicula'):
        """
        Extrae información de las películas de la página principal o una página específica
        """
        if url is None:
            if pagina == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}/page/{pagina}/"
        
        try:
            print(f"Scrapeando: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Encontrar todos los artículos de películas
            peliculas = soup.find_all('article', class_='tposty')
            
            datos_peliculas = []
            
            for pelicula in peliculas:
                try:
                    # Extraer el enlace
                    enlace_tag = pelicula.find('a', class_='absolute')
                    enlace = enlace_tag['href'] if enlace_tag else None
                    
                    # Extraer el título
                    titulo_span = pelicula.find('span', class_='sr-only')
                    titulo = titulo_span.text.strip() if titulo_span else None
                    
                    # Extraer la imagen
                    img_tag = pelicula.find('img')
                    imagen = img_tag['src'] if img_tag else None
                    
                    # Extraer calidad y año
                    calidad_tag = pelicula.find('span', class_='quality')
                    calidad = calidad_tag.text.strip() if calidad_tag else None
                    
                    año_tag = pelicula.find('span', class_='year')
                    año = año_tag.text.strip() if año_tag else None
                    
                    # Extraer descripción
                    desc_tag = pelicula.find('p', class_='text-sm opacity-70')
                    descripcion = desc_tag.text.strip() if desc_tag else None
                    
                    # Extraer géneros
                    generos_container = pelicula.find('p', class_=['absolute', 'bottom-0'])
                    generos = []
                    if generos_container:
                        generos_links = generos_container.find_all('a')
                        generos = [g.text.strip() for g in generos_links]
                    
                    pelicula_data = {
                        'tipo': tipo,
                        'titulo': titulo,
                        'enlace': enlace,
                        'imagen': imagen,
                        'calidad': calidad,
                        'año': año,
                        'descripcion': descripcion,
                        'generos': generos if generos else []
                    }
                    
                    datos_peliculas.append(pelicula_data)
                    
                except Exception as e:
                    print(f"Error al extraer película: {e}")
                    continue
            
            print(f"✓ {len(datos_peliculas)} películas extraídas de la página {pagina}")
            return datos_peliculas
            
        except Exception as e:
            print(f"Error al hacer scraping: {e}")
            return []
        
    def extraer_series(self, url=None, pagina=1, tipo='serie'):
        """
        Extrae información de las series de la página principal o una página específica
        """
        if url is None:
            if pagina == 1:
                url = f"{self.base_url}/serie/"
            else:
                url = f"{self.base_url}/serie/page/{pagina}/"
    
        try:
            print(f"Scrapeando: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
        
            soup = BeautifulSoup(response.content, 'html.parser')
        
            # Encontrar todos los artículos de series
            series = soup.find_all('article', class_='tposty')
        
            datos_series = []
        
            for serie in series:
                try:                    
                    # Extraer información de temporadas y episodios
                    temporadas_tag = serie.find('span', class_='last-s')
                    temporadas = temporadas_tag.text.strip() if temporadas_tag else None
                    
                    episodios_tag = serie.find('span', class_='last-ep')
                    episodios = episodios_tag.text.strip() if episodios_tag else None
                    
                    # Extraer el enlace
                    enlace_tag = serie.find('a', class_='absolute')
                    enlace = enlace_tag['href'] if enlace_tag else None
                
                    # Extraer el título
                    titulo_span = serie.find('span', class_='sr-only')
                    titulo = titulo_span.text.strip() if titulo_span else None
                
                    # Extraer la imagen
                    img_tag = serie.find('img')
                    imagen = img_tag['src'] if img_tag else None
                
                    # Extraer calidad y año
                    calidad_tag = serie.find('span', class_='quality')
                    calidad = calidad_tag.text.strip() if calidad_tag else None
                
                    año_tag = serie.find('span', class_='year')
                    año = año_tag.text.strip() if año_tag else None
                
                    # Extraer descripción
                    desc_tag = serie.find('p', class_='text-sm opacity-70')
                    descripcion = desc_tag.text.strip() if desc_tag else None
                
                    # Extraer géneros
                    generos_container = serie.find('p', class_=['absolute', 'bottom-0'])
                    generos = []
                    if generos_container:
                        generos_links = generos_container.find_all('a')
                        generos = [g.text.strip() for g in generos_links]
                
                    serie_data = {
                        'tipo': tipo,
                        'titulo': titulo,
                        'enlace': enlace,
                        'imagen': imagen,
                        'temporadas': temporadas,
                        'episodios': episodios,
                        'calidad': calidad,
                        'año': año,
                        'descripcion': descripcion,
                        'generos': generos if generos else []
                    }
                
                    datos_series.append(serie_data)
                
                except Exception as e:
                    print(f"Error al extraer serie: {e}")
                    continue
        
            print(f"✓ {len(datos_series)} series extraídas de la página {pagina}")
            return datos_series
        
        except Exception as e:
            print(f"Error al hacer scraping: {e}")
            return []
    
    def extraer_multiples_paginas(self, num_paginas=3, tipo='pelicula'):
        """
        Extrae películas o series de múltiples páginas
        tipo: 'pelicula' o 'serie'
        """
        todos_items = []        
        for pagina in range(1, num_paginas + 1):
            print(f"\n{'='*60}")
            print(f"Página {pagina} de {num_paginas} - {tipo_texto}")
            print('='*60)

            if tipo == 'serie':
                items = self.extraer_series(pagina=pagina, tipo=tipo)
            else:
                items = self.extraer_peliculas(pagina=pagina, tipo=tipo)

            todos_items.extend(items)
            
            # Pausa entre páginas para ser respetuoso
            if pagina < num_paginas:
                time.sleep(2)
        
        return todos_items
    
    def guardar_json(self, datos, archivo='peliculas_cinecalidad.json'):
        """
        Guarda los datos en un archivo JSON
        """
        if not datos:
            print("No hay datos para guardar")
            return
        
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Datos guardados en '{archivo}'")
    
    def mostrar_peliculas(self, datos, limite=5):
        """
        Muestra las películas o series extraídas en la consola
        """
        print(f"\n{'='*80}")
        print(f"ITEMS ENCONTRADOS (Mostrando {min(limite, len(datos))} de {len(datos)})")
        print('='*80)
        
        for i, item in enumerate(datos[:limite], 1):
            tipo_emoji = "📺" if item.get('tipo') == 'serie' else "🎬"
            print(f"\n{i}. {tipo_emoji} {item['titulo']}")
            
            if item.get('tipo') == 'serie':
                print(f"   {item.get('temporadas', 'N/A')} | {item.get('episodios', 'N/A')}")
            else:
                print(f"   Año: {item['año']} | Calidad: {item['calidad']}")
            
            print(f"   Géneros: {', '.join(item['generos']) if item['generos'] else 'N/A'}")
            print(f"   URL: {item['enlace']}")
            
            if item['descripcion']:
                desc = item['descripcion'][:100] + "..." if len(item['descripcion']) > 100 else item['descripcion']
                print(f"   Descripción: {desc}")

    def obtener_numero_paginas(self, tipo):
        """
        Obtiene el número total de páginas disponibles
        
        Args:
            tipo (str): 'peliculas' o 'series'
        
        Returns:
            int: Número total de páginas, o 1 si hay error
        """
        if tipo == 'pelicula':
            url = self.base_url
        elif tipo == 'serie':
            url = f"{self.base_url}/serie/"
        else:
            print("Tipo no válido. Usa 'peliculas' o 'series'")
            return 1
        
        try:
            print(f"Obteniendo número de páginas de {tipo}...")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar el contenedor de paginación
            nav_pagination = soup.find('nav', class_='navigation pagination')
            
            if not nav_pagination:
                print("No se encontró paginación")
                return 1
            
            # Buscar todos los enlaces de página
            page_links = nav_pagination.find_all('a', class_='page-numbers')
            
            # Filtrar solo los enlaces numéricos (excluir "Siguiente")
            numeros_pagina = []
            for link in page_links:
                texto = link.text.strip()
                if texto.isdigit():
                    numeros_pagina.append(int(texto))
            
            # El número más alto es el total de páginas
            if numeros_pagina:
                total_paginas = max(numeros_pagina)
                print(f"✓ Total de páginas encontradas: {total_paginas}")
                return total_paginas
            else:
                print("No se encontraron números de página")
                return 1
                
        except Exception as e:
            print(f"Error al obtener número de páginas: {e}")
            return 1

# Ejemplo de uso
if __name__ == "__main__":
    scraper = CinecalidadScraper()

    print("🎬 SCRAPER DE CINECALIDAD")
    print("=" * 80)

    tipo = input("¿Qué deseas extraer? Películas o Series (p/s): ").strip().lower()
    if tipo not in ['p', 's']:
        print("⚠️ Opción inválida. Se usará 'película' por defecto.")
        tipo = 'p'

    tipo_texto = "serie" if tipo == 's' else "pelicula"
    print(f"\n📂 Tipo de contenido seleccionado: {tipo_texto.upper()}")

    total_paginas = scraper.obtener_numero_paginas(tipo=tipo_texto)

    print("\n" + "=" * 80)
    multiple = input("¿Deseas extraer de múltiples páginas? (s/n): ").strip().lower()

    if multiple == 's':
        try:
            num_paginas = int(input(f"¿Cuántas páginas quieres scrapear? (1-{total_paginas}): "))
            if not (1 <= num_paginas <= total_paginas):
                print(f"⚠️ El número de páginas debe estar entre 1 y {total_paginas}.")
                exit()

            print(f"\n📚 Extrayendo {tipo_texto}s de {num_paginas} páginas...")
            resultados = scraper.extraer_multiples_paginas(num_paginas=num_paginas, tipo=tipo_texto)

            scraper.mostrar_peliculas(resultados, limite=15)
            archivo = f"{tipo_texto}s_{num_paginas}_paginas.json"
            scraper.guardar_json(resultados, archivo)
            print(f"\n📊 Total de {tipo_texto}s extraídas: {len(resultados)}")

        except ValueError:
            print("⚠️ Debes ingresar un número válido para la cantidad de páginas.")

    # --- MODO UNA SOLA PÁGINA ---
    else:
        print(f"\n📄 Extrayendo {tipo_texto}s de la primera página...")
        resultados = scraper.extraer_multiples_paginas(num_paginas=1, tipo=tipo_texto)
        scraper.mostrar_peliculas(resultados, limite=10)
        archivo = f"{tipo_texto}s_pagina_1.json"
        scraper.guardar_json(resultados, archivo)

    print("\n✅ Scraping completado exitosamente!")