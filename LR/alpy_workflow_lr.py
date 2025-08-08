#

# 	Diamètre (cm)	Tps de pose (s)	Gain (e-/ADU)	p (A/px)	S signal (10e-6)	Q = (D^2*p)/(G)	Score		Score de perf = (S*G)/(T*D^2*p) (e/A/s/cm^2)		Capteur IMX	Fente	Remarques

import argparse
import os.path
from enum import Enum
import subprocess
import yaml
from pathlib import Path
import sys
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )

class SetupType(str, Enum)
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

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run spectroscopic reduction workflows with specinti."
    )

    parser.add_argument(
        "specinti_install_path",
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

    specinti_install_path = args.specinti_install_path.resolve()

    if not specinti_install_path.is_dir():
        logging.error(f"Invalid path: {specinti_install_path}")
        sys.exit(1)

    specinti_binary = os.path.join(specinti_install_path, "specinti")
    if not specinti_binary.is_file():
        logging.error(f"specinti binary not found at: {specinti_binary}")
        sys.exit(1)

    config_path = os.path.join(specinti_install_path, "runtime_config.yaml")
    write_config_file(config_path, args.setup_type, args.mode)
    run_specinti(specinti_install_path, specinti_binary, config_path, dry_run=args.dry_run)

if __name__ == "__main__":
    main()

# Sample usage
# python spectro_reducer.py /opt/specinti \
#   --setup_type starex_2400 \
#   --mode science \
#   --dry_run