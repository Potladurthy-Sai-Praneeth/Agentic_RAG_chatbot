from typing import Dict, Any
import yaml
import pathlib
import os
import httpx
import asyncio
from dotenv import load_dotenv


def load_config(config_path: str = None) -> Dict:
        """Load configuration from YAML file"""
        # Get the directory where this script is located
        if config_path is None:
            script_dir = pathlib.Path(__file__).parent
            config_path = script_dir / "config.yaml"
        else:
            # Convert string path to Path object
            config_path = pathlib.Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")
        
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        
        return config