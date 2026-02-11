from pathlib import Path

from config.production import settings
from src.cache_manager import CacheManager


def test_cache_key_uses_salt(tmp_path: Path):
    original_salt = settings.cache_key_salt
    try:
        settings.cache_key_salt = "salt_a"
        cm_a = CacheManager(cache_dir=str(tmp_path / "cache_a"))
        key_a = cm_a.get_cache_key("Client cherche un sac noir", "pipeline_v3")

        settings.cache_key_salt = "salt_b"
        cm_b = CacheManager(cache_dir=str(tmp_path / "cache_b"))
        key_b = cm_b.get_cache_key("Client cherche un sac noir", "pipeline_v3")

        assert key_a != key_b
    finally:
        settings.cache_key_salt = original_salt


def test_cache_key_stable_for_same_input(tmp_path: Path):
    original_salt = settings.cache_key_salt
    try:
        settings.cache_key_salt = "stable_salt"
        cm = CacheManager(cache_dir=str(tmp_path / "cache"))
        k1 = cm.get_cache_key("Same Text", "pipeline_v3")
        k2 = cm.get_cache_key("Same Text", "pipeline_v3")
        assert k1 == k2
    finally:
        settings.cache_key_salt = original_salt
