# 第 16 组：组长 A 的环境与实验交接草稿

A 已完成任务 0，证据目录为 `runs/task0-20261027T135748Z/`，报告第 1–2 节已填写。以下服务状态和 B 接手步骤记录的是 2026-10-27 的任务 0 交接：短暂服务检查中两个 Prometheus targets 均为 up，enrolld 的 GOMAXPROCS=1，检查后全部进程已停止。四名成员的普通 Linux 账号与共享目录权限已配置。2026-10-29 已整合 B/C 的任务 1、R1/R2 数据，后续主机实时状态须由当前操作者重新核对。

## 环境与访问约定

- 正式实验目录：`/srv/lab2`；桌面仓库用于编辑和同步，正式性能数据在云主机上采集。
- 主机：华为云 ECS，Ubuntu，2 vCPU、4 GiB 内存。操作系统、内核、CPU 拓扑、工具版本以任务 0 的实际输出为准。
- 分核方案：enrolld 使用 CPU `1`；loadgen、Prometheus、node_exporter 使用 CPU `0`。启动前用 `lscpu -e` 核对可用 CPU 与 CORE；如共享物理核或虚拟机未暴露真实拓扑，照实写入报告。
- 正式服务数据目录为 `/srv/lab2/data`，必须位于真实块设备；Prometheus 时序数据按课程要求放在 `/dev/shm/lab2-prom-$(id -un)`，重启会丢失。
- SSH 只使用个人密钥。仓库邀请已由组长完成。四名成员已分别配置普通 Linux 账号；组长私下分发用户名与公钥对应表，每人须用本人私钥验证登录。成员只提交公钥，私钥留在自己的电脑。
- 监控及实验接口保持监听本机地址，通过 SSH 隧道访问。不要为查看监控而开放公网 8080、9090、9100。

成员账号和公钥配置好后，可在自己电脑的 PowerShell 建立隧道。先替换账号、IP 和本地私钥路径：

```powershell
ssh -N -o ExitOnForwardFailure=yes -o IdentitiesOnly=yes -i "$env:USERPROFILE\.ssh\id_ed25519" -L 9090:127.0.0.1:9090 -L 8080:127.0.0.1:8080 -L 9100:127.0.0.1:9100 <你的Linux账号>@<公网IP>
```

保留这个窗口；另开浏览器访问 `http://127.0.0.1:9090`（Prometheus）、`http://127.0.0.1:8080/metrics`（服务指标）或 `http://127.0.0.1:9100/metrics`（主机指标）。对应服务必须已在主机上启动；关闭隧道窗口或按 Ctrl-C 可结束转发。私钥有保护口令时，在自己电脑上输入。

## A 的任务 0 交付清单

以下已由实际命令输出核对，原始数据与派生汇总一并保存。复测应使用新的时间戳目录，不能覆盖已交付证据。

- [x] `/srv/lab2` 是本组仓库，记录采样时的提交号，确认工作区状态与服务参数。
- [x] 安装并核对 Go（课程要求至少 1.26）、sysstat；完成 `make build test`，保留构建与测试输出。
- [x] 用 `scripts/get-tools.sh` 获取工具且通过 SHA256 校验，记录 Prometheus、node_exporter 的实际版本。
- [x] 保存 `lscpu`、`lscpu -e`、`free -m`、`uname -r`、`cat /etc/os-release`、`findmnt -T data`、`lsblk` 的完整输出。
- [x] 确认 `data/` 的 SOURCE、FSTYPE、云盘类型与容量，并确认它不是 tmpfs。
- [x] 连续三次运行 `bin/enrolld -bench-fsync 2000`，保留完整输出；计算平均耗时、三次差异及 `1000 / 平均耗时(ms)` 得到的串行 fsync 次数/秒。
- [x] 并行采集 `vmstat -w 1` 与 `iostat -dx 1 <整盘名>`：先空载 10 秒，再运行 `bin/enrolld -bench-fsync 5000`，观察负载期。排除第一份开机累计报告，并记录实际负载时间，不把测试结束后的空载样本当作负载样本。
- [x] 填写报告第 1–2 节或提供供 E 合并的独立草稿，所有数值注明原始文件出处；说明 CPU 是否忙、哪些指标体现等待。
- [ ] 由组长在群里通知 B/C/D/E 查看本分支交接资料；本次未替组长发送群消息。三次 mean 为 1.706/1.728/1.725 ms，综合 1.719667 ms，串行推算约 582 次/秒。

