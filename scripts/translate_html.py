# -*- coding: utf-8 -*-
"""
批量翻译 HTML → 中文
- 逐个文件处理，避免大文件溢出
- 正确 UTF-8 (BOM) 编码处理
- 分块合理（每批 15 条文本），避免 token 溢出
- 进度保存到 translate_v2_progress.json，断了能从上次继续

用法:
    python scripts/translate_html.py
"""
import os
import re
import json
import time
import subprocess
from html.parser import HTMLParser
from pathlib import Path

# 仓库根 = scripts/ 的父目录
_REPO_ROOT = Path(__file__).resolve().parent.parent

# ========== 路径配置(可被环境变量覆盖) ==========
# 便于在其他机器 / CI 上跑
SRC = Path(os.environ.get("CFDCHG_HTML_SRC", _REPO_ROOT / "html"))
DST = Path(os.environ.get("CFDCHG_HTML_DST", _REPO_ROOT / "html_cn"))
LOG = Path(os.environ.get("CFDCHG_HTML_LOG", _REPO_ROOT / "scripts" / ".state" / "translate_v2_progress.json"))
# LLM 脚本路径(Windows 内置 skill 目录)
SKILL_DIR = Path(os.environ.get(
    "CFDCHG_LLM_SKILL_DIR",
    Path.home() / ".mavis" / ".builtin-skills" / "llm-call",
))
LLM_SCRIPT = Path(os.environ.get(
    "CFDCHG_LLM_SCRIPT", SKILL_DIR / "scripts" / "llm_call.py",
))

# 跳过这些标签内的内容不翻译
SKIP_TAGS = {"script", "style", "code", "pre", "kbd", "var", "samp", "tt", "math", "svg"}

# LLM 配置
LLM_MODEL = "anthropic/claude-sonnet-4-7"
MAX_TOKENS = 8192


# ========== HTML 解析器 ==========
class HTMLTextExtractor(HTMLParser):
    """提取 HTML 中的文本节点，保留标签结构"""

    def __init__(self):
        super().__init__()
        self.segs = []  # (type, content) type: "tag" 或 "text"
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        tl = tag.lower()
        if tl in SKIP_TAGS:
            self.skip += 1
        attrs_str = ''.join(f' {n}="{v}"' for n, v in attrs if v is not None)
        self.segs.append(("tag", f"<{tag}{attrs_str}>"))

    def handle_endtag(self, tag):
        tl = tag.lower()
        if tl in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        self.segs.append(("tag", f"</{tag}>"))

    def handle_data(self, data):
        if self.skip == 0:
            stripped = data
            if stripped.strip():
                self.segs.append(("text", stripped))

    def handle_comment(self, data):
        self.segs.append(("tag", f"<!--{data}-->"))

    def handle_startendtag(self, tag, attrs):
        tl = tag.lower()
        if tl in SKIP_TAGS:
            self.skip += 1
        attrs_str = ''.join(f' {n}="{v}"' for n, v in attrs if v is not None)
        self.segs.append(("tag", f"<{tag}{attrs_str}/>"))

    def handle_decl(self, decl):
        self.segs.append(("tag", f"<!{decl}>"))

    def handle_pi(self, data):
        self.segs.append(("tag", f"<?{data}>"))

    def unknown_decl(self, data):
        self.segs.append(("tag", f"<![CDATA[{data}]>"))


def extract_texts(html_content):
    """从 HTML 中提取所有文本片段"""
    ext = HTMLTextExtractor()
    ext.feed(html_content)
    texts = []
    segs = []
    for tp, ct in ext.segs:
        if tp == "text" and ct.strip():
            texts.append(ct.strip())
            segs.append((tp, ct))
        elif tp == "tag":
            segs.append((tp, ct))
    return texts, segs


def reconstruct_html(segs, translated_texts):
    """将翻译后的文本放回 HTML 结构"""
    result = []
    text_idx = 0
    for tp, ct in segs:
        if tp == "text":
            if text_idx < len(translated_texts):
                result.append(translated_texts[text_idx])
                text_idx += 1
            else:
                result.append(ct)  # fallback: 保留原文
        else:
            result.append(ct)
    return "".join(result)


