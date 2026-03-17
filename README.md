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
  --activity-csv /path/to/activity.csv
```

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
    "strategy": "multievolve"
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

当前保留了对旧三步流程的自动探测：

- `scripts/process/process_data.py`
- `scripts/plm/extract_embeddings.py`
- `scripts/exp/run_evolvepro.py`

如果你的 EvolvePro 实际入口不同，请直接配置 `evolvepro.command` 或 `EVOLVE_AGENT_EVOLVEPRO_COMMAND_JSON`。

## 测试

```bash
pytest -q
```

## 引用

- Foldseek Agent: `D:\foldseek-agent`
- EvolvePro: <https://github.com/mat10d/EvolvePro>
- MULTI-evolve: <https://github.com/ArcInstitute/MULTI-evolve>
