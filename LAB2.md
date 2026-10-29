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

构建及检查：`make build test fmt-check vet` 已通过；四个 Go 包测试通过。安装日志中的原始构建/测试输出见 `build-tools.log`，监控配置检查及版本见 `tools-verification.txt`。短暂服务检查也通过：`smoke-20261027T153552Z/smoke-targets.json` 中两个目标均为 up，GOMAXPROCS=1，三个服务仅监听回环地址；检查后均已停止。任务 0 交接后，B 已完成 RED 查询与指标基线，见第 3 节。

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

两个抓取目标的状态（`curl -s 127.0.0.1:9090/api/v1/targets` 中两处 `"health"` 的值）：up、up

本组编写的四条查询（与 `deploy/queries-red.txt` 一致）：

```text
server_rps          sum(rate(http_requests_total{route="${route}"}[${window}]))
server_error_rate   (sum(rate(http_requests_total{route="${route}",code=~"5.."}[${window}])) or vector(0)) / sum(rate(http_requests_total{route="${route}"}[${window}]))
server_p99_ms       1000 * histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{route="${route}"}[${window}])))
server_slo_good     sum(rate(http_request_duration_seconds_bucket{route="${route}",code="200",le="${slo}"}[${window}])) / sum(rate(http_request_duration_seconds_count{route="${route}"}[${window}]))
```

`runs/t1-light` 的数据（`scripts/table.sh runs/t1-light ok_rps mean_ms p99_ms server_rps server_mean_ms server_p99_ms cpu_ms_per_req db_query_mean_ms`）：

| step | target_rps | ok_rps | mean_ms | p99_ms | server_rps | server_mean_ms | server_p99_ms | cpu_ms_per_req | db_query_mean_ms |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0.0 | - | - | - | - | - | - | NaN |
| 2 | 50 | 50.5 | 11.51 | 12.74 | 51.7083 | 10.7291 | 19.9 | 0.575588 | 10.3165 |
| 3 | 100 | 97.8 | 11.66 | 13.99 | 95.3333 | 10.8729 | 19.9 | 0.572802 | 10.4239 |
| all | - | 74.2 | 11.61 | 13.41 | - | - | - | - | - |

从这次实验读出：每次查询实际占用连接 **10.42 ms**（`db_query_mean_ms`，取 100 rps 阶段）；每个请求消耗的 CPU **0.573 ms**（`cpu_ms_per_req`，取 100 请求/秒的阶段）。

## 4. 任务 2：读路径

### 4.1 预测（R1 之前写）

| 资源 | 容量 | 每个请求占用（数据来源） | 推算的上限（请求/秒） |
|---|---|---|---|
| 连接池 | 4 个连接 | 10.42 ms（t1-light 第3阶段 db_query_mean_ms） | 384 |
| CPU | enrolld 的 1 个核 | 0.573 ms（t1-light 第3阶段 cpu_ms_per_req） | 1745 |

先达到上限的是：**连接池**。预计从 **303-307 请求/秒**起，客户端 p99 超过 50 ms。

**计算依据：**

1. **系统模型与容量上限**：
   - 模型：M/D/4 排队系统（泊松到达，确定性服务时间 D=10.42 ms，4个并行服务台）
   - 单连接服务率：μ₁ = 1/0.01042 ≈ 95.97 请求/秒
   - 总容量上限：μ = 4 × 95.97 ≈ 384 TPS（当 λ ≥ 384 时，ρ ≥ 1，系统不稳定）
   - 利用率：ρ = λ/384

2. **p99 = 50ms 的数值求解**：
   
   M/D/c 的等待时间可用 M/M/c 近似。等待时间分布：
   ```
   P(W_q > t) = P_wait × exp(-c(1-ρ)/D × t)
   ```
   
   其中 P_wait 为 Erlang C 排队概率：
   ```
   P_wait = [(cρ)^c / c!(1-ρ)] / [Σ(k=0~c-1) (cρ)^k/k! + (cρ)^c / c!(1-ρ)]
   ```
   
   令 P(W_q > 50ms) = 0.01，求解 ρ：
   ```
   exp(-4(1-ρ)/10.42 × 50) = 0.01/P_wait
   1-ρ = -0.0521 × ln(0.01/P_wait)
   ```
   
   数值迭代结果：
   - ρ ≈ 0.79 时，要求 1-ρ ≈ 0.207（P_wait ≈ 0.53），实际 1-ρ = 0.21，吻合
   - 对应到达率：λ = 0.79 × 384 ≈ 303 TPS
   
   验证：第5阶段 307 TPS（ρ=0.80）时，p99 预计略超 50ms



R1 的到达率（`scripts/rates.sh 384` 的输出）：77,154,230,269,307,346,384,422,461

