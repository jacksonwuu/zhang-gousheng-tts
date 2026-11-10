# 张狗剩式新闻旁白声线档案

版本：`2026-11-09`
用途：在 IndexTTS 2.5 中复用“张狗剩式”的**节奏、停顿、动态和语气**，搭配使用者自己的参考音色。

> 这不是张狗剩的音色克隆。档案只记录可复现的风格参数；`spk_audio_prompt` 必须换成使用者本人或已获授权的参考音频。

## 当前选定

- 成品：本地 `outputs/voice_samples/` 中的参考音频；不随仓库分发
- 参数：`emo_alpha=0.55`、`duration_factor=1.10`
- 说明：听感比 `0.45` 更有起伏，又不像 `0.65` 那样赶；文件是 `zhang_style_emoref55_slow.wav` 的同内容副本。

## 一句话结论

核心不是“低沉”，而是：

**快语速、较高的音高上限、强动态、短停顿，以及关键词突然加重。**

听感上偏“松弛的新闻解说”，不能念得太稳、太圆、太像播音腔。

## 听感标签

- 语速偏快，句子推进干脆，不拖尾
- 句间停顿短，通常不留给听众明显的“换气感”
- 音高不低，句尾经常下压，但关键词会突然抬高
- 重音落在观点词、数字、转折词和结论句上
- 整体自信、松弛，带一点痞气，不能过度兴奋
- 长句会被切成多个短句群，而不是一口气念完

## 实测声学指标

测量素材为两段 16 kHz 中文新闻解说音频及字幕，仅用于本地声学分析，不随仓库分发。

| 指标 | 第一期 | 第二期 | 复用建议 |
|---|---:|---:|---|
| 语速 | 304 字/分钟 | 317 字/分钟 | 目标 `300–320` |
| 字幕句群中位数 | 10 字 / 1.82 秒 | 10 字 / 1.88 秒 | 一句约 `8–14` 字 |
| F0 中位数 | 133.8 Hz | 134.6 Hz | 只作参考，不要强行改本音 |
| F0 10%–90% | 100.8–178.5 Hz | 100.8–173.5 Hz | 高音上限要打开 |
| F0 标准差 | 34.0 | 31.5 | 音高起伏要大 |
| 停顿 > 200 ms 占比 | 8.1% | 8.2% | 短停顿多，长停顿少 |
| 停顿 > 500 ms 占比 | 3.0% | 2.1% | 不要频繁大停顿 |
| 频谱重心 | 1244 Hz | 1254 Hz | 保持中高频清晰度 |
| 综合响度 | 约 -18.3 LUFS | 约 -17.0 LUFS | 交付时再统一响度 |
| LRA | 5.6 LU | 5.5 LU | 动态不要压得太死 |

注意：F0 是音色的一部分。使用者本人的 F0 中位数如果只有 `117 Hz`，生成结果落在 `135–145 Hz` 已经算“风格化”，不要为了凑 `134.6 Hz` 强行移调。

## IndexTTS 2.5 参数路线

### 路线 A：情感向量基线

这组参数用于“自己的音色 + 张狗剩式节奏”。在 143 个规范化读音单元的测试文本上，生成约 `27.0 秒`，语速约 `317 字/分钟`。

优点是稳定、可复制；缺点是整段一次性生成时，重音和停顿容易被抹平，听感仍偏“整段 TTS”。如果目标是更像真人在讲话，优先使用路线 B。

```yaml
lang: ZH
duration_factor: 1.08
emo_vector: [0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65]
emo_alpha: 0.35
temperature: 0.85
top_p: 0.90
top_k: 40
repetition_penalty: 8.5
max_text_tokens_per_segment: 300
interval_silence: 200
text_normalization: true
```

`emo_vector` 的顺序是：

```text
[happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
```

这组向量的 `calm` 占比高，是为了压住模型常见的“假兴奋”和飘忽感；`emo_alpha=0.35` 则负责保留本音，不让情绪把音高整体抬得太多。

如果启用 `QwenEmotion`，可以把情绪描述固定为：

> 快节奏的新闻解说，松弛、自信，带一点痞气；短停顿，句尾下压，关键词突然加重，不要播音腔，不要过度兴奋。

### 路线 B：情感参考（更接近真人）

这是目前更推荐的方式：`spk_audio_prompt` 仍然使用你的音色，`emo_audio_prompt` 只用一段 `10–15 秒`的目标风格音频控制情绪、停顿和节奏。

```yaml
lang: ZH
emo_audio_prompt: /path/to/zhang_style_15s.wav
emo_alpha: 0.55
duration_factor: 1.10
temperature: 0.86
top_p: 0.91
top_k: 45
repetition_penalty: 8.2
max_text_tokens_per_segment: 300
interval_silence: 200
text_normalization: true
```

