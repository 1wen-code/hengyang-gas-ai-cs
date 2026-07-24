"""生成附录文档：开发与运行环境说明"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import os

doc = Document()
for s in doc.sections:
    s.page_width = Cm(21.0); s.page_height = Cm(29.7)
    s.top_margin = Cm(2.54); s.bottom_margin = Cm(2.54)
    s.left_margin = Cm(3.17); s.right_margin = Cm(3.17)

def fn(run, cn='宋体', en='Times New Roman', sz=12, bold=False):
    run.font.size = Pt(sz); run.font.bold = bold
    run.font.name = en; run._element.rPr.rFonts.set(qn('w:eastAsia'), cn)

def heading(text, level=1):
    sizes = {1:18, 2:15, 3:14}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14); p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.5
    r = p.add_run(text); fn(r, '黑体', 'Times New Roman', sizes.get(level,14), bold=True)
    if level == 1: p.alignment = WD_ALIGN_PARAGRAPH.CENTER

def body(text, indent=True):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5; p.paragraph_format.space_after = Pt(4)
    if indent: p.paragraph_format.first_line_indent = Pt(24)
    r = p.add_run(text); fn(r, '宋体', 'Times New Roman', 12)

def bullet(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(1.5); p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text); fn(r, '宋体', 'Times New Roman', 12)

def tbl(headers, rows):
    t = doc.add_table(rows=1+len(rows), cols=len(headers)); t.style = 'Table Grid'
    from docx.enum.table import WD_TABLE_ALIGNMENT
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i,h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ''
        p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h); fn(r, '黑体', 'Times New Roman', 10, bold=True)
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1a1a2e"/>')
        c._element.get_or_add_tcPr().append(shd)
        r.font.color.rgb = RGBColor(255,255,255)
    for ri,row in enumerate(rows):
        for ci,val in enumerate(row):
            c = t.rows[ri+1].cells[ci]; c.text = ''
            p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val)); fn(r, '宋体', 'Times New Roman', 10)
            if ri%2==0:
                shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="f0f0f5"/>')
                c._element.get_or_add_tcPr().append(shd)
    doc.add_paragraph()

def code(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(1.5); p.paragraph_format.space_after = Pt(1)
    r = p.add_run(text); fn(r, 'Consolas', 'Consolas', 10)

# ═══════════════════════════════════════════
# 封面
# ═══════════════════════════════════════════
for _ in range(8): doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('衡阳市燃气AI智能客服系统'); fn(r, '黑体', 'Times New Roman', 24, bold=True)
doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('附录：开发与运行环境说明'); fn(r, '黑体', 'Times New Roman', 16)
for _ in range(8): doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('2026年5月'); fn(r, '宋体', 'Times New Roman', 14)
doc.add_page_break()

# ═══════════════════════════════════════════
# 正文
# ═══════════════════════════════════════════
heading('一、开发环境')
body('本系统在Windows 11操作系统上进行开发，使用VS Code作为主要集成开发环境。Python解释器版本为CPython 3.9+（推荐3.11+），所有依赖通过pip包管理器安装，依赖列表维护在项目根目录的requirements.txt文件中。')

heading('1.1 硬件环境', 2)
tbl(['配置项', '最低要求', '推荐配置'],
    [['CPU', '双核 2.0GHz', '四核 3.0GHz+'],
     ['内存', '4GB RAM', '8GB RAM+'],
     ['磁盘', '1GB 可用空间', '5GB SSD+'],
     ['网络', '宽带连接', '稳定宽带连接'],
     ['操作系统', 'Windows 10 / macOS 11 / Linux', 'Windows 11 / macOS 14+']])

heading('1.2 软件环境', 2)
tbl(['软件', '版本', '用途'],
    [['Python', '3.9+ (推荐 3.11+)', '编程语言运行时'],
     ['VS Code / PyCharm', '最新版', '集成开发环境'],
     ['Git', '2.30+', '版本控制'],
     ['GitHub', '—', '代码托管与自动部署'],
     ['Chrome / Edge', '最新版', '前端调试与测试']])

heading('1.3 Python 解释器说明', 2)
body('本系统使用的Python解释器为CPython，即Python官方参考实现。CPython是目前最广泛使用的Python解释器，与所有主流第三方库兼容。项目中的依赖库（如Flask、pandas、jieba、openai等）均基于CPython开发和测试，无需额外安装JIT编译器或特殊运行时。')
body('系统在Render云平台上的运行环境同样使用CPython 3.9+。Render自动识别项目根目录下的requirements.txt文件，在构建阶段通过 pip install -r requirements.txt 安装所有依赖。Gunicorn作为WSGI服务器负责多进程并发处理HTTP请求，每个worker进程均运行CPython解释器。')

heading('1.4 依赖库清单', 2)
tbl(['依赖库', '版本要求', '用途说明', '安装方式'],
    [['flask', '>=3.0', 'Web框架，提供RESTful API路由和模板渲染', 'pip install flask'],
     ['pandas', '>=2.0', '读取和解析CSV格式的FAQ知识库文件', 'pip install pandas'],
     ['openpyxl', '>=3.0', '解析Excel格式的知识库上传文件', 'pip install openpyxl'],
     ['jieba', '>=0.42', '中文分词引擎，用于RAG知识库检索', 'pip install jieba'],
     ['openai', '>=1.0', 'DeepSeek API的SDK（兼容OpenAI接口）', 'pip install openai'],
     ['python-dotenv', '>=1.0', '从.env文件加载环境变量（API密钥等）', 'pip install python-dotenv'],
     ['gunicorn', '>=22.0', '生产级WSGI HTTP服务器', 'pip install gunicorn']])

heading('1.5 依赖安装方法', 2)
body('在项目根目录下执行以下命令，一键安装所有依赖：')
code('pip install -r requirements.txt')
body('')
body('或逐个安装：', indent=False)
code('pip install flask>=3.0 pandas>=2.0 openpyxl>=3.0 jieba>=0.42')
code('pip install openai>=1.0 python-dotenv>=1.0 gunicorn>=22.0')
body('')
body('注意：CPython 3.9+ 自带 sqlite3、urllib、json、os、re、threading、datetime、uuid 等标准库模块，无需额外安装。本项目的数据持久化层（db.py）仅使用Python标准库中的 urllib.request 实现Supabase REST API调用，无额外数据库驱动依赖。')

doc.add_page_break()

heading('二、运行环境')
body('本系统部署于Render云平台（免费版），运行环境由Render自动配置和管理。Render为Python Web服务提供预构建的运行环境，包含CPython解释器、pip包管理器和Gunicorn WSGI服务器。')

heading('2.1 云平台环境', 2)
tbl(['配置项', '参数', '说明'],
    [['云平台', 'Render (Free Tier)', '自动部署、免费SSL、GitHub集成'],
     ['实例规格', '512MB RAM / 共享CPU', '免费版默认配置'],
     ['WSGI服务器', 'Gunicorn 22.0', '多worker模式，处理并发请求'],
     ['Python版本', 'CPython 3.9+', 'Render自动检测runtime.txt或默认最新版'],
     ['启动命令', 'gunicorn app:app --bind 0.0.0.0:$PORT', '在Render控制台配置'],
     ['自动部署', 'GitHub Push触发', '推送代码到主分支即自动部署'],
     ['休眠策略', '15分钟无请求自动休眠', '免费版特性，首次唤醒需30-60秒']])

heading('2.2 数据库环境', 2)
tbl(['配置项', '参数', '说明'],
    [['数据库服务', 'Supabase (Free Tier)', '托管PostgreSQL，免费500MB'],
     ['数据库类型', 'PostgreSQL 15', '通过PostgREST自动暴露REST API'],
     ['连接方式', 'HTTPS REST API', '使用service_role key认证，无需数据库驱动'],
     ['数据表', 'tickets / chat_logs / emergency_logs', '工单、对话记录、安全日志'],
     ['RLS策略', 'service_role全权读写', 'service_role key绕过行级安全策略']])

heading('2.3 AI 服务环境', 2)
tbl(['配置项', '参数', '说明'],
    [['大模型服务', 'DeepSeek API', 'https://api.deepseek.com'],
     ['模型名称', 'deepseek-chat', '中文理解和生成能力强，API成本低'],
     ['SDK', 'OpenAI Python SDK 1.x', '兼容DeepSeek API接口'],
     ['认证方式', 'API Key（环境变量注入）', 'DEEPSEEK_API_KEY，不提交到代码仓库'],
     ['调用频率', '仅normal_handler调用', '4/5 Handler不调用AI，API消耗极低'],
     ['单次Token', 'max_tokens=150-300', '固定Prompt + 短回复策略控制Token消耗']])

heading('2.4 本地开发运行', 2)
body('在本地开发环境中启动系统的步骤如下：')
body('第一步，克隆代码仓库：')
code('git clone https://github.com/1wen-code/hengyang-gas-ai-cs.git')
code('cd hengyang-gas-ai-cs')
body('第二步，安装依赖：')
code('pip install -r requirements.txt')
body('第三步，配置环境变量。在项目根目录创建 .env 文件，填入以下内容：')
code('DEEPSEEK_API_KEY=sk-xxxxxxxx    # DeepSeek API密钥（必填）')
code('FLASK_DEBUG=True               # 开发模式（可选）')
body('第四步，启动Flask开发服务器：')
code('python app.py')
body('第五步，浏览器打开 http://localhost:5000 即可访问系统。')
body('注意：本地开发模式下，如果未配置Supabase（db.py中的URL和KEY），系统仍可正常运行，但工单和日志数据不会被持久化存储。如需本地测试完整数据链路，需创建Supabase项目并建表，然后将Supabase URL和service_role key填入db.py。')

doc.add_page_break()

heading('三、生产环境部署')
body('生产环境部署于Render云平台，通过GitHub自动部署流水线实现持续交付。')

heading('3.1 环境变量配置', 2)
body('在Render控制台的Environment标签页中配置以下环境变量：')
tbl(['变量名', '是否必填', '说明', '示例值'],
    [['DEEPSEEK_API_KEY', '是', 'DeepSeek API密钥', 'sk-xxxxxxxxxxxxxxxx'],
     ['FLASK_DEBUG', '否', '调试模式开关', 'False'],
     ['SECRET_KEY', '否', 'Flask会话加密密钥', '随机字符串'],
     ['ADMIN_PASSWORD', '否', '管理后台登录密码', 'hygas0826']])

heading('3.2 启动命令', 2)
body('Render Web Service的启动命令配置为：')
code('gunicorn app:app --bind 0.0.0.0:$PORT')
body('Gunicorn参数说明：app:app 表示从 app.py 模块中导入名为 app 的Flask实例。--bind 0.0.0.0:$PORT 表示监听所有网络接口的 $PORT 端口（$PORT由Render自动分配，通常为10000）。Gunicorn默认启动（CPU核心数×2+1）个worker进程，在Render免费版的共享CPU环境下通常为2-3个worker。')

heading('3.3 数据库初始化', 2)
body('Supabase数据库的初始化步骤：')
bullet('1. 在Supabase SQL Editor中执行建表SQL，创建tickets、chat_logs、emergency_logs三张表')
bullet('2. 配置Row Level Security策略，允许service_role全权读写')
bullet('3. 获取Project URL和service_role key，填入db.py的URL和KEY变量中')
bullet('4. 无需在app.py或db.py中引入任何数据库驱动依赖（如psycopg2），直接使用Python标准库urllib.request调用Supabase REST API')

heading('3.4 部署验证', 2)
body('部署完成后，可通过以下方式验证系统是否正常运行：')
bullet('1. 浏览器访问系统URL，确认聊天界面正常加载，欢迎页显示 LOGO、快捷入口和状态面板')
bullet('2. 输入你好，确认AI回复您好，请问有什么可以帮您？')
bullet('3. 输入闻到煤气味了，确认出现黄色预警横幅和EM格式工单号')
bullet('4. 访问 /admin 路径，使用密码登录管理后台，确认工单列表和安全日志有数据')
bullet('5. 查看Render控制台的Logs标签页，确认没有报错日志，[DB] Supabase连接成功的日志出现')

doc.add_page_break()

heading('四、常见问题排查')
tbl(['问题', '原因', '解决方法'],
    [['系统返回 Application Error', 'Render冷启动中或代码有语法错误', '等待30-60秒刷新；检查Render Logs中的错误信息'],
     ['AI回复速度很慢(>10秒)', 'DeepSeek API国际网络延迟', '正常现象，非AI Handler在1.5秒内响应'],
     ['管理后台工单列表为空', 'Supabase表不存在或写入失败', '检查Supabase SQL Editor确认表已创建；检查db.py中URL和KEY是否正确'],
     ['知识库检索不准确', 'MATCH_THRESHOLD设置不当', '调整config.py中MATCH_THRESHOLD值(默认0.28)'],
     ['对话记录不显示', 'Supabase写入失败', '检查Render Logs中是否有[DB] POST error日志'],
     ['本地运行报ModuleNotFoundError', '依赖未安装', '执行 pip install -r requirements.txt']])

# 保存
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '附录-开发与运行环境说明.docx')
doc.save(out)
print(f'附录已生成: {out}')
