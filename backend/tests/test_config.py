"""Tests for the typed config module."""
import os
import pytest


class TestAriaSettings:
    """Test AriaSettings validation and defaults."""

    def test_default_values(self):
        from config.settings import AriaSettings
        cfg = AriaSettings()
        assert cfg.ollama_url == "http://localhost:11434"
        assert cfg.backend_port == 8000
        assert cfg.max_message_chars == 8000
        assert cfg.max_image_bytes == 20 * 1024 * 1024
        assert cfg.student_age == 13

    def test_port_validation(self):
        from config.settings import AriaSettings
        with pytest.raises(Exception):
            AriaSettings(backend_port=80)  # too low

    def test_port_validation_upper(self):
        from config.settings import AriaSettings
        with pytest.raises(Exception):
            AriaSettings(backend_port=99999)  # too high

    def test_url_strips_trailing_slash(self):
        from config.settings import AriaSettings
        cfg = AriaSettings(ollama_url="http://localhost:11434/")
        assert cfg.ollama_url == "http://localhost:11434"

    def test_url_strips_api_suffix(self):
        from config.settings import AriaSettings
        cfg = AriaSettings(ollama_url="http://localhost:11434/api/generate")
        assert cfg.ollama_url == "http://localhost:11434"

    def test_rate_limit_string(self):
        from config.settings import AriaSettings
        cfg = AriaSettings(rate_limit_global="60/minute")
        assert cfg.rate_limit_global == "60/minute"

    def test_message_chars_min(self):
        from config.settings import AriaSettings
        with pytest.raises(Exception):
            AriaSettings(max_message_chars=0)

    def test_context_chars_validation(self):
        from config.settings import AriaSettings
        with pytest.raises(Exception):
            AriaSettings(default_context_chars=100)  # below minimum

    def test_get_settings_singleton(self):
        from config.settings import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2  # same instance


class TestConfigInit:
    """Test config package imports."""

    def test_import(self):
        from config import get_settings, AriaSettings
        assert callable(get_settings)
        assert AriaSettings is not None
