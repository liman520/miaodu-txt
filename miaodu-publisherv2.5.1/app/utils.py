"""
MiaoDuAI Workflow - 工具函数模块
提供文本清洗、错别字修正、垃圾过滤、字数统计、归档存储等通用功能
"""
import re
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = BASE_DIR / "Archive_Data"

# ── 错别字映射字典（规则库） ──
TYPO_CORRECTIONS = {
    "的的": "的",
    "了了": "了",
    "是是": "是",
    "有有": "有",
    "在在": "在",
    "和和": "和",
    "与与": "与",
    "或或": "或",
    "但但": "但",
    "而而": "而",
    "就就": "就",
    "都都": "都",
    "也也": "也",
    "还还": "还",
    "又又": "又",
    "再再": "再",
    "已已": "已",
    "正正": "正",
    "将将": "将",
    "会会": "会",
    "能能": "能",
    "可可": "可",
    "该该": "该",
    "要要": "要",
    "必须须": "必须",
    "需要要": "需要",
    "因为为": "因为",
    "所以以": "所以",
    "虽然然": "虽然",
    "但是是": "但是",
    "如果果": "如果",
    "那么么": "那么",
    "这么么": "这么",
    "怎么么": "怎么",
    "什么么": "什么",
    "这个个": "这个",
    "那个个": "那个",
    "这些些": "这些",
    "那些些": "那些",
    "自己己": "自己",
    "大家家": "大家",
    "人们们": "人们",
    "孩子子": "孩子",
    "学生生": "学生",
    "老师师": "老师",
    "工作作": "工作",
    "学习习": "学习",
    "生活活": "生活",
    "发展展": "发展",
    "建设设": "建设",
    "教育育": "教育",
    "文化化": "文化",
    "经济济": "经济",
    "社会会": "社会",
    "政治治": "政治",
    "科学学": "科学",
    "技术术": "技术",
    "历史史": "历史",
    "地理理": "地理",
    "物理理": "物理",
    "化学学": "化学",
    "生物物": "生物",
    "数学学": "数学",
    "语文文": "语文",
    "英语语": "英语",
}

# ── 垃圾文本过滤正则 ──
JUNK_PATTERNS = [
    # 微信/公众号推广
    r"关注公众号.*",
    r"微信[号群].*",
    r"扫码关注.*",
    r"长按识别二维码.*",
    r"点击上方.*关注.*",
    r"搜索.*关注.*",
    r"微信ID[:：].*",
    # 广告文案
    r"广告[：:].*",
    r"推广[：:].*",
    r"赞助商.*",
    r"商务合作.*",
    r"投稿邮箱.*@.*\..*",
    # 版权声明
    r"(?:©|Copyright).*",
    r"版权所有.*",
    r"转载请注明.*",
    r"原文链接[:：].*",
    r"来源[:：].*?(?:网|报|社|台)$",
    # 弹窗/JS残留
    r"javascript:.*",
    r"window\.open.*",
    r"document\.write.*",
    r"alert\(.*\);?",
    r"<script.*?</script>",
    r"<style.*?</style>",
    # 导航/面包屑残留
    r"首页\s*>\s*.*?\s*>\s*.*",
    r"当前位置[:：].*",
    r"您(现在)?所在(的)?位置.*",
    # 社交分享残留
    r"分享到.*",
    r"转发到.*",
    r"发送给.*",
    r"收藏.*举报.*",
    # 评论区残留
    r"全部评论.*",
    r"我要评论.*",
    r"热门评论.*",
    r"暂无评论.*",
    r"条评论.*",
    # 页码残留
    r"上一页\s*下一页",
    r"共\s*\d+\s*页.*",
    r"第\s*\d+\s*页.*共\s*\d+\s*页",
    # 外部链接残留
    r"https?://\S+",
    r"www\.\S+",
]

# ── 初高中不适配内容关键词矩阵 ──
UNFIT_KEYWORDS = [
    # 成人/色情/暴力
    "成人", "色情", "暴力", "血腥", "恐怖", "赌博", "毒品",
    "自杀", "自残", "虐杀", "色情", "裸体", "性行为",
    # 过度玄幻/超纲
    "穿越", "重生", "系统流", "金手指", "修仙", "修真",
    "玄幻", "仙侠", "异世界", "魔法", "超能力",
    # 商业营销
    "购买", "下单", "优惠券", "折扣", "秒杀", "限时",
    "免费领", "扫码购买", "点击购买", "立即购买",
    "促销", "爆款", "热卖", "包邮", "满减",
    # 政治敏感（适度过滤）
    "六四", "天安门事件", "法轮功",
]


