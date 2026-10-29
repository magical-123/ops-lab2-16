# 实验 2 记录：第 16 组

评分时依据本文件和 `runs/` 中的原始数据核对。本文件中的每一个数值，都须能在某个 `runs/<名字>/` 的文件中找到：表格用 `scripts/table.sh` 生成后粘贴，其他数值注明出处（例如“`runs/r1-pool4/red.csv` 第 6 阶段”）。不要只贴截图。将 `<填写>` 替换为本组的内容。

第 4.1、4.4、5.1、5.3 节的预测须在对应的测量之前写好，写好后不要修改。预测错误不扣分，与实测不一致之处在分析中讨论。

## 1. 基本信息

本节和第 2 节由 A 于 **2026-10-27（北京时间）**在正式云主机采集。原始证据目录为 [`runs/task0-20261027T135748Z/`](runs/task0-20261027T135748Z/)，采样源码提交为 `d7ae8a402a98adc21d81ba58a015332affee77a0`；完整命令输出见 `meta.txt`。

| 项 | 内容 |
|---|---|
| 小组 | 第 16 组 |
| 仓库地址 | <https://github.com/magical-123/ops-lab2-16> |
| 主机 | 华为云 ECS c6s.large.2，2 vCPU、标称 4 GiB，华东-上海一 |
| CPU | Intel(R) Xeon(R) Gold 6278C CPU @ 2.60GHz；2 个逻辑 CPU；`lscpu -e` 中 CPU 0/1 均为 SOCKET 0、CORE 0 |
| 内存 | `free -m` 的 Mem total 为 **3531 MiB**；以操作系统实际可见值为准 |
| 数据目录所在的盘 | `/srv/lab2/data`，SOURCE=`/dev/vda1`、FSTYPE=`ext4`；整盘 `vda`，通用型 SSD（GPSSD）云盘 40 GiB，非 tmpfs |
| 操作系统与内核 | Ubuntu 24.04.4 LTS；`6.8.0-136-generic` |
| Go、Prometheus、node_exporter | `go version go1.27.3 linux/amd64`；Prometheus **3.13.4**、node_exporter **1.12.1** 的安装校验记录见`runs/task0-20261027T135748Z/tools-verification.txt`（工具下载在基线之后完成，未回写原始 meta） |
| 分核 | 后续 enrolld：CPU **1**；loadgen、Prometheus、node_exporter：CPU **0**；任务 0 的 fsync 按指导书原命令运行，未额外绑核 |

虚拟机呈现两个逻辑 CPU 共享同一 CORE 的 SMT 拓扑；这只是来宾系统可见拓扑，不能据此确定宿主机实际调度，也不能将 0/1 分工描述为两个独立物理核的完全隔离。后续 CPU 上限计算应使用实测每请求开销。

构建及检查：`make build test fmt-check vet` 已通过；四个 Go 包测试通过。安装日志中的原始构建/测试输出见 `build-tools.log`，监控配置检查及版本见 `tools-verification.txt`。短暂服务检查也通过：`smoke-20261027T153552Z/smoke-targets.json` 中两个目标均为 up，GOMAXPROCS=1，三个服务仅监听回环地址；检查后均已停止。课程提供的 RED 查询 TODO 留给 B 完成。

## 2. 任务 0：基线

`bin/enrolld -bench-fsync 2000` 连续三次的原始输出（分别见 `fsync-1.txt`、`fsync-2.txt`、`fsync-3.txt`）：

```text
fsync 次数 2000，总耗时 3.43 s，数据目录 data
fsync 耗时（毫秒）：mean 1.706  p50 1.550  p90 1.975  p99 4.255  max 32.342
按平均值推算，一个写者串行 fsync 每秒最多约 586 次（= 1000 / 1.706）

fsync 次数 2000，总耗时 3.48 s，数据目录 data
fsync 耗时（毫秒）：mean 1.728  p50 1.544  p90 2.062  p99 4.824  max 11.352
按平均值推算，一个写者串行 fsync 每秒最多约 579 次（= 1000 / 1.728）

fsync 次数 2000，总耗时 3.47 s，数据目录 data
fsync 耗时（毫秒）：mean 1.725  p50 1.546  p90 2.007  p99 4.718  max 37.764
按平均值推算，一个写者串行 fsync 每秒最多约 580 次（= 1000 / 1.725）
```