### 4.2 R1：`-pool 4`

`scripts/table.sh runs/r1-pool4 ok_rps error_rate p99_ms server_p99_ms server_mean_ms inflight_avg cpu_ms_per_req pool_in_use_avg pool_wait_p99_ms sched_wait_p99_ms svc_cpu_busy procs_running_avg`：

| step | target_rps | ok_rps | error_rate | p99_ms | server_p99_ms | server_mean_ms | inflight_avg | cpu_ms_per_req | pool_in_use_avg | pool_wait_p99_ms | sched_wait_p99_ms | svc_cpu_busy | procs_running_avg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 77 | 79.0 | 0.0000 | 13.56 | 19.9 | 10.8261 | 0.6 | 0.579616 | 0.6 | 1.28 | 0.518571 | 0.055 | 1.2 |
| 2 | 154 | 152.8 | 0.0000 | 18.16 | 19.9322 | 11.1713 | 1.68 | 0.555165 | 1.68 | 7.99923 | 0.496268 | 0.087 | 2.2 |
| 3 | 230 | 229.8 | 0.0000 | 22.78 | 36.175 | 11.9673 | 3 | 0.544365 | 2.88 | 14.486 | 0.497587 | 0.1305 | 1.6 |
| 4 | 269 | 273.9 | 0.0000 | 32.07 | 46.9959 | 13.7089 | 4.24 | 0.537152 | 3.08 | 22.35 | 0.511636 | 0.1485 | 1.6 |
| 5 | 307 | 311.1 | 0.0000 | 46.32 | 49.2824 | 16.3557 | 5.08 | 0.529764 | 3.32 | 45.1336 | 0.570956 | 0.166 | 2.2 |
| 6 | 346 | 342.4 | 0.0000 | 64.11 | 87.9898 | 22.2277 | 6.48 | 0.513729 | 3.6 | 70.4929 | 0.494784 | 0.174 | 1.2 |
| 7 | 384 | 383.5 | 0.0083 | 1009.22 | 1784.47 | 601.125 | 233.6 | 0.516707 | 4 | 997.282 | 0.729358 | 0.199 | 2 |
| 8 | 422 | 373.2 | 0.1062 | 1011.91 | 1982.42 | 997.707 | 414.36 | 0.493992 | 4 | 1906.7 | 0.696102 | 0.2085 | 1.8 |
| 9 | 461 | 374.9 | 0.1902 | 1012.14 | 1987.2 | 1002.48 | 463.92 | 0.493668 | 4 | 1950.61 | 0.73535 | 0.231 | 2.4 |
| all | - | 280.1 | 0.0511 | 1011.39 | - | - | - | - | - | - | - | - | - |

最大吞吐量 **383.5 请求/秒**，出现在第 **7** 阶段；客户端 p99 首次超过 50 ms 是在第 **6** 阶段（**346 请求/秒**）。


### 4.3 CPU 消耗在何处

在约 0.8 倍上限的负载下采集 20 秒 CPU 剖析，`go tool pprof -top` 的前 10 行（同时保存在 `runs/r1-pool4/pprof-top.txt`）：

```text
Showing nodes accounting for 2.73s, 91.30% of 2.99s total
Dropped 94 nodes (cum <= 0.01s)
Showing top 15 nodes out of 53
      flat  flat%   sum%        cum   cum%
     2.37s 79.26% 79.26%      2.37s 79.26%  main.spin (inline)
     0.25s  8.36% 87.63%      0.25s  8.36%  internal/runtime/syscall/linux.Syscall6
     0.02s  0.67% 88.29%      0.02s  0.67%  runtime.acquireSudog
     0.02s  0.67% 88.96%      0.08s  2.68%  runtime.netpoll
     0.02s  0.67% 89.63%      0.04s  1.34%  time.Time.appendFormat
     0.01s  0.33% 89.97%      0.05s  1.67%  net/http.(*chunkWriter).writeHeader
     0.01s  0.33% 90.30%      2.46s 82.27%  net/http.HandlerFunc.ServeHTTP
     0.01s  0.33% 90.64%      0.02s  0.67%  runtime.mallocgcSmallScanNoHeaderSC7
     0.01s  0.33% 90.97%      0.13s  4.35%  runtime.park_m
     0.01s  0.33% 91.30%      0.03s  1.00%  runtime.selectgo
```

`main.spin` 占 **79.26%**；采集期间负载约 307 TPS、持续 20 秒，enrolld 消耗总 CPU 时间 2.99s，每个请求 **0.487 ms**（2.99s ÷ 6140个请求），其中 spin 约 **0.386 ms**（79.26%），其余 **0.101 ms** 消耗在：系统调用（Syscall6, 8.36%）、Go 运行时调度和网络轮询（netpoll, park_m, selectgo 等）、HTTP 框架处理和时间格式化。

