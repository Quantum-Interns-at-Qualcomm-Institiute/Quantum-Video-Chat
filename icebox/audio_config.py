"""Audio configuration management with YAML support."""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Audio config validation bounds
_MAX_DELAY_MS = 10000
_MIN_SAMPLE_RATE = 8000
_MAX_SAMPLE_RATE = 96000


class Config:
    """Manages audio delay and sample rate configuration."""

    def __init__(self, config_file = None):
        """Initialize config with optional YAML file."""
        self.delay = 0
        self.samplerate = 44100
        if config_file:
          self.set_config_from_yaml(self.read_and_validate_yaml(config_file))

    def get_delay(self):
        """Return the current delay in milliseconds."""
        return self.delay

    def set_delay(self, delay):
        """Set the audio delay in milliseconds."""
        self.delay = delay
        logger.info("Set delay to %s ms", delay)

    def get_samplerate(self):
        """Return the current sample rate in Hz."""
        return self.samplerate

    def set_samplerate(self, samplerate):
        """Set the audio sample rate in Hz."""
        self.samplerate = samplerate
        logger.info("Set sample rate to %s Hz", samplerate)

    def read_and_validate_yaml(self, yaml_file):
        """Read and validate the YAML configuration file."""
        if not Path(yaml_file).exists():
            logger.error("The file %s does not exist.", yaml_file)
            msg = f"The file {yaml_file} does not exist."
            raise FileNotFoundError(msg)

        with Path(yaml_file).open() as file:
            try:
                config = yaml.full_load(file)
            except yaml.YAMLError as exc:
                logger.exception("Error parsing YAML file")
                msg = f"Error parsing YAML file: {exc}"
                raise ValueError(msg) from exc

            if "audio" not in config or "delay" not in config["audio"] or "samplerate" not in config["audio"]:
                logger.error("YAML file does not have the correct structure.")
                msg = "YAML file does not have the correct structure."
                raise ValueError(msg)

        return config

    def set_config_from_yaml(self, yaml_file):
        """Apply audio settings from a validated YAML config."""
        logger.info("Reading and validating %s.", yaml_file)
        config = self.read_and_validate_yaml(yaml_file)

        assert 0 <= config["audio"]["delay"] <= _MAX_DELAY_MS
        self.set_delay(config["audio"]["delay"])

        assert _MIN_SAMPLE_RATE <= config["audio"]["samplerate"] <= _MAX_SAMPLE_RATE
        self.set_samplerate(config["audio"]["samplerate"])

        logger.info("Configuration successfully applied.")
