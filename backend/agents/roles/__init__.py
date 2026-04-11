"""
SAP SIM — Agent Roles Package
Phase: 2.3
Purpose: Exports all role classes so the agent factory can import them by codename.
         Batch 1: 10 consultant agents (PM, Architect, BASIS, ABAP Dev, Fiori Dev,
                  FI, CO, MM, SD, PP).
Dependencies: base_agent.BaseAgent (via each role module)
"""

from agents.roles.pm_alex import PmAlex
from agents.roles.arch_sara import ArchSara
from agents.roles.basis_kurt import BasisKurt
from agents.roles.dev_priya import DevPriya
from agents.roles.dev_leon import DevLeon
from agents.roles.fi_chen import FiChen
from agents.roles.co_marta import CoMarta
from agents.roles.mm_ravi import MmRavi
from agents.roles.sd_isla import SdIsla
from agents.roles.pp_jonas import PpJonas

# Registry mapping codename → class.
# Used by agents/factory.py: create_agent(codename, ...) looks up this dict.
ROLE_REGISTRY: dict[str, type] = {
    "PM_ALEX":    PmAlex,
    "ARCH_SARA":  ArchSara,
    "BASIS_KURT": BasisKurt,
    "DEV_PRIYA":  DevPriya,
    "DEV_LEON":   DevLeon,
    "FI_CHEN":    FiChen,
    "CO_MARTA":   CoMarta,
    "MM_RAVI":    MmRavi,
    "SD_ISLA":    SdIsla,
    "PP_JONAS":   PpJonas,
}

__all__ = [
    "PmAlex",
    "ArchSara",
    "BasisKurt",
    "DevPriya",
    "DevLeon",
    "FiChen",
    "CoMarta",
    "MmRavi",
    "SdIsla",
    "PpJonas",
    "ROLE_REGISTRY",
]
