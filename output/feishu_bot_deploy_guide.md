# SKWM 飞书学科服务机器人部署指南

## 一、飞书后台配置

### 1.1 创建自定义机器人（如果从未配置）

1. 打开飞书桌面版 → 进入群聊
2. 群设置 → **群机器人** → **添加机器人** → **自定义机器人**
3. 填写名称: `SKWM 学科服务`
4. 复制 **Webhook URL**
5. 点击**完成**

### 1.2 配置到 Railway

```bash
# 在 Railway 后台添加环境变量
FEISHU_WEBHOOK_URL = https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook_id
```

### 1.3 验证配置

```bash
# 发送测试消息到飞书群
curl -X POST https://你的railway域名/api/feishu/push-test

# 或在飞书群里 @机器人
```

---

## 二、可用命令

| 命令 | 效果 | 角色 |
|:-----|:-----|:----:|
| `@SKWM 中阿文旅热点` | 带来源卡片的智能问答 | 学生(默认) |
| `@SKWM 教师：中阿文旅热点` | 教师版：含方法论与数据溯源 | 教师 |
| `@SKWM 学生：文化遗产数字化` | 学生版：含概念解释 | 学生 |
| `@SKWM 馆员：学科服务趋势` | 馆员版：含审核状态 | 馆员 |
| `@SKWM 热点` | 查看当前研究热点 | 通用 |
| `@SKWM 前沿` | 查看新兴前沿方向 | 通用 |

---

## 三、API 端点

| 端点 | 方法 | 说明 |
|:-----|:----:|:-----|
| `/api/feishu/webhook` | POST | 飞书事件回调入口 |
| `/api/feishu/push-test` | GET | 发送测试消息 |
| `/api/feishu/push-weekly` | GET | 推送周报（热点+前沿） |
| `/api/feishu/subscriptions` | GET | 查看订阅配置 |

---

## 四、每周自动推送

通过 Railway Cron Job 实现：

```bash
# Railway 后台 → Cron Jobs → 新建
Schedule: 0 9 * * 1     # 每周一早9点
Command: curl https://你的域名/api/feishu/push-weekly
```

或通过 Hermes cronjob 配置：

```bash
hermes cronjob create \
  --name "skwm-feishu-weekly" \
  --schedule "0 9 * * 1" \
  --prompt "调用 /api/feishu/push-weekly 推送本周研究热点与前沿周报到飞书群"
```

---

## 五、卡片按钮功能

| 按钮 | 功能 |
|:-----|:-----|
| 📥 存入知识库 | 一键沉淀到 Obsidian 目录 |
| 📋 查看详情 | 调起详情面板 |
| ❌ 不相关 | 标记为不相关（审核辅助） |
| 📥 收藏周报 | 收藏周报到知识库 |

---

## 六、架构图

```
飞书群
  │ @机器人
  ▼
/api/feishu/webhook
  │ POST
  ▼
FeishuBotV2.handle_webhook()
  ├─ URL验证 → {challenge}
  ├─ 按钮回调 → sediment/detail/flag
  └─ 消息处理
       ├─ 解析文本 + 角色
       ├─ GraphRAG.ask() → 溯源回答
       └─ 构建卡片 → 返回飞书

每周自动
  │ cron
  ▼
/api/feishu/push-weekly
  │ 热点TOP5 + 前沿TOP5
  ▼
交互式卡片（含沉淀按钮）
