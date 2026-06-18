"""
SQLAlchemy 数据模型 - 8 张核心表
兼容 PostgreSQL 和 SQLite
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float,
    ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# JSON 列工厂：PG 用 JSONB，SQLite 用 JSON
def JsonCol(**kwargs):
    return Column(JSON, **kwargs)


def ArrayCol(**kwargs):
    """数组列：PG 原生 ARRAY，SQLite 用 JSON 模拟"""
    return Column(JSON, default=list, **kwargs)


# ==================== 0. 公司/品牌表 ====================
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="公司/品牌名称")
    slug = Column(String(100), unique=True, nullable=False, comment="URL 友好标识（用于文件夹命名）")
    description = Column(Text, comment="公司简介")
    industry = Column(String(100), comment="行业领域")
    logo = Column(String(500), comment="公司 Logo URL")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联
    products = relationship("Product", back_populates="company", lazy="dynamic")
    knowledge_docs = relationship("KnowledgeBaseDoc", back_populates="company", lazy="dynamic",
                                  foreign_keys="KnowledgeBaseDoc.company_id")

    __table_args__ = (
        Index("idx_companies_slug", "slug"),
    )


# ==================== 1. 产品信息表 ====================
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="产品名称")
    category = Column(String(100), comment="产品品类")
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, comment="所属公司")
    image = Column(String(500), comment="产品图片URL")
    tone_config = JsonCol(comment="各平台语调配置")
    forbidden_words = ArrayCol(comment="广告法敏感词")
    topic_rotation = JsonCol(comment="选题轮询状态: phase/topic_stats/last_used")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联
    company = relationship("Company", back_populates="products")
    contents = relationship("Content", back_populates="product", lazy="dynamic")
    optimization_changes = relationship("OptimizationChange", back_populates="product", lazy="dynamic")
    scheduled_tasks = relationship("ScheduledTask", back_populates="product", lazy="dynamic")
    knowledge_docs = relationship("KnowledgeBaseDoc", back_populates="product", lazy="dynamic",
                                  foreign_keys="KnowledgeBaseDoc.product_id")


# ==================== 2. 账号管理表 ====================
class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, comment="平台: xiaohongshu/zhihu/weibo/wechat/toutiao/douyin")
    account_name = Column(String(200), comment="账号名/昵称")
    account_id = Column(String(200), comment="平台账号ID")
    login_type = Column(String(20), nullable=False, comment="登录类型: api/cookie/playwright")
    auth_config = JsonCol(comment="加密的认证信息")
    session_state_path = Column(Text, comment="StorageState 文件路径")
    proxy_ip = Column(String(50), comment="绑定的代理IP")
    status = Column(String(20), default="active", comment="状态: active/expired/banned")
    last_check_at = Column(DateTime(timezone=True), comment="最后一次会话检查时间")
    next_check_at = Column(DateTime(timezone=True), comment="下次检查时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联
    publish_records = relationship("PublishRecord", back_populates="account", lazy="dynamic")

    __table_args__ = (
        Index("idx_accounts_platform", "platform"),
    )


# ==================== 3. 内容生成记录表 ====================
class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    platform = Column(String(50), nullable=False, comment="目标平台")
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    tags = ArrayCol(comment="标签列表")
    image_paths = ArrayCol(comment="MinIO 存储路径列表")
    prompt_version = Column(String(50), comment="使用的提示词版本号")
    topic_category = Column(String(30), comment="选题分类: tech_explanation/product_guide/case_study/industry_trend/pain_point/comparison/seasonal")
    generation_params = JsonCol(comment="AI 生成参数快照")
    status = Column(String(20), default="draft", comment="draft/approved/published/archived")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联
    product = relationship("Product", back_populates="contents")
    publish_records = relationship("PublishRecord", back_populates="content", lazy="dynamic")

    __table_args__ = (
        Index("idx_contents_product", "product_id"),
        Index("idx_contents_platform", "platform"),
    )


# ==================== 4. 发布记录表 ====================
class PublishRecord(Base):
    __tablename__ = "publish_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    account_id = Column(Integer, ForeignKey("platform_accounts.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(50), nullable=False)
    external_content_id = Column(String(200), comment="平台返回的内容ID（用于数据抓取）")
    publish_time = Column(DateTime(timezone=True))
    status = Column(String(20), default="pending", comment="pending/success/failed")
    error_message = Column(Text)
    publish_strategy = Column(String(20), comment="api/playwright")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联
    content = relationship("Content", back_populates="publish_records")
    account = relationship("PlatformAccount", back_populates="publish_records")
    metrics = relationship("ContentMetric", back_populates="publish_record", lazy="dynamic")

    __table_args__ = (
        Index("idx_publish_record_platform", "platform"),
    )


# ==================== 5. 数据指标表（时序数据） ====================
class ContentMetric(Base):
    __tablename__ = "content_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    publish_record_id = Column(Integer, ForeignKey("publish_records.id"), nullable=False)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    views = Column(Integer, default=0, comment="阅读量/浏览量/展现量")
    likes = Column(Integer, default=0, comment="点赞数")
    comments = Column(Integer, default=0, comment="评论数")
    shares = Column(Integer, default=0, comment="分享数")
    collects = Column(Integer, default=0, comment="收藏数")
    followers_delta = Column(Integer, default=0, comment="粉丝变化")
    raw_data = JsonCol(comment="平台原始返回数据")

    # 关联
    publish_record = relationship("PublishRecord", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("publish_record_id", "scraped_at", name="uq_metrics_record_time"),
        Index("idx_metrics_record", "publish_record_id"),
    )


# ==================== 6. 优化改动记录表 ====================
class OptimizationChange(Base):
    __tablename__ = "optimization_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    platform = Column(String(50))
    related_content_ids = ArrayCol(comment="关联的内容ID列表")

    # 改动信息
    change_type = Column(String(50), nullable=False, comment="title_style/body_style/image_style/tags/publish_time/prompt_tuning")
    issue_description = Column(Text, nullable=False, comment="发现的问题描述")
    hypothesis = Column(Text, comment="假设原因")
    action_taken = Column(Text, nullable=False, comment="执行的动作")

    # 改动详情
    before_value = JsonCol(comment="改动前（原文/原配置）")
    after_value = JsonCol(comment="改动后（新文/新配置）")
    prompt_diff = Column(Text, comment="提示词变更 diff")

    # 去重与追踪
    change_hash = Column(String(64), comment="语义哈希（用于去重）")
    is_duplicate = Column(Boolean, default=False)
    similar_to_change_id = Column(Integer, ForeignKey("optimization_changes.id"), nullable=True)

    # 效果验证
    next_publish_id = Column(Integer, comment="改动后下一次发布的内容ID")
    effect_verified = Column(Boolean, default=False)
    effect_result = Column(Text, comment="改动效果描述（数据对比结果）")

    # 审核流程
    status = Column(String(20), default="pending", comment="pending/approved/rejected/applied/verified")
    approved_by = Column(String(50))
    approved_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联
    product = relationship("Product", back_populates="optimization_changes")

    __table_args__ = (
        Index("idx_changes_product_platform", "product_id", "platform"),
        Index("idx_changes_hash", "change_hash"),
        Index("idx_changes_status", "status"),
    )


# ==================== 7. 提示词版本管理表 ====================
class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_template = Column(Text, nullable=False)
    change_log = Column(Text, comment="本次版本变更说明")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("platform", "version", name="uq_prompt_version"),
    )


# ==================== 8. 任务调度表 ====================
class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), nullable=False, comment="generate_content/publish/scrape_data/optimize")
    product_id = Column(Integer, ForeignKey("products.id"))
    platform = Column(String(50))
    cron_expression = Column(String(100), comment="cron 表达式")
    config = JsonCol(comment="任务配置")
    status = Column(String(20), default="active", comment="active/paused/completed")
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联
    product = relationship("Product", back_populates="scheduled_tasks")

    __table_args__ = (
        Index("idx_scheduled_next_run", "next_run_at"),
    )


# ==================== 9. 评论互动记录表 ====================
class CommentReply(Base):
    """记录已回复的评论，实现去重"""
    __tablename__ = "comment_replies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, comment="平台")
    account_id = Column(Integer, ForeignKey("platform_accounts.id"), nullable=False)
    publish_record_id = Column(Integer, ForeignKey("publish_records.id"), nullable=True, comment="关联发布记录")
    content_external_id = Column(String(200), comment="平台内容ID")
    comment_id = Column(String(200), nullable=False, comment="平台评论ID（用于去重）")
    commenter_name = Column(String(200), comment="评论者昵称")
    comment_text = Column(Text, nullable=False, comment="原评论内容")
    reply_text = Column(Text, nullable=False, comment="回复内容")
    ai_generated = Column(Boolean, default=True, comment="是否AI生成")
    reply_strategy = Column(String(20), default="playwright", comment="回复方式: playwright/api")
    status = Column(String(20), default="success", comment="success/failed/pending_approval")
    error_message = Column(Text)
    replied_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_by = Column(String(50), comment="审核人（手动模式时）")

    __table_args__ = (
        UniqueConstraint("platform", "comment_id", name="uq_comment_reply"),
        Index("idx_comment_reply_platform", "platform"),
        Index("idx_comment_reply_account", "account_id"),
        Index("idx_comment_reply_status", "status"),
    )


# ==================== 10. 知识库文档表 ====================
class KnowledgeBaseDoc(Base):
    """独立的知识库 MD 文档 — 可挂载到 Company 或 Product"""
    __tablename__ = "knowledge_base_docs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False, comment="文档标题")
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, comment="所属公司")
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, comment="所属产品")
    file_path = Column(String(500), comment="磁盘上 .md 文件路径（相对路径）")
    content = Column(Text, nullable=False, comment="Markdown 内容")
    category = Column(String(50), default="product", comment="分类: product/company/industry/faq/case/other")
    source = Column(String(20), default="manual", comment="来源: manual/imported/scanned")
    word_count = Column(Integer, default=0, comment="字数统计")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联
    company = relationship("Company", back_populates="knowledge_docs", foreign_keys=[company_id])
    product = relationship("Product", back_populates="knowledge_docs", foreign_keys=[product_id])

    __table_args__ = (
        Index("idx_kbdoc_company", "company_id"),
        Index("idx_kbdoc_product", "product_id"),
        Index("idx_kbdoc_category", "category"),
    )
