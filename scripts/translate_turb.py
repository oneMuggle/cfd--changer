# -*- coding: utf-8 -*-
"""
translate_turb.py - 翻译 turb.html 到中文
两种模式:
  - 字典模式 (默认): 用已手工翻译的标题/段落做字面替换
  - LLM 模式  (--llm): 分块调用 LLM 翻译,处理字典未覆盖的部分

用法:
    python scripts/translate_turb.py            # 字典模式
    python scripts/translate_turb.py --llm      # LLM 模式
    python scripts/translate_turb.py --help     # 帮助
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# 仓库根 = scripts/ 的父目录
_REPO_ROOT = Path(__file__).resolve().parent.parent

# ========== 路径配置(可被环境变量覆盖) ==========
INPUT_FILE = Path(os.environ.get(
    "CFDCHG_TURB_INPUT", _REPO_ROOT / "html" / "turb.html",
))
OUTPUT_FILE = Path(os.environ.get(
    "CFDCHG_TURB_OUTPUT", _REPO_ROOT / "html_cn" / "turb.html",
))
SKILL_DIR = Path(os.environ.get(
    "CFDCHG_LLM_SKILL_DIR",
    Path.home() / ".mavis" / ".builtin-skills" / "llm-call",
))
LLM_SCRIPT = Path(os.environ.get(
    "CFDCHG_LLM_SCRIPT", SKILL_DIR / "scripts" / "llm_call.py",
))
LLM_MODEL = "anthropic/claude-sonnet-4-7"
LLM_MAX_TOKENS = 8192
LLM_CHUNK_MAX_CHARS = 3500  # LLM 模式下每块最大字符数


# ========== 字典数据 ==========
TITLE_TRANSLATIONS = {
    "Turbulence Models within CFD++": "CFD++ 中的湍流模型",
    "Classical Statistically-Steady (RANS) Turbulence Models": "经典统计定常（RANS）湍流模型",
    "Goldberg's One-Equation Rt Model": "Goldberg 单方程 Rt 模型",
    "One-equation SA model": "单方程 SA 模型",
    "Two-equation realizable k-epsilon model": "两方程可实现 k-epsilon 模型",
    "Two-equation k-l model": "两方程 k-l 模型",
    "Two-equation non-linear (cubic) k-epsilon model": "两方程非线性（立方）k-epsilon 模型",
    "Goldberg's Two-equation realizable q-L model": "Goldberg 两方程可实现 q-L 模型",
    "Two-equation SST model": "两方程 SST 模型",
    "Two-equation R-&gamma; transition model": "两方程 R-γ 转捩模型",
    "Goldberg's Three-equation k-epsilon-Rt model": "Goldberg 三方程 k-epsilon-Rt 模型",
    "Goldberg's Three-equation k-epsilon-f_mu model": "Goldberg 三方程 k-epsilon-f_mu 模型",
    "Four-equation Langtry-Menter transition model": "四方程 Langtry-Menter 转捩模型",
    "Seven equation second moment closure model": "七方程二阶矩封闭模型",
    "k-&omega; model": "k-ω 模型",
    "Realizable k-&omega; model": "可实现 k-ω 模型",
    "Hellsten quartic k-&omega; model": "Hellsten 四次 k-ω 模型",
}

PARAGRAPH_TRANSLATIONS = [
    # 开头段落
    ("CFD++ supports a range of conventional turbulence models for predicting "
     "statistically-steady flows, as well as large-eddy simulation (LES) models and "
     "hybrid RANS/LES models.",
     "CFD++ 支持多种常规湍流模型，用于预测统计定常流动，同时也支持大涡模拟（LES）模型和混合 RANS/LES 模型。"),
    ("None of these models require surface topography-related "
     "parameters (such as normal-to-wall distances), making them ideal "
     "for use within a complex multi-block, overset or moving mesh environment.",
     "这些模型均无需表面形貌相关参数（如壁面法向距离），非常适用于复杂多块网格、重叠网格或运动网格环境。"),
    ("This section considers the three categories of model separately.",
     "本节将分别介绍这三类模型。"),
    # RANS 段落
    ("The most widespread form of turbulence modeling is ensemble-averaging, "
     "in which the model accounts for all turbulent stresses arising "
     "from an average over a repeated number of flow realizations or "
     "a time-averaging over a sufficiently-long interval.",
     "湍流建模最广泛采用的形式是集合平均，模型通过在大量流动样本的重复平均或充分长时间的时间平均来考虑所有湍流应力。"),
    ("This category of modeling together with the flow equations in which it is embedded has acquired the name `RANS' (Reynolds-averaged Navier Stokes), "
     "although other forms of averaging (such as mass-weighting) are also used "
     "routinely in conjunction with Reynolds averaging.",
     "这类建模方法连同嵌入其中的流动方程一起被称为“RANS”（雷诺平均N-S方程），尽管雷诺平均也经常与其他形式的平均方法（如质量加权）结合使用。"),
    ("We here use the term RANS to denote any ensemble- or time-averaged form of the Navier-Stokes "
     "equations with a turbulence closure.",
     "本文中，RANS 一词泛指任何带有湍流模型封闭的 Navier-Stokes 方程的集合平均或时间平均形式。"),
    # k-epsilon 段落
    ("By far the most commonly-used model in the RANS category is the k-epsilon model.",
     "在 RANS 类模型中，迄今应用最广泛的模型是 k-epsilon 模型。"),
    ("Many weaknesses of the k-epsilon model have been documented in the literature over the "
     "last few decades and as a result, various modifications have been suggested.",
     "过去几十年间，文献中记载了 k-epsilon 模型的诸多缺陷，并因此提出了多种改进方案。"),
    ("Two such improvements, incorporated into CFD++, are the realizable k-epsilon "
     "model and the non-linear k-epsilon model, which introduces many of the advantages "
     "of full Reynolds-stress transport models, but without the associated cost.",
     "CFD++ 中纳入了两项此类改进：可实现 k-epsilon 模型和非线性 k-epsilon 模型。后者引入了完整雷诺应力输运模型的许多优点，但无需额外的计算代价。"),
    ("The realizable variant accounts for certain known physical properties of the "
     "stress tensor by introducing a bound on the magnitude of the predicted tensor "
     "components, which improves predictive accuracy and has a beneficial "
     "effect on stability.",
     "可实现版本通过引入预测张量分量幅值的约束来考虑应力张量的某些已知物理性质，从而提高了预测精度并有助于提升数值稳定性。"),
    ("It should also be noted, that in previous "
     "versions of CFD++, the realizable k-epsilon model was known only as "
     "the k-epsilon model.",
     "还需指出，在早期版本的 CFD++ 中，可实现 k-epsilon 模型仅被称为 k-epsilon 模型。"),
    ("This was a difference in name only, for the "
     "k-epsilon model has always been realizable.",
     "这只是名称上的差异，因为 k-epsilon 模型始终是可实现的。"),
    ("It is also important to note that all models in CFD++ have some form of realizability built into "
     "them.",
     "同样重要的是，CFD++ 中的所有模型都内置了某种形式的可实现性约束。"),
    ("The non-linear variant provides a similar enforcement of realizability, but "
     "goes further by representing the stress tensor using a more general expansion "
     "of mean strain and vorticity tensors.",
     "非线性版本提供了类似的可实现性约束，并通过使用更通用的平均应变率张量和涡量张量展开来表示应力张量，从而更进一步。"),
    ("Either model should provide improved "
     "predictions, relative to conventional k-epsilon models.",
     "与标准 k-epsilon 模型相比，这两种模型均应能提供更优的预测结果。"),
    ("The following is a complete list of choices available with the RANS category of models in CFD++:",
     "以下是 CFD++ 中 RANS 类模型的所有可选模型完整列表："),
    # 模型描述
    ("Solves directly for the undamped eddy viscosity (Rt).",
     "直接求解未衰减的涡粘性（Rt）。"),
    ("Solves a transport equation for an undamped eddy viscosity, nu_tilde.",
     "求解未衰减涡粘性的输运方程，nu_tilde。"),
    ("Solves transport equations for the "
     "turbulence kinetic energy (k) and its dissipation rate (epsilon).",
     "求解湍动能（k）及其耗散率（epsilon）的输运方程。"),
    ("Solves transport equations for the "
     "turbulence kinetic energy (k) and the turbulence length scale (l).",
     "求解湍动能（k）和湍流长度尺度（l）的输运方程。"),
    ("This model has non-linear terms which account for normal-stress anisotropy, "
     "swirl and streamline curvature effects.",
     "该模型包含非线性项，可考虑正应力各向异性、旋流和流线曲率效应。"),
    ("This model behaves similar to the realizable k-e model for wall-bounded flows but improves free-shear flow prediction.",
     "该模型对壁面约束流动的行为与可实现 k-e 模型相似，但改善了自由剪切流的预测。"),
    ("Solves the transport equations for the "
     "turbulence kinetic energy, k, and for the turbulence inverse time-scale, "
     "omega.",
     "求解湍动能 k 和湍流逆时间尺度 ω 的输运方程。"),
    ("The latter is modified such that it blends omega in near-wall "
     "regions with epsilon (the turbulence dissipation rate) further away from "
     "walls and in wake regions.",
     "后者经过修正，使其在近壁区域与 epsilon（湍流耗散率）混合，在远离壁面和尾流区域则单独使用 ω。"),
    ("Solves transport equations for undamped eddy viscosity and for intermittency.",
     "求解未衰减涡粘性和间歇性的输运方程。"),
    ("Solves transport equations for the turbulence kinetic energy (k), its dissipation rate (epsilon), "
     "and the undamped eddy viscosity (Rt) in a manner which accounts for "
     "non-equilibrium conditions and avoids freestream turbulence decay under "
     "shear-free flow conditions.",
     "以考虑非平衡条件的方式求解湍动能（k）及其耗散率（epsilon）和未衰减涡粘性（Rt）的输运方程，同时避免剪切自由流条件下自由流湍流衰减的问题。"),
    ("Enables improved prediction of some flows involving back-flow regions.",
     "能够改善涉及回流区域的某些流动预测精度。"),
    ("Solves transport equations for k,ω, intermittency and transition momentum thickness Reynolds number.",
     "求解 k、ω、间歇性以及转捩动量厚度雷诺数的输运方程。"),
    ("Solves transport equations for the Reynolds-stress tensor and the homogeneous dissipation rate of the "
     "mass-averaged turbulent kinetic energy.",
     "求解雷诺应力张量和质量平均湍动能的均匀耗散率的输运方程。"),
    ("It is recommended for three dimensional flows, swirling flows, and flows with mass separation.",
     "推荐用于三维流动、旋流和有质量分离的流动。"),
    ("It is strongly recommended that this model be used as a low Reynolds-number (solve-to-wall) model, with y<sup>+</sup> &le; 0.5 everywhere.",
     "强烈建议将该模型用作低雷诺数（求解至壁面）模型，且需保证全场 y<sup>+</sup> ≤ 0.5。"),
    ("Solves transport equations for turbulence kinetic energy (k) and turbulence inverse time-scale(&omega;).",
     "求解湍动能（k）和湍流逆时间尺度（ω）的输运方程。"),
    ("Solves transport equations for turbulence kinetic energy (k) and &omega; using non-liner stress/strain relations.",
     "使用非线性应力/应变关系求解湍动能（k）和 ω 的输运方程。"),
    # 壁函数段落
    ("All the above models can be used together with a sophisticated "
     "<A HREF=\"wallfunctions.html\">wall function treatment</A> if coarse grids are "
     "placed adjacent to walls.",
     "如果壁面附近放置了粗网格，上述所有模型均可配合精细的<A HREF=\"wallfunctions.html\">壁函数处理</A>一起使用。"),
    ("The three default models in CFD++ are the one-equation "
     "Rt model, the two-equation k-epsilon model and the three equation k-epsilon-Rt closure.",
     "CFD++ 的三个默认模型是：单方程 Rt 模型、两方程 k-epsilon 模型和三方程 k-epsilon-Rt 封闭模型。"),
    ("The other models (except for the k-&omega; models) become available "
     "for selection by checking the <B>More Models</B> button in the "
     "<A HREF=\"eqset.html\">equation-set entry panel</A>.",
     "其他模型（除 k-ω 模型外）可通过在<A HREF=\"eqset.html\">方程组设置面板</A>中勾选<B>更多模型</B>按钮来启用选择。"),
    ("Several models "
     "are described in more detail below.",
     "以下将对部分模型做更详细的说明。"),
    # Goldberg 模型
    ("This model is based on a single equation for the undamped "
     "eddy viscosity, Rt, given in its most general form as:",
     "该模型基于未衰减涡粘性 Rt 的单方程，其最一般形式为："),
    ("in which the usual linear Boussinesq assumption is adopted for the "
     "Reynolds-stresses.",
     "其中，雷诺应力采用标准的线性 Boussinesq 假设。"),
    ("Thus, the rate of turbulence production becomes:",
     "因此，湍流产生率变为："),
    ("and the extra diffusion term is modeled as:",
     "附加扩散项的模型为："),
    ("in which ",
     "其中"),
    ("where <img src=\"gifs/1eqdestrt3.gif\" alt=\"$\\vec {U}_g$\" align=\"middle\" border=\"0\" > is the local grid velocity.",
     "<img src=\"gifs/1eqdestrt3.gif\" alt=\"$\\vec {U}_g$\" align=\"middle\" border=\"0\" > 为当地网格速度。"),
    ("The eddy-viscosity is defined as:",
     "涡粘性定义为："),
    ("with the low Reynolds number damping function defined as:",
     "低雷诺数阻尼函数定义为："),
    ("in which ",
     "其中"),
    ("The remaining model terms and constants are:",
     "其余模型项和常数为："),
    ("This model can be used in conjunction with <A HREF=\"wallfunctions.html\">wall "
     "functions</A> or integrated directly to the wall; in the latter case Rt is simply set "
     "to zero at solid surfaces.",
     "该模型可配合<A HREF=\"wallfunctions.html\">壁函数</A>使用，也可直接积分至壁面；在后一种情况下，Rt 在固体表面直接设为零。"),
    ("NOTE: This model should not be used when rotating/translating walls are present.",
     "注意：当存在旋转/平移壁面时，不应使用此模型。"),
    ("Equilibrium Wall Function",
     "平衡壁函数"),
    ("In the R<SUB>t</SUB> model's transport equation (1) the second term on the RHS is the (production-destruction) term which is modified at the off-wall centroids as explained below. ",
     "在 R<SUB>t</SUB> 模型的输运方程（1）中，右端第二项为（生成-耗散）项，其在壁面外重心处的修正如下所述。"),
    ("Under equilibrium conditions, generation and destruction of turbulence kinetic energy are of equal magnitude and opposite sign, "
     "<IMG ALIGN=\"MIDDLE\" BORDER=\"0\" SRC=\"gifs/1eqmodel_img1.gif\" ALT=\"$P_k=\\varepsilon$\">.",
     "在平衡条件下，湍动能的生成与耗散大小相等、符号相反，"
     "<IMG ALIGN=\"MIDDLE\" BORDER=\"0\" SRC=\"gifs/1eqmodel_img1.gif\" ALT=\"$P_k=\\varepsilon$\">。"),
    ("Where the friction speed can be extracted from the y<SUP>+</SUP> level as",
     "其中摩阻速度可由 y<SUP>+</SUP> 层级导出"),
    ("The logarithmic law-of-the-wall reads",
     "对数律壁面定律如下"),
]


# ========== 翻译函数 ==========
def translate_with_dict(content: str) -> str:
    """字典模式：使用已翻译的标题与段落做字面替换。"""
    result = content
    for en, cn in TITLE_TRANSLATIONS.items():
        result = result.replace(en, cn)
    for en, cn in PARAGRAPH_TRANSLATIONS:
        result = result.replace(en, cn)
    return result


def chunk_html(content: str, max_chars: int = LLM_CHUNK_MAX_CHARS) -> list:
    """按 <P, <LI, <H 标签分块,每块约 max_chars 字符。"""
    paragraphs = re.split(r'(?=<[A-Za-z])', content)
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += para
        else:
            if current.strip():
                chunks.append(current)
            current = para
    if current.strip():
        chunks.append(current)
    return chunks


def translate_with_llm(content: str) -> str:
    """LLM 模式:分块调用 LLM 翻译后拼接。"""
    chunks = chunk_html(content)
    print(f"Split into {len(chunks)} chunks (max {LLM_CHUNK_MAX_CHARS} chars each)")

    translated_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        prompt = f"""You are a professional CFD (Computational Fluid Dynamics) technical translator.
