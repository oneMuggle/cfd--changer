"""
inp_tool FastAPI 后端 v0.3

把 inp_tool 包成 REST API。
- 文件路径作为隐式 ID(不持久化,纯内存)
- 支持 load / get / set / save / diff
- 自动 OpenAPI 文档(/docs)
"""
from __future__ import annotations
import os
import uuid
from typing import Optional, Any
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path

from . import parse, parse_file, write, diff
from .model import Stmt, Value, Block, InpFile, infer_type


WEB_DIR = Path(__file__).parent.parent / "web"

app = FastAPI(
    title="inp_tool API",
    description="mcfd.inp 解析、修改、diff 工具的 REST API",
    version="0.3.0",
)

# CORS(开发期间允许所有)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存中的文件缓存:file_id -> (path, InpFile)
_file_cache: dict[str, tuple[str, InpFile]] = {}


# === Pydantic schemas ===
class LoadRequest(BaseModel):
    path: str


class LoadResponse(BaseModel):
    file_id: str
    path: str
    block_count: int
    top_stmt_count: int
    blocks: list[dict]  # [{name, idx, begin_line, end_line, stmt_count, has_children}]


class SetRequest(BaseModel):
    block_name: str
    block_idx: int = 0
    keyword: str
    value_index: int = 0
    value: str  # 字符串输入,在后端推断类型


class AppendRequest(BaseModel):
    block_name: str
    block_idx: int = 0
    keyword: str
    values: list[str] = Field(default_factory=list)


class SaveAsRequest(BaseModel):
    path: str


class DiffRequest(BaseModel):
    path_a: str
    path_b: str


class DiffEntrySchema(BaseModel):
    kind: str
    location: str
    keyword: str
    old: Any = None
    new: Any = None
    line_old: int = 0
    line_new: int = 0


class DiffResponse(BaseModel):
    change_count: int
    changes: list[DiffEntrySchema]
    unified: str


# === 工具函数 ===
def _get_file(file_id: str) -> tuple[str, InpFile]:
    if file_id not in _file_cache:
        raise HTTPException(404, f"file_id {file_id!r} not found")
    return _file_cache[file_id]


def _block_summary(b: Block, name: str, idx: int) -> dict:
    has_children = any(s.children for s in b.statements)
    return {
        'name': name,
        'idx': idx,
        'begin_line': b.begin_line,
        'end_line': b.end_line,
        'stmt_count': len(b.statements),
        'has_children': has_children,
    }


def _stmt_to_dict(s: Stmt, include_children: bool = True) -> dict:
    return {
        'keyword': s.keyword,
        'values': [{'raw': v.raw, 'typed': v.typed, 'type': type(v.typed).__name__}
                   for v in s.values],
        'line': s.line,
        'comment_after': s.comment_after,
        'children': [_stmt_to_dict(c) for c in s.children] if include_children else [],
    }


# === 路由 ===
@app.get("/api/health")
def health():
    return {'status': 'ok', 'version': '0.3.0'}


@app.post("/api/files/load", response_model=LoadResponse)
def load_file(req: LoadRequest):
    if not os.path.isfile(req.path):
        raise HTTPException(404, f"file not found: {req.path}")
    try:
        inp = parse_file(req.path)
    except Exception as e:
        raise HTTPException(400, f"parse failed: {e}")
    file_id = str(uuid.uuid4())[:8]
    _file_cache[file_id] = (req.path, inp)
    # 块列表(同名的多个实例都列出)
    blocks = []
    for i, b in enumerate(inp.block_list):
        blocks.append(_block_summary(b, b.name, i))
    return LoadResponse(
        file_id=file_id,
        path=req.path,
        block_count=len(inp.block_list),
        top_stmt_count=len(inp.top_stmts),
        blocks=blocks,
    )


@app.get("/api/files/{file_id}")
def get_file_info(file_id: str):
    path, inp = _get_file(file_id)
    blocks = [_block_summary(b, b.name, i) for i, b in enumerate(inp.block_list)]
    return {
        'file_id': file_id,
        'path': path,
        'block_count': len(inp.block_list),
        'top_stmt_count': len(inp.top_stmts),
        'blocks': blocks,
        'modified': False,  # TODO: track dirty
    }


@app.get("/api/files/{file_id}/block/{idx}")
def get_block(file_id: str, idx: int):
    path, inp = _get_file(file_id)
    if idx < 0 or idx >= len(inp.block_list):
        raise HTTPException(404, f"block idx {idx} out of range")
    b = inp.block_list[idx]
    return {
        'name': b.name,
        'idx': idx,
        'begin_line': b.begin_line,
        'end_line': b.end_line,
        'pre_comments': b.pre_comments,
        'trailing_comments': b.trailing_comments,
        'statements': [_stmt_to_dict(s) for s in b.statements],
    }