三次迭代数相同，平均 fsync 耗时为 `(1.706 + 1.728 + 1.725) / 3 = 1.719667 ms`，因此单个写者串行 fsync 推算上限约 **581.51 次/秒（约 582 次/秒）**。三次 mean 的极差为 **0.022 ms**，约占综合均值 **1.28%**。此推算仅基于 fsync 时间，未计每次 write、循环和后续 HTTP 服务开销，不能直接当成写接口实测 TPS。

空载和 fsync 对照数据由 `python3 scripts/summarize-task0.py runs/task0-20261027T135748Z` 从原始日志计算，结果同时保存为 `summary.json`：

| 工具与列 | 空载 | fsync 运行时 | 该列的含义 |
|---|---|---|---|
| `vmstat -w 1`：r、b | 0.08、0.08 | 1.93、0.57 | 采样瞬间可运行的进程数、不可中断睡眠的进程数（常与 I/O 等待有关） |
| `vmstat -w 1`：us、sy、id、wa、st | 0.58%、0.67%、99.00%、0.08%、0.00% | 1.36%、6.57%、48.36%、44.29%、0.00% | 整机用户态、内核态、空闲、I/O 等待及虚拟 CPU 被宿主机占走的时间比例 |
| `iostat -dx 1 vda`：w/s、wkB/s | 0.58、9.33 | 1775.29、9711.14 | 块设备每秒完成写请求数、每秒写入量（KiB/s） |
| `iostat -dx 1 vda`：w_await、f/s、f_await | 0.857 ms、0.33/s、0.000 ms | 0.535 ms、1182.29/s、0.054 ms | 写请求平均完成耗时、每秒 flush 请求数、flush 请求平均完成耗时；耗时包含队列等待 |
| `iostat -dx 1 vda`：aqu-sz、%util | 0.000、0.03% | 1.014、94.17% | 平均未完成 I/O 数（含处理中），有 I/O 进行的设备忙碌时间比例 |

采样口径：空载取 **UTC 13:58:00–13:58:11** 的 12 个一秒报告；负载取 `fsync-extended` 的 **UTC 13:58:24–13:58:37** 的 14 个报告。已排除每个工具的首份开机累计报告及负载起止边界区间，原始日志完整保留。率、CPU 百分比与队列值为等时长采样的算术均值；`w_await` 按各秒 `w/s` 加权，`f_await` 按 `f/s` 加权，避免空载无 I/O 的零值稀释延迟。空载仅 7 个写请求，延迟不具代表性，flush 延迟显示 0 也受工具精度限制。脚本另保留各秒算术均值供核查。CPU 原始整数百分比四舍五入后相加可能略偏离 100%。

指导书的 5000 次运行持续 **8.51 秒**（见 `fsync5000-bench.txt` 与 `load-windows.tsv`）；为充分观察，另外明确标注了 **9404 次**的延长运行，持续 **15.90 秒**，没有把结束后的空载混入负载统计。三次 2000 次的基线仍独立保留，不与延长运行混算。

fsync 时整机 `us+sy` 约 **7.93%**，CPU 并不繁忙；`wa≈44.29%`、`b` 出现及 `aqu-sz≈1.01` 表明存在 I/O 等待。`%util≈94.17%` 说明设备大部分时间有请求在处理，不能单独证明云盘已达吞吐上限。`r` 是瞬时值，偶见较高值也不能单独判定 CPU 饱和。应用 fsync 包含文件系统、日志和块层操作，衡量对象不同于单个设备 write/flush 的 await；几个耗时无需相等。

原始证据完整性：在仓库根目录运行 `find runs/task0-20261027T135748Z -name 'SHA256SUMS*' -exec sha256sum -c {} \;`；派生汇总重新生成后应与 `summary.json` 一致。采集脚本见 `scripts/task0-baseline.sh`，使用新时间戳目录并拒绝覆盖已有运行。

## 3. 任务 1：指标流水线

两个抓取目标的状态（`curl -s 127.0.0.1:9090/api/v1/targets` 中两处 `"health"` 的值）：<填写>

本组编写的四条查询（与 `deploy/queries-red.txt` 一致）：

```text
server_rps          <填写>
server_error_rate   <填写>
server_p99_ms       <填写>
server_slo_good     <填写>
```

`runs/t1-light` 的数据（`scripts/table.sh runs/t1-light ok_rps mean_ms p99_ms server_rps server_mean_ms server_p99_ms cpu_ms_per_req db_query_mean_ms`）：

<粘贴表格>

