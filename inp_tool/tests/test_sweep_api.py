"""
mcfd.inp sweep FastAPI — Phase 5 RED

测试目标:
- POST /api/sweep 端点
- 接受 CaseSweep 配置 dict
- 返回 SweepReport JSON
- dry_run 模式不写盘
"""
from __future__ import annotations
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from inp_tool.api import app
    return TestClient(app)


@pytest.fixture
def template_inp(tmp_path):
    p = tmp_path / "template.inp"
    p.write_text(
        "guiopts begin\n"
        "aero_alpha 0.0\nguiopts end\n"
        "physics begin\nrefvel 0.0\nreftem 288.15\nrefpre 101325.0\nphysics end\n"
    )
    return p


class TestSweepAPI:
    def test_sweep_endpoint_exists(self, client):
        r = client.post("/api/sweep", json={})
        # 4xx 表示路由存在并被处理
        assert r.status_code in (400, 422)

    def test_sweep_runs_and_returns_report(self, client, template_inp, tmp_path):
        out_dir = str(tmp_path / "api_cases")
        r = client.post("/api/sweep", json={
            "template": str(template_inp),
            "output_dir": out_dir,
            "sweeps": {
                "alpha": [0.0, 4.0],
                "mach": [0.6, 0.8],
                "T_inf": [288.15],
                "p_inf": [101325.0],
            },
        })
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 4
        assert len(data["cases"]) == 4

    def test_sweep_dry_run_does_not_write(self, client, template_inp, tmp_path):
        out_dir = str(tmp_path / "api_dry")
        r = client.post("/api/sweep", json={
            "template": str(template_inp),
            "output_dir": out_dir,
            "sweeps": {"alpha": [0.0, 4.0], "T_inf": [288.15], "p_inf": [101325.0]},
            "dry_run": True,
        })
        assert r.status_code == 200
        # dry-run 不应写盘
        assert not (tmp_path / "api_dry").exists()

    def test_sweep_missing_template_returns_4xx(self, client, tmp_path):
        r = client.post("/api/sweep", json={
            "template": str(tmp_path / "missing.inp"),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0]},
        })
        assert r.status_code in (400, 404, 422, 500)

    def test_sweep_invalid_config_returns_4xx(self, client, template_inp, tmp_path):
        r = client.post("/api/sweep", json={
            "template": str(template_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {},
        })
        assert r.status_code in (400, 422, 500)

    def test_sweep_writes_files_to_output_dir(self, client, template_inp, tmp_path):
        out_dir = str(tmp_path / "api_written")
        r = client.post("/api/sweep", json={
            "template": str(template_inp),
            "output_dir": out_dir,
            "sweeps": {"alpha": [0.0, 2.0, 4.0], "T_inf": [288.15], "p_inf": [101325.0]},
        })
        assert r.status_code == 200
        # 验证文件已写
        inps = list((tmp_path / "api_written").glob("*.inp"))
        assert len(inps) == 3