Translate the following HTML content to Chinese. Rules:
1. Preserve ALL HTML tags and attributes exactly as-is
2. Preserve all image src references, href links, and other attributes
3. Translate text content only (between tags) to Chinese
4. Technical terms: keep English for model names (k-epsilon, RANS, LES, SST, SA), translate others
5. Use accurate CFD terminology in Chinese
6. Output only the translated HTML, no explanations

Translate this HTML chunk:
---HTML---
{chunk}
---END HTML---"""
        try:
            result = subprocess.run(
                ['py', '-3', LLM_SCRIPT,
                 '--model', LLM_MODEL,
                 '--max-tokens', str(LLM_MAX_TOKENS),
                 '--prompt', prompt],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr[:200]}")
                translated_chunks.append(chunk)  # fallback: 保留原文
            else:
                translated_chunks.append(result.stdout.strip())
                print(f"  Done ({len(result.stdout.strip())} chars)")
        except subprocess.TimeoutExpired:
            print(f"  ERROR: LLM call timeout")
            translated_chunks.append(chunk)
        except Exception as e:
            print(f"  ERROR: {e}")
            translated_chunks.append(chunk)

    return "\n".join(translated_chunks)


# ========== 主流程 ==========
def main():
    parser = argparse.ArgumentParser(
        description="翻译 turb.html 到中文 (默认字典模式, --llm 切换 LLM 模式)"
    )
    parser.add_argument(
        "--llm", action="store_true",
        help="使用 LLM 分块翻译模式(默认: 字典模式,基于已翻译的标题/段落)"
    )
    parser.add_argument(
        "--input", default=INPUT_FILE,
        help=f"输入 HTML (默认: {INPUT_FILE})"
    )
    parser.add_argument(
        "--output", default=OUTPUT_FILE,
        help=f"输出 HTML (默认: {OUTPUT_FILE})"
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: 输入文件不存在: {args.input}", file=sys.stderr)
        return 1

    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"Read {len(content)} chars from {args.input}")

    if args.llm:
        result = translate_with_llm(content)
    else:
        result = translate_with_dict(content)
        print(f"Applied {len(TITLE_TRANSLATIONS)} title translations and "
              f"{len(PARAGRAPH_TRANSLATIONS)} paragraph translations")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"Written {len(result)} chars to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
