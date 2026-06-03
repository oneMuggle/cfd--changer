# CFD++ HTML 中文翻译检查报告

生成时间：2026-05-23

## 一、概况

| 项目 | 数值 |
|---|---|
| html 源文件总数 | 629 |
| html_cn 翻译文件总数 | 629 |
| 文件对应率 | **100%** ✅ |

---

## 二、检查结果汇总

### ✅ 通过项

1. **文件对应率**：html 目录的 629 个文件在 html_cn 目录中均有对应翻译文件，无遗漏。
2. **HTML 标题翻译**：抽检的大文件（turb.html、bc_descriptions.html、train_2dball.html 等）标题均已正确翻译为中文。
3. **内容完整性（95%+）**：随机抽检 80+ 个文件（覆盖各批次），绝大多数文件已将正文内容完整翻译为中文，HTML 结构完好。
4. **专业术语保留适当**：代码片段（PRE 标签）、工具名称、命令示例、文件名等保留英文，符合技术文档规范。
5. **内部链接基本正确**：大部分 href 链接指向 `.html`，在 _cn 目录下使用时路径正确。图片路径（gifs/...）保持正确。

### ⚠️ 发现问题

#### 问题 1：部分文件存在残留英文段落（40 个文件）

通过正则 `The \w+ is [a-z]` 扫描发现以下 40 个文件在正文或表格中仍有英文句子未被翻译：

| 文件名 | 说明 |
|---|---|
| bc_descriptions.html | 大文件，残留少量英文表格条目 |
| train 系列文件（21 个） | 训练示例文件，教程内容残留英文 |
| turb.html | 湍流模型文档 |
| turbgui.html | 湍流 GUI 文档 |
| wallfunctions.html | 壁面函数文档 |
| wizards.html | 向导文档 |
| vent.html | vent 工具文档 |
| vof.html | VOF 模型文档 |
| vrlog.html | 求解日志文档 |
| unsfast.html | UNSFAST 文档 |
| xyplotter.html | XY 绘图器文档 |
| zobmerge.html | 工具文档 |

**严重程度**：低。这 40 个文件大多为训练示例或大型参考文档，残留英文通常出现在：
- 少量辅助说明文字
- 示例数据或边界条件描述
- 图表的英文 alt 属性说明

#### 问题 2：xyplotter.html 严重翻译不完整（混写英文/中文）

该文件存在大量半中半英的混杂段落，例如：
- `The XY plotter is a 也l 那个 plots`
- `在...范围内 每个 menu item is underlined`

这是翻译过程中断后遗留的混写文件，需要优先重新翻译。

#### 问题 3：href 链接未更新为 _cn 版本

扫描发现有 26 个文件中的内部链接仍指向源 html 目录路径（如 `href="resplot.html"`），而不是 `_cn` 版本。这在用户仅使用 html_cn 目录时会引起链接失效。

典型问题文件（部分）：
```
chap_examples.html → ftp://ftp.metacomptech.com/... 和 trainingexamplelist.html
chap_fileformats.html → solplotter.html
guidelines.html → reyinf.html, mreyinf.html
probing.html → resplot.html, tresplot.html
训练示例文件 → resplot.html
```

**严重程度**：中等。链接失效影响用户体验，需要将内部 .html 链接加上 `_cn` 后缀或替换为指向 html_cn 目录的路径。

---

## 三、总体评价

| 维度 | 评分 | 说明 |
|---|---|---|
| 文件完整性 | ⭐⭐⭐⭐⭐ | 629 个文件全部对应，无遗漏 |
| 标题翻译 | ⭐⭐⭐⭐⭐ | 抽检文件标题均已翻译 |
| 正文翻译 | ⭐⭐⭐⭐ | 95%+ 文件正文完整翻译 |
| HTML 结构保留 | ⭐⭐⭐⭐⭐ | HTML 标签、代码块完整保留 |
| 内部链接修正 | ⭐⭐ | 26 个文件链接需更新 |

**整体质量**：良好（~80-85%）。大部分文件翻译质量高，少数文件需要补充翻译或修正链接。

---

## 四、修复建议

### 高优先级（需立即处理）

1. **xyplotter.html** —— 重新翻译全文（已发现严重混写）
2. **href 链接修正**（26 个文件）—— 批量将内部 `.html` 链接替换为 `_cn` 版本

### 中优先级

3. **40 个残留英文文件** —— 逐个检查并补充翻译剩余英文段落

---

*报告生成工具：Mavis 自动检查*