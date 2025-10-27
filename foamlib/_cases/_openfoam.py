"""OpenFOAM environment detection and command wrapping utilities."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

if sys.version_info >= (3, 9):
    from collections.abc import Sequence
else:
    from typing import Sequence

# Common OpenFOAM utilities that need to be wrapped
OPENFOAM_COMMANDS = {
    "blockMesh",
    "decomposePar",
    "reconstructPar",
    "foamRun",
    "simpleFoam",
    "icoFoam",
    "pimpleFoam",
    "interFoam",
    "setFields",
    "postProcess",
    "checkMesh",
    "surfaceFeatureExtract",
    "snappyHexMesh",
    "ansysToFoam",
    "fluent3DMeshToFoam",
    "transformPoints",
    "createPatch",
    "mapFields",
    "renumberMesh",
    "splitMeshRegions",
    "stitchMesh",
    "mergeOrSplitBaffles",
    "createBaffles",
    "topoSet",
    "refineMesh",
}

# Default OpenFOAM version to use if none can be detected
DEFAULT_OPENFOAM_VERSION = "2412"


def is_in_openfoam_environment() -> bool:
    """
    Check if we're currently running in an OpenFOAM environment.

    This checks for the presence of standard OpenFOAM environment variables
    that are set when the OpenFOAM environment is sourced.

    Returns:
        True if in an OpenFOAM environment, False otherwise.
    """
    # Check for key OpenFOAM environment variables
    openfoam_vars = [
        "WM_PROJECT_DIR",
        "FOAM_APP",
        "FOAM_SRC",
        "FOAM_LIBBIN",
    ]

    # If any of these critical variables are set, we're likely in OpenFOAM environment
    for var in openfoam_vars:
        if os.environ.get(var):
            return True

    # Also check if OpenFOAM commands are directly available in PATH
    # This handles cases where OpenFOAM is installed system-wide
    return bool(shutil.which("blockMesh") and shutil.which("foamRun"))


def get_openfoam_version() -> str | None:
    """
    Determine the OpenFOAM version to use.

    This checks various sources in order of priority:
    1. FOAMLIB_OPENFOAM_VERSION environment variable
    2. OPENFOAM_VERSION environment variable
    3. WM_PROJECT_VERSION if in an OpenFOAM environment
    4. Default version based on common installations

    Returns:
        OpenFOAM version string or None if unable to determine.
    """
    # Check explicit version override
    if version := os.environ.get("FOAMLIB_OPENFOAM_VERSION"):
        return version

    if version := os.environ.get("OPENFOAM_VERSION"):
        return version

    # If we're in an OpenFOAM environment, try to get the version
    if is_in_openfoam_environment():
        if version := os.environ.get("WM_PROJECT_VERSION"):
            return version

        # Try to extract from FOAM_INST_DIR or WM_PROJECT_DIR
        if foam_dir := os.environ.get("WM_PROJECT_DIR"):
            # Try to extract version from path like /opt/openfoam10/...
            path_parts = Path(foam_dir).parts
            for part in path_parts:
                if part.startswith("openfoam") and len(part) > 8:
                    version = part[8:]  # Remove "openfoam" prefix
                    if version.isdigit() or "." in version:
                        return version

    # Try to detect available openfoam commands in system
    common_versions = ["2412", "2406", "11", "10", "9", "8"]
    for version in common_versions:
        if shutil.which(f"openfoam{version}"):
            return version

    return None


def get_openfoam_command_prefix() -> list[str]:
    """
    Get the command prefix needed to run OpenFOAM commands.

    Returns:
        List of command parts to prefix OpenFOAM commands with.
        Empty list if no prefix is needed (already in environment).
    """
    # If we're already in OpenFOAM environment, no prefix needed
    if is_in_openfoam_environment():
        return []

    # Get the version and construct the appropriate command
    version = get_openfoam_version()
    if not version:
        # If we can't determine version, try some common defaults
        for default_version in ["2412", "2406", "11", "10"]:
            if shutil.which(f"openfoam{default_version}"):
                version = default_version
                break

        if not version:
            # As a last resort, see if docker is available
            if shutil.which("docker"):
                # Use a reasonable default version with docker
                return ["docker", "run", "--rm", "-v", "${PWD}:/workspace",
                        "-w", "/workspace", f"openfoam/openfoam{DEFAULT_OPENFOAM_VERSION}-paraview510"]
            # No OpenFOAM available, return empty (will likely fail)
            return []

    # Use the openfoamXXXX command wrapper
    openfoam_cmd = f"openfoam{version}"
    if shutil.which(openfoam_cmd):
        return [openfoam_cmd]

    # If the direct command isn't available, try other approaches
    if shutil.which("docker"):
        return ["docker", "run", "--rm", "-v", "${PWD}:/workspace",
                "-w", "/workspace", f"openfoam/openfoam{version}-paraview510"]

    return []


def should_wrap_command(cmd: str | os.PathLike[str]) -> bool:
    """
    Determine if a command should be wrapped with OpenFOAM prefix.

    Args:
        cmd: The command to check (first element of command sequence).

    Returns:
        True if the command should be wrapped, False otherwise.
    """
    cmd_name = Path(cmd).name if isinstance(cmd, os.PathLike) else str(cmd)
    return cmd_name in OPENFOAM_COMMANDS


def wrap_openfoam_command(
    cmd: Sequence[str | os.PathLike[str]] | str,
) -> Sequence[str | os.PathLike[str]] | str:
    """
    Wrap an OpenFOAM command with the appropriate prefix if needed.

    Args:
        cmd: The command to potentially wrap.

    Returns:
        The wrapped command or original command if no wrapping needed.
    """
    # Handle string commands
    if isinstance(cmd, str):
        cmd_parts = cmd.split()
        if not cmd_parts or not should_wrap_command(cmd_parts[0]):
            return cmd

        prefix = get_openfoam_command_prefix()
        if not prefix:
            return cmd

        # For string commands with openfoam prefix, we need to handle carefully
        # since openfoamXXXX command expects the OF command as argument
        if len(prefix) == 1 and prefix[0].startswith("openfoam"):
            return f"{prefix[0]} {cmd}"
        # For docker or other complex prefixes, join everything
        return " ".join(str(p) for p in prefix) + " " + cmd

    # Handle sequence commands
    if not cmd or not should_wrap_command(cmd[0]):
        return cmd

    prefix = get_openfoam_command_prefix()
    if not prefix:
        return cmd

    # For sequence commands, prepend the prefix
    return [*prefix, *cmd]
