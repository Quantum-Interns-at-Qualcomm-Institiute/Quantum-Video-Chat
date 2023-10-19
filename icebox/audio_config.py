import yaml
import os
import logging

logging.basicConfig(level=logging.INFO)

# config.py
class Config:
    def __init__(self, config_file = None):
        self.delay = 0
        self.samplerate = 44100
        if config_file:
          self.set_config_from_yaml(self.read_and_validate_yaml(config_file))

    def get_delay(self):
        return self.delay

    def set_delay(self, delay):
        self.delay = delay
        logging.info(f'Set delay to {delay} ms')
        
    def get_samplerate(self):
        return self.samplerate

    def set_samplerate(self, samplerate):
        self.samplerate = samplerate
        logging.info(f'Set sample rate to {samplerate} Hz')

    def read_and_validate_yaml(self, yaml_file):
        if not os.path.exists(yaml_file):
            logging.error(f"The file {yaml_file} does not exist.")
            raise FileNotFoundError(f"The file {yaml_file} does not exist.")

        with open(yaml_file) as file:
            try:
                config = yaml.full_load(file)
            except yaml.YAMLError as exc:
                logging.error(f"Error parsing YAML file: {exc}")
                raise ValueError(f"Error parsing YAML file: {exc}")

            if 'audio' not in config or 'delay' not in config['audio'] or 'samplerate' not in config['audio']:
                logging.error("YAML file does not have the correct structure.")
                raise ValueError("YAML file does not have the correct structure.")
              
        return config
      
    def set_config_from_yaml(self, yaml_file):
        logging.info(f"Reading and validating {yaml_file}.")
        config = self.read_and_validate_yaml(yaml_file)
        
        assert 0 <= config['audio']['delay'] <= 10000 
        self.set_delay(config['audio']['delay'])
        
        assert 8000 <= config['audio']['samplerate'] <= 96000
        self.set_samplerate(config['audio']['samplerate'])
        
        logging.info("Configuration successfully applied.")