从这次实验读出：每次查询实际占用连接 <填写> ms（`db_query_mean_ms`）；每个请求消耗的 CPU <填写> ms（`cpu_ms_per_req`，取 100 请求/秒的阶段）。

## 4. 任务 2：读路径

### 4.1 预测（R1 之前写）

| 资源 | 容量 | 每个请求占用（数据来源） | 推算的上限（请求/秒） |
|---|---|---|---|
| 连接池 | <`-pool`> 个连接 | <填写> ms | <填写> |
| CPU | enrolld 的 <填写> 个核 | <填写> ms | <填写> |

先达到上限的是：<填写>。预计从多少请求/秒起，客户端 p99 超过 50 ms：<填写>，理由：<填写>

R1 的到达率（`scripts/rates.sh <较小的上限>` 的输出）：<填写>

### 4.2 R1：`-pool 4`

`scripts/table.sh runs/r1-<…> ok_rps error_rate p99_ms server_p99_ms server_mean_ms inflight_avg cpu_ms_per_req pool_in_use_avg pool_wait_p99_ms sched_wait_p99_ms svc_cpu_busy procs_running_avg`：

<粘贴表格>

最大吞吐量 <填写> 请求/秒，出现在第 <填写> 阶段；客户端 p99 首次超过 50 ms 是在第 <填写> 阶段（<填写> 请求/秒）。

### 4.3 CPU 消耗在何处

在约 0.8 倍上限的负载下采集 20 秒 CPU 剖析，`go tool pprof -top` 的前 10 行（同时保存在 `runs/<填写>/pprof-top.txt`）：

```text
<粘贴>
```

`main.spin` 占 <填写>%；按本次的吞吐量和 enrolld 消耗的 CPU 计算，每个请求 <填写> ms，其中 spin 约 <填写> ms，其余 <填写> ms 消耗在：<填写>

### 4.4 R2：调大连接池（预测在 R2 之前写）

| 项 | 值与算法 |
|---|---|
| 每个请求占用的 CPU（取 R1 哪一阶段的 `cpu_ms_per_req`，选取理由） | <填写> |
| 推算的 CPU 上限 C | <填写> |
| R2 的池大小 P2 = ceil(2 × C × 每次查询的秒数) | <填写> |
| R2 的到达率（`scripts/rates.sh C 0.3 0.6 0.8 0.9 1.0 1.1 1.25 1.5`） | <填写> |
| 预测：R2 中先达到上限的是 | <填写> |

`scripts/table.sh runs/r2-<…> ok_rps error_rate p99_ms server_p99_ms inflight_avg cpu_cores cpu_ms_per_req cpu_wait_threads sched_wait_p99_ms pool_in_use_avg svc_cpu_busy procs_running_avg cpu_psi_some`：

<粘贴表格>

最大吞吐量 <填写> 请求/秒；与预测的 C 相差：<填写>

## 5. 任务 3：写路径

### 5.1 预测：`-sync each`（W1 之前写）

| 项 | 值与算法 |
|---|---|
| fsync 平均耗时（任务 0） | <填写> ms |
| 推算的最大 TPS | <填写> |
| 达到上限时 enrolld 大约使用几个核（写路径没有 spin，按 4.3 节拆分出的“spin 以外的开销”估计每个写请求的 CPU） | <填写> |
| W1 的到达率（`scripts/rates.sh <最大 TPS> 0.2 0.4 0.6 0.8 0.9 1.0 1.1 1.2`） | <填写> |

### 5.2 W1：`-sync each`

`scripts/table.sh runs/w1-<…> ok_rps error_rate p99_ms server_p99_ms cpu_cores fsync_per_s fsync_mean_ms batch_mean svc_cpu_busy cpu_iowait disk_w_per_s disk_w_await_ms disk_f_per_s disk_f_await_ms disk_aqu_sz disk_util`：

<粘贴表格>

### 5.3 预测：`-sync group`（W2 之前写）

在 W1 达到上限时的到达率下，改为组提交后：吞吐量 <填写>；平均每次 fsync 处理 <填写> 条记录；客户端 p99 约 <填写>。理由：<填写>

W2 的到达率：<填写>

### 5.4 W2：`-sync group`

（列与 5.2 相同）

<粘贴表格>

### 5.5 W3：`-sync interval`

（列与 5.2 相同）

<粘贴表格>

## 6. 分析问题

每题先列出所用数据（引用上面的表或 `runs/` 中的文件），再写结论，并说明结论的成立条件。每题 300～600 字。