@app.get("/api/files/{file_id}/top")
def get_top(file_id: str):
    path, inp = _get_file(file_id)
    return {
        'statements': [_stmt_to_dict(s) for s in inp.top_stmts],
    }


@app.get("/api/files/{file_id}/search")
def search_keyword(file_id: str, keyword: str):
    """全局搜一个关键字,返回所有出现位置"""
    path, inp = _get_file(file_id)
    results = []
    for i, b in enumerate(inp.block_list):
        for s in b.statements:
            if s.keyword == keyword:
                results.append({
                    'block': b.name, 'block_idx': i,
                    'line': s.line,
                    'values': [v.typed for v in s.values],
                })
    for s in inp.top_stmts:
        if s.keyword == keyword:
            results.append({
                'block': None, 'block_idx': -1, 'top': True,
                'line': s.line,
                'values': [v.typed for v in s.values],
            })
    return {'keyword': keyword, 'count': len(results), 'results': results}


@app.post("/api/files/{file_id}/set")
def set_value(file_id: str, req: SetRequest):
    path, inp = _get_file(file_id)
    # 找块
    b = None
    actual_idx = 0
    for i, bb in enumerate(inp.block_list):
        if bb.name == req.block_name:
            if actual_idx == req.block_idx:
                b = bb
                break
            actual_idx += 1
    if b is None:
        # 尝试顶层
        if req.block_name.lower() == 'top' or req.block_name == '':
            found = None
            for s in inp.top_stmts:
                if s.keyword == req.keyword:
                    found = s
                    break
            if found is None:
                raise HTTPException(404, f"top keyword {req.keyword!r} not found")
            if req.value_index >= len(found.values):
                raise HTTPException(400, f"value_index {req.value_index} out of range")
            found.set(req.value_index, infer_type(req.value))
            return {
                'ok': True,
                'location': 'top',
                'keyword': req.keyword,
                'new_value': found.values[req.value_index].typed,
            }
        raise HTTPException(404, f"block {req.block_name!r}[{req.block_idx}] not found")
    # 在块内改
    found = None
    for s in b.statements:
        if s.keyword == req.keyword:
            found = s
            break
    if found is None:
        raise HTTPException(404, f"keyword {req.keyword!r} not in block")
    if req.value_index >= len(found.values):
        raise HTTPException(400, f"value_index {req.value_index} out of range")
    found.set(req.value_index, infer_type(req.value))
    return {
        'ok': True,
        'location': f'{b.name}[{req.block_idx}]',
        'keyword': req.keyword,
        'new_value': found.values[req.value_index].typed,
    }


@app.post("/api/files/{file_id}/append")
def append_stmt(file_id: str, req: AppendRequest):
    path, inp = _get_file(file_id)
    b = None
    actual_idx = 0
    for i, bb in enumerate(inp.block_list):
        if bb.name == req.block_name:
            if actual_idx == req.block_idx:
                b = bb
                break
            actual_idx += 1
    if b is None:
        raise HTTPException(404, f"block {req.block_name!r}[{req.block_idx}] not found")
    stmt = b.append(req.keyword, *req.values)
    return {'ok': True, 'line': stmt.line}


@app.post("/api/files/{file_id}/save")
def save_file(file_id: str):
    path, inp = _get_file(file_id)
    write(inp, path)
    return {'ok': True, 'path': path}


@app.post("/api/files/{file_id}/save_as")
def save_as(file_id: str, req: SaveAsRequest):
    path, inp = _get_file(file_id)
    write(inp, req.path)
    _file_cache[file_id] = (req.path, inp)
    return {'ok': True, 'path': req.path}


@app.post("/api/diff", response_model=DiffResponse)
def diff_files(req: DiffRequest):
    if not os.path.isfile(req.path_a):
        raise HTTPException(404, f"file A not found: {req.path_a}")
    if not os.path.isfile(req.path_b):
        raise HTTPException(404, f"file B not found: {req.path_b}")
    try:
        a = parse_file(req.path_a)
        b = parse_file(req.path_b)
    except Exception as e:
        raise HTTPException(400, f"parse failed: {e}")
    r = diff(a, b)
    changes = [DiffEntrySchema(
        kind=e.kind, location=e.location, keyword=e.keyword,
        old=e.old, new=e.new, line_old=e.line_old, line_new=e.line_new,
    ) for e in r.changes]
    return DiffResponse(
        change_count=len(changes),
        changes=changes,
        unified=r.unified(req.path_a, req.path_b),
    )


# === 静态前端 ===
if WEB_DIR.is_dir():
    @app.get("/")
    def root():
        return FileResponse(WEB_DIR / "index.html")
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def main():
    """inp-tool-api 入口:启动 FastAPI 开发服务器。

    生产环境建议用 uvicorn 直接调用:
        uvicorn inp_tool.api:app --host 0.0.0.0 --port 8765 --workers 4
    """
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
