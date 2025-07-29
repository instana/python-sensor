# (c) Copyright IBM Corp. 2025

import yaml

from instana.log import logger


class ConfigReader:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.data = {}
        if file_path:
            self.load_file()
        else:
            logger.warning("ConfigReader: No configuration file specified")

    def load_file(self) -> None:
        """Loads and parses the YAML file"""
        try:
            with open(self.file_path, "r") as file:
                self.data = yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(
                f"ConfigReader: Configuration file has not found: {self.file_path}"
            )
        except yaml.YAMLError as e:
            logger.error(f"ConfigReader: Error parsing YAML file: {e}")
