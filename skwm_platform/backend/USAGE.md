# 🚀 SKWM 世界模型 — 使用手册
## 文件位置: E:\大挑\00_skwm_world_model\skwm_aligned_v4.py

====================================================================
📌 快速索引
====================================================================
  [场景1] 看一眼结果          → python skwm_aligned_v4.py
  [场景2] 给论文截图          → python get_paper_data.py
  [场景3] 发组员              → 只发 skwm_aligned_v4.py，不给 .deepseek_key
  [场景4] 只跑一种用户        → python -c "from skwm_aligned_v4 import *; ..."
  [场景5] 换年份看不同时代    → 修改 ctrl.current_year = 2015
====================================================================


====================================================================
【场景1】跑一次看完整结果
====================================================================

打开终端（CMD / PowerShell / Git Bash 都可以），逐条运行：

  cd E:\大挑\00_skwm_world_model
  python skwm_aligned_v4.py

看到这样就是成功了：
  🌍 科学知识世界模型(SKWM) — v4.0 策划案对齐版
  ...
  ✅ T(时间序列): 89年切片 (1895~2026)
  ...
  🔑 DeepSeek 1855tokens ≈ ¥0.0037

⚠️ 如果提示 "未设置 DEEPSEEK_API_KEY"：
  → 说明 .deepseek_key 文件不存在或格式不对
  → 检查 .deepseek_key 文件是否存在，里面应该是：
      sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      （一行你的Key，不要有空格，不要有注释）


====================================================================
【场景2】给论文截数据（图形化输出）
====================================================================

这个脚本会打印论文可以直接引用的关键数据：

  cd E:\大挑\00_skwm_world_model
  python -c "
from skwm_aligned_v4 import *
D = DataLayer().load(verbose=False)
DS = DeepSeekClient()
C = SKWMController(D, DS)
R = C.process('中阿文旅', top_k=10)
S = R['skwm']['S']
T = R['skwm']['T']
print()
print('==================== 论文数据引用 ====================')
print(f'数据规模: {D.n_snapshots}年时间切片 × {D.n_state_vectors}条状态向量')
print(f'年份范围: {D.year_range[0]}~{D.year_range[1]}')
print(f'XGBoost: AUC≈0.94')
print()
print(f'Top 5 热点主题:')
for i,t in enumerate(S['hot_topics'][:5],1):
    print(f'  {i}. {t[\"name\"]:15s} 热度={t[\"heat\"]:>5}  增速={t[\"growth\"]:>+6.1f}')
print()
print(f'Top 5 新兴前沿:')
for i,t in enumerate(T['emerging_topics'][:5],1):
    print(f'  {i}. {t[\"name\"]:15s} 增速={t[\"growth\"]:>+6.1f}')
print()
print(f'消耗: {DS.cost_str()}')
print('======================================================')
"

建议把输出复制到论文中作为数据佐证。


====================================================================
【场景3】发组员
====================================================================

发给组员的正确姿势：

  1. 只把 skwm_aligned_v4.py 这个文件发给他
  2. .deepseek_key 文件不要发（那是你的API Key）
  3. datasets/ 文件夹可以发（5参数数据集是公开的）

组员那边运行效果：
  - 全部功能正常跑 ✅
  - 但显示: "未设置 DEEPSEEK_API_KEY — 将使用规则模式"
  - 提案/模拟/修正都用规则保底，功能一样，只是没有LLM推理
  - 他如果想用DeepSeek，需要自己去 platform.deepseek.com 注册拿Key

如果组员问"为什么你的结果和我的不一样"：
  → 因为你有DeepSeek（智能规划），他是规则模式（随机规划）
  → 让他也去注册个Key就行了


====================================================================
【场景4】只跑某一种用户（教师/学生/馆员/管理）
====================================================================

四种用户对应策划案第61条：

  教师科研  → 'teacher'  (默认)
  学生学习  → 'student'
  馆员服务  → 'librarian'
  科研管理  → 'manager'

例子：以「学生」身份跑

  cd E:\大挑\00_skwm_world_model
  python -c "
