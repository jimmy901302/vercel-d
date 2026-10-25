# MCP_INTEGRATION

**麦当劳 MCP 集成技术说明 —— 麦门营养管家**

本文档说明「麦门营养管家」如何接入麦当劳官方 MCP Server，包括接入配置、使用的工具、调用链路与错误处理。作品卖点：**预算内最划算 + 热量内最健康**，营养约束基于官方营养接口数据。

## 1. 接入配置

### 1.1 连接信息（来源：<https://open.mcd.cn/mcp/doc>）

| 项 | 值 |
|---|---|
| 服务器接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | HTTP Header `Authorization: Bearer <MCP_TOKEN>` |
| 限流 | 600 次/分钟（超限返回 429） |

### 1.2 WorkBuddy 连接器配置

在 WorkBuddy **专家·技能·连接器 → 连接器 → 自定义连接器 → 配置 MCP** 中粘贴：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

> **安全说明**：`YOUR_MCP_TOKEN` 必须替换为用户本人申请的 Token（申请地址 <https://open.mcd.cn/mcp>，手机号登录 → 控制台 → 激活 → 复制）。Token 仅存在于用户自己的 WorkBuddy 连接器配置中，**绝不写入代码仓库或任何提交文件中**。

## 2. 使用的 MCP 工具

本作品主链路使用以下工具（完整 35 个工具的参考见 `skill/mcd-save-assistant/references/mcp-tools.md`）：

### 2.1 领券链路

| 工具 | 用途 |
|---|---|
| `available-coupons` | 查询当前可领的麦麦省券列表 |
| `auto-bind-coupons` | 一键领取所有可领券 |
| `query-my-coupons` | 查询用户当前可用券 |

### 2.2 门店与菜单链路

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `query-nearby-stores` | 到店/DT 场景查附近门店 | `searchType=2`, `beType=1或5`, `city`, `keyword` |
| `delivery-query-addresses` | 查可配送地址 | 无 |
| `delivery-create-address` | 新增配送地址 | `city/contactName/phone/address/addressDetail` |
| `delivery-query-stores` | 外送场景查可配送门店 | `addressId`, `beType=2` |
| `query-meals` | 查可售餐品列表（含现价/原价/优惠类型） | `storeCode`, `beCode`, `orderType`, `beType` |
| `query-meal-detail` | 查套餐组成/可换项 | `code`, 门店与业务参数 |
| `query-store-coupons` | 查当前门店可用券 | `storeCode`, `beCode`, `orderType`, `beType` |

### 2.3 算价与下单链路

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `calculate-price` | 商品价格计算（含券、配送费、随单购） | `storeCode`, `beCode`, `orderType`, `beType`, `items[]` |
| `create-order` | 创建订单，返回支付链接 | 同算价 + `addressId`（外送）/ `takeWayCode`（到店） |
| `query-order` | 查询订单详情 | `orderId` |
| `order-list` | 查询历史订单 | 无 |

### 2.4 营养与增强能力

| 工具 | 用途 |
|---|---|
| `list-nutrition-foods` | 餐品营养信息（能量/蛋白/脂肪/碳水/钠/钙），**健康双目标比价的数据源** |
| `campaign-calendar` | 当月营销活动日历 |
| `query-my-account` | 积分查询 |
| `now-time-info` | 当前时间 |

## 3. 核心调用链路

```
用户需求（预算/人数/口味/忌口/就餐方式 + 可选营养目标：max-kcal / min-protein）
        │
        ▼
available-coupons → auto-bind-coupons → query-my-coupons   [第1步：先领券]
        │
        ▼
query-nearby-stores (到店)  /  delivery-query-addresses → delivery-query-stores (外送)
        │
        ▼
query-meals + query-store-coupons + list-nutrition-foods   [第2步：菜单+门店可用券+官方营养数据]
        │
        ▼
save_optimizer.py（离线枚举，预算+营养双约束） + calculate-price（实时验证）
        │                                                   [第3步：省钱+健康比价]
        ▼
输出 3 套方案（最便宜/最划算/最丰盛，含 kcal / protein / 每元蛋白），用户确认
        │
        ▼
create-order → 引导用户到麦当劳 APP 订单页支付          [第4步：下单支付]
```

> **支付坑（实测）**：`create-order` 返回的 `payH5Url` 是**扫码引导页而非支付页**，打开后还会显示二维码让麦当劳 APP 扫（手机端套娃）。正确做法是引导用户到**麦当劳 APP 订单页**完成支付；订单约 15 分钟支付窗口，超时自动取消不扣款。

## 4. 参数约定

| 参数 | 取值 | 含义 |
|---|---|---|
| `orderType` | 1 / 2 | 1=到店，2=外送 |
| `beType` | 1 / 2 / 5 / 6 | 1=到店取餐，2=麦乐送到家，5=得来速(DT)，6=企业团餐 |
| `searchType` | 1 / 2 | 1=搜索收藏餐厅，2=按位置搜索 |
| `reservationDate` | `yyyy-MM-dd HH:mm` | 仅预约场景必填 |

## 5. 错误处理

| 错误码 | 原因 | 处理 |
|---|---|---|
| 401 | Token 无效/过期/缺失 | 提示用户检查 Authorization 头与 Token 配置 |
| 429 | 触发限流（>600 次/分钟） | 放缓调用频率，使用离线比价引擎减少试算 |

## 6. 合规要点

1. 本作品通过用户本人 Token 访问，所有操作（领券、下单、新增地址）均在用户明确确认后执行。
2. 不使用、不存储、不泄露任何人的 Token 与隐私数据。
3. 离线演示样本（`samples/`）仅用于展示算法，不产生任何真实订单。
