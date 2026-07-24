# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

def set_run_font(run, cn, en, size, bold=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = en
    run._element.rPr.rFonts.set(qn('w:eastAsia'), cn)

def add_heading(doc, text, level=1, center=True):
    sizes = {1: 16, 2: 15, 3: 14}
    p = doc.add_paragraph()
    p.style = doc.styles[f'Heading {level}']
    run = p.add_run(text)
    set_run_font(run, '黑体', 'Times New Roman', sizes.get(level, 14), bold=True)
    if center and level == 1:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p

def add_body(doc, text, size=12, indent=True, bold=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, '宋体', 'Times New Roman', size, bold)
    pf = p.paragraph_format
    if indent:
        pf.first_line_indent = Pt(24)
    pf.line_spacing = 1.5
    pf.space_after = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p

def add_body_no_indent(doc, text, size=12, bold=False):
    return add_body(doc, text, size, indent=False, bold=bold)

def add_code(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(10.5)
    run.font.name = 'Consolas'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    pf = p.paragraph_format
    pf.line_spacing = 1.2
    pf.space_before = Pt(3)
    pf.space_after = Pt(3)
    return p

def make_table(doc, headers, rows_data):
    table = doc.add_table(rows=1 + len(rows_data), cols=len(headers), style='Table Grid')
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_run_font(p.runs[0], '黑体', 'Times New Roman', 10.5, bold=True)
    for r_idx, row in enumerate(rows_data):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = val
            for p in cell.paragraphs:
                set_run_font(p.runs[0], '宋体', 'Times New Roman', 10.5)
    return table

# ============ 开始生成 ============
doc = Document()

s = doc.sections[0]
s.page_width = Cm(21.0)
s.page_height = Cm(29.7)
s.top_margin = Cm(2.54)
s.bottom_margin = Cm(2.54)
s.left_margin = Cm(3.17)
s.right_margin = Cm(3.17)

# 封面
for _ in range(6):
    doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('衡阳市燃气AI智能客服系统')
set_run_font(run, '黑体', 'Times New Roman', 26, bold=True)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('系统代码运行说明书')
set_run_font(run, '黑体', 'Times New Roman', 22, bold=True)

for _ in range(4):
    doc.add_paragraph()

for line in ['项目组：衡阳市燃气AI智能客服系统开发组', '负 责 人：文俊宇', '学　　校：湖南信息学院', '日　　期：2026年5月']:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(line)
    set_run_font(run, '宋体', 'Times New Roman', 14)

doc.add_page_break()

# 目录
add_heading(doc, '目  录', 1)
for item in ['一、项目概述', '二、开发环境与技术栈', '三、项目目录结构',
             '四、环境搭建与依赖安装', '五、配置说明', '六、启动与运行',
             '七、核心模块说明', '八、知识库维护', '九、部署上线指南', '十、常见问题与排查']:
    add_body_no_indent(doc, item, 12)

doc.add_page_break()

# 一、项目概述
add_heading(doc, '一、项目概述', 1)
add_body(doc, '本项目是一个基于Flask框架的燃气行业AI智能客服系统，采用Router/Session/Handler模块化架构设计，集成DeepSeek大语言模型实现智能问答，通过jieba分词与Jaccard相似度算法实现知识库检索，并内置三级风险检测与自动工单机制。')

# 二、开发环境与技术栈
add_heading(doc, '二、开发环境与技术栈', 1)
add_heading(doc, '2.1 运行环境要求', 2)
add_body(doc, '· 操作系统：Windows 10/11、macOS、Linux均可')
add_body(doc, '· Python版本：3.9或更高版本（推荐3.11+）')
add_body(doc, '· 网络：需要稳定的互联网连接（调用DeepSeek API）')
add_body(doc, '· 磁盘空间：约50MB（含知识库文件）')

add_heading(doc, '2.2 技术栈清单', 2)
make_table(doc, ['类别', '技术/框架', '版本要求'], [
    ['后端框架', 'Flask', '>=3.0'],
    ['AI模型', 'DeepSeek Chat API', '-'],
    ['中文分词', 'jieba', '>=0.42'],
    ['数据处理', 'pandas + openpyxl', 'pandas>=2.0'],
    ['AI SDK', 'openai (兼容DeepSeek)', '>=1.0'],
    ['环境变量', 'python-dotenv', '>=1.0'],
    ['生产服务器', 'Gunicorn', '>=22.0'],
    ['前端', 'HTML/CSS/JavaScript', '-'],
])

# 三、项目目录结构
add_heading(doc, '三、项目目录结构', 1)
add_body(doc, '项目采用模块化目录结构，各目录职责明确：')

tree = [
    '衡阳燃气/                        项目根目录',
    '  app.py                         Flask主应用入口，定义所有路由',
    '  router.py                      核心路由分发器，根据意图调用对应Handler',
    '  detectors.py                   纯规则检测引擎（意图识别、情绪检测等）',
    '  session_manager.py             会话状态管理（多轮上下文维护）',
    '  db.py                          Supabase数据持久化接口',
    '  deepseek_client.py             DeepSeek API封装调用',
    '  prompts.py                     固定Prompt模板',
    '  config.py                      全局配置文件',
    '  requirements.txt               Python依赖清单',
    '  .env                           环境变量（API密钥等，不提交Git）',
    '  Procfile                       Render部署配置',
    '  handlers/                      业务处理器模块',
    '    faq_handler.py               FAQ问答处理器',
    '    normal_handler.py            常规业务处理器',
    '    danger_handler.py            危险事件处理器',
    '    smalltalk_handler.py         闲聊处理器',
    '    human_handler.py             转人工处理器',
    '  services/                      服务层',
    '    knowledge_service.py         知识库检索服务（jieba+Jaccard）',
    '    emergency.py                 风险检测与工单服务',
    '  knowledge/                     知识库文件',
    '    faq/faq_knowledge.csv        FAQ知识库（1009条）',
    '    policy/policy_knowledge.csv  法规知识库（72条）',
    '    labels/tag_system.json       标签体系（8大类）',
    '  static/                        前端静态资源',
    '    css/style.css                样式文件',
    '    js/chat.js                   前端交互逻辑',
    '  templates/                     HTML模板',
    '    index.html                   聊天主页面',
    '    admin.html                   管理后台页面',
    '    admin_login.html             管理后台登录页',
    '    my_tickets.html              工单查询页面',
    '  logs/                          日志目录',
    '    chat_log.csv                 对话日志',
    '    emergency.log                风险事件日志',
    '    tickets.csv                  工单数据',
]
for line in tree:
    add_body_no_indent(doc, line, 10.5)

# 四、环境搭建与依赖安装
add_heading(doc, '四、环境搭建与依赖安装', 1)

add_heading(doc, '4.1 安装Python', 2)
add_body(doc, '前往Python官网（https://www.python.org）下载Python 3.11或更高版本。安装时务必勾选"Add Python to PATH"选项，将Python添加到系统环境变量。')

add_heading(doc, '4.2 获取项目代码', 2)
add_body(doc, '方式一：从GitHub克隆', bold=True)
add_code(doc, 'git clone https://github.com/1wen-code/hengyang-gas-ai-cs.git')
add_code(doc, 'cd hengyang-gas-ai-cs')
add_body(doc, '方式二：直接解压项目压缩包到本地目录。')

add_heading(doc, '4.3 安装依赖', 2)
add_body(doc, '在项目根目录下打开终端，执行以下命令安装所有依赖包：')
add_code(doc, 'pip install -r requirements.txt')
add_body(doc, '如遇网络问题导致安装缓慢，可使用国内镜像源：')
add_code(doc, 'pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple')

# 五、配置说明
add_heading(doc, '五、配置说明', 1)

add_heading(doc, '5.1 环境变量配置（.env文件）', 2)
add_body(doc, '在项目根目录创建.env文件，填入以下配置：')
add_code(doc, '# 必填：DeepSeek API密钥')
add_code(doc, 'DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx')
add_code(doc, '')
add_code(doc, '# 可选：管理后台密码（默认hygas0826）')
add_code(doc, 'ADMIN_PASSWORD=your_password')
add_code(doc, '')
add_code(doc, '# 可选：是否开启Flask调试模式')
add_code(doc, 'FLASK_DEBUG=True')
add_body(doc, '获取DeepSeek API密钥：访问DeepSeek开放平台（https://platform.deepseek.com），注册账号后在API密钥页面创建密钥。')

add_heading(doc, '5.2 核心配置参数（config.py）', 2)
make_table(doc, ['参数名', '默认值', '说明'], [
    ['DEEPSEEK_BASE_URL', 'https://api.deepseek.com', 'DeepSeek API地址'],
    ['DEEPSEEK_MODEL', 'deepseek-chat', '使用的模型名称'],
    ['MATCH_THRESHOLD', '0.28', '知识库匹配阈值（0-1，越小越严格）'],
    ['SECRET_KEY', 'hengyang-gas-ai-cs-2024', 'Flask会话密钥'],
    ['DEBUG', 'False', '调试模式开关'],
    ['ENABLE_AI_FALLBACK', '自动检测', '无API Key时自动禁用AI'],
])

# 六、启动与运行
add_heading(doc, '六、启动与运行', 1)

add_heading(doc, '6.1 本地开发模式启动', 2)
add_body(doc, '在项目根目录执行以下命令：')
add_code(doc, 'python app.py')
add_body(doc, '启动成功后，终端会显示类似以下信息：')
add_code(doc, ' * Running on http://127.0.0.1:5000')
add_code(doc, ' * Debug mode: on')
add_body(doc, '打开浏览器访问 http://localhost:5000 即可使用系统。')

add_heading(doc, '6.2 Windows快捷启动', 2)
add_body(doc, '项目根目录下提供"启动客服.bat"双击即可启动，适合不熟悉命令行的用户。')

add_heading(doc, '6.3 生产模式启动', 2)
add_body(doc, '在Linux服务器上使用Gunicorn部署：')
add_code(doc, 'gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120')
add_body(doc, '参数说明：--workers指定工作进程数（建议CPU核心数x2+1），--timeout指定请求超时时间（秒）。')

add_heading(doc, '6.4 功能入口', 2)
make_table(doc, ['功能', '本地地址', '说明'], [
    ['聊天界面', 'http://localhost:5000', '用户端主页面'],
    ['管理后台', 'http://localhost:5000/admin', '工单管理、数据统计'],
    ['我的工单', 'http://localhost:5000/my-tickets', '用户工单查询'],
])

# 七、核心模块说明
add_heading(doc, '七、核心模块说明', 1)

add_heading(doc, '7.1 路由分发（router.py）', 2)
add_body(doc, 'Router是系统的核心调度模块，负责接收用户消息并根据意图识别结果分发到对应的Handler处理。处理流程为：用户输入 → 语义归一化 → 意图识别 → 风险检测 → FAQ检索 → Handler分发 → AI生成回复 → 返回用户。')

add_heading(doc, '7.2 知识库检索（services/knowledge_service.py）', 2)
add_body(doc, '采用jieba中文分词 + Jaccard相似度算法实现FAQ匹配。检索流程：用户输入分词 → 同义词扩展 → 关键词倒排索引匹配 → Jaccard相似度计算 → 返回最匹配的结果。当前匹配阈值为0.28，匹配准确率达96%。')

add_heading(doc, '7.3 风险检测（services/emergency.py）', 2)
add_body(doc, '三级风险检测机制：一级（普通）正常回复；二级（疑似）加入安全提示；三级（高危）触发紧急处理流程，自动生成工单并记录到emergency.log。')

add_heading(doc, '7.4 会话管理（session_manager.py）', 2)
add_body(doc, '维护用户多轮对话上下文，支持话题追踪和已答FAQ去重。每个用户会话独立存储，包含对话历史、当前话题分类、追问状态等信息。')

add_heading(doc, '7.5 业务处理器（handlers/）', 2)
add_body(doc, '5个独立Handler分别处理不同场景：faq_handler处理FAQ问答，normal_handler处理常规业务，danger_handler处理危险事件，smalltalk_handler处理闲聊，human_handler处理转人工请求。')

# 八、知识库维护
add_heading(doc, '八、知识库维护', 1)

add_heading(doc, '8.1 FAQ知识库', 2)
add_body(doc, '文件位置：knowledge/faq/faq_knowledge.csv')
add_body(doc, 'CSV格式，包含问题、答案、分类标签等字段。新增FAQ时，按照knowledge/knowledge_template.xlsx模板填写后导入即可。当前包含1009条FAQ，覆盖8大类标签体系。')

add_heading(doc, '8.2 法规知识库', 2)
add_body(doc, '文件位置：knowledge/policy/policy_knowledge.csv')
add_body(doc, '包含72条燃气行业法规条文，采用5级分类体系。支持按法规名称、条文内容进行检索。')

add_heading(doc, '8.3 标签体系', 2)
add_body(doc, '文件位置：knowledge/labels/tag_system.json')
add_body(doc, '定义了8大类标签（费用、报装、安全、法规、投诉、设备、服务、其他），用于FAQ分类和检索优化。')

# 九、部署上线指南
add_heading(doc, '九、部署上线指南', 1)

add_heading(doc, '9.1 Render平台部署', 2)
add_body(doc, '（1）将项目推送到GitHub仓库。')
add_body(doc, '（2）登录Render（https://render.com），创建Web Service。')
add_body(doc, '（3）关联GitHub仓库，Render会自动识别Procfile配置。')
add_body(doc, '（4）在Environment中添加环境变量DEEPSEEK_API_KEY。')
add_body(doc, '（5）点击Deploy，等待部署完成。')

add_heading(doc, '9.2 推送到GitHub', 2)
add_code(doc, 'cd D:\\衡阳燃气')
add_code(doc, 'git add -A')
add_code(doc, 'git commit -m "提交说明"')
add_code(doc, 'git push')
add_body(doc, '注意：推送时需要手机热点或稳定的网络环境。.env文件已在.gitignore中排除，不会被提交。')

add_heading(doc, '9.3 其他服务器部署', 2)
add_body(doc, '在任意Linux服务器上，安装Python和依赖后，使用Gunicorn启动即可：')
add_code(doc, 'pip install -r requirements.txt')
add_code(doc, 'gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120')
add_body(doc, '建议配合Nginx做反向代理，并配置SSL证书启用HTTPS。')

# 十、常见问题与排查
add_heading(doc, '十、常见问题与排查', 1)

faqs = [
    ('Q：启动报错ModuleNotFoundError', 'A：执行pip install -r requirements.txt安装依赖。如已安装仍报错，检查是否使用了正确的Python环境。'),
    ('Q：AI不回复，日志报API错误', 'A：检查.env文件中DEEPSEEK_API_KEY是否正确配置，密钥是否过期，账户余额是否充足。'),
    ('Q：知识库检索不到结果', 'A：检查knowledge/faq/faq_knowledge.csv文件是否存在且格式正确。可尝试降低config.py中的MATCH_THRESHOLD值。'),
    ('Q：管理后台无法登录', 'A：确认密码正确（默认hygas0826），或检查.env中ADMIN_PASSWORD是否修改过。'),
    ('Q：工单数据不显示', 'A：本地模式下工单存储在logs/tickets.csv，需触发风险检测后才会生成工单。'),
    ('Q：线上访问显示空白页', 'A：Render免费版首次访问需等待30-60秒冷启动。如持续空白，检查Render部署日志是否有报错。'),
]
for q, a in faqs:
    add_body(doc, q, bold=True)
    add_body(doc, a)

doc.save(r'C:\Users\wenju\OneDrive\文档\衡阳燃气AI智能客服系统-代码运行说明书.docx')
print('代码运行说明书已生成')
