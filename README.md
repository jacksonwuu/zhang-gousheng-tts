# zhang-gousheng-tts

把一份文档，变成**你自己的声音 + 张狗剩式快节奏、短停顿、强动态**的中文讲解音频。
底层使用 [IndexTTS 2.5](https://github.com/index-tts/index-tts)。

[English](README.en.md) | 中文

![License](https://img.shields.io/github/license/jacksonwuu/zhang-gousheng-tts)
![Python](https://img.shields.io/badge/python-3.10%20--%203.11-blue)
![IndexTTS](https://img.shields.io/badge/IndexTTS-2.5-orange)

> **这不是张狗剩的音色克隆。**
> 只复刻节奏、停顿、动态和语气。音色必须是你本人或已获授权的声音；风格参考只负责
> 情绪和韵律。不要用它冒充真实人物，也不要生成欺骗性内容。

## 给用户：只需要说一句话

把文档发给 agent，然后说：

> 用我的声音，把这份文档做成张狗剩那种节奏的讲解音频。

第一次使用时，agent 只会再向你要两样东西：

1. 一段 10–60 秒的本人说话样本，视频或音频都行；
2. 对模型下载的确认，因为 IndexTTS 大约占 8 GB。

之后每次只需要给文档。agent 会自己完成解析、分段、生成、拼接、转码，最后把
WAV/MP3 和时长交给你。你不需要执行任何命令，也不需要安装 Python 包。

### 支持的文件

`txt`、`md`、`rst`、`csv`、`json`、`docx`、旧版 `doc`、`rtf`、文本型 `pdf`、
`html`、`epub`、`srt`、`vtt`。扫描版 PDF 需要先 OCR。

### 你会拿到什么

- `<文档名>.zhang-gousheng.wav`：44.1 kHz / 24-bit
- `<文档名>.zhang-gousheng.mp3`：192 kbps
- `<文档名>.zhang-gousheng.json`：时长、参数、分段和完整复现信息

默认输出在文档旁边；如果目录不可写，会落到 `~/Documents/zhang-gousheng-tts/`，
再不可写则落到系统临时目录。最终路径以报告里的绝对路径为准。

## 这适合什么场景

- 长文章、公众号稿、课程讲稿直接转口播
- 用自己的声音批量做短视频旁白
- 同一篇稿子里，不同段落用不同情绪和语速
- 从旧视频里提取一段干净人声，作为长期音色参考
- 给已有文案快速试听节奏，再决定是否精修

## 给 Agent：一键接入

这个仓库是**通用 skill**，不绑定 Codex。任何能读取 `SKILL.md` 的 agent 都可以
直接使用；只支持 `AGENTS.md` 的 runtime 也有入口。核心只有一个 agent 入口：

```bash
"$SKILL_DIR/scripts/zhang-tts" check
"$SKILL_DIR/scripts/zhang-tts" setup --root "$HOME/index-tts" --download-models --yes
"$SKILL_DIR/scripts/zhang-tts" configure --voice-source "/path/to/user-sample.mov"
"$SKILL_DIR/scripts/zhang-tts" make "/path/to/document.docx"
"$SKILL_DIR/scripts/zhang-tts" say "要读出来的文本"
```

这些命令是给 agent 用的，不要交给最终用户执行。

### 安装到不同 runtime

仓库本身放在哪里都可以，只要 agent 能读到 `SKILL.md`：

```text
Codex:        ~/.codex/skills/zhang-gousheng-tts
Claude Code:  ~/.claude/skills/zhang-gousheng-tts
其他 agent:   任意目录；让 agent 先读 SKILL.md 或 AGENTS.md
```

用软链接可以保持更新：

```bash
git clone https://github.com/jacksonwuu/zhang-gousheng-tts.git \
  "$HOME/code/zhang-gousheng-tts"
ln -sfn "$HOME/code/zhang-gousheng-tts" \
  "$HOME/.codex/skills/zhang-gousheng-tts"   # Codex
ln -sfn "$HOME/code/zhang-gousheng-tts" \
  "$HOME/.claude/skills/zhang-gousheng-tts"  # Claude Code
```

### 首次安装

IndexTTS 的资源成本必须先确认：

| 项目 | 需求 |
|---|---:|
| IndexTTS-2.5 模型 | 约 8 GB |
| Python 环境与缓存 | 约 2–4 GB |
| 安装期间可用磁盘 | 至少 20 GB |
| 内存 | 16 GB 起步，32 GB 以上更稳 |
| 30 秒音频的 CPU 生成时间 | 通常数分钟，约 5–8 倍实时 |

确认后再运行安装。`setup` 会在缺少 checkout 时自动 clone IndexTTS，用 `uv`
安装 WebUI 依赖，下载模型，然后做一次深度检查：

```bash
"$SKILL_DIR/scripts/zhang-tts" setup \
  --root "$HOME/index-tts" \
  --download-models \
  --yes
```

macOS 只安装 WebUI 依赖。不要使用 `uv sync --all-extras`，它可能拉取 NVIDIA
CUDA 包。模型下载支持断点续传；网络失败后重跑同一条命令，不要先删
`checkpoints/`。

### 环境变量

| 变量 | 用途 |
|---|---|
| `INDEXTTS_ROOT` | IndexTTS 仓库路径 |
| `ZHANG_PROFILE` | 声音 profile，默认 `~/.config/zhang-gousheng-tts/profile.json` |
| `ZHANG_OUTPUT_DIR` | 默认输出目录 |
| `FFMPEG_BIN` | 自定义 ffmpeg |
| `UV_CACHE_DIR` | uv 缓存 |
| `MPLCONFIGDIR` | Matplotlib 缓存 |
| `NUMBA_CACHE_DIR` | Numba 编译缓存 |

在沙箱里运行时，建议把三个缓存都指向 `/tmp`，否则可能遇到 `uv` 权限错误或
`cannot cache function ... no locator available`。

## 进阶：同一篇稿子里换情绪和语速

在文档里单独放一行指令，后面的段落会继承它，直到出现下一条：

```text
[[emo_alpha=0.62 duration_factor=0.98]]
这一段更冲，语速快一点。

[[emo_alpha=0.45 duration_factor=1.18]]
这一段收稳，停顿放长一点。
```

支持：`emo_alpha`、`duration_factor`（也可写 `speed`）、`temperature`、
`top_p`、`top_k`、`repetition_penalty`。也可以直接给 8 维情绪向量：

```text
[[emo_vector=0.08 0.02 0 0 0 0 0.05 0.65]]
```

顺序是 `happy, angry, sad, afraid, disgusted, melancholic, surprised, calm`。
大多数情况下，先调 `emo_alpha` 和 `duration_factor` 就够了。

## 参数

Profile 会在两条路线中选一条：

| 参数 | 向量路线（默认，无需风格音频） | 参考路线（有授权风格音频） |
|---|---:|---:|
| `emo_alpha` | `0.35` | `0.55` |
| `duration_factor` | `1.08` | `1.10` |
| `temperature` | `0.85` | `0.86` |
| `top_p` | `0.90` | `0.91` |
| `top_k` | `40` | `45` |
| `repetition_penalty` | `8.5` | `8.2` |

通用默认：`max_text_tokens_per_segment=300`、`interval_silence=200`、
`chunk_chars=500`、`pause_ms=250`。

| 症状 | 先调什么 |
|---|---|
| 太像风格参考 | 把 `emo_alpha` 降到 `0.35–0.45` |
| 太平、太客气 | 把 `emo_alpha` 升到 `0.55–0.65` |
| 太快、赶 | 把 `duration_factor` 升到 `1.15–1.25` |
| 太慢、没劲 | 把 `duration_factor` 降到 `0.95–1.05` |
| 发音不稳 | 把 `temperature` 降到 `0.80–0.84` |
| 重复、卡音 | 稍微提高 `repetition_penalty` |
| 长文越读越飘 | 缩短分段，或在句中补标点 |

不要为了贴近目标人物的 F0 去做移调，那会破坏本音。改 `emo_alpha` 重新生成。

## 文本规则

- 一个气口控制在 8–14 个汉字。
- 想强调的词前面加逗号或句号。
- 金句单独成句：`真不是。`
- 多用口语钩子：`完了`、`说白了`、`你记住`。
- 英文缩写可以加发音提示，例如 `<AI|EY2 . AY1>`。

## 批量与维护者命令

多条独立文案用 JSONL manifest，可以一次加载模型、逐条覆盖参数：

```jsonl
{"text":"第一段旁白。","output":"001.wav","emo_alpha":0.55,"duration_factor":1.10}
{"text":"第二段更冲一点。","output":"002.wav","emo_alpha":0.62,"duration_factor":0.98}
```

```bash
cd "$INDEXTTS_ROOT"
uv run --frozen python "$SKILL_DIR/scripts/generate.py" \
  --manifest "/path/to/manifest.jsonl" \
  --voice "$HOME/.config/zhang-gousheng-tts/voice_15s.wav" \
  --emo-vector "[0.08,0.02,0,0,0,0,0.05,0.65]" \
  --output "/path/to/out" \
  --report "/path/to/out/report.json" \
  --continue-on-error
```

有授权风格音频时，把 `--emo-vector` 换成
`--style-reference "/path/to/style_15s.wav"`。两者同时给时，IndexTTS 会优先
使用向量，风格音频不参与。

## 环境检查与测试

```bash
"$SKILL_DIR/scripts/zhang-tts" check

UV_CACHE_DIR=/tmp/uv-cache \
MPLCONFIGDIR=/tmp/mpl-cache \
NUMBA_CACHE_DIR=/tmp/numba-cache \
uv run --project "$INDEXTTS_ROOT" --frozen \
  python -m unittest discover -s "$SKILL_DIR/tests" -v
```

测试覆盖参数范围、批量输出路径安全、文档解析、分段指令、静音/长音频选段和
读音单元统计。

## 隐私与合规

声音样本属于生物特征数据。参考音频、原始文档和生成结果都应保存在本地私有目录，
不要提交到公开仓库。项目的 `.gitignore` 已排除音频、视频、`outputs/`、
`downloads/`、模型和虚拟环境。

- 只克隆你本人或明确授权的声音。
- 不使用本项目冒充真实人物、制造虚假陈述或规避平台规则。
- 公开使用前确认音色和风格参考的使用权。
- 不再需要的参考音频和废弃生成结果应及时删除。

## 项目结构

```text
.
├── SKILL.md                    # 通用 agent 契约
├── AGENTS.md                   # 不支持 skill 的 agent 入口
├── README.md
├── README.en.md
├── scripts/
│   ├── zhang-tts               # 一键入口（agent 调用）
│   ├── check_env.py
│   ├── setup_env.sh
│   ├── configure_profile.py
│   ├── prepare_reference.py
│   ├── make_audio.py
│   ├── generate.py
│   └── analyze_audio.py
├── references/
│   ├── zhang_gousheng.md
│   └── installation.md
├── tests/
└── evals/
```

## 第三方依赖与许可证

本项目只包含 skill 脚本和文档，不包含 IndexTTS 权重、示例视频、用户声音或生成
音频。IndexTTS 及其模型受上游项目自己的许可证约束，请在使用前阅读
[index-tts](https://github.com/index-tts/index-tts) 和
[IndexTTS-2.5](https://huggingface.co/IndexTeam/IndexTTS-2.5) 的许可条款。

本仓库代码和文档使用 MIT License，见 [`LICENSE`](LICENSE)。
