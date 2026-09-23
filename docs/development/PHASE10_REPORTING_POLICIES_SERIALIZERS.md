# Phase 10 Reporting Policies + Serializers

## 1. Scope

本阶段实现 Analysis Reporting & Export Center 的确定性 Policy 和传输序列化组件：

- Report Filter Policy；
- Export Limit Policy；
- CSV Serializer；
- XLSX Serializer。

本阶段不包含 Repository、Provider、ReportingService、API、Frontend、Migration、ORM 或持久化文件。所有组件不查询数据库、不修改业务数据，也不产生新的分析事实。

当前仓库尚未实现 Phase 10 Contracts 与 Schema Registry。为保持本阶段提交范围，Policy/Serializer 使用结构化 `Protocol` 描述所需最小接口，测试通过显式 stub 提供 Schema/Registry。后续 Contracts/Registry 必须实现该接口，不允许 Policy 动态发现字段。

## 2. File Structure

```text
backend/services/reporting/
├── policies/
│   ├── __init__.py
│   ├── filter_policy.py
│   └── export_limit_policy.py
└── serializers/
    ├── __init__.py
    ├── csv_serializer.py
    └── xlsx_serializer.py

backend/tests/
├── test_reporting_policies.py
└── test_reporting_serializers.py
```

## 3. Report Filter Policy

`ReportFilterPolicy` 从注入的 `FilterRegistryLike` 获取当前 Report Type 的 Filter 定义。Registry 最小接口为：

```python
get_filter_definitions(report_type) -> tuple[FilterDefinitionLike, ...]
```

Filter Definition 声明：

- `key`；
- `value_type`：`STRING`、`INTEGER`、`DATETIME`、`ENUM`；
- `required`；
- `default`；
- `allowed_values`。

Policy 行为：

- 只接受 Registry allowlist；
- 未支持字段返回 `UNSUPPORTED_REPORT_FILTER`；
- 必填缺失返回 `MISSING_REQUIRED_FILTER`；
- 无效类型或格式返回 `INVALID_FILTER_VALUE`；
- naive datetime 被拒绝，aware datetime 规范化为 UTC；
- `start_time > end_time` 返回 `INVALID_FILTER_RANGE`；
- Enum 必须属于 Registry 声明集合；
- 正整数不接受布尔值或零；
- 输出为 immutable `ValidatedFilters`，key 使用稳定排序；
- 默认值与用户显式 Filter 分开记录，默认值不构成“有效 Filter”。

`FilterValidationError` 提供稳定 `code`、`field` 和 `message`，供后续 API 层映射；Policy 本身不生成 HTTP Response。

禁止自由 SQL、自由字段、自由排序、文本推断、数据查询或业务判断。

## 4. Export Limit Policy

`ExportLimitPolicy` 版本为 `Export Limit Policy V1.0`，只做确定性规则判断，不生成文件。

冻结常量：

| 限制 | 值 |
| --- | ---: |
| 直接导出最大行数 | 1,000 |
| CSV硬上限 | 10,000行 |
| XLSX硬上限 | 5,000行 |
| 文件硬上限 | 25 MiB |
| 内存Spool阈值 | 5 MiB |

决策：

- 零行：`REJECT / EMPTY_REPORT`；
- 超过格式行数硬上限：`REJECT / EXPORT_LIMIT_EXCEEDED`；
- 无显式 Filter 或超过1,000行：`REQUIRE_CONFIRMATION / EXPORT_CONFIRMATION_REQUIRED`；
- `confirmed_row_count` 与重新 Count 不一致：继续要求确认；
- 行数在硬上限内且确认数一致：`ALLOW`；
- 文件超过25 MiB：`REJECT / EXPORT_SIZE_LIMIT_EXCEEDED`。

Policy 提供纯数学文件大小估算方法；最终字节上限仍须在 Serializer 完成、HTTP Header 发送前再次检查。用户确认不能绕过硬上限。

## 5. Serializer Contract

`ReportSerializer` 统一接口：

```python
serialize(rows, schema) -> SerializedReport
```

Schema 由外部 Registry/Contracts 提供：

- 有序 `columns`；
- 每列 `key`、`title`、`column_type`、`nullable`；
- XLSX固定 `sheet_name`。

Row 必须与 Schema key 精确一致；缺失或额外字段均失败。Serializer 不推断字段或类型。

支持列类型：

