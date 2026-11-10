# zhang-gousheng-tts

用**自己的音色**，配合张狗剩式快节奏、短停顿、强动态的中文新闻解说风格，通过
[IndexTTS 2.5](https://github.com/index-tts/index-tts) 生成讲解音频。

[English](README.en.md) | 中文

![License](https://img.shields.io/github/license/jacksonwuu/zhang-gousheng-tts)
![Python](https://img.shields.io/badge/python-3.10%20--%203.11-blue)
![IndexTTS](https://img.shields.io/badge/IndexTTS-2.5-orange)

> **这不是张狗剩的音色克隆。**
> 本项目只复刻节奏、停顿、动态和语气。`spk_audio_prompt` 必须使用你本人或已获授权
> 的声音；`emo_audio_prompt` 只作为风格参考。不要用它冒充真实人物，也不要生成
> 欺骗性内容。

## 能做什么

- 从视频或音频中提取 5–15 秒干净的人声参考
- 用自己的音色 + 独立的情绪/风格参考生成中文 TTS
- 调节 `emo_alpha`、语速、temperature、top-p/top-k、重复惩罚等参数
- 用 JSONL 批量生成，并为每一行覆盖情绪、语速和情感向量
- 自动记录完整参数、模型版本、输出和失败项，方便复现
- 分析时长、F0、停顿、动态、频谱重心和 LUFS/LRA
- 在安装前检查磁盘、内存、模型完整性和真实推理模块导入

## 重要资源提示

安装或下载模型前必须先得到用户确认：

| 项目 | 需求 |
|---|---:|
| IndexTTS-2.5 模型 | 约 8 GB |
| Python 环境与缓存 | 约 2–4 GB |
| 安装期间可用磁盘 | 至少 20 GB |
| 内存 | 16 GB 起步，32 GB 以上更稳 |
| 30 秒音频的 CPU 生成时间 | 通常数分钟，约 5–8 倍实时 |

`setup_env.sh` 在非交互环境默认拒绝安装。确认磁盘和资源成本后才使用 `--yes`。
脚本还会硬性检查剩余磁盘，低于 20 GB 时直接停止。

## 环境要求

- Python 3.10–3.11
- [uv](https://docs.astral.sh/uv/)
- `ffmpeg` / `ffprobe`
- 一个可用的 IndexTTS 2.5 checkout 和模型
- macOS / Linux / WSL2；Windows 原生环境未实机验证

## 安装 Skill

```bash
git clone https://github.com/jacksonwuu/zhang-gousheng-tts.git \
  "$HOME/code/zhang-gousheng-tts"
mkdir -p "$HOME/.codex/skills"
ln -sfn "$HOME/code/zhang-gousheng-tts" \
  "$HOME/.codex/skills/zhang-gousheng-tts"
```

也可以用普通复制代替软链接，但以后更新时需要重新复制。

## 安装 IndexTTS

```bash
git clone https://github.com/index-tts/index-tts.git "$HOME/index-tts"

export INDEXTTS_ROOT="$HOME/index-tts"
export SKILL_DIR="$HOME/.codex/skills/zhang-gousheng-tts"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl-cache}"
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-/tmp/numba-cache}"

"$SKILL_DIR/scripts/setup_env.sh" \
  --root "$INDEXTTS_ROOT" \
  --download-models \
  --yes
```

macOS 默认只安装 WebUI 依赖：

```text
uv sync --extra webui
```

不要盲目使用 `--all-extras`，它可能拉取 NVIDIA CUDA 包。模型下载支持断点续传；
网络失败后重新执行安装命令即可，不要先删除 `checkpoints/`。

## 环境检查

```bash
"$SKILL_DIR/scripts/setup_env.sh" --check
```

或直接运行：

```bash
python3 "$SKILL_DIR/scripts/check_env.py" --root "$INDEXTTS_ROOT" --deep
```

检查包括：

- Python、`uv`、`ffmpeg`、`ffprobe`
- 模型关键文件及最低合理大小
- `.venv`、可用磁盘、内存
- `IndexTTS2` 推理模块的真实导入

## 快速开始

### 1. 准备你的音色参考

```bash
cd "$INDEXTTS_ROOT"

uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/your-video.mov" \
  --output "outputs/voice_samples/user_voice_15s.wav"
```

优先使用单人、干声、无音乐、无混响的 10–15 秒素材。自动选段只依据响度，
无法可靠识别背景音乐、多人声或混响；遇到这类素材时请试听并用 `--start` 手动指定。

### 2. 准备风格参考

```bash
uv run --frozen python "$SKILL_DIR/scripts/prepare_reference.py" \
  --input "/path/to/authorized-style-source.wav" \
  --output "/tmp/zhang_style_15s.wav"
```

风格参考也必须确认授权。它只控制情绪和韵律，不用于提供音色。

### 3. 生成

```bash
uv run --frozen python "$SKILL_DIR/scripts/generate.py" \
  --text "很多人以为，声音克隆就是把一段录音丢给 AI，然后按下生成，完了。真不是。" \
  --voice "outputs/voice_samples/user_voice_15s.wav" \
  --style-reference "/tmp/zhang_style_15s.wav" \
  --output "outputs/voice_samples/demo.wav" \
  --report "outputs/voice_samples/demo.json"
```

成功后会输出 44.1 kHz / 24-bit WAV。中间 `.raw.wav` 默认删除；调试时使用
`--keep-raw` 保留。JSON 报告会记录模型版本、参考文件、全部参数、输出和失败项。

### 4. 分析结果

```bash
uv run --frozen python "$SKILL_DIR/scripts/analyze_audio.py" \
  "outputs/voice_samples/demo.wav" \
  --text "很多人以为，声音克隆就是把一段录音丢给 AI，然后按下生成，完了。真不是。" \
  --loudnorm
```

可以查看 F0、停顿、动态、频谱重心、读音单元/分钟和 LUFS/LRA。

## 推荐参数

| 参数 | 默认值 | 作用 |
|---|---:|---|
| `emo_alpha` | `0.55` | 风格参考的影响强度 |
| `duration_factor` | `1.10` | 数值越大越慢、越长 |
| `temperature` | `0.86` | 变化量；过高会更不稳定 |
| `top_p` | `0.91` | 采样范围 |
| `top_k` | `45` | 采样候选数 |
| `repetition_penalty` | `8.2` | 抑制重复和卡音 |
| `max_text_tokens_per_segment` | `300` | 单段最大 token 数 |
| `interval_silence` | `200` | 段间静音毫秒数 |

调节顺序通常是：先改文本断句，再调 `duration_factor`，最后微调情绪和采样参数。
不要通过移调强行模仿目标人物音高，那会破坏本人音色。

完整声线档案和调参历史见
[`references/zhang_gousheng.md`](references/zhang_gousheng.md)。

## 批量生成

创建 `manifest.jsonl`：

```jsonl
{"text":"第一段旁白。","output":"001.wav","emo_alpha":0.55,"duration_factor":1.10}
{"text":"第二段更冲一点。","output":"002.wav","emo_alpha":0.62,"duration_factor":0.98}
{"text":"第三段收稳。","output":"003.wav","emo_alpha":0.48,"duration_factor":1.12,"emo_vector":[0.08,0.02,0,0,0,0,0.05,0.65]}
```

生成：

```bash
uv run --frozen python "$SKILL_DIR/scripts/generate.py" \
  --manifest "/path/to/manifest.jsonl" \
  --voice "outputs/voice_samples/user_voice_15s.wav" \
  --style-reference "/tmp/zhang_style_15s.wav" \
  --output "outputs/voice_samples/batch" \
  --continue-on-error
```

模型只加载一次。输出目录会生成 `generation_report.json`，记录每一行的参数和结果。
输出路径被限制在批量目录内，带 `../` 或绝对路径的条目会被拒绝。

## 环境变量

| 变量 | 用途 |
|---|---|
| `INDEXTTS_ROOT` | IndexTTS 仓库路径 |
| `SKILL_DIR` | 本 skill 路径 |
| `ZHANG_STYLE_REFERENCE` | 默认风格参考 WAV |
| `FFMPEG_BIN` | 自定义 ffmpeg 可执行文件 |
| `UV_CACHE_DIR` | uv 缓存目录 |
| `MPLCONFIGDIR` | Matplotlib 缓存目录 |
| `NUMBA_CACHE_DIR` | Numba 编译缓存目录 |

在 Codex、CI 或其他沙箱中，建议把三个缓存都指向 `/tmp`。否则可能遇到
`uv` 权限错误或 `cannot cache function ... no locator available`。

## 隐私与合规

声音样本属于生物特征数据。请把参考音频、生成结果和个人文案保存在本地私有目录，
不要提交到公开仓库。项目的 `.gitignore` 已排除 `outputs/`、`downloads/`、
虚拟环境和 Python 缓存。

- 只克隆你本人或明确授权的声音。
- 不使用本项目冒充真实人物、制造虚假陈述或规避平台规则。
- 公开使用前确认音色和风格参考的使用权。
- 不再需要的参考音频和废弃生成结果应及时删除。

## 测试

```bash
UV_CACHE_DIR=/tmp/uv-cache \
MPLCONFIGDIR=/tmp/mpl-cache \
NUMBA_CACHE_DIR=/tmp/numba-cache \
uv run --project "$INDEXTTS_ROOT" --frozen \
  python -m unittest discover -s "$SKILL_DIR/tests" -v
```

当前测试覆盖参数范围、批量输出路径安全、静音/长音频选段和读音单元统计。

## 项目结构

```text
.
├── SKILL.md
├── README.md
├── README.en.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── scripts/
│   ├── check_env.py
│   ├── setup_env.sh
│   ├── prepare_reference.py
│   ├── generate.py
│   └── analyze_audio.py
├── references/
│   ├── zhang_gousheng.md
│   └── installation.md
├── tests/
│   └── test_scripts.py
└── evals/
    └── evals.json
```

## 第三方依赖与许可证

本项目只包含 skill 脚本和文档，不包含 IndexTTS 权重、示例视频、用户声音或生成音频。
IndexTTS 及其模型受上游项目自己的许可证约束，请在使用前阅读
[index-tts](https://github.com/index-tts/index-tts) 和
[IndexTTS-2.5](https://huggingface.co/IndexTeam/IndexTTS-2.5) 的许可条款。

本仓库代码和文档使用 MIT License，见 [`LICENSE`](LICENSE)。