第 2 节需要的对照列：`vmstat` 的 `r/b`、`us/sy/id/wa/st`；`iostat` 的 `w/s`、`wkB/s`、`w_await`、`f/s`、`f_await`、`aqu-sz`、`%util`。解释应围绕本组实测，不能只给概念定义。


## B 接手的启动命令

目前这些进程已停止；从仓库根目录分别启动。以下操作应由当前独占主机的实验负责人执行。共享组与目录权限已配置。每轮负责人用自己的账号启动 enrolld，并用同一账号运行 run.sh；交接前先停止自己启动的服务和监控。

终端 A：

```bash
cd /srv/lab2
taskset -c 1 bin/enrolld
```

终端 B：

```bash
cd /srv/lab2
taskset -c 0 tools/node_exporter --web.listen-address=127.0.0.1:9100 > data/node_exporter.log 2>&1 &
taskset -c 0 tools/prometheus --config.file=deploy/prometheus.yml --storage.tsdb.path=/dev/shm/lab2-prom-$(id -un) --web.listen-address=127.0.0.1:9090
```

终端 C：

```bash
cd /srv/lab2
unset SLO
curl -fsS 127.0.0.1:8080/config
curl -fsS 127.0.0.1:9090/api/v1/targets
```

等待首次抓取完成，确认 enrolld 与 node 两个 target 均为 `up` 后再开始 B 的任务 1。B 完成 `deploy/queries-red.txt` 四个 TODO 并执行课程 `t1-light`；A 的短暂连通性检查不能代替该正式实验。

## 串行使用与交接

主机顺序为 **A 任务 0 → B 指标基线 → C 读路径 → D 写路径 → 选做窗口**。当前操作者完成后明确交接；其他人可以准备代码、预测和草稿，但不要同时启动 loadgen、改服务参数或清理监控数据。

交接时提供：仓库提交号、工作目录、当前进程及启动参数、CPU 绑定、`SLO`、数据目录、已保存的 `runs/` 目录及尚需重查的指标。写路径使用 `SLO=0.02`；回到读路径前执行 `unset SLO`。重启 Prometheus 或清理 `/dev/shm/lab2-prom-$(id -un)` 前，先确认所有需要的重查询结果都已保存。

## A 的问题 2：已完成实测分析

