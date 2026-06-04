"""
inp_tool v0.4 sweep 演示

基于一个 mcfd.inp 样例批量生成 (alpha, beta, Ma) 扫描算例。

运行:
    conda run -n cfdchanger python examples/sweep_demo.py

输出:
    examples/sweep_cases/case_aoa00_b00_ma0.60.inp
    examples/sweep_cases/case_aoa00_b00_ma0.80.inp
    ...
    examples/sweep_cases/manifest.json
"""
from __future__ import annotations
import json
import os
import sys

# 让本文件能直接 `python examples/sweep_demo.py` 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inp_tool import CaseSweep, FreestreamPreset, generate, parse_file


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    template = os.path.join(here, "mcfd_v2_modified.inp")
    out_dir = os.path.join(here, "sweep_cases")

    # 显式构造配置(也可以写 JSON 文件再 CaseSweep.from_json 加载)
    cs = CaseSweep.from_dict({
        "template": template,
        "output_dir": out_dir,
        "sweeps": {
            "alpha": [0.0, 4.0, 8.0],      # deg
            "beta":  [0.0],                 # 单值
            "mach":  [0.60, 0.80],          # Ma
            "T_inf": [288.15],              # K(单值,辅助)
            "p_inf": [101325.0],            # Pa(单值,辅助)
        },
        "naming": "case_aoa{alpha:02.0f}_b{beta:02.0f}_ma{mach:.2f}",
        "manifest": {"path": os.path.join(out_dir, "manifest.json")},
    })

    print(f"=== sweep 配置 ===")
    print(f"  template: {cs.template}")
    print(f"  output:   {cs.output_dir}")
    print(f"  naming:   {cs.naming}")

    report = generate(cs)
    print(f"\n=== 生成结果: {report.total} 个 case ===")
    for c in report.cases:
        # 抽查一个生成文件,验证 aero_alpha 写入了
        if c.path and os.path.isfile(c.path):
            inp2 = parse_file(c.path)
            alpha = inp2.get("guiopts", "aero_alpha")
            print(f"  - {c.case_id}  "
                  f"alpha={c.params['alpha']}  "
                  f"mach={c.params['mach']}  "
                  f"[verify: guiopts.aero_alpha={alpha}]")
        else:
            print(f"  - {c.case_id}  (file missing)")

    print(f"\n=== manifest ===")
    if os.path.isfile(cs.manifest_path):
        with open(cs.manifest_path) as f:
            data = json.load(f)
        print(f"  total: {data['total']}")
        print(f"  template_sha256: {data.get('template_sha256', 'N/A')[:16]}...")
        print(f"  path: {cs.manifest_path}")


if __name__ == "__main__":
    main()