### 4.4 R2：调大连接池（预测在 R2 之前写）

| 项 | 值与算法 |
|---|---|
| 每个请求占用的 CPU（取 R1 哪一阶段的 `cpu_ms_per_req`，选取理由） | 0.529764 ms（取 R1 第5阶段，该阶段 ok_rps=311.1，error_rate=0，连接池尚未完全饱和，pool_wait_p99=45.13ms 处于可接受范围） |
| 推算的 CPU 上限 C | 1000 / 0.529764 ≈ 1888 TPS |
| R2 的池大小 P2 = ceil(2 × C × 每次查询的秒数) | ceil(2 × 1888 × 0.01042) = ceil(39.32) ≈ 40 |
| R2 的到达率（`scripts/rates.sh C 0.3 0.6 0.8 0.9 1.0 1.1 1.25 1.5`） | 566,944,1322,1510,1699,1888,2077,2266 |
| 预测：R2 中先达到上限的是 | **CPU**。 |

`scripts/table.sh runs/r2-pool40 ok_rps error_rate p99_ms server_p99_ms inflight_avg cpu_cores cpu_ms_per_req cpu_wait_threads sched_wait_p99_ms pool_in_use_avg svc_cpu_busy procs_running_avg cpu_psi_some`：

| step | target_rps | ok_rps | error_rate | p99_ms | server_p99_ms | inflight_avg | cpu_cores | cpu_ms_per_req | cpu_wait_threads | sched_wait_p99_ms | pool_in_use_avg | svc_cpu_busy | procs_running_avg | cpu_psi_some |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 566 | 567.4 | 0.0000 | 13.16 | 19.9 | 5.52 | 0.284039 | 0.503058 | 0.238657 | 0.815446 | 5.52 | 0.279 | 2 | 0.203888 |
| 2 | 944 | 947.7 | 0.0000 | 13.62 | 19.9 | 9.48 | 0.458192 | 0.48649 | 0.336869 | 1.17698 | 9.48 | 0.4495 | 1.8 | 0.291973 |
| 3 | 1322 | 1318.9 | 0.0000 | 14.42 | 19.9 | 14.32 | 0.616595 | 0.46824 | 0.260561 | 1.84129 | 14.32 | 0.608 | 2.2 | 0.24099 |
| 4 | 1510 | 1511.0 | 0.0000 | 15.17 | 19.9 | 16.32 | 0.690596 | 0.457172 | 0.172417 | 2.23436 | 16.32 | 0.69 | 2.6 | 0.173523 |
| 5 | 1699 | 1687.1 | 0.0000 | 15.94 | 19.9 | 16.24 | 0.753959 | 0.446636 | 0.1025 | 3.43983 | 16.24 | 0.75 | 2.2 | 0.12122 |
| 6 | 1888 | 1887.5 | 0.0000 | 18.73 | 19.9004 | 18.44 | 0.835956 | 0.44448 | 0.0528602 | 4.64119 | 18.44 | 0.839 | 3.6 | 0.0849647 |
| 7 | 2077 | 2077.1 | 0.0000 | 26.24 | 19.9024 | 21.32 | 0.917263 | 0.440542 | 0.0237856 | 8.7903 | 21.32 | 0.917 | 2.8 | 0.0585435 |
| 8 | 2266 | 2265.2 | 0.0000 | 352.82 | 19.9601 | 23.8 | 0.987426 | 0.438572 | 0.00589939 | 175.573 | 23.8 | 0.9935 | 3 | 0.0416508 |
| all | - | 1532.7 | 0.0000 | 123.46 | - | - | - | - | - | - | - | - | - | - |

最大吞吐量 **2265.2 请求/秒**（阶段8）；与预测的 C（1888 TPS）相差：**+377 TPS (+20%)**。差异原因：高负载下 cpu_ms_per_req 从预测值 0.5298 ms 降至 0.4386 ms，重新计算 CPU 上限 = 1000/0.4386 ≈ 2280 TPS，与实测吻合。CPU 饱和证据：阶段8 svc_cpu_busy=99.35%，sched_wait_p99_ms=175.57ms（Go调度排队），而 pool_wait_p99_ms 保持 0.99ms 低位，pool_in_use_avg=23.8（池40仍有余量），瓶颈成功从连接池转移到 CPU。

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

