# Options Provider

Unified options analysis service integrating **Bridge API** (volatility_analysis) and **ORATS** data sources.

## Architecture

```
options_provider/
├── start.sh                 # ⚡ One-command launcher (bash)
├── cli.py                   # ⚡ Unified CLI entry point (python)
├── Makefile                 # ⚡ Quick make commands
├── pyproject.toml           # ⚡ Modern packaging + entry points
├── .env.example             # ⚡ Environment template
│
├── bridge_provider/         # Bridge API client + middleware + boundary engine
│   ├── models.py            # BridgeSnapshot / MicroBoundary dataclass family
│   ├── client.py            # BridgeClient + AsyncBridgeClient
│   ├── bridge_builder.py    # Bridge record → snapshot builder
│   ├── micro_templates.py   # Template selection (zero core dependency)
│   ├── contracts.py         # Pydantic batch request/response contracts
│   ├── dispatcher.py        # Batch dispatch by source (swing / vol)
│   ├── boundary_engine.py   # Micro boundary computation engine
│   ├── boundary_rules.yaml  # Centralized boundary rule configuration
│   └── adapters/
│       ├── swing.py         # Swing-specific row builder
│       └── vol.py           # Vol-specific row builder
│
├── orats_provider/          # ORATS data provider
│   ├── config.py            # API config + field mappings
│   ├── models.py            # 6 data models + 2 result models
│   ├── cache.py             # Thread-safe TTL cache
│   ├── utils.py             # Filtering + grouping utilities
│   ├── client.py            # OratsClient + AsyncOratsClient
│   ├── greeks_exposure/     # GEX/DEX/VEX/Vanna calculator
│   │   ├── calculator.py    # 9 computation functions
│   │   ├── commands.py      # Command pipeline
│   │   └── formatter.py     # Output formatting
│   └── volatility/          # Skew/Term/Surface analyzer
│       ├── analyzer.py      # Analysis functions
│       ├── commands.py      # Command pipeline
│       └── formatter.py     # Output formatting
│
├── provider/                # Unified provider
│   └── unified.py           # UnifiedProvider (fault-tolerant)
│
├── api/                     # FastAPI service
│   ├── main.py              # App + lifespan + /full endpoint
│   ├── dependencies.py      # Shared provider singleton
│   └── routes/
│       ├── bridge.py        # /api/v1/bridge/*
│       ├── greeks.py        # /api/v1/greeks/{cmd}/{sym}
│       └── volatility.py    # /api/v1/volatility/{cmd}/{sym}
│
└── tests/
    ├── test_micro_boundary.py   # MicroBoundary model + contract tests
    └── test_boundary_engine.py  # Boundary engine computation tests
```

## 消费端调用 Bridge Provider 任务处理逻辑

下游工作流（swing_workflow / vol_quant_workflow）通过 bridge_provider 获取 bridge 数据和 micro boundary 决策。
整体流程按以下阶段执行：

### 总览流程

```
Consumer (swing / vol_quant workflow)
  │
  ├─ POST /api/bridge/batch  ←  BatchRequest { source, date, symbols, ... }
  │
  ▼
API Route (routes/bridge.py)
  │
  ├─ BridgeClient.get_records()   ← 从 volatility_analysis 拉取全量 VA records
  │
  ▼
Dispatcher (dispatcher.py)  dispatch_by_source(req, records)
  │
  ├─ 1. 日期解析       _resolve_date()
  ├─ 2. Symbol 筛选    按 symbols 白名单过滤
  ├─ 3. Source 过滤     _filter_for_source() — bias / score 门控
  ├─ 4. Row 构建        adapters/swing.py  or  adapters/vol.py
  ├─ 5. Boundary 计算   boundary_engine.compute_micro_boundary()
  ├─ 6. 排序 + 截断     symbol asc → limit 截断
  │
  ▼
BatchResponse { success, source, date, results: [SwingBatchRow | VolBatchRow], errors }
```

### 阶段 1：请求入口

消费端构造 `BatchRequest` 发送到 `POST /api/bridge/batch`：

```python
BatchRequest(
    source="swing" | "vol",       # 决定过滤逻辑和 row 结构
    date="2025-05-30" | None,     # 指定日期（None → 取最新）
    symbols=["AAPL", "TSLA"],     # 指定标的（空 → 全量）
    limit=50,                     # 结果上限
    min_direction_score=0.55,     # 方向分门控（swing 用）
    min_vol_score=0.12,           # 波动分门控（vol 用）
    vix_override=None,            # 覆写 VIX（仅 swing）
    filtering={},                 # 扩展过滤（如 strict_date）
    sorting={},                   # 扩展排序
)
```

### 阶段 2：Records 拉取

