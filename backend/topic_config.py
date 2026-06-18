"""
选题类别配置 — 渔业智能设备专用
每个选题方向定义了适用的平台、目标人群、内容形式和 prompt 注入指令
"""
from typing import Dict, List, Optional


class TopicCategory:
    """选题类别定义"""
    __slots__ = ("id", "name", "subtitle", "best_platforms", "target_audience",
                 "content_type", "prompt_injection", "platform_specific")

    def __init__(self, id_: str, name: str, subtitle: str, best_platforms: List[str],
                 target_audience: str, content_type: str, prompt_injection: str,
                 platform_specific: Optional[Dict[str, str]] = None):
        self.id = id_
        self.name = name
        self.subtitle = subtitle
        self.best_platforms = best_platforms
        self.target_audience = target_audience
        self.content_type = content_type
        self.prompt_injection = prompt_injection
        self.platform_specific = platform_specific or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "subtitle": self.subtitle,
            "best_platforms": self.best_platforms, "target_audience": self.target_audience,
            "content_type": self.content_type,
        }


# ==================== 渔业智能设备 7 大选题方向 ====================
FISHERY_TOPICS: List[TopicCategory] = [
    TopicCategory(
        id_="tech_explanation",
        name="技术原理解析",
        subtitle="声呐成像 / AI鱼群识别 / IoT传感器 / 水下通信",
        best_platforms=["zhihu", "wechat"],
        target_audience="行业技术决策者、设备采购方",
        content_type="深度技术长文",
        prompt_injection=(
            "【选题角度：技术原理解析】\n"
            "请以行业技术专家的身份，深入解析产品的核心技术原理。\n"
            "- 从「为什么需要这项技术」的问题出发，引出技术背景\n"
            "- 用通俗语言解释复杂技术（声呐回波/机器学习模型/IoT拓扑），让非技术读者也能理解\n"
            "- 引用行业技术参数对比，体现产品的技术先进性\n"
            "- 避免营销感，以「技术科普」的口吻撰写\n"
            "- 可适当提及技术演进历程和未来方向"
        ),
        platform_specific={
            "zhihu": (
                "知乎特别要求：开篇抛出技术痛点问题（如「传统声呐为什么看不清浅水区鱼群？」），"
                "用「问题→原理→方案→效果」的论证链，每节标题加粗，引用权威数据来源。"
            ),
            "wechat": (
                "微信特别要求：标题用设问句式（如「一文看懂XX技术的底层逻辑」），"
                "配信息图表说明技术架构，文末附「技术白皮书领取」引导关注。"
            ),
        },
    ),
    TopicCategory(
        id_="product_guide",
        name="产品功能指南",
        subtitle="安装部署 / 参数调优 / 固件升级 / 常见问题",
        best_platforms=["toutiao", "wechat"],
        target_audience="已有/潜在用户、养殖场设备管理员",
        content_type="图文教程",
        prompt_injection=(
            "【选题角度：产品功能指南】\n"
            "请以产品使用顾问的身份，撰写一份实用操作指南。\n"
            "- 从用户最常遇到的场景切入（如「新设备到手，第一步该做什么？」）\n"
            "- 步骤化呈现，每步配操作要点和注意事项\n"
            "- 加入「避坑提示」和「进阶技巧」，体现专业度\n"
            "- 语气亲切、实用，像技术售后在面对面指导\n"
            "- 可引用真实使用场景和数据佐证功能价值"
        ),
    ),
    TopicCategory(
        id_="case_study",
        name="养殖增效案例",
        subtitle="投喂优化 / 水质预警 / 产量提升 / 成本核算",
        best_platforms=["toutiao", "xiaohongshu"],
        target_audience="养殖户老板、渔业合作社负责人",
        content_type="故事型案例",
        prompt_injection=(
            "【选题角度：客户案例故事】\n"
            "请以一个真实的养殖场案例为蓝本，讲述产品带来的改变。\n"
            "- 用「之前 vs 之后」的对比框架：投喂成本、产量、人工成本等维度\n"
            "- 引用具体的数字变化（如「投喂成本降低了X%」「巡塘时间从X小时缩短到Y分钟」）\n"
            "- 用养殖户的第一视角口吻，讲出真实感受\n"
            "- 突出「用了就回不去」的体验改变\n"
            "- 文末带出产品名字要自然，不让读者觉得在看硬广"
        ),
    ),
    TopicCategory(
        id_="industry_trend",
        name="行业政策趋势",
        subtitle="智慧渔业政策 / 数字化补贴 / 养殖转型 / 市场分析",
        best_platforms=["zhihu", "wechat"],
        target_audience="行业从业者、政策研究者",
        content_type="政策解读/行业分析",
        prompt_injection=(
            "【选题角度：行业趋势解读】\n"
            "请以行业分析师的身份，解读渔业智能化领域的最新动态。\n"
            "- 从政策文件/行业报告/市场数据出发，给出有依据的判断\n"
            "- 结合产品所在赛道，分析行业的机遇和挑战\n"
            "- 观点鲜明，不模棱两可——「我认为XX趋势将在未来三年内重塑水产养殖」\n"
            "- 引用具体的政策条文、行业数据、典型企业案例\n"
            "- 结尾给出「从业者该怎么做」的实操建议"
        ),
    ),
    TopicCategory(
        id_="pain_point",
        name="场景痛点共鸣",
        subtitle="巡塘辛苦 / 水质突变 / 投喂不准 / 设备维护难",
        best_platforms=["xiaohongshu", "douyin"],
        target_audience="一线养殖工人、水产从业者",
        content_type="短图文/痛点共鸣",
        prompt_injection=(
            "【选题角度：场景痛点共鸣】\n"
            "请以真实从业者的视角，描述渔业养殖中的痛点场景。\n"
            "- 用「你是不市也经历过…」的共鸣式开场\n"
            "- 描述具体的痛点场景：半夜巡塘、台风天值守、投喂算不准等\n"
            "- 让读者产生「这就是我」的认同感\n"
            "- 自然引出产品如何解决这个痛点（不要生硬转场）\n"
            "- 语气真实接地气，用一线养殖户的口吻，不要高大上"
        ),
    ),
    TopicCategory(
        id_="comparison",
        name="对比选型指南",
        subtitle="传统vs智能 / 设备选型Checklist / 投入产出ROI",
        best_platforms=["zhihu", "toutiao"],
        target_audience="养殖场采购决策者",
        content_type="横向对比评测",
        prompt_injection=(
            "【选题角度：对比选型指南】\n"
            "请以采购顾问的身份，写一份客观的设备选型对比。\n"
            "- 列出选型的关键维度：精度、稳定性、易用性、售后、价格\n"
            "- 对比「传统方式 vs 智能化设备」的各维度表现\n"
            "- 加入投入产出比（ROI）计算——让读者算清楚「多久回本」\n"
            "- 给出一份「选型Checklist」，方便读者对照评估\n"
            "- 客观中立，不贬低竞品，不夸大自家"
        ),
    ),
    TopicCategory(
        id_="seasonal",
        name="季节时令专题",
        subtitle="投苗季部署 / 越冬管理 / 台风应急 / 高温防病",
        best_platforms=["toutiao", "xiaohongshu", "douyin", "wechat"],
        target_audience="全量养殖从业者",
        content_type="时令专题/实用攻略",
        prompt_injection=(
            "【选题角度：季节时令专题】\n"
            "请结合当前季节（请根据生成时间判断），撰写应季的养殖管理内容。\n"
            "- 聚焦该季节最核心的养殖痛点（如春季投苗、夏季高温、秋季收获、冬季越冬）\n"
            "- 给出具体的操作建议和时间节点\n"
            "- 自然引入智能化设备如何在这个季节发挥价值\n"
            "- 语气实用接地气，不搞虚的"
        ),
    ),
]

# 选题快捷索引
TOPIC_MAP: Dict[str, TopicCategory] = {t.id: t for t in FISHERY_TOPICS}
TOPIC_LIST = [t.id for t in FISHERY_TOPICS]

# ==================== 平台-选题适配矩阵 ====================
# 每个平台优先推荐的选题方向
PLATFORM_TOPIC_PRIORITY: Dict[str, List[str]] = {
    "zhihu":        ["tech_explanation", "industry_trend", "comparison"],
    "wechat":       ["tech_explanation", "product_guide", "industry_trend", "seasonal"],
    "toutiao":      ["product_guide", "case_study", "comparison", "seasonal"],
    "xiaohongshu":  ["pain_point", "case_study", "seasonal"],
    "weibo":        ["pain_point", "seasonal"],
    "douyin":       ["pain_point", "seasonal"],
}

# 去重窗口（天）
DEDUP_WINDOW_DAYS = 30
