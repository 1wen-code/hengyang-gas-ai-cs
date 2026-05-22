"""
衡阳市天然气AI客服智能体 — 多路召回RAG检索服务
支持：FAQ精确匹配 + 关键词召回 + 同义词扩展 + 法规分类检索
"""
import jieba
import pandas as pd
import json
import os
import re
from config import KB_FAQ_PATH, KB_POLICY_PATH, TAG_SYSTEM_PATH, MATCH_THRESHOLD

# 同义词词典
SYNONYM_MAP = {
    "开户": ["报装", "新装", "开通", "申请"],
    "缴费": ["充值", "交费", "支付", "付款", "交钱"],
    "燃气": ["天然气", "煤气", "管道气"],
    "灶具": ["燃气灶", "灶", "煤气灶", "炉灶"],
    "热水器": ["燃气热水器", "洗澡"],
    "漏气": ["泄漏", "泄露", "跑气", "漏"],
    "安检": ["检查", "检测", "入户检查"],
    "过户": ["变更", "改名", "换户主", "转让"],
    "销户": ["注销", "取消", "停用", "报停"],
    "投诉": ["举报", "反映", "意见", "不满意"],
    "发票": ["收据", "票据", "凭证", "开票"],
    "报修": ["维修", "修理", "修", "坏了", "故障"],
    "改管": ["改装", "改造", "移表", "移管", "移位"],
    "欠费": ["没交", "忘记交", "逾期", "拖欠"],
    "停气": ["断气", "没气", "无气", "中断"],
    "营业厅": ["网点", "大厅", "柜台", "服务点"],
    "客服": ["热线", "电话", "联系方式"],
    "点火": ["通气", "开通", "启用"],
    "换表": ["更换", "换电表", "换气表"],
    "补贴": ["优惠", "减免", "补助", "低保"],
}

