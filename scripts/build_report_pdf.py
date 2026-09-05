"""Typeset the final report as a PDF with XeLaTeX.

Converts report/final-report.md to LaTeX and compiles it. Kept deliberately
small and explicit rather than pulling in a general Markdown-to-LaTeX
dependency: the report uses a narrow subset of Markdown (headings, paragraphs,
tables, inline code, bold) and handling exactly that subset is more predictable
than configuring a general converter.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "report" / "final-report.md"
BUILD = REPO / "report" / "build"

PREAMBLE = r"""
\documentclass[11pt,a4paper]{article}
\usepackage{fontspec}
\usepackage[margin=2.5cm]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{microtype}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage[hidelinks]{hyperref}
\usepackage{parskip}

\setmainfont{Times New Roman}[Ligatures=TeX]
\newfontfamily\codefont{Consolas}[Scale=0.92]
\let\oldtexttt\texttt
\renewcommand{\texttt}[1]{{\codefont #1}}

\titleformat{\section}{\Large\bfseries}{\thesection.}{0.6em}{}
\titleformat{\subsection}{\large\bfseries}{\thesubsection}{0.6em}{}
\titlespacing*{\section}{0pt}{1.4em}{0.6em}

\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small Sage, Final Project Report}
\fancyhead[R]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}

\setlength{\emergencystretch}{3em}
\hyphenpenalty=1000

\begin{document}
"""

END_DOC = "\n" + chr(92) + "end{document}\n"


def escape(text: str) -> str:
    """Escape LaTeX specials, leaving already-converted markup alone."""
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}")]:
        text = text.replace(a, b)
    return text


def inline(text: str) -> str:
    """Convert inline markdown to LaTeX, escaping the rest."""
    parts: list[str] = []
    for i, chunk in enumerate(re.split(r"(`[^`]+`)", text)):
        if i % 2:                       # inside backticks: code, escape then wrap
            parts.append(r"\texttt{" + escape(chunk[1:-1]) + "}")
        else:
            safe = escape(chunk)
            safe = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", safe)
            safe = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\emph{\1}", safe)
            safe = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\\href{\2}{\1}", safe)
            parts.append(safe)
    return "".join(parts)


def convert(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped == "---":
            out.append("")
            i += 1
            continue

        # Tables
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                cols = len(rows[0])
                out.append(r"\begin{center}")
                out.append(r"\begin{tabular}{" + "l" * cols + "}")
                out.append(r"\toprule")
                out.append(" & ".join(inline(c) for c in rows[0]) + r" \\")
                out.append(r"\midrule")
                for row in rows[1:]:
                    padded = row + [""] * (cols - len(row))
                    out.append(" & ".join(inline(c) for c in padded[:cols]) + r" \\")
                out.append(r"\bottomrule")
                out.append(r"\end{tabular}")
                out.append(r"\end{center}")
            continue

        # Headings
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            # Strip the chapter number only from chapter headings, which LaTeX
            # numbers itself. Subsection numbers like "4.7" are part of the
            # title text and must survive, or "4.7 Test suite" renders as "7".
            if level == 2:
                title = re.sub(r"^\d+\.\s*", "", title)
            if level == 1:
                out.append(r"\begin{center}{\LARGE\bfseries " + inline(title) + r"}\end{center}")
            elif level == 2:
                out.append(r"\section{" + inline(title) + "}")
            elif level == 3:
                out.append(r"\subsection*{" + inline(title) + "}")
            else:
                out.append(r"\subsubsection*{" + inline(title) + "}")
            i += 1
            continue

        # Bullet lists
        if re.match(r"^[-*]\s+", stripped):
            out.append(r"\begin{itemize}\setlength\itemsep{0.2em}")
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[i])
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() \
                        and not re.match(r"^\s*[-*]\s+", lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                out.append(r"\item " + inline(item))
            out.append(r"\end{itemize}")
            continue

        # Paragraph
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(
                ("#", "|", "-", "*", "---")):
            para.append(lines[i].strip())
            i += 1
        out.append(inline(" ".join(para)))
        out.append("")

    return "\n".join(out)


def main() -> None:
    if not SOURCE.exists():
        print(f"FAIL: {SOURCE} does not exist")
        sys.exit(1)
    if not shutil.which("xelatex"):
        print("FAIL: xelatex not found on PATH")
        sys.exit(1)

    BUILD.mkdir(parents=True, exist_ok=True)
    tex = PREAMBLE + convert(SOURCE.read_text(encoding="utf-8")) + END_DOC
    tex_path = BUILD / "final-report.tex"
    tex_path.write_text(tex, encoding="utf-8")

    for run in (1, 2):   # twice, so the page numbering settles
        proc = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory", str(BUILD), str(tex_path)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=600,
        )
        if proc.returncode != 0:
            tail = (proc.stdout or "")[-1800:]
            print(f"FAIL: xelatex run {run} failed\n{tail}")
            sys.exit(1)

    pdf = BUILD / "final-report.pdf"
    if not pdf.exists():
        print("FAIL: no PDF produced")
        sys.exit(1)
    print(f"built {pdf.relative_to(REPO)} ({pdf.stat().st_size:,} bytes)")
    print("PDF BUILD PASSED")


if __name__ == "__main__":
    main()
