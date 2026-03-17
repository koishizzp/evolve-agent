# evolve-agent

## 1) 项目介绍 | Introduction

**中文**：`evolve-agent` 是一个面向蛋白质定向进化的 AI Agent 框架。用户通过自然语言描述优化目标（如提高结合亲和力、增强酶活性）并提供 FASTA 序列，Agent 会自动决策调用 **EvolvePro** 或 **MULTI-evolve**（或串联两者），执行命令、解析输出并生成可读摘要。

**English**: `evolve-agent` is an AI Agent framework for protein directed evolution. Given a natural-language optimization goal and a FASTA sequence, it automatically routes to **EvolvePro**, **MULTI-evolve**, or both, executes workflows, parses outputs, and returns a user-friendly summary.

---

## 2) EvolvePro vs MULTI-evolve 适用场景对比 | Comparison

| 维度 / Aspect | EvolvePro | MULTI-evolve |
|---|---|---|
| 典型场景 | few-shot 主动学习，迭代优化 | 一轮 ML 引导多突变体探索 |
| 数据需求 | 需要少量实验活性数据（每轮 10-16） | 可在无/少量实验数据下启动 |
| 建模特点 | 迭代学习，适合持续回流实验数据 | 蛋白语言模型 + 上位性建模，擅长协同突变 |
| 推荐使用时机 | 已有初始实验数据后精修 | 冷启动或早期探索阶段 |

---

## 3) 安装步骤 | Installation

### 3.1 安装 Python 依赖
```bash
pip install -r requirements.txt
```

### 3.2 安装项目
```bash
pip install -e .
```

### 3.3 Conda 环境准备（示例）
```bash
conda create -n evolvepro python=3.10 -y
conda create -n plm python=3.10 -y
```

并确保服务器上已安装：
- EvolvePro: https://github.com/mat10d/EvolvePro
- MULTI-evolve: https://github.com/ArcInstitute/MULTI-evolve

---

## 4) 配置说明 | Configuration

配置文件：`config/config.yaml`

- `evolvepro_path`: EvolvePro 安装目录（默认 `~/EvolvePro`）
- `multievolve_path`: MULTI-evolve 安装目录
- `conda_env_evolvepro`: EvolvePro 执行环境名
- `conda_env_plm`: PLM embedding 环境名
- `anthropic_api_key`: 从环境变量读取（`${ANTHROPIC_API_KEY}`）
- `model`: 默认 `claude-sonnet-4-20250514`
- `output_dir`: 输出目录（默认 `./outputs`）
- `tmp_dir`: 临时目录（默认 `./tmp`）

---

## 5) 使用示例 | Usage

### CLI 命令
```bash
python scripts/run_agent.py \
  --fasta examples/example_input.fasta \
  --task "优化这个抗体的结合亲和力" \
  --activity-csv data/activity.csv \
  --verbose
```

### 示例输出（节选）
```text
=== evolve-agent summary ===
任务: 优化这个抗体的结合亲和力
策略: evolvepro
推荐 Top 变体: {'sequence': '...', 'mutations': 'A25V', 'score': 1.42}
建议下一步：合成 Top 变体并进行湿实验验证，随后将新数据回流继续优化。
```

---

## 6) 项目结构 | Project Structure

```text
evolve-agent/
├── README.md
├── requirements.txt
├── setup.py
├── config/
│   └── config.yaml
├── evolve_agent/
│   ├── __init__.py
│   ├── agent.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base_tool.py
│   │   ├── evolvepro_tool.py
│   │   └── multievolve_tool.py
│   ├── planner/
│   │   ├── __init__.py
│   │   └── planner.py
│   ├── parser/
│   │   ├── __init__.py
│   │   └── output_parser.py
│   └── utils/
│       ├── __init__.py
│       ├── fasta_utils.py
│       └── logger.py
├── scripts/
│   └── run_agent.py
├── examples/
│   ├── example_input.fasta
│   └── example_run.sh
└── tests/
    ├── test_evolvepro_tool.py
    └── test_multievolve_tool.py
```

---

## 7) 引用信息 | Citation

- foldseek-agent design inspiration: https://github.com/koishizzp/foldseek-agent
- EvolvePro: Matreyek Lab, https://github.com/mat10d/EvolvePro
- MULTI-evolve: Arc Institute, https://github.com/ArcInstitute/MULTI-evolve