实测对比：

| `emo_alpha` | 时长 | 语速 | F0 中位数 | RMS 动态 | LRA |
|---:|---:|---:|---:|---:|---:|
| `0.45` | 26.5s | 324 字/分 | 125.4 Hz | 16.8 dB | 2.2 LU |
| `0.55`（选定） | 25.0s | 344 字/分 | 128.4 Hz | 17.5 dB | 3.6 LU |
| `0.65` | 24.0s | 358 字/分 | 128.4 Hz | 18.6 dB | 3.0 LU |

经试听，当前选定 `0.55`。如果觉得太冲，降到 `0.45`；如果还太平，升到 `0.60–0.65`，但语速会明显变快，必要时把 `duration_factor` 调大。

参考片段可以这样切：

```bash
ffmpeg -ss 0 -t 15 -i /path/to/style-source.wav \
  -ac 1 -ar 16000 -c:a pcm_s16le /tmp/zhang_style_15s.wav
```

`emo_audio_prompt` 是情感/韵律参考，不是音色参考。不要把参考片段直接放进 `spk_audio_prompt`。

### 更冲、更快的版本

适合短视频开头、观点输出、需要更强压迫感的段落。代价是音高会明显上抬，音色可能不像本人。

```yaml
duration_factor: 0.95
emo_vector: [0.14, 0.05, 0, 0, 0, 0, 0.10, 0.51]
emo_alpha: 0.60
temperature: 0.88
top_p: 0.92
top_k: 50
repetition_penalty: 8.0
```

### 更贴本音的版本

适合长视频和需要稳定音色的段落，语速会更快一些。

```yaml
duration_factor: 0.97
emo_vector: [0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65]
emo_alpha: 0.35
temperature: 0.85
top_p: 0.90
top_k: 40
repetition_penalty: 8.5
```

### 参数调节顺序

1. 先调文本断句，不要先调模型参数。
2. 语速不对，优先改 `duration_factor`：数值越大越慢、越长。
3. 使用路线 B 时，情绪太飘或音高太高，先降 `emo_alpha`。
4. 使用路线 A 时，先降 `happy` 和 `surprised`，再降 `emo_alpha`。
5. 语气太稳、太平，增加 `emo_alpha`，或稍微提高 `temperature`。
6. 吐字粘连、重复，降低 `temperature`，并适当提高 `repetition_penalty`。
7. 不要用移调来“修音色”。移调会破坏本人音色，优先重新生成。

## 文本写法

这套声线对文本断句的敏感度高于参数。

- 一句控制在 `8–14` 个汉字，长句拆成两到三个短句。
- 观点句、数字、转折词前后加逗号或句号，给模型一个“重音落点”。
- 连续短句用于加速，突然出现的短结论句用于制造停顿感。
- 少用长定语和书面连接词，多用“完了、真不是、说白了、你记住”这类口语钩子。
- 英文缩写用注音标记，避免被逐字母念。例如：`<AI|EY2 . AY1>`。
- 长文本按 `1–3` 句切块生成，再拼接；不要一次塞几千字，否则后半段容易漂。

可用示例：

> 很多人以为，声音克隆就是把一段录音丢给 AI，然后按下生成，完了。真不是。决定像不像的，第一是参考音频，第二是断句，第三才是模型。

## 参考音频要求

音色参考（`spk_audio_prompt`）：

- 时长 `10–15 秒`，单人、干声、无音乐、无混响
- 语速自然，不要刻意播音，也不要太激动的表演
- 采样率 `44.1 kHz` 或 `16 kHz`，峰值不要削波
- 参考音色必须来自本人或已获授权的声音
- 测试时使用使用者本人提供且获授权的本地参考音频

情感/风格参考（`emo_audio_prompt`）：

- 同样要求单人、干声、无音乐、无混响
- 选目标风格最典型的一段，不要选开场音乐或多人对话
- 只控制情绪和韵律，不要把它当音色参考
- 使用前确认授权；公开内容建议改用自制或已授权的风格样本

## 后期链

这套链只做轻度塑形，不改变音色：

```text
60 Hz 高通
90–180 Hz 胸腔共鸣 +0.04
2.5–4.5 kHz 清晰度 +0.025
10 ms 淡入淡出
峰值归一到 0.95
输出 44.1 kHz / 24-bit WAV
```

当前选定版 `zhang_style_selected.wav` 的实测值：

- 综合响度约 `-17.2 LUFS`
- True Peak 约 `-0.43 dBTP`
- LRA 约 `3.6 LU`

如果用于播客、YouTube 或课程交付，建议再统一到平台目标响度；如果用于短视频，可以保留更多动态，不要把所有句子的音量压成一条直线。

