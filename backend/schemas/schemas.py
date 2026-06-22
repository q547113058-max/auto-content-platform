"""
Pydantic Schemas - API 请求/响应模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ==================== 产品 ====================
class ProductCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category: Optional[str] = None
    company_id: Optional[int] = Field(None, description="所属公司 ID")
    image: Optional[str] = Field(None, max_length=500, description="产品图片URL")
    tone: Optional[str] = Field(None, description="语调风格（字符串，存入 tone_config）")
    sensitive_words: Optional[str] = Field(None, description="敏感词（逗号分隔，存入 forbidden_words）")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    company_id: Optional[int] = Field(None, description="所属公司 ID")
    image: Optional[str] = Field(None, max_length=500, description="产品图片URL")
    tone: Optional[str] = Field(None, description="语调风格")
    sensitive_words: Optional[str] = Field(None, description="敏感词")


class ProductResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    image: Optional[str] = None
    tone_config: Optional[Dict[str, Any]]
    forbidden_words: Optional[List[str]]
    kb_doc_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ==================== 公司/品牌 ====================
class CompanyCreate(BaseModel):
    name: str = Field(..., max_length=200)
    slug: Optional[str] = Field(None, max_length=100, description="自动从 name 生成，无需手动填写")
    description: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    logo: Optional[str] = Field(None, max_length=500)


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    logo: Optional[str] = Field(None, max_length=500)


class CompanyResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    industry: Optional[str] = None
    logo: Optional[str] = None
    product_count: Optional[int] = 0
    doc_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ==================== 知识库文档 ====================
class KBDocCreate(BaseModel):
    title: str = Field(..., max_length=300)
    content: str = Field(..., description="Markdown 内容")
    company_id: Optional[int] = Field(None, description="所属公司 ID")
    product_id: Optional[int] = Field(None, description="所属产品 ID")
    category: Optional[str] = Field("product", max_length=50)


class KBDocUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    content: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    company_id: Optional[int] = None
    product_id: Optional[int] = None


class KBDocResponse(BaseModel):
    id: int
    title: str
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    file_path: Optional[str] = None
    category: str
    source: str
    word_count: int
    content: Optional[str] = None  # 列表时不返回，详情时返回
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KBDocListResponse(BaseModel):
    items: List[KBDocResponse]
    total: int


class KBScanRequest(BaseModel):
    """请求扫描 data/knowledge_base/ 目录"""
    path: Optional[str] = Field(None, description="扫描子目录，留空则扫描全部")


# ==================== 平台账号 ====================
class PlatformAccountCreate(BaseModel):
    platform: str = Field(..., max_length=50)
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    login_type: str = Field(..., max_length=20)
    auth_config: Optional[Any] = Field(None, description="Auth JSON — 支持 Dict 或字符串，自动解析")
    proxy_ip: Optional[str] = None

    @staticmethod
    def _parse_auth_config(v: Any) -> Optional[Dict[str, Any]]:
        """前端 textarea 发字符串 → 后端存入 JSON 列需要 dict"""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            import json
            return json.loads(v)
        return None


class PlatformAccountUpdate(BaseModel):
    """编辑时可只传要改的字段"""
    platform: Optional[str] = Field(None, max_length=50)
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    login_type: Optional[str] = Field(None, max_length=20)
    auth_config: Optional[Any] = Field(None, description="Auth JSON 字符串或 Dict，自动解析")
    proxy_ip: Optional[str] = None

    @staticmethod
    def _parse_auth_config(v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            import json
            return json.loads(v)
        return None


class PlatformAccountResponse(BaseModel):
    id: int
    platform: str
    account_name: Optional[str]
    account_id: Optional[str]
    login_type: str
    auth_config: Optional[Dict[str, Any]] = None
    session_state_path: Optional[str] = None
    proxy_ip: Optional[str]
    status: str
    last_check_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== 内容 ====================
class ContentCreate(BaseModel):
    product_id: int
    platform: str
    title: str
    body: str
    tags: Optional[List[str]] = None
    image_paths: Optional[List[str]] = None
    prompt_version: Optional[str] = None
    topic_category: Optional[str] = Field(None, description="选题分类: tech_explanation/product_guide/case_study/industry_trend/pain_point/comparison/seasonal")
    generation_params: Optional[Dict[str, Any]] = None


class ContentUpdate(BaseModel):
    """内容部分更新"""
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    topic_category: Optional[str] = None


class ContentGenerateRequest(BaseModel):
    """AI 内容生成请求"""
    product_id: Optional[int] = None                    # 纯公司模式时可为 None
    company_id: Optional[int] = None                    # 纯公司/混合模式时需传
    content_mode: str = Field(
        default="product",
        description="生成模式: product=纯产品 | company=纯公司 | mixed=公司产品混合（公司为主）"
    )
    platforms: Optional[List[str]] = None               # 留空则全平台生成
    override_prompt: Optional[str] = None               # 覆盖提示词
    topic_category: Optional[str] = Field(None, description="选题分类（留空自动推荐）")


class ContentResponse(BaseModel):
    id: int
    product_id: Optional[int] = None
    product_name: Optional[str] = None  # JOIN Product 填充
    company_id: Optional[int] = None
    company_name: Optional[str] = None  # JOIN Company 填充
    content_mode: Optional[str] = "product"
    platform: str
    title: str
    body: str
    tags: Optional[List[str]]
    image_paths: Optional[List[str]]
    prompt_version: Optional[str]
    topic_category: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ContentListResponse(BaseModel):
    """分页列表响应"""
    items: List[ContentResponse]
    total: int
    page: int
    page_size: int


class ContentBatchRequest(BaseModel):
    """批量操作请求"""
    ids: List[int]
    status: Optional[str] = None  # 仅 batch-status 需要


# ==================== 发布记录 ====================
class PublishRequest(BaseModel):
    content_id: int
    account_id: int
    publish_strategy: Optional[str] = None  # auto 则自动选择


class PublishResponse(BaseModel):
    id: int
    content_id: Optional[int] = None
    content_title: Optional[str] = None
    platform: str
    status: str
    external_id: Optional[str] = None
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    publish_strategy: Optional[str] = None

    model_config = {"from_attributes": True}


# ==================== 数据指标 ====================
class ContentMetricResponse(BaseModel):
    id: int
    publish_record_id: int
    scraped_at: datetime
    views: int
    likes: int
    comments: int
    shares: int
    collects: int
    followers_delta: int

    class Config:
        from_attributes = True


class MetricSummary(BaseModel):
    """数据分析摘要"""
    platform: str
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    total_collects: int
    avg_engagement_rate: float  # 互动率
    content_count: int


# ==================== 优化改动 ====================
class OptimizationChangeCreate(BaseModel):
    product_id: int
    platform: str
    change_type: str
    issue_description: str
    hypothesis: Optional[str] = None
    action_taken: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Optional[Dict[str, Any]] = None
    prompt_diff: Optional[str] = None


class OptimizationChangeResponse(BaseModel):
    id: int
    product_id: int
    platform: str
    change_type: str
    issue_description: str
    hypothesis: Optional[str]
    action_taken: str
    is_duplicate: bool
    effect_verified: bool
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 提示词版本 ====================
class PromptVersionCreate(BaseModel):
    platform: str
    version: str
    system_prompt: str
    user_template: str
    change_log: Optional[str] = None


class PromptVersionResponse(BaseModel):
    id: int
    platform: str
    version: str
    system_prompt: str
    user_template: str
    change_log: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 任务调度 ====================
class ScheduledTaskCreate(BaseModel):
    task_type: str
    product_id: Optional[int] = None
    platform: Optional[str] = None
    cron_expression: str
    config: Optional[Dict[str, Any]] = None


class ScheduledTaskResponse(BaseModel):
    id: int
    task_type: str
    product_id: Optional[int]
    platform: Optional[str]
    cron_expression: str
    status: str
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== 会话管理 ====================
class SessionStatusResponse(BaseModel):
    platform: str
    account_id: str
    status: str  # active / expired / unknown
    last_check_at: Optional[datetime]
    remaining_hours: Optional[int]  # Cookie 剩余有效时间


class SessionCheckRequest(BaseModel):
    platforms: Optional[List[str]] = None  # 留空检查全部
    account_ids: Optional[List[int]] = None


# ==================== 通用 ====================
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