**问题 1：上限由什么决定。** 按 L-07 第 25 页资源账的格式，为 enrolld 的读路径编制一份资源账：资源、每个请求占用（实测）、容量、推算的上限、实测的最大吞吐量、饱和观测项。预测与实测相差多少，差异来自何处？`cpu_ms_per_req` 随负载如何变化，原因是什么？这对“在低负载下测量每请求开销，再推算上限”的做法意味着什么？`db_query_mean_ms` 为什么大于 `-db-ms`？以“p99 ≤ 50 ms”为目标，R1 能承受的最大阶段相当于上限的多少比例？与 L-07 第 6 页“容量 = 上限 × 0.7”比较，为什么尚未达到上限延迟就已上升？R2 调大连接池后，瓶颈转移到了哪个资源？

<填写>

**问题 2：利用率不等于饱和。** R1 达到上限时，enrolld 所在核的 CPU 利用率是多少？哪个数值最先表明资源已经饱和？R2 中 CPU 利用率接近 100% 时，内核层的 `procs_running_avg`、`cpu_psi_some`、`cpu_wait_threads` 和 Go 运行时层的 `sched_wait_p99_ms` 分别如何变化？为什么内核层几乎观察不到排队，排队发生在哪里？这与 L-06 第 16、17 页 Tomcat 的线程池有何相同之处？最后用 Little's Law 核对：从 R1 选取三个阶段，用 `server_rps × server_mean_ms` 计算在途请求数，并与 `inflight_avg` 比较；W 为什么必须用平均值而不能用 p99？哪个阶段不一致，原因是什么？

待 C 提交 R1/R2 后由 A 完成定量分析；证据需求与 Little 定律核对框架见 [`docs/leader-handoff.md`](docs/leader-handoff.md)。当前没有运行 R1/R2，未预填结论。

**问题 3：持久性以延迟为代价。** W1 实测的最大 TPS 与 1000 ÷ fsync 平均耗时相比如何？W1 达到上限时 CPU、内存、磁盘的指标各是多少，哪几列表明磁盘饱和？应用测得的 `fsync_mean_ms` 与 `disk_w_await_ms`、`disk_f_await_ms` 为什么不同？一次 fsync 大约对应几次写和几次 flush？W1 与 W2 在 `disk_util` 相近时吞吐量相差多少，`%util` 接近 100% 能否说明磁盘已经饱和？组提交的 `batch_mean` 如何随负载变化，低负载时是否有收益，本组的预测是否正确？W3 快了多少，代价是什么？选课记录应采用哪一种方式，在什么条件下 interval 可以接受？

<填写>

**问题 4：延迟数值的测量位置与方法。** 同一阶段中，客户端与服务端的平均值、p99 各相差多少？列出只计入客户端的时间组成。找出一个服务端 p99 大于客户端 p99 的阶段，并解释原因（L-08 第 10 页）。比较服务端的 `server_slo_good` 与客户端的 `slo_good`；若存在过载阶段，二者为何相差很大？SLI 应在何处测量（L-08 第 19 页）？用 R1 的 `steps.csv`，将各阶段的 p99 求平均，与 `all` 行的 p99 比较，说明百分位数为什么不能平均，以及正确的合并方法。最后计算错误预算：SLO 为“30 天内 99% 的读请求在 50 ms 内成功返回”，若 R1 中第一个不达标阶段的负载持续下去，燃烧率是多少，30 天的预算多久耗尽（L-08 第 21 页）？

<填写>

## 7. 选做记录

| 选做 | 完成情况与证据 |
|---|---|
| O1 内存与 GC | 尚未执行；等待必做压测结束后的独占窗口。测前计划见 [`docs/A-O1-plan.md`](docs/A-O1-plan.md)。 |
| O2 网络 | <未做 / 两台主机的规格与拓扑、`runs/` 或日志、结论> |
| O3 告警与看板 | <未做 / 规则文件、触发记录、看板说明> |
| O4 迁移到小组项目 | <未做 / 仓库链接、测了哪个资源、结论> |

## 8. 成员分工

每位成员一行，只填写 GitHub 用户名，无需填写姓名；行数应与小组人数一致。

| GitHub 用户名 | 负责的部分 |
|---|---|
| magical-123 | A（组长）：环境与任务 0；问题 2、O1 待前置实验完成；仓库和主机协调。其余四位 GitHub 用户名由 E 汇总补入。 |
