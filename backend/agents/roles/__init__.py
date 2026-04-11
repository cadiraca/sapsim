"""
SAP SIM — Agent Roles Package
Phase: 2.3
Purpose: Exports all role classes so the agent factory can import them by codename.
         Batch 1 (10): Consultant core — PM, Architect, BASIS, ABAP Dev, Fiori Dev,
                        FI, CO, MM, SD, PP.
         Batch 2 (10): Consultant extended + Customer strategic — WM, Integration,
                        Security, BI, Change, Data Migration; Exec Sponsor, IT Mgr,
                        Customer PM, FI Key User.
         Batch 3 (10): Customer operational KUs + cross-functional — CO KU, MM KU,
                        SD KU, WM KU, PP KU, HR KU, Customer BA, Change Champion,
                        PMO Lead, QA Lead.
Dependencies: base_agent.BaseAgent (via each role module)
"""

# ── Batch 1: Consultant core ─────────────────────────────────────────────────
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

# ── Batch 2: Consultant extended + Customer strategic ────────────────────────
from agents.roles.wm_fatima import WmFatima
from agents.roles.int_marco import IntMarco
from agents.roles.sec_diana import SecDiana
from agents.roles.bi_sam import BiSam
from agents.roles.chg_nadia import ChgNadia
from agents.roles.dm_felix import DmFelix
from agents.roles.exec_victor import ExecVictor
from agents.roles.it_mgr_helen import ItMgrHelen
from agents.roles.cust_pm_omar import CustPmOmar
from agents.roles.fi_ku_rose import FiKuRose

# ── Batch 3: Customer KUs (operational/basic) + cross-functional ─────────────
from agents.roles.co_ku_bjorn import CoKuBjorn
from agents.roles.mm_ku_grace import MmKuGrace
from agents.roles.sd_ku_tony import SdKuTony
from agents.roles.wm_ku_elena import WmKuElena
from agents.roles.pp_ku_ibrahim import PpKuIbrahim
from agents.roles.hr_ku_sophie import HrKuSophie
from agents.roles.ba_cust_james import BaCustJames
from agents.roles.champ_leila import ChampLeila
from agents.roles.pmo_niko import PmoNiko
from agents.roles.qa_claire import QaClaire

# Registry mapping codename → class.
# Used by agents/factory.py: create_agent(codename, ...) looks up this dict.
ROLE_REGISTRY: dict[str, type] = {
    # Batch 1 — Consultant core
    "PM_ALEX":      PmAlex,
    "ARCH_SARA":    ArchSara,
    "BASIS_KURT":   BasisKurt,
    "DEV_PRIYA":    DevPriya,
    "DEV_LEON":     DevLeon,
    "FI_CHEN":      FiChen,
    "CO_MARTA":     CoMarta,
    "MM_RAVI":      MmRavi,
    "SD_ISLA":      SdIsla,
    "PP_JONAS":     PpJonas,
    # Batch 2 — Consultant extended + Customer strategic
    "WM_FATIMA":    WmFatima,
    "INT_MARCO":    IntMarco,
    "SEC_DIANA":    SecDiana,
    "BI_SAM":       BiSam,
    "CHG_NADIA":    ChgNadia,
    "DM_FELIX":     DmFelix,
    "EXEC_VICTOR":  ExecVictor,
    "IT_MGR_HELEN": ItMgrHelen,
    "CUST_PM_OMAR": CustPmOmar,
    "FI_KU_ROSE":   FiKuRose,
    # Batch 3 — Customer KUs + cross-functional
    "CO_KU_BJORN":   CoKuBjorn,
    "MM_KU_GRACE":   MmKuGrace,
    "SD_KU_TONY":    SdKuTony,
    "WM_KU_ELENA":   WmKuElena,
    "PP_KU_IBRAHIM": PpKuIbrahim,
    "HR_KU_SOPHIE":  HrKuSophie,
    "BA_CUST_JAMES": BaCustJames,
    "CHAMP_LEILA":   ChampLeila,
    "PMO_NIKO":      PmoNiko,
    "QA_CLAIRE":     QaClaire,
}

__all__ = [
    # Batch 1
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
    # Batch 2
    "WmFatima",
    "IntMarco",
    "SecDiana",
    "BiSam",
    "ChgNadia",
    "DmFelix",
    "ExecVictor",
    "ItMgrHelen",
    "CustPmOmar",
    "FiKuRose",
    # Batch 3
    "CoKuBjorn",
    "MmKuGrace",
    "SdKuTony",
    "WmKuElena",
    "PpKuIbrahim",
    "HrKuSophie",
    "BaCustJames",
    "ChampLeila",
    "PmoNiko",
    "QaClaire",
    "ROLE_REGISTRY",
]
