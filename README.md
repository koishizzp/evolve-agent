# Evolve Agent

`evolve-agent` 是一个面向蛋白质定向进化场景的部署型代理，参考 `D:\foldseek-agent` 的结构整理而成，目标不是只做一个 Python 库，而是提供：

- 基于 `.env` / YAML 的环境感知配置
- EvolvePro 与 MULTI-evolve 的统一执行入口
- OpenAI 兼容 LLM 规划与结果解释
- FastAPI 服务、浏览器工作台、上传接口
- `start_all.sh` / `stop_all.sh` / `status_all.sh` 这类服务器运维脚本

当前默认针对你的服务器布局预设：

```yaml
evolvepro_root: /mnt/disk3/tio_nekton4/EvolvePro
multievolve_root: /mnt/disk3/tio_nekton4/MULTI-evolve
multievolve_model_dir: /mnt/disk3/tio_nekton4/MULTI-evolve/models
```

## 目录结构

```text
api/
  main.py
  chat_ui.html
config/
  config.yaml
evolve_agent/
  agent.py
  settings.py
  service.py
  chat.py
  reasoner.py
  parser/
  planner/
  tools/
main.py
start_agent.sh
start_all.sh
stop_all.sh
status_all.sh
restart.sh
smoke_test.sh
```

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果你是直接在服务器上运行，建议先复制环境变量模板：

```bash
cp .env.example .env
```

## LLM 配置

这里不再绑定 `Anthropic`。和 `foldseek-agent` 一样，直接复用 OpenAI 兼容变量：

```bash
OPENAI_BASE_URL=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

如果不配置 LLM，代理仍可使用启发式规划兜底。

## 配置说明

默认配置文件是 [config/config.yaml](/D:/evolve-agent/config/config.yaml)。

重点字段：

- `evolvepro_root`: EvolvePro 根目录
- `multievolve_root`: MULTI-evolve 根目录
- `multievolve_model_dir`: MULTI-evolve 模型目录
- `default_strategy`: 默认策略，通常为 `multievolve`
- `evolvepro.command`: 可选，显式指定 EvolvePro 命令模板
- `evolvepro.process_script` / `evolvepro.plm_script` / `evolvepro.exp_script`: 可选，指定官方 EvolvePro 脚本布局下的三个步骤
- `evolvepro.result_glob`: 可选，官方 EvolvePro 脚本把结果写回仓库目录时，用于定位结果 CSV
- `evolvepro.params`: 可选，给 EvolvePro 预置默认参数；CLI / API 传入的 `params` 会覆盖这些默认值
- `multievolve.train_command`: 可选，显式指定 MULTI-evolve 训练命令模板
- `multievolve.propose_command`: 可选，显式指定 MULTI-evolve 推理命令模板

命令模板支持字符串占位，例如：

```json
["conda","run","-n","evolvepro","python","{root}/some_script.py","--fasta","{fasta_path}","--output","{output_csv}"]
```

可通过 `.env` 中的以下变量覆盖：

```bash
EVOLVE_AGENT_EVOLVEPRO_COMMAND_JSON=[...]
EVOLVE_AGENT_MULTIEVOLVE_TRAIN_COMMAND_JSON=[...]
EVOLVE_AGENT_MULTIEVOLVE_PROPOSE_COMMAND_JSON=[...]
EVOLVE_AGENT_MULTIEVOLVE_CHECKPOINT_PATH=/path/to/checkpoint
```

## CLI 用法

自动规划：

```bash
python main.py run examples/example_input.fasta \
  --task "优化这个蛋白的活性，优先考虑冷启动探索"
```

强制走 MULTI-evolve：

```bash
python main.py multievolve examples/example_input.fasta \
  --task "给出多突变候选"
```

强制走 EvolvePro：

```bash
python main.py evolvepro examples/example_input.fasta \
  --task "基于已有实验数据继续优化" \
  --activity-csv /path/to/activity.csv \
  --params-json @examples/evolvepro_params/bxb1.json
```

如果你已经把这些值写进 [config/config.yaml](/D:/evolve-agent/config/config.yaml)，也可以不传 `--params-json`。

查看状态：

```bash
python main.py status
python main.py list-tools
```

## API 用法

启动：

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8110
```

或者：

```bash
./start_all.sh
```

健康检查：

```bash
curl http://127.0.0.1:8110/health
curl http://127.0.0.1:8110/ui/status
curl http://127.0.0.1:8110/evolve/tools
```

直接执行：

```bash
curl -X POST http://127.0.0.1:8110/run_evolution \
  -H "Content-Type: application/json" \
  -d '{
    "fasta_path": "/path/to/query.fasta",
    "task": "优化这个蛋白的活性",
    "strategy": "evolvepro",
    "activity_csv_path": "/path/to/activity.csv",
    "params": {
      "protein_name": "Bxb1",
      "system_name": "bxb1",
      "embeddings_type": "esm2_15B"
    }
  }'
```

