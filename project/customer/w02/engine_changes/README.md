# 对课程工程 w02-agent-0.5.4 的改动

`w02-agent-0.5.4.patch` 是相对课程原始工程包 `fde-student-w02-0.5.4.zip` 的全部改动，含 5 个修改文件和 3 个新增测试。改动原因和验证见 `docs/w02/interview_notes.md` 的"必要代码改动"一节。

在解压后的工程目录中应用：

```sh
patch -p1 < w02-agent-0.5.4.patch
```

本周运行时用到的环境变量（密钥另配，不在此列）：

```sh
FDE_MODEL_STREAM=1 FDE_MODEL_TIMEOUT=3600 FDE_MODEL_RETRY_TIMEOUT=3600 \
FDE_MODEL_MAX_TOKENS=32768 FDE_MODEL_RETRY_MAX_TOKENS=65536 FDE_WORKFLOW_DEADLINE=3600
```

不设置这些变量时，行为与原工程相同（非流式、600 秒总时限）。去句号和"对不上原文的条目放一边"两项改动始终生效。