- `STRING`；
- `INTEGER`；
- `DECIMAL`；
- `BOOLEAN`；
- `DATE`；
- `DATETIME`。

`SerializedReport` 持有请求期 `SpooledTemporaryFile`、MIME、扩展名和字节数，提供分块迭代与显式 `close()`/context manager。调用方必须在响应完成或失败时关闭资源。

## 6. CSV Serializer

`CsvReportSerializer` 使用标准库 `csv.writer`：

- UTF-8 with BOM；
- 记录分隔固定 CRLF；
- 逗号、双引号和内嵌换行由标准 writer 处理；
- Header 严格按 Schema 顺序；
- nullable列的 `None` 输出空单元格；
- non-nullable列的 `None` 直接失败；
- V1拒绝有业务意义的空字符串；
- Decimal保留十进制文本；
- Boolean输出小写 `true` / `false`；
- datetime必须 timezone-aware，并输出UTC ISO 8601 `Z`格式；
- 不进行字符串数值推断。

MIME：`text/csv; charset=utf-8`；扩展名：`.csv`。

## 7. XLSX Serializer

`XlsxReportSerializer` 使用已有 `openpyxl`：

- `Workbook(write_only=True)`；
- 行从 iterable 逐条消费，不把完整数据集放入列表；
- 输出到请求期 Spooled Temporary File；
- 固定并验证安全 Sheet Name；
- 不创建公式、宏、外部链接或隐藏 Sheet；
- 文本危险前缀按纯文本处理；
- nullable `None` 保持空单元格；
- datetime输出UTC ISO 8601文本；
- Workbook属性时间固定，避免业务输出依赖当前时间。

MIME：`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`；扩展名：`.xlsx`。

## 8. Security Controls

### 8.1 Formula Injection

字符串忽略前导空白后，如首字符为下列任一值，则在完整原字符串前加单引号：

- `=`；
- `+`；
- `-`；
- `*`；
- `@`。

防护同时用于 CSV 和 XLSX。Serializer 不删除内容、不执行公式，也不把非字符串列按文本猜测。

### 8.2 NULL and Type Safety

NULL只能由 Schema 的 `nullable=True` 明确授权。`None` 不会变成 0、false 或字符串 `NULL`。类型与 Schema 不一致时立即失败，不进行隐式修复。

### 8.3 Resource Safety

- 默认5 MiB以内使用内存，超过后由 `SpooledTemporaryFile` 转入操作系统临时存储；
- 不使用固定文件路径；
- 生成异常会关闭流；
- `SerializedReport`支持显式关闭；
- 最终25 MiB限制由 Export Limit Policy 在发送 Header 前检查。

## 9. Architecture Boundaries

Policy/Serializer代码没有：

- SQLAlchemy、ORM、Session；
- Repository、Provider、ReportingService；
- query、execute、commit、rollback或数据库flush；
- 网络、当前时间或随机数；
- Migration、持久化目录或数据库写入。

唯一跨目录依赖是 Serializer 使用 Export Policy 冻结的 Spool 阈值常量，方向符合 `Policies → Serializers`。

## 10. Tests

专项测试覆盖：

- allowlist、默认值、显式Filter、类型、Enum、aware UTC与时间范围；
- Missing/Unsupported/Invalid结构化错误；
- 直接导出、确认重计数、格式硬上限、精确边界、空报告与25 MiB限制；
- CSV BOM、CRLF、Unicode、quote、NULL、zero/false与公式注入；
- XLSX生成、MIME、纯文本公式防护、NULL、write-only流式输入和磁盘rollover；
- 资源关闭；
- Policy/Serializer无数据层、事务或业务Service依赖；
- 相同CSV输入产生相同字节结果。

验证结果：

```text
30 passed
```

执行命令：

```text
backend/.venv/Scripts/python.exe -m pytest \
  tests/test_reporting_policies.py \
  tests/test_reporting_serializers.py \
  -q -W error::pytest.PytestUnraisableExceptionWarning
```

## 11. Current Limitation and Next Step

当前仓库尚无 Reporting Contracts / Schema Registry 正式实现；本阶段使用的 Protocol 已冻结其最小消费接口，但不能代替 Registry 本身。进入 Repository + Providers 前，应先确认 Contracts/Registry 已获授权并实现，否则只能编写孤立的数据读取组件，无法完成端到端类型接合。

本阶段未实现 Repository、Providers、ReportingService、API 或 Frontend。
