# (c) Copyright IBM Corp. 2025

from typing import Union
from instana.log import logger
import yaml


class ConfigReader:
    def __init__(self, file_path: Union[str]) -> None:
        self.file_path = file_path
        self.data = None
        self.load_file()

    def load_file(self) -> None:
        """Loads and parses the YAML file"""
        try:
            with open(self.file_path, "r") as file:
                self.data = yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Configuration file has not found: {self.file_path}")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