class KnowledgeService:
    """RAG知识检索服务 — 多路召回 + 法规分类"""

    @staticmethod
    def _safe(v):
        """将NaN转为空字符串"""
        try:
            if v != v:  # NaN check
                return ""
            return str(v)
        except:
            return ""

    def __init__(self):
        self._faq_df = None
        self._policy_df = None
        self._tag_system = None
        self._keyword_index = {}  # 关键词倒排索引
        self._load()

    def _load(self):
        """加载知识库与标签体系"""
        self._faq_df = pd.read_csv(KB_FAQ_PATH, encoding="utf-8-sig")
        self._policy_df = pd.read_csv(KB_POLICY_PATH, encoding="utf-8-sig")
        with open(TAG_SYSTEM_PATH, "r", encoding="utf-8") as f:
            self._tag_system = json.load(f)
        self._build_index()
        print(f"[KB] FAQ: {len(self._faq_df)}条 | Policy: {len(self._policy_df)}条 | Tags: {len(self._tag_system['tags'])}类")

    def _build_index(self):
        """构建关键词倒排索引"""
        for idx, row in self._faq_df.iterrows():
            text = str(row.get("用户问题", "")) + " " + str(row.get("关键词", ""))
            words = set(jieba.lcut(text))
            for w in words:
                if w not in self._keyword_index:
                    self._keyword_index[w] = []
                self._keyword_index[w].append(idx)

    def _expand_query(self, question: str) -> set:
        """同义词扩展"""
        tokens = set(jieba.lcut(question))
        expanded = set(tokens)
        for word in tokens:
            for key, syns in SYNONYM_MAP.items():
                if word in syns or word == key:
                    expanded.add(key)
                    expanded.update(syns)
        return expanded

    def _classify(self, question: str) -> str:
        """根据关键词将问题分类到一级标签"""
        tags = self._tag_system["tags"]
        scores = {}
        for tag in tags:
            cat = tag["一级标签"]
            scores[cat] = 0
            for sub in tag["二级标签"]:
                for kw in sub["关键词"]:
                    if kw in question:
                        scores[cat] += 1
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        return "转人工"

    def search_faq(self, question: str) -> dict | None:
        """FAQ精确匹配"""
        if not question or not question.strip():
            return None
        question = question.strip()
        query_tokens = self._expand_query(question)
        best = None
        best_score = 0.0
        for _, row in self._faq_df.iterrows():
            kb_q = str(row["用户问题"])
            kb_kws = str(row.get("关键词", ""))
            kb_tokens = set(jieba.lcut(kb_q + " " + kb_kws))
            if not query_tokens or not kb_tokens:
                continue
            intersection = query_tokens & kb_tokens
            union = query_tokens | kb_tokens
            score = len(intersection) / len(union)
            # 多词重合大幅加分
            if len(intersection) >= 3:
                score += 0.10 * (len(intersection) - 2)
            # 短问题匹配长答案：轻微降权
            if len(query_tokens) <= 3 and len(kb_tokens) > 8:
                score -= 0.05
            score = max(0.0, min(score, 1.0))
            if score > best_score:
                best_score = score
                best = {
                    "question": kb_q,
                    "answer": self._safe(row["标准回答"]),
                    "category": f"{self._safe(row.get('一级标签', ''))} > {self._safe(row.get('二级标签', ''))}",
                    "source": self._safe(row.get("回答来源", "")),
                    "law": self._safe(row.get("法规依据", "")),
                    "law_code": self._safe(row.get("依据编码", "")),
                    "risk": self._safe(row.get("风险等级", "低")),
                    "score": round(best_score, 3),
                }
        if best and best_score >= MATCH_THRESHOLD:
            return best
        return None

    def search_policy(self, question: str) -> dict | None:
        """法规知识库匹配"""
        if not question or not question.strip():
            return None
        question = question.strip()
        query_tokens = self._expand_query(question)
        best = None
        best_score = 0.0
        for _, row in self._policy_df.iterrows():
            kb_q = str(row.get("法规条款", row.get("用户问题", "")))
            kb_tokens = set(jieba.lcut(kb_q))
            if not query_tokens or not kb_tokens:
                continue
            intersection = query_tokens & kb_tokens
            union = query_tokens | kb_tokens
            score = len(intersection) / len(union)
            if score > best_score:
                best_score = score
                best = {
                    "question": kb_q,
                    "answer": self._safe(row.get("条款内容", row.get("标准回答", ""))),
                    "category": f"政策咨询 > {self._safe(row.get('法规分类', ''))}",
                    "source": self._safe(row.get("法规分类", "")),
                    "law": self._safe(row.get("法规名称", "")),
                    "law_code": self._safe(row.get("依据编码", "")),
                    "risk": "中",
                    "score": round(best_score, 3),
                }
        if best and best_score >= MATCH_THRESHOLD:
            return best
        return None

    def search_top_k(self, question: str, k: int = 5) -> list[dict]:
        """Top-K RAG上下文召回"""
        if not question or not question.strip():
            return []
        question = question.strip()
        query_tokens = self._expand_query(question)
        scored = []
        for _, row in self._faq_df.iterrows():
            kb_q = str(row["用户问题"])
            kb_kws = str(row.get("关键词", ""))
            kb_tokens = set(jieba.lcut(kb_q + " " + kb_kws))
            if not query_tokens or not kb_tokens:
                continue
            intersection = query_tokens & kb_tokens
            union = query_tokens | kb_tokens
            score = len(intersection) / len(union)
            if len(intersection) >= 2:
                score += 0.05 * (len(intersection) - 1)
            scored.append({
                "question": kb_q,
                "answer": row["标准回答"],
                "category": f"{self._safe(row.get('一级标签', ''))} > {self._safe(row.get('二级标签', ''))}",
                "source": self._safe(row.get("回答来源", "")),
                "law": self._safe(row.get("法规依据", "")),
                "law_code": self._safe(row.get("依据编码", "")),
                "score": round(min(score, 1.0), 3),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def classify_and_search(self, question: str):
        """综合检索：分类 -> FAQ -> 法规 -> 转人工"""
        category = self._classify(question)
        faq_result = self.search_faq(question)
        if faq_result:
            return {"type": "faq", "category": category, "data": faq_result}
        policy_result = self.search_policy(question)
        if policy_result:
            return {"type": "policy", "category": category, "data": policy_result}
        return {"type": "unmatched", "category": category, "data": None}
