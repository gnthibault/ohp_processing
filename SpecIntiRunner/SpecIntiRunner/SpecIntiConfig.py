# Generic imports
from importlib import resources
import logging
import os.path
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import yaml


class TemporarySpecintiProcessingRessources:
    def __init__(self,
                 specinti_install_path):
        self.directory = tempfile.mkdtemp() #tempfile.TemporaryDirectory()
        self.processing_cfg_dict = {}
        self.config_file = None
        self.ini_file = None
        self.processing_file = None
        self.specinti_install_path = specinti_install_path

    def cleanup(self):
        logging.debug(f"Cleaning up TemporaryThing directory {self.directory}")
        shutil.rmtree(self.directory)

def load_yaml(path: Path):
    """Load a YAML file into memory."""
    with open(path, "r") as f:
        return yaml.safe_load(f)

def build_specinti_ini_file(processing_res: TemporarySpecintiProcessingRessources):
    dest_ini_file = Path(os.path.join(processing_res.specinti_install_path, "_configuration/specinti_ini.yaml"))
    with resources.path(
            "data", "specinti_ini.yaml"
    ) as specinti_ini_filepath:
        yaml_data = load_yaml(specinti_ini_filepath)
        # conf_alpy600, no base directory, no yaml extension
        updated_config_yaml = template_update(yaml_data,
                                            "SPECINTI_CONF_FILE" ,
                                            processing_res.config_file.stem)
        updated_config_yaml = template_update(updated_config_yaml,
                                            "FULL_PATH_TO_PROCESSING_FILE",
                                            str(processing_res.processing_file))
        save_yaml(updated_config_yaml, dest_ini_file)
        processing_res.ini_file = dest_ini_file

def build_specinti_processing_file(processing_res: TemporarySpecintiProcessingRessources):
    dest_processing_file = Path(os.path.join(processing_res.directory, "processing.yaml"))
    with resources.path(
            "data", "processing_config.yaml"
    ) as specinti_processing_filepath:
        yaml_data = load_yaml(specinti_processing_filepath)
        updated_config_yaml = template_update(yaml_data,
                                            "SIMBAD_NAME",
                                            processing_res.processing_cfg_dict["SIMBAD_NAME"])
        updated_config_yaml = template_update(updated_config_yaml,
                                            "LIGHT_PREFIX",
                                            processing_res.processing_cfg_dict["LIGHT_PREFIX"])# generic target file name, example: altair-
        updated_config_yaml = template_update(updated_config_yaml,
                                            "LIGHT_NB",
                                            processing_res.processing_cfg_dict["LIGHT_NB"])# number of target spectral images, example: 13
        updated_config_yaml = template_update(updated_config_yaml,
                                            "SPEC_CALIB_PREFIX",
                                            processing_res.processing_cfg_dict["SPEC_CALIB_PREFIX"])# generic spectral lamp files name, example: altair_neon-
        updated_config_yaml = template_update(updated_config_yaml,
                                            "SPEC_CALIB_NB",
                                            processing_res.processing_cfg_dict["SPEC_CALIB_NB"])# number of spectral lamp images, example: 1
        updated_config_yaml = template_update(updated_config_yaml,
                                            "SPEC_FLAT_PREFIX",
                                            processing_res.processing_cfg_dict["SPEC_FLAT_PREFIX"])# generic flat lamp files name, example: altair_tung-
        updated_config_yaml = template_update(updated_config_yaml,
                                            "SPEC_FLAT_NB",
                                            processing_res.processing_cfg_dict["SPEC_FLAT_NB"])# number of flat images, example: 18
        updated_config_yaml = template_update(updated_config_yaml,
                                            "DARK_PREFIX",
                                            processing_res.processing_cfg_dict["DARK_PREFIX"])# generic dark files name, example: n900-
        updated_config_yaml = template_update(updated_config_yaml,
                                            "DARK_NB",
                                            processing_res.processing_cfg_dict["DARK_NB"])# number of dark images, example: 18
        updated_config_yaml = template_update(updated_config_yaml,
                                            "OFFSET_PREFIX",
                                            processing_res.processing_cfg_dict["OFFSET_PREFIX"])# generic offset files name, example: o-
        updated_config_yaml = template_update(updated_config_yaml,
                                            "OFFSET_NB",
                                            processing_res.processing_cfg_dict["OFFSET_NB"])# number of offset files name, example: 25
        updated_config_yaml = template_update(updated_config_yaml,
                                            "INSTRUMENT_RESPONSE",
                                            processing_res.processing_cfg_dict["INSTRUMENT_RESPONSE"])
        save_yaml(updated_config_yaml, dest_processing_file)
        processing_res.processing_file = dest_processing_file

def build_specinti_config_file(processing_res: TemporarySpecintiProcessingRessources):
    dest_config_file = Path(os.path.join(processing_res.specinti_install_path, "_configuration/config.yaml"))

    with resources.path(
            "data", "conf_alpy600.yaml"
    ) as specinti_config_filepath:
        yaml_data = load_yaml(specinti_config_filepath)
        updated_config_yaml = template_update(yaml_data,
                                            "WORKING_PATH_WITH_ALL_DATA",
                                            processing_res.directory)
        updated_config_yaml = template_update(updated_config_yaml,
                                            "PROCESSING_FILE",
                                            processing_res.processing_file.stem)
        save_yaml(updated_config_yaml, dest_config_file)
        processing_res.config_file = dest_config_file


def template_update(data, search_value, replace_value):
    """Recursively search and replace values inside a YAML data structure."""
    if isinstance(data, dict):
        return {template_update(k, search_value, replace_value): template_update(v, search_value, replace_value) for k, v in data.items()}
    elif isinstance(data, list):
        return [template_update(item, search_value, replace_value) for item in data]
    elif data == search_value:
        return replace_value
    else:
        return data

def save_yaml(data, path: Path):
    """Write modified YAML back to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)  # mkdir -p
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)