def clean_html_tags(text: str) -> str:
    """清除HTML标签，保留纯文本"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", "", text)
    return text


def _is_cjk(ch: str) -> bool:
    """判断字符是否为CJK中文字符"""
    cp = ord(ch)
    return (
        (0x4E00 <= cp <= 0x9FFF) or    # CJK统一汉字
        (0x3400 <= cp <= 0x4DBF) or    # CJK扩展A
        (0x3000 <= cp <= 0x303F) or    # CJK符号和标点
        (0xFF00 <= cp <= 0xFFEF) or    # 全角ASCII
        (0x2000 <= cp <= 0x206F)       # 通用标点
    )


def normalize_punctuation(text: str) -> str:
    """规范化标点符号（半角转全角，统一中文标点）"""
    # 半角 -> 全角 标点映射
    replacements = {
        ",": "\u3001",   # , -> 、
        ".": "\u3002",   # 。-> 。
        "!": "\uff01",   # ! -> ！
        "?": "\uff1f",   # ? -> ？
        ":": "\uff1a",   # : -> ：
        ";": "\uff1b",   # ; -> ；
        "(": "\uff08",   # ( -> （
        ")": "\uff09",   # ) -> ）
        "[": "\u3010",   # [ -> 【
        "]": "\u3011",   # ] -> 】
        "<": "\u300a",   # < -> 《
        ">": "\u300b",   # > -> 》
    }
    # 仅在中文语境下替换（前后有中文字符时）
    result = []
    for i, ch in enumerate(text):
        if ch in replacements:
            # 判断前后是否有中文字符
            prev_cn = i > 0 and _is_cjk(text[i - 1])
            next_cn = i < len(text) - 1 and _is_cjk(text[i + 1])
            if prev_cn or next_cn:
                result.append(replacements[ch])
            else:
                result.append(ch)
        else:
            result.append(ch)
    text = "".join(result)
    # 修复连续标点
    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"[。.]{2,}", "。", text)
    text = re.sub(r"[！!]{2,}", "！", text)
    text = re.sub(r"[？?]{2,}", "？", text)
    return text


def fix_typos(text: str) -> str:
    """基于规则库的错别字修正"""
    for wrong, correct in TYPO_CORRECTIONS.items():
        text = text.replace(wrong, correct)
    return text


def remove_junk(text: str) -> str:
    """清除垃圾文本（广告、水印、版权声明等）"""
    for pattern in JUNK_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    # 清除多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 清除行首行尾空白
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return text.strip()


def check_content_fitness(text: str) -> tuple:
    """
    检查内容是否适合初高中学生
    返回 (is_fit: bool, reason: str)
    """
    text_lower = text.lower()
    for keyword in UNFIT_KEYWORDS:
        if keyword in text_lower:
            return (False, f"包含不适配关键词: {keyword}")
    return (True, "")


def count_words(text: str) -> int:
    """统计纯正文字数（去除HTML标签和特殊字符后）"""
    clean = clean_html_tags(text)
    # 去除空白字符
    clean = re.sub(r"\s+", "", clean)
    # 去除标点符号
    clean = re.sub(r"[，。！？：；""''（）【】《》—…、\.\,\!\?\;\:\'\"\(\)\[\]\{\}]", "", clean)
    return len(clean)


def validate_article_length(text: str, min_len: int = 300, max_len: int = 3000) -> tuple:
    """
    验证文章字数是否在规定范围内
    返回 (is_valid: bool, word_count: int, message: str)
    """
    wc = count_words(text)
    if wc < min_len:
        return (False, wc, f"字数不足: {wc}字 < 最低{min_len}字")
    if wc > max_len:
        return (False, wc, f"字数超标: {wc}字 > 最高{max_len}字")
    return (True, wc, f"字数合格: {wc}字")


def rule_based_correct(text: str) -> str:
    """
    第一层审校：基于规则的快速纠错清洗
    包含：HTML清除 -> 垃圾过滤 -> 标点规范 -> 错别字修正
    """
    text = clean_html_tags(text)
    text = remove_junk(text)
    text = normalize_punctuation(text)
    text = fix_typos(text)
    # 清理首尾空白
    text = text.strip()
    return text


# ── 本地归档功能 ──

def archive_article(article: dict) -> str:
    """
    将文章保存到本地归档目录
    返回归档文件路径
    """
    today = date.today().isoformat()
    day_dir = ARCHIVE_DIR / today
    os.makedirs(day_dir, exist_ok=True)

    # 文件名：分类_标题_已清洗.json
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.get("title", "untitled"))
    safe_title = safe_title[:50]  # 限制文件名长度
    category = article.get("category", "未分类")
    filename = f"{category}_{safe_title}_已清洗.json"
    filepath = day_dir / filename

    archive_data = {
        "title": article.get("title", ""),
        "content": article.get("content", ""),
        "category": category,
        "author": article.get("author", ""),
        "source": article.get("source", ""),
        "source_url": article.get("source_url", ""),
        "word_count": article.get("word_count", 0),
        "archived_at": datetime.now().isoformat(),
        "status": "pending",
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(archive_data, f, ensure_ascii=False, indent=2)

    return str(filepath)


def delete_archive(article: dict) -> bool:
    """删除文章对应的本地归档文件"""
    today = date.today().isoformat()
    day_dir = ARCHIVE_DIR / today

    safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.get("title", "untitled"))
    safe_title = safe_title[:50]
    category = article.get("category", "未分类")
    filename = f"{category}_{safe_title}_已清洗.json"
    filepath = day_dir / filename

    if filepath.exists():
        os.remove(filepath)
        return True
    return False


def get_archive_dates() -> list:
    """获取所有归档日期列表"""
    if not ARCHIVE_DIR.exists():
        return []
    dates = []
    for d in sorted(ARCHIVE_DIR.iterdir(), reverse=True):
        if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name):
            dates.append(d.name)
    return dates


def get_archive_files(date_str: str = None) -> list:
    """获取指定日期的归档文件列表"""
    if date_str is None:
        date_str = date.today().isoformat()
    day_dir = ARCHIVE_DIR / date_str
    if not day_dir.exists():
        return []
    files = []
    for f in sorted(day_dir.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                data["filepath"] = str(f)
                data["filename"] = f.name
                files.append(data)
        except Exception:
            pass
    return files