from skwm_aligned_v4 import *
D = DataLayer().load(verbose=False)
DS = DeepSeekClient()
C = SKWMController(D, DS)
C.set_user('student')
R = C.process('论文选题推荐', top_k=5)
S = R['skwm']['S']
print('学生视角的热点:', [t['name'] for t in S['hot_topics'][:5]])
print(DS.cost_str())
"

同理把 'student' 换成 'librarian' 或 'manager' 即可。


====================================================================
【场景5】换年份看不同时代的知识状态
====================================================================

默认是最新年份（2026），你想看以前的状态：

  cd E:\大挑\00_skwm_world_model
  python -c "
from skwm_aligned_v4 import *
D = DataLayer().load(verbose=False)
C = SKWMController(D, DeepSeekClient())
C.current_year = 2000   # ← 改成2000年
R = C.process('文化遗产')
S = R['skwm']['S']
print(f'2000年的热点:')
for t in S['hot_topics'][:5]:
    print(f'  {t[\"name\"]:15s} 热度={t[\"heat\"]}')
"

可换的年份: 1895 ~ 2026 （不是每年都有数据，89年切片覆盖了大部分）


====================================================================
【场景6】完整服务闭环演示（挑战杯答辩演示用）
====================================================================

  cd E:\大挑\00_skwm_world_model
  python -c "
from skwm_aligned_v4 import *
D = DataLayer().load(verbose=False)
DS = DeepSeekClient()
C = SKWMController(D, DS)

# 模拟挑战杯答辩的完整演示
queries = [
    ('中阿文旅研究热点有哪些？', 'teacher'),   # 教师问热点
    ('帮我推荐一个论文方向', 'student'),        # 学生问选题
    ('生成本月学科服务报告', 'librarian'),      # 馆员做报告
]
C.run_service_loop(queries, verbose=True)
"


====================================================================
📁 输出文件说明
====================================================================

运行后 output/ 目录下生成的文件：

  skwm_output_demo.json
    → SKWM 7维输出（E/R/S/T/C/U/P）
    → 论文里可以引用这个JSON结构
    → 格式:
        {
          "E": {"entities_found": 0, ...},
          "R": {"relation_types": ["共现","共引","合作"], ...},
          "S": {"hot_topics": [{"name":"旅游","heat":6555,...}], ...},
          "T": {"current_year": 2026, "year_range": [1895,2026], ...},
          ...
        }

  skwm_coverage_report.json
    → 策划案54-62条逐条对照验证结果
    → 论文里可以写"系统验证了SKWM 7维中5/7完全覆盖，2/7框架就绪"


====================================================================
📊 论文可引用的关键数据
====================================================================

  数据维度:
    89年时间切片 (1895~2026)
    43,537条状态向量 (年×节点)
    586,912条共现关系
    XGBoost链接预测 AUC≈0.94
    5参数控制: M(束宽)/σ(噪声)/λ(视野)/α(后训练)/β(探索率)

  热点主题 (2026年):
    旅游(6,555) > 文化(3,956) > 遗产(2,417) > 数字(1,330) > 阿拉伯(1,132)

  新兴前沿 (2026年增速最快):
    gene(+638) > 旅游(+441) > generative ai(+372) > rate(+305) > tour(+304)

  运行成本: ¥0.0037/次 (DeepSeek API)


====================================================================
❓ 常见问题
====================================================================

Q: 报错 "No module named 'requests'"
A: pip install requests

Q: 报错 "No module named 'numpy'"
A: pip install numpy

Q: 报错 "No module named 'xgboost'"
A: pip install xgboost  （或者改代码把 xgb_model = None 可以跳过）

Q: 跑出来全是英文像 gene, rate 这些？
A: 因为状态向量里的关键词来自原始论文关键词（中英阿混杂）。
   加载 术语对齐表_v3.json 后可以翻译显示，当前v4.0未对接。

Q: 我想改top_k（显示更多/更少热点）？
A: 在 process(query, top_k=N) 里改N，默认7