API 路由通过 `BridgeClient.get_records()` 从 volatility_analysis 服务获取全量分析记录。
每条 record 是一个 dict，包含 `symbol`, `timestamp`, `direction_score`, `vol_score`, `direction_bias`, `vol_bias`, `quadrant`, `confidence`, `liquidity`, `raw_data`, `bridge` 等字段。

### 阶段 3：Dispatcher 处理 — `dispatch_by_source(req, records)`

Dispatcher 是消费端任务处理的核心编排层，按以下步骤执行：

#### 3.1 日期解析

```
available_dates = 从 records 提取所有 trade_date，降序排列
resolved_date, fallback_used = _resolve_date(req.date, available_dates)
```

解析规则：无指定日期 → 取最新日期；指定日期存在 → 精确匹配；指定日期不存在 → 回退到最近的较早日期（除非 `strict_date=true`）。

#### 3.2 Symbol 筛选

如果 `req.symbols` 非空，按白名单过滤 records。不在该日期中的 symbol 会生成 `SYMBOL_NOT_FOUND` 错误条目。
如果 `req.symbols` 为空，使用该日期的全量 records。

#### 3.3 Source 过滤 — `_filter_for_source()`

根据 `source` 类型应用不同的 bias + score 门控：

| 条件 | source=swing | source=vol |
|---|---|---|
| direction_bias | ∈ {偏多, 偏空} | ∈ {偏多, 偏空} |
| vol_bias | == 买波 | == 卖波 |
| score 门控 | \|direction_score\| ≥ min_direction_score (0.55) | \|vol_score\| ≥ min_vol_score (0.12) |

Bias 解析回退：如果 `direction_bias` / `vol_bias` 缺失，从 `quadrant` 字段推断（如 `"偏多—买波"` → `direction_bias=偏多`, `vol_bias=买波`）。

#### 3.4 Row 构建 — Source Adapter

通过 `adapters/` 下的适配器将 VA record 转换为标准化的 row 结构。

**Swing 适配器** (`adapters/swing.py` → `to_swing_row`)：

```python
{
    "symbol": "AAPL",
    "market_params": {                   # swing 工作流专用参数
        "vix": 18.5,                     # 支持 vix_override
        "ivr": 45.2,
        "iv30": 0.28,
        "hv20": 0.22,
        "iv_path": "Rising" | "Flat" | "Falling",  # 从 term_structure ratio 推断
        "earning_date": "2025-07-24",
        "beta": 1.15
    },
    "bridge": { ... },                   # 完整 bridge payload（见下）
    "micro_boundary": { ... }            # 阶段 3.5 计算后附加
}
```

**Vol 适配器** (`adapters/vol.py` → `to_vol_row`)：

```python
{
    "symbol": "AAPL",
    "bridge": { ... },                   # 完整 bridge payload
    "micro_boundary": { ... }            # 阶段 3.5 计算后附加
}
```

两种适配器都通过 `build_bridge_payload()` 构建标准化 bridge payload。Bridge payload 由四个子状态块组成：

```python
bridge = {
    "symbol": "AAPL",
    "as_of": "2025-05-30",
    "market_state": {                    # 市场状态
        "symbol", "as_of", "vix", "ivr", "iv30", "hv20"
    },
    "event_state": {                     # 事件状态
        "earnings_date", "days_to_earnings", "is_earnings_window",
        "is_index", "is_squeeze"
    },
    "execution_state": {                 # 执行状态（boundary engine 主要输入）
        "quadrant", "direction_score", "vol_score",
        "direction_bias", "vol_bias",
        "confidence", "confidence_notes",
        "liquidity", "active_open_ratio", "oi_data_available",
        "data_quality", "trade_permission",
        "flow_bias", "posture_5d", "fear_regime"
    },
    "term_structure": {                  # 期限结构
        "label_code", "ratio", "adjustment",
        "horizon_bias", "state_flags"
    }
}
```

#### 3.5 Micro Boundary 计算 — `boundary_engine.compute_micro_boundary()`

Boundary engine 基于 bridge payload + `boundary_rules.yaml` 中心化规则，计算出 `MicroBoundary` 并附加到 row 上。整个计算流程包含 13 个子步骤：

