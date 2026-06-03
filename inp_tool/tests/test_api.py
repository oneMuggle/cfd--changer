"""inp_tool.api (FastAPI) 单元测试。

依赖:pip install -e .[api,dev]  (fastapi / uvicorn / pydantic / httpx)
若任一依赖缺失,整个文件 pytest.importorskip 跳过(不报错)。
"""
import pytest

# 缺任何依赖就跳过整个文件
pytest.importorskip("fastapi", reason="api tests need `pip install -e .[api,dev]`")
pytest.importorskip("httpx", reason="api tests need `pip install -e .[dev]` for TestClient")
pytest.importorskip("pydantic", reason="api tests need `pip install -e .[api]`")

from fastapi.testclient import TestClient  # noqa: E402

from inp_tool.api import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def file_id(client, sample_inp):
    """加载 sample_inp,返回 file_id(整个 module 复用)。"""
    r = client.post("/api/files/load", json={"path": str(sample_inp)})
    assert r.status_code == 200, r.text
    return r.json()["file_id"]


# ========== health ==========
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ========== load ==========
def test_load_file(client, sample_inp):
    r = client.post("/api/files/load", json={"path": str(sample_inp)})
    assert r.status_code == 200
    data = r.json()
    assert "file_id" in data
    assert data["path"] == str(sample_inp)
    assert data["block_count"] > 0
    assert isinstance(data["blocks"], list)


def test_load_file_not_found(client):
    r = client.post("/api/files/load", json={"path": "Z:/does/not/exist.inp"})
    assert r.status_code == 404


# ========== get_file_info ==========
def test_get_file_info(client, file_id):
    r = client.get(f"/api/files/{file_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["file_id"] == file_id
    assert data["block_count"] > 0


def test_get_file_info_unknown_id(client):
    r = client.get("/api/files/unknown_id")
    assert r.status_code == 404


# ========== get_block ==========
def test_get_block(client, file_id):
    r = client.get(f"/api/files/{file_id}/block/0")
    assert r.status_code == 200
    data = r.json()
    assert data["idx"] == 0
    assert "statements" in data


def test_get_block_out_of_range(client, file_id):
    r = client.get(f"/api/files/{file_id}/block/9999")
    assert r.status_code == 404


# ========== get_top ==========
def test_get_top(client, file_id):
    r = client.get(f"/api/files/{file_id}/top")
    assert r.status_code == 200
    assert "statements" in r.json()


# ========== search_keyword ==========
def test_search_keyword(client, file_id):
    r = client.get(f"/api/files/{file_id}/search", params={"keyword": "cflbot"})
    assert r.status_code == 200
    data = r.json()
    assert data["keyword"] == "cflbot"
    assert data["count"] >= 1
    # 结果里至少一个 location 应是 tsteps 块
    assert any("tsteps" in (loc.get("block") or "") for loc in data["results"])


# ========== set_value ==========
def test_set_value_in_block(client, file_id):
    r = client.post(
        f"/api/files/{file_id}/set",
        json={
            "block_name": "tsteps",
            "block_idx": 0,
            "keyword": "cflbot",
            "value_index": 0,
            "value": "0.999",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["new_value"] == 0.999


def test_set_value_block_not_found(client, file_id):
    r = client.post(
        f"/api/files/{file_id}/set",
        json={
            "block_name": "no_such_block",
            "block_idx": 0,
            "keyword": "x",
            "value_index": 0,
            "value": "1",
        },
    )
    assert r.status_code == 404


# ========== append_stmt ==========
def test_append_stmt(client, file_id):
    r = client.post(
        f"/api/files/{file_id}/append",
        json={
            "block_name": "tsteps",
            "block_idx": 0,
            "keyword": "test_extra_key",
            "values": ["42"],
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ========== save / save_as ==========
def test_save_as(client, file_id, tmp_path):
    out = tmp_path / "api_saved.inp"
    r = client.post(f"/api/files/{file_id}/save_as", json={"path": str(out)})
    assert r.status_code == 200
    assert out.exists()
    assert "tsteps begin" in out.read_text(encoding="utf-8")


def test_save(client, file_id, tmp_path):
    """save 端点写回原路径(测试中用 tmp_path,避免覆盖原 sample_inp)。"""
    src = tmp_path / "orig.inp"
    src.write_text("tsteps begin\nntstep 100\ntsteps end\n", encoding="utf-8")
    r = client.post("/api/files/load", json={"path": str(src)})
    fid = r.json()["file_id"]
    r2 = client.post(f"/api/files/{fid}/save")
    assert r2.status_code == 200
    assert r2.json()["path"] == str(src)


# ========== diff ==========
def test_diff_files(client, sample_inp, tmp_path):
    a = sample_inp
    b = tmp_path / "modified.inp"
    b.write_text(
        sample_inp.read_text(encoding="utf-8", errors="replace")
        .replace("cflbot  ", "cflbot 0.999"),
        encoding="utf-8",
    )
    r = client.post("/api/diff", json={"path_a": str(a), "path_b": str(b)})
    assert r.status_code == 200
    data = r.json()
    assert "changes" in data
    assert "unified" in data


def test_diff_files_missing(client):
    r = client.post(
        "/api/diff",
        json={"path_a": "Z:/no/a.inp", "path_b": "Z:/no/b.inp"},
    )
    assert r.status_code == 404
