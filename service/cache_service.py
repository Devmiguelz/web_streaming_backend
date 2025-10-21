"""
cache_manager.py
Sistema de caché para almacenar películas scrapeadas
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

class CacheService:
    """Gestor de caché para películas"""
    
    def __init__(self, cache_dir="../cache", expiration_hours=48):
        """
        Inicializa el gestor de caché
        
        Args:
            cache_dir (str): Directorio donde se almacenan los archivos de caché
            expiration_hours (int): Horas de validez de la caché (default: 24)
        """
        self.cache_dir = Path(cache_dir)
        self.expiration_hours = expiration_hours
        
        # Crear directorio si no existe
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, slug: str) -> Path:
        """Genera la ruta del archivo de caché para un slug"""
        safe_slug = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in slug)
        return self.cache_dir / f"{safe_slug}.json"
    
    def _is_cache_valid(self, cache_data: Dict) -> bool:
        """Verifica si la caché aún es válida según el tiempo de expiración"""
        try:
            cached_time = datetime.fromisoformat(cache_data.get('cached_at', ''))
            expiration_time = cached_time + timedelta(hours=self.expiration_hours)
            return datetime.now() < expiration_time
        except (ValueError, TypeError):
            return False
    
    def get(self, slug: str) -> Optional[Dict]:
        """
        Obtiene una película de la caché si existe y es válida
        
        Args:
            slug (str): Slug de la película
            
        Returns:
            dict: Datos de la película o None si no existe/expiró
        """
        cache_path = self._get_cache_path(slug)
        
        # Verificar si el archivo existe
        if not cache_path.exists():
            return None
        
        try:
            # Leer archivo de caché
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verificar si la caché es válida
            if not self._is_cache_valid(cache_data):
                # Caché expirada, eliminar archivo
                cache_path.unlink()
                return None
            
            # Retornar los datos (sin el campo cached_at)
            movie_data = cache_data.get('data')
            return movie_data
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error leyendo caché para {slug}: {e}")
            return None
    
    def set(self, slug: str, movie_data: Dict) -> bool:
        """
        Guarda una película en la caché
        
        Args:
            slug (str): Slug de la película
            movie_data (dict): Datos de la película a cachear
            
        Returns:
            bool: True si se guardó correctamente, False si hubo error
        """
        cache_path = self._get_cache_path(slug)
        
        try:
            # Preparar datos para caché
            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'slug': slug,
                'data': movie_data
            }
            
            # Guardar en archivo JSON
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except IOError as e:
            print(f"Error guardando caché para {slug}: {e}")
            return False
    
    def delete(self, slug: str) -> bool:
        """
        Elimina una película de la caché
        
        Args:
            slug (str): Slug de la película
            
        Returns:
            bool: True si se eliminó, False si no existía o hubo error
        """
        cache_path = self._get_cache_path(slug)
        
        try:
            if cache_path.exists():
                cache_path.unlink()
                return True
            return False
        except IOError as e:
            print(f"Error eliminando caché para {slug}: {e}")
            return False
    
    def clear_expired(self) -> int:
        """
        Limpia todos los archivos de caché expirados
        
        Returns:
            int: Número de archivos eliminados
        """
        deleted_count = 0
        
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    if not self._is_cache_valid(cache_data):
                        cache_file.unlink()
                        deleted_count += 1
                        
                except (json.JSONDecodeError, IOError):
                    # Archivo corrupto, eliminar
                    cache_file.unlink()
                    deleted_count += 1
                    
        except Exception as e:
            print(f"Error limpiando caché expirada: {e}")
        
        return deleted_count
    
    def clear_all(self) -> int:
        """
        Elimina toda la caché
        
        Returns:
            int: Número de archivos eliminados
        """
        deleted_count = 0
        
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                deleted_count += 1
        except Exception as e:
            print(f"Error limpiando toda la caché: {e}")
        
        return deleted_count
    
    def get_cache_stats(self) -> Dict:
        """
        Obtiene estadísticas de la caché
        
        Returns:
            dict: Estadísticas (total, válidas, expiradas)
        """
        total = 0
        valid = 0
        expired = 0
        
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                total += 1
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    if self._is_cache_valid(cache_data):
                        valid += 1
                    else:
                        expired += 1
                        
                except:
                    expired += 1
                    
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
        
        return {
            'total': total,
            'valid': valid,
            'expired': expired,
            'expiration_hours': self.expiration_hours
        }


# Instancia singleton del gestor de caché
cache_service = CacheService(cache_dir="../cache", expiration_hours=24)