```
bridge payload + boundary_rules.yaml
  │
  ├─  0. 缺失字段检测       _find_missing_fields()
  ├─  1. Meso State 推导    direction_bias + vol_bias → "偏多-买波" 等
  ├─  2. 方向范围            DirectionalRange (upper/lower/bias)
  ├─  3. 波动率范围          VolRange (iv/rv/vrp/vrp_regime)
  ├─  4. 流动性边界          LiquidityBoundary (strikes_ceiling, is_sufficient)
  ├─  5. OI 可用性           OIAvailability (strikes_cap)
  ├─  6. 置信度门控          ConfidenceBoundary (gate_passed, recommended_context)
  ├─  7. 时间边界            TemporalBoundary (earnings_window, dte_cluster)
  ├─  8. 期限结构            TermStructureBoundary (scale_factors)
  ├─  9. 有效 Strikes        min(liquidity_ceil, oi_cap) → clamp [7, 31]
  ├─ 10. 有效 Context        blocked > event > minimum > standard
  ├─ 11. Strategy Overlay    SwingOverlay (scenario) + VolQuantOverlay (gexbot_context)
  ├─ 12. 降级状态            Degradation (full/partial/fallback/blocked)
  └─ 13. 元数据              BoundaryMetadata (completeness, version)
```

输出的 `MicroBoundary` 结构：

```python
MicroBoundary(
    ticker="AAPL",
    timestamp="2025-05-30",
    meso_state="偏多-买波",              # 方向 + 波动维度组合
    base_boundary=BaseBoundary(
        directional=DirectionalRange(upper, lower, bias, direction_score, direction_bias),
        vol_range=VolRange(iv_current, iv_low, iv_high, rv_ref, vrp, vrp_regime, ivr, vol_score, vol_bias),
        liquidity=LiquidityBoundary(raw_label, score, tier, is_sufficient, strikes_ceiling),
        oi=OIAvailability(available, strikes_cap, concentration),
        confidence=ConfidenceBoundary(level, gate_passed, gate_threshold, recommended_context),
        temporal=TemporalBoundary(earnings_window, days_to_earnings, dte_cluster, is_index, is_squeeze),
        term_structure=TermStructureBoundary(label_code, adjustment, state_flags, scale_factors),
    ),
    effective_strikes=17,                # 综合流动性 + OI 后的实际 strikes 上限
    effective_context="standard",        # 综合置信度 + 时间 + 权限后的最终 context
    strategy_overlay=StrategyOverlay(
        swing=SwingOverlay(scenario, suggested_dyn_params),       # swing 场景 + 动态参数
        vol_quant=VolQuantOverlay(gexbot_context, horizon_scales), # gexbot context + scale
    ),
    degradation=Degradation(mode, missing_fields, fallback_rules_applied, warnings),
    metadata=BoundaryMetadata(data_completeness, source_freshness, boundary_version),
)
```

**关键规则 (boundary_rules.yaml)：**

| 规则维度 | 说明 |
|---|---|
| 流动性 → strikes | excellent=21, good=17, fair=13, poor=9; poor+买波 → blocked |
| OI 不可用 | strikes_cap=11 |
| 置信度门控 | 买波 ≥ 0.35, 卖波 ≥ 0.50; < 0.20 → blocked |
| 财报窗口 | ≤ 14 天 → event context; ≤ 3 天 → event_imminent |
| 数据质量 | poor → confidence × 0.80 |
| 期限结构 scale | full_inversion → gex×0.70, skew×0.80 等 |
| Strikes clamp | [7, 31] |
| 降级优先级 | blocked > fallback > partial > full |

**容错设计：** boundary 计算失败不会丢弃 row，而是将 `micro_boundary` 设为 `null` 并记录 `BOUNDARY_COMPUTE_FAILED` 错误。

#### 3.6 排序与截断

所有 row 按 symbol 升序排列，然后按 `req.limit` 截断。

### 阶段 4：Response 输出

最终返回 `BatchResponse`：

```python
BatchResponse(
    success=True,
    source="swing" | "vol",
    date="2025-05-30",                   # 实际使用的日期
    requested_date="2025-05-30",         # 请求的日期
    fallback_used=False,                 # 是否发生了日期回退
    count=12,
    results=[SwingBatchRow(...) | VolBatchRow(...)],
    errors=[BatchError(code, symbol, message, detail), ...],
)
```

错误码包括：`INVALID_SOURCE`, `NO_AVAILABLE_DATE`, `SYMBOL_NOT_FOUND`, `ROW_BUILD_FAILED`, `BOUNDARY_COMPUTE_FAILED`。

### 消费端调用示例

**Swing 工作流调用：**

```python
from bridge_provider import BatchRequest, dispatch_by_source

req = BatchRequest(
    source="swing",
    symbols=["AAPL", "TSLA", "NVDA"],
    min_direction_score=0.55,
    vix_override=20.0,
)

# records 从 BridgeClient.get_records() 获取
response = dispatch_by_source(req, records)

for row in response.results:
    symbol = row.symbol
    market_params = row.market_params   # vix, ivr, iv30, hv20, iv_path, earning_date
    bridge = row.bridge                 # 完整 bridge payload
    mb = row.micro_boundary             # MicroBoundary dict (or None)

    if mb and mb["degradation"]["mode"] != "blocked":
        strikes = mb["effective_strikes"]
        context = mb["effective_context"]
        scenario = mb["strategy_overlay"]["swing"]["scenario"]
        # → 传入 swing 执行层
```