OpenAI 兼容聊天：

```bash
curl -X POST http://127.0.0.1:8110/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "evolve-agent",
    "messages": [
      {
        "role": "user",
        "content": "请用 /path/to/query.fasta 做一次冷启动优化"
      }
    ]
  }'
```

上传文件：

```bash
curl -X POST http://127.0.0.1:8110/ui/upload \
  -F "file=@/local/path/query.fasta"
```

## 浏览器工作台

服务启动后，直接访问：

```text
http://服务器IP:8110/
```

页面包含：

- `LLM Chat`: 用自然语言驱动规划与执行
- `Direct Runner`: 直接填写 FASTA / CSV / strategy 执行
- `Upload + Status`: 上传文件并查看服务状态

## MULTI-evolve 说明

当前默认封装优先尝试官方常见脚本：

- `p1_train.py`
- `p2_propose.py`

如果检测不到这些脚本，就会退回到显式命令模板配置，不再像旧仓库那样写死一个很可能不存在的 `run_multievolve.py`。

注意：

- 如果你没有 `activity_csv_path`，且没有配置已有 `checkpoint_path`，默认的 `p2_propose.py` 流程无法直接运行。
- 这时应在 `.env` 或 `config.yaml` 中补 `EVOLVE_AGENT_MULTIEVOLVE_CHECKPOINT_PATH`，或者提供自定义 `multievolve.propose_command`。

## EvolvePro 说明

当前 EvolvePro 封装的优先级如下：

1. 如果配置了 `evolvepro.command`，直接按显式命令模板执行。
2. 如果仓库里仍然存在旧三步流程，则兼容：
   - `scripts/process/process_data.py`
   - `scripts/plm/extract_embeddings.py`
   - `scripts/exp/run_evolvepro.py`
3. 如果检测到官方 EvolvePro 风格的 `scripts/` 目录，则自动尝试：
   - `scripts/process/exp_process.py` 或 `scripts/process/dms_process.py`
   - `scripts/plm/{embeddings_type}_exp.sh`，或显式指定 `evolvepro.plm_script`
   - `scripts/exp/{system_name}.py`，或显式指定 `evolvepro.exp_script`

注意：

- 官方 EvolvePro 的 `scripts/plm/*.sh` 和 `scripts/exp/*.py` 更像预配置实验脚本，不是通用 CLI；自动兼容时通常至少需要传 `protein_name`、`system_name`、`embeddings_type`。
- 你给出的目录里 `scripts/exp` 当前对应 `bxb1.py`、`mlv.py`、`t7_pol.py`；仓库内已补了现成模板：
  - [examples/evolvepro_params/bxb1.json](/D:/evolve-agent/examples/evolvepro_params/bxb1.json)
  - [examples/evolvepro_params/mlv.json](/D:/evolve-agent/examples/evolvepro_params/mlv.json)
  - [examples/evolvepro_params/t7_pol.json](/D:/evolve-agent/examples/evolvepro_params/t7_pol.json)
- 从你贴过来的 `bxb1.py`、`mlv.py`、`t7_pol.py` 看，脚本本身不使用 `assay_name`；它们直接读取 `data/exp/exp_data/<protein>/rounds` 和 `data/exp/exp_data/<protein>/esm`。
- 因此在你当前这套目录里，可以先把 `assay_name` 当成“不需要填”。只有当你本地的 `scripts/process/exp_process.py` 明确报缺少 `--assay_name` 时，再额外传它。
- 有些 EvolvePro fork 里的 `scripts/process/exp_process.py` 不是 CLI，而是直接运行的固定脚本。如果脚本里没有 `argparse` / `sys.argv`，代理会自动改成无参数执行，并预建 `output/exp`、`output/exp_results`、`data/exp/wt_fasta`。
- 官方脚本常把结果写到 `output/` 而不是本代理默认的 `results/`，所以默认配置已改成 `evolvepro.result_glob: output/**/*.csv`。如果你的 fork 输出位置不同，再通过 `params.result_file`、`params.result_glob` 或 `evolvepro.result_glob` 覆盖。
- 如果你的 EvolvePro 是自定义 fork，最稳妥的方式仍然是直接配置 `evolvepro.command` 或 `EVOLVE_AGENT_EVOLVEPRO_COMMAND_JSON`。

## 测试

```bash
pytest -q
```

## 引用

- Foldseek Agent: `D:\foldseek-agent`
- EvolvePro: <https://github.com/mat10d/EvolvePro>
- MULTI-evolve: <https://github.com/ArcInstitute/MULTI-evolve>
