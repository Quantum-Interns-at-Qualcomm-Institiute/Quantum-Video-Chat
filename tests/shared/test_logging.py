"""Tests for shared/logging.py — get_logger()."""
import logging
from logging.handlers import RotatingFileHandler

from shared.logging import get_logger


class TestGetLogger:
    def test_returns_logger_with_correct_name(self, tmp_path):
        logger = get_logger('test_name', log_dir=str(tmp_path))
        assert logger.name == 'test_name'

    def test_logger_level_is_debug(self, tmp_path):
        logger = get_logger('test_debug', log_dir=str(tmp_path))
        assert logger.level == logging.DEBUG

    def test_has_stream_handler(self, tmp_path):
        logger = get_logger('test_stream', log_dir=str(tmp_path))
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types

    def test_has_file_handler(self, tmp_path):
        logger = get_logger('test_file', log_dir=str(tmp_path))
        handler_types = [type(h) for h in logger.handlers]
        assert RotatingFileHandler in handler_types

    def test_idempotent_handlers(self, tmp_path):
        name = 'test_idempotent'
        logger1 = get_logger(name, log_dir=str(tmp_path))
        count1 = len(logger1.handlers)
        logger2 = get_logger(name, log_dir=str(tmp_path))
        count2 = len(logger2.handlers)
        assert count1 == count2
        assert logger1 is logger2

    def test_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / 'subdir' / 'logs'
        _logger = get_logger('test_mkdir', log_dir=str(log_dir))
        assert log_dir.exists()

    def test_stream_handler_level_is_info(self, tmp_path):
        logger = get_logger('test_stream_level', log_dir=str(tmp_path))
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                assert handler.level == logging.INFO

    def test_file_handler_level_is_debug(self, tmp_path):
        logger = get_logger('test_file_level', log_dir=str(tmp_path))
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                assert handler.level == logging.DEBUG