## Python 复现

```python
import os
from pathlib import Path

from indextts.infer_v2_5 import IndexTTS2

ROOT = Path(os.environ.get("INDEXTTS_ROOT", Path.cwd()))
VOICE_PROMPT = Path(os.environ["VOICE_PROMPT"])
STYLE_REFERENCE = Path(os.environ["STYLE_REFERENCE"])
OUTPUT = Path("outputs/voice_samples/zhang_style.wav")

tts = IndexTTS2(
    cfg_path=str(ROOT / "checkpoints/config.yaml"),
    model_dir=str(ROOT / "checkpoints"),
    device="cpu",
    use_qwen_emo=False,
)

tts.infer(
    spk_audio_prompt=str(VOICE_PROMPT),
    text="先把观点说清楚。再补一句原因。最后落一个结论。",
    lang="ZH",
    output_path=str(OUTPUT),
    emo_audio_prompt=str(STYLE_REFERENCE),
    emo_alpha=0.55,
    duration_factor=1.10,
    max_text_tokens_per_segment=300,
    interval_silence=200,
    text_normalization=True,
    temperature=0.86,
    top_p=0.91,
    top_k=45,
    repetition_penalty=8.2,
    verbose=False,
)
```

运行前设置：

```bash
export VOICE_PROMPT="/path/to/your_15s_prompt.wav"
export STYLE_REFERENCE="/path/to/zhang_style_15s.wav"
```

如果改走路线 A，把 `emo_audio_prompt` 换成
`emo_vector=[0.08, 0.02, 0, 0, 0, 0, 0.05, 0.65]`，
并把 `emo_alpha` 改为 `0.35`、`duration_factor` 改为 `1.08`。

## 复测方法

用于判断新生成音频是否仍然像这套风格：

- 时长与字数换算语速，目标 `300–320 字/分钟`
- `librosa.pyin(fmin=70, fmax=400)` 统计 F0 中位数和 10%–90% 分位
- RMS 门限 `max_dB - 40` 统计停顿占比
- `ffmpeg loudnorm` 读取 LUFS、LRA 和 True Peak
- 重点听三件事：句间是否够短、关键词是否突然加重、句尾是否下压

## 验证样本

项目内的对照记录：

| 版本 | 路线 | 时长 | 语速 | F0 中位数 | F0 90% | LRA |
|---|---|---:|---:|---:|---:|---:|
| `zhang_style_selected.wav` | 情感参考（选定，同 `emoref55_slow`） | 25.0s | 344 字/分 | 128.4 Hz | 157.1 Hz | 3.6 LU |
| `zhang_style_emoref45.wav` | 情感参考 | 26.5s | 324 字/分 | 125.4 Hz | 156.2 Hz | 2.2 LU |
| `zhang_style_emoref65.wav` | 情感参考 | 24.0s | 358 字/分 | 128.4 Hz | 165.5 Hz | 3.0 LU |
| `zhang_style_final.wav` | 向量基线 | 27.0s | 317 字/分 | 136.0 Hz | 196.8 Hz | 3.3 LU |
| `zhang_style_natural.wav` | 向量基线 | 25.3s | 339 字/分 | 140.8 Hz | 185.8 Hz | 3.5 LU |
| `zhang_style_base.wav` | 向量基线 | 26.5s | 324 字/分 | 149.2 Hz | 198.0 Hz | 2.7 LU |
| `zhang_style_punch.wav` | 向量基线 | 24.8s | 346 字/分 | 159.9 Hz | 214.7 Hz | 2.2 LU |

对照文件位于：

```text
outputs/voice_samples/zhang_style_test/
```

已知差距：

- 向量基线版为了接近目标指标，会把 F0 抬高到 `136–160 Hz`，比本人参考音频的 `117 Hz` 高不少，听感容易“不像你”。
- 情感参考版的音色更稳，但语速会随 `emo_alpha` 上升；`0.65` 已经到 `358 字/分`，不适合长段落。
- 情感参考版的 LRA 仍在 `2–4 LU`，低于张狗剩原片的 `5.5 LU`。
- 整段一次性生成会压平重音；但把全文拆成六段逐句生成，实测会膨胀到 `41.8 秒`，并产生 `122–143 Hz` 的段落间音高跳变，不建议整篇逐句拼接。更稳的做法是整段生成，只单独重做开头钩子和结尾金句。

## 使用边界

- 只复用节奏和表达方式，不把张狗剩的原声作为 `spk_audio_prompt`
- `emo_audio_prompt` 只用于个人实验中的情绪/韵律参考；公开使用需取得授权
- 不冒充本人、不伪造其发言、不用于欺骗性内容
- 公开使用前确认声音授权、平台规则和当地法律要求