**Vol Quant 工作流调用：**

```python
req = BatchRequest(
    source="vol",
    min_vol_score=0.12,
    limit=30,
)

response = dispatch_by_source(req, records)

for row in response.results:
    bridge = row.bridge
    mb = row.micro_boundary

    if mb and mb["degradation"]["mode"] in ("full", "partial"):
        gexbot_ctx = mb["strategy_overlay"]["vol_quant"]["gexbot_context"]
        scales = mb["strategy_overlay"]["vol_quant"]["horizon_scales"]
        strikes = mb["effective_strikes"]
        # → 传入 gexbot 参数解析器
```

**通过 HTTP 调用：**

```bash
curl -X POST http://localhost:9988/api/bridge/batch \
  -H "Content-Type: application/json" \
  -d '{
    "source": "swing",
    "symbols": ["AAPL", "TSLA"],
    "min_direction_score": 0.55,
    "limit": 20
  }'
```

## Micro Boundary System (v3.0)

The boundary engine centralizes micro boundary decisions that were previously
scattered across downstream workflows (swing_workflow / vol_quant_workflow).

**Data flow:**

```
volatility_analysis record (dict)
  → bridge_builder.build_bridge_response_from_record(record) → bridge_data
  → boundary_engine.compute_micro_boundary(bridge_data) → MicroBoundary
  → attached to SwingBatchRow.micro_boundary / VolBatchRow.micro_boundary
  → consumed by downstream workflows
```

**Key components:**

- `MicroBoundary` — top-level dataclass containing all boundary decisions
- `boundary_rules.yaml` — centralized rule configuration (liquidity, confidence gates, clamps, etc.)
- `boundary_engine.py` — computation engine with graceful degradation
- `degradation.mode` — `full` / `partial` / `fallback` / `blocked`

## Quick Start

### 1. One-Command Setup

```bash
./start.sh setup              # Install deps + create .env (interactive)
# or
./start.sh                    # Interactive menu (auto-detects first run)
```

### 2. Start Server

```bash
# start.sh (recommended)
./start.sh serve              # Foreground server (0.0.0.0:9988)
./start.sh dev                # Dev mode (auto-reload)
./start.sh start-bg           # Background daemon
PORT=9000 ./start.sh serve    # Custom port

# make
make serve                    # Same as ./start.sh serve
make dev                      # Same as ./start.sh dev

# cli.py
python cli.py serve -p 9000   # Custom port
python cli.py s --reload      # Short alias + reload
```

### 3. Run Tests

```bash
./start.sh test               # All tests
./start.sh test -k greeks     # Filter by name
make test                     # All tests
make test-greeks              # Only Greeks tests
make test-boundary            # Boundary engine tests
make test-cov                 # Tests + coverage report
```

### 4. Direct CLI Queries (No Server Needed)

```bash
# start.sh
./start.sh greeks gex AAPL
./start.sh vol skew SPY
./start.sh full TSLA

# cli.py (more options)
python cli.py greeks gex AAPL --dte-max 60
python cli.py vol term QQQ --target-dte 60
python cli.py full TSLA --greeks gex,vanna --vol skew,term
```

### 5. Server Management

```bash
./start.sh start-bg           # Start as background daemon
./start.sh status             # Check server status
./start.sh logs               # Tail server logs
./start.sh health             # HTTP health check
./start.sh stop               # Stop background server
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ORATS_TOKEN` | Yes* | — | ORATS API token (* for Greeks/Vol) |
| `BRIDGE_URL` | No | `http://localhost:8668` | Bridge API URL |
| `ORATS_BASE_URL` | No | `https://api.orats.io/datav2` | ORATS API base URL |

The CLI auto-loads `.env` files — just copy `.env.example` to `.env` and fill in your tokens.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/bridge/snapshot/{symbol}` | GET | Bridge snapshot |
| `/api/v1/bridge/batch` | POST | Batch snapshots (with micro_boundary) |
| `/api/v1/bridge/micro-template/{symbol}` | GET | Micro-template selection |
| `/api/v1/greeks/{command}/{symbol}` | GET | Greeks exposure (9 commands) |
| `/api/v1/volatility/{command}/{symbol}` | GET | Vol analysis (3 commands) |
| `/api/v1/full/{symbol}` | GET | Comprehensive analysis |
| `/health` | GET | Health check |

## Greeks Commands

`gex`, `net_gex`, `gex_distribution`, `gex_3d`, `dex`, `net_dex`, `vex`, `net_vex`, `vanna`

## Volatility Commands

`skew`, `term`, `surface`