定量答案和三个阶段的 Little 定律核算已写入 [`LAB2.md` 问题 2](../LAB2.md#6-分析问题)。证据为 `runs/r1-pool4/` 和 `runs/r2-pool40/` 中的原始 CSV 与 `meta.txt`。R1 达到连接池上限时 CPU 仅 19.90%；R2 CPU 达 99.35% 时 Go 调度等待 p99 为 175.573 ms，而内核 PSI 和线程等待反而下降，不能写成所有排队指标一起上升。以下保留取数与复核方法。

1. **R1：利用率与连接池饱和。** 找出达到上限的阶段，记录服务核 CPU 利用率、`pool_in_use_avg`、`pool_wait_p99_ms`、吞吐与延迟，指出哪个指标最先体现等待。CPU 不忙并不能单独证明服务未饱和。
2. **R2：内核与 Go 运行时的排队。** 在 CPU 利用率接近 100% 的阶段，对照 `procs_running_avg`、`cpu_psi_some`、`cpu_wait_threads` 与 `sched_wait_p99_ms`。根据结果说明等待发生在哪一层，并联系课程中 Tomcat 线程池的机制；不要预设所有内核排队指标一定不变。
3. **Little 定律。** 从 R1 选三个阶段，优先覆盖低负载、接近上限和过载状态。分别读取同一阶段的 `server_rps`、`server_mean_ms`、`inflight_avg`，计算：

   ```text
   估算在途请求数 L = server_rps × server_mean_ms / 1000
   对照差值 = 估算 L - inflight_avg
   ```

   `server_mean_ms` 必须换算为秒。Little 定律中的 W 是平均停留时间，不能用 p99 代替。对照时说明统计窗口、采样方式和稳态条件；过载、在途请求持续增长或窗口两端未完成请求可能导致不一致。

报告已选 R1 第 1、5、7 阶段：估算 L 分别为 0.87195、5.10980、224.59653，对照实测 0.60、5.08、233.60。第 1 阶段相对差异最大，第 7 阶段还受过载过渡和窗口边界影响。复算时使用所有状态码的 `server_rps`，不要改用 `ok_rps` 或目标到达率。

E 整合时须核对：问题 1 原有末段写着“cpu_wait_threads 和 cpu_psi_some 上升”，但 R2 第 2→8 阶段两者实际下降（分别为 0.336869→0.00589939、0.291973→0.0416508）。应按原始 CSV 修正该处，避免与问题 2 的定量分析相反；本分支保留 C 的原文供集中整合。

## O1：尚未执行

O1 在必做压测结束、独占主机的选做窗口运行。先保存预测，再在相同到达率下请求 `/api/report?mb=4`，分别以 `GOGC=100`、`GOGC=400` 启动 enrolld，连续进行可比对照。

- 测前固定并记录：到达率、阶段时长、预热、绑核、其他启动参数及采样方法。课程中的 100 请求/秒仅为示例，须确认本机和负载生成器能稳定维持。
- 记录 `go_gc_cycles_total`、`go_gc_cpu_seconds_total` 的增量，RSS 与客户端 p99；不要跨服务重启直接比较累计计数器绝对值。
- 预测框架：更高 GOGC 可能减少 GC 次数并增加内存占用；GC CPU 与 p99 的变化由实际数据判断，不能预先宣称更好。
- 保存原始输出和证据索引，再填写报告第 7 节，解释时间与空间的取舍并联系 JVM 的堆与 GC。

## 仓库与证据要求

- `LAB2.md` 的每个数值都要追溯到 `runs/`。正式实验的表格用 `scripts/table.sh` 生成，不能改写 `scripts/run.sh` 的原始输出；查询修正只按课程提供的 `scripts/requery.sh` 重新生成相应数据。
- 不提交 `bin/`、`tools/`、`data/`，也不提交任何密钥、密码、主机公网 IP。连接信息另行私下保管，文档统一使用 `<公网IP>` 占位。
- 各人先在自己的草稿或分支写作，由 E 集中合并；不要覆盖他人的实验目录。公开报告成员栏只需 GitHub 用户名。
- 仓库邀请已完成；后续由 E 补齐报告中的 GitHub 用户名。四把 SSH 公钥已安装到独立 Linux 账号；成员仍需在自己的电脑上验证实际登录。仓库权限与 Linux 登录权限是两套配置。
- 主机及复现所需工具保留到现场验收结束；最终报告由 E 汇总、A 验收后，再记录评分提交的完整 40 位哈希。

## 独立账号的目录与交接规则

- 各成员属于共享组 `lab2`，可编辑 `/srv/lab2` 的代码和报告、执行编译、写入 `data/` 及创建自己的 `runs/<新名字>/`。账号为普通用户，系统管理操作由组长处理。
- `runs/` 父目录设置 setgid 和 sticky bit；新实验目录默认给其他成员只读权限，已完成的任务 0 原始数据保持只读。由生成该次运行的本人进行官方 requery；其他人修改查询应先协调，不能直接改别人的证据。
- `scripts/run.sh` 需要对 enrolld 的 PID 执行 `kill -0`，普通账号跨用户会失败。所以同一轮的 enrolld 与采集必须由同一账号运行。上一位停止自己的进程，下一位在本人账号重新启动。
- Prometheus 使用每个负责人自己的 `/dev/shm/lab2-prom-$(id -un)`。交接前保存 CSV 并完成必要重查询，再停止旧实例；不要尝试写另一位成员的 TSDB，也不要在导出前清理旧数据。
- 当前 `data/enroll.log` 已给共享组写权限；程序明确以 `0644` 创建新文件，因此若按写路径步骤删除并重建该日志，创建者应在下一位接手前运行 `chmod g+rw data/enroll.log`。默认 ACL/umask 不能强行补上程序明确移除的组写位。
- 每人的 Git 已仅信任 `/srv/lab2` 这个共享仓库。用各自 GitHub 身份提交代码；GitHub 推送认证与服务器 SSH 登录是两套配置，服务器登录成功不会自动获得 GitHub 推送凭据。
