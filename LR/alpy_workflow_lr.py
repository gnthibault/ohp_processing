#

# 	Diamètre (cm)	Tps de pose (s)	Gain (e-/ADU)	p (A/px)	S signal (10e-6)	Q = (D^2*p)/(G)	Score		Score de perf = (S*G)/(T*D^2*p) (e/A/s/cm^2)		Capteur IMX	Fente	Remarques

# Generic imports
import argparse
from contextlib import contextmanager
from enum import Enum
import logging
import os.path
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import yaml

# Astropy
from astropy.io import fits


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )

class SetupType(str, Enum):
    starex_2400 = "starex_2400"
    alpy_600    = "alpy_600"
    
class Mode(str, Enum):
    """
    * raw         : will produce just a calibrated spectra with raw values, so that one can perform diagnostic on
    actual ADUs
    * calibration : expects a set of calibration star images, as well as a reference star spectrum, and will produce
    an instrument response file
    * science     : will produce a spectrum

    """
    RAW         = "raw"
    CALIBRATION = "calibration"
    SCIENCE     = "science"

def read_fits_header(file_path):
    res = {}
    with fits.open(file_path) as hdul:
        header = hdul[0].header  # usually the primary header is at index 0
        logging.debug(f"Read file {file_path} - full Header:\n" + "-"*40 + "header")
        res = {k:v for k,v in header.items()}
    return res

def list_matching_files(directory, pattern):
    regex = re.compile(pattern)
    matched_files = []
    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path) and regex.search(entry):
            matched_files.append(entry)
    return matched_files

def list_all_acquisition_files(src_light_directory):
    """
        # \d{4}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])T([01]\d|2[0-3])[0-5]\d[0-5]\d\.fits
        # Explanation:
        # \d{4}: Matches exactly four digits (for the year YYYY).
        # (0[1-9]|1[0-2]): Matches the month (MM).
        #   0[1-9]: Matches months from 01 to 09.
        #   1[0-2]: Matches months from 10 to 12.
        # (0[1-9]|[12]\d|3[01]): Matches the day (DD).
        #   0[1-9]: Matches days from 01 to 09.
        #   [12]\d: Matches days from 10 to 29.
        #   3[01]: Matches days 30 and 31.
        # T: Matches the literal character "T" separating the date and time.
        # ([01]\d|2[0-3]): Matches the hour (HH).
        #   [01]\d: Matches hours from 00 to 19.
        #   2[0-3]: Matches hours from 20 to 23.
        # [0-5]\d: Matches the minute (MM) from 00 to 59.
        # [0-5]\d: Matches the second (SS) from 00 to 59.
        # \.fits: Matches the literal string ".fits" at the end of the filename. The \ is used to escape the . character, as . has a special meaning in regular expressions (it matches any character).
    """

    all_light_files = list_matching_files(
        directory=src_light_directory,
        pattern="\d{4}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])T([01]\d|2[0-3])[0-5]\d[0-5]\d\.fits"
    )
    return all_light_files

def copy_src_file_to_dest(all_src_files, destination_directory, filename_prefix):
    light_number = len(all_src_files)
    all_dst_files = []
    for index, src_file in enumerate(all_src_files):
        new_file_name = f"{filename_prefix}{index}.fits"
        if not os.path.isfile(src_file):
            raise FileNotFoundError(f"Source file does not exist: {src_file}")
        if not os.path.isdir(destination_directory):
            raise NotADirectoryError(f"Destination is not a directory: {destination_directory}")
        destination_path = os.path.join(destination_directory, new_file_name)
        shutil.copy2(src_file, destination_path)  # copy2 preserves metadata
        all_dst_files.append(destination_path)
    return filename_prefix, light_number, all_dst_files

class TemporarySpecintiProcessingDir:
    def __init__(self):
        self.directory = tempfile.mkdtemp() #tempfile.TemporaryDirectory()
        self.processing_cfg_dict = {}

    def cleanup(self):
        logging.debug(f"Cleaning up TemporaryThing directory {self.directory}")
        shutil.rmtree(self.directory)

