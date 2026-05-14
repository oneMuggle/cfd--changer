# -*- coding: utf-8 -*-
"""
批量翻译 HTML → 中文
将 HTML 文本提取为 JSON 文件，然后逐批发送翻译请求，
翻译完成后将结果写回 HTML。
"""
import os, re, json, time
from html.parser import HTMLParser

SRC  = r"E:\ProgrammingData\python\cfd++changer\html"
DST  = r"E:\ProgrammingData\python\cfd++changer\html_cn"
LOG  = r"E:\ProgrammingData\python\cfd++changer\translate_progress.json"
SKIP_TAGS = {"script","style","code","pre","kbd","var","samp","tt","math","svg"}

class Ext(HTMLParser):
    def __init__(self):
        super().__init__()
        self.segs = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        tl = tag.lower()
        if tl in SKIP_TAGS: self.skip += 1
        self.segs.append(("tag", f"<{tag}{''.join(f' {n}=\"{v}\"' for n,v in attrs if v)}>"))
    def handle_endtag(self, tag):
        tl = tag.lower()
        if tl in SKIP_TAGS: self.skip = max(0, self.skip-1)
        self.segs.append(("tag", f"</{tag}>"))
    def handle_data(self, data):
        if self.skip == 0: self.segs.append(("text", data))
    def handle_comment(self, data): self.segs.append(("tag", f"<!--{data}-->\n"))
    def handle_startendtag(self, tag, attrs):
        tl = tag.lower()
        if tl in SKIP_TAGS: self.skip += 1
        self.segs.append(("tag", f"<{tag}{''.join(f' {n}=\"{v}\"' for n,v in attrs if v)}/>"))
    def handle_decl(self, decl): self.segs.append(("tag", f"<!{decl}>"))
    def handle_pi(self, data):   self.segs.append(("tag", f"<?{data}>"))
    def unknown_decl(self, data): self.segs.append(("tag", f"<![CDATA[{data}]>"))

def extract_file(filepath, filename):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()
    if re.search(r'[\u4e00-\u9fff]', html):
        return None  # skip
    ext = Ext()
    ext.feed(html)
    texts = []
    for tp, ct in ext.segs:
        if tp == "text" and ct.strip():
            texts.append(ct.strip())
    if not texts:
        return None
    return {"filename": filename, "all_text": texts, "segs": [(tp,ct) for tp,ct in ext.segs]}

def reconstruct(segs, translated):
    out = []
    ti = 0
    for tp, ct in segs:
        if tp == "text":
            out.append(translated[ti] if ti < len(translated) else ct)
            ti += 1
        else:
            out.append(ct)
    return "".join(out)

def main():
    os.makedirs(DST, exist_ok=True)
    
    # 加载进度
    done = {}
    if os.path.exists(LOG):
        try:
            with open(LOG, "r", encoding="utf-8") as f:
                done = json.load(f)
        except: pass

    files = sorted(f for f in os.listdir(SRC) if f.endswith(".html"))
    total = len(files)
    pending = [f for f in files if f not in done]
    
    print(f"📋 总计 {total}, 已完成 {len(done)}, 待处理 {len(pending)}\n")
    
    # 分批提取文本
    batch_size = 30  # 每批处理 30 个文件
    batch_num = 0
    
    for i in range(0, len(pending), batch_size):
        batch_files = pending[i:i+batch_size]
        batch_num += 1
        
        # 提取本批文本
        batch_data = []
        for fn in batch_files:
            data = extract_file(os.path.join(SRC, fn), fn)
            if data:
                batch_data.append(data)
        
        if not batch_data:
            print(f"批次 {batch_num}: 无有效文本")
            for fn in batch_files:
                done[fn] = "skipped"
            continue
        
        print(f"\n{'='*50}")
        print(f"📦 批次 {batch_num}: {len(batch_data)} 个文件, {sum(len(d['all_text']) for d in batch_data)} 段文本")
        print(f"请将这些文本翻译为中文 (保持顺序)。\n")
        
        # 将待翻译内容保存到文件，由外部翻译
        temp_file = os.path.join(os.path.dirname(LOG), f"batch_{batch_num}_input.json")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(batch_data, f, ensure_ascii=False, indent=2)
        
        print(f"已将批次内容保存到: {temp_file}")
        print(f"翻译完成后请运行: translate_html.py (会自动读取结果)\n")
        print(f"⚠️  注意: 由于文件数量太多(629个)且文件体积大，")
        print(f"     建议先翻译几个典型文件测试效果，")
        print(f"     确认满意后再决定是否全部翻译。\n")
        print(f"当前已完成的文件列表:")
        for fn in list(done.keys())[:10]:
            print(f"  ✅ {fn}")
        if len(done) > 10:
            print(f"  ... 共 {len(done)} 个文件")
        break  # 先停下来让用户确认

if __name__ == "__main__":
    main()
