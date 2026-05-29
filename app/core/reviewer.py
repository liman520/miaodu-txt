"""内容审核引擎 - v2.3 增强版"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class ContentReviewer:
    """文章内容审核引擎"""

    PUNCTUATION_MAP = {
        ",": "，", ";": "；", ":": "：", "?": "？", "!": "！",
        "(": "（", ")": "）",
    }

    SPAM_KEYWORDS = [
        "微信号", "加微信", "扫码关注", "点击链接", "限时优惠",
        "免费领取", "转发有礼", "广告合作", "商务合作",
        "www.", "http://", "https://",
        "联系方式", "联系电话", "QQ群",
    ]

    INAPPROPRIATE_KEYWORDS = [
        "赌博", "彩票", "博彩", "色情", "暴力", "毒品",
        "传销", "诈骗", "非法集资",
    ]

    def __init__(self, ai_corrector=None):
        self.ai_corrector = ai_corrector

    def review(self, title: str, content: str, category: str) -> Tuple[bool, str, str]:
        logs = []
        corrected_content = content

        word_count = len(content.strip())
        if word_count < 300:
            logs.append(f"[FAIL] 字数不足: {word_count} 字 (最少300字)")
            return False, content, "\n".join(logs)
        if word_count > 3000:
            logs.append(f"[FAIL] 字数过多: {word_count} 字 (最多3000字)")
            return False, content, "\n".join(logs)
        logs.append(f"[OK] 字数检查通过: {word_count} 字")

        spam_found = [kw for kw in self.SPAM_KEYWORDS if kw in content or kw in title]
        if spam_found:
            logs.append(f"[FAIL] 检测到广告/垃圾关键词: {', '.join(spam_found)}")
            return False, content, "\n".join(logs)
        logs.append("[OK] 广告内容检查通过")

        inappropriate_found = [kw for kw in self.INAPPROPRIATE_KEYWORDS if kw in content]
        if inappropriate_found:
            logs.append(f"[FAIL] 检测到不当内容关键词: {', '.join(inappropriate_found)}")
            return False, content, "\n".join(logs)
        logs.append("[OK] 内容安全检查通过")

        corrected_content = self._fix_punctuation(corrected_content)
        logs.append("[OK] 标点符号修正完成")

        corrected_content = self._clean_garbage_paragraphs(corrected_content)
        logs.append("[OK] 格式清理完成")

        if self.ai_corrector and self.ai_corrector.enabled:
            try:
                ai_result = self.ai_corrector.correct(corrected_content)
                if ai_result:
                    corrected_content = ai_result
                    logs.append("[OK] AI语义纠错完成")
                else:
                    logs.append("[WARN] AI纠错无有效输出，保留原始纠错结果")
            except Exception as e:
                logs.append(f"[WARN] AI纠错异常: {str(e)}，保留原始纠错结果")
        else:
            logs.append("[SKIP] AI语义纠错未启用")

        final_count = len(corrected_content.strip())
        if final_count < 300:
            logs.append(f"[FAIL] 纠错后字数不足: {final_count} 字")
            return False, corrected_content, "\n".join(logs)

        logs.append(f"[PASS] 审核通过，最终字数: {final_count} 字")
        return True, corrected_content, "\n".join(logs)

    def _fix_punctuation(self, text: str) -> str:
        for eng, chn in self.PUNCTUATION_MAP.items():
            text = re.sub(rf'([\u4e00-\u9fff]){re.escape(eng)}([\u4e00-\u9fff])', rf'\1{chn}\2', text)
        text = re.sub(r'[ 　]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _clean_garbage_paragraphs(self, text: str) -> str:
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                cleaned.append(line)
                continue
            if re.match(r'^https?://\S+$', line_stripped):
                continue
            if any(kw in line_stripped for kw in self.SPAM_KEYWORDS):
                continue
            if re.match(r'^\d+$', line_stripped):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)