# ========== LLM 翻译 ==========
def translate_batch(texts, batch_num):
    """调用 LLM 翻译一批文本"""
    if not texts:
        return texts

    prompt = """You are a professional CFD (Computational Fluid Dynamics) technical translator.
Translate the following English text to Chinese. Rules:
1. Keep ALL HTML tags unchanged
2. Keep image src, href links unchanged
3. Translate text content only to Chinese
4. Technical terms: keep English for model names (k-epsilon, RANS, LES, SST, SA, DNS, etc.)
5. Use accurate CFD terminology in Chinese
6. Output only the translated text, one phrase per line
7. Preserve line breaks as separators

Text to translate:
---
"""

    combined = "\n===TEXT_SEPARATOR===\n".join(texts)
    prompt += combined
    prompt += "\n---"

    try:
        result = subprocess.run(
            ['py', '-3', LLM_SCRIPT,
             '--model', LLM_MODEL,
             '--max-tokens', str(MAX_TOKENS),
             '--prompt', prompt],
            capture_output=True,
            text=True,
            timeout=180,
            encoding='utf-8'
        )

        if result.returncode != 0:
            print(f"  [ERROR] LLM call failed: {result.stderr[:200]}")
            return texts

        output = result.stdout.strip()

        if "===TEXT_SEPARATOR===" in output:
            translated = output.split("===TEXT_SEPARATOR===")
            translated = [t.strip() for t in translated]
        else:
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            if len(lines) >= len(texts):
                translated = lines[:len(texts)]
            else:
                print(f"  [WARN] Translation line count mismatch ({len(lines)} vs {len(texts)})")
                translated = texts

        while len(translated) < len(texts):
            translated.append(texts[len(translated)])

        return translated[:len(texts)]

    except subprocess.TimeoutExpired:
        print(f"  [WARN] LLM call timeout")
        return texts
    except Exception as e:
        print(f"  翻译错误: {e}")
        return texts


# ========== 主流程 ==========
def translate_file(src_path, dst_path, batch_num):
    """翻译单个文件"""
    try:
        with open(src_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        print(f"  读取失败: {e}")
        return False

    if re.search(r'[一-鿿]', html):
        print(f"  [SKIP] Already has Chinese")
        return True

    texts, segs = extract_texts(html)
    if not texts:
        print(f"  [SKIP] No text content")
        return True

    translated_texts = []
    batch_size = 15

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        print(f"  Translating batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1} ({len(batch)} texts)...")

        result = translate_batch(batch, batch_num)
        translated_texts.extend(result)

        time.sleep(0.5)

    result_html = reconstruct_html(segs, translated_texts)

    if not result_html.startswith('﻿'):
        result_html = '﻿' + result_html

    try:
        with open(dst_path, 'w', encoding='utf-8-sig') as f:
            f.write(result_html)
        return True
    except Exception as e:
        print(f"  [ERROR] Write failed: {e}")
        return False


def main():
    os.makedirs(DST, exist_ok=True)

    done = {}
    if os.path.exists(LOG):
        try:
            with open(LOG, "r", encoding="utf-8") as f:
                done = json.load(f)
        except:
            pass

    files = sorted(f for f in os.listdir(SRC) if f.endswith('.html'))
    total = len(files)
    pending = [f for f in files if f not in done or done.get(f) != 'done']

    print(f"[SUMMARY] Total: {total}, Done: {sum(1 for v in done.values() if v == 'done')}, Pending: {len(pending)}\n")

    if not pending:
        print("全部完成！")
        return

    success = 0
    failed = []

    for idx, filename in enumerate(pending):
        src_path = os.path.join(SRC, filename)
        dst_path = os.path.join(DST, filename)

        print(f"[PROCESS] Translating file: {idx+1}/{len(pending)} - {filename}")

        try:
            ok = translate_file(src_path, dst_path, idx)

            if ok:
                done[filename] = 'done'
                success += 1
                with open(LOG, 'w', encoding='utf-8') as f:
                    json.dump(done, f, ensure_ascii=False, indent=2)
                print(f"  [OK] Complete")
            else:
                done[filename] = 'failed'
                failed.append(filename)
                print(f"  [FAIL] Failed")

        except KeyboardInterrupt:
            print("\n[INTERRUPT] Saving progress...")
            with open(LOG, 'w', encoding='utf-8') as f:
                json.dump(done, f, ensure_ascii=False, indent=2)
            break
        except Exception as e:
            print(f"  [ERROR] {e}")
            done[filename] = 'failed'
            failed.append(filename)

        time.sleep(0.3)

    print(f"[DONE] Complete: {success}/{len(pending)}")
    if failed:
        print(f"[FAIL] Failed count: {len(failed)}")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