@contextmanager
def build_temp_processing_dir(src_light_directory, remove=True):
    processing_dir = TemporarySpecintiProcessingDir()
    try:
        # Manage lights
        all_src_light_files = list_all_acquisition_files(src_light_directory=src_light_directory)
        light_prefix, light_number, all_dst_light_files = copy_src_file_to_dest(
            all_src_files=all_src_light_files,
            destination_directory=processing_dir.directory,
            filename_prefix="light_")
        processing_dir.processing_cfg_dict["LIGHT_PREFIX"] = light_prefix
        processing_dir.processing_cfg_dict["LIGHT_NB"] = light_number
        # Open first file, and check gain/offset/
        headers = read_fits_header(file_path=all_dst_light_files[0])

        processing_dir.processing_cfg_dict["SIMBAD_NAME"] = 0
        
        # Manage dark
        processing_dir.processing_cfg_dict["DARK_PREFIX"] = "None"
        processing_dir.processing_cfg_dict["DARK_NB"] = 0

        # Manage offset
        processing_dir.processing_cfg_dict["OFFSET_PREFIX"] = "None"
        processing_dir.processing_cfg_dict["OFFSET_NB"] = 0

        # Manage tungsten flat
        processing_dir.processing_cfg_dict["SPEC_FLAT_PREFIX"] = "None"
        processing_dir.processing_cfg_dict["SPEC_FLAT_NB"] = 0

        # Manage spectral calibration files
        processing_dir.processing_cfg_dict["SPEC_CALIB_PREFIX"] = "None"
        processing_dir.processing_cfg_dict["SPEC_CALIB_NB"] = 0

        # Manage reference response file
        processing_dir.processing_cfg_dict["INSTRUMENT_RESPONSE"] = "None"

        yield processing_dir.processing_cfg_dict
    finally:
        if remove:
            processing_dir.cleanup()

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run spectroscopic reduction workflows with specinti."
    )

    parser.add_argument(
        "--specinti_install_path",
        type=Path,
        help="Path to the directory where specinti is installed."
    )

    parser.add_argument(
        "--setup_type",
        choices=list(SetupType),
        required=True,
        help="The instrument setup type."
    )

    parser.add_argument(
        "--mode",
        type=Mode,
        choices=list(Mode),
        required=True,
        help="Reduction mode: raw, calibration, or science."
    )

    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="If set, do not execute specinti, just generate the config file."
    )

    return parser.parse_args()

def write_config_file(config_path, setup_type, mode):
    config = {
        "setup_type": setup_type,
        "mode": mode
    }

    with open(config_path, "w") as f:
        yaml.dump(config, f)
    logging.info(f"Config written to {config_path}")

def run_specinti(specinti_install_path, specinti_path, config_path, dry_run=False):
    if dry_run:
        logging.info(f"[DRY-RUN] Would run: {specinti_path} {config_path}")
        return

    try:
        logging.info(f"Executing: {specinti_path} {config_path}")
        subprocess.run(
            [str(specinti_path), str(config_path)],
            cwd=specinti_install_path,
            check=True
        )
        logging.info("specinti executed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"specinti failed: {e}")
        sys.exit(e.returncode)

def main():
    setup_logging()
    args = parse_args()

    # Will yield an object of type TemporarySpecintiProcessingDir
    with build_temp_processing_dir(src_light_directory, remove=True) as processing_dir:
        build_specinti_processing_file()
        build_specinti_config_file()

        specinti_install_path = args.specinti_install_path.resolve()

        if not specinti_install_path.is_dir():
            logging.error(f"Invalid path: {specinti_install_path}")
            sys.exit(1)

        specinti_binary = specinti_install_path.joinpath("specinti")
        if not specinti_binary.is_file():
            logging.error(f"specinti binary not found at: {specinti_binary}")
            sys.exit(1)

    # Write processing file
    src_processing_path = Path("./processing_config_alpy600.yaml")
    dst_processing_path = specinti_install_path.joinpath("runtime_config.yaml")
    write_processing_file(src_processing_path, dst_processing_path)

    # Write config file
    src_config_path = Path("./conf_alpy600.yaml")
    dst_config_path = specinti_install_path.joinpath("runtime_config.yaml")
    write_config_file(config_path, args.setup_type, args.mode)

    # Run actual specinti
    run_specinti(specinti_install_path, specinti_binary, config_path, dry_run=args.dry_run)

if __name__ == "__main__":
    main()

# Sample usage
# python spectro_reducer.py /opt/specinti \
#   --setup_type starex_2400 \
#   --mode science \
#   --dry_run