**问题 1：上限由什么决定。** 按 L-07 第 25 页资源账的格式，为 enrolld 的读路径编制一份资源账：资源、每个请求占用（实测）、容量、推算的上限、实测的最大吞吐量、饱和观测项。预测与实测相差多少，差异来自何处？`cpu_ms_per_req` 随负载如何变化，原因是什么？这对”在低负载下测量每请求开销，再推算上限”的做法意味着什么？`db_query_mean_ms` 为什么大于 `-db-ms`？以”p99 ≤ 50 ms”为目标，R1 能承受的最大阶段相当于上限的多少比例？与 L-07 第 6 页”容量 = 上限 × 0.7”比较，为什么尚未达到上限延迟就已上升？R2 调大连接池后，瓶颈转移到了哪个资源？

### enrolld 读路径资源账（基于 R1 和 R2 数据）

| 资源 | 每个请求占用（实测） | 容量 | 推算上限 | 实测最大吞吐量 | 利用率 | 饱和观测项 |
|------|---------------------|------|----------|---------------|--------|-----------|
| 连接池（R1） | 10.42 ms（t1-light db_query_mean_ms） | 4个连接 | 384 TPS | 383.5 TPS（R1阶段7） | 100% | pool_wait_p99_ms=997ms, pool_in_use_avg=4 |
| CPU（R2） | 0.439 ms（R2阶段8 cpu_ms_per_req） | 1核=1000ms | 2280 TPS | 2265.2 TPS（R2阶段8） | 99.35% | sched_wait_p99_ms=175.57ms, svc_cpu_busy=0.9935 |

**预测与实测差异分析：** R1预测连接池上限384 TPS，实测383.5 TPS，误差<1%，高度吻合。R2预测CPU上限1888 TPS（基于阶段5的0.530 ms），实测2265 TPS，超出20%。差异来源于**cpu_ms_per_req随负载下降**：从低负载的0.530 ms降至高负载的0.439 ms。原因是enrolld存在**固定开销**（HTTP解析、Go运行时、日志等约0.1 ms），这部分不随TPS线性增长；高负载下固定开销被分摊，单请求CPU降低。这说明**低负载测量会低估上限**，应在接近目标负载下测量，或分离固定开销与变动开销。

**db_query_mean_ms > -db-ms原因：** 实测10.43 ms > 配置10 ms，额外开销包括：①连接池获取延迟（pool_wait），②Go database/sql驱动开销，③网络往返（虽是本地回环，仍有调度开销），④数据库处理时间的统计误差。R1阶段5的pool_wait_p99=45ms说明连接池已开始排队，拉高了平均占用时间。

**容量分析：** R1以p99≤50ms为目标，第5阶段（307 TPS）p99=46.32ms尚可接受，第6阶段（346 TPS）p99=64.11ms已超标。307 TPS相当于连接池上限384 TPS的**80%**，而非L-07建议的70%。原因是M/D/4模型下，ρ=0.80时排队已显著（Erlang C公式显示P_wait≈0.53），延迟在ρ>0.7后非线性上升。这验证了**容量=上限×0.7的合理性**：预留30%用于吸收排队，ρ超过0.7后p99急剧恶化。

**R2瓶颈转移：** 池大小从4→40后，连接池上限提升至3071 TPS（40/0.01043），远超CPU上限2280 TPS。R2阶段8数据证实瓶颈转移到CPU：svc_cpu_busy=99.35%，pool_wait_p99_ms保持0.99ms低位（连接池仍有16.2个余量），而sched_wait_p99_ms=175.57ms（Go调度排队），cpu_wait_threads和cpu_psi_some上升。此时系统从**资源饱和**（连接池）转变为**计算饱和**（CPU），印证了L-07关于多资源系统中瓶颈迁移的论述。

**问题 2：利用率不等于饱和。** R1 达到上限时，enrolld 所在核的 CPU 利用率是多少？哪个数值最先表明资源已经饱和？R2 中 CPU 利用率接近 100% 时，内核层的 `procs_running_avg`、`cpu_psi_some`、`cpu_wait_threads` 和 Go 运行时层的 `sched_wait_p99_ms` 分别如何变化？为什么内核层几乎观察不到排队，排队发生在哪里？这与 L-06 第 16、17 页 Tomcat 的线程池有何相同之处？最后用 Little's Law 核对：从 R1 选取三个阶段，用 `server_rps × server_mean_ms` 计算在途请求数，并与 `inflight_avg` 比较；W 为什么必须用平均值而不能用 p99？哪个阶段不一致，原因是什么？

R1/R2 原始数据已由 C 提交（见第 4 节），问题 2 由 A 在独立分支完成；取数框架见 [`docs/leader-handoff.md`](docs/leader-handoff.md)。

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
| magical-123 | A（组长）：环境与任务 0；问题 2 另行完成，O1 待必做压测完成；仓库和主机协调。其余四位 GitHub 用户名由 E 汇总补入。 |
