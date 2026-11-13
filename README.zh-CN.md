<div align="center">

# repro-score

**别人能用你的代码复现你的论文吗？** 给科研代码仓库按项打分（满分 100），每一项都给出据以判断的文件与行号、以及该补什么——只读文件，不运行任何代码。

<a href="https://github.com/zch6a/repro-score/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/zch6a/repro-score/actions/workflows/ci.yml/badge.svg"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
<img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-2ea44f">
<a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>

[English](README.md) · **简体中文**

</div>

---

Papers with Code 分析了 200 多个机器学习仓库，总结出可复现仓库的共同点：依赖、训练代码、评测代码、训练好的模型，以及带结果表和对应命令的 README（ML Code Completeness Checklist）。各会议的论文清单也问同样的问题，外加算力。repro-score 逐项检查，用在发布代码之前，或者动手复现别人的论文之前。

```bash
uvx --from git+https://github.com/zch6a/repro-score repro-score path/to/repo
```

输出示例见[英文 README](README.md)（对虚构仓库 [examples/paper-code](examples/paper-code) 的运行结果）。`--brief` 省略证据，`--markdown` 输出表格（用于 PR 或 CI 摘要），`--json` 输出完整报告，`--badge score.svg` 生成徽章，`--min-score 60` 低于 60 分时退出码为 1。

## 检查什么

- **依赖（20）**：依赖文件（只在 README 的 `pip install` 里列出的包算一部分）、版本是否锁定（锁文件，或 80% 以上用 `==`）、Python 版本、Dockerfile 或 conda 环境。
- **说明（20）**：README、安装命令、运行代码的命令（命令里的脚本是否真的在仓库里）、结果表。
- **训练与评测代码（15）**：训练脚本、评测脚本（单元测试不算）、写在配置文件或命令行默认值里的超参数。
- **模型与数据（15）**：训练好的模型的下载链接或加载代码；每个数据集从哪里来。
- **随机性（10）**：代码里设置的随机种子；GPU 确定性设置。
- **算力（5）**：用的什么 GPU/TPU；要跑多久、多少显存。
- **许可证与引用（10）**：按文本识别许可证；CITATION.cff 或 BibTeX。
- **Notebook（5）**：保存时带输出、按顺序从头运行过。

不适用的项（没有 notebook、没有代码）不计入总分。前五部分即 Papers with Code 的清单，算力一项来自 NeurIPS 论文清单。

## 在 CI 里用：GitHub Action

```yaml
- uses: zch6a/repro-score@v0
  with:
    min-score: 60
```

报告写入作业摘要，分数是该步骤的 `score` 输出；只读取仓库，不运行其中的任何代码。

## 局限

- 只读不跑：README 写的脚本存在，也可能跑不通；链接不会去访问，可能已失效。分数说明仓库给了读者什么，不保证结果能复现。
- 对 Python 项目最熟；R、Julia 等语言部分支持。
- 部分判断依据文字（脚本的名字、链接附近的词），名为 `run.py` 的训练脚本若 README 命令没说明，就不会被认作训练代码。

## 许可证

MIT。所依据的清单来自 Papers with Code（MIT 许可）。
