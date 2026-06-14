"""
mcfd.inp 工具包 v0.4

v0.4 变更:
- 新增 sweep 批量算例生成器(inp_tool.sweep)
  - FreestreamPreset: 几何分解 (alpha, beta, Ma) → (U, V, W) + refvel
  - CaseSweep: YAML/JSON 配置
  - generate(): 笛卡尔积展开 → N 个 .inp + manifest.json
  - CLI: `inp-tool sweep <template> <config.json>`
  - API: `POST /api/sweep`

v0.3 变更:
- 完整 Python 包工程化(pyproject.toml / __main__.py / pytest 套件)
- 80% 测试覆盖率(parser / writer / diff / cli / api 五大模块)
- Web GUI 暴露为 `inp-tool-api` console_script
"""
from .model import InpFile, Block, Stmt, Value, infer_type
from .parser import parse, parse_file
from .writer import to_text, write, write_bytes
from .diff import diff, DiffReport, DiffEntry
from .sweep import (
    SweepSpec,
    expand_cartesian,
    FreestreamPreset,
    render_case_name,
    CaseResult,
    SweepReport,
    CaseSweep,
    generate,
    CopyStrategy,        # v0.8.0
    DEFAULT_EXCLUDE,     # v0.8.0
)
from .pbs import (       # v0.9.0
    PbsConfig,
    PbsIssue,
    detect_pbs_template,
    validate_base_case_dir,
    render_pbs_name,
    write_pbs,
    extract_pbs_basename,
    # v0.14.0 新增
    validate_pbs_name,        # 校验名字符合集群硬约束
    PbsValidationError,       # write_pbs 写出前抛
    PBS_NAME_MAX_LEN,         # = 15
)
from .cluster import (     # v0.14.0 新增
    SchedulerType,
    ClusterConfig,
    ClusterInfo,
    PbsJobStatus,
    TorqueAdapter,
    SlurmAdapter,
    SshClusterClient,
    LocalDryRunClient,
    probe_scheduler,
)
from .batch import (       # v0.14.0 新增(Phase 2)
    PbsSubmission,
    PbsBatchResult,
    submit_sweep,
    # v0.14.0 / Phase 3 新增
    SweepStatusEntry,
    query_sweep_status,
    summarize_states,
    format_status_table,
    # v0.14.0 / Phase 5+6 新增
    PbsCancelResult,
    cancel_sweep,
    PbsRerunResult,
    rerun_sweep,
)
from .monitor import (      # v0.14.0 / Phase 4 新增
    Info0Parser,
    CaseProgress,
    CaseMonitor,
    SweepMonitor,
    parse_info0_meta,
    format_progress_table,
    DEFAULT_INFO0_COLUMNS,
)

__all__ = [
    'InpFile', 'Block', 'Stmt', 'Value', 'infer_type',
    'parse', 'parse_file',
    'to_text', 'write', 'write_bytes',
    'diff', 'DiffReport', 'DiffEntry',
    # v0.4 sweep
    'SweepSpec', 'expand_cartesian', 'FreestreamPreset',
    'render_case_name', 'CaseResult', 'SweepReport',
    'CaseSweep', 'generate',
    # v0.8.0 整算例目录模式
    'CopyStrategy', 'DEFAULT_EXCLUDE',
    # v0.9.0 pbs 模块
    'PbsConfig', 'PbsIssue',
    'detect_pbs_template', 'validate_base_case_dir',
    'render_pbs_name', 'write_pbs', 'extract_pbs_basename',
    # v0.14.0 pbs 校验
    'validate_pbs_name', 'PbsValidationError', 'PBS_NAME_MAX_LEN',
    # v0.14.0 cluster
    'SchedulerType', 'ClusterConfig', 'ClusterInfo', 'PbsJobStatus',
    'TorqueAdapter', 'SlurmAdapter',
    'SshClusterClient', 'LocalDryRunClient',
    'probe_scheduler',
    # v0.14.0 batch
    'PbsSubmission', 'PbsBatchResult', 'submit_sweep',
    # v0.14.0 status (Phase 3)
    'SweepStatusEntry', 'query_sweep_status',
    'summarize_states', 'format_status_table',
    # v0.14.0 cancel / rerun (Phase 5+6)
    'PbsCancelResult', 'cancel_sweep',
    'PbsRerunResult', 'rerun_sweep',
    # v0.14.0 monitor (Phase 4)
    'Info0Parser', 'CaseProgress', 'CaseMonitor', 'SweepMonitor',
    'parse_info0_meta', 'format_progress_table',
    'DEFAULT_INFO0_COLUMNS',
]
__version__ = '0.13.0'
