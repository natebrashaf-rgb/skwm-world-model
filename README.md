# 🌍 中阿文旅世界模型 - 部署指南

## 本地运行

```bash
cd deploy

# 方式1：仅知识库查询（不需要 DeepSeek Key）
python3 app.py

# 方式2：带 DeepSeek 推理
DEEPSEEK_API_KEY="sk-你的key" python3 app.py

# 方式3：自定义端口
PORT=3000 DEEPSEEK_API_KEY="sk-你的key" python3 app.py
```

然后打开浏览器访问 `http://localhost:8080`

---

## 🚀 部署到 Railway（给所有人用）

### 第一步：注册 Railway

1. 打开 https://railway.app
2. 用 GitHub 账号登录（没有就注册一个）
3. 免费套餐每月 **$5 或 500小时**，够用了

### 第二步：上传代码

**方法 A：通过 GitHub（推荐）**

```bash
# 在你的电脑上
cd deploy
git init
git add .
git commit -m "中阿文旅世界模型"
# 在 GitHub 新建仓库，然后推上去
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

然后在 Railway 点击 **New Project → Deploy from GitHub repo**，选你的仓库。

**方法 B：直接上传文件夹**

Railway 支持直接拖拽上传整个 `deploy/` 文件夹。

### 第三步：设置环境变量

在 Railway 项目设置中，添加：

| 变量名 | 值 | 必填？ |
|--------|-----|-------|
| `DEEPSEEK_API_KEY` | `sk-4c115205e2c14ca79347838aaeca283a` | 可选（不设置则无AI推理） |

### 第四步：部署完成！

Railway 会自动：
1. 检测到 `railway.json` 配置文件
2. 运行 `python3 app.py`
3. 生成一个 **https://你的项目名.up.railway.app** 的公开链接

把这个链接发给任何人，他们就能用你的世界模型了！

---

## 项目结构

```
deploy/
├── app.py              # 主程序（零外部依赖）
├── railway.json        # Railway 配置文件
├── requirements.txt    # 依赖说明（空的）
└── data/
    ├── literature_catalog.md          # 200篇中阿文旅文献
    └── _arabic_bulk_metadata.json     # 4194篇阿语文献元数据
```

## 注意

- 本部署版**不包含 1148 份 PDF**（太大了），只包含文本元数据
- 如果你想包含 PDF，需要自己上传到对象存储（如 AWS S3）
- DeepSeek Key 在 Railway 用环境变量设置，**不要写在代码里**
