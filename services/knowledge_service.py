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
            # 精确率惩罚：用户问题中未匹配到的关键词越多，降权越重
            precision = len(intersection) / len(query_tokens) if query_tokens else 0
            if precision < 0.6:
                score -= 0.12
            # 多词重合加分
            if len(intersection) >= 3:
                score += 0.08 * (len(intersection) - 2)
            if len(intersection) >= 5:
                score += 0.10
            # 短问题匹配长答案：降权
            if len(query_tokens) <= 3 and len(kb_tokens) > 8:
                score -= 0.05
            # 精确包含加分
            if question in kb_q or kb_q in question:
                score += 0.15
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
            ans = best["answer"]
            # 拒绝模板短回答：<80字且含"客服热线"或"建议"的
            if len(ans) < 80 and ("客服热线" in ans or "建议您" in ans):
                return None
            return best
        return None

    
    def search_faq_by_category(self, question: str, category: str = "", top_k: int = 5) -> list[dict]:
        """分类过滤检索 + 关键词重排序"""
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
            precision = len(intersection) / len(query_tokens) if query_tokens else 0
            if precision < 0.6: score -= 0.12
            if len(intersection) >= 3: score += 0.08 * (len(intersection) - 2)
            if len(intersection) >= 5: score += 0.10
            if len(query_tokens) <= 3 and len(kb_tokens) > 8: score -= 0.05
            if question in kb_q or kb_q in question: score += 0.15
            score = max(0.0, min(score, 1.0))
            faq_cat = str(row.get("一级标签", ""))
            scored.append({
                "question": kb_q,
                "answer": self._safe(row["标准回答"]),
                "category": f"{self._safe(row.get('一级标签', ''))} > {self._safe(row.get('二级标签', ''))}",
                "faq_cat": faq_cat,
                "source": self._safe(row.get("回答来源", "")),
                "law": self._safe(row.get("法规依据", "")),
                "law_code": self._safe(row.get("依据编码", "")),
                "risk": self._safe(row.get("风险等级", "低")),
                "score": round(min(score, 1.0), 3),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)

        # 分类过滤：优先匹配同类FAQ
        if category:
            priority_keywords = {
                "开户业务": ["材料", "流程", "费用", "办理", "身份证", "房产证", "时间"],
                "缴费业务": ["微信", "支付宝", "充值", "线上", "银行", "代扣"],
                "安全风险": ["关阀", "通风", "撤离", "抢修", "报警"],
                "灶具维修": ["排查", "电池", "阀门", "火盖", "清理"],
                "故障报修": ["报修", "上门", "维修", "预约", "师傅"],
                "投诉建议": ["投诉", "反馈", "赔偿", "处理"],
            }
            keywords = priority_keywords.get(category, [])

            # 重排序：同类FAQ提权，含优先关键词的额外加分
            for item in scored:
                if category in item.get("faq_cat", ""):
                    item["score"] += 0.15
                for kw in keywords:
                    if kw in item.get("question", "") or kw in item.get("answer", ""):
                        item["score"] += 0.05

            scored.sort(key=lambda x: x["score"], reverse=True)
            # 剔除分太低且类别不匹配的
            scored = [s for s in scored if s["score"] >= 0.10]

        # 去重：相似问题只保留最高分
        seen_answers = set()
        unique = []
        for s in scored:
            ans_key = s["answer"][:50]
            if ans_key not in seen_answers:
                seen_answers.add(ans_key)
                unique.append(s)
        return unique[:top_k]

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
            precision = len(intersection) / len(query_tokens) if query_tokens else 0
            if precision < 0.6: score -= 0.12
            if len(intersection) >= 3: score += 0.08 * (len(intersection) - 2)
            if len(intersection) >= 5: score += 0.10
            if len(query_tokens) <= 3 and len(kb_tokens) > 8: score -= 0.05
            if question in kb_q or kb_q in question: score += 0.15
            score = max(0.0, min(score, 1.0))
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
