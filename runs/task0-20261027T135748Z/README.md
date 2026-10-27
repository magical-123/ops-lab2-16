# A 的任务 0 证据索引

- `meta.txt`：UTC/北京时间、被测源码提交、CPU/内存/磁盘/OS/Go/采集工具信息。采样时监控包尚在本机下载，因此原始 meta 如实记录尚未安装；后续版本另见 `tools-verification.txt`。
- `fsync-1.txt`、`fsync-2.txt`、`fsync-3.txt`：连续三次 2000 次的原始输出。
- `idle-*.log`：空载原始日志；`fsync5000-*`：指导书 5000 次的原始输出和日志。
- `fsync-extended-*`：5000 次仅持续约 8.51 秒，为充分观察额外采集 9404 次（约 15.90 秒）。
- `load-windows.tsv`：每次负载准确起止时间与迭代数；`commands.txt`：采集命令。
- `build-tools.log`：真实构建、4 个包测试、fmt-check/vet 输出，末尾还保留了随后被停止的慢速下载记录。
- `tools-verification.txt`：完整包 SHA256、原始 get-tools 校验与解压、版本和 promtool 配置检查。
- 根目录 `smoke-*`：首次短暂检查，node 尚未完成首次抓取（`unknown`），不是正式压测或有效任务 1 结果；保留原记录。
- `smoke-20261027T153552Z/`：再次等待首次抓取后，两个 targets 均 up、GOMAXPROCS=1、三端口均回环监听的成功检查；检查后进程均已停止。
- `summary.json`：派生统计，可重算，不是原始输出。未运行任务 1/2/3 或 O1。

从仓库根目录复算：

```bash
python3 scripts/summarize-task0.py runs/task0-20261027T135748Z
find runs/task0-20261027T135748Z -name 'SHA256SUMS*' -exec sha256sum -c {} \;
```

汇总排除每个工具首个开机累计报告，并保守剔除负载起止边界秒。空载 UTC13:58:00–11 共12个一秒报告；负载 UTC13:58:24–37 共14个报告。延迟列同时提供各秒算术均值与按 I/O 数加权均值，报告采用后者；所有原始文件保持不变。
