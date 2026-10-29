# A 的 O1 测前计划（尚未执行）

仅在 B/C/D 的必做实验完成、主机已明确交接给 A 后运行。当前没有 O1 实测结果；此计划和预测须在正式 O1 开始前提交并保留，测后另加解释，不回改预测。

预测：将 `GOGC` 从 100 提高到 400，通常允许堆增长得更大后再触发 GC，因此预测 GC 次数减少、RSS 上升。GC CPU 时间和 p99 可能降低，但也可能受更大堆的扫描、单核竞争或吞吐差异影响，不能保证改善。比较时解释额外内存与 GC 成本的取舍，并联系 JVM 堆大小、触发阈值与 GC。

保持相同 Go 版本、分核、服务参数、到达过程和请求接口；enrolld CPU 1，loadgen/Prometheus/node_exporter CPU 0。接口为 `/api/report?mb=4`。初定到达率 100 请求/秒；若负载生成器不能稳定维持或出现过载，保留失败结果，先记录并提交改动原因，再用对两组相同的新到达率重做，不能只降低其中一组。

两次分别重启服务，在各自终端中运行（先停止上一组服务）：

```bash
cd /srv/lab2
GOGC=100 taskset -c 1 bin/enrolld
# 下一次：GOGC=400 taskset -c 1 bin/enrolld
```

每次用相同 10 秒预热（原始结果另存 `o1-100-warmup` / `o1-400-warmup`），待在途请求排空，再运行正式 60 秒阶段。预热和正式测量不得混合累计计数器：

```bash
unset SLO
GEN_CPUS=0 scripts/run.sh o1-gogc100 -url 'http://127.0.0.1:8080/api/report?mb=4' -rates 100 -step 60s
# 下一次把运行名换为 o1-gogc400，其他负载参数不变。
```

运行前确认 B 已完成正确的 RED 查询；O1 需要使用 `/api/report` 对应的 route。保留 `run.sh` 的原始输出，不手改。Prometheus/node_exporter 继续仅监听回环地址，Prometheus 数据保存在 `/dev/shm/lab2-prom-$(id -un)`。

从每次 `metrics-start.txt`、`metrics-end.txt` 计算 `go_gc_cycles_total`、`go_gc_cpu_seconds_total` 的增量；二者均在同一次进程内做差。结合采样期间 RSS 的均值/峰值和客户端 p99、完成吞吐、错误率、dropped 共同判断，不跨重启比较累计值，也不只比较结束时 RSS。需要从 Prometheus 补查的 RSS 数据必须在 TSDB 清理或主机重启前导出保存。

报告待填表：GOGC、目标/实际 RPS、完成请求数、错误率、GC 次数增量、GC CPU 秒增量、RSS 均值/峰值、客户端 p99、证据目录。若两组都未稳定达到相同负载，先解释可比性限制，不宣称 GOGC 改动导致尾延迟改善。
