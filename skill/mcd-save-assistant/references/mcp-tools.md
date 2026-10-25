# 麦当劳 MCP 工具参考

接入地址：`https://mcp.mcd.cn`，Streamable HTTP，请求头 `Authorization: Bearer <MCP_TOKEN>`。
限流：600 次/分钟（超限返回 429）。Token 无效/过期返回 401。

## 通用参数速查

| 参数 | 取值 | 含义 |
|---|---|---|
| orderType | 1 / 2 | 1=到店，2=外送 |
| beType | 1 / 2 / 5 / 6 | 1=到店取餐，2=麦乐送到家，5=得来速(DT)，6=企业团餐 |
| searchType | 1 / 2 | 1=搜索收藏餐厅，2=按位置搜索 |
| reservationDate | yyyy-MM-dd HH:mm | 仅预约场景必填 |

## 点餐链路工具

### list-nutrition-foods（餐品营养信息）
- 入参：无
- 返回：TOON 紧凑格式，字段 `productName, nutritionDescription, energyKj, energyKcal, protein, fat, carbohydrate, sodium, calcium`

### delivery-query-addresses（可配送地址列表）
- 入参：无
- 返回：`data.addresses[]` → `addressId, contactName, phone, fullAddress`

### delivery-create-address（新增配送地址）
- 入参：`city`、`contactName`、`gender`(选)、`phone`(11位数字)、`address`、`addressDetail` 均必填（除 gender）
- 返回：新 `addressId`

### delivery-query-stores（外送可配送门店）
- 入参：`addressId` 必填，`beType` 必填（2=麦乐送，6=企业团餐）
- 返回：门店列表含 `storeCode`、`beCode`、`businessStatus`、`reservationTimeOptions`

### query-nearby-stores（附近门店，到店场景）
- 入参：`searchType` 必填，`beType` 必填（1=到店自取，5=DT），`city`+`keyword` 仅 searchType=2 必填
- 返回：门店列表含 `storeCode`、`beCode`、`storeName`、`businessStatus`

### query-store-coupons（当前门店可用券）
- 入参：`storeCode`、`beCode`、`orderType`、`beType`、`reservationDate`(预约时)
- 返回：券列表含 `title`、`couponId`、`couponCode`、`products[]`（适用商品 productCode/productName）

### query-meals（可售餐品列表）
- 入参：`storeCode`、`beCode`、`orderType`、`beType`、`reservationDate`(预约时)
- 返回：`data.categories[]`（name/meals[]/daypart）+ `data.meals{}`：
  - `name`、`currentPrice`、`originalPrice`、`discountType`（null/促销优惠/麦金卡优惠/随单购麦金卡优惠）
  - `isCanWithOrder`、`withOrder`（cardId/cardType/membershipCode/specId）——随单购需带入算价和下单

### query-meal-detail（餐品详情）
- 入参：`code`、`storeCode`、`beCode`、`orderType`、`beType`、`reservationDate`(预约时)
- 返回：`name`、`price`、`image`、`modification.items[]`（可换项 maxValues/minValues/values[]）、`supportModify`

### calculate-price（价格计算）
- 入参：`storeCode`、`beCode`、`orderType`、`beType`、`reservationDate`(预约时)、`gmServiceCode`(团餐)、`withOrder`(随单购)、`items[]`
- items 元素：`productCode` 必填、`quantity` 必填、`couponId` 选填、`couponCode` 选填、`modification`(特调)、`roundList`(子项)
- modification：`values[]` → `code`、`quantity`、`key`
- roundList：`round`、`comboItemList[]` → `code`、`quantity`、`modification`
- 返回：`productPrice`、`deliveryPrice`、`originalPrice`、`discount`、`price`（应付）、`takeWayList`（到店取餐方式）、`mealAssistanceList`（团餐）

### create-order（创建订单）
- 入参：`storeCode`、`beCode`、`beType`、`addressId`(外送必填)、`takeWayCode`(到店必填，取自算价响应)、`reservationDate`(预约时)、`gmServiceCode`(团餐必填)、`withOrder`、`items[]`（结构同算价）
- 返回：`orderId`、`payId`、`payH5Url`（支付链接）、`orderDetail`（订单状态=待支付、takeWay、lockerCode 等）

### query-order（订单详情）
- 入参：`orderId` 必填
- 返回：订单状态、商品、金额、配送信息

### order-list（历史订单）
- 入参：无
- 返回：最近 10 笔订单（非商城订单）

## 互动与内容工具

- **campaign-calendar**：活动日历。入参 `specifiedDate`(选，yyyy-MM-dd，默认当月)。返回进行中/往期/未来活动文案。
- **query-lottery-info**：积分抽奖信息。入参：无。
- **draw-lottery**：执行抽奖。入参：无。注意 1 秒内不可重复调用。
- **query-my-prizes**：我的奖品。入参 `pageNum`(选)、`pageSize`(选，默认10最大20)。

## 麦麦省领券工具

- **available-coupons**：可领券列表。入参：无。
- **auto-bind-coupons**：一键领取所有可领券。入参：无。返回成功/失败数量与 couponId/couponCode。
- **query-my-coupons**：我的可用券列表。入参：无。

## 麦麦商城工具

- **query-my-account**：积分账户。入参：无。返回 availablePoint 等。
- **mall-points-products**：商城商品列表。入参 `catRuleIds`(选，逗号分隔，如 `1>4,2`)。
- **mall-product-detail**：商品详情。入参 `spuId` 必填。
- **mall-create-order**：积分兑换下单。入参 `skuId` 必填、`count`(选)、`addressId`(实物必填)、`spuCategory`(1虚拟/2实物)。
- **mall-order-list / mall-order-detail**：商城订单查询。

## 主题活动工具

- **query-party-city** → **query-party-store** → **query-partystore-date** → **query-partystore-session** → **party-order-create**（城市→门店→日期→场次→下单），仅主题活动场景使用。

## 通用工具

- **now-time-info**：当前时间。入参：无